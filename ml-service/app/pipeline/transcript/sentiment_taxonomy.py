"""Text-Emotion taxonomy + polarity lookup (AD-4, AD-15) — Story 1.5. Two
fixed stages, mirroring `acoustic/taxonomy.py`'s exact shape:

1. `raw_label_to_text_emotion` renames the classifier's raw label strings to
   full, readable, API-facing canonical Emotion names — the classifier's raw
   labels are an implementation detail of the chosen checkpoint, never a
   stored/API-facing value.
2. `text_emotion_to_polarity` maps each canonical text-Emotion to exactly
   one of the four UX-defined Sentiment polarity colors (negative/mixed/
   positive/neutral) — the *same* four-value vocabulary AD-4 fixed for the
   acoustic path (see `acoustic/taxonomy.py`), so Fusion (Story 1.6, AD-8)
   can compare polarities across modalities. This is a deliberately
   **separate** lookup table from the acoustic one — the two classifiers
   have different raw label sets; only the target vocabulary is shared.

Both raise on an unknown input: a classifier output outside the known label
set is a bug, not a data condition to silently default.

**`mixed` is reachable here** (unlike the acoustic-only taxonomy, whose own
comment already anticipated this): `confusion`, `realization`, and
`surprise` are ambivalent-valence enough (can be pleasant or unpleasant
depending on context) that mapping any of them to `positive`/`negative`
would misrepresent them — `mixed` is the honest polarity for all three.
"""

from __future__ import annotations

# Raw id2label strings from SamLowe/roberta-base-go_emotions's config.json
# (verified empirically at implementation time, not assumed) — the standard
# 28-class GoEmotions taxonomy this checkpoint was trained on.
_RAW_LABEL_TO_TEXT_EMOTION = {
    "admiration": "admiring",
    "amusement": "amused",
    "anger": "angry",
    "annoyance": "annoyed",
    "approval": "approving",
    "caring": "caring",
    "confusion": "confused",
    "curiosity": "curious",
    "desire": "desiring",
    "disappointment": "disappointed",
    "disapproval": "disapproving",
    "disgust": "disgusted",
    "embarrassment": "embarrassed",
    "excitement": "excited",
    "fear": "fearful",
    "gratitude": "grateful",
    "grief": "grieving",
    "joy": "happy",
    "love": "loving",
    "nervousness": "nervous",
    "optimism": "optimistic",
    "pride": "proud",
    "realization": "realizing",
    "relief": "relieved",
    "remorse": "remorseful",
    "sadness": "sad",
    "surprise": "surprised",
    "neutral": "neutral",
}

# The 28-class canonical text-Emotion taxonomy mapped to exactly one of the
# four UX polarity colors (AD-4's shared target vocabulary). Grouped by
# polarity below for readability; every row's rationale is simple valence
# (pleasant -> positive, unpleasant -> negative, ambivalent -> mixed,
# affectively flat -> neutral).
_TEXT_EMOTION_TO_POLARITY = {
    "neutral": "neutral",
    "curious": "neutral",
    # Pleasant valence.
    "admiring": "positive",
    "amused": "positive",
    "approving": "positive",
    "caring": "positive",
    "desiring": "positive",
    "excited": "positive",
    "grateful": "positive",
    "happy": "positive",
    "loving": "positive",
    "optimistic": "positive",
    "proud": "positive",
    "relieved": "positive",
    # Unpleasant valence.
    "angry": "negative",
    "annoyed": "negative",
    "disappointed": "negative",
    "disapproving": "negative",
    "disgusted": "negative",
    "embarrassed": "negative",
    "fearful": "negative",
    "grieving": "negative",
    "nervous": "negative",
    "remorseful": "negative",
    "sad": "negative",
    # Ambivalent valence (can be pleasant or unpleasant depending on
    # context) — where `mixed` becomes reachable.
    "confused": "mixed",
    "realizing": "mixed",
    "surprised": "mixed",
}


def raw_label_to_text_emotion(label: str) -> str:
    try:
        return _RAW_LABEL_TO_TEXT_EMOTION[label]
    except KeyError:
        raise ValueError(f"unknown raw text-sentiment classifier label: {label!r}") from None


def text_emotion_to_polarity(emotion: str) -> str:
    try:
        return _TEXT_EMOTION_TO_POLARITY[emotion]
    except KeyError:
        raise ValueError(f"unknown canonical text emotion: {emotion!r}") from None
