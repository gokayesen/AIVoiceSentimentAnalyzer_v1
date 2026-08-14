"""Unit tests for the pure fusion logic (Story 1.6, AC 2, 3, 4, 6, 9)."""

from __future__ import annotations

import pytest

from app.pipeline.fusion import fuse as fuse_module
from app.pipeline.fusion.fuse import FusedSegment, fuse_segment, reduce_call


def test_fuse_segment_single_modality_returns_acoustic_reading_unchanged():
    result = fuse_segment(
        acoustic_emotion="happy",
        acoustic_confidence=0.8,
        text_emotion=None,
        text_sentiment=None,
        text_confidence=None,
    )
    assert result.fused_emotion == "happy"
    assert result.fused_sentiment == "positive"
    assert result.fused_confidence == 0.8
    assert result.single_modality_flag is True
    assert result.disagreement_flag is False
    assert result.secondary_emotion is None
    assert result.secondary_confidence is None


def test_fuse_segment_acoustic_dominant_when_higher_confidence():
    result = fuse_segment(
        acoustic_emotion="angry",
        acoustic_confidence=0.9,
        text_emotion="disappointed",
        text_sentiment="negative",
        text_confidence=0.4,
    )
    assert result.fused_emotion == "angry"
    assert result.fused_sentiment == "negative"
    assert result.single_modality_flag is False
    assert result.secondary_emotion == "disappointed"
    assert result.secondary_confidence == 0.4


def test_fuse_segment_text_dominant_when_higher_confidence():
    result = fuse_segment(
        acoustic_emotion="neutral",
        acoustic_confidence=0.3,
        text_emotion="excited",
        text_sentiment="positive",
        text_confidence=0.85,
    )
    assert result.fused_emotion == "excited"
    assert result.fused_sentiment == "positive"
    assert result.single_modality_flag is False
    assert result.secondary_emotion == "neutral"
    assert result.secondary_confidence == 0.3


def test_fuse_segment_ties_favor_acoustic():
    result = fuse_segment(
        acoustic_emotion="sad",
        acoustic_confidence=0.6,
        text_emotion="relieved",
        text_sentiment="positive",
        text_confidence=0.6,
    )
    assert result.fused_emotion == "sad"
    assert result.fused_sentiment == "negative"
    # This fixture already has a polarity mismatch (negative vs. positive) at
    # equal, above-default-threshold (0.6 > 0.5) confidence on both sides —
    # a naturally disagreeing scenario, now asserted on that axis too.
    assert result.disagreement_flag is True


def test_fuse_segment_confidence_weighting_formula():
    acoustic_confidence = 0.8
    text_confidence = 0.4
    expected = (acoustic_confidence**2 + text_confidence**2) / (
        acoustic_confidence + text_confidence
    )
    result = fuse_segment(
        acoustic_emotion="happy",
        acoustic_confidence=acoustic_confidence,
        text_emotion="admiring",
        text_sentiment="positive",
        text_confidence=text_confidence,
    )
    assert result.fused_confidence == pytest.approx(expected)


def test_fuse_segment_confidence_weighting_pulls_toward_more_confident_signal():
    result = fuse_segment(
        acoustic_emotion="happy",
        acoustic_confidence=0.9,
        text_emotion="disappointed",
        text_sentiment="negative",
        text_confidence=0.1,
    )
    # Self-weighted averaging must land strictly between the two raw values,
    # closer to the more confident one (0.9) than a plain arithmetic mean
    # (0.5) would.
    assert 0.5 < result.fused_confidence < 0.9


def test_fuse_segment_disagreement_flag_true_when_polarities_differ_and_both_confident():
    result = fuse_segment(
        acoustic_emotion="sad",  # -> negative
        acoustic_confidence=0.7,
        text_emotion="admiring",
        text_sentiment="positive",
        text_confidence=0.6,
    )
    assert result.disagreement_flag is True


def test_fuse_segment_disagreement_flag_false_when_polarities_agree_even_if_both_confident():
    result = fuse_segment(
        acoustic_emotion="angry",  # -> negative
        acoustic_confidence=0.9,
        text_emotion="disappointed",
        text_sentiment="negative",
        text_confidence=0.8,
    )
    assert result.disagreement_flag is False


def test_fuse_segment_disagreement_flag_false_when_one_modality_below_threshold():
    # Polarities differ (negative vs. positive) but the text confidence
    # (0.4) does not exceed the default 0.5 threshold — a weak signal on
    # either side must not trigger a flagged disagreement.
    result = fuse_segment(
        acoustic_emotion="angry",  # -> negative
        acoustic_confidence=0.9,
        text_emotion="admiring",
        text_sentiment="positive",
        text_confidence=0.4,
    )
    assert result.disagreement_flag is False


def test_fuse_segment_disagreement_flag_false_at_exact_threshold_boundary():
    # AC1's "exceed" is strict `>` — both confidences exactly at the default
    # 0.5 threshold never counts as clearing it, even with a real polarity
    # mismatch.
    result = fuse_segment(
        acoustic_emotion="sad",  # -> negative
        acoustic_confidence=0.5,
        text_emotion="admiring",
        text_sentiment="positive",
        text_confidence=0.5,
    )
    assert result.disagreement_flag is False


def test_fuse_segment_disagreement_flag_false_when_acoustic_below_threshold():
    # Mirror direction of the existing "weak text signal" case: polarities
    # differ (negative vs. positive) but this time it's the acoustic
    # confidence (0.4) that doesn't exceed the default 0.5 threshold.
    result = fuse_segment(
        acoustic_emotion="sad",  # -> negative
        acoustic_confidence=0.4,
        text_emotion="admiring",
        text_sentiment="positive",
        text_confidence=0.9,
    )
    assert result.disagreement_flag is False


def test_fuse_segment_disagreement_flag_false_at_asymmetric_boundary():
    # One side exactly at the threshold (never counts, strict `>`), the
    # other comfortably above it — still not a disagreement, since the
    # condition requires BOTH to individually exceed the threshold.
    result = fuse_segment(
        acoustic_emotion="sad",  # -> negative
        acoustic_confidence=0.5,
        text_emotion="admiring",
        text_sentiment="positive",
        text_confidence=0.9,
    )
    assert result.disagreement_flag is False


def test_fuse_segment_disagreement_flag_is_live_configurable_via_module_attribute():
    # Code review (2026-08-14): `fuse.py` does `from app.config import
    # DISAGREEMENT_THRESHOLD`, binding the name into fuse.py's own module
    # namespace at import time. Monkeypatching `app.config.DISAGREEMENT_
    # THRESHOLD` would NOT affect fuse_segment (it already holds its own
    # bound value) — the correct, and only working, patch target is the
    # `fuse` module's own attribute, exactly as Story 1.8 established for
    # web-api's `calls_module.LOW_CONFIDENCE_THRESHOLD`. This test proves
    # the threshold is genuinely live-configurable at fuse_segment's actual
    # point of consumption, not just validated in config.py.
    original = fuse_module.DISAGREEMENT_THRESHOLD
    try:
        fuse_module.DISAGREEMENT_THRESHOLD = 0.95
        result = fuse_segment(
            acoustic_emotion="sad",  # -> negative
            acoustic_confidence=0.9,
            text_emotion="admiring",
            text_sentiment="positive",
            text_confidence=0.9,
        )
        # Both confidences (0.9) no longer exceed the raised threshold
        # (0.95), so the same inputs that disagreed under the default no
        # longer do.
        assert result.disagreement_flag is False
    finally:
        fuse_module.DISAGREEMENT_THRESHOLD = original


def test_reduce_call_raises_on_empty_list():
    with pytest.raises(ValueError):
        reduce_call([])


def _segment(
    *,
    sentiment="positive",
    emotion="happy",
    confidence=0.8,
    single_modality=False,
    disagreement_flag=False,
    secondary_emotion=None,
    secondary_confidence=None,
) -> FusedSegment:
    return FusedSegment(
        fused_sentiment=sentiment,
        fused_emotion=emotion,
        fused_confidence=confidence,
        single_modality_flag=single_modality,
        disagreement_flag=disagreement_flag,
        secondary_emotion=secondary_emotion,
        secondary_confidence=secondary_confidence,
    )


def test_reduce_call_single_modality_flag_true_when_every_segment_is_single_modality():
    reduction = reduce_call(
        [
            _segment(single_modality=True),
            _segment(single_modality=True),
        ]
    )
    assert reduction.single_modality_flag is True


def test_reduce_call_single_modality_flag_false_when_mixed():
    reduction = reduce_call(
        [
            _segment(single_modality=True),
            _segment(single_modality=False, secondary_emotion="sad", secondary_confidence=0.3),
        ]
    )
    assert reduction.single_modality_flag is False


def test_reduce_call_single_modality_flag_false_when_none_single_modality():
    reduction = reduce_call(
        [
            _segment(single_modality=False, secondary_emotion="sad", secondary_confidence=0.3),
            _segment(single_modality=False, secondary_emotion="sad", secondary_confidence=0.3),
        ]
    )
    assert reduction.single_modality_flag is False


def test_reduce_call_secondary_signal_none_when_call_is_fully_single_modality():
    reduction = reduce_call([_segment(single_modality=True), _segment(single_modality=True)])
    assert reduction.secondary_signal_emotion is None
    assert reduction.secondary_signal_confidence is None


def test_reduce_call_secondary_signal_present_when_a_segment_had_two_signals():
    reduction = reduce_call(
        [
            _segment(single_modality=True),
            _segment(single_modality=False, secondary_emotion="sad", secondary_confidence=0.3),
        ]
    )
    assert reduction.secondary_signal_emotion == "sad"
    assert reduction.secondary_signal_confidence == 0.3


def test_reduce_call_segments_flagged_count_is_zero_when_no_segment_disagreed():
    reduction = reduce_call([_segment(), _segment(), _segment()])
    assert reduction.segments_flagged_count == 0


def test_reduce_call_segments_flagged_count_sums_disagreement_flags():
    reduction = reduce_call(
        [
            _segment(disagreement_flag=True),
            _segment(disagreement_flag=False),
            _segment(disagreement_flag=True),
        ]
    )
    assert reduction.segments_flagged_count == 2


def test_reduce_call_overall_confidence_is_self_weighted_average():
    reduction = reduce_call([_segment(confidence=0.9), _segment(confidence=0.1)])
    assert 0.5 < reduction.overall_confidence < 0.9


def test_reduce_call_overall_sentiment_is_confidence_weighted_vote():
    reduction = reduce_call(
        [
            _segment(sentiment="positive", confidence=0.9),
            _segment(sentiment="negative", confidence=0.2),
            _segment(sentiment="negative", confidence=0.2),
        ]
    )
    # "negative" wins even though it appears in more segments only because
    # its summed weight (0.4) is still less than "positive"'s single 0.9 —
    # this exercises the weighted-vote logic itself, not just majority count.
    assert reduction.overall_sentiment == "positive"


def test_reduce_call_single_segment_overall_confidence_equals_that_segment():
    reduction = reduce_call([_segment(confidence=0.42)])
    assert reduction.overall_confidence == pytest.approx(0.42)


def test_reduce_call_handles_genuinely_mixed_taxonomy_segments():
    """Code review (2026-08-14): segments can legitimately have different
    dominant modalities, and therefore fused_emotion values drawn from two
    different taxonomies (acoustic's 4-class vs. text's 28-class GoEmotions-
    derived set, see fuse.py's module docstring). reduce_call must resolve
    a Call-level winner deterministically without crashing when this
    happens — the cross-taxonomy pooling itself is documented, intentional
    behavior, not a defect this test is meant to catch; this test only
    proves it doesn't blow up and stays deterministic."""
    segments = [
        # Acoustic-dominant segment: fused_emotion from the 4-class taxonomy.
        _segment(sentiment="negative", emotion="angry", confidence=0.9),
        # Text-dominant segment: fused_emotion from the 28-class taxonomy.
        _segment(sentiment="positive", emotion="admiring", confidence=0.9),
    ]
    reduction = reduce_call(segments)
    assert reduction.overall_emotion in {"angry", "admiring"}
    # Equal weight (0.9 each) -> deterministic earliest-segment tie-break
    # (see _weighted_vote's own tie-break documentation).
    assert reduction.overall_emotion == "angry"
    assert reduction.overall_sentiment == "negative"
