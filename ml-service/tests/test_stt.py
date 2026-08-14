"""Tests for the faster-whisper STT wrapper (Story 1.4, AC 1/2/3)."""

from __future__ import annotations

import numpy as np
import pytest
import torchaudio

from app.pipeline.transcript.stt import transcribe_segment

_SR = 16000


class _FakeWord:
    def __init__(self, word, start, end, probability):
        self.word = word
        self.start = start
        self.end = end
        self.probability = probability


class _FakeSegment:
    def __init__(self, text, start, end, words):
        self.text = text
        self.start = start
        self.end = end
        self.words = words


class _FakeModel:
    """Records the kwargs `transcribe_segment` passed through to the real
    faster-whisper model, without needing a real model call — deterministic,
    same discipline as the acoustic classifier tests' monkeypatching."""

    def __init__(self, segments):
        self._segments = segments
        self.calls = []

    def transcribe(self, _waveform, **kwargs):
        self.calls.append(kwargs)
        return iter(self._segments), None


def _load_mono_16k(path):
    waveform, sr = torchaudio.load(str(path))
    mono = waveform.mean(dim=0)
    if sr != _SR:
        mono = torchaudio.functional.resample(mono, orig_freq=sr, new_freq=_SR)
    return mono.numpy()


def test_transcribe_segment_returns_turns_with_word_level_timestamps(fixtures_dir):
    waveform = _load_mono_16k(fixtures_dir / "speech.wav")

    turns = transcribe_segment(waveform, absolute_offset_seconds=0.0)

    assert len(turns) >= 1
    turn = turns[0]
    assert turn.text
    assert turn.start_time <= turn.end_time
    assert len(turn.words) >= 1
    for word in turn.words:
        assert word.word
        assert word.start_time <= word.end_time
        assert 0.0 <= word.probability <= 1.0


def test_transcribe_segment_offsets_timestamps_to_call_absolute_time(fixtures_dir):
    """AC 2 / Consistency Conventions: timestamps must be Call-absolute float
    seconds, not left relative to the padded slice passed in."""
    waveform = _load_mono_16k(fixtures_dir / "speech.wav")

    zero_turns = transcribe_segment(waveform, absolute_offset_seconds=0.0)
    offset_turns = transcribe_segment(waveform, absolute_offset_seconds=10.0)

    assert offset_turns[0].start_time == pytest.approx(zero_turns[0].start_time + 10.0)
    assert offset_turns[0].words[0].start_time == pytest.approx(
        zero_turns[0].words[0].start_time + 10.0
    )


def test_transcribe_segment_pins_english_and_disables_previous_text_conditioning(monkeypatch):
    """Code review (2026-08-13): AC1/FR-6's English-only MVP scope must be
    enforced via `language="en"`, not left to auto-detection; disabling
    `condition_on_previous_text` reinforces the hallucination mitigation."""
    fake_model = _FakeModel([_FakeSegment("hi", 0.0, 1.0, [])])
    monkeypatch.setattr("app.pipeline.transcript.stt._get_model", lambda: fake_model)

    transcribe_segment(np.zeros(1600, dtype="float32"), absolute_offset_seconds=0.0)

    assert len(fake_model.calls) == 1
    assert fake_model.calls[0]["language"] == "en"
    assert fake_model.calls[0]["condition_on_previous_text"] is False


def test_transcribe_segment_strips_words_and_drops_whitespace_only_turns(monkeypatch):
    """Code review (2026-08-13): a whitespace-only Whisper segment (filler/
    non-speech) must not become an empty TranscriptTurn; word text must be
    stripped consistently with turn text."""
    segments = [
        _FakeSegment("  ", 0.0, 0.5, []),
        _FakeSegment(
            " hello world ",
            0.5,
            1.5,
            [_FakeWord(" hello", 0.5, 1.0, 0.9), _FakeWord(" world", 1.0, 1.5, 0.8)],
        ),
    ]
    fake_model = _FakeModel(segments)
    monkeypatch.setattr("app.pipeline.transcript.stt._get_model", lambda: fake_model)

    turns = transcribe_segment(np.zeros(1600, dtype="float32"), absolute_offset_seconds=0.0)

    assert len(turns) == 1
    assert turns[0].text == "hello world"
    assert [w.word for w in turns[0].words] == ["hello", "world"]
