"""VAD/chunk-boundary detection (AD-11) via Silero VAD — dev-agent library
choice, not an Architecture mandate (MIT-licensed, recommended by Technical
Research §3.2/§11; not in the Stack table). See story Dev Agent Record."""

from __future__ import annotations

import torch
from silero_vad import get_speech_timestamps, load_silero_vad

VAD_SAMPLE_RATE = 16000

_model = None


def _get_model():
    global _model
    if _model is None:
        _model = load_silero_vad()
    return _model


def compute_speech_boundaries(mono_waveform: torch.Tensor) -> list[tuple[float, float]]:
    """`mono_waveform` must already be 1-D, float, at VAD_SAMPLE_RATE.
    Returns an ordered list of (start_seconds, end_seconds) tuples."""
    model = _get_model()
    timestamps = get_speech_timestamps(
        mono_waveform,
        model,
        sampling_rate=VAD_SAMPLE_RATE,
        return_seconds=True,
    )
    return [(ts["start"], ts["end"]) for ts in timestamps]
