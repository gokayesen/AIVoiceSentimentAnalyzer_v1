"""Tests for DELETE /calls/{call_id} — Story 1.10 (Call Deletion, Backend).

Covers AC1 (atomic dual-store removal across all six tables + filesystem),
AC2 (in-flight `queued`/`processing` job coordination before removal), and
AC4 (independently runnable — no live Redis/ml-service needed, only
`fakeredis` and SQLite, same as every other web-api test module).

Local seeding helpers insert directly via `db.insert_call` / raw SQL INSERTs
for the other five tables — deliberately not new db.py write functions (only
`delete_call_cascade`, this story's one documented exception, writes to those
tables in web-api production code; see Dev Notes in the story file).
"""

from __future__ import annotations

import uuid

from rq.job import Job, JobStatus

from app import db
from app import queue as queue_module
from app.config import STORAGE_DIR
from app.routers import calls as calls_module


def _make_call(*, status: str) -> str:
    call_id = str(uuid.uuid4())
    conn = db.get_connection()
    try:
        db.insert_call(
            conn,
            call_id=call_id,
            status=status,
            filename="call.wav",
            audio_format="wav",
            duration_seconds=5.0,
            size_bytes=1024,
            created_at="2026-08-15T00:00:00+00:00",
        )
    finally:
        conn.close()
    return call_id


def _seed_full_call_graph(call_id: str) -> None:
    """Seeds one row in every one of the five non-Call tables a Call owns —
    including AcousticEvidence/TranscriptWord, the two tables beyond AD-12's
    literal four-table list — so a test can prove all six are actually
    cleaned up, not just the four named verbatim in the AC."""
    segment_id = str(uuid.uuid4())
    turn_id = str(uuid.uuid4())
    conn = db.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO TimelineSegment
                (id, call_id, segment_index, start_time, end_time,
                 fused_sentiment, fused_emotion, fused_confidence,
                 single_modality_flag, disagreement_flag)
            VALUES (?, ?, 0, 0.0, 2.0, 'positive', 'happy', 0.8, 0, 0)
            """,
            (segment_id, call_id),
        )
        conn.execute(
            """
            INSERT INTO AcousticEvidence
                (segment_id, pitch_mean_hz, pitch_std_hz, energy_rms_mean,
                 speaking_rate_estimate, pause_ratio)
            VALUES (?, 180.0, 12.0, 0.05, 3.2, 0.1)
            """,
            (segment_id,),
        )
        conn.execute(
            """
            INSERT INTO AnalysisResult
                (call_id, overall_sentiment, overall_emotion, overall_confidence,
                 single_modality_flag, secondary_signal_emotion,
                 secondary_signal_confidence, segments_flagged_count)
            VALUES (?, 'positive', 'happy', 0.8, 0, NULL, NULL, 0)
            """,
            (call_id,),
        )
        conn.execute(
            """
            INSERT INTO TranscriptTurn
                (id, call_id, turn_index, start_time, end_time, text,
                 text_sentiment, text_emotion, text_confidence, text_keywords)
            VALUES (?, ?, 0, 0.0, 2.0, 'hello there', 'positive', 'admiring', 0.7, '[]')
            """,
            (turn_id, call_id),
        )
        conn.execute(
            """
            INSERT INTO TranscriptWord
                (id, turn_id, word_index, word, start_time, end_time, probability)
            VALUES (?, ?, 0, 'hello', 0.0, 0.5, 0.95)
            """,
            (str(uuid.uuid4()), turn_id),
        )
        conn.commit()
    finally:
        conn.close()


def _row_counts(call_id: str, *, turn_id: str | None, segment_id: str | None) -> dict[str, int]:
    conn = db.get_connection()
    try:
        counts = {
            "Call": conn.execute("SELECT COUNT(*) FROM Call WHERE id = ?", (call_id,)).fetchone()[0],
            "TimelineSegment": conn.execute(
                "SELECT COUNT(*) FROM TimelineSegment WHERE call_id = ?", (call_id,)
            ).fetchone()[0],
            "AnalysisResult": conn.execute(
                "SELECT COUNT(*) FROM AnalysisResult WHERE call_id = ?", (call_id,)
            ).fetchone()[0],
            "TranscriptTurn": conn.execute(
                "SELECT COUNT(*) FROM TranscriptTurn WHERE call_id = ?", (call_id,)
            ).fetchone()[0],
        }
        if segment_id is not None:
            counts["AcousticEvidence"] = conn.execute(
                "SELECT COUNT(*) FROM AcousticEvidence WHERE segment_id = ?", (segment_id,)
            ).fetchone()[0]
        if turn_id is not None:
            counts["TranscriptWord"] = conn.execute(
                "SELECT COUNT(*) FROM TranscriptWord WHERE turn_id = ?", (turn_id,)
            ).fetchone()[0]
        return counts
    finally:
        conn.close()


def _set_status(call_id: str, status: str) -> None:
    conn = db.get_connection()
    try:
        conn.execute("UPDATE Call SET status = ? WHERE id = ?", (status, call_id))
        conn.commit()
    finally:
        conn.close()


def test_delete_nonexistent_call_returns_404(client):
    resp = client.delete(f"/calls/{uuid.uuid4()}")

    assert resp.status_code == 404
    body = resp.json()
    assert body["error_code"] == "CALL_NOT_FOUND"
    assert body["next_step"]


def test_delete_complete_call_removes_all_rows_and_files(client):
    """AC1: every one of the six tables a Call owns — including
    AcousticEvidence/TranscriptWord, beyond AD-12's literal four-table
    naming — plus its filesystem directory, are all gone after delete."""
    call_id = _make_call(status="complete")
    _seed_full_call_graph(call_id)
    conn = db.get_connection()
    try:
        segment_id = conn.execute(
            "SELECT id FROM TimelineSegment WHERE call_id = ?", (call_id,)
        ).fetchone()[0]
        turn_id = conn.execute(
            "SELECT id FROM TranscriptTurn WHERE call_id = ?", (call_id,)
        ).fetchone()[0]
    finally:
        conn.close()

    call_dir = STORAGE_DIR / call_id
    call_dir.mkdir(parents=True, exist_ok=True)
    (call_dir / "original.wav").write_bytes(b"fake audio")

    resp = client.delete(f"/calls/{call_id}")

    assert resp.status_code == 204
    assert resp.content == b""
    counts = _row_counts(call_id, turn_id=turn_id, segment_id=segment_id)
    assert counts == {
        "Call": 0,
        "TimelineSegment": 0,
        "AnalysisResult": 0,
        "TranscriptTurn": 0,
        "AcousticEvidence": 0,
        "TranscriptWord": 0,
    }
    assert not call_dir.exists()


def test_delete_failed_call_removes_all_rows_and_files(client):
    """AC1/AC2: a `failed` Call has no in-flight job at all — deletion
    proceeds immediately, no cancel/await branch triggers."""
    call_id = _make_call(status="failed")
    _seed_full_call_graph(call_id)

    resp = client.delete(f"/calls/{call_id}")

    assert resp.status_code == 204
    conn = db.get_connection()
    try:
        assert db.get_call(conn, call_id=call_id) is None
    finally:
        conn.close()


def test_cancel_queued_job_returns_true_when_no_job_exists(fake_queue):
    """Unit test (code review, 2026-08-15) for `_cancel_queued_job`'s
    `NoSuchJobError` branch — a `queued` Call whose job was never enqueued
    or has already expired is safe to delete immediately."""
    call_id = str(uuid.uuid4())

    assert calls_module._cancel_queued_job(call_id) is True


def test_cancel_queued_job_returns_false_when_job_already_started(fake_queue):
    """Unit test (code review, 2026-08-15) for `_cancel_queued_job`'s
    already-claimed-by-worker branch. Corrects a code review mistake caught
    via empirical verification: this project's pinned `rq==2.10.0`
    `job.cancel()` does NOT raise for an already-`STARTED` job (it only
    raises for an already-`CANCELED` one) — the real signal is
    `job.get_status() != QUEUED`, checked *before* ever calling `cancel()`."""
    call_id = str(uuid.uuid4())
    queue_module.enqueue_ingest(call_id)
    job = Job.fetch(call_id, connection=fake_queue.connection)
    job.set_status(JobStatus.STARTED)

    assert calls_module._cancel_queued_job(call_id) is False

    # Left alone — cancel() must never have been called on an already-
    # started job, so its status stays STARTED, not CANCELED.
    still_started = Job.fetch(call_id, connection=fake_queue.connection).get_status()
    assert still_started == JobStatus.STARTED


def test_delete_queued_call_cancels_the_job_and_deletes(client, fake_queue):
    """AC2: a `queued` Call's job is the one job web-api itself controls
    (job_id=call_id, Task 2) — deleting it must cancel that job, not just
    remove the DB rows underneath a job the worker might still pick up."""
    call_id = _make_call(status="queued")
    queue_module.enqueue_ingest(call_id)
    assert call_id in fake_queue.job_ids

    resp = client.delete(f"/calls/{call_id}")

    assert resp.status_code == 204
    conn = db.get_connection()
    try:
        assert db.get_call(conn, call_id=call_id) is None
    finally:
        conn.close()

    # job.cancel() does not delete the job from Redis, only dequeues it and
    # marks it CANCELED (verified empirically against this RQ version) — so
    # Job.fetch must still succeed, just report the canceled status.
    assert call_id not in fake_queue.job_ids
    job = Job.fetch(call_id, connection=fake_queue.connection)
    assert job.get_status() == "canceled"


def test_delete_processing_call_awaits_completion_then_deletes(client, monkeypatch):
    """AC2: a `processing` Call's job isn't reliably cancelable (see the
    story's Dev Notes on the fan-in job chain) — delete must wait for
    Call.status to leave 'processing' before removing anything, and must
    actually delete once it does."""
    monkeypatch.setattr(calls_module, "DELETE_AWAIT_TIMEOUT_SECONDS", 5.0)
    monkeypatch.setattr(calls_module, "DELETE_AWAIT_POLL_INTERVAL_SECONDS", 0.01)
    call_id = _make_call(status="processing")

    real_sleep = calls_module.time.sleep
    call_count = {"n": 0}

    def fake_sleep(seconds: float) -> None:
        call_count["n"] += 1
        if call_count["n"] == 1:
            _set_status(call_id, "complete")
        real_sleep(0)

    monkeypatch.setattr(calls_module.time, "sleep", fake_sleep)

    resp = client.delete(f"/calls/{call_id}")

    assert resp.status_code == 204
    assert call_count["n"] >= 1  # proves the wait loop actually ran, not a no-op
    conn = db.get_connection()
    try:
        assert db.get_call(conn, call_id=call_id) is None
    finally:
        conn.close()


def test_delete_processing_call_times_out_returns_409_and_deletes_nothing(client, monkeypatch):
    """AC2: if the wait window elapses while still 'processing', nothing is
    deleted — a live job may still be writing to this Call's rows/files.

    Code review (2026-08-15): fully deterministic via a fake monotonic clock
    (patching both `time.monotonic` and `time.sleep`) instead of the
    original version's unmocked real-time 30ms/10ms values — matches the
    sibling awaits-completion test's determinism instead of risking CI
    flakiness. Also strengthened to assert all six tables' rows and the
    filesystem directory survive, not just `AnalysisResult`'s row count,
    matching this test's own docstring claim ("deletes nothing")."""
    monkeypatch.setattr(calls_module, "DELETE_AWAIT_TIMEOUT_SECONDS", 1.0)
    monkeypatch.setattr(calls_module, "DELETE_AWAIT_POLL_INTERVAL_SECONDS", 0.1)
    call_id = _make_call(status="processing")
    _seed_full_call_graph(call_id)
    conn = db.get_connection()
    try:
        segment_id = conn.execute(
            "SELECT id FROM TimelineSegment WHERE call_id = ?", (call_id,)
        ).fetchone()[0]
        turn_id = conn.execute(
            "SELECT id FROM TranscriptTurn WHERE call_id = ?", (call_id,)
        ).fetchone()[0]
    finally:
        conn.close()

    call_dir = STORAGE_DIR / call_id
    call_dir.mkdir(parents=True, exist_ok=True)
    (call_dir / "original.wav").write_bytes(b"fake audio")

    fake_clock = {"t": 0.0}

    def fake_monotonic() -> float:
        return fake_clock["t"]

    def fake_sleep(seconds: float) -> None:
        fake_clock["t"] += seconds

    monkeypatch.setattr(calls_module.time, "monotonic", fake_monotonic)
    monkeypatch.setattr(calls_module.time, "sleep", fake_sleep)

    resp = client.delete(f"/calls/{call_id}")

    assert resp.status_code == 409
    body = resp.json()
    assert body["error_code"] == "CALL_DELETION_IN_PROGRESS"
    assert body["next_step"]

    counts = _row_counts(call_id, turn_id=turn_id, segment_id=segment_id)
    assert counts == {
        "Call": 1,
        "TimelineSegment": 1,
        "AnalysisResult": 1,
        "TranscriptTurn": 1,
        "AcousticEvidence": 1,
        "TranscriptWord": 1,
    }
    conn = db.get_connection()
    try:
        call = db.get_call(conn, call_id=call_id)
        assert call is not None
        assert call["status"] == "processing"
    finally:
        conn.close()
    assert call_dir.exists()
    assert (call_dir / "original.wav").exists()
