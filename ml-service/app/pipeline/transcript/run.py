"""The transcript-generation RQ job (AC 1, 2, 4, 6, 7, 8) — Story 1.4.
Enqueued by `acoustic/run.py` on successful acoustic analysis, chained via
the job queue (AD-13), consumed by the same RQ Worker process (AD-7)."""

from __future__ import annotations

import logging
import uuid

from app import db, queue
from app.audio import load_mono_waveform
from app.pipeline.ingest.vad import VAD_SAMPLE_RATE
from app.pipeline.transcript.stt import transcribe_segment

logger = logging.getLogger(__name__)

# AD-11: same fixed context margin pattern as the acoustic classifier
# (acoustic/run.py) — fed to the STT model only, never altering the
# persisted TimelineSegment boundaries, so per-segment transcription isn't
# artificially discontinuous at chunk edges. Also reinforces the
# hallucination-on-silence mitigation (stt.py) by keeping model input
# VAD-bounded rather than raw full-Call audio.
CONTEXT_MARGIN_SECONDS = 0.5


def run_transcript(call_id: str) -> None:
    """**Deliberately does not follow run_ingest/run_acoustic's rollback-
    then-fail-Call pattern.** Per AC 4/AD-1, a transcript-stage failure must
    NEVER set Call.status = "failed" — the acoustic signal (Story 1.3)
    remains independently valid regardless of this stage's outcome. See the
    except block below: it logs and returns normally instead of
    rolling back + writing a failed status + re-raising."""
    conn = db.get_connection()
    try:
        logger.info("transcript generation started", extra={"extra_fields": {"call_id": call_id}})

        segments = db.get_timeline_segments(conn, call_id=call_id)
        _raw_waveform, mono_waveform, _sample_rate = load_mono_waveform(call_id)
        total_samples = mono_waveform.shape[-1]
        margin_samples = int(CONTEXT_MARGIN_SECONDS * VAD_SAMPLE_RATE)

        # Compute every turn/word for the whole Call in memory first, write
        # once at the end — same atomicity discipline as run_acoustic
        # (Story 1.3 code review): no risk of some turns persisting while
        # later segments in the same Call were never reached.
        turn_rows: list[tuple[str, str, int, float, float, str]] = []
        word_rows: list[tuple[str, str, int, str, float, float, float]] = []
        turn_index = 0
        for segment in segments:
            start_sample = int(segment["start_time"] * VAD_SAMPLE_RATE)
            end_sample = int(segment["end_time"] * VAD_SAMPLE_RATE)
            if end_sample <= start_sample:
                # Degenerate (zero/negative-width) segment — nothing to
                # transcribe. Unlike run_acoustic's AcousticSanityFloorError
                # (AD-1 requires acoustic to fail hard on this), transcript
                # generation simply skips it: AD-1 forbids treating any
                # transcript-stage condition as a Call-level failure, so
                # skipping the one degenerate segment and continuing with
                # the rest of the Call's turns is the correct behavior here.
                logger.warning(
                    "skipping zero/negative-width segment",
                    extra={"extra_fields": {"call_id": call_id, "segment_id": segment["id"]}},
                )
                continue

            # AD-11 context margin, same clipping-to-Call-duration logic as
            # run_acoustic's classifier input.
            context_start = max(0, start_sample - margin_samples)
            context_end = min(total_samples, end_sample + margin_samples)
            context_slice = mono_waveform[context_start:context_end].numpy()
            absolute_offset_seconds = context_start / VAD_SAMPLE_RATE

            # Code review (2026-08-13): isolate each segment's transcription
            # so one segment's failure (bad data, transient model error)
            # doesn't discard every other segment's already-computed turns
            # for the whole Call — same skip-and-continue philosophy as the
            # zero-width-segment guard above, now applied to transcription
            # errors too. Consistent with AD-1's "never fail the whole Call"
            # rule for this stage: partial results are strictly better than
            # none.
            try:
                turns = transcribe_segment(
                    context_slice, absolute_offset_seconds=absolute_offset_seconds
                )
            except Exception:
                logger.exception(
                    "segment transcription failed, skipping this segment",
                    extra={"extra_fields": {"call_id": call_id, "segment_id": segment["id"]}},
                )
                continue

            for turn in turns:
                turn_id = str(uuid.uuid4())
                turn_rows.append(
                    (turn_id, call_id, turn_index, turn.start_time, turn.end_time, turn.text)
                )
                for word_index, word in enumerate(turn.words):
                    word_rows.append(
                        (
                            str(uuid.uuid4()),
                            turn_id,
                            word_index,
                            word.word,
                            word.start_time,
                            word.end_time,
                            word.probability,
                        )
                    )
                turn_index += 1

        db.persist_transcript_turns(conn, turns=turn_rows, words=word_rows)

        logger.info(
            "transcript generation completed",
            extra={"extra_fields": {"call_id": call_id, "turn_count": len(turn_rows)}},
        )
        # AC 6: transcript generation alone does not complete a Call —
        # fusion (Story 1.6) is the only stage that can. Call.status is
        # never written by this function, in any code path (success or
        # failure), unlike run_ingest/run_acoustic.

        # Story 1.5: chain to the transcript-sentiment stage via the job
        # queue (AD-13), same intra-service stage-chaining pattern as
        # acoustic -> transcript (Story 1.4). Enqueued unconditionally on
        # success, even if turn_count == 0 — run_text_sentiment's own
        # empty-transcript no-op handles that case. Isolated in its own
        # try/except (same pattern Story 1.4's code review established for
        # run_acoustic's enqueue call): a queueing failure here (e.g. Redis
        # unreachable) must not be misreported as "transcript generation
        # failed" by the outer except below, since the transcript itself
        # was already written successfully.
        try:
            queue.get_text_sentiment_queue().enqueue(
                "app.pipeline.transcript.sentiment_run.run_text_sentiment", call_id
            )
        except Exception:
            logger.exception(
                "failed to enqueue transcript-sentiment job — transcript result "
                "stands, sentiment analysis will not run for this call",
                extra={"extra_fields": {"call_id": call_id}},
            )
            # Story 1.6 (AD-1, AC 1): if text-sentiment never even got the
            # chance to start, its own fusion-enqueue call sites will never
            # fire either — fusion must be enqueued from here instead. One
            # of five mutually exclusive fan-in call sites; see
            # fusion/run.py's module docstring for the full list.
            try:
                queue.get_fusion_queue().enqueue("app.pipeline.fusion.run.run_fusion", call_id)
            except Exception:
                logger.exception(
                    "failed to enqueue fusion job — transcript result stands, "
                    "this call will never reach Call.status = complete",
                    extra={"extra_fields": {"call_id": call_id}},
                )
    except Exception:
        # Deliberately blind: AD-1 requires every transcript-stage failure
        # (unpredictable ML-library errors,
        # missing audio, DB errors) to be absorbed here, not just a
        # pre-enumerated subset. AC 4/AD-1: log and return normally — no
        # rollback (nothing was ever committed; writes only happen once at
        # the very end, above, so there is no partial state to discard),
        # no Call.status write, no re-raise. The RQ job itself completes
        # "successfully" from RQ's own bookkeeping perspective: there is no
        # Call-level failure state for a transcript failure to feed into,
        # per AD-1. The absence of TranscriptTurn rows for this Call plus
        # this log line (with full traceback, via logger.exception) is the
        # only record of what happened.
        logger.exception(
            "transcript generation failed — Call continues without a transcript",
            extra={"extra_fields": {"call_id": call_id}},
        )
        # Story 1.6 (AD-1, AC 1): this path never reaches the
        # text-sentiment enqueue call above, so text-sentiment's own
        # fusion-enqueue call sites will never fire — fusion must be
        # enqueued from here instead, the only remaining path to
        # Call.status = "complete" for this Call. One of five mutually
        # exclusive fan-in call sites; see fusion/run.py's module
        # docstring for the full list.
        try:
            queue.get_fusion_queue().enqueue("app.pipeline.fusion.run.run_fusion", call_id)
        except Exception:
            logger.exception(
                "failed to enqueue fusion job — this call will never reach "
                "Call.status = complete",
                extra={"extra_fields": {"call_id": call_id}},
            )
    finally:
        conn.close()
