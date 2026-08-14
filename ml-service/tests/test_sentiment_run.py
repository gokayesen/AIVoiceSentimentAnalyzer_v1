"""Tests for the transcript-sentiment RQ job (Story 1.5, AC 1,2,3,4,5,6,7,8)."""

from __future__ import annotations

import json
import uuid

from app import db
from app.pipeline.transcript.keywords import extract_keywords
from app.pipeline.transcript.run import run_transcript
from app.pipeline.transcript.sentiment_run import run_text_sentiment

_KNOWN_POLARITIES = {"negative", "mixed", "positive", "neutral"}


def _seed_segments(call_id: str, boundaries: list[tuple[float, float]]) -> None:
    conn = db.get_connection()
    try:
        segments = [
            (str(uuid.uuid4()), idx, start, end) for idx, (start, end) in enumerate(boundaries)
        ]
        db.insert_timeline_segments(conn, call_id=call_id, segments=segments)
        db.set_call_status(conn, call_id=call_id, status="processing")
    finally:
        conn.close()


def _seed_transcript(call_id: str, fixtures_dir) -> None:
    """Real end-to-end input: run the actual Story 1.4 STT stage against the
    real speech fixture to get real `TranscriptTurn` rows, same
    fixture-chaining approach as this story's Dev Notes recommend."""
    _seed_segments(call_id, [(0.0, 1.5), (1.5, 3.0)])
    run_transcript(call_id)


def _seed_turns_directly(call_id: str, texts: list[str]) -> None:
    """Code review (2026-08-14): inserts `TranscriptTurn` rows directly via
    `db.persist_transcript_turns`, bypassing both VAD and real STT — used by
    the deterministic, mocked happy-path test below so it doesn't depend on
    real transformer inference or a network-downloaded audio fixture. Also
    sets Call.status = "processing" (mirrors _seed_segments' realistic
    precondition — make_call alone leaves a Call at "queued")."""
    conn = db.get_connection()
    try:
        turns = [
            (str(uuid.uuid4()), call_id, idx, float(idx), float(idx) + 1.0, text)
            for idx, text in enumerate(texts)
        ]
        db.persist_transcript_turns(conn, turns=turns, words=[])
        db.set_call_status(conn, call_id=call_id, status="processing")
    finally:
        conn.close()


def test_run_text_sentiment_persists_valid_results_for_every_turn(make_call, call_row, fixtures_dir):
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "speech.wav")
    _seed_transcript(call_id, fixtures_dir)

    conn = db.get_connection()
    try:
        turns_before = db.get_transcript_turns(conn, call_id=call_id)
    finally:
        conn.close()
    assert len(turns_before) >= 1  # sanity: the real STT fixture produced turns

    run_text_sentiment(call_id)

    conn = db.get_connection()
    try:
        turns = db.get_transcript_turns(conn, call_id=call_id)
    finally:
        conn.close()

    assert len(turns) == len(turns_before)
    for turn in turns:
        assert turn["text_sentiment"] in _KNOWN_POLARITIES
        assert turn["text_emotion"]
        assert 0.0 <= turn["text_confidence"] <= 1.0
        # Code review (2026-08-14): assert the persisted keywords actually
        # match what extract_keywords produces for this turn's real text —
        # not just "is valid JSON" (YAKE is deterministic, so recomputing
        # here is a legitimate equality check, not a flaky re-run).
        assert json.loads(turn["text_keywords"]) == extract_keywords(turn["text"])

    # AC 6: transcript-sentiment analysis alone never completes (or fails) a
    # Call — Call.status is left exactly as run_transcript left it.
    assert call_row(call_id)["status"] == "processing"


def test_run_text_sentiment_persists_mocked_results_deterministically(monkeypatch, make_call, call_row):
    """Code review (2026-08-14): a fast, deterministic unit test of
    run_text_sentiment's persistence logic that mocks both the classifier
    and the keyword extractor — complements (does not replace) the
    real-model integration test above, which depends on real transformer
    inference and is therefore slower and implicitly stable-output-
    dependent."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=None)
    _seed_turns_directly(call_id, ["I love this product!", "This is terrible."])

    monkeypatch.setattr(
        "app.pipeline.transcript.sentiment_run.analyze_turn_text",
        lambda _text: ("joy", 0.87),
    )
    monkeypatch.setattr(
        "app.pipeline.transcript.sentiment_run.extract_keywords",
        lambda _text: ["mocked", "keyword"],
    )

    run_text_sentiment(call_id)

    conn = db.get_connection()
    try:
        turns = db.get_transcript_turns(conn, call_id=call_id)
    finally:
        conn.close()

    assert len(turns) == 2
    for turn in turns:
        assert turn["text_emotion"] == "happy"
        assert turn["text_sentiment"] == "positive"
        assert turn["text_confidence"] == 0.87
        assert json.loads(turn["text_keywords"]) == ["mocked", "keyword"]
    assert call_row(call_id)["status"] == "processing"


def test_run_text_sentiment_success_enqueues_fusion_job(
    make_call, fixtures_dir, fake_fusion_queue
):
    """Story 1.6/AD-13 stage-chaining: a run_text_sentiment success (turns
    persisted, even zero of them) must enqueue exactly one fusion job,
    referencing run_fusion by its exact import-path string (never a direct
    import, AD-7) — mirrors Story 1.5's own transcript->text-sentiment
    enqueue test."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "speech.wav")
    _seed_transcript(call_id, fixtures_dir)

    run_text_sentiment(call_id)

    jobs = fake_fusion_queue.jobs
    assert len(jobs) == 1
    assert jobs[0].func_name == "app.pipeline.fusion.run.run_fusion"
    assert jobs[0].args == (call_id,)


def test_run_text_sentiment_internal_failure_still_enqueues_fusion(
    monkeypatch, make_call, fixtures_dir, fake_fusion_queue
):
    """Story 1.6 fan-in (AD-1, AC 1): this path never reaches the fusion
    enqueue call in the success branch, so fusion must be enqueued from
    run_text_sentiment's own outer except block instead — otherwise this
    Call (whose acoustic signal is still valid) would never reach
    Call.status = complete."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "speech.wav")
    _seed_transcript(call_id, fixtures_dir)

    def _raise(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.pipeline.transcript.sentiment_run.db.get_transcript_turns", _raise)

    run_text_sentiment(call_id)  # must not raise

    jobs = fake_fusion_queue.jobs
    assert len(jobs) == 1
    assert jobs[0].func_name == "app.pipeline.fusion.run.run_fusion"
    assert jobs[0].args == (call_id,)


def test_run_text_sentiment_empty_transcript_is_a_noop(make_call, call_row):
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=None)
    _seed_segments(call_id, [(0.0, 1.0)])
    # No run_transcript call — zero TranscriptTurn rows exist for this Call.

    run_text_sentiment(call_id)  # must not raise

    assert call_row(call_id)["status"] == "processing"


def test_run_text_sentiment_failure_does_not_fail_the_call(monkeypatch, make_call, call_row, fixtures_dir):
    """AC 6/AD-1: a transcript-sentiment-stage failure must never set
    Call.status = "failed" and must not propagate/raise."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "speech.wav")
    _seed_transcript(call_id, fixtures_dir)

    def _raise(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.pipeline.transcript.sentiment_run.db.get_transcript_turns", _raise)

    result = run_text_sentiment(call_id)  # must not raise

    assert result is None
    assert call_row(call_id)["status"] == "processing"


def test_run_text_sentiment_skips_only_the_turn_that_fails_to_analyze(
    monkeypatch, make_call, call_row, fixtures_dir
):
    """One turn's analysis failure must not discard other turns' already-
    computed results for the whole Call."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "speech.wav")
    _seed_transcript(call_id, fixtures_dir)

    conn = db.get_connection()
    try:
        turns_before = db.get_transcript_turns(conn, call_id=call_id)
    finally:
        conn.close()
    assert len(turns_before) >= 1

    call_count = {"n": 0}

    def _flaky(_text):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("boom")
        return "joy", 0.9

    monkeypatch.setattr("app.pipeline.transcript.sentiment_run.analyze_turn_text", _flaky)

    run_text_sentiment(call_id)

    conn = db.get_connection()
    try:
        turns = db.get_transcript_turns(conn, call_id=call_id)
    finally:
        conn.close()

    analyzed = [t for t in turns if t["text_sentiment"] is not None]
    skipped = [t for t in turns if t["text_sentiment"] is None]
    assert len(analyzed) == len(turns_before) - 1
    assert len(skipped) == 1


def test_run_text_sentiment_keyword_failure_does_not_discard_sentiment_result(
    monkeypatch, make_call, call_row
):
    """Code review (2026-08-14): a keyword-extraction-only failure must not
    discard an already-successful sentiment/emotion result for that turn —
    keywords are isolated in their own try/except, separate from
    analyze_turn_text."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=None)
    _seed_turns_directly(call_id, ["some content-bearing turn text"])

    monkeypatch.setattr(
        "app.pipeline.transcript.sentiment_run.analyze_turn_text",
        lambda _text: ("joy", 0.9),
    )

    def _raise(_text):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.pipeline.transcript.sentiment_run.extract_keywords", _raise)

    run_text_sentiment(call_id)

    conn = db.get_connection()
    try:
        turns = db.get_transcript_turns(conn, call_id=call_id)
    finally:
        conn.close()

    assert len(turns) == 1
    assert turns[0]["text_sentiment"] == "positive"
    assert turns[0]["text_emotion"] == "happy"
    assert json.loads(turns[0]["text_keywords"]) == []
    assert call_row(call_id)["status"] == "processing"
