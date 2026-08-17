"""Tests for the transcript-generation RQ job (Story 1.4, AC 1,2,4,5,6,7,8)."""

from __future__ import annotations

import uuid

import torch

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


def _canned_turn(_waveform, *, absolute_offset_seconds):
    return [
        TurnResult(
            text="ok",
            start_time=absolute_offset_seconds,
            end_time=absolute_offset_seconds + 1.0,
            words=[],
        )
    ]


def test_run_transcript_persists_speaker_a_when_channel_0_is_louder(
    monkeypatch, make_call, fixtures_dir
):
    """Story 3.1 (AC1, AC2): a stereo Call whose channel 0 carries the
    speech-bearing energy gets its turn labeled "Speaker A"."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "stereo_channel0_louder.wav")
    _seed_segments(call_id, [(0.0, 1.5)])

    monkeypatch.setattr("app.pipeline.transcript.run.transcribe_segment", _canned_turn)

    run_transcript(call_id)

    conn = db.get_connection()
    try:
        turns = db.get_transcript_turns(conn, call_id=call_id)
    finally:
        conn.close()
    assert len(turns) == 1
    assert turns[0]["speaker_label"] == "Speaker A"
    assert turns[0]["speaker_channel_index"] == 0


def test_run_transcript_persists_speaker_b_when_channel_1_is_louder(
    monkeypatch, make_call, fixtures_dir
):
    """Story 3.1 (AC1, AC2): mirror of the Speaker A case above, channel 1
    carrying the energy instead."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "stereo_channel1_louder.wav")
    _seed_segments(call_id, [(0.0, 1.5)])

    monkeypatch.setattr("app.pipeline.transcript.run.transcribe_segment", _canned_turn)

    run_transcript(call_id)

    conn = db.get_connection()
    try:
        turns = db.get_transcript_turns(conn, call_id=call_id)
    finally:
        conn.close()
    assert len(turns) == 1
    assert turns[0]["speaker_label"] == "Speaker B"
    assert turns[0]["speaker_channel_index"] == 1


def test_run_transcript_mono_call_leaves_speaker_label_none_when_unattributed(
    monkeypatch, make_call, fixtures_dir
):
    """Story 3.1 (AC6): stereo attribution never runs for a mono Call
    (speaker_channel_index stays None regardless of diarization outcome).
    Story 3.2: diarization itself is monkeypatched here to return "no
    attribution" for the turn, proving that outcome leaves speaker_label
    None too — a real diarization result is covered separately below."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "mono.wav")
    _seed_segments(call_id, [(0.0, 1.5)])

    monkeypatch.setattr("app.pipeline.transcript.run.transcribe_segment", _canned_turn)
    monkeypatch.setattr(
        "app.pipeline.transcript.run.diarize_mono_turns", lambda _waveform, turns: [None] * len(turns)
    )

    run_transcript(call_id)

    conn = db.get_connection()
    try:
        turns = db.get_transcript_turns(conn, call_id=call_id)
    finally:
        conn.close()
    assert len(turns) == 1
    assert turns[0]["speaker_label"] is None
    assert turns[0]["speaker_channel_index"] is None


def test_run_transcript_mono_call_persists_real_diarization_result(
    monkeypatch, make_call, fixtures_dir
):
    """Story 3.2 (AC1, AC4, AC5, AC6): a mono Call whose diarization succeeds
    gets its turn's speaker_label/speaker_cluster_id/speaker_confidence
    persisted from diarize_mono_turns's result."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "mono.wav")
    _seed_segments(call_id, [(0.0, 1.5)])

    monkeypatch.setattr("app.pipeline.transcript.run.transcribe_segment", _canned_turn)
    monkeypatch.setattr(
        "app.pipeline.transcript.run.diarize_mono_turns",
        lambda _waveform, turns: [("SPEAKER_00", "Speaker A", 0.9)] * len(turns),
    )

    run_transcript(call_id)

    conn = db.get_connection()
    try:
        turns = db.get_transcript_turns(conn, call_id=call_id)
    finally:
        conn.close()
    assert len(turns) == 1
    assert turns[0]["speaker_label"] == "Speaker A"
    assert turns[0]["speaker_channel_index"] is None
    assert turns[0]["speaker_cluster_id"] == "SPEAKER_00"
    assert turns[0]["speaker_confidence"] == 0.9


def test_run_transcript_stereo_call_never_invokes_mono_diarization(
    monkeypatch, make_call, fixtures_dir
):
    """Story 3.2 (AC3): stereo input never invokes WhisperX/diarization —
    the channel_count == 1 gate, not != 2, so a stereo Call must never reach
    diarize_mono_turns at all.

    Code review (2026-08-17): asserts the call count directly rather than
    only checking speaker_label — a prior version of this test monkeypatched
    diarize_mono_turns to raise and only asserted speaker_label == "Speaker
    A", which is fully determined by the independent stereo path and would
    have passed identically even if the channel_count == 1 gate regressed
    and wrongly invoked diarization (the exception would be silently
    absorbed without touching the already-stereo-set speaker_label) — that
    version provided no actual regression protection for AC3."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "stereo_channel0_louder.wav")
    _seed_segments(call_id, [(0.0, 1.5)])

    calls: list = []

    def _spy(mono_waveform, turns):
        calls.append(turns)
        return [None] * len(turns)

    monkeypatch.setattr("app.pipeline.transcript.run.transcribe_segment", _canned_turn)
    monkeypatch.setattr("app.pipeline.transcript.run.diarize_mono_turns", _spy)

    run_transcript(call_id)

    assert calls == []

    conn = db.get_connection()
    try:
        turns = db.get_transcript_turns(conn, call_id=call_id)
    finally:
        conn.close()
    assert len(turns) == 1
    assert turns[0]["speaker_label"] == "Speaker A"


def test_run_transcript_diarization_failure_leaves_turns_unattributed_but_completes(
    monkeypatch, make_call, fixtures_dir
):
    """Story 3.2 (AD-1's governing pattern): a diarization failure (missing/
    invalid HF_TOKEN, model load error, etc.) must never fail the Call — the
    turn is persisted unattributed instead, same as Story 3.1's per-turn
    stereo failure isolation."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "mono.wav")
    _seed_segments(call_id, [(0.0, 1.5)])

    monkeypatch.setattr("app.pipeline.transcript.run.transcribe_segment", _canned_turn)
    monkeypatch.setattr("app.pipeline.transcript.run.diarize_mono_turns", _raise)

    run_transcript(call_id)

    conn = db.get_connection()
    try:
        turns = db.get_transcript_turns(conn, call_id=call_id)
    finally:
        conn.close()
    assert len(turns) == 1
    assert turns[0]["speaker_label"] is None
    assert turns[0]["speaker_cluster_id"] is None
    assert turns[0]["speaker_confidence"] is None


def test_run_transcript_attributes_every_turn_in_a_multi_turn_stereo_call(
    monkeypatch, make_call, fixtures_dir
):
    """Code review (2026-08-17), Story 3.1 AC4: attribution must apply to
    every TranscriptTurn in the Call, not just the first — regression guard
    against a bug that only attributes the first turn/segment."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "stereo_channel0_louder.wav")
    _seed_segments(call_id, [(0.0, 1.0), (1.0, 2.0), (2.0, 3.0)])

    monkeypatch.setattr("app.pipeline.transcript.run.transcribe_segment", _canned_turn)

    run_transcript(call_id)

    conn = db.get_connection()
    try:
        turns = db.get_transcript_turns(conn, call_id=call_id)
    finally:
        conn.close()
    assert len(turns) == 3
    assert all(t["speaker_label"] == "Speaker A" for t in turns)
    assert all(t["speaker_channel_index"] == 0 for t in turns)


def test_run_transcript_three_channel_call_leaves_speaker_label_none(
    monkeypatch, make_call
):
    """Code review (2026-08-17), deferred-work.md (Story 1.2 review): the
    channel_count == 2 gate must not silently become >= 2 — a >2-channel
    Call falls through to the same unattributed behavior as mono, never
    guessed at. Uses a monkeypatched load_mono_waveform (synthetic 3-channel
    tensor) rather than a new audio fixture, since only the channel count
    matters here."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=None)
    _seed_segments(call_id, [(0.0, 1.0)])

    total_samples = 32000  # 2s at VAD_SAMPLE_RATE — plenty for a 1.0s segment + margin
    fake_raw_waveform = torch.zeros(3, total_samples)
    fake_mono_waveform = torch.zeros(total_samples)

    monkeypatch.setattr(
        "app.pipeline.transcript.run.load_mono_waveform",
        lambda _call_id: (fake_raw_waveform, fake_mono_waveform, 16000),
    )
    monkeypatch.setattr("app.pipeline.transcript.run.transcribe_segment", _canned_turn)

    run_transcript(call_id)

    conn = db.get_connection()
    try:
        turns = db.get_transcript_turns(conn, call_id=call_id)
    finally:
        conn.close()
    assert len(turns) == 1
    assert turns[0]["speaker_label"] is None
    assert turns[0]["speaker_channel_index"] is None
    # Code review (2026-08-17): also cover Story 3.2's two new columns, same
    # as the mono diarization-failure test does — a >2-channel Call must
    # stay unattributed on every speaker field, not just the stereo-path ones.
    assert turns[0]["speaker_cluster_id"] is None
    assert turns[0]["speaker_confidence"] is None


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
