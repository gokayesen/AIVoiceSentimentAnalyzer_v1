"""faster-whisper STT wrapper (AD-5, AC 1/2/3) — Story 1.4. English-only
MVP (FR-6); no alternate STT engine may be substituted (AD-5).

Whisper-family models are known to hallucinate repeated/fabricated phrases
during silence/low-energy audio (Technical Research §4.1: near-zero
embeddings cause decoder looping). Feeding this module already-VAD-bounded
segment slices (never raw full-Call audio) is this story's mitigation for
that failure mode, not a separate silence-detection pass.

Input waveform slices must already be mono float audio at 16kHz
(VAD_SAMPLE_RATE) — faster-whisper's numpy-array input path assumes 16kHz,
same rate `app/audio.py`'s `load_mono_waveform` already produces.
"""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np
from faster_whisper import WhisperModel

from app.config import WHISPER_COMPUTE_TYPE, WHISPER_DEVICE, WHISPER_MODEL_SIZE

_model: WhisperModel | None = None


def _get_model() -> WhisperModel:
    # Same module-level lazy-singleton pattern as vad.py/classifier.py.
    # Provides no real benefit under RQ's default forking Worker (already
    # deferred twice for those two models, see deferred-work.md) — not
    # fixed here either, same accepted trade-off, now a third time.
    global _model
    if _model is None:
        _model = WhisperModel(WHISPER_MODEL_SIZE, device=WHISPER_DEVICE, compute_type=WHISPER_COMPUTE_TYPE)
    return _model


@dataclass(frozen=True)
class WordResult:
    word: str
    start_time: float
    end_time: float
    probability: float


@dataclass(frozen=True)
class TurnResult:
    text: str
    start_time: float
    end_time: float
    words: list[WordResult]


def transcribe_segment(waveform: np.ndarray, *, absolute_offset_seconds: float) -> list[TurnResult]:
    """`waveform` should include Task 6's AD-11 context margin when called
    from the pipeline. `absolute_offset_seconds` is the Call-relative
    absolute start time of the FIRST sample in `waveform` — faster-whisper
    reports timestamps relative to the slice it's given, so every returned
    turn/word timestamp is offset by this value before being returned, to
    land back in Call-absolute float seconds (Consistency Conventions).

    One faster-whisper "segment" (its own internal phrase/sentence split)
    maps to one TurnResult; a single input slice can yield zero, one, or
    multiple TurnResults — never assume a 1:1 mapping to the caller's
    TimelineSegment."""
    model = _get_model()
    segments, _info = model.transcribe(
        waveform,
        word_timestamps=True,
        # Code review (2026-08-13): pin to English rather than letting
        # faster-whisper run its own per-segment language-detection pass —
        # FR-6/AC1 scope this story to English-only audio, and detection on
        # short, context-padded slices is unreliable.
        language="en",
        # Code review (2026-08-13): disabling this stops each internal
        # Whisper segment's decoding from conditioning on the previous
        # segment's text, a known driver of repeated/runaway hallucination
        # loops — reinforces the VAD-bounded-input mitigation described
        # above rather than relying on it alone.
        condition_on_previous_text=False,
    )
    # transcribe() is lazy by default — force it to completion here so the
    # caller never receives an unconsumed generator.
    segments = list(segments)

    turns = []
    for segment in segments:
        text = segment.text.strip()
        if not text:
            # Code review (2026-08-13): a filler/non-speech Whisper segment
            # can produce an all-whitespace text — not real transcript
            # content, so it's dropped here rather than persisted as an
            # empty TranscriptTurn.
            continue
        words = [
            WordResult(
                word=word.word.strip(),
                start_time=word.start + absolute_offset_seconds,
                end_time=word.end + absolute_offset_seconds,
                probability=word.probability,
            )
            for word in (segment.words or [])
        ]
        turns.append(
            TurnResult(
                text=text,
                start_time=segment.start + absolute_offset_seconds,
                end_time=segment.end + absolute_offset_seconds,
                words=words,
            )
        )
    return turns
