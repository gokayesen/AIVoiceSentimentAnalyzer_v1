"""Tests for GET /calls/{call_id}/timeline — Story 1.7 (Emotional Timeline Retrieval).

Covers AC1 (fused Sentiment/Emotion/confidence/disagreement flag, chronological
order, zero-segment "no speech detected" Call), AC2 (granularity — distinct
segments never merged), AC3 (segment boundaries are an exact pass-through of
the persisted start_time/end_time), and AC4 (independently runnable — no
Redis/queue involved, only SQLite).

Local seeding helpers insert directly via `db.insert_call` (a real web-api
write function — status is not restricted to "queued") and a raw SQL INSERT
for TimelineSegment (deliberately not a new db.py write function — web-api's
production code must never write this table, per AD-13; see Dev Notes in the
story file).
"""

from __future__ import annotations

import uuid

import pytest

from app import db
from app.routers import calls as calls_module


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
            created_at="2026-08-14T00:00:00+00:00",
        )
    finally:
        conn.close()
    return call_id


def _seed_segment(
    *,
    call_id: str,
    segment_index: int,
    start_time: float,
    end_time: float,
    fused_sentiment: str | None = "positive",
    fused_emotion: str | None = "happy",
    fused_confidence: float | None = 0.75,
    single_modality_flag: int = 0,
    disagreement_flag: int = 0,
    acoustic_emotion: str | None = None,
    acoustic_confidence: float | None = None,
) -> str:
    segment_id = str(uuid.uuid4())
    conn = db.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO TimelineSegment
                (id, call_id, segment_index, start_time, end_time,
                 fused_sentiment, fused_emotion, fused_confidence,
                 single_modality_flag, disagreement_flag,
                 acoustic_emotion, acoustic_confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                segment_id,
                call_id,
                segment_index,
                start_time,
                end_time,
                fused_sentiment,
                fused_emotion,
                fused_confidence,
                single_modality_flag,
                disagreement_flag,
                acoustic_emotion,
                acoustic_confidence,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return segment_id


def _seed_acoustic_evidence(
    *,
    segment_id: str,
    pitch_mean_hz: float | None = 180.0,
    energy_rms_mean: float | None = 0.05,
    speaking_rate_estimate: float | None = 3.2,
    pause_ratio: float | None = 0.2,
) -> None:
    conn = db.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO AcousticEvidence
                (segment_id, pitch_mean_hz, energy_rms_mean,
                 speaking_rate_estimate, pause_ratio)
            VALUES (?, ?, ?, ?, ?)
            """,
            (segment_id, pitch_mean_hz, energy_rms_mean, speaking_rate_estimate, pause_ratio),
        )
        conn.commit()
    finally:
        conn.close()


def test_complete_call_returns_multimodal_and_single_modality_segments(client):
    """AC1: fused Sentiment/Emotion/confidence/disagreement flag are all
    returned; disagreement flag defaults to false (Story 1.9 not yet built)."""
    call_id = _make_call(status="complete")
    seg1 = _seed_segment(
        call_id=call_id,
        segment_index=0,
        start_time=0.0,
        end_time=2.0,
        fused_sentiment="negative",
        fused_emotion="angry",
        fused_confidence=0.9,
        single_modality_flag=0,
    )
    # single_modality_flag=1 mirrors a realistic single-modality
    # TimelineSegment row shape — it is intentionally NOT asserted below
    # because the response contract (Dev Notes) deliberately excludes this
    # field; nothing to check for it here.
    seg2 = _seed_segment(
        call_id=call_id,
        segment_index=1,
        start_time=2.0,
        end_time=4.0,
        fused_sentiment="positive",
        fused_emotion="happy",
        fused_confidence=0.6,
        single_modality_flag=1,
    )

    resp = client.get(f"/calls/{call_id}/timeline")

    assert resp.status_code == 200
    body = resp.json()
    assert body["call_id"] == call_id
    assert body["status"] == "complete"
    assert [s["segment_id"] for s in body["segments"]] == [seg1, seg2]

    first = body["segments"][0]
    assert first["fused_sentiment"] == "negative"
    assert first["fused_emotion"] == "angry"
    assert first["fused_confidence"] == 0.9
    assert first["disagreement_flag"] is False
    assert first["low_confidence_flag"] is False
    assert first["flag_reason"] is None

    second = body["segments"][1]
    assert second["fused_sentiment"] == "positive"
    assert second["fused_confidence"] == 0.6
    assert second["disagreement_flag"] is False
    assert second["low_confidence_flag"] is False
    assert second["flag_reason"] is None


def test_disagreement_flag_true_is_returned(client):
    """AC1: disagreement_flag is a pure pass-through of whatever ml-service
    persisted — the True path must round-trip correctly too, not just the
    all-False default every other test happens to use."""
    call_id = _make_call(status="complete")
    _seed_segment(call_id=call_id, segment_index=0, start_time=0.0, end_time=2.0, disagreement_flag=1)

    resp = client.get(f"/calls/{call_id}/timeline")

    assert resp.json()["segments"][0]["disagreement_flag"] is True


def test_below_threshold_confidence_is_flagged_low_confidence(client):
    """AC2: a segment whose fused_confidence falls below the configured
    low_confidence_threshold (default 0.5) is marked low_confidence_flag=True
    with a non-empty flag_reason naming the actual confidence value — never a
    bare float on a flagged item."""
    call_id = _make_call(status="complete")
    _seed_segment(call_id=call_id, segment_index=0, start_time=0.0, end_time=2.0, fused_confidence=0.3)

    resp = client.get(f"/calls/{call_id}/timeline")

    segment = resp.json()["segments"][0]
    assert segment["low_confidence_flag"] is True
    assert isinstance(segment["flag_reason"], str)
    assert segment["flag_reason"]
    assert "0.3" in segment["flag_reason"]


def test_confidence_exactly_at_threshold_is_not_flagged(client):
    """AC2: 'falls below' is a strict less-than — a confidence exactly equal
    to the threshold (default 0.5) is not low-confidence."""
    call_id = _make_call(status="complete")
    _seed_segment(call_id=call_id, segment_index=0, start_time=0.0, end_time=2.0, fused_confidence=0.5)

    resp = client.get(f"/calls/{call_id}/timeline")

    segment = resp.json()["segments"][0]
    assert segment["low_confidence_flag"] is False
    assert segment["flag_reason"] is None


def test_custom_low_confidence_threshold_changes_flagging_behavior(client, monkeypatch):
    """AC4: the threshold is genuinely operator-tunable, not just the default
    0.5 every other test in this file exercises — raising it changes which
    segments get flagged."""
    monkeypatch.setattr(calls_module, "LOW_CONFIDENCE_THRESHOLD", 0.85)
    call_id = _make_call(status="complete")
    _seed_segment(call_id=call_id, segment_index=0, start_time=0.0, end_time=2.0, fused_confidence=0.8)

    resp = client.get(f"/calls/{call_id}/timeline")

    segment = resp.json()["segments"][0]
    assert segment["low_confidence_flag"] is True
    assert "0.80" in segment["flag_reason"]
    assert "0.85" in segment["flag_reason"]


def test_zero_segment_complete_call_returns_empty_timeline(client):
    """AC1: a Call with zero TimelineSegment rows (Story 1.6's "no speech
    detected" outcome) is a valid, complete result — empty list, not an
    error."""
    call_id = _make_call(status="complete")

    resp = client.get(f"/calls/{call_id}/timeline")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "complete"
    assert body["segments"] == []


def test_distinct_emotional_shifts_are_never_merged(client):
    """AC2: two segments with different fused_sentiment values on the same
    Call both appear distinctly — never aggregated into one entry."""
    call_id = _make_call(status="complete")
    _seed_segment(
        call_id=call_id, segment_index=0, start_time=0.0, end_time=1.5,
        fused_sentiment="negative", fused_emotion="angry", fused_confidence=0.8,
    )
    _seed_segment(
        call_id=call_id, segment_index=1, start_time=1.5, end_time=3.0,
        fused_sentiment="positive", fused_emotion="happy", fused_confidence=0.7,
    )

    resp = client.get(f"/calls/{call_id}/timeline")

    body = resp.json()
    sentiments = [s["fused_sentiment"] for s in body["segments"]]
    assert sentiments == ["negative", "positive"]
    assert len(body["segments"]) == 2


def test_segment_boundaries_are_an_exact_pass_through(client):
    """AC3: returned start_time/end_time exactly match what was persisted —
    no second, independently-computed boundary set."""
    call_id = _make_call(status="complete")
    _seed_segment(call_id=call_id, segment_index=0, start_time=0.42, end_time=3.17)

    resp = client.get(f"/calls/{call_id}/timeline")

    segment = resp.json()["segments"][0]
    assert segment["start_time"] == 0.42
    assert segment["end_time"] == 3.17


def test_segments_are_returned_in_chronological_order_regardless_of_insertion_order(client):
    call_id = _make_call(status="complete")
    # Insert out of chronological order.
    seg_third = _seed_segment(call_id=call_id, segment_index=2, start_time=4.0, end_time=6.0)
    seg_first = _seed_segment(call_id=call_id, segment_index=0, start_time=0.0, end_time=2.0)
    seg_second = _seed_segment(call_id=call_id, segment_index=1, start_time=2.0, end_time=4.0)

    resp = client.get(f"/calls/{call_id}/timeline")

    segment_ids = [s["segment_id"] for s in resp.json()["segments"]]
    assert segment_ids == [seg_first, seg_second, seg_third]


def test_acoustic_and_tone_signal_fields_round_trip(client):
    """Story 2.5 Task 1: acoustic_emotion/acoustic_confidence (already read
    via SELECT * but previously excluded from the response) plus the four
    per-segment AcousticEvidence fields are now returned, joined by
    segment_id."""
    call_id = _make_call(status="complete")
    seg_id = _seed_segment(
        call_id=call_id,
        segment_index=0,
        start_time=0.0,
        end_time=2.0,
        acoustic_emotion="frustration",
        acoustic_confidence=0.71,
    )
    _seed_acoustic_evidence(
        segment_id=seg_id,
        pitch_mean_hz=210.5,
        energy_rms_mean=0.061,
        speaking_rate_estimate=4.1,
        pause_ratio=0.15,
    )

    resp = client.get(f"/calls/{call_id}/timeline")

    segment = resp.json()["segments"][0]
    assert segment["acoustic_emotion"] == "frustration"
    assert segment["acoustic_confidence"] == 0.71
    assert segment["pitch_mean_hz"] == 210.5
    assert segment["energy_rms_mean"] == 0.061
    assert segment["speaking_rate_estimate"] == 4.1
    assert segment["pause_ratio"] == 0.15


def test_segment_with_no_matching_acoustic_evidence_returns_null_fields(client):
    """Story 2.5 Task 1: should not occur under normal operation (AD-3), but
    a segment with no AcousticEvidence row must return null for all four
    fields, not raise."""
    call_id = _make_call(status="complete")
    _seed_segment(call_id=call_id, segment_index=0, start_time=0.0, end_time=2.0)

    resp = client.get(f"/calls/{call_id}/timeline")

    segment = resp.json()["segments"][0]
    assert segment["pitch_mean_hz"] is None
    assert segment["energy_rms_mean"] is None
    assert segment["speaking_rate_estimate"] is None
    assert segment["pause_ratio"] is None
    assert segment["acoustic_emotion"] is None
    assert segment["acoustic_confidence"] is None


def test_nonexistent_call_returns_404(client):
    resp = client.get(f"/calls/{uuid.uuid4()}/timeline")

    assert resp.status_code == 404
    body = resp.json()
    assert body["error_code"] == "CALL_NOT_FOUND"
    assert set(body.keys()) == {"error_code", "message", "next_step"}
    assert body["next_step"]


@pytest.mark.parametrize("status", ["queued", "processing", "failed"])
def test_non_complete_call_returns_409_naming_actual_status(client, status):
    call_id = _make_call(status=status)

    resp = client.get(f"/calls/{call_id}/timeline")

    assert resp.status_code == 409
    body = resp.json()
    assert body["error_code"] == "CALL_NOT_COMPLETE"
    assert status in body["message"]
    assert body["next_step"]
