"""Mono-path diarization (Story 3.2, AD-6). Runs pyannote.audio's
Community-1 diarization pipeline directly, once per Call over the full mono
waveform, and assigns each of Story 1.4's already-produced faster-whisper
turns/words a speaker via a time-overlap lookup — never a second
transcription pass (AD-5 forbids an alternate STT engine). Stereo-path
attribution (Story 3.1, `speaker.py`) and uncertainty states (Story 3.3) are
not implemented here.

**Dev-agent deviation from AD-6's "WhisperX orchestrating... forced
alignment" wording** (verified at implementation time, confirmed with the
user): no `whisperx` package release supports pyannote.audio>=4.0
(Community-1) while also being compatible with this project's pinned
`torch==2.13.0` — every whisperx version that added Community-1 support
(3.8.0+) also tightened its own pin to `torch~=2.8.0`, which conflicts with
every other already-shipped pipeline stage in this codebase. `pyannote.audio`
itself (`torch>=2.8.0`) is satisfied by `torch==2.13.0` in isolation — only
`whisperx`'s own bundling forced the conflict. This module therefore calls
`pyannote.audio.Pipeline` directly and performs its own time-overlap
word-to-speaker lookup (mirroring `fusion/overlap.py`'s existing pattern)
instead of WhisperX's `assign_word_speakers`. Forced re-alignment is skipped
entirely — this relies on faster-whisper's own already-persisted word-level
timestamps (Story 1.4) rather than a second, WhisperX-driven alignment pass;
Community-1 is still the exact pinned diarization model (AC1/AC2 unaffected).

The Community-1 tier has no native per-turn confidence score (that is an
explicitly paid precision-2 feature, forbidden by AC2) — the confidence value
this module produces (`_resolve_turn_result`) is a word-level speaker-
agreement ratio, a dev-agent decision documented in the story's Dev Notes,
not an Architecture mandate."""

from __future__ import annotations

import torch
from pyannote.audio import Pipeline
from pyannote.core import Annotation

from app.config import HF_TOKEN
from app.pipeline.ingest.vad import VAD_SAMPLE_RATE
from app.pipeline.transcript.speaker import CHANNEL_SPEAKER_LABELS
from app.pipeline.transcript.stt import TurnResult

_diarize_pipeline: Pipeline | None = None


def _get_diarize_pipeline() -> Pipeline:
    # Same module-level lazy-singleton pattern as stt.py's _get_model()/
    # classifier.py/vad.py — provides no real benefit under RQ's default
    # forking Worker, not fixed here either, same accepted trade-off.
    global _diarize_pipeline
    if _diarize_pipeline is None:
        # Deliberately hardcoded, not a config value — overriding this model
        # id risks silently pulling a different, possibly-paid tier (AC2).
        _diarize_pipeline = Pipeline.from_pretrained(
            "pyannote/speaker-diarization-community-1", token=HF_TOKEN
        )
    return _diarize_pipeline


def _speaker_at(diarization: Annotation, time: float) -> str | None:
    """Returns the raw cluster id of whichever diarization turn's window
    contains `time`, or None if no turn covers it (silence/no speaker
    detected there) — mirrors `fusion/overlap.py`'s existing time-range-
    overlap join pattern, applied at a single time point (a word's
    midpoint, see `_to_segments_with_speakers`) rather than a range.

    Code review (2026-08-17): when two diarization turns overlap (Community-1
    can and does emit these, e.g. cross-talk), the first match in
    `itertracks()` order wins. This is deterministic, not arbitrary —
    `pyannote.core.Annotation.itertracks()` iterates in start-time-sorted
    order (verified empirically), so the earliest-starting overlapping turn
    always wins, same result every run. Explicit tie-break rule, mirroring
    `overlap.py`'s own "earliest/largest wins" convention rather than an
    unstated default."""
    for turn, _track, speaker in diarization.itertracks(yield_label=True):
        if turn.start <= time < turn.end:
            return speaker
    return None


def _to_segments_with_speakers(turns: list[TurnResult], diarization: Annotation) -> list[dict]:
    """Reshapes `turns` into the same `{"words": [{"word", "speaker"}, ...]}`
    shape `_resolve_speaker_labels`/`_resolve_turn_result` expect, resolving
    each word's speaker by its time-window midpoint against `diarization`."""
    segments = []
    for turn in turns:
        words = []
        for word in turn.words:
            midpoint = (word.start_time + word.end_time) / 2
            words.append({"word": word.word, "speaker": _speaker_at(diarization, midpoint)})
        segments.append({"words": words})
    return segments


def _resolve_speaker_labels(aligned_segments: list[dict]) -> dict[str, str]:
    """First-seen-wins: the first distinct cluster id encountered (segment
    order is chronological — turns are already in Call-time order) maps to
    CHANNEL_SPEAKER_LABELS[0], the second to CHANNEL_SPEAKER_LABELS[1]. A
    3rd+ distinct cluster (diarization over-splitting a nominally two-party
    conversation, FR-1) has no label slot and is simply absent from the
    returned mapping — dev-agent decision, mirrors the stereo path's
    >2-channel gap rather than inventing a 3rd label."""
    mapping: dict[str, str] = {}
    for segment in aligned_segments:
        for word in segment.get("words", []):
            speaker = word.get("speaker")
            if (
                speaker is not None
                and speaker not in mapping
                and len(mapping) < len(CHANNEL_SPEAKER_LABELS)
            ):
                mapping[speaker] = CHANNEL_SPEAKER_LABELS[len(mapping)]
    return mapping


def _resolve_turn_result(
    segment: dict, label_by_cluster: dict[str, str]
) -> tuple[str, str, float] | None:
    """One segment (== one input turn, same order) ->
    `(cluster_id, canonical_label, confidence)`, or `None` when unattributed:
    zero of this turn's words got any diarization-assigned speaker, or its
    majority speaker is a 3rd+ cluster with no canonical label slot.

    `confidence` is the fraction of this turn's speaker-assigned words that
    agree with the turn's majority (most common) speaker — see module
    docstring for why this heuristic exists rather than a native score."""
    speakers = [
        word["speaker"] for word in segment.get("words", []) if word.get("speaker") is not None
    ]
    if not speakers:
        return None
    # Code review (2026-08-17): `max(set(speakers), key=speakers.count)`
    # depended on Python's per-process string hash order to break a tied
    # word count, so a genuinely tied turn could persist a different speaker
    # across worker restarts. Explicit deterministic tie-break instead —
    # highest count wins, ties broken by the lower cluster id string — same
    # "explicit, documented rule" discipline as `overlap.py`'s own tie-break.
    majority = min(set(speakers), key=lambda speaker: (-speakers.count(speaker), speaker))
    label = label_by_cluster.get(majority)
    if label is None:
        return None
    confidence = speakers.count(majority) / len(speakers)
    return majority, label, confidence


def diarize_mono_turns(
    mono_waveform: torch.Tensor, turns: list[TurnResult]
) -> list[tuple[str, str, float] | None]:
    """Runs Community-1 diarization once over the full `mono_waveform`
    (16kHz, from `load_mono_waveform`) and resolves each of `turns` to a
    speaker. Returns one entry per input turn, same order. Raises on any
    pyannote failure (missing/invalid HF_TOKEN, model load error) — the
    caller (`transcript/run.py`) is responsible for catching this and
    leaving the Call's turns unattributed rather than failing the Call
    (AD-1's governing pattern for this whole module)."""
    if not turns:
        return []
    if not HF_TOKEN:
        # Fail fast and local, before any network call. No HF_TOKEN is
        # configured in this project's dev/CI environment by design (see
        # story Dev Notes) — this guard is what keeps every other test/dev
        # run in this environment from ever attempting a real network call
        # here.
        raise RuntimeError(
            "HF_TOKEN is not configured — mono diarization requires a Hugging "
            "Face access token for an account that has accepted "
            "pyannote/speaker-diarization-community-1's usage conditions"
        )

    pipeline = _get_diarize_pipeline()
    waveform = mono_waveform if mono_waveform.dim() == 2 else mono_waveform.unsqueeze(0)
    output = pipeline({"waveform": waveform, "sample_rate": VAD_SAMPLE_RATE})
    diarization = output.speaker_diarization

    segments = _to_segments_with_speakers(turns, diarization)
    label_by_cluster = _resolve_speaker_labels(segments)
    return [_resolve_turn_result(segment, label_by_cluster) for segment in segments]
