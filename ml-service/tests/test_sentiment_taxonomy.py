"""Tests for the text-Emotion taxonomy + polarity lookup (Story 1.5, AC 4/5)."""

from __future__ import annotations

import pytest

from app.pipeline.transcript.sentiment_taxonomy import (
    raw_label_to_text_emotion,
    text_emotion_to_polarity,
)

_KNOWN_POLARITIES = {"negative", "mixed", "positive", "neutral"}

# The real model's raw id2label values (SamLowe/roberta-base-go_emotions),
# verified empirically at implementation time — see sentiment.py/
# sentiment_taxonomy.py docstrings.
_REAL_RAW_LABELS = [
    "admiration", "amusement", "anger", "annoyance", "approval", "caring",
    "confusion", "curiosity", "desire", "disappointment", "disapproval",
    "disgust", "embarrassment", "excitement", "fear", "gratitude", "grief",
    "joy", "love", "nervousness", "optimism", "pride", "realization",
    "relief", "remorse", "sadness", "surprise", "neutral",
]


def test_every_real_raw_label_maps_to_a_known_text_emotion():
    for label in _REAL_RAW_LABELS:
        emotion = raw_label_to_text_emotion(label)
        assert isinstance(emotion, str) and emotion


def test_every_canonical_text_emotion_maps_to_exactly_one_known_polarity():
    for label in _REAL_RAW_LABELS:
        emotion = raw_label_to_text_emotion(label)
        polarity = text_emotion_to_polarity(emotion)
        assert polarity in _KNOWN_POLARITIES


def test_unknown_raw_label_raises():
    with pytest.raises(ValueError):
        raw_label_to_text_emotion("not-a-real-label")


def test_unknown_text_emotion_raises():
    with pytest.raises(ValueError):
        text_emotion_to_polarity("not-a-real-emotion")


def test_mixed_polarity_is_reachable_via_surprise():
    """AC 5: unlike the acoustic-only taxonomy (where `mixed` is not
    reachable), this 28-class text taxonomy includes ambivalent-valence
    categories (e.g. `surprise`) that map to `mixed`."""
    emotion = raw_label_to_text_emotion("surprise")
    assert text_emotion_to_polarity(emotion) == "mixed"


def test_polarity_table_only_produces_known_polarities():
    from app.pipeline.transcript import sentiment_taxonomy

    all_polarities = {
        sentiment_taxonomy.text_emotion_to_polarity(e)
        for e in sentiment_taxonomy._TEXT_EMOTION_TO_POLARITY
    }
    assert all_polarities <= _KNOWN_POLARITIES
