"""The acoustic-analysis RQ job (AC 1, 2, 5, 6, 7, 8, 9, 11) — Story 1.3.
Enqueued by `ingest/run.py` on successful ingest, chained via the job queue
(AD-13), consumed by the same RQ Worker process (AD-7)."""

from __future__ import annotations

import logging

from app import db, queue
from app.audio import load_mono_waveform
from app.config import ACOUSTIC_SANITY_FLOOR, TRANSCRIPT_JOB_TIMEOUT_SECONDS
from app.pipeline.acoustic.classifier import classify_segment
from app.pipeline.acoustic.features import extract_features
from app.pipeline.acoustic.taxonomy import raw_label_to_emotion
from app.pipeline.ingest.vad import VAD_SAMPLE_RATE

logger = logging.getLogger(__name__)

# AD-11: a small fixed context margin fed to the classifier only (never to
# handcrafted-feature extraction, and never altering the persisted
# start_time/end_time) so per-segment classification isn't artificially
# discontinuous at chunk boundaries.
CONTEXT_MARGIN_SECONDS = 0.5


class AcousticSanityFloorError(Exception):
    """Raised when a segment's calibrated confidence falls below
    ACOUSTIC_SANITY_FLOOR (AD-1). This fails the whole Call, not just that
    segment: AD-1 requires the acoustic filter itself to raise a job
    failure whenever its own output is degenerate, at the natural
    per-TimelineSegment granularity AD-3/AD-8 already establish."""


def run_acoustic(call_id: str) -> None:
    conn = db.get_connection()
    try:
        logger.info("acoustic analysis started", extra={"extra_fields": {"call_id": call_id}})

        segments = db.get_timeline_segments(conn, call_id=call_id)
        _raw_waveform, mono_waveform, _sample_rate = load_mono_waveform(call_id)
        total_samples = mono_waveform.shape[-1]
        margin_samples = int(CONTEXT_MARGIN_SECONDS * VAD_SAMPLE_RATE)

        # Compute every segment's results in memory first, write once at the
        # end (mirrors ingest/run.py's single-batch-write shape, AC 6/7): if
        # any segment breaches the sanity floor, nothing has been written
        # yet, so there is no risk of some segments' results persisting
        # while later segments in the same Call were never reached.
        evidence_rows = []
        acoustic_results = []
        for segment in segments:
            start_sample = int(segment["start_time"] * VAD_SAMPLE_RATE)
            end_sample = int(segment["end_time"] * VAD_SAMPLE_RATE)
            if end_sample <= start_sample:
                # Zero/negative-width segment (e.g. a boundary-rounding
                # mismatch between VAD's returned seconds and the exact
                # sample count) — there is no audio to analyze, so this
                # counts as a degenerate result rather than silently
                # producing a NaN energy_rms_mean or a bogus classification.
                raise AcousticSanityFloorError(
                    f"segment {segment['id']} has zero/negative width "
                    f"(start_time={segment['start_time']}, end_time={segment['end_time']})"
                )

            # Handcrafted features (AC 2/3): strictly within the segment's
            # own persisted boundaries — never the context-padded slice.
            strict_slice = mono_waveform[start_sample:end_sample].numpy()
            extracted = extract_features(strict_slice, VAD_SAMPLE_RATE)
            evidence_rows.append(
                (
                    segment["id"],
                    extracted.pitch_mean_hz,
                    extracted.pitch_std_hz,
                    extracted.energy_rms_mean,
                    extracted.speaking_rate_estimate,
                    extracted.pause_ratio,
                )
            )

            # Classification input (AC 1/5): AD-11 context margin into
            # neighboring audio, clipped to the Call's total duration.
            context_start = max(0, start_sample - margin_samples)
            context_end = min(total_samples, end_sample + margin_samples)
            context_slice = mono_waveform[context_start:context_end].numpy()
            raw_label, confidence = classify_segment(context_slice, VAD_SAMPLE_RATE)

            # AC 6/7: below the sanity floor, this result is invalid/
            # degenerate — fail the whole Call, never persist it or fall
            # back to anything.
            if confidence < ACOUSTIC_SANITY_FLOOR:
                raise AcousticSanityFloorError(
                    f"segment {segment['id']} calibrated confidence {confidence:.3f} "
                    f"below sanity floor {ACOUSTIC_SANITY_FLOOR}"
                )

            emotion = raw_label_to_emotion(raw_label)
            acoustic_results.append((segment["id"], emotion, confidence))

        db.persist_acoustic_results(conn, evidence_rows=evidence_rows, results=acoustic_results)

        logger.info(
            "acoustic analysis completed",
            extra={"extra_fields": {"call_id": call_id, "segment_count": len(segments)}},
        )
        # AC 9: acoustic analysis alone does not complete a Call — fusion
        # (Story 1.6, AD-8) is the only stage that can. Call.status stays
        # "processing".

        # Story 1.4: chain to the transcript-generation stage via the job
        # queue (AD-13), same intra-service stage-chaining pattern as
        # ingest -> acoustic (Story 1.3). Isolated in its own try/except
        # (code review, 2026-08-13): a queueing failure here (e.g. Redis
        # unreachable) must not roll back or fail this already-successful,
        # already-committed acoustic Call — it is a downstream hand-off
        # problem, not an acoustic-analysis failure (AD-1).
        # job_timeout: RQ's class-level 180s default is too low for this
        # specific job — see config.TRANSCRIPT_JOB_TIMEOUT_SECONDS's own
        # comment for the full rationale (real-world bug report, 2026-08-18,
        # same class of fix as the acoustic enqueue's own job_timeout).
        # Passed explicitly here only; RQ's global default is untouched.
        try:
            queue.get_transcript_queue().enqueue(
                "app.pipeline.transcript.run.run_transcript",
                call_id,
                job_timeout=TRANSCRIPT_JOB_TIMEOUT_SECONDS,
            )
        except Exception:
            logger.exception(
                "failed to enqueue transcript job — acoustic result stands, "
                "transcript will not run for this call",
                extra={"extra_fields": {"call_id": call_id}},
            )
            # Story 1.6 (AD-1, AC 1): if the transcript stage never even got
            # the chance to start, none of transcript/text-sentiment's own
            # fusion-enqueue call sites will ever fire either — fusion must
            # be enqueued from here instead, as this Call's only remaining
            # path to Call.status = "complete". One of five mutually
            # exclusive fan-in call sites; see fusion/run.py's module
            # docstring for the full list.
            try:
                queue.get_fusion_queue().enqueue("app.pipeline.fusion.run.run_fusion", call_id)
            except Exception:
                logger.exception(
                    "failed to enqueue fusion job — acoustic result stands, "
                    "this call will never reach Call.status = complete",
                    extra={"extra_fields": {"call_id": call_id}},
                )
    except Exception as exc:
        # Same rollback-before-failed-status pattern established and
        # code-reviewed in Story 1.2's ingest/run.py — do not simplify away.
        conn.rollback()
        try:
            db.set_call_status(conn, call_id=call_id, status="failed")
        except Exception:
            logger.exception(
                "failed to write failed status",
                extra={"extra_fields": {"call_id": call_id}},
            )
        logger.error(
            "acoustic analysis failed",
            extra={"extra_fields": {"call_id": call_id, "error": str(exc)}},
        )
        raise
    finally:
        conn.close()
