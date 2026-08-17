"""Tests for GET /calls/{call_id}/acoustic-summary — Story 2.4 (Task 4).

Local seeding helpers mirror test_timeline.py's `_make_call`/raw-SQL-insert
pattern exactly (copied locally rather than imported across test files, per
that file's own established convention). AcousticEvidence rows are seeded
via TimelineSegment (its parent, joined on segment_id) since the endpoint
aggregates through that join.
"""

from __future__ import annotations

import uuid

import pytest

from app import db


def _make_call(*, status: str) -> str:
    call_id = str(uuid.uuid4())
    conn = db.get_connection()
    try:
        db.insert_call(
            conn,
            call_id=call_id,
            status=status,
            filename="call.wav",
            audio_format="wav",
            duration_seconds=5.0,
            size_bytes=1024,
            created_at="2026-08-15T00:00:00+00:00",
        )
    finally:
        conn.close()
    return call_id


def _seed_segment_with_acoustic_evidence(
    *,
    call_id: str,
    segment_index: int,
    pitch_mean_hz: float | None,
    energy_rms_mean: float = 0.04,
    speaking_rate_estimate: float = 2.5,
    pause_ratio: float = 0.2,
) -> None:
    segment_id = str(uuid.uuid4())
    conn = db.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO TimelineSegment (id, call_id, segment_index, start_time, end_time)
            VALUES (?, ?, ?, ?, ?)
            """,
            (segment_id, call_id, segment_index, float(segment_index), float(segment_index) + 1.0),
        )
        conn.execute(
            """
            INSERT INTO AcousticEvidence
                (segment_id, pitch_mean_hz, pitch_std_hz, energy_rms_mean,
                 speaking_rate_estimate, pause_ratio)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (segment_id, pitch_mean_hz, 10.0, energy_rms_mean, speaking_rate_estimate, pause_ratio),
        )
        conn.commit()
    finally:
        conn.close()


def test_multi_segment_call_returns_exact_computed_means(client):
    call_id = _make_call(status="complete")
    _seed_segment_with_acoustic_evidence(
        call_id=call_id,
        segment_index=0,
        pitch_mean_hz=120.0,
        energy_rms_mean=0.04,
        speaking_rate_estimate=2.0,
        pause_ratio=0.1,
    )
    _seed_segment_with_acoustic_evidence(
        call_id=call_id,
        segment_index=1,
        pitch_mean_hz=140.0,
        energy_rms_mean=0.06,
        speaking_rate_estimate=3.0,
        pause_ratio=0.3,
    )

    resp = client.get(f"/calls/{call_id}/acoustic-summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["call_id"] == call_id
    assert body["status"] == "complete"
    assert body["segment_count"] == 2
    assert body["pitch_mean_hz"] == pytest.approx(130.0)
    assert body["energy_rms_mean"] == pytest.approx(0.05)
    assert body["speaking_rate_estimate"] == pytest.approx(2.5)
    assert body["pause_ratio"] == pytest.approx(0.2)


def test_null_pitch_segment_excluded_from_pitch_average_only(client):
    """A segment with pitch_mean_hz IS NULL (entirely unvoiced) is excluded
    from the pitch average, but its other three (NOT NULL) fields still
    contribute to their own averages."""
    call_id = _make_call(status="complete")
    _seed_segment_with_acoustic_evidence(
        call_id=call_id,
        segment_index=0,
        pitch_mean_hz=None,
        energy_rms_mean=0.02,
        speaking_rate_estimate=1.0,
        pause_ratio=0.9,
    )
    _seed_segment_with_acoustic_evidence(
        call_id=call_id,
        segment_index=1,
        pitch_mean_hz=150.0,
        energy_rms_mean=0.06,
        speaking_rate_estimate=3.0,
        pause_ratio=0.1,
    )

    resp = client.get(f"/calls/{call_id}/acoustic-summary")

    body = resp.json()
    assert body["segment_count"] == 2
    # Only the one non-null pitch value, not averaged with a 0 for the null.
    assert body["pitch_mean_hz"] == pytest.approx(150.0)
    assert body["energy_rms_mean"] == pytest.approx(0.04)
    assert body["speaking_rate_estimate"] == pytest.approx(2.0)
    assert body["pause_ratio"] == pytest.approx(0.5)


def test_zero_segment_complete_call_returns_all_null(client):
    call_id = _make_call(status="complete")

    resp = client.get(f"/calls/{call_id}/acoustic-summary")

    assert resp.status_code == 200
    body = resp.json()
    assert body["segment_count"] == 0
    assert body["pitch_mean_hz"] is None
    assert body["energy_rms_mean"] is None
    assert body["speaking_rate_estimate"] is None
    assert body["pause_ratio"] is None


def test_nonexistent_call_returns_404(client):
    resp = client.get(f"/calls/{uuid.uuid4()}/acoustic-summary")

    assert resp.status_code == 404
    body = resp.json()
    assert body["error_code"] == "CALL_NOT_FOUND"
    assert set(body.keys()) == {"error_code", "message", "next_step"}
    assert body["next_step"]


@pytest.mark.parametrize("status", ["queued", "processing", "failed"])
def test_non_complete_call_returns_409_naming_actual_status(client, status):
    call_id = _make_call(status=status)

    resp = client.get(f"/calls/{call_id}/acoustic-summary")

    assert resp.status_code == 409
    body = resp.json()
    assert body["error_code"] == "CALL_NOT_COMPLETE"
    assert status in body["message"]
    assert body["next_step"]
