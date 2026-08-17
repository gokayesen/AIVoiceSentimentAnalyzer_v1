"""Tests for GET /calls/{call_id} — Story 2.2 (Call Upload & Processing-Status
Feedback), Task 1's status-read endpoint.

This endpoint is the minimal correction described in the story's Dev Notes
"Known spec gaps" item 1: Epic 1 never shipped a way for a client to
distinguish `processing` from `failed`, or to read a `complete` Call's
Sentiment/Emotion/Confidence. It is read-only (AD-13 unaffected) and reuses
`db.get_call`/introduces `db.get_analysis_result`, both plain SELECTs.

Local seeding helpers mirror `test_timeline.py`'s `_make_call` pattern
(copied locally rather than imported across test files, per that file's own
established convention).
"""

from __future__ import annotations

import uuid

import pytest

from app import db


def _make_call(*, status: str, duration_seconds: float = 5.0, channel_count: int | None = None) -> str:
    call_id = str(uuid.uuid4())
    conn = db.get_connection()
    try:
        db.insert_call(
            conn,
            call_id=call_id,
            status=status,
            filename="call.wav",
            audio_format="wav",
            duration_seconds=duration_seconds,
            size_bytes=1024,
            created_at="2026-08-15T00:00:00+00:00",
        )
        if channel_count is not None:
            # Story 3.4: db.insert_call() never accepts channel_count by
            # design (Story 1.2/1.10) — only ml-service's ingest job writes
            # it. Seeded directly here, same raw-SQL pattern
            # test_transcript.py's own `_make_call` already uses.
            conn.execute("UPDATE Call SET channel_count = ? WHERE id = ?", (channel_count, call_id))
            conn.commit()
    finally:
        conn.close()
    return call_id


def _seed_turn(
    *,
    call_id: str,
    turn_index: int,
    start_time: float,
    end_time: float,
    speaker_label: str | None = None,
) -> str:
    """Story 3.4: minimal local copy of test_transcript.py's `_seed_turn`
    helper (per this test suite's established convention of copying seeding
    helpers per-file rather than importing across test files) — trimmed to
    only the fields these tests need (`speaker_label`)."""
    turn_id = str(uuid.uuid4())
    conn = db.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO TranscriptTurn (id, call_id, turn_index, start_time, end_time, text, speaker_label)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (turn_id, call_id, turn_index, start_time, end_time, "hello", speaker_label),
        )
        conn.commit()
    finally:
        conn.close()
    return turn_id


def _seed_analysis_result(
    *,
    call_id: str,
    overall_sentiment: str = "negative",
    overall_emotion: str = "frustration",
    overall_confidence: float = 0.84,
    single_modality_flag: int = 0,
    secondary_signal_emotion: str | None = None,
    secondary_signal_confidence: float | None = None,
    segments_flagged_count: int = 0,
) -> None:
    conn = db.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO AnalysisResult
                (call_id, overall_sentiment, overall_emotion, overall_confidence,
                 single_modality_flag, secondary_signal_emotion,
                 secondary_signal_confidence, segments_flagged_count)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                call_id,
                overall_sentiment,
                overall_emotion,
                overall_confidence,
                single_modality_flag,
                secondary_signal_emotion,
                secondary_signal_confidence,
                segments_flagged_count,
            ),
        )
        conn.commit()
    finally:
        conn.close()


def test_queued_call_returns_status_without_result_fields(client):
    call_id = _make_call(status="queued")

    resp = client.get(f"/calls/{call_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["call_id"] == call_id
    assert body["status"] == "queued"
    assert body["filename"] == "call.wav"
    assert body["duration_seconds"] == 5.0
    assert "overall_sentiment" not in body
    assert "overall_emotion" not in body
    assert "overall_confidence" not in body


def test_processing_call_returns_status_without_result_fields(client):
    call_id = _make_call(status="processing")

    resp = client.get(f"/calls/{call_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "processing"
    assert "overall_sentiment" not in body


def test_failed_call_is_distinguishable_from_processing(client):
    """The whole reason this endpoint exists (Dev Notes item 1): a client
    must be able to tell `failed` and `processing` apart structurally, not
    by parsing a message string."""
    call_id = _make_call(status="failed")

    resp = client.get(f"/calls/{call_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "failed"
    assert "overall_sentiment" not in body


def test_complete_call_includes_sentiment_emotion_confidence(client):
    call_id = _make_call(status="complete", duration_seconds=402.0)
    _seed_analysis_result(
        call_id=call_id,
        overall_sentiment="negative",
        overall_emotion="frustration",
        overall_confidence=0.84,
    )

    resp = client.get(f"/calls/{call_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["call_id"] == call_id
    assert body["status"] == "complete"
    assert body["filename"] == "call.wav"
    assert body["duration_seconds"] == 402.0
    assert body["overall_sentiment"] == "negative"
    assert body["overall_emotion"] == "frustration"
    assert body["overall_confidence"] == 0.84


def test_complete_call_with_no_analysis_result_is_no_speech_detected_not_an_error(client):
    """Story 2.4 (Task 2): a `complete` Call with no AnalysisResult row is
    the well-defined "no speech detected" outcome (Story 1.6, 2026-08-14
    decision), not an infra fault — must not be a 500."""
    call_id = _make_call(status="complete")

    resp = client.get(f"/calls/{call_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "complete"
    assert body["no_speech_detected"] is True
    assert "overall_sentiment" not in body
    assert "overall_emotion" not in body
    assert "overall_confidence" not in body
    assert "single_modality_flag" not in body
    assert "secondary_signal_emotion" not in body
    assert "secondary_signal_confidence" not in body


def test_complete_call_includes_completed_at(client):
    """Story 2.4 (Task 1/2): completed_at is read straight from the Call
    row once a Call is complete."""
    call_id = _make_call(status="complete")
    _seed_analysis_result(call_id=call_id)
    conn = db.get_connection()
    try:
        conn.execute(
            "UPDATE Call SET completed_at = ? WHERE id = ?",
            ("2026-08-15T00:03:12+00:00", call_id),
        )
        conn.commit()
    finally:
        conn.close()

    resp = client.get(f"/calls/{call_id}")

    assert resp.status_code == 200
    assert resp.json()["completed_at"] == "2026-08-15T00:03:12+00:00"


def test_complete_call_includes_secondary_signal_and_single_modality_fields(client):
    """Story 2.4 (Task 2): single_modality_flag/secondary_signal_emotion/
    secondary_signal_confidence round-trip from AnalysisResult into the
    response, non-default values included."""
    call_id = _make_call(status="complete")
    _seed_analysis_result(
        call_id=call_id,
        single_modality_flag=1,
        secondary_signal_emotion="resignation",
        secondary_signal_confidence=0.41,
    )

    resp = client.get(f"/calls/{call_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["single_modality_flag"] is True
    assert body["secondary_signal_emotion"] == "resignation"
    assert body["secondary_signal_confidence"] == 0.41


def test_complete_call_with_no_secondary_signal_returns_null(client):
    """Story 2.4 (Task 2): the "None flagged" case — secondary_signal_* are
    real SQL NULL, passed through as JSON null, not omitted or coerced."""
    call_id = _make_call(status="complete")
    _seed_analysis_result(call_id=call_id)

    resp = client.get(f"/calls/{call_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["secondary_signal_emotion"] is None
    assert body["secondary_signal_confidence"] is None


def test_nonexistent_call_returns_404(client):
    resp = client.get(f"/calls/{uuid.uuid4()}")

    assert resp.status_code == 404
    body = resp.json()
    assert body["error_code"] == "CALL_NOT_FOUND"
    assert set(body.keys()) == {"error_code", "message", "next_step"}
    assert body["next_step"]


# Story 3.4 (AC4): `speaker_attribution_unavailable` — the same whole-Call
# fact `get_transcript` already computes (Story 3.3), also exposed here
# because the Session Call List (frontend/src/pages/SessionCallList.tsx)
# only ever polls this endpoint, never `/transcript`.


def test_complete_call_includes_speaker_attribution_unavailable_true_for_mono_call_with_no_labels(client):
    call_id = _make_call(status="complete", channel_count=1)
    _seed_analysis_result(call_id=call_id)
    _seed_turn(call_id=call_id, turn_index=0, start_time=0.0, end_time=2.0)
    _seed_turn(call_id=call_id, turn_index=1, start_time=2.0, end_time=4.0)

    resp = client.get(f"/calls/{call_id}")

    assert resp.status_code == 200
    assert resp.json()["speaker_attribution_unavailable"] is True


def test_complete_call_includes_speaker_attribution_unavailable_false_for_mono_call_with_partial_labels(client):
    call_id = _make_call(status="complete", channel_count=1)
    _seed_analysis_result(call_id=call_id)
    _seed_turn(call_id=call_id, turn_index=0, start_time=0.0, end_time=2.0, speaker_label="Speaker A")
    _seed_turn(call_id=call_id, turn_index=1, start_time=2.0, end_time=4.0)

    resp = client.get(f"/calls/{call_id}")

    assert resp.status_code == 200
    assert resp.json()["speaker_attribution_unavailable"] is False


def test_complete_call_includes_speaker_attribution_unavailable_false_for_stereo_call(client):
    call_id = _make_call(status="complete", channel_count=2)
    _seed_analysis_result(call_id=call_id)
    _seed_turn(call_id=call_id, turn_index=0, start_time=0.0, end_time=2.0, speaker_label="Speaker A")

    resp = client.get(f"/calls/{call_id}")

    assert resp.status_code == 200
    assert resp.json()["speaker_attribution_unavailable"] is False


def test_complete_call_with_no_speech_detected_includes_speaker_attribution_unavailable_false(client):
    """Story 3.4: a `no_speech_detected` complete Call (zero turns, zero
    AnalysisResult) has nothing to have failed attribution on — both facts
    are co-present on the same response, neither suppressing the other.
    `channel_count=1` (mono) is set explicitly so a `False` result here can
    only come from the turns-empty guard, not the channel_count guard."""
    call_id = _make_call(status="complete", channel_count=1)

    resp = client.get(f"/calls/{call_id}")

    assert resp.status_code == 200
    body = resp.json()
    assert body["no_speech_detected"] is True
    assert body["speaker_attribution_unavailable"] is False


def test_complete_call_includes_speaker_attribution_unavailable_false_when_channel_count_unset(client):
    """Code review (2026-08-17): pre-existing Calls with no channel_count
    recorded (`None`) must not be treated as mono — `None == 1` is `False`,
    not a crash. Mirrors test_transcript.py's equivalent coverage of the
    same shared `_speaker_attribution_unavailable_flag` helper."""
    call_id = _make_call(status="complete")
    _seed_analysis_result(call_id=call_id)
    _seed_turn(call_id=call_id, turn_index=0, start_time=0.0, end_time=2.0)

    resp = client.get(f"/calls/{call_id}")

    assert resp.status_code == 200
    assert resp.json()["speaker_attribution_unavailable"] is False


@pytest.mark.parametrize("status", ["queued", "processing", "failed"])
def test_non_complete_call_never_includes_speaker_attribution_unavailable(client, status):
    call_id = _make_call(status=status)

    resp = client.get(f"/calls/{call_id}")

    assert resp.status_code == 200
    assert "speaker_attribution_unavailable" not in resp.json()
