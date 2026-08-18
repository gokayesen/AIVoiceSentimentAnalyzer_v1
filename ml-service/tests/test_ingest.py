"""Tests for the ingest RQ job — Story 1.2 (Async Processing Lifecycle & Audio Ingest).

Runs against a real temp SQLite DB (conftest's isolated STORAGE_DIR/DB_PATH),
not mocks, so the actual DDL/writes are exercised — same discipline as
web-api/tests/test_upload.py (Story 1.1).
"""

from __future__ import annotations

import uuid
from itertools import pairwise
from pathlib import Path

import fakeredis
import pytest
from rq import Queue

from app import config
from app.pipeline.ingest.run import IngestError, run_ingest


def test_mono_ingest_detects_channel_count_and_stays_processing(make_call, call_row, fixtures_dir: Path):
    """AC1, AC2, AC5: worker writes `processing` at job start, detects mono
    channel count, and — since no downstream filter exists yet — leaves the
    Call in `processing` on success rather than completing it."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "mono.wav")

    run_ingest(call_id)

    row = call_row(call_id)
    assert row["channel_count"] == 1
    assert row["status"] == "processing"


def test_stereo_ingest_detects_channel_count(make_call, call_row, fixtures_dir: Path):
    """AC2: stereo input is detected and persisted distinctly from mono."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "stereo.wav")

    run_ingest(call_id)

    row = call_row(call_id)
    assert row["channel_count"] == 2


def test_ingest_persists_ordered_timeline_segments(make_call, timeline_segments, fixtures_dir: Path):
    """AC3, AC4: VAD-detected boundaries are persisted as an ordered, strictly
    sequential, gapless/contiguous TimelineSegment set (AC4) — not the raw
    speech-only intervals VAD returns, which have silence gaps between them.
    Uses the real-speech fixture (not a synthesized tone) since VAD is a
    neural speech detector and a sine tone correctly yields zero segments —
    useless for verifying persistence."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "speech.wav")

    run_ingest(call_id)

    segments = timeline_segments(call_id)
    assert len(segments) >= 1
    assert [s["segment_index"] for s in segments] == list(range(len(segments)))
    for s in segments:
        assert s["start_time"] < s["end_time"]
    # Strictly increasing start times confirm the set is truly ordered, not
    # just sequentially indexed over an arbitrary/unordered VAD output.
    starts = [s["start_time"] for s in segments]
    assert starts == sorted(starts)
    # AC4: gapless-within-the-Call — the first segment starts at 0.0 and each
    # segment's end exactly meets the next segment's start (no silence gaps),
    # so later stages can do adjacent-segment lookups (AD-11).
    assert segments[0]["start_time"] == 0.0
    for prev, nxt in pairwise(segments):
        assert prev["end_time"] == nxt["start_time"]


def test_ingest_failure_sets_status_failed_and_raises(make_call, call_row):
    """AC6: a failure (here, no audio file at all — the job can't find
    anything to load) transitions the Call to `failed` and re-raises, rather
    than leaving it silently stuck in `processing`."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=None)

    with pytest.raises(IngestError):
        run_ingest(call_id)

    row = call_row(call_id)
    assert row["status"] == "failed"


def test_ingest_success_enqueues_acoustic_job_with_correct_path_and_call_id(
    make_call, fixtures_dir: Path, fake_acoustic_queue
):
    """AD-13 stage-chaining: a successful run_ingest must enqueue exactly one
    acoustic job, referencing run_acoustic by its exact import-path string
    (never a direct import, AD-7) and passing the same call_id — a typo in
    either would silently break the ingest->acoustic hand-off while every
    other ingest test (which only exercises the fake queue incidentally)
    stays green. Also asserts the job's timeout is explicitly overridden to
    config.ACOUSTIC_JOB_TIMEOUT_SECONDS (fixed 2026-08-18: RQ's 180s default
    was too low for this specific job — see config.py's comment) rather than
    silently falling back to RQ's 180s class default."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "mono.wav")

    run_ingest(call_id)

    jobs = fake_acoustic_queue.jobs
    assert len(jobs) == 1
    assert jobs[0].func_name == "app.pipeline.acoustic.run.run_acoustic"
    assert jobs[0].args == (call_id,)
    assert jobs[0].timeout == config.ACOUSTIC_JOB_TIMEOUT_SECONDS


def test_ingest_job_resolvable_by_rq_string_reference(make_call, call_row, fixtures_dir: Path):
    """AD-13/AD-7 integration check: web-api enqueues by import-path string
    (`app.pipeline.ingest.run.run_ingest`), never a direct import — confirm
    RQ can actually resolve and execute that reference inside ml-service's
    own environment, using the `is_async=False` + fakeredis synchronous
    pattern (AD-21: no live Redis needed)."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "mono.wav")

    q = Queue("ingest", is_async=False, connection=fakeredis.FakeStrictRedis())
    job = q.enqueue("app.pipeline.ingest.run.run_ingest", call_id)

    assert job.is_finished
    row = call_row(call_id)
    assert row["status"] == "processing"
