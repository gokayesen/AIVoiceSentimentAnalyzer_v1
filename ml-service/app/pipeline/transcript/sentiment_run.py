"""The transcript-sentiment RQ job (AC 1, 2, 3, 4, 5, 6, 7, 8) — Story 1.5.
Enqueued by `transcript/run.py` on successful transcript generation, chained
via the job queue (AD-13), consumed by the same RQ Worker process (AD-7)."""

from __future__ import annotations

import json
import logging

from app import db, queue
from app.pipeline.transcript.keywords import extract_keywords
from app.pipeline.transcript.sentiment import analyze_turn_text
from app.pipeline.transcript.sentiment_taxonomy import (
    raw_label_to_text_emotion,
    text_emotion_to_polarity,
)

logger = logging.getLogger(__name__)


def run_text_sentiment(call_id: str) -> None:
    """**Mirrors `run_transcript`'s failure semantics, not
    `run_ingest`/`run_acoustic`'s.** Per AC 6/AD-1, a transcript-sentiment-
    stage failure must NEVER set Call.status = "failed" — the acoustic
    signal (Story 1.3) and the raw transcript (Story 1.4) both remain
    independently valid regardless of this stage's outcome. See the except
    block below: it logs and returns normally instead of rolling back +
    writing a failed status + re-raising."""
    conn = db.get_connection()
    try:
        logger.info(
            "transcript-sentiment analysis started",
            extra={"extra_fields": {"call_id": call_id}},
        )

        turns = db.get_transcript_turns(conn, call_id=call_id)

        # Compute every turn's result in memory first, write once at the
        # end — same atomicity discipline as run_acoustic/run_transcript.
        results: list[db.TextSentimentResult] = []
        for turn in turns:
            # Per-turn isolation: one turn's analysis failure must not
            # discard every other turn's already-computed results for the
            # whole Call — same skip-and-continue philosophy Story 1.4's
            # code review added to run_transcript's per-segment loop.
            try:
                raw_label, confidence = analyze_turn_text(turn["text"])
                text_emotion = raw_label_to_text_emotion(raw_label)
                text_sentiment = text_emotion_to_polarity(text_emotion)
            except Exception:
                logger.exception(
                    "turn sentiment analysis failed, skipping this turn",
                    extra={"extra_fields": {"call_id": call_id, "turn_id": turn["id"]}},
                )
                continue

            # Code review (2026-08-14): keyword extraction is isolated in
            # its own try/except, separate from the sentiment/emotion
            # analysis above — a keyword-extraction-only failure must not
            # discard an already-successful sentiment/emotion result for
            # this turn. Keywords are a secondary enrichment; sentiment is
            # the mandatory result.
            try:
                keywords = extract_keywords(turn["text"])
            except Exception:
                logger.exception(
                    "keyword extraction failed for turn, keeping sentiment result with no keywords",
                    extra={"extra_fields": {"call_id": call_id, "turn_id": turn["id"]}},
                )
                keywords = []

            results.append(
                db.TextSentimentResult(
                    turn_id=turn["id"],
                    text_sentiment=text_sentiment,
                    text_emotion=text_emotion,
                    text_confidence=confidence,
                    text_keywords=json.dumps(keywords),
                )
            )

        db.persist_text_sentiment_results(conn, results=results)

        # Code review (2026-08-14): a Call where every turn's analysis
        # failed must not log identically to a Call with zero turns to
        # begin with — both would otherwise report "completed,
        # turn_count=0", hiding a full-Call analysis failure from
        # observability (AD-21).
        if turns and not results:
            logger.warning(
                "transcript-sentiment analysis completed but every turn failed",
                extra={"extra_fields": {"call_id": call_id, "turn_count_attempted": len(turns)}},
            )
        else:
            logger.info(
                "transcript-sentiment analysis completed",
                extra={"extra_fields": {"call_id": call_id, "turn_count": len(results)}},
            )
        # AC 6: transcript-sentiment analysis alone does not complete a
        # Call — fusion (Story 1.6) is the only stage that can. Call.status
        # is never written by this function, in any code path.

        # Story 1.6: chain to the fusion stage via the job queue (AD-13),
        # unconditionally on reaching this point (even if every turn's
        # analysis failed above and `results` is empty — fusion still runs
        # on the acoustic signal alone, single-modality, per AD-1). Isolated
        # in its own try/except, same pattern as every prior stage-chaining
        # enqueue. One of five mutually exclusive fan-in call sites; see
        # fusion/run.py's module docstring for the full list.
        try:
            queue.get_fusion_queue().enqueue("app.pipeline.fusion.run.run_fusion", call_id)
        except Exception:
            logger.exception(
                "failed to enqueue fusion job — transcript-sentiment result "
                "stands, this call will never reach Call.status = complete",
                extra={"extra_fields": {"call_id": call_id}},
            )
    except Exception:
        # Deliberately blind, same rationale as run_transcript's own except
        # block: AD-1 requires every transcript-path failure to be absorbed
        # here, not just a pre-enumerated subset. AC 6/AD-1: log and return
        # normally — no rollback (writes only happen once at the very end,
        # above, so there is no partial state to discard), no Call.status
        # write, no re-raise.
        logger.exception(
            "transcript-sentiment analysis failed — Call continues without it",
            extra={"extra_fields": {"call_id": call_id}},
        )
        # Story 1.6 (AD-1, AC 1): this path never reaches the fusion
        # enqueue call above, so fusion must be enqueued from here instead
        # — the only remaining path to Call.status = "complete" for this
        # Call. One of five mutually exclusive fan-in call sites; see
        # fusion/run.py's module docstring for the full list.
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
