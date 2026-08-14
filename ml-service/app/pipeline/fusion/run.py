"""The fusion RQ job (AC 1, 2, 3, 4, 7) — Story 1.6. Reads Story 1.3's
acoustic signal and Story 1.5's text-sentiment signal (if available) for
every `TimelineSegment` of a Call, combines them (`fuse.py`), and writes
both the per-segment fusion output and the Call-level `AnalysisResult`
aggregate.

**Trigger fan-in, not a simple linear chain.** Every previous stage enqueues
exactly one successor, only on its own success. Fusion is different: AC 1/
AD-1 require it to run whenever acoustic succeeded, regardless of whether
the transcript branch (`acoustic -> transcript -> text_sentiment`) ever
completed. Five call sites enqueue this job: `acoustic/run.py`'s
transcript-enqueue `except` block, `transcript/run.py`'s
text-sentiment-enqueue `except` block and its own outer `except` block, and
`sentiment_run.py`'s success path and its own outer `except` block. Tracing
that control flow shows exactly one of the five fires per Call, so this job
is enqueued exactly once — never zero, never more than once. Do not add a
sixth call site, and do not make this job self-triggering/re-entrant."""

from __future__ import annotations

import logging

from app import db
from app.pipeline.fusion.fuse import FusedSegment, fuse_segment, reduce_call
from app.pipeline.fusion.overlap import resolve_text_signal

logger = logging.getLogger(__name__)


def run_fusion(call_id: str) -> None:
    """**Fail-hard, unlike `run_transcript`/`run_text_sentiment`.** Fusion is
    the only stage that can ever move `Call.status` to `complete` (AC 7/
    FR-3); if it cannot complete, the Call must not be left stuck at
    `processing` forever — see Story 1.6's Dev Notes for the full
    rationale. This mirrors `run_ingest`/`run_acoustic`'s rollback-then-
    failed-then-re-raise pattern instead."""
    conn = db.get_connection()
    try:
        logger.info("fusion started", extra={"extra_fields": {"call_id": call_id}})

        segments = db.get_timeline_segments(conn, call_id=call_id)

        # Code review (2026-08-14) / user decision: a Call with zero
        # TimelineSegment rows (e.g. silence/no-speech audio — VAD/ingest
        # legitimately produces no segments for such a Call, see the
        # `silence.wav` test fixture) is a valid outcome, not a failure.
        # There is nothing to fuse and no AnalysisResult to compute, so this
        # Call completes with no AnalysisResult row at all —
        # `db.get_analysis_result(...)` returning None is the well-defined
        # "no speech detected, nothing to report" signal for downstream
        # consumers (Story 1.7+), distinct from a real internal failure.
        if not segments:
            db.set_call_status(conn, call_id=call_id, status="complete")
            logger.info(
                "fusion completed with zero segments — no speech detected, "
                "no AnalysisResult produced",
                extra={"extra_fields": {"call_id": call_id}},
            )
            return

        turns = db.get_transcript_turns(conn, call_id=call_id)

        # Compute every segment's fusion result in memory first, write once
        # at the end — same atomicity discipline as every prior stage.
        fused_segments: list[FusedSegment] = []
        segment_results: list[db.FusedSegmentResult] = []
        for segment in segments:
            text_turn = resolve_text_signal(segment, turns)
            fused = fuse_segment(
                acoustic_emotion=segment["acoustic_emotion"],
                acoustic_confidence=segment["acoustic_confidence"],
                text_emotion=text_turn["text_emotion"] if text_turn is not None else None,
                text_sentiment=text_turn["text_sentiment"] if text_turn is not None else None,
                text_confidence=text_turn["text_confidence"] if text_turn is not None else None,
            )
            fused_segments.append(fused)
            segment_results.append(
                db.FusedSegmentResult(
                    segment_id=segment["id"],
                    fused_sentiment=fused.fused_sentiment,
                    fused_emotion=fused.fused_emotion,
                    fused_confidence=fused.fused_confidence,
                    single_modality_flag=fused.single_modality_flag,
                    disagreement_flag=fused.disagreement_flag,
                )
            )

        reduction = reduce_call(fused_segments)
        analysis_result = db.AnalysisResultRow(
            call_id=call_id,
            overall_sentiment=reduction.overall_sentiment,
            overall_emotion=reduction.overall_emotion,
            overall_confidence=reduction.overall_confidence,
            single_modality_flag=reduction.single_modality_flag,
            secondary_signal_emotion=reduction.secondary_signal_emotion,
            secondary_signal_confidence=reduction.secondary_signal_confidence,
            segments_flagged_count=reduction.segments_flagged_count,
        )

        # AC 7/FR-3: persist_fusion_results also writes Call.status =
        # "complete" as part of this same transaction (code review,
        # 2026-08-14) — the only place in the whole pipeline that does so —
        # so "fusion results persisted" and "Call marked complete" can never
        # diverge (a failure in one no longer leaves the other half-done).
        db.persist_fusion_results(
            conn, segment_results=segment_results, analysis_result=analysis_result
        )

        logger.info(
            "fusion completed",
            extra={
                "extra_fields": {
                    "call_id": call_id,
                    "segment_count": len(segments),
                    "single_modality_flag": reduction.single_modality_flag,
                }
            },
        )
    except Exception as exc:
        # Same rollback-before-failed-status pattern as run_ingest/
        # run_acoustic (Story 1.2/1.3) — fusion is the mandatory terminal
        # stage, so an internal failure here is a genuine Call-level
        # failure, unlike run_transcript/run_text_sentiment's fail-soft
        # pattern. Do not simplify this away.
        conn.rollback()
        try:
            db.set_call_status(conn, call_id=call_id, status="failed")
        except Exception:
            logger.exception(
                "failed to write failed status",
                extra={"extra_fields": {"call_id": call_id}},
            )
        logger.error(
            "fusion failed",
            extra={"extra_fields": {"call_id": call_id, "error": str(exc)}},
        )
        raise
    finally:
        conn.close()
