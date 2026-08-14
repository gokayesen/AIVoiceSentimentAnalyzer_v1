"""Tests for POST /calls — Story 1.1 (Call Upload & Validation).

Covers every AC: valid upload for each accepted format (AC1), unsupported
format (AC2), oversized/over-duration (AC3), corrupt file (AC4), and the
"what to do next" guidance on every rejection (AC5).
"""

from __future__ import annotations

from pathlib import Path

import pytest


def _upload(client, path: Path, content_type: str):
    with path.open("rb") as f:
        return client.post("/calls", files={"file": (path.name, f, content_type)})


@pytest.mark.parametrize(
    "filename,content_type",
    [
        ("valid.wav", "audio/wav"),
        ("valid.mp3", "audio/mpeg"),
        ("valid.m4a", "audio/mp4"),
    ],
)
def test_valid_upload_accepted(client, fixtures_dir: Path, filename, content_type):
    """AC1: accepted format under the limits -> Call created with status queued."""
    resp = _upload(client, fixtures_dir / filename, content_type)

    assert resp.status_code == 201
    body = resp.json()
    assert body["status"] == "queued"
    assert isinstance(body["call_id"], str) and len(body["call_id"]) > 0


def test_unsupported_format_rejected(client, fixtures_dir: Path):
    """AC2: unsupported format -> structured error naming the format, no Call created."""
    resp = _upload(client, fixtures_dir / "unsupported.ogg", "audio/ogg")

    assert resp.status_code == 422
    body = resp.json()
    assert body["error_code"] == "UNSUPPORTED_FORMAT"
    assert ".ogg" in body["message"]
    assert body["next_step"]


def test_oversized_file_rejected(client, fixtures_dir: Path):
    """AC3 (size): file over 200MB -> structured error naming the size limit exceeded."""
    resp = _upload(client, fixtures_dir / "oversized.wav", "audio/wav")

    assert resp.status_code == 422
    body = resp.json()
    assert body["error_code"] == "FILE_TOO_LARGE"
    assert "200" in body["message"] or "bytes" in body["message"]
    assert body["next_step"]


def test_over_duration_file_rejected(client, fixtures_dir: Path):
    """AC3 (duration): file over 30 minutes -> structured error naming the duration limit exceeded."""
    resp = _upload(client, fixtures_dir / "over_duration.wav", "audio/wav")

    assert resp.status_code == 422
    body = resp.json()
    assert body["error_code"] == "DURATION_EXCEEDED"
    assert body["next_step"]


@pytest.mark.parametrize("filename", ["corrupt.wav", "corrupt.mp3", "corrupt.m4a"])
def test_corrupt_file_rejected(client, fixtures_dir: Path, filename):
    """AC4: non-decodable/corrupt file -> structured error identifying it as undecodable."""
    resp = _upload(client, fixtures_dir / filename, "application/octet-stream")

    assert resp.status_code == 422
    body = resp.json()
    assert body["error_code"] == "UNDECODABLE_FILE"
    assert body["next_step"]


def test_mismatched_extension_rejected(client, fixtures_dir: Path):
    """Real MP3 content saved under a .wav extension is rejected, not silently
    accepted with a misleading stored `format` — libsndfile can decode it
    despite the wrong extension, so the probe must cross-check content vs. claim.
    """
    resp = _upload(client, fixtures_dir / "mismatched_extension.wav", "audio/wav")

    assert resp.status_code == 422
    body = resp.json()
    assert body["error_code"] == "UNDECODABLE_FILE"
    assert body["next_step"]


@pytest.mark.parametrize(
    "filename,content_type",
    [
        ("unsupported.ogg", "audio/ogg"),
        ("oversized.wav", "audio/wav"),
        ("over_duration.wav", "audio/wav"),
        ("corrupt.wav", "audio/wav"),
    ],
)
def test_rejection_never_creates_a_call_record(
    client, fixtures_dir: Path, filename, content_type
):
    """'No Call record is created' on ANY rejection path — verified via DB row count.

    Covers all four rejection types, not just UNSUPPORTED_FORMAT: DURATION_EXCEEDED
    and UNDECODABLE_FILE only reject after the decode probe runs, a structurally
    later point than the format/size pre-checks, so each path needs its own check.
    """
    from app import db

    conn = db.get_connection()
    try:
        before = conn.execute("SELECT COUNT(*) FROM Call").fetchone()[0]
    finally:
        conn.close()

    _upload(client, fixtures_dir / filename, content_type)

    conn = db.get_connection()
    try:
        after = conn.execute("SELECT COUNT(*) FROM Call").fetchone()[0]
    finally:
        conn.close()

    assert after == before


@pytest.mark.parametrize(
    "filename,content_type",
    [
        ("unsupported.ogg", "audio/ogg"),
        ("oversized.wav", "audio/wav"),
        ("over_duration.wav", "audio/wav"),
        ("corrupt.wav", "audio/wav"),
    ],
)
def test_rejection_leaves_no_orphaned_storage(
    client, fixtures_dir: Path, filename, content_type
):
    """No rejection path leaves anything behind under storage/, for any of the four
    rejection types — validation now runs entirely before any write to storage/.
    """
    from app.config import STORAGE_DIR

    before = set(STORAGE_DIR.glob("*")) if STORAGE_DIR.exists() else set()

    _upload(client, fixtures_dir / filename, content_type)

    after = set(STORAGE_DIR.glob("*")) if STORAGE_DIR.exists() else set()
    assert after == before


def test_persist_failure_cleans_up_and_returns_structured_error(
    client, fixtures_dir: Path, monkeypatch
):
    """A failure AFTER validation passes (e.g. the DB write) is not a validation
    rejection, but must still: clean up the storage it had just written, create
    no Call record, and return a structured error — not a raw 500 traceback.
    """
    from app import db
    from app.config import STORAGE_DIR

    def _boom(*args, **kwargs):
        raise RuntimeError("simulated DB failure")

    monkeypatch.setattr(db, "insert_call", _boom)

    conn = db.get_connection()
    try:
        before_count = conn.execute("SELECT COUNT(*) FROM Call").fetchone()[0]
    finally:
        conn.close()
    before_dirs = set(STORAGE_DIR.glob("*")) if STORAGE_DIR.exists() else set()

    resp = _upload(client, fixtures_dir / "valid.wav", "audio/wav")

    assert resp.status_code == 500
    body = resp.json()
    assert body["error_code"] == "INTERNAL_ERROR"
    assert body["next_step"]

    conn = db.get_connection()
    try:
        after_count = conn.execute("SELECT COUNT(*) FROM Call").fetchone()[0]
    finally:
        conn.close()
    after_dirs = set(STORAGE_DIR.glob("*")) if STORAGE_DIR.exists() else set()

    assert after_count == before_count
    assert after_dirs == before_dirs


@pytest.mark.parametrize(
    "filename,content_type,expected_code",
    [
        ("unsupported.ogg", "audio/ogg", "UNSUPPORTED_FORMAT"),
        ("oversized.wav", "audio/wav", "FILE_TOO_LARGE"),
        ("over_duration.wav", "audio/wav", "DURATION_EXCEEDED"),
        ("corrupt.wav", "audio/wav", "UNDECODABLE_FILE"),
    ],
)
def test_every_rejection_has_error_code_message_and_next_step(
    client, fixtures_dir: Path, filename, content_type, expected_code
):
    """AC5: every rejection tells the Analyst what to do next — exact shape check."""
    resp = _upload(client, fixtures_dir / filename, content_type)

    body = resp.json()
    assert set(body.keys()) == {"error_code", "message", "next_step"}
    assert body["error_code"] == expected_code
    assert isinstance(body["message"], str) and body["message"]
    assert isinstance(body["next_step"], str) and body["next_step"]


def test_valid_upload_enqueues_ingest_job(client, fixtures_dir: Path, fake_queue):
    """AC1/AD-13: a successful upload enqueues exactly one ingest job for the
    ML service (by import-path string, so web-api never imports ml-service
    code) and never writes Call.status past the initial `queued` insert —
    all later transitions belong exclusively to the ML service's RQ worker.
    """
    from app import db

    resp = _upload(client, fixtures_dir / "valid.wav", "audio/wav")
    call_id = resp.json()["call_id"]

    assert len(fake_queue.job_ids) == 1
    job = fake_queue.fetch_job(fake_queue.job_ids[0])
    assert job.func_name == "app.pipeline.ingest.run.run_ingest"
    assert job.args == (call_id,)

    conn = db.get_connection()
    try:
        row = conn.execute("SELECT status FROM Call WHERE id = ?", (call_id,)).fetchone()
    finally:
        conn.close()
    assert row["status"] == "queued"


def test_rejection_never_enqueues_a_job(client, fixtures_dir: Path, fake_queue):
    """No rejection path enqueues an ingest job — there is no Call for the
    ML service to process."""
    _upload(client, fixtures_dir / "unsupported.ogg", "audio/ogg")

    assert fake_queue.job_ids == []


def test_enqueue_failure_cleans_up_and_returns_structured_error(
    client, fixtures_dir: Path, monkeypatch
):
    """A failure during enqueue (e.g. Redis unreachable) is treated the same
    as any other post-persist failure: storage cleaned up, no Call record,
    structured 500 — never a silently orphaned `queued` Call that no worker
    will ever pick up.
    """
    from app import db, queue
    from app.config import STORAGE_DIR

    def _boom(call_id):
        raise RuntimeError("simulated Redis failure")

    monkeypatch.setattr(queue, "enqueue_ingest", _boom)

    conn = db.get_connection()
    try:
        before_count = conn.execute("SELECT COUNT(*) FROM Call").fetchone()[0]
    finally:
        conn.close()
    before_dirs = set(STORAGE_DIR.glob("*")) if STORAGE_DIR.exists() else set()

    resp = _upload(client, fixtures_dir / "valid.wav", "audio/wav")

    assert resp.status_code == 500
    body = resp.json()
    assert body["error_code"] == "INTERNAL_ERROR"
    assert body["next_step"]

    conn = db.get_connection()
    try:
        after_count = conn.execute("SELECT COUNT(*) FROM Call").fetchone()[0]
    finally:
        conn.close()
    after_dirs = set(STORAGE_DIR.glob("*")) if STORAGE_DIR.exists() else set()

    assert after_count == before_count
    assert after_dirs == before_dirs
