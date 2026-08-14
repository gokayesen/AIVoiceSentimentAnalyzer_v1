"""Tests for keyword/context extraction (Story 1.5, AC 1/2)."""

from __future__ import annotations

from app.pipeline.transcript.keywords import _MAX_KEYWORDS, extract_keywords


def test_extract_keywords_on_content_bearing_text_returns_capped_nonempty_list():
    text = (
        "I would like to request a refund for my recent order because the "
        "product arrived damaged and customer support has not responded."
    )

    keywords = extract_keywords(text)

    assert 0 < len(keywords) <= _MAX_KEYWORDS
    assert all(isinstance(k, str) and k for k in keywords)


def test_extract_keywords_on_low_content_turn_does_not_raise():
    for text in ["yes", "okay", "", "   "]:
        keywords = extract_keywords(text)
        assert isinstance(keywords, list)
        assert len(keywords) <= _MAX_KEYWORDS
