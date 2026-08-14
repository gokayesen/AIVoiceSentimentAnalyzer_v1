"""Text-sentiment/emotion transformer classifier (AD-19, AC 1/3) — Story 1.5.
Dev-agent model choice, not an Architecture mandate (see story 1-5's Dev
Agent Record for the full rationale): `SamLowe/roberta-base-go_emotions`, a
RoBERTa-base checkpoint fine-tuned on the 28-class GoEmotions dataset,
MIT-licensed (verified at implementation time — a different, unlicensed
checkpoint was rejected during implementation, see Dev Agent Record).

**Dev-agent simplification, documented deliberately:** this checkpoint was
trained for *multi-label* classification (independent per-class sigmoid
probabilities — more than one emotion may genuinely apply to a sentence),
but this story's schema needs exactly one dominant `text_emotion` value per
`TranscriptTurn`. Rather than a per-class sigmoid+threshold (which could
yield zero or many labels per turn), this module applies AD-9's
temperature-scaled **softmax** over the model's raw logits and takes the
single highest-probability class — a deliberate reinterpretation of a
multi-label model as "pick the single most dominant emotion," not a defect.
The resulting confidence is still a genuine temperature-calibrated value,
just computed over a softmax redistribution rather than the model's native
independent sigmoids.

Mirrors `acoustic/classifier.py`'s exact shape: a lazy-singleton model,
`AutoTokenizer` in place of `AutoFeatureExtractor`, and the same
temperature-scaling-before-softmax calibration (AD-9). Returns the model's
own raw label (not the canonical Emotion/Sentiment taxonomy — see
`sentiment_taxonomy.py` for that mapping, applied by the caller) and a
temperature-scaled calibrated confidence — never the raw, uncalibrated
softmax value.
"""

from __future__ import annotations

import torch
from transformers import AutoModelForSequenceClassification, AutoTokenizer

from app.config import TEXT_SENTIMENT_MODEL_NAME, TEXT_SENTIMENT_TEMPERATURE

_model = None
_tokenizer = None

# Code review (2026-08-14): RoBERTa-family models have a 512-token position-
# embedding limit. `truncation=True` alone does not guarantee truncation at
# a sane length if the checkpoint's tokenizer_config.json ever fails to
# declare a real `model_max_length` (some tokenizers fall back to a
# sentinel "very large int" meaning "unset"). Pinning an explicit
# `_MAX_TOKENS` removes that dependency on the checkpoint's own config.
_MAX_TOKENS = 512


def _get_model():
    global _model, _tokenizer
    if _model is None:
        _model = AutoModelForSequenceClassification.from_pretrained(TEXT_SENTIMENT_MODEL_NAME)
        _model.eval()
        _tokenizer = AutoTokenizer.from_pretrained(TEXT_SENTIMENT_MODEL_NAME)
    return _model, _tokenizer


def analyze_turn_text(text: str) -> tuple[str, float]:
    """`text` should be a single `TranscriptTurn.text` value. Returns
    (raw_label, calibrated_confidence) — the caller maps `raw_label` through
    `sentiment_taxonomy.py` to canonical Emotion/Sentiment values."""
    model, tokenizer = _get_model()
    inputs = tokenizer(text, return_tensors="pt", truncation=True, max_length=_MAX_TOKENS)
    with torch.no_grad():
        logits = model(**inputs).logits
    # AD-9: temperature scaling before softmax — the sole required MVP
    # calibration mechanism. Never return the raw uncalibrated softmax max.
    calibrated = torch.nn.functional.softmax(logits / TEXT_SENTIMENT_TEMPERATURE, dim=-1)
    idx = int(torch.argmax(calibrated, dim=-1).item())
    confidence = float(calibrated[0, idx].item())
    label = model.config.id2label[idx]
    return label, confidence
