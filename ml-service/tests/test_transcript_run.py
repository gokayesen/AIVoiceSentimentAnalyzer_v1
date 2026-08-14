"""Tests for the transcript-generation RQ job (Story 1.4, AC 1,2,4,5,6,7,8)."""

from __future__ import annotations

import uuid

from app import db
from app.pipeline.transcript.run import run_transcript
from app.pipeline.transcript.stt import TurnResult


def _seed_segments(call_id: str, boundaries: list[tuple[float, float]]) -> None:
    conn = db.get_connection()
    try:
        segments = [
            (str(uuid.uuid4()), idx, start, end) for idx, (start, end) in enumerate(boundaries)
        ]
        db.insert_timeline_segments(conn, call_id=call_id, segments=segments)
        # run_transcript is always chained after run_acoustic (Task 7), which
        # never changes Call.status away from "processing" on success —
        # simulate that realistic precondition.
        db.set_call_status(conn, call_id=call_id, status="processing")
    finally:
        conn.close()


def _raise(*_args, **_kwargs):
    raise RuntimeError("boom")


def test_run_transcript_persists_ordered_turns_with_words(make_call, call_row, fixtures_dir):
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "speech.wav")
    _seed_segments(call_id, [(0.0, 1.5), (1.5, 3.0)])

    run_transcript(call_id)

    conn = db.get_connection()
    try:
        turns = db.get_transcript_turns(conn, call_id=call_id)
        words = [db.get_transcript_words(conn, turn_id=t["id"]) for t in turns]
    finally:
        conn.close()

    assert len(turns) >= 1
    assert [t["turn_index"] for t in turns] == list(range(len(turns)))
    for t in turns:
        assert t["text"]
        assert t["start_time"] <= t["end_time"]
    assert any(len(w) >= 1 for w in words)

    # AC 6: transcript generation alone never completes (or fails) a Call —
    # Call.status is left exactly as run_acoustic left it.
    assert call_row(call_id)["status"] == "processing"


def test_transcript_turn_has_no_segment_id_column(make_call, fixtures_dir):
    """AC 5 / AD-11 schema-shape regression guard: TranscriptTurn must relate
    to TimelineSegment only via time-range overlap, never a scalar FK."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "speech.wav")
    _seed_segments(call_id, [(0.0, 1.5)])

    run_transcript(call_id)

    conn = db.get_connection()
    try:
        columns = {row[1] for row in conn.execute("PRAGMA table_info(TranscriptTurn)")}
    finally:
        conn.close()

    assert "segment_id" not in columns


def test_run_transcript_skips_zero_width_segment_but_keeps_others(
    make_call, call_row, fixtures_dir
):
    """A degenerate segment must not abort the whole Call's transcript —
    unlike run_acoustic (which must fail hard, AD-1), transcript generation
    simply skips it and continues with the remaining valid segments."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "speech.wav")
    _seed_segments(call_id, [(1.0, 1.0), (0.0, 1.5)])

    run_transcript(call_id)

    assert call_row(call_id)["status"] == "processing"
    conn = db.get_connection()
    try:
        turns = db.get_transcript_turns(conn, call_id=call_id)
    finally:
        conn.close()
    assert len(turns) >= 1


def test_run_transcript_failure_does_not_fail_the_call(monkeypatch, make_call, call_row, fixtures_dir):
    """AC 4/AD-1: unlike run_ingest/run_acoustic, a transcript-stage failure
    must never set Call.status = "failed" and must not propagate/raise — the
    RQ job completes normally, leaving zero TranscriptTurn rows."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "speech.wav")
    _seed_segments(call_id, [(0.0, 1.5)])

    monkeypatch.setattr("app.pipeline.transcript.run.transcribe_segment", _raise)

    result = run_transcript(call_id)  # must not raise

    assert result is None
    assert call_row(call_id)["status"] == "processing"

    conn = db.get_connection()
    try:
        turns = db.get_transcript_turns(conn, call_id=call_id)
    finally:
        conn.close()
    assert turns == []


def test_run_transcript_skips_only_the_segment_that_fails_to_transcribe(
    monkeypatch, make_call, call_row, fixtures_dir
):
    """Code review (2026-08-13): one segment's transcription failure must
    not discard other segments' already-computed turns for the whole Call."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "speech.wav")
    _seed_segments(call_id, [(0.0, 1.5), (1.5, 3.0)])

    call_count = {"n": 0}

    def _flaky(_waveform, *, absolute_offset_seconds):
        call_count["n"] += 1
        if call_count["n"] == 1:
            raise RuntimeError("boom")
        return [
            TurnResult(
                text="ok",
                start_time=absolute_offset_seconds,
                end_time=absolute_offset_seconds + 1.0,
                words=[],
            )
        ]

    monkeypatch.setattr("app.pipeline.transcript.run.transcribe_segment", _flaky)

    run_transcript(call_id)

    assert call_row(call_id)["status"] == "processing"
    conn = db.get_connection()
    try:
        turns = db.get_transcript_turns(conn, call_id=call_id)
    finally:
        conn.close()
    assert len(turns) == 1
    assert turns[0]["text"] == "ok"


def test_run_transcript_missing_audio_does_not_fail_the_call(make_call, call_row):
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=None)
    _seed_segments(call_id, [(0.0, 1.0)])

    run_transcript(call_id)  # must not raise

    assert call_row(call_id)["status"] == "processing"


def test_run_transcript_success_enqueues_text_sentiment_job_with_correct_path_and_call_id(
    make_call, fixtures_dir, fake_text_sentiment_queue
):
    """Story 1.5/AD-13 stage-chaining: a successful run_transcript must
    enqueue exactly one text-sentiment job, referencing run_text_sentiment
    by its exact import-path string (never a direct import, AD-7) — mirrors
    Story 1.4's own acoustic->transcript enqueue test."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "speech.wav")
    _seed_segments(call_id, [(0.0, 1.5), (1.5, 3.0)])

    run_transcript(call_id)

    jobs = fake_text_sentiment_queue.jobs
    assert len(jobs) == 1
    assert jobs[0].func_name == "app.pipeline.transcript.sentiment_run.run_text_sentiment"
    assert jobs[0].args == (call_id,)


def test_run_transcript_text_sentiment_enqueue_failure_does_not_fail_the_call(
    monkeypatch, make_call, call_row, fixtures_dir
):
    """Code review precedent (Story 1.4): a downstream text-sentiment-queue
    enqueue failure (e.g. Redis unreachable) must not be misreported as a
    transcript-generation failure — the already-persisted TranscriptTurn
    rows stand."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "speech.wav")
    _seed_segments(call_id, [(0.0, 1.5), (1.5, 3.0)])

    class _BrokenQueue:
        def enqueue(self, *args, **kwargs):
            raise ConnectionError("redis unreachable")

    import app.queue as queue_module

    monkeypatch.setattr(queue_module, "get_text_sentiment_queue", lambda: _BrokenQueue())

    run_transcript(call_id)  # must not raise

    assert call_row(call_id)["status"] == "processing"
    conn = db.get_connection()
    try:
        turns = db.get_transcript_turns(conn, call_id=call_id)
    finally:
        conn.close()
    assert len(turns) >= 1


def test_run_transcript_text_sentiment_enqueue_failure_also_enqueues_fusion(
    monkeypatch, make_call, fixtures_dir, fake_fusion_queue
):
    """Story 1.6 fan-in (AD-1, AC 1): if text-sentiment never even gets the
    chance to start, its own fusion-enqueue call sites will never fire —
    this except block must enqueue fusion directly as the fallback."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "speech.wav")
    _seed_segments(call_id, [(0.0, 1.5), (1.5, 3.0)])

    class _BrokenQueue:
        def enqueue(self, *args, **kwargs):
            raise ConnectionError("redis unreachable")

    import app.queue as queue_module

    monkeypatch.setattr(queue_module, "get_text_sentiment_queue", lambda: _BrokenQueue())

    run_transcript(call_id)  # must not raise

    jobs = fake_fusion_queue.jobs
    assert len(jobs) == 1
    assert jobs[0].func_name == "app.pipeline.fusion.run.run_fusion"
    assert jobs[0].args == (call_id,)


def test_run_transcript_internal_failure_still_enqueues_fusion(
    make_call, fake_fusion_queue
):
    """Story 1.6 fan-in (AD-1, AC 1): a failure that happens before the
    per-segment loop (e.g. missing audio — `transcribe_segment` failures are
    caught per-segment and never reach here, see
    `test_run_transcript_skips_only_the_segment_that_fails_to_transcribe`)
    hits run_transcript's own outer except block, which never reaches the
    text-sentiment enqueue call at all — fusion must be enqueued from here
    instead, otherwise this Call (whose acoustic signal is still valid)
    would never reach Call.status = complete."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=None)
    _seed_segments(call_id, [(0.0, 1.0)])

    run_transcript(call_id)  # must not raise

    jobs = fake_fusion_queue.jobs
    assert len(jobs) == 1
    assert jobs[0].func_name == "app.pipeline.fusion.run.run_fusion"
    assert jobs[0].args == (call_id,)
