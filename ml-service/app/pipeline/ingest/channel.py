"""Channel-count detection (AD-2). Only detects and persists the count —
stereo-channel-index speaker assignment and mono diarization dispatch are
Stories 3.1/3.2 (Epic 3), not built here."""

from __future__ import annotations

import torch


def detect_channel_count(waveform: torch.Tensor) -> int:
    """`waveform` is the [channels, samples] tensor from torchaudio.load()."""
    return waveform.shape[0]
