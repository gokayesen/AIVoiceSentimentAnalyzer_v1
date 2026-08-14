"""Tests for the embedding-based SER classifier (Story 1.3, AC 1/5/11)."""

from __future__ import annotations

import torchaudio

from app.pipeline.acoustic.classifier import classify_segment
from app.pipeline.acoustic.taxonomy import raw_label_to_emotion

_SR = 16000


def _load_mono_16k(path):
    waveform, sr = torchaudio.load(str(path))
    mono = waveform.mean(dim=0)
    if sr != _SR:
        mono = torchaudio.functional.resample(mono, orig_freq=sr, new_freq=_SR)
    return mono.numpy(), _SR


def test_classify_segment_returns_taxonomy_known_label_and_valid_confidence(fixtures_dir):
    waveform, sr = _load_mono_16k(fixtures_dir / "speech.wav")
    label, confidence = classify_segment(waveform, sr)

    assert 0.0 <= confidence <= 1.0
    raw_label_to_emotion(label)  # raises ValueError if unknown — assertion by non-raise


def test_higher_temperature_never_increases_confidence(monkeypatch, fixtures_dir):
    """AD-9: temperature scaling only ever flattens (or leaves unchanged),
    never sharpens, the calibrated confidence."""
    waveform, sr = _load_mono_16k(fixtures_dir / "speech.wav")

    monkeypatch.setattr("app.pipeline.acoustic.classifier.ACOUSTIC_TEMPERATURE", 1.0)
    _, confidence_t1 = classify_segment(waveform, sr)

    monkeypatch.setattr("app.pipeline.acoustic.classifier.ACOUSTIC_TEMPERATURE", 5.0)
    _, confidence_t5 = classify_segment(waveform, sr)

    assert confidence_t5 <= confidence_t1
