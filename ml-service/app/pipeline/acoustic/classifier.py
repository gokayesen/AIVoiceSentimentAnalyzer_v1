"""Embedding-based SER classifier (AD-3, AC 1/5/11) — dev-agent model choice,
not an Architecture mandate (see story 1-3's Dev Agent Record for the full
rationale): `superb/wav2vec2-base-superb-er`, apache-2.0, the official SUPERB
benchmark IEMOCAP 4-class Emotion Recognition submission.

**Empirically verified model-loading gap (see story Debug Log):** the
originally-chosen alternative, `ehcalabres/wav2vec2-lg-xlsr-en-speech-
emotion-recognition` (a genuinely backbone-fine-tuned RAVDESS 8-class model),
was rejected after `AutoModelForAudioClassification.from_pretrained(...)`
reported its classifier head weights as MISSING under transformers 5.14.1 —
that checkpoint's classifier submodule naming (`classifier.dense.*`/
`classifier.output.*`) doesn't match current transformers' expected
`Wav2Vec2ForSequenceClassification` head naming (`projector.*`/
`classifier.weight`/`classifier.bias`), so its classification head silently
loads as **randomly initialized**, not the actual trained weights — a
non-functional classifier despite loading without error. `superb/
wav2vec2-base-superb-er` was verified to load with zero MISSING/UNEXPECTED
keys. A working linear-probe beats a checkpoint whose "fine-tuned" head
doesn't actually load.

The model's published 62.58% frozen-feature IEMOCAP accuracy (source: the
model's Hugging Face model card, https://huggingface.co/superb/wav2vec2-base-superb-er
— verified at implementation time, same as this model's apache-2.0 license
and id2label mapping) is an optimistic upper bound (AD-17), not this
system's expected accuracy on real call-center-style audio (a comparable
architecture shows a ~17-point absolute accuracy drop moving from lab data
to real call-center audio — see Technical Research §1.5).

Returns the model's own raw label (not the canonical Emotion taxonomy —
see `taxonomy.py` for that mapping, applied by the caller) and a
temperature-scaled calibrated confidence (AD-9) — never the raw,
uncalibrated softmax value.
"""

from __future__ import annotations

import numpy as np
import torch
from transformers import AutoFeatureExtractor, AutoModelForAudioClassification

from app.config import ACOUSTIC_MODEL_NAME, ACOUSTIC_TEMPERATURE

_model = None
_feature_extractor = None


def _get_model():
    global _model, _feature_extractor
    if _model is None:
        _model = AutoModelForAudioClassification.from_pretrained(ACOUSTIC_MODEL_NAME)
        _model.eval()
        _feature_extractor = AutoFeatureExtractor.from_pretrained(ACOUSTIC_MODEL_NAME)
    return _model, _feature_extractor


def classify_segment(waveform: np.ndarray, sr: int) -> tuple[str, float]:
    """`waveform` should include Task 6's AD-11 context margin (a small
    fixed padding into neighboring audio) when called from the pipeline —
    this function itself is agnostic to that, it just classifies whatever
    slice it's given."""
    model, feature_extractor = _get_model()
    inputs = feature_extractor(waveform, sampling_rate=sr, return_tensors="pt")
    with torch.no_grad():
        logits = model(**inputs).logits
    # AD-9: temperature scaling before softmax — the sole required MVP
    # calibration mechanism. Never return the raw uncalibrated softmax max.
    calibrated = torch.nn.functional.softmax(logits / ACOUSTIC_TEMPERATURE, dim=-1)
    idx = int(torch.argmax(calibrated, dim=-1).item())
    confidence = float(calibrated[0, idx].item())
    label = model.config.id2label[idx]
    return label, confidence
