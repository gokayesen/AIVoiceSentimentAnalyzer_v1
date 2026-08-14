"""Shared audio-loading helper used by multiple pipeline stages (ingest,
acoustic). Factored out in Story 1.3 to avoid two independently-drifting
copies of the same load -> downmix-to-mono -> resample-to-VAD_SAMPLE_RATE
logic that `ingest/run.py` (Story 1.2) already contained."""

from __future__ import annotations

from pathlib import Path

import torch
import torchaudio

from app.config import STORAGE_DIR
from app.pipeline.ingest.vad import VAD_SAMPLE_RATE


def find_audio_path(call_id: str) -> Path | None:
    call_dir = STORAGE_DIR / call_id
    matches = sorted(call_dir.glob("original.*"))
    return matches[0] if matches else None


def load_mono_waveform(call_id: str) -> tuple[torch.Tensor, torch.Tensor, int]:
    """Returns (raw_waveform [channels, samples], mono_waveform_at_VAD_SAMPLE_RATE
    [samples], original_sample_rate). Raises FileNotFoundError if no audio
    file exists for `call_id` — callers translate this to their own
    stage-specific failure semantics."""
    audio_path = find_audio_path(call_id)
    if audio_path is None:
        raise FileNotFoundError(f"no audio file found for call {call_id} under {STORAGE_DIR / call_id}")

    waveform, sample_rate = torchaudio.load(str(audio_path))

    # Downmix to mono for VAD/SER input (AD-2's stereo-channel speaker
    # assignment is a separate, later concern — Story 3.1 — not decided
    # here; both VAD and the acoustic classifier only need a single
    # speech-activity/prosody signal).
    mono_waveform = waveform.mean(dim=0)
    if sample_rate != VAD_SAMPLE_RATE:
        mono_waveform = torchaudio.functional.resample(
            mono_waveform, orig_freq=sample_rate, new_freq=VAD_SAMPLE_RATE
        )
    return waveform, mono_waveform, sample_rate
