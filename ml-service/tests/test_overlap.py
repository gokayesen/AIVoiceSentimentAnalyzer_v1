"""Unit tests for the AD-11 time-range-overlap join (Story 1.6, AC 9).

Uses plain dicts standing in for `sqlite3.Row` — `resolve_text_signal` only
ever does `row["column"]` lookups, so a dict satisfies the same interface
without needing a real SQLite connection.
"""

from __future__ import annotations

from app.pipeline.fusion.overlap import resolve_text_signal


def _segment(start_time: float, end_time: float) -> dict:
    return {"start_time": start_time, "end_time": end_time}


def _turn(turn_index: int, start_time: float, end_time: float, text_sentiment="positive") -> dict:
    return {
        "turn_index": turn_index,
        "start_time": start_time,
        "end_time": end_time,
        "text_sentiment": text_sentiment,
        "text_emotion": "happy",
        "text_confidence": 0.7,
    }


def test_resolve_text_signal_returns_none_when_no_turns_overlap():
    segment = _segment(0.0, 1.0)
    turns = [_turn(0, 2.0, 3.0)]
    assert resolve_text_signal(segment, turns) is None


def test_resolve_text_signal_returns_none_when_only_overlapping_turn_lacks_text_sentiment():
    segment = _segment(0.0, 1.0)
    turns = [_turn(0, 0.0, 1.0, text_sentiment=None)]
    assert resolve_text_signal(segment, turns) is None


def test_resolve_text_signal_returns_single_overlapping_turn():
    segment = _segment(0.0, 2.0)
    turn = _turn(0, 0.5, 1.5)
    assert resolve_text_signal(segment, [turn]) == turn


def test_resolve_text_signal_picks_largest_overlap_among_multiple_turns():
    segment = _segment(0.0, 3.0)
    small_overlap = _turn(0, 2.5, 4.0)  # overlaps [2.5, 3.0] = 0.5s
    large_overlap = _turn(1, 0.0, 2.0)  # overlaps [0.0, 2.0] = 2.0s
    assert resolve_text_signal(segment, [small_overlap, large_overlap]) == large_overlap


def test_resolve_text_signal_tie_breaks_on_lowest_turn_index():
    segment = _segment(0.0, 2.0)
    later_turn = _turn(5, 0.0, 1.0)  # overlaps 1.0s
    earlier_turn = _turn(2, 1.0, 2.0)  # overlaps 1.0s, same duration
    assert resolve_text_signal(segment, [later_turn, earlier_turn]) == earlier_turn


def test_resolve_text_signal_touching_boundaries_do_not_count_as_overlap():
    # A turn ending exactly where the segment starts (or vice versa) shares
    # zero duration, not a real overlap — the strict < / > comparison in
    # resolve_text_signal excludes this.
    segment = _segment(1.0, 2.0)
    turn = _turn(0, 0.0, 1.0)
    assert resolve_text_signal(segment, [turn]) is None
