"""SQLite access layer for the `Call` entity (AD-12, Consistency Conventions).

`channel_count` (Story 1.2, AD-2) is nullable here: web-api's insert_call() at
upload time does not know it — only ml-service's ingest job determines and
writes it (ml-service has its own db.py, AD-7 service boundary; the two are
kept schema-compatible for `Call` by hand, not by import).

Story 1.7 adds read-only access to `TimelineSegment` (`get_timeline_segments`)
and a general `Call` reader (`get_call`) for the timeline-retrieval endpoint.
Per AD-13, web-api's DB access is metadata-write + status/results-**read**
only: this module must never gain a `TimelineSegment`/`AnalysisResult` writer
or a `Call.status` writer for *normal* operation — those are ml-service's RQ
worker's exclusively.

Story 1.10 adds hand-synced DDL for the four remaining tables a Call owns
(`AnalysisResult`, `TranscriptTurn`, `TranscriptWord`, `AcousticEvidence`,
copied column-for-column from ml-service/app/db.py, same AD-7 hand-sync
discipline as `TimelineSegment` above) plus `delete_call_cascade`, the one
documented exception to the "web-api never writes these tables" rule above:
AD-12's atomic-delete rule explicitly assigns web-api the responsibility for
removing a Call's rows across all six tables (Architecture's Capability →
Architecture Map: "web-api delete endpoint, dual-store removal | AD-12"). The
DDL is needed here even though web-api never *populates* these tables in
normal operation, so that (a) `DELETE FROM AnalysisResult ...` etc. don't
raise "no such table" in web-api's own isolated test suite, which never runs
ml-service's init_db(), and (b) a real deployment doesn't race ml-service's
worker container's own (also idempotent) table creation at startup.

Story 3.1 adds `TranscriptTurn.speaker_label`/`speaker_channel_index`
(hand-synced from ml-service/app/db.py, AD-7) — `get_transcript` reads
`speaker_label` only; `speaker_channel_index` is internal provenance, never
read here either.

Story 3.2 adds `TranscriptTurn.speaker_cluster_id`/`speaker_confidence`
(hand-synced from ml-service/app/db.py, AD-7) — `speaker_cluster_id` is
internal provenance of the mono diarization filter, never read or returned
by `get_transcript`; `speaker_label` already carries mono values through
unchanged, same field as the stereo path populates.

Story 3.3 reads `speaker_confidence` in `get_transcript` (never persisted
as its own API-visible column) to derive the response's `speaker_uncertain`
flag at read time — see that function's own docstring.
"""

from __future__ import annotations

import sqlite3
from pathlib import Path

from app.config import DB_PATH

# `completed_at` (Story 2.4, nullable): hand-synced with ml-service/app/db.py
# (AD-7) — only ml-service ever writes it (set the moment `status` becomes
# "complete"); web-api only ever reads it (get_call_status, Story 2.4 Task 2).
_CREATE_CALL_TABLE = """
CREATE TABLE IF NOT EXISTS Call (
    id TEXT PRIMARY KEY,
    status TEXT NOT NULL,
    filename TEXT NOT NULL,
    format TEXT NOT NULL,
    duration_seconds REAL NOT NULL,
    size_bytes INTEGER NOT NULL,
    created_at TEXT NOT NULL,
    channel_count INTEGER,
    completed_at TEXT
);
"""

# Story 1.7: mirrors ml-service/app/db.py's _CREATE_TIMELINE_SEGMENT_TABLE
# column-for-column — hand-synced, not imported (AD-7 service boundary, same
# discipline already used for the Call table above). Registered here so
# web-api's own test suite (and a container that starts before ml-service)
# can create this table without ml-service ever having run.
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

# Story 1.10: hand-synced from ml-service/app/db.py's _CREATE_ANALYSIS_RESULT_TABLE,
# column-for-column — needed only so delete_call_cascade's `DELETE FROM
# AnalysisResult` has a table to act on (web-api never writes rows here in
# normal operation, per AD-13; only reads/deletes for this one story).
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

# Story 1.10: hand-synced from ml-service/app/db.py's _CREATE_TRANSCRIPT_TURN_TABLE.
# Deliberately NO segment_id column (AD-11: TranscriptTurn relates to
# TimelineSegment only via time-range overlap, never a scalar FK) — unrelated
# to why it's here (delete-only), noted so this DDL isn't "fixed" to add one.
# Story 3.1: speaker_label/speaker_channel_index hand-synced from
# ml-service's own DDL comment (AD-2) — web-api only reads speaker_label
# (get_transcript); speaker_channel_index is internal provenance, never
# read or returned here either.
# Story 3.2: speaker_cluster_id/speaker_confidence hand-synced from
# ml-service's own DDL comment (AD-6) — speaker_cluster_id is
# speaker_channel_index's mono-path counterpart (internal provenance, never
# read or returned here). speaker_confidence is the per-turn diarization
# confidence (AD-6/AD-10) — Story 3.3 reads it (get_transcript) to derive
# the API-visible speaker_uncertain flag at response time, never persisting
# a redundant column for it (see get_transcript's own docstring).
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
    text_keywords TEXT,
    speaker_label TEXT,
    speaker_channel_index INTEGER,
    speaker_cluster_id TEXT,
    speaker_confidence REAL
);
"""

# Story 1.10: hand-synced from ml-service/app/db.py's _CREATE_TRANSCRIPT_WORD_TABLE.
# No call_id column — only reachable from a Call via TranscriptTurn.turn_id,
# which is why delete_call_cascade deletes this table via a subquery on
# TranscriptTurn, not a direct call_id filter.
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

# Story 1.10: hand-synced from ml-service/app/db.py's _CREATE_ACOUSTIC_EVIDENCE_TABLE.
# No call_id column — only reachable via TimelineSegment.segment_id, same
# subquery-based deletion reasoning as TranscriptWord above.
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


def get_connection(db_path: Path = DB_PATH) -> sqlite3.Connection:
    db_path.parent.mkdir(parents=True, exist_ok=True)
    # timeout=30: retry on "database is locked" for up to 30s instead of
    # failing immediately: concurrent per-request connections (one per
    # upload) will contend for the write lock under real traffic.
    conn = sqlite3.connect(db_path, timeout=30.0)
    conn.row_factory = sqlite3.Row
    # WAL allows concurrent readers alongside a single writer instead of
    # rollback-journal's exclusive-lock-per-write, reducing contention.
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def init_db(db_path: Path = DB_PATH) -> None:
    conn = get_connection(db_path)
    try:
        conn.execute(_CREATE_CALL_TABLE)
        conn.execute(_CREATE_TIMELINE_SEGMENT_TABLE)
        conn.execute(_CREATE_ANALYSIS_RESULT_TABLE)
        conn.execute(_CREATE_TRANSCRIPT_TURN_TABLE)
        conn.execute(_CREATE_TRANSCRIPT_WORD_TABLE)
        conn.execute(_CREATE_ACOUSTIC_EVIDENCE_TABLE)
        conn.commit()
    finally:
        conn.close()


def insert_call(
    conn: sqlite3.Connection,
    *,
    call_id: str,
    status: str,
    filename: str,
    audio_format: str,
    duration_seconds: float,
    size_bytes: int,
    created_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO Call (id, status, filename, format, duration_seconds, size_bytes, created_at)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (call_id, status, filename, audio_format, duration_seconds, size_bytes, created_at),
    )
    conn.commit()


def delete_call(conn: sqlite3.Connection, *, call_id: str) -> None:
    """Compensating action for upload_call's post-persist cleanup (Story 1.2):
    insert_call() commits immediately, so a later failure in the same request
    (e.g. RQ enqueue) can no longer be rolled back — it must be explicitly
    undone here instead, or the Call row is orphaned with no worker ever
    picking it up."""
    conn.execute("DELETE FROM Call WHERE id = ?", (call_id,))
    conn.commit()


def delete_call_cascade(conn: sqlite3.Connection, *, call_id: str) -> None:
    """Story 1.10 (AD-12, AC1): deletes a Call and every row it owns across
    all six tables, in one transaction (one commit) — atomic, never one
    table's rows removed without the rest. Distinct from delete_call() above,
    which stays a single-table (Call-only) compensating action for
    upload_call's own rollback path and must not be repurposed or renamed.

    Child-before-parent order (TranscriptWord/AcousticEvidence before their
    parents) is defensive/semantically correct even though neither this
    module nor ml-service's turns PRAGMA foreign_keys=ON, so SQLite does not
    itself enforce it. TranscriptWord/AcousticEvidence have no call_id column
    of their own (only turn_id/segment_id respectively — see their DDL
    comments above), hence the subqueries instead of a direct call_id filter.
    """
    conn.execute(
        "DELETE FROM TranscriptWord WHERE turn_id IN "
        "(SELECT id FROM TranscriptTurn WHERE call_id = ?)",
        (call_id,),
    )
    conn.execute(
        "DELETE FROM AcousticEvidence WHERE segment_id IN "
        "(SELECT id FROM TimelineSegment WHERE call_id = ?)",
        (call_id,),
    )
    conn.execute("DELETE FROM TimelineSegment WHERE call_id = ?", (call_id,))
    conn.execute("DELETE FROM TranscriptTurn WHERE call_id = ?", (call_id,))
    conn.execute("DELETE FROM AnalysisResult WHERE call_id = ?", (call_id,))
    conn.execute("DELETE FROM Call WHERE id = ?", (call_id,))
    conn.commit()


def get_call(conn: sqlite3.Connection, *, call_id: str) -> sqlite3.Row | None:
    """Story 1.7: read-only Call lookup for the timeline-retrieval endpoint
    (status gate) and any future results endpoint."""
    return conn.execute("SELECT * FROM Call WHERE id = ?", (call_id,)).fetchone()


def get_analysis_result(conn: sqlite3.Connection, *, call_id: str) -> sqlite3.Row | None:
    """Story 2.2: read-only `AnalysisResult` lookup for the Call-status
    endpoint (Sentiment/Emotion/Confidence once a Call is `complete`) — the
    "future results endpoint" `get_call`'s own docstring above anticipated.
    Read-only: web-api never writes this table (AD-13)."""
    return conn.execute(
        "SELECT * FROM AnalysisResult WHERE call_id = ?", (call_id,)
    ).fetchone()


def get_timeline_segments(conn: sqlite3.Connection, *, call_id: str) -> list[sqlite3.Row]:
    """Story 1.7 (AC 1, 3): ordered by segment_index — identical query shape
    to ml-service's own get_timeline_segments. Read-only: web-api never
    writes this table (AD-13)."""
    return conn.execute(
        "SELECT * FROM TimelineSegment WHERE call_id = ? ORDER BY segment_index",
        (call_id,),
    ).fetchall()


def get_transcript_turns(conn: sqlite3.Connection, *, call_id: str) -> list[sqlite3.Row]:
    """Story 2.4 (Task 3): ordered by turn_index — same read-only,
    ordered-by-index pattern as get_timeline_segments above. Read-only:
    web-api never writes this table (AD-13)."""
    return conn.execute(
        "SELECT * FROM TranscriptTurn WHERE call_id = ? ORDER BY turn_index",
        (call_id,),
    ).fetchall()


def get_acoustic_evidence_for_call(conn: sqlite3.Connection, *, call_id: str) -> list[sqlite3.Row]:
    """Story 2.4 (Task 4): every AcousticEvidence row belonging to one Call,
    joined through TimelineSegment (AcousticEvidence has no call_id column
    of its own — only segment_id, same relationship delete_call_cascade's
    subquery above already relies on). No ORDER BY: this story only
    aggregates these rows (get_acoustic_summary), never lists them
    per-segment. Read-only: web-api never writes this table (AD-13)."""
    return conn.execute(
        "SELECT AcousticEvidence.* FROM AcousticEvidence "
        "JOIN TimelineSegment ON AcousticEvidence.segment_id = TimelineSegment.id "
        "WHERE TimelineSegment.call_id = ?",
        (call_id,),
    ).fetchall()
