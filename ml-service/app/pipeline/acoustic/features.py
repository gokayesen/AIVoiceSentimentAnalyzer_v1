"""Handcrafted acoustic-feature extraction (AD-3, AC 2/3) — the mandatory
explainability layer, persisted as one AcousticEvidence row per
TimelineSegment. Only librosa/torchaudio calls anywhere in this module (AC
3) — never openSMILE/eGeMAPS or Praat/parselmouth, even transitively.

`speaking_rate_estimate` is a documented **approximation**: true
words-per-minute needs STT, unavailable until Story 1.4/1.5. It is an
unsupervised syllable-nuclei-rate proxy (onset-peak count over the RMS
envelope, divided by voiced duration) — an acoustic proxy, not a linguistic
syllable/word count.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import librosa
import numpy as np

logger = logging.getLogger(__name__)

# Typical human speech fundamental-frequency range (Hz) — a broad band
# covering both low male and high female/child voices, not a tuned value.
_PITCH_FMIN_HZ = 65.0
_PITCH_FMAX_HZ = 400.0


@dataclass
class AcousticFeatures:
    pitch_mean_hz: float | None
    pitch_std_hz: float | None
    energy_rms_mean: float
    speaking_rate_estimate: float
    pause_ratio: float


def extract_features(y: np.ndarray, sr: int) -> AcousticFeatures:
    """`y` is a 1-D mono float array (already downmixed/resampled by the
    caller — app.audio.load_mono_waveform), `sr` is its sample rate."""
    energy_rms_mean = float(np.mean(librosa.feature.rms(y=y)))

    voiced_flag: np.ndarray | None = None
    f0: np.ndarray | None = None
    try:
        f0, voiced_flag, _voiced_prob = librosa.pyin(
            y, fmin=_PITCH_FMIN_HZ, fmax=_PITCH_FMAX_HZ, sr=sr
        )
    except Exception:
        # Segment too short (or otherwise degenerate) for pyin's default
        # frame/window sizing — treat as "no voiced frames determinable"
        # rather than failing the whole acoustic stage over a feature that
        # is explainability evidence, not a hard classification input.
        logger.exception("pyin pitch extraction failed, treating segment as unvoiced")
        voiced_flag = None

    if voiced_flag is None or voiced_flag.size == 0:
        pitch_mean_hz = None
        pitch_std_hz = None
        pause_ratio = 1.0
        voiced_duration_s = 0.0
    else:
        voiced_f0 = f0[voiced_flag]
        if voiced_f0.size == 0:
            pitch_mean_hz = None
            pitch_std_hz = None
        else:
            pitch_mean_hz = float(np.mean(voiced_f0))
            pitch_std_hz = float(np.std(voiced_f0))
        pause_ratio = 1.0 - float(np.mean(voiced_flag))
        frame_duration_s = librosa.get_duration(y=y, sr=sr) / voiced_flag.size
        voiced_duration_s = float(np.count_nonzero(voiced_flag)) * frame_duration_s

    if voiced_duration_s > 0:
        try:
            onset_times = librosa.onset.onset_detect(y=y, sr=sr, units="time")
            speaking_rate_estimate = float(len(onset_times)) / voiced_duration_s
        except Exception:
            # Same rationale as the pyin guard above: a degenerate segment
            # shouldn't fail the whole acoustic stage over an explainability
            # feature, not a hard classification input.
            logger.exception("onset detection failed, treating segment as having no onsets")
            speaking_rate_estimate = 0.0
    else:
        speaking_rate_estimate = 0.0

    return AcousticFeatures(
        pitch_mean_hz=pitch_mean_hz,
        pitch_std_hz=pitch_std_hz,
        energy_rms_mean=energy_rms_mean,
        speaking_rate_estimate=speaking_rate_estimate,
        pause_ratio=pause_ratio,
    )
