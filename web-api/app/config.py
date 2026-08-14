"""Fixed ingest constants (AD-20). Adopted architecture decisions, not operator-tunable."""

import math
import os
from pathlib import Path

# AD-20: accepted formats, size, and duration ceilings are fixed by Architecture — not deferred.
ALLOWED_AUDIO_EXTENSIONS = {".wav", ".mp3", ".m4a"}
MAX_FILE_SIZE_BYTES = 200 * 1024 * 1024  # 200MB
MAX_DURATION_SECONDS = 30 * 60  # 30 minutes

# AD-12: session-scoped filesystem storage for uploaded audio + intermediate artifacts.
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", Path(__file__).resolve().parents[2] / "storage"))

# SQLite: structured Call metadata (AD-12). Stdlib sqlite3 per Stack table.
DB_PATH = Path(os.environ.get("DB_PATH", STORAGE_DIR / "app.db"))

# AD-13: RQ + Redis job queue. web-api only ever enqueues here — it never
# runs a worker. Default matches docker-compose's `redis` service.
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")
INGEST_QUEUE_NAME = "ingest"

# Story 1.8 (AC2/AC4): a segment's `fused_confidence` below this value is
# marked Low-Confidence in the timeline response. Same env var name/default
# as ml-service/app/config.py's own `LOW_CONFIDENCE_THRESHOLD` (added in
# Story 1.3, still unconsumed by any ml-service pipeline code — that copy
# exists only to validate ACOUSTIC_SANITY_FLOOR's ordering there) — hand-
# synced, not imported (AD-7). This is the copy that's actually consumed:
# the flagging logic lives in web-api's response contract, not ml-service
# (see Story 1.8 Dev Notes, "Where the flagging logic lives").
_low_confidence_threshold_raw = os.environ.get("LOW_CONFIDENCE_THRESHOLD", "0.5")
try:
    LOW_CONFIDENCE_THRESHOLD = float(_low_confidence_threshold_raw)
except ValueError as exc:
    raise ValueError(
        f"LOW_CONFIDENCE_THRESHOLD must be a float, got {_low_confidence_threshold_raw!r}"
    ) from exc
if not 0 <= LOW_CONFIDENCE_THRESHOLD <= 1:
    raise ValueError(
        f"LOW_CONFIDENCE_THRESHOLD must be in [0, 1], got {LOW_CONFIDENCE_THRESHOLD}"
    )

# Story 1.10 (AD-12): bound how long DELETE /calls/{call_id} will wait for an
# in-flight ("processing") job to finish before giving up and returning 409 —
# an operational timing parameter, not a fourth tunable domain threshold
# alongside LOW_CONFIDENCE_THRESHOLD/DISAGREEMENT_THRESHOLD/ACOUSTIC_SANITY_
# FLOOR (those are compared against calibrated [0, 1] confidence values; these
# two are plain wall-clock seconds with no spec-mandated value).
_delete_await_timeout_raw = os.environ.get("DELETE_AWAIT_TIMEOUT_SECONDS", "10")
try:
    DELETE_AWAIT_TIMEOUT_SECONDS = float(_delete_await_timeout_raw)
except ValueError as exc:
    raise ValueError(
        f"DELETE_AWAIT_TIMEOUT_SECONDS must be a float, got {_delete_await_timeout_raw!r}"
    ) from exc
# Code review (2026-08-15): `> 0` alone lets "inf" through (float("inf") > 0
# is True) — `math.isfinite` also rejects NaN, though NaN already fails the
# `> 0` check on its own (all NaN comparisons are False in IEEE754); the
# explicit isfinite check is what actually rules out "inf"/"-inf", which
# would otherwise make this wait effectively unbounded. Verified empirically
# that an "inf" POLL_INTERVAL (checked below) crashes time.sleep() outright
# with OverflowError — this same guard on TIMEOUT prevents its own, quieter
# failure mode (an unbounded wait that never times out).
if not (math.isfinite(DELETE_AWAIT_TIMEOUT_SECONDS) and DELETE_AWAIT_TIMEOUT_SECONDS > 0):
    raise ValueError(
        f"DELETE_AWAIT_TIMEOUT_SECONDS must be a finite number > 0, got {DELETE_AWAIT_TIMEOUT_SECONDS}"
    )

_delete_await_poll_interval_raw = os.environ.get("DELETE_AWAIT_POLL_INTERVAL_SECONDS", "0.2")
try:
    DELETE_AWAIT_POLL_INTERVAL_SECONDS = float(_delete_await_poll_interval_raw)
except ValueError as exc:
    raise ValueError(
        "DELETE_AWAIT_POLL_INTERVAL_SECONDS must be a float, got "
        f"{_delete_await_poll_interval_raw!r}"
    ) from exc
# Code review (2026-08-15): same isfinite rationale as TIMEOUT above — an
# "inf" poll interval reaches _await_processing_completion's time.sleep()
# call and raises an unhandled OverflowError (verified empirically against
# this Python/platform), which would otherwise surface as an unstructured
# crash instead of a clear config-time error naming the variable.
if not (
    math.isfinite(DELETE_AWAIT_POLL_INTERVAL_SECONDS) and DELETE_AWAIT_POLL_INTERVAL_SECONDS > 0
):
    raise ValueError(
        "DELETE_AWAIT_POLL_INTERVAL_SECONDS must be a finite number > 0, got "
        f"{DELETE_AWAIT_POLL_INTERVAL_SECONDS}"
    )
# Code review (2026-08-15): cross-validated against TIMEOUT above (only
# possible after both are individually parsed and validated) — without this,
# _await_processing_completion's loop checks its deadline *before* sleeping,
# not after, so a POLL_INTERVAL larger than TIMEOUT lets one sleep overshoot
# the documented wait bound by nearly the full poll interval.
if DELETE_AWAIT_POLL_INTERVAL_SECONDS > DELETE_AWAIT_TIMEOUT_SECONDS:
    raise ValueError(
        "DELETE_AWAIT_POLL_INTERVAL_SECONDS "
        f"({DELETE_AWAIT_POLL_INTERVAL_SECONDS}) must not exceed "
        f"DELETE_AWAIT_TIMEOUT_SECONDS ({DELETE_AWAIT_TIMEOUT_SECONDS})"
    )
