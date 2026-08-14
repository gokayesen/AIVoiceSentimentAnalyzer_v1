"""Decodability + duration probe for uploaded audio (FR-1 AC4, AD-20).

Not an Architecture mandate (Stack table pins librosa/torchaudio to ml-service's
feature extraction, AD-3, not to web-api's ingest validation). This story uses a
lightweight header/container probe rather than the full ML stack, to avoid
pulling a heavy new runtime dependency into web-api for a fast validation gate:

- WAV / MP3: `soundfile.info()` — a real libsndfile-backed decode probe.
- M4A: `mutagen.mp4.MP4` — validates MP4/AAC container structure. libsndfile
  does not support M4A/AAC at all, so soundfile cannot be used for this format.

Probes operate on an already-open, seekable file-like object (the upload's
spooled temp file) rather than a path on disk — this lets validation run
*before* anything is persisted to permanent storage, so a rejected upload
never costs a full write-then-delete cycle. Callers must `seek(0)` the object
before probing and again before any subsequent read (probing consumes the
stream position).

See Dev Agent Record (Completion Notes) in the story file for the full rationale.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import BinaryIO

import soundfile as sf
from mutagen.mp4 import MP4

# soundfile's `info.format` for each extension we accept via this branch —
# used to catch content whose real container doesn't match its claimed
# extension (e.g. an MP3 stream renamed to .wav).
_EXPECTED_SOUNDFILE_FORMAT = {".wav": "WAV", ".mp3": "MP3"}


@dataclass
class ProbeResult:
    duration_seconds: float


class AudioProbeError(Exception):
    """Raised when the file cannot be validated as decodable audio."""


def probe_audio(file_obj: BinaryIO, extension: str) -> ProbeResult:
    """Return duration for a decodable file; raise AudioProbeError otherwise."""
    ext = extension.lower()
    if ext in (".wav", ".mp3"):
        try:
            info = sf.info(file_obj)
        except Exception as exc:  # soundfile raises LibsndfileError / RuntimeError
            raise AudioProbeError(str(exc)) from exc
        if info.frames <= 0 or info.samplerate <= 0:
            raise AudioProbeError("empty or zero-samplerate audio stream")
        expected_format = _EXPECTED_SOUNDFILE_FORMAT[ext]
        if info.format != expected_format:
            raise AudioProbeError(
                f"file content is {info.format}, not {expected_format} as its "
                f"{ext} extension claims"
            )
        return ProbeResult(duration_seconds=info.frames / info.samplerate)

    if ext == ".m4a":
        try:
            mp4 = MP4(file_obj)
        except Exception as exc:  # mutagen raises MP4StreamInfoError and others
            raise AudioProbeError(str(exc)) from exc
        if mp4.info is None or mp4.info.length <= 0:
            raise AudioProbeError("no audio stream found in MP4/M4A container")
        return ProbeResult(duration_seconds=mp4.info.length)

    raise AudioProbeError(f"no decode probe available for extension {ext!r}")
