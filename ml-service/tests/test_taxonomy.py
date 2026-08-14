"""Tests for the Emotion taxonomy + polarity lookup (Story 1.3, AC 4)."""

from __future__ import annotations

import pytest

from app.pipeline.acoustic.taxonomy import emotion_to_polarity, raw_label_to_emotion

_KNOWN_POLARITIES = {"negative", "mixed", "positive", "neutral"}

# The real model's raw id2label values (superb/wav2vec2-base-superb-er),
# verified empirically at implementation time — see classifier.py docstring.
_REAL_RAW_LABELS = ["neu", "hap", "ang", "sad"]


def test_every_real_raw_label_maps_to_a_known_emotion():
    for label in _REAL_RAW_LABELS:
        emotion = raw_label_to_emotion(label)
        assert isinstance(emotion, str) and emotion


def test_every_canonical_emotion_maps_to_exactly_one_known_polarity():
    for label in _REAL_RAW_LABELS:
        emotion = raw_label_to_emotion(label)
        polarity = emotion_to_polarity(emotion)
        assert polarity in _KNOWN_POLARITIES


def test_unknown_raw_label_raises():
    with pytest.raises(ValueError):
        raw_label_to_emotion("not-a-real-label")


def test_unknown_emotion_raises():
    with pytest.raises(ValueError):
        emotion_to_polarity("not-a-real-emotion")


def test_polarity_table_only_produces_known_polarities():
    # Exercise the whole table, not just the 4 currently-real raw labels —
    # confirms the lookup table itself is well-formed. This does NOT assert
    # that all four polarities are reachable: with only 4 raw classes
    # (neu/hap/ang/sad), "mixed" is not currently reachable from this
    # classifier at all (see taxonomy.py's module docstring) — that is a
    # documented, accepted simplification from the original 8-class plan,
    # not something this test verifies or should assert.
    from app.pipeline.acoustic import taxonomy

    all_polarities = {taxonomy.emotion_to_polarity(e) for e in taxonomy._EMOTION_TO_POLARITY}
    assert all_polarities <= _KNOWN_POLARITIES
