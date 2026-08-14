"""AD-11 time-range-overlap join: resolves the one `TranscriptTurn` (if any)
that best represents a given `TimelineSegment`'s text signal — Story 1.6.

AD-11 fixes the *boundary relationship* (`TranscriptTurn` <-> `TimelineSegment`
is many-to-many via time-range overlap, never a scalar FK) but does not fix a
segment-level *aggregation* rule for when multiple turns overlap one segment.
This module's rule — the dev-agent's documented choice — is: the turn with
the largest overlap duration wins; ties break on the lowest `turn_index`
(deterministic, matches turn persistence order).
"""

from __future__ import annotations

import sqlite3


def _overlap_duration(segment: sqlite3.Row, turn: sqlite3.Row) -> float:
    return min(segment["end_time"], turn["end_time"]) - max(
        segment["start_time"], turn["start_time"]
    )


def resolve_text_signal(segment: sqlite3.Row, turns: list[sqlite3.Row]) -> sqlite3.Row | None:
    """`turns` is every `TranscriptTurn` for this segment's Call (unfiltered
    — this function does the filtering). Returns `None` when no overlapping
    turn has a usable (non-null `text_sentiment`) result, e.g. a pause/
    silence segment with no overlapping speech, or every overlapping turn's
    own text-sentiment analysis failed (Story 1.5's per-turn isolation)."""
    candidates = [
        turn
        for turn in turns
        if turn["text_sentiment"] is not None
        and segment["start_time"] < turn["end_time"]
        and segment["end_time"] > turn["start_time"]
    ]
    if not candidates:
        return None
    return max(
        candidates,
        key=lambda turn: (_overlap_duration(segment, turn), -turn["turn_index"]),
    )
