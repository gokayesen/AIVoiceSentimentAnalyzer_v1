"""The ingest RQ job (AC 1, 2, 3, 5, 6). Enqueued by web-api as
`app.pipeline.ingest.run.run_ingest` (a string reference — web-api never
imports this module in-process, AD-7)."""

from __future__ import annotations

import logging
import uuid

from app import db, queue
from app.audio import load_mono_waveform
from app.pipeline.ingest.channel import detect_channel_count
from app.pipeline.ingest.vad import VAD_SAMPLE_RATE, compute_speech_boundaries

logger = logging.getLogger(__name__)


class IngestError(Exception):
    """Raised for any expected ingest failure (missing/corrupt audio, etc)."""


def _fill_gaps(
    boundaries: list[tuple[float, float]], total_duration: float
) -> list[tuple[float, float]]:
    """AC4: the persisted set must be gapless-within-the-Call and contiguous
    (segment[i].end_time == segment[i+1].start_time), not just the raw
    speech-only intervals VAD returns. Extends the first segment's start back
    to 0.0 and each segment's end forward to the next segment's start (the
    last segment's end to the Call's total duration), so the ordered set
    tiles [0, total_duration] with no gaps for later stages' adjacent-segment
    lookups (AD-11)."""
    if not boundaries:
        return []
    filled = []
    last_index = len(boundaries) - 1
    for i, (start, _end) in enumerate(boundaries):
        seg_start = 0.0 if i == 0 else start
        seg_end = boundaries[i + 1][0] if i < last_index else total_duration
        filled.append((seg_start, seg_end))
    return filled


def run_ingest(call_id: str) -> None:
    conn = db.get_connection()
    try:
        # AD-13: this is the only place in the system that writes Call.status
        # transitions beyond web-api's initial `queued` insert.
        db.set_call_status(conn, call_id=call_id, status="processing")
        logger.info("ingest started", extra={"extra_fields": {"call_id": call_id}})

        try:
            waveform, mono_waveform, _sample_rate = load_mono_waveform(call_id)
        except FileNotFoundError as exc:
            raise IngestError(str(exc)) from exc

        channel_count = detect_channel_count(waveform)
        db.set_call_channel_count(conn, call_id=call_id, channel_count=channel_count)
        logger.info(
            "channel count detected",
            extra={"extra_fields": {"call_id": call_id, "channel_count": channel_count}},
        )

        total_duration = mono_waveform.shape[-1] / VAD_SAMPLE_RATE
        boundaries = _fill_gaps(compute_speech_boundaries(mono_waveform), total_duration)
        segments = [
            (str(uuid.uuid4()), idx, start, end)
            for idx, (start, end) in enumerate(boundaries)
        ]
        db.insert_timeline_segments(conn, call_id=call_id, segments=segments)
        logger.info(
            "timeline segments persisted",
            extra={"extra_fields": {"call_id": call_id, "segment_count": len(segments)}},
        )

        # Story 1.3: chain to the acoustic-analysis stage via the job queue
        # (AD-13) rather than an in-process call — same-service stage
        # hand-off, not a web-api->ml-service boundary crossing (AD-7).
        # Indirected through app.queue.get_acoustic_queue() (mirroring
        # web-api/app/queue.py's pattern) so tests can monkeypatch the
        # connection without a live Redis server.
        queue.get_acoustic_queue().enqueue("app.pipeline.acoustic.run.run_acoustic", call_id)

        # AC 5: ingest alone never completes a Call — status stays "processing"
        # until fusion (Story 1.6) exists to complete it.
    except Exception as exc:
        # Discard any statements executed-but-uncommitted earlier in this try
        # block (e.g. a partially-written TimelineSegment batch) so the
        # upcoming "failed" status commit below can't drag partial data along
        # with it.
        conn.rollback()
        try:
            db.set_call_status(conn, call_id=call_id, status="failed")
        except Exception:
            logger.exception(
                "failed to write failed status",
                extra={"extra_fields": {"call_id": call_id}},
            )
        logger.error(
            "ingest failed",
            extra={"extra_fields": {"call_id": call_id, "error": str(exc)}},
        )
        raise
    finally:
        conn.close()
