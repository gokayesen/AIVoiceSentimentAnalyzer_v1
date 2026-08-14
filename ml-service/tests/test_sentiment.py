"""Tests for the text-sentiment/emotion transformer classifier (Story 1.5,
AC 1/3)."""

from __future__ import annotations

from app.pipeline.transcript.sentiment import analyze_turn_text
from app.pipeline.transcript.sentiment_taxonomy import raw_label_to_text_emotion


def test_analyze_turn_text_returns_taxonomy_known_label_and_valid_confidence():
    label, confidence = analyze_turn_text("I am absolutely thrilled with this service, thank you!")

    assert 0.0 <= confidence <= 1.0
    raw_label_to_text_emotion(label)  # raises ValueError if unknown — assertion by non-raise


def test_higher_temperature_never_increases_confidence(monkeypatch):
    """AD-9: temperature scaling only ever flattens (or leaves unchanged),
    never sharpens, the calibrated confidence."""
    text = "This is a completely ordinary sentence about billing."

    monkeypatch.setattr("app.pipeline.transcript.sentiment.TEXT_SENTIMENT_TEMPERATURE", 1.0)
    _, confidence_t1 = analyze_turn_text(text)

    monkeypatch.setattr("app.pipeline.transcript.sentiment.TEXT_SENTIMENT_TEMPERATURE", 5.0)
    _, confidence_t5 = analyze_turn_text(text)

    assert confidence_t5 <= confidence_t1
