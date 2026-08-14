"""Emotion taxonomy + polarity lookup (AD-4). Two fixed stages:

1. `raw_label_to_emotion` renames the classifier's raw short label codes
   (`neu`/`hap`/`ang`/`sad`) to full, readable, API-facing canonical Emotion
   names — the classifier's raw codes are an implementation detail of the
   chosen checkpoint, never a stored/API-facing value.
2. `emotion_to_polarity` maps each canonical Emotion to exactly one of the
   four UX-defined Sentiment polarity colors (negative/mixed/positive/
   neutral) — see ux-designs DESIGN.md's semantic color tokens.

Both raise on an unknown input: a classifier output outside the known label
set is a bug, not a data condition to silently default.

**"mixed" is not reachable** from this 4-class acoustic-only mapping — no
canonical Emotion in this taxonomy is ambivalent-valence enough to justify
it. Acceptable per AD-4 (the table must map to *one of* the four, not
exercise all four); becomes reachable only if the taxonomy is later
extended with an ambivalent-valence category (e.g. "surprised").
"""

from __future__ import annotations

# Raw id2label strings from superb/wav2vec2-base-superb-er's config.json
# (verified empirically at implementation time, not assumed) — the
# conventional SUPERB IEMOCAP 4-class evaluation protocol.
_RAW_LABEL_TO_EMOTION = {
    "neu": "neutral",
    "hap": "happy",
    "ang": "angry",
    "sad": "sad",
}

# The 4-class canonical Emotion taxonomy (AD-4-compliant) mapped to exactly
# one of the four UX polarity colors.
_EMOTION_TO_POLARITY = {
    "neutral": "neutral",
    "happy": "positive",
    "sad": "negative",
    "angry": "negative",
}


def raw_label_to_emotion(label: str) -> str:
    try:
        return _RAW_LABEL_TO_EMOTION[label]
    except KeyError:
        raise ValueError(f"unknown raw classifier label: {label!r}") from None


def emotion_to_polarity(emotion: str) -> str:
    try:
        return _EMOTION_TO_POLARITY[emotion]
    except KeyError:
        raise ValueError(f"unknown canonical emotion: {emotion!r}") from None
