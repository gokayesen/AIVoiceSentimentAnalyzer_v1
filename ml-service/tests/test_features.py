"""Tests for handcrafted acoustic-feature extraction (Story 1.3, AC 2/3)."""

from __future__ import annotations

import torchaudio

from app.pipeline.acoustic.features import extract_features

_SR = 16000


def _load_mono_16k(path):
    waveform, sr = torchaudio.load(str(path))
    mono = waveform.mean(dim=0)
    if sr != _SR:
        mono = torchaudio.functional.resample(mono, orig_freq=sr, new_freq=_SR)
    return mono.numpy(), _SR


def test_features_on_steady_tone_are_finite_and_in_sane_ranges(fixtures_dir):
    y, sr = _load_mono_16k(fixtures_dir / "mono.wav")
    f = extract_features(y, sr)

    assert f.energy_rms_mean > 0
    assert 0.0 <= f.pause_ratio <= 1.0
    assert f.speaking_rate_estimate >= 0.0


def test_features_on_real_speech_are_finite_and_in_sane_ranges(fixtures_dir):
    y, sr = _load_mono_16k(fixtures_dir / "speech.wav")
    f = extract_features(y, sr)

    assert f.energy_rms_mean > 0
    assert 0.0 <= f.pause_ratio <= 1.0
    assert f.speaking_rate_estimate >= 0.0


def test_features_on_silence_yield_null_pitch_not_fabricated_zero(fixtures_dir):
    y, sr = _load_mono_16k(fixtures_dir / "silence.wav")
    f = extract_features(y, sr)

    assert f.pitch_mean_hz is None
    assert f.pitch_std_hz is None
    assert f.pause_ratio == 1.0
