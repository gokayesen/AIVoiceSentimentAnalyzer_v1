"""Call resource endpoints: upload/validation (FR-1, FR-2, FR-3; AD-20; AD-7;
AD-13), Emotional Timeline retrieval (Story 1.7; FR-9, AD-11, AD-13),
low-confidence segment flagging on that same timeline response (Story 1.8;
FR-10, AD-16), Call deletion (Story 1.10; AD-12), and the Analysis
Dashboard's remaining read-only data (Story 2.4; FR-12): `GET
/calls/{call_id}/transcript`, `GET /calls/{call_id}/acoustic-summary`, and
`get_call_status`'s extended complete-branch fields (`completed_at`,
`single_modality_flag`, `secondary_signal_*`, `no_speech_detected`).

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
    SPEAKER_UNCERTAIN_THRESHOLD,
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


def _speaker_uncertain_flag(speaker_confidence: float | None) -> bool:
    """Story 3.3 (AC2/AC4/AC6, AD-10): a turn's mono-diarization
    `speaker_confidence` (Story 3.2) below the configured threshold is
    "uncertain". `None` (stereo turns always, per Story 3.1 AC5; mono turns
    diarization never attributed a speaker to at all) is never uncertain —
    "no confidence value exists" is not the same claim as "confidence is
    low". Same strictly-less-than, deliberately-not-persisted rationale as
    `_low_confidence_flag` above, against its own independent threshold
    (never `LOW_CONFIDENCE_THRESHOLD` — AD-10 forbids conflating the two
    confidence axes, including at the threshold-tuning level)."""
    if speaker_confidence is None:
        return False
    return speaker_confidence < SPEAKER_UNCERTAIN_THRESHOLD


def _speaker_attribution_unavailable_flag(
    channel_count: int | None, turns: list[sqlite3.Row]
) -> bool:
    """Story 3.3/3.4 (AC1/AC3/AC4, AD-6): `True` only for a mono Call
    (`channel_count == 1`) that has at least one turn, where *every* one of
    those turns has `speaker_label is None` — "no usable speaker split at
    all" (AC1's exact wording), not merely "some turns unattributed." A
    stereo Call
    (`channel_count == 2`) or one with `channel_count is None` (legacy/
    unset) always returns `False` structurally, via this same equality
    check — never a separate branch. A zero-turn Call (`turns` empty, e.g.
    "no speech detected") also returns `False`, guarded by `turns` being
    truthy: there is nothing to have failed attribution on.

    Shared by `get_transcript` (Story 3.3, the original computation) and
    `get_call_status` (Story 3.4) — the Session Call List only ever polls
    the latter, never `/transcript`, so both endpoints need this same
    Call-level fact computed identically, from one source."""
    return bool(channel_count == 1 and turns and all(turn["speaker_label"] is None for turn in turns))


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


@router.get("/calls/{call_id}")
def get_call_status(call_id: str) -> dict:
    """Call-status retrieval (Story 2.2 Task 1). Read-only, same AD-13
    discipline as `get_timeline` below — reuses `db.get_call` and the new
    `db.get_analysis_result`, never writes `Call.status` or any ml-service-
    owned table.

    Exists because `GET /calls/{call_id}/timeline` alone cannot support
    Story 2.2: it only ever returns 200 once `status == "complete"`, and its
    409 `CALL_NOT_COMPLETE` error carries the identical `error_code` for
    `queued`, `processing`, and `failed` alike — a client cannot
    structurally distinguish "still working" from "processing failed" from
    that response alone. This endpoint always returns 200 with the Call's
    real status, plus Sentiment/Emotion/Confidence once `complete`.

    A `complete` Call usually has an `AnalysisResult` row by the time fusion
    finishes (Story 1.6 AC6) — except a Call with zero `TimelineSegment`
    rows (silence/no-speech audio), which completes with **no**
    `AnalysisResult` row at all by design (Story 1.6's 2026-08-14 decision:
    `db.get_analysis_result(...)` returning `None` on a `complete` Call is
    the well-defined "no speech detected" signal, not an infra fault). Story
    2.4 (Task 2) distinguishes the two: `no_speech_detected: true` for the
    legitimate empty case, with no `overall_*`/`single_modality_flag`/
    `secondary_signal_*` fields (FR-10/AD-16: never a fabricated Sentiment/
    Emotion value with nothing behind it) — never a `500`.

    `sqlite3.Error` from either read is treated as an infrastructure fault,
    same `errors.internal_error` contract `get_timeline` below uses for its
    own reads (code review, 2026-08-15 — the original version left these two
    reads unwrapped, the one place in this endpoint that deviated from
    `get_timeline`'s pattern despite the docstring above claiming parity).

    Story 3.4 (AC4, AD-6): a `complete` Call also gets `speaker_attribution_
    unavailable` — the same whole-Call fact `get_transcript` computes
    (Story 3.3), via the shared `_speaker_attribution_unavailable_flag`
    helper. Present on every `complete` Call, `no_speech_detected` or not.
    """
    conn = db.get_connection()
    try:
        try:
            call = db.get_call(conn, call_id=call_id)
        except sqlite3.Error as exc:
            raise errors.internal_error(str(exc)) from exc

        if call is None:
            raise errors.call_not_found(call_id)

        result: dict = {
            "call_id": call_id,
            "status": call["status"],
            "filename": call["filename"],
            "duration_seconds": call["duration_seconds"],
        }

        if call["status"] == "complete":
            result["completed_at"] = call["completed_at"]
            try:
                analysis_result = db.get_analysis_result(conn, call_id=call_id)
                turns = db.get_transcript_turns(conn, call_id=call_id)
            except sqlite3.Error as exc:
                raise errors.internal_error(str(exc)) from exc
            # Story 3.4 (AC4): the Session Call List (frontend) only ever
            # polls this endpoint, never `/transcript` — so the whole-Call
            # "attribution unavailable" fact `get_transcript` already
            # exposes (Story 3.3) must also be exposed here, computed
            # identically via the shared helper. Set for every complete
            # Call (both branches below), not just the "has a result"
            # branch: a zero-turn no-speech Call correctly resolves to
            # `False` via the helper's own `turns`-truthiness guard.
            result["speaker_attribution_unavailable"] = _speaker_attribution_unavailable_flag(
                call["channel_count"], turns
            )
            if analysis_result is None:
                # Story 2.4: "no speech detected" (Story 1.6) is a valid,
                # expected outcome, not an infra fault — see the docstring
                # above. Nothing else is added: no fabricated Sentiment/
                # Emotion/Confidence for a Call that was never analyzed.
                result["no_speech_detected"] = True
            else:
                result["overall_sentiment"] = analysis_result["overall_sentiment"]
                result["overall_emotion"] = analysis_result["overall_emotion"]
                result["overall_confidence"] = analysis_result["overall_confidence"]
                result["single_modality_flag"] = bool(analysis_result["single_modality_flag"])
                result["secondary_signal_emotion"] = analysis_result["secondary_signal_emotion"]
                result["secondary_signal_confidence"] = analysis_result[
                    "secondary_signal_confidence"
                ]
    finally:
        conn.close()

    return result


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
            raise errors.call_not_complete(call_id, call["status"], resource="The Emotional Timeline")

        try:
            segments = db.get_timeline_segments(conn, call_id=call_id)
            acoustic_rows = db.get_acoustic_evidence_for_call(conn, call_id=call_id)
        except sqlite3.Error as exc:
            raise errors.internal_error(str(exc)) from exc
    finally:
        conn.close()

    # Story 2.5 (Task 1): per-segment acoustic evidence, keyed by segment_id
    # (AcousticEvidence.segment_id is a 1:1 FK onto TimelineSegment, AD-3) —
    # joined in Python since db.get_acoustic_evidence_for_call (Story 2.4)
    # already reads every AcousticEvidence row for this Call in one query.
    acoustic_by_segment = {row["segment_id"]: row for row in acoustic_rows}

    result_segments = []
    for segment in segments:
        low_confidence_flag, flag_reason = _low_confidence_flag(segment["fused_confidence"])
        acoustic = acoustic_by_segment.get(segment["id"])
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
                # Story 2.5 (Task 1; FR-13, AD-10): the tone-signal half of
                # the Dual-signal panel — already read via SELECT * on
                # TimelineSegment, now returned instead of dropped.
                "acoustic_emotion": segment["acoustic_emotion"],
                "acoustic_confidence": segment["acoustic_confidence"],
                # Story 2.5 (Task 1; AC7): per-segment acoustic evidence for
                # the Acoustic panel's selection-driven highlight mode. Every
                # TimelineSegment gets exactly one AcousticEvidence row under
                # normal operation (AD-3) — `acoustic` is None only in the
                # defensive, should-not-occur case, in which case every
                # field below is None rather than raising.
                "pitch_mean_hz": acoustic["pitch_mean_hz"] if acoustic else None,
                "energy_rms_mean": acoustic["energy_rms_mean"] if acoustic else None,
                "speaking_rate_estimate": acoustic["speaking_rate_estimate"] if acoustic else None,
                "pause_ratio": acoustic["pause_ratio"] if acoustic else None,
            }
        )

    return {
        "call_id": call_id,
        "status": call["status"],
        "segments": result_segments,
    }


@router.get("/calls/{call_id}/transcript")
def get_transcript(call_id: str) -> dict:
    """Transcript retrieval (Story 2.4, Task 3; FR-12). Same read-only
    404/409 gate as `get_timeline` above — a zero-turn complete Call (a
    "no speech detected" Call, or one whose transcript branch never
    completed — Story 1.4/1.5's single-modality path) returns `200` with
    `"turns": []`, a valid result, not an error, same precedent as
    `get_timeline`'s zero-segment case.

    Returns every `TranscriptTurn` column this story's UI needs plus the
    three text-signal fields (`text_sentiment`/`text_emotion`/
    `text_confidence`) even though this story's own transcript panel only
    renders `text`/timestamps — so Story 2.5's dual-signal panel does not
    need a second backend change to this same endpoint. Deliberately
    excluded: `text_keywords` and any `TranscriptWord` data (no consumer in
    this story or Story 2.5's stated AC list).

    Story 3.1 (AD-2): also returns `speaker_label` — the canonical
    "Speaker A"/"Speaker B" value populated for stereo Calls, `null` for
    mono/unattributed turns (Story 2.5's `SpeakerLabel` component already
    consumes exactly this shape). `speaker_channel_index` is deliberately
    never returned here — internal provenance only, never the display-facing
    value (AC3).

    Story 3.3 (AC1-AC7, AD-6, AD-10) adds two derived states, computed at
    read time from columns Story 3.2 already persists — neither is
    persisted as its own DB column (same "pure function of an already-
    stored column" rationale as `_low_confidence_flag`): per-turn
    `speaker_uncertain` (`_speaker_uncertain_flag` on `speaker_confidence`,
    always `False` when `speaker_confidence` is `null`) and the Call-level
    `speaker_attribution_unavailable` (`true` only for a mono Call,
    `channel_count == 1`, where every turn's `speaker_label` is `null` — a
    stereo Call or a Call with at least one attributed turn is always
    `false`). The two states are structurally distinct fields, never
    conflated (AC3): the former is per-turn, the latter is a top-level,
    Call-wide fact.
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
            raise errors.call_not_complete(call_id, call["status"], resource="The transcript")

        try:
            turns = db.get_transcript_turns(conn, call_id=call_id)
        except sqlite3.Error as exc:
            raise errors.internal_error(str(exc)) from exc
    finally:
        conn.close()

    speaker_attribution_unavailable = _speaker_attribution_unavailable_flag(call["channel_count"], turns)

    return {
        "call_id": call_id,
        "status": call["status"],
        "speaker_attribution_unavailable": speaker_attribution_unavailable,
        "turns": [
            {
                "turn_id": turn["id"],
                "turn_index": turn["turn_index"],
                "start_time": turn["start_time"],
                "end_time": turn["end_time"],
                "text": turn["text"],
                "text_sentiment": turn["text_sentiment"],
                "text_emotion": turn["text_emotion"],
                "text_confidence": turn["text_confidence"],
                "speaker_label": turn["speaker_label"],
                "speaker_uncertain": _speaker_uncertain_flag(turn["speaker_confidence"]),
            }
            for turn in turns
        ],
    }


@router.get("/calls/{call_id}/acoustic-summary")
def get_acoustic_summary(call_id: str) -> dict:
    """Call-level acoustic aggregate retrieval (Story 2.4, Task 4; FR-12).
    Same read-only 404/409 gate as `get_timeline`/`get_transcript` above.

    Plain call-level averages only — no narrative text, no per-segment
    anchoring/highlighting, no "vs. baseline" comparison (Story 2.5's
    evidence drill-down, FR-13, owns all of that).

    Every field is averaged only over rows where it is not `NULL` — a
    segment can be entirely unvoiced (`ml-service/app/pipeline/acoustic/
    features.py`'s documented nullable case for `pitch_mean_hz`), and while
    `energy_rms_mean`/`speaking_rate_estimate`/`pause_ratio` are populated
    on every row the current pipeline writes, the schema itself does not
    enforce `NOT NULL` on any of the four columns — filtering `None`
    defensively for all of them (code review, 2026-08-15) avoids an
    unhandled `TypeError` from `sum()` if that ever changes, and matches
    `pitch_mean_hz`'s own already-defensive handling instead of trusting an
    unenforced invariant. Treating a missing value as 0 would silently bias
    the average low, same reasoning for every field. Zero rows (a "no
    speech detected" Call, or — should not occur under normal operation —
    a segment with no matching AcousticEvidence row) returns every field as
    `null` with `segment_count: 0`, not an error, same precedent as
    `get_timeline`'s zero-segment case.
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
            raise errors.call_not_complete(call_id, call["status"], resource="Acoustic insights")

        try:
            rows = db.get_acoustic_evidence_for_call(conn, call_id=call_id)
        except sqlite3.Error as exc:
            raise errors.internal_error(str(exc)) from exc
    finally:
        conn.close()

    segment_count = len(rows)

    def _mean(field: str) -> float | None:
        values = [row[field] for row in rows if row[field] is not None]
        return sum(values) / len(values) if values else None

    return {
        "call_id": call_id,
        "status": call["status"],
        "segment_count": segment_count,
        "pitch_mean_hz": _mean("pitch_mean_hz"),
        "energy_rms_mean": _mean("energy_rms_mean"),
        "speaking_rate_estimate": _mean("speaking_rate_estimate"),
        "pause_ratio": _mean("pause_ratio"),
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
