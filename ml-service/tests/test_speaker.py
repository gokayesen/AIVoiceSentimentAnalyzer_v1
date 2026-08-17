"""Unit tests for stereo channel-based speaker attribution (Story 3.1, AD-2).

Uses synthetic 2-channel `torch.Tensor`s with known per-channel energy —
fast and precise, independent of STT/VAD (neither is invoked by
`assign_stereo_speaker`).
"""

from __future__ import annotations

import torch

from app.pipeline.transcript.speaker import CHANNEL_SPEAKER_LABELS, assign_stereo_speaker

SAMPLE_RATE = 16000


def _stereo_waveform(*, louder_channel: int, duration_s: float = 1.0) -> torch.Tensor:
    """Two channels of the same length: `louder_channel` carries a
    full-amplitude tone, the other is silence — an unambiguous energy
    difference for asserting correct channel selection."""
    samples = int(duration_s * SAMPLE_RATE)
    quiet = torch.zeros(samples)
    loud = torch.ones(samples)
    return torch.stack([loud, quiet]) if louder_channel == 0 else torch.stack([quiet, loud])


def test_picks_channel_0_when_channel_0_is_louder():
    waveform = _stereo_waveform(louder_channel=0)
    result = assign_stereo_speaker(waveform, SAMPLE_RATE, start_time=0.0, end_time=1.0)
    assert result == (0, "Speaker A")


def test_picks_channel_1_when_channel_1_is_louder():
    waveform = _stereo_waveform(louder_channel=1)
    result = assign_stereo_speaker(waveform, SAMPLE_RATE, start_time=0.0, end_time=1.0)
    assert result == (1, "Speaker B")


def test_canonical_labels_are_fixed_and_ordered():
    assert CHANNEL_SPEAKER_LABELS == ("Speaker A", "Speaker B")


def test_only_compares_energy_within_the_requested_window():
    """A channel that's louder outside [start_time, end_time) must not win —
    only the windowed slice's energy is compared."""
    samples = SAMPLE_RATE  # 1 second
    channel0 = torch.zeros(samples)
    channel0[: samples // 2] = 1.0  # loud in the first half only
    channel1 = torch.zeros(samples)
    channel1[samples // 2 :] = 1.0  # loud in the second half only
    waveform = torch.stack([channel0, channel1])

    first_half = assign_stereo_speaker(waveform, SAMPLE_RATE, start_time=0.0, end_time=0.5)
    second_half = assign_stereo_speaker(waveform, SAMPLE_RATE, start_time=0.5, end_time=1.0)

    assert first_half == (0, "Speaker A")
    assert second_half == (1, "Speaker B")


def test_returns_none_for_zero_width_window():
    waveform = _stereo_waveform(louder_channel=0)
    assert assign_stereo_speaker(waveform, SAMPLE_RATE, start_time=0.5, end_time=0.5) is None


def test_returns_none_for_negative_width_window():
    waveform = _stereo_waveform(louder_channel=0)
    assert assign_stereo_speaker(waveform, SAMPLE_RATE, start_time=0.8, end_time=0.2) is None


def test_clips_end_time_beyond_waveform_length_instead_of_raising():
    waveform = _stereo_waveform(louder_channel=1, duration_s=1.0)
    result = assign_stereo_speaker(waveform, SAMPLE_RATE, start_time=0.0, end_time=10.0)
    assert result == (1, "Speaker B")


def test_negative_start_time_clips_to_zero_instead_of_raising():
    waveform = _stereo_waveform(louder_channel=0, duration_s=1.0)
    result = assign_stereo_speaker(waveform, SAMPLE_RATE, start_time=-5.0, end_time=1.0)
    assert result == (0, "Speaker A")
