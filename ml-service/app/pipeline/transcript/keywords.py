"""Keyword/context extraction (AD-19, AC 1/2) — Story 1.5. Dev-agent
technique choice, not an Architecture mandate: `yake` (Yet Another Keyword
Extractor) — unsupervised, purely statistical (co-occurrence/position/
casing heuristics over the input text itself), no model weights, no
training data, fully offline. AD-19 forbids any general-purpose LLM for
this stage; YAKE never invokes one.

YAKE's own score is inverted (**lower is better** — it is a deviation-from-
ideal-keyword score, not a relevance score), so results are sorted
ascending and only the keyword strings are returned, never the raw score.
"""

from __future__ import annotations

import yake

_MAX_KEYWORDS = 8

_extractor = yake.KeywordExtractor(lan="en", top=_MAX_KEYWORDS)


def extract_keywords(text: str) -> list[str]:
    """Returns up to `_MAX_KEYWORDS` keywords/short phrases, most relevant
    first. A very short or low-content turn (e.g. "okay", "yes") may
    legitimately yield an empty list — never an error."""
    if not text.strip():
        return []
    scored = _extractor.extract_keywords(text)
    # Code review (2026-08-14): YAKE's own `extract_keywords()` already
    # returns results ranked ascending by score, but that ordering isn't
    # part of its documented public contract — sorting explicitly here is
    # deliberate defense against a future YAKE version changing that
    # internal behavior, not redundant leftover code.
    ranked = sorted(scored, key=lambda pair: pair[1])
    return [keyword for keyword, _score in ranked[:_MAX_KEYWORDS]]
