"""Unit tests for Story 3.2's diarize.py. Deliberately never load a real
pyannote.audio Pipeline, and never reach the network/Hugging Face Hub — no
HF_TOKEN exists in this dev/CI environment, and none should be required for
these tests to pass. `_resolve_speaker_labels`/`_resolve_turn_result` are
exercised directly against hand-built word/speaker dicts;
`diarize_mono_turns`'s own orchestration is exercised with
`_get_diarize_pipeline` monkeypatched to a fake pipeline returning a real
`pyannote.core.Annotation` (a plain data structure — safe to construct
directly, no model loading involved)."""

from __future__ import annotations

import pytest
import torch
from pyannote.core import Annotation, Segment

from app.pipeline.transcript import diarize
from app.pipeline.transcript.diarize import (
    _resolve_speaker_labels,
    _resolve_turn_result,
    diarize_mono_turns,
)
from app.pipeline.transcript.stt import TurnResult, WordResult


def _build_diarization(turns: list[tuple[float, float, str]]) -> Annotation:
    annotation = Annotation()
    for start, end, speaker in turns:
        annotation[Segment(start, end)] = speaker
    return annotation


def _word(text: str, speaker: str | None) -> dict:
    return {"word": text, "start": 0.0, "end": 0.5, "speaker": speaker}


def test_resolve_speaker_labels_first_seen_wins():
    segments = [
        {"words": [_word("hi", "SPEAKER_01"), _word("there", "SPEAKER_01")]},
        {"words": [_word("hello", "SPEAKER_00")]},
    ]
    assert _resolve_speaker_labels(segments) == {
        "SPEAKER_01": "Speaker A",
        "SPEAKER_00": "Speaker B",
    }


def test_resolve_speaker_labels_ignores_words_with_no_assigned_speaker():
    segments = [{"words": [_word("hi", None), _word("there", "SPEAKER_00")]}]
    assert _resolve_speaker_labels(segments) == {"SPEAKER_00": "Speaker A"}


def test_resolve_speaker_labels_caps_at_two_even_with_more_clusters():
    segments = [
        {
            "words": [
                _word("a", "SPEAKER_00"),
                _word("b", "SPEAKER_01"),
                _word("c", "SPEAKER_02"),
            ]
        }
    ]
    mapping = _resolve_speaker_labels(segments)
    assert mapping == {"SPEAKER_00": "Speaker A", "SPEAKER_01": "Speaker B"}
    assert "SPEAKER_02" not in mapping


def test_resolve_turn_result_majority_speaker_and_confidence():
    segment = {
        "words": [
            _word("a", "SPEAKER_00"),
            _word("b", "SPEAKER_00"),
            _word("c", "SPEAKER_01"),
            _word("d", "SPEAKER_00"),
        ]
    }
    label_by_cluster = {"SPEAKER_00": "Speaker A", "SPEAKER_01": "Speaker B"}
    result = _resolve_turn_result(segment, label_by_cluster)
    assert result == ("SPEAKER_00", "Speaker A", 0.75)


def test_resolve_turn_result_unattributed_when_no_words_have_speaker():
    segment = {"words": [_word("a", None), _word("b", None)]}
    assert _resolve_turn_result(segment, {}) is None


def test_resolve_turn_result_unattributed_when_majority_speaker_has_no_label_slot():
    segment = {"words": [_word("a", "SPEAKER_02"), _word("b", "SPEAKER_02")]}
    label_by_cluster = {"SPEAKER_00": "Speaker A", "SPEAKER_01": "Speaker B"}
    assert _resolve_turn_result(segment, label_by_cluster) is None


def test_diarize_mono_turns_empty_turns_returns_empty_list():
    assert diarize_mono_turns(torch.zeros(16000), []) == []


def test_diarize_mono_turns_raises_fast_when_hf_token_missing(monkeypatch):
    """No HF_TOKEN is configured anywhere in this dev/CI environment by
    design (see story Dev Notes) — this must fail fast and locally, never
    attempt a network call (not even to the align model, which is public)."""
    monkeypatch.setattr(diarize, "HF_TOKEN", None)
    turn = TurnResult(text="hi", start_time=0.0, end_time=1.0, words=[])
    with pytest.raises(RuntimeError, match="HF_TOKEN"):
        diarize_mono_turns(torch.zeros(16000), [turn])


def test_diarize_mono_turns_wires_pipeline_and_resolves_speakers(monkeypatch):
    monkeypatch.setattr(diarize, "HF_TOKEN", "fake-token")
    turn = TurnResult(
        text="hello there",
        start_time=0.0,
        end_time=1.0,
        words=[
            WordResult(word="hello", start_time=0.0, end_time=0.4, probability=0.9),
            WordResult(word="there", start_time=0.4, end_time=1.0, probability=0.9),
        ],
    )
    # Both words' midpoints (0.2, 0.7) fall inside this single SPEAKER_00
    # diarization turn covering the whole call.
    diarization = _build_diarization([(0.0, 1.0, "SPEAKER_00")])

    class _FakeOutput:
        speaker_diarization = diarization

    def _fake_pipeline(audio):
        assert set(audio.keys()) == {"waveform", "sample_rate"}
        assert audio["sample_rate"] == 16000
        assert audio["waveform"].dim() == 2
        return _FakeOutput()

    monkeypatch.setattr(diarize, "_get_diarize_pipeline", lambda: _fake_pipeline)

    result = diarize_mono_turns(torch.zeros(16000), [turn])
    assert result == [("SPEAKER_00", "Speaker A", 1.0)]


def test_diarize_mono_turns_unassigned_word_outside_any_diarization_turn(monkeypatch):
    monkeypatch.setattr(diarize, "HF_TOKEN", "fake-token")
    turn = TurnResult(
        text="hello there",
        start_time=0.0,
        end_time=2.0,
        words=[
            WordResult(word="hello", start_time=0.0, end_time=0.4, probability=0.9),
            # This word's midpoint (1.5) falls outside the only diarization
            # turn (0.0-1.0) — stays unassigned (fill_nearest-equivalent
            # behavior: never guessed).
            WordResult(word="there", start_time=1.0, end_time=2.0, probability=0.9),
        ],
    )
    diarization = _build_diarization([(0.0, 1.0, "SPEAKER_00")])

    class _FakeOutput:
        speaker_diarization = diarization

    monkeypatch.setattr(diarize, "_get_diarize_pipeline", lambda: lambda audio: _FakeOutput())

    result = diarize_mono_turns(torch.zeros(32000), [turn])
    # Majority speaker among assigned words is still SPEAKER_00 (1 of 1
    # assigned word), confidence reflects only the assigned subset.
    assert result == [("SPEAKER_00", "Speaker A", 1.0)]
