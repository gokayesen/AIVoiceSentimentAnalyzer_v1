"""Rule-based, confidence-weighted fusion of the acoustic and text-sentiment
signals (AD-8, AD-15) — Story 1.6. Pure functions only: no SQLite, no RQ, no
audio/model loading — unit-testable in isolation (AD-21).

**Two Emotion taxonomies, one shared polarity vocabulary.** `acoustic_emotion`
values come from `acoustic/taxonomy.py`'s 4-class vocabulary; `text_emotion`
values come from `sentiment_taxonomy.py`'s 28-class GoEmotions-derived
vocabulary. These are intentionally different label spaces (AD-4 fixes only
the 4-value *polarity* vocabulary as cross-modal-comparable, not Emotion
itself). `fused_emotion`/`overall_emotion` therefore carry whichever taxonomy
the winning modality happens to use — this module never normalizes the two
into one vocabulary. `fused_sentiment`/`overall_sentiment` are always one of
the four shared polarity values: derived via `emotion_to_polarity` for the
acoustic reading (there is no stored `acoustic_sentiment` column) or read
directly for the text reading (already computed by Story 1.5).

**Disagreement flag (Story 1.9, AD-8).** `disagreement_flag` is `True` only
for a multimodal segment (never the single-modality case, which has no
second signal to disagree with) where the acoustic and text polarities
differ *and* both raw per-modality confidences individually exceed
`DISAGREEMENT_THRESHOLD` — a weak signal on either side never counts as a
"disagreement" worth surfacing, even if the two polarities happen to differ.
This check is independent of which modality ends up dominant (the fused
Sentiment/Emotion the segment eventually reports) and independent of the
Secondary Signal mechanism below, which already retains the non-dominant
reading unconditionally.
"""

from __future__ import annotations

from typing import NamedTuple

from app.config import DISAGREEMENT_THRESHOLD
from app.pipeline.acoustic.taxonomy import emotion_to_polarity


class FusedSegment(NamedTuple):
    """One `TimelineSegment`'s fusion output, plus the secondary
    (non-dominant) modality's raw reading — carried here only so
    `reduce_call` can compute the Call-level Secondary Signal. The
    `secondary_*` fields are not themselves persisted on `TimelineSegment`
    (see `db.FusedSegmentResult`, which has no `secondary_*` fields)."""

    fused_sentiment: str
    fused_emotion: str
    fused_confidence: float
    single_modality_flag: bool
    disagreement_flag: bool
    secondary_emotion: str | None
    secondary_confidence: float | None


class AnalysisResultReduction(NamedTuple):
    overall_sentiment: str
    overall_emotion: str
    overall_confidence: float
    single_modality_flag: bool
    secondary_signal_emotion: str | None
    secondary_signal_confidence: float | None
    segments_flagged_count: int


def _self_weighted_average(values_and_weights: list[tuple[float, float]]) -> float:
    """Confidence-weighted average where each value is weighted by itself
    (AD-8's "confidence-weighted averaging"): the more confident reading
    pulls the result toward itself more. Degrades to the single remaining
    value as every other weight -> 0."""
    numerator = sum(value * weight for value, weight in values_and_weights)
    denominator = sum(weight for _value, weight in values_and_weights)
    return numerator / denominator


def _weighted_vote(labels_and_weights: list[tuple[str, float]]) -> str:
    """Confidence-weighted vote for a categorical value: sum weight per
    distinct label, return the label with the largest summed weight — the
    categorical analogue of `_self_weighted_average` (AD-8).

    **Tie-break (code review, 2026-08-14):** when two labels end up with
    exactly equal summed weight, `max()` returns the first one encountered
    with that maximum — and `totals` accumulates in the order
    `labels_and_weights` is iterated, which Python dicts preserve by
    insertion. Callers pass segments in `segment_index` (chronological)
    order, so a tie resolves to the label carried by the **earliest**
    segment. This is deterministic and intentional, not incidental — but
    unlike `fuse_segment`'s explicit "ties favor acoustic" rule, it was
    previously undocumented here."""
    totals: dict[str, float] = {}
    for label, weight in labels_and_weights:
        totals[label] = totals.get(label, 0.0) + weight
    return max(totals.items(), key=lambda item: item[1])[0]


def fuse_segment(
    acoustic_emotion: str,
    acoustic_confidence: float,
    text_emotion: str | None,
    text_sentiment: str | None,
    text_confidence: float | None,
) -> FusedSegment:
    """AC 2/3 (AD-8, AD-1): fuses one `TimelineSegment`'s acoustic reading
    (always present, AD-1: acoustic is mandatory) with its overlapping text
    reading, if any. `text_emotion`/`text_sentiment`/`text_confidence` must
    be all `None` together or all present together (never partially `None`)
    — the caller (`fusion/run.py`, via `overlap.py`) is responsible for that
    invariant."""
    acoustic_sentiment = emotion_to_polarity(acoustic_emotion)

    if text_confidence is None:
        # Single-modality case: no averaging happens — there is nothing to
        # average against (AC 3).
        return FusedSegment(
            fused_sentiment=acoustic_sentiment,
            fused_emotion=acoustic_emotion,
            fused_confidence=acoustic_confidence,
            single_modality_flag=True,
            disagreement_flag=False,
            secondary_emotion=None,
            secondary_confidence=None,
        )

    fused_confidence = _self_weighted_average(
        [(acoustic_confidence, acoustic_confidence), (text_confidence, text_confidence)]
    )

    # AC1/AD-8: "exceed" is strict `>` (mirrors Story 1.8's "falls below" `<`
    # precedent for threshold language) — a confidence exactly at the
    # threshold never counts as clearing it.
    disagreement_flag = (
        acoustic_sentiment != text_sentiment
        and acoustic_confidence > DISAGREEMENT_THRESHOLD
        and text_confidence > DISAGREEMENT_THRESHOLD
    )

    if acoustic_confidence >= text_confidence:
        # Acoustic dominant. Ties favor acoustic — a dev-agent-documented
        # tie-break choice (code review, 2026-08-14: AD-1 mandates acoustic
        # as mandatory for fusion to *run* at all, it does not itself
        # specify per-segment tie-break priority; this rule is thematically
        # consistent with AD-1's voice-first spirit but is not a direct AD-1
        # requirement — do not cite it as one), mirroring overlap.py's own
        # honestly-labeled tie-break choice.
        return FusedSegment(
            fused_sentiment=acoustic_sentiment,
            fused_emotion=acoustic_emotion,
            fused_confidence=fused_confidence,
            single_modality_flag=False,
            disagreement_flag=disagreement_flag,
            secondary_emotion=text_emotion,
            secondary_confidence=text_confidence,
        )

    # Text dominant.
    return FusedSegment(
        fused_sentiment=text_sentiment,
        fused_emotion=text_emotion,
        fused_confidence=fused_confidence,
        single_modality_flag=False,
        disagreement_flag=disagreement_flag,
        secondary_emotion=acoustic_emotion,
        secondary_confidence=acoustic_confidence,
    )


def reduce_call(fused_segments: list[FusedSegment]) -> AnalysisResultReduction:
    """AC 4 (AD-8): a deterministic reduction over the Call's already-fused
    `TimelineSegment` results — never an independent fusion pass."""
    if not fused_segments:
        raise ValueError(
            "reduce_call requires at least one FusedSegment — a Call with "
            "zero TimelineSegment rows should never reach fusion"
        )

    overall_confidence = _self_weighted_average(
        [(s.fused_confidence, s.fused_confidence) for s in fused_segments]
    )
    overall_sentiment = _weighted_vote(
        [(s.fused_sentiment, s.fused_confidence) for s in fused_segments]
    )
    overall_emotion = _weighted_vote(
        [(s.fused_emotion, s.fused_confidence) for s in fused_segments]
    )
    single_modality_flag = all(s.single_modality_flag for s in fused_segments)

    secondary_candidates = [
        (s.secondary_emotion, s.secondary_confidence)
        for s in fused_segments
        if s.secondary_emotion is not None
    ]
    if secondary_candidates:
        secondary_signal_emotion = _weighted_vote(list(secondary_candidates))
        secondary_signal_confidence = _self_weighted_average(
            [(confidence, confidence) for _emotion, confidence in secondary_candidates]
        )
    else:
        secondary_signal_emotion = None
        secondary_signal_confidence = None

    segments_flagged_count = sum(1 for s in fused_segments if s.disagreement_flag)

    return AnalysisResultReduction(
        overall_sentiment=overall_sentiment,
        overall_emotion=overall_emotion,
        overall_confidence=overall_confidence,
        single_modality_flag=single_modality_flag,
        secondary_signal_emotion=secondary_signal_emotion,
        secondary_signal_confidence=secondary_signal_confidence,
        segments_flagged_count=segments_flagged_count,
    )
