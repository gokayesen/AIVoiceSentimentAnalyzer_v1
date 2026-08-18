"""Tests for the acoustic-analysis RQ job (Story 1.3, AC 1,2,5,6,7,8,9,11)."""

from __future__ import annotations

import uuid

import pytest

from app import config, db
from app.pipeline.acoustic.run import AcousticSanityFloorError, run_acoustic


def _seed_segments(call_id: str, boundaries: list[tuple[float, float]]) -> None:
    conn = db.get_connection()
    try:
        segments = [
            (str(uuid.uuid4()), idx, start, end) for idx, (start, end) in enumerate(boundaries)
        ]
        db.insert_timeline_segments(conn, call_id=call_id, segments=segments)
        # run_acoustic is always chained after run_ingest (Task 8), which
        # already wrote status="processing" at its own job start (AD-13) —
        # simulate that realistic precondition rather than the fixture's
        # raw "queued" insert.
        db.set_call_status(conn, call_id=call_id, status="processing")
    finally:
        conn.close()


def test_run_acoustic_persists_emotion_confidence_and_evidence_per_segment(
    make_call, call_row, timeline_segments, acoustic_evidence_rows, fixtures_dir
):
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "speech.wav")
    _seed_segments(call_id, [(0.0, 1.5), (1.5, 3.0)])

    run_acoustic(call_id)

    segments = timeline_segments(call_id)
    assert len(segments) == 2
    for s in segments:
        assert s["acoustic_emotion"] is not None
        assert s["acoustic_confidence"] is not None
        assert 0.0 <= s["acoustic_confidence"] <= 1.0

    evidence = acoustic_evidence_rows(call_id)
    assert len(evidence) == 2
    assert {e["segment_id"] for e in evidence} == {s["id"] for s in segments}

    # AC 9: acoustic analysis alone never completes a Call.
    assert call_row(call_id)["status"] == "processing"


def test_run_acoustic_sanity_floor_failure_fails_whole_call_atomically(
    monkeypatch, make_call, call_row, timeline_segments, acoustic_evidence_rows, fixtures_dir
):
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "speech.wav")
    _seed_segments(call_id, [(0.0, 1.5), (1.5, 3.0)])

    # Force every segment's classification below the sanity floor.
    monkeypatch.setattr(
        "app.pipeline.acoustic.run.classify_segment", lambda waveform, sr: ("neu", 0.01)
    )

    with pytest.raises(AcousticSanityFloorError):
        run_acoustic(call_id)

    assert call_row(call_id)["status"] == "failed"

    # AC 6/7: no partial results — the sanity-floor breach must not leave
    # some segments' evidence/emotion committed while others weren't reached.
    segments = timeline_segments(call_id)
    assert all(s["acoustic_emotion"] is None for s in segments)
    assert all(s["acoustic_confidence"] is None for s in segments)
    assert acoustic_evidence_rows(call_id) == []


def test_run_acoustic_zero_width_segment_fails_the_call(make_call, call_row, fixtures_dir):
    """Code review (2026-08-13): a zero/negative-width segment (e.g. a VAD
    boundary-rounding edge case) must fail the Call outright rather than
    silently feeding an empty slice into feature extraction/classification,
    which would otherwise produce a fabricated NaN energy_rms_mean."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "speech.wav")
    _seed_segments(call_id, [(1.0, 1.0)])

    with pytest.raises(AcousticSanityFloorError):
        run_acoustic(call_id)

    assert call_row(call_id)["status"] == "failed"


def test_run_acoustic_missing_audio_fails_the_call(make_call, call_row):
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=None)
    _seed_segments(call_id, [(0.0, 1.0)])

    with pytest.raises(FileNotFoundError):
        run_acoustic(call_id)

    assert call_row(call_id)["status"] == "failed"


def test_run_acoustic_success_enqueues_transcript_job_with_correct_path_and_call_id(
    make_call, fixtures_dir, fake_transcript_queue
):
    """Story 1.4/AD-13 stage-chaining: a successful run_acoustic must enqueue
    exactly one transcript job, referencing run_transcript by its exact
    import-path string (never a direct import, AD-7) and passing the same
    call_id — mirrors Story 1.3's ingest->acoustic enqueue test. Also asserts
    the job's timeout is explicitly overridden to
    config.TRANSCRIPT_JOB_TIMEOUT_SECONDS (fixed 2026-08-18: RQ's 180s
    default was too low for this specific job too — see config.py's comment)
    rather than silently falling back to RQ's 180s class default."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "speech.wav")
    _seed_segments(call_id, [(0.0, 1.5), (1.5, 3.0)])

    run_acoustic(call_id)

    jobs = fake_transcript_queue.jobs
    assert len(jobs) == 1
    assert jobs[0].func_name == "app.pipeline.transcript.run.run_transcript"
    assert jobs[0].args == (call_id,)
    assert jobs[0].timeout == config.TRANSCRIPT_JOB_TIMEOUT_SECONDS


def test_run_acoustic_transcript_enqueue_failure_does_not_fail_the_call(
    monkeypatch, make_call, call_row, timeline_segments, acoustic_evidence_rows, fixtures_dir
):
    """Code review (2026-08-13): a downstream transcript-queue enqueue
    failure (e.g. Redis unreachable) must not roll back or fail an
    already-successful, already-committed acoustic analysis."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "speech.wav")
    _seed_segments(call_id, [(0.0, 1.5), (1.5, 3.0)])

    class _BrokenQueue:
        def enqueue(self, *args, **kwargs):
            raise ConnectionError("redis unreachable")

    import app.queue as queue_module

    monkeypatch.setattr(queue_module, "get_transcript_queue", lambda: _BrokenQueue())

    run_acoustic(call_id)  # must not raise

    assert call_row(call_id)["status"] == "processing"
    segments = timeline_segments(call_id)
    assert all(s["acoustic_emotion"] is not None for s in segments)
    assert acoustic_evidence_rows(call_id) != []


def test_run_acoustic_transcript_enqueue_failure_also_enqueues_fusion(
    monkeypatch, make_call, fixtures_dir, fake_fusion_queue
):
    """Story 1.6 fan-in (AD-1, AC 1): if the transcript stage never even
    gets the chance to start, none of transcript/text-sentiment's own
    fusion-enqueue call sites will ever fire — run_acoustic's own
    transcript-enqueue-failure except block must enqueue fusion directly as
    the fallback, so this Call still reaches Call.status = complete
    eventually."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "speech.wav")
    _seed_segments(call_id, [(0.0, 1.5), (1.5, 3.0)])

    class _BrokenQueue:
        def enqueue(self, *args, **kwargs):
            raise ConnectionError("redis unreachable")

    import app.queue as queue_module

    monkeypatch.setattr(queue_module, "get_transcript_queue", lambda: _BrokenQueue())

    run_acoustic(call_id)  # must not raise

    jobs = fake_fusion_queue.jobs
    assert len(jobs) == 1
    assert jobs[0].func_name == "app.pipeline.fusion.run.run_fusion"
    assert jobs[0].args == (call_id,)
