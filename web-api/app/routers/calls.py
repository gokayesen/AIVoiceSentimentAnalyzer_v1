"""Call resource endpoints: upload/validation (FR-1, FR-2, FR-3; AD-20; AD-7;
AD-13), Emotional Timeline retrieval (Story 1.7; FR-9, AD-11, AD-13),
low-confidence segment flagging on that same timeline response (Story 1.8;
FR-10, AD-16), and Call deletion (Story 1.10; AD-12).

`POST /calls` validates, persists the raw audio, writes Call metadata as
`queued`, then enqueues an RQ ingest job (Story 1.2) so the ML service picks
it up. This endpoint never writes `Call.status` beyond that initial `queued`
insert — all later transitions (`processing`/`complete`/`failed`) are written
exclusively by the ML service's RQ worker (AD-13).

Validation (format, size, decodability, duration) runs against the upload's
already-spooled temp file *before* anything is written to permanent storage —
a rejected upload never touches `storage/`, so no cleanup is needed for any
validation failure. Only the persist step (copy to storage + DB insert) can
still fail after validation passes (disk full, DB lock, ...); that step is
the only one wrapped in cleanup-on-failure.

`GET /calls/{call_id}/timeline` is read-only: it only reads `Call`/
`TimelineSegment` rows already written by ml-service's RQ worker, never
`Call.status` or analysis data (AD-13 service boundary).

`DELETE /calls/{call_id}` (Story 1.10) is the one deliberate exception to
"web-api never writes ml-service's tables" — AD-12 explicitly assigns it the
job of atomic, dual-store Call removal. See the story's own Dev Notes ("Why
no ml-service changes are needed") for why a Call's multi-stage RQ pipeline
only ever needs *one* job cancelled from here (the `queued` case) and why the
`processing` case waits on `Call.status` instead of trying to reach into
ml-service's dynamically-chained job queues.

All handlers are declared as a plain `def` (not `async def`): every
operation (file I/O, audio decode probing, SQLite access, the bounded
delete-await wait) is blocking. FastAPI runs `def` path operations in a
worker thread pool automatically; an `async def` with no `await` would
instead block the single event loop for the whole request, serializing all
concurrent requests.
"""

from __future__ import annotations

import logging
import os
import shutil
import sqlite3
import time
import uuid
from datetime import UTC, datetime

from fastapi import APIRouter, File, Response, UploadFile
from rq.exceptions import InvalidJobOperation, NoSuchJobError
from rq.job import Job, JobStatus

from app import db, errors, queue
from app.audio_validation import AudioProbeError, probe_audio
from app.config import (
    ALLOWED_AUDIO_EXTENSIONS,
    DELETE_AWAIT_POLL_INTERVAL_SECONDS,
    DELETE_AWAIT_TIMEOUT_SECONDS,
    LOW_CONFIDENCE_THRESHOLD,
    MAX_DURATION_SECONDS,
    MAX_FILE_SIZE_BYTES,
    STORAGE_DIR,
)

logger = logging.getLogger(__name__)

router = APIRouter()


def _extension_of(filename: str | None) -> str:
    if not filename or "." not in filename:
        return ""
    return "." + filename.rsplit(".", 1)[-1].lower()


def _low_confidence_flag(confidence: float) -> tuple[bool, str | None]:
    """Story 1.8 (AC2/AC3/AC4): a segment's confidence "falls below" the
    configured threshold — strictly less than, so a confidence exactly equal
    to the threshold is not flagged. Never called with a confidence below
    ml-service's own ACOUSTIC_SANITY_FLOOR: a Call whose acoustic confidence
    fell below that gate never reaches `status == "complete"` at all (AD-1),
    so this endpoint never sees such a segment in the first place — no
    sanity-floor check is needed or possible here (web-api has no access to
    that ml-service-internal constant).

    Deliberately recomputed on every read against the *current*
    LOW_CONFIDENCE_THRESHOLD, never persisted on `TimelineSegment` — the flag
    is a pure function of an already-stored column (`fused_confidence`), so
    persisting it would mean one more hand-synced DDL column to keep
    byte-for-byte identical across web-api/ml-service (AD-7) for a value with
    nothing gained by storing it. This also means a Call's flagged segments
    can change on a later read if the threshold is reconfigured — an
    accepted tradeoff, not an oversight (code review, 2026-08-14)."""
    if confidence < LOW_CONFIDENCE_THRESHOLD:
        return True, (
            f"Confidence {confidence:.2f} is below the configured "
            f"low-confidence threshold ({LOW_CONFIDENCE_THRESHOLD:.2f})."
        )
    return False, None


def _upload_size(upload: UploadFile) -> int:
    """Size via seek/tell on the already-spooled file — no full read into memory."""
    upload.file.seek(0, os.SEEK_END)
    size = upload.file.tell()
    upload.file.seek(0)
    return size


@router.post("/calls", status_code=201)
def upload_call(file: UploadFile = File(...)) -> dict:
    extension = _extension_of(file.filename)
    if extension not in ALLOWED_AUDIO_EXTENSIONS:
        raise errors.unsupported_format(extension or "(no extension)")

    size_bytes = _upload_size(file)
    if size_bytes > MAX_FILE_SIZE_BYTES:
        raise errors.file_too_large(size_bytes, MAX_FILE_SIZE_BYTES)

    try:
        probe = probe_audio(file.file, extension)
    except AudioProbeError as exc:
        raise errors.undecodable_file(str(exc)) from exc
    finally:
        file.file.seek(0)

    if probe.duration_seconds > MAX_DURATION_SECONDS:
        raise errors.duration_exceeded(probe.duration_seconds, MAX_DURATION_SECONDS)

    # Validation passed — nothing has touched storage/ or the DB yet. Any
    # failure from here on is an infrastructure fault, not a validation
    # rejection, so it's wrapped uniformly and cleaned up below.
    call_id = str(uuid.uuid4())
    call_dir = STORAGE_DIR / call_id
    dest_path = call_dir / f"original{extension}"

    call_inserted = False
    try:
        call_dir.mkdir(parents=True, exist_ok=True)
        with dest_path.open("wb") as dest:
            shutil.copyfileobj(file.file, dest)

        conn = db.get_connection()
        try:
            db.insert_call(
                conn,
                call_id=call_id,
                status="queued",
                filename=file.filename or "unknown",
                audio_format=extension.lstrip("."),
                duration_seconds=probe.duration_seconds,
                size_bytes=size_bytes,
                created_at=datetime.now(UTC).isoformat(),
            )
            call_inserted = True
        finally:
            conn.close()

        # AD-13: web-api enqueues and never performs analysis itself.
        queue.enqueue_ingest(call_id)
    except Exception as exc:
        shutil.rmtree(call_dir, ignore_errors=True)
        if call_dir.exists():
            logger.warning("cleanup left residue at %s", call_dir)
        # insert_call() above commits immediately, so a failure here (e.g.
        # the enqueue call) can no longer be rolled back by the DB itself —
        # explicitly undo it, or the Call row is orphaned with no worker
        # ever picking it up.
        if call_inserted:
            conn = db.get_connection()
            try:
                db.delete_call(conn, call_id=call_id)
            except Exception:
                logger.exception("failed to delete orphaned call %s after enqueue failure", call_id)
            finally:
                conn.close()
        raise errors.internal_error(str(exc)) from exc

    return {"call_id": call_id, "status": "queued"}


@router.get("/calls/{call_id}/timeline")
def get_timeline(call_id: str) -> dict:
    """Emotional Timeline retrieval (Story 1.7; FR-9, AD-11, AD-13). See the
    module docstring for the shared plain-`def`/read-only rationale.

    `sqlite3.Error` from either read is treated as an infrastructure fault
    (same `errors.internal_error` contract `upload_call` uses for its own
    infra failures) and kept separate from the two business-logic raises
    below (`call_not_found`/`call_not_complete`), which are expected,
    structured outcomes, not errors to be wrapped.
    """
    conn = db.get_connection()
    try:
        try:
            call = db.get_call(conn, call_id=call_id)
        except sqlite3.Error as exc:
            raise errors.internal_error(str(exc)) from exc

        if call is None:
            raise errors.call_not_found(call_id)
        if call["status"] != "complete":
            raise errors.call_not_complete(call_id, call["status"])

        try:
            segments = db.get_timeline_segments(conn, call_id=call_id)
        except sqlite3.Error as exc:
            raise errors.internal_error(str(exc)) from exc
    finally:
        conn.close()

    result_segments = []
    for segment in segments:
        low_confidence_flag, flag_reason = _low_confidence_flag(segment["fused_confidence"])
        result_segments.append(
            {
                "segment_id": segment["id"],
                "start_time": segment["start_time"],
                "end_time": segment["end_time"],
                "fused_sentiment": segment["fused_sentiment"],
                "fused_emotion": segment["fused_emotion"],
                "fused_confidence": segment["fused_confidence"],
                "disagreement_flag": bool(segment["disagreement_flag"]),
                "low_confidence_flag": low_confidence_flag,
                "flag_reason": flag_reason,
                # acoustic_emotion/acoustic_confidence are read (SELECT *)
                # but deliberately not returned here — the acoustic-evidence
                # drill-down (FR-13) is Epic 2 territory, out of this
                # story's scope (see Dev Notes' "What NOT to build").
            }
        )

    return {
        "call_id": call_id,
        "status": call["status"],
        "segments": result_segments,
    }


def _cancel_queued_job(call_id: str) -> bool:
    """Story 1.10 (AD-12): the only job that can exist for a `queued` Call is
    the one this service's own `enqueue_ingest` created with `job_id=call_id`
    (Task 2) — no downstream ml-service stage has run yet.

    Returns `True` when it is safe to proceed straight to deletion (no job
    was ever enqueued/already expired, or the job was observed genuinely
    `QUEUED` and successfully canceled before any worker could claim it) and
    `False` otherwise — the caller must NOT trust a `Call.status` re-read in
    that case and must force the await-branch instead.

    Code review (2026-08-15), corrected after empirical verification: an
    earlier version of this function relied on `job.cancel()` raising
    `InvalidJobOperation` to detect "a worker already claimed this job" —
    verified empirically (against this project's pinned `rq==2.10.0`) that
    this is **wrong**: `cancel()` only raises `InvalidJobOperation` for a
    job that is *already canceled*; called on a `STARTED` job it succeeds
    silently, marking it `CANCELED` in Redis bookkeeping while the worker
    process — which already forked/claimed the job payload before ever
    updating Redis — keeps executing `run_ingest` completely unaware. Acting
    on that false "canceled" success would have raced a live job's writes,
    exactly what AD-12 forbids. The fix: explicitly check `job.get_status()`
    first, and only attempt `cancel()` — and only trust its success — when
    the job is still genuinely `QUEUED`. A narrow window remains between
    this status check and the `cancel()` call immediately after it (RQ 2.10
    offers no atomic "cancel-if-still-queued" primitive), but this is far
    smaller than the original gap (the worker's entire dequeue-to-first-
    Call.status-write window) and is an accepted residual risk, not
    something closable without a distributed-locking redesign out of this
    story's scope."""
    redis_conn = queue.get_queue().connection
    try:
        job = Job.fetch(call_id, connection=redis_conn)
    except NoSuchJobError:
        return True
    if job.get_status() != JobStatus.QUEUED:
        return False
    try:
        job.cancel()
        return True
    except InvalidJobOperation:
        return False


def _await_processing_completion(conn: sqlite3.Connection, *, call_id: str) -> str | None:
    """Story 1.10 (AD-12): bounded poll on `Call.status` until it leaves
    `processing` (or the row disappears) or the timeout elapses. Each
    iteration issues a fresh, unwrapped SELECT (no explicit transaction held
    across the loop) so it observes the RQ worker's most recently committed
    write under WAL — holding one long-lived transaction here would freeze
    the read at whatever was committed when the loop started, defeating the
    wait entirely. Returns the final observed status (or None if the Call
    row no longer exists)."""
    deadline = time.monotonic() + DELETE_AWAIT_TIMEOUT_SECONDS
    while True:
        call = db.get_call(conn, call_id=call_id)
        status = call["status"] if call else None
        if status != "processing":
            return status
        if time.monotonic() >= deadline:
            return status
        time.sleep(DELETE_AWAIT_POLL_INTERVAL_SECONDS)


@router.delete("/calls/{call_id}", status_code=204)
def delete_call_endpoint(call_id: str) -> Response:
    """Call deletion (Story 1.10; AD-12). See the module docstring and the
    story's own Dev Notes for why the `queued`/`processing` split below is
    the correct interpretation of AD-12's "cancel or await" wording given a
    Call's multi-stage RQ pipeline.

    Named `delete_call_endpoint` (code review, 2026-08-15), not `delete_call`
    — this file has no `db` import-aliasing collision risk today (callers
    always use the qualified `db.delete_call`/`db.delete_call_cascade`), but
    a same-named function in a different module was flagged as inviting
    exactly the confusion this story's own Dev Notes warn against for the
    `delete_call`/`delete_call_cascade` pair.

    The whole body below is wrapped in one broad exception handler (code
    review, 2026-08-15): unlike `get_timeline`'s per-call `except
    sqlite3.Error`, this handler's work spans a DB read, a Redis-touching
    cancel attempt, a bounded DB-polling wait, and a final cascade delete —
    any of which can raise an unexpected infra error (DB, Redis, RQ). Our
    own deliberately-raised `UploadValidationError`s (`call_not_found`,
    `call_deletion_in_progress`) are re-raised unchanged; anything else is
    wrapped into the same `internal_error` contract `upload_call` uses.
    """
    conn = db.get_connection()
    try:
        try:
            call = db.get_call(conn, call_id=call_id)
            if call is None:
                raise errors.call_not_found(call_id)
            status = call["status"]

            if status == "queued":
                cancel_succeeded = _cancel_queued_job(call_id)
                # Re-read: the cancel attempt above may have lost a race
                # against the worker actually starting the job in between
                # the first read and now.
                call = db.get_call(conn, call_id=call_id)
                status = call["status"] if call else None
                if not cancel_succeeded and status != "processing":
                    # The worker already claimed the job, but our own
                    # re-read hasn't observed "processing" yet (see
                    # _cancel_queued_job's docstring for the exact race) —
                    # force the await-branch regardless of the stale read.
                    status = "processing"

            if status == "processing":
                status = _await_processing_completion(conn, call_id=call_id)
                if status == "processing":
                    raise errors.call_deletion_in_progress(call_id)

            db.delete_call_cascade(conn, call_id=call_id)
        except errors.UploadValidationError:
            raise
        except Exception as exc:
            raise errors.internal_error(str(exc)) from exc
    finally:
        conn.close()

    # DB delete has already committed at this point — filesystem removal is
    # deliberately the second step (see the story's "Delete ordering" Dev
    # Note): an orphaned directory is inert, whereas a Call whose files were
    # removed but whose rows survived would be a live, visibly broken Call.
    call_dir = STORAGE_DIR / call_id
    shutil.rmtree(call_dir, ignore_errors=True)
    if call_dir.exists():
        logger.warning("delete cleanup left residue at %s", call_dir)

    return Response(status_code=204)
