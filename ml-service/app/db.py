"""SQLite access layer for the RQ worker (AD-12, AD-7, Consistency Conventions).

Deliberately does NOT import web-api/app/db.py: the two services share a
database file via the filesystem volume only, never a Python module (AD-7
service boundary). The `Call` DDL here is kept schema-compatible (same table
and column names) with web-api's definition by hand, not by import.

`TimelineSegment` was introduced in Story 1.2; `AcousticEvidence` and its
`acoustic_emotion`/`acoustic_confidence` columns on `TimelineSegment` were
added in Story 1.3. `TranscriptTurn`/`TranscriptWord` were added in Story 1.4.
Story 1.5 added `TranscriptTurn.text_*` columns. Story 1.6 added
`TimelineSegment.fused_*`/`*_flag` columns and the `AnalysisResult` table.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path
from typing import NamedTuple

from app.config import DB_PATH


class TextSentimentResult(NamedTuple):
    """Story 1.5 code review: a structural safeguard for
    `persist_text_sentiment_results`'s input — a raw tuple with fields
    reordered relative to the SQL `UPDATE` below was flagged as a footgun
    documented only by a code comment; a `NamedTuple` makes the field order
    self-describing at the call site instead."""

    turn_id: str
    text_sentiment: str
    text_emotion: str
    text_confidence: float
    text_keywords: str


class FusedSegmentResult(NamedTuple):
    """Story 1.6: one `TimelineSegment`'s fusion output (see
    `app.pipeline.fusion.fuse.fuse_segment`), paired with its `segment_id`
    for the `UPDATE ... WHERE id = ?` — same field-order-by-name rationale
    as `TextSentimentResult` above."""

    segment_id: str
    fused_sentiment: str
    fused_emotion: str
    fused_confidence: float
    single_modality_flag: bool
    disagreement_flag: bool


class AnalysisResultRow(NamedTuple):
    """Story 1.6: the Call-level fusion aggregate (see
    `app.pipeline.fusion.fuse.reduce_call`), paired with its `call_id` for
    the `AnalysisResult` upsert."""

    call_id: str
    overall_sentiment: str
    overall_emotion: str
    overall_confidence: float
    single_modality_flag: bool
    secondary_signal_emotion: str | None
    secondary_signal_confidence: float | None
    segments_flagged_count: int


# Mirrors web-api/app/db.py's Call DDL exactly, plus the channel_count column
# this story adds (nullable: only ingest, running here, knows the value —
# web-api's insert_call() at upload time does not).
_CREATE_CALL_TABLE = """
CREATE TABLE IF NOT EXISTS Call (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    filename TEXT NOT NULL,
    format TEXT NOT NULL,
    duration_seconds REAL NOT NULL,
    size_bytes INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    channel_count INTEGER
);
"""

# Story 1.6 (AD-8/AD-15): fused_sentiment/fused_emotion/fused_confidence are
# this segment's fusion output — always one of the four AD-4 polarity values
# for fused_sentiment, but fused_emotion may come from either the acoustic
# (4-class) or text (28-class) Emotion taxonomy depending on which modality
# dominated (see fusion/fuse.py's module docstring). single_modality_flag is
# true when this segment had no usable text signal to fuse against (fusion
# output is the acoustic reading alone). disagreement_flag (Story 1.9, AD-8)
# is 1 when the acoustic/text polarities differ and both raw per-modality
# confidences exceed DISAGREEMENT_THRESHOLD (see fusion/fuse.py), else 0 —
# never set for a single-modality segment (see Story 1.7's explicit
# forward-decoupling dependency note, which reserved this column's shape).
_CREATE_TIMELINE_SEGMENT_TABLE = """
CREATE TABLE IF NOT EXISTS TimelineSegment (
    id TEXT PRIMARY KEY,
    call_id TEXT NOT NULL REFERENCES Call(id),
    segment_index INTEGER NOT NULL,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    acoustic_emotion TEXT,
    acoustic_confidence REAL,
    fused_sentiment TEXT,
    fused_emotion TEXT,
    fused_confidence REAL,
    single_modality_flag INTEGER,
    disagreement_flag INTEGER
);
"""

# Story 1.6 (AD-8): the Call-level fusion aggregate — a deterministic
# reduction over the Call's TimelineSegment rows (never an independent
# fusion pass, per AD-8's Core-entity sketch: TIMELINE_SEGMENT is
# segment-level detail, AnalysisResult is the separate Call-level
# aggregate). call_id is the PRIMARY KEY, not just an indexed FK: this is a
# strict 1:1 with Call, mirroring AcousticEvidence's segment_id PK pattern.
# secondary_signal_emotion/secondary_signal_confidence are nullable — NULL
# means "no distinct secondary reading exists" (the "None flagged" state),
# reachable whenever the whole Call is single-modality. segments_flagged_count
# (Story 1.9) is reduce_call's count of this Call's segments with
# disagreement_flag=1 — 0 whenever no segment disagreed, never a special case.
_CREATE_ANALYSIS_RESULT_TABLE = """
CREATE TABLE IF NOT EXISTS AnalysisResult (
    call_id TEXT PRIMARY KEY REFERENCES Call(id),
    overall_sentiment TEXT NOT NULL,
    overall_emotion TEXT NOT NULL,
    overall_confidence REAL NOT NULL,
    single_modality_flag INTEGER NOT NULL,
    secondary_signal_emotion TEXT,
    secondary_signal_confidence REAL,
    segments_flagged_count INTEGER NOT NULL
);
"""

# Story 1.3 (AD-3): the acoustic classifier's own raw Emotion + calibrated
# confidence live directly on TimelineSegment (`acoustic_*`, above) — kept
# separate from this table, which is the handcrafted-feature explainability
# layer only. segment_id is the PRIMARY KEY, not just an indexed FK: the
# Core-entity sketch's TIMELINE_SEGMENT ||--|| ACOUSTIC_EVIDENCE cardinality
# is a strict 1:1, and a PK is what actually enforces "one row per segment"
# rather than merely convention.
_CREATE_ACOUSTIC_EVIDENCE_TABLE = """
CREATE TABLE IF NOT EXISTS AcousticEvidence (
    segment_id TEXT PRIMARY KEY REFERENCES TimelineSegment(id),
    pitch_mean_hz REAL,
    pitch_std_hz REAL,
    energy_rms_mean REAL,
    speaking_rate_estimate REAL,
    pause_ratio REAL
);
"""

# Story 1.4 (AD-11): deliberately NO segment_id column — TranscriptTurn
# relates to TimelineSegment only via time-range overlap (many-to-many,
# computed at query time), never a scalar FK. This is unlike
# AcousticEvidence's strict 1:1 segment_id PK above; conflating the two
# relationship shapes is the single most likely schema-design mistake here.
#
# Story 1.5 (AD-15/AD-19): text_sentiment/text_emotion/text_confidence/
# text_keywords are the transcript-sentiment filter's output, added directly
# onto this table (mirrors acoustic_emotion/acoustic_confidence living
# directly on TimelineSegment, not a separate 1:1 table) and left NULL until
# that stage runs. text_sentiment is always one of the four AD-4 polarity
# values (negative/mixed/positive/neutral) so Fusion (Story 1.6) can compare
# it against TimelineSegment.acoustic_emotion's polarity mapping. No
# equivalent columns are added to TimelineSegment — a future story computes
# a segment-level view via the AD-11 time-range-overlap join, never a second
# stored copy. text_keywords is a JSON-encoded array of strings (the first
# JSON column in this schema); use `json.dumps`/`json.loads`, no new
# dependency.
_CREATE_TRANSCRIPT_TURN_TABLE = """
CREATE TABLE IF NOT EXISTS TranscriptTurn (
    id TEXT PRIMARY KEY,
    call_id TEXT NOT NULL REFERENCES Call(id),
    turn_index INTEGER NOT NULL,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    text TEXT NOT NULL,
    text_sentiment TEXT,
    text_emotion TEXT,
    text_confidence REAL,
    text_keywords TEXT
);
"""

# Story 1.4 (AC 2): word-level timestamps as their own normalized table
# (consistent with AcousticEvidence's own-table style, not a JSON blob
# column) so later stories can query/join on individual words directly.
_CREATE_TRANSCRIPT_WORD_TABLE = """
CREATE TABLE IF NOT EXISTS TranscriptWord (
    id TEXT PRIMARY KEY,
    turn_id TEXT NOT NULL REFERENCES TranscriptTurn(id),
    word_index INTEGER NOT NULL,
    word TEXT NOT NULL,
    start_time REAL NOT NULL,
    end_time REAL NOT NULL,
    probability REAL NOT NULL
);
"""


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # Same WAL + busy-timeout rationale as web-api/app/db.py: the worker
    # process and web-api process now write to this file concurrently.
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    """Idempotent — safe to call at worker startup regardless of whether
    web-api's own init_db() has already run (container startup order between
    the two services is not guaranteed by docker-compose)."""
    conn = get_connection(db_path)
    try:
        conn.execute(_CREATE_CALL_TABLE)
        conn.execute(_CREATE_TIMELINE_SEGMENT_TABLE)
        conn.execute(_CREATE_ACOUSTIC_EVIDENCE_TABLE)
        conn.execute(_CREATE_TRANSCRIPT_TURN_TABLE)
        conn.execute(_CREATE_TRANSCRIPT_WORD_TABLE)
        conn.execute(_CREATE_ANALYSIS_RESULT_TABLE)
        conn.commit()
    finally:
        conn.close()


def set_call_status(conn: sqlite3.Connection, *, call_id: str, status: str) -> None:
    """The only writer of Call.status transitions beyond the initial `queued`
    insert (AD-13) — web-api must never call this."""
    conn.execute("UPDATE Call SET status = ? WHERE id = ?", (status, call_id))
    conn.commit()


def set_call_channel_count(conn: sqlite3.Connection, *, call_id: str, channel_count: int) -> None:
    conn.execute("UPDATE Call SET channel_count = ? WHERE id = ?", (channel_count, call_id))
    conn.commit()


def insert_timeline_segments(
    conn: sqlite3.Connection,
    *,
    call_id: str,
    segments: list[tuple[str, int, float, float]],
) -> None:
    """`segments` is a list of (id, segment_index, start_time, end_time) tuples,
    already ordered by segment_index (AC 3, 4) — this function does not sort."""
    conn.executemany(
        """
        INSERT INTO TimelineSegment (id, call_id, segment_index, start_time, end_time)
        VALUES (?, ?, ?, ?, ?)
        """,
        [(seg_id, call_id, idx, start, end) for seg_id, idx, start, end in segments],
    )
    conn.commit()


def get_timeline_segments(conn: sqlite3.Connection, *, call_id: str) -> list[sqlite3.Row]:
    """Ordered by segment_index (AC 3/4's persisted ordering) — Story 1.3's
    run_acoustic is the first consumer that needs TimelineSegment rows read
    back; Story 1.2 only ever wrote them."""
    return conn.execute(
        "SELECT * FROM TimelineSegment WHERE call_id = ? ORDER BY segment_index",
        (call_id,),
    ).fetchall()


def persist_acoustic_results(
    conn: sqlite3.Connection,
    *,
    evidence_rows: list[tuple[str, float | None, float | None, float, float, float]],
    results: list[tuple[str, str, float]],
) -> None:
    """Writes both the handcrafted-feature `AcousticEvidence` rows (AD-3) and
    the classifier's raw Emotion + calibrated confidence onto `TimelineSegment`
    in a **single transaction** (one commit for both statements) — a mid-Call
    sanity-floor failure (Story 1.3) can't leave one of the two writes
    committed while the other is never reached, since the caller only calls
    this once, after every segment in the Call has already cleared the
    sanity check.

    `evidence_rows` is a list of (segment_id, pitch_mean_hz, pitch_std_hz,
    energy_rms_mean, speaking_rate_estimate, pause_ratio) tuples.
    `pitch_mean_hz`/`pitch_std_hz` may be NULL when a segment has no voiced
    frames at all (never fabricated as 0.0, which would misrepresent
    silence as a real pitch reading).

    `results` is a list of (segment_id, emotion, confidence) tuples, both
    lists covering *all* segments of the Call."""
    conn.executemany(
        """
        INSERT INTO AcousticEvidence
            (segment_id, pitch_mean_hz, pitch_std_hz, energy_rms_mean, speaking_rate_estimate, pause_ratio)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        evidence_rows,
    )
    conn.executemany(
        "UPDATE TimelineSegment SET acoustic_emotion = ?, acoustic_confidence = ? WHERE id = ?",
        [(emotion, confidence, segment_id) for segment_id, emotion, confidence in results],
    )
    conn.commit()


def persist_transcript_turns(
    conn: sqlite3.Connection,
    *,
    turns: list[tuple[str, str, int, float, float, str]],
    words: list[tuple[str, str, int, str, float, float, float]],
) -> None:
    """Writes both `TranscriptTurn` rows and their `TranscriptWord` children
    in a **single transaction** (one commit for both statements), mirroring
    `persist_acoustic_results`'s atomicity rationale (Story 1.3 code review):
    the caller computes every turn/word for the whole Call in memory first,
    calling this once, so there is no risk of turns persisting without their
    words or vice versa.

    `turns` is a list of (id, call_id, turn_index, start_time, end_time, text)
    tuples, already ordered by turn_index — this function does not sort.
    `words` is a list of (id, turn_id, word_index, word, start_time, end_time,
    probability) tuples covering all turns passed in `turns`. May be empty if
    `turns` is empty (nothing to write, still a no-op single "transaction")."""
    conn.executemany(
        """
        INSERT INTO TranscriptTurn (id, call_id, turn_index, start_time, end_time, text)
        VALUES (?, ?, ?, ?, ?, ?)
        """,
        turns,
    )
    if words:
        conn.executemany(
            """
            INSERT INTO TranscriptWord (id, turn_id, word_index, word, start_time, end_time, probability)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            words,
        )
    conn.commit()


def persist_text_sentiment_results(
    conn: sqlite3.Connection,
    *,
    results: list[TextSentimentResult],
) -> None:
    """Story 1.5 (AD-9/AD-15): writes the transcript-sentiment filter's
    per-turn output onto existing `TranscriptTurn` rows in a **single
    transaction** (one commit) — same "compute everything in memory first,
    write once" atomicity discipline as `persist_acoustic_results`/
    `persist_transcript_turns`.

    `results` is a list of `TextSentimentResult` — a `NamedTuple` (code
    review, Story 1.5) so callers pass fields by name, not by a
    reorder-prone positional tuple. The SQL `UPDATE` below still needs
    `turn_id` last (after the `SET` columns, for the `WHERE` clause), which
    the list comprehension reorders explicitly."""
    conn.executemany(
        """
        UPDATE TranscriptTurn
        SET text_sentiment = ?, text_emotion = ?, text_confidence = ?, text_keywords = ?
        WHERE id = ?
        """,
        [
            (r.text_sentiment, r.text_emotion, r.text_confidence, r.text_keywords, r.turn_id)
            for r in results
        ],
    )
    conn.commit()


def get_transcript_turns(conn: sqlite3.Connection, *, call_id: str) -> list[sqlite3.Row]:
    """Ordered by turn_index (this story's persisted ordering)."""
    return conn.execute(
        "SELECT * FROM TranscriptTurn WHERE call_id = ? ORDER BY turn_index",
        (call_id,),
    ).fetchall()


def get_transcript_words(conn: sqlite3.Connection, *, turn_id: str) -> list[sqlite3.Row]:
    """Ordered by word_index."""
    return conn.execute(
        "SELECT * FROM TranscriptWord WHERE turn_id = ? ORDER BY word_index",
        (turn_id,),
    ).fetchall()


def persist_fusion_results(
    conn: sqlite3.Connection,
    *,
    segment_results: list[FusedSegmentResult],
    analysis_result: AnalysisResultRow,
) -> None:
    """Story 1.6 (AD-8, AC 7): writes every `TimelineSegment`'s fusion
    output, the single Call-level `AnalysisResult` row, AND the
    `Call.status = "complete"` transition in **one single transaction** (one
    commit) — same "compute everything in memory first, write once"
    atomicity discipline as `persist_acoustic_results`/
    `persist_text_sentiment_results`, extended to cover the status write
    too (code review, 2026-08-14): a prior version called
    `db.set_call_status(..., "complete")` as a *separate* statement/commit
    after this function returned, which meant a failure in that second call
    could mark the Call `"failed"` despite the fusion results above already
    being fully and validly committed. Folding the status write into this
    same transaction makes "fusion results persisted" and "Call marked
    complete" succeed or fail together, never one without the other. The
    `AnalysisResult` write is an upsert (`ON CONFLICT`) rather than a plain
    `INSERT`: `run_fusion` is not guaranteed to be invoked exactly once by
    RQ's own delivery semantics (at-least-once), so a retry must not raise a
    PRIMARY KEY violation."""
    conn.executemany(
        """
        UPDATE TimelineSegment
        SET fused_sentiment = ?, fused_emotion = ?, fused_confidence = ?,
            single_modality_flag = ?, disagreement_flag = ?
        WHERE id = ?
        """,
        [
            (
                r.fused_sentiment,
                r.fused_emotion,
                r.fused_confidence,
                r.single_modality_flag,
                r.disagreement_flag,
                r.segment_id,
            )
            for r in segment_results
        ],
    )
    conn.execute(
        """
        INSERT INTO AnalysisResult
            (call_id, overall_sentiment, overall_emotion, overall_confidence,
             single_modality_flag, secondary_signal_emotion,
             secondary_signal_confidence, segments_flagged_count)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(call_id) DO UPDATE SET
            overall_sentiment = excluded.overall_sentiment,
            overall_emotion = excluded.overall_emotion,
            overall_confidence = excluded.overall_confidence,
            single_modality_flag = excluded.single_modality_flag,
            secondary_signal_emotion = excluded.secondary_signal_emotion,
            secondary_signal_confidence = excluded.secondary_signal_confidence,
            segments_flagged_count = excluded.segments_flagged_count
        """,
        (
            analysis_result.call_id,
            analysis_result.overall_sentiment,
            analysis_result.overall_emotion,
            analysis_result.overall_confidence,
            analysis_result.single_modality_flag,
            analysis_result.secondary_signal_emotion,
            analysis_result.secondary_signal_confidence,
            analysis_result.segments_flagged_count,
        ),
    )
    conn.execute("UPDATE Call SET status = ? WHERE id = ?", ("complete", analysis_result.call_id))
    conn.commit()


def get_analysis_result(conn: sqlite3.Connection, *, call_id: str) -> sqlite3.Row | None:
    return conn.execute(
        "SELECT * FROM AnalysisResult WHERE call_id = ?",
        (call_id,),
    ).fetchone()
