"""Stereo channel-based speaker attribution (Story 3.1, AD-2). Deterministic:
speaker identity is assigned by comparing which channel carries more energy
during a `TranscriptTurn`'s time window — no diarization model runs for
stereo Calls. Mono-path diarization (Story 3.2) and its uncertainty states
(Story 3.3) are not implemented here."""

from __future__ import annotations

import math

import torch

# AD-4-style fixed lookup: channel index -> canonical display label. Never
# the raw channel index itself (AC3) — this table is the only place that
# index is ever translated into the display-facing value. Deliberately
# fixed at 2 entries: this module only ever runs for channel_count == 2
# Calls (see transcript/run.py's caller) — a >2-channel Call is left
# unattributed entirely rather than guessing a policy this story's ACs
# don't define (deferred-work.md, Story 1.2 review).
CHANNEL_SPEAKER_LABELS: tuple[str, str] = ("Speaker A", "Speaker B")


def assign_stereo_speaker(
    raw_waveform: torch.Tensor,
    sample_rate: int,
    *,
    start_time: float,
    end_time: float,
) -> tuple[int, str] | None:
    """Returns `(channel_index, canonical_label)` for the channel with higher
    mean-squared energy over `[start_time, end_time)`, or `None` for a
    degenerate (zero/negative-width, after clipping to the waveform's own
    sample range) window — mirrors `transcript/run.py`'s existing
    zero-width-segment guard rather than raising.

    `raw_waveform` is `[channels, samples]` at its *original* `sample_rate`
    (i.e. `load_mono_waveform`'s first return value, not the VAD-resampled
    mono mix) — AD-2's channel-index provenance must reflect the real input
    channels. `start_time`/`end_time` are Call-absolute float seconds (the
    same unit `TurnResult.start_time`/`end_time` already use), converted to
    sample indices via `sample_rate` here.

    Code review (2026-08-17): also returns `None` — rather than raising —
    for a non-finite (NaN/Inf) timestamp or a `raw_waveform` that isn't
    exactly 2 channels. `run.py`'s caller already gates on `channel_count
    == 2`, so the latter is not reachable today, but this function has no
    way to enforce that a future caller (e.g. Story 3.2/3.4, which the
    story's own Dev Notes say will extend this same package) replicates
    that exact gate — defending here too means a misuse elsewhere degrades
    to "this turn stays unattributed" instead of an uncaught `IndexError`.
    """
    if raw_waveform.shape[0] != len(CHANNEL_SPEAKER_LABELS):
        return None
    if not (math.isfinite(start_time) and math.isfinite(end_time)):
        return None

    start_sample = max(0, int(start_time * sample_rate))
    end_sample = min(raw_waveform.shape[-1], int(end_time * sample_rate))
    if end_sample <= start_sample:
        return None

    window = raw_waveform[:, start_sample:end_sample]
    energy_per_channel = window.pow(2).mean(dim=-1)
    # A perfect tie (equal energy on both channels, e.g. simultaneous
    # cross-talk or a fully silent window) resolves to channel 0/"Speaker A"
    # via argmax's lowest-index tie-break — deterministic, not a bug: AC5
    # forbids inventing any confidence/uncertainty signal for this path, so
    # there is no "ambiguous" state to report, only a fixed pick.
    channel_index = int(torch.argmax(energy_per_channel).item())
    return channel_index, CHANNEL_SPEAKER_LABELS[channel_index]
