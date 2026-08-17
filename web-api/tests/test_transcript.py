"""Tests for GET /calls/{call_id}/transcript — Story 2.4 (Task 3).

Local seeding helpers mirror test_timeline.py's `_make_call`/raw-SQL-insert
pattern exactly (copied locally rather than imported across test files, per
that file's own established convention).
"""

from __future__ import annotations

import uuid

import pytest

from app import db


def _make_call(*, status: str, channel_count: int | None = None) -> str:
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
        if channel_count is not None:
            # Story 3.3: db.insert_call() never accepts channel_count by
            # design (Story 1.2/1.10) — only ml-service's ingest job writes
            # it. Seeded directly here, same raw-SQL pattern this file
            # already uses for TranscriptTurn fields insert_call() doesn't
            # cover.
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
    text: str = "hello",
    text_sentiment: str | None = "neutral",
    text_emotion: str | None = "neutral",
    text_confidence: float | None = 0.7,
    speaker_label: str | None = None,
    speaker_confidence: float | None = None,
) -> str:
    turn_id = str(uuid.uuid4())
    conn = db.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO TranscriptTurn
                (id, call_id, turn_index, start_time, end_time, text,
                 text_sentiment, text_emotion, text_confidence, speaker_label,
                 speaker_confidence)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                turn_id,
                call_id,
                turn_index,
                start_time,
                end_time,
                text,
                text_sentiment,
                text_emotion,
                text_confidence,
                speaker_label,
                speaker_confidence,
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return turn_id


def test_complete_call_returns_turns_in_order_with_all_fields(client):
    call_id = _make_call(status="complete")
    turn2 = _seed_turn(
        call_id=call_id,
        turn_index=1,
        start_time=2.0,
        end_time=4.0,
        text="second turn",
        text_sentiment="positive",
        text_emotion="happy",
        text_confidence=0.6,
    )
    turn1 = _seed_turn(
        call_id=call_id,
        turn_index=0,
        start_time=0.0,
        end_time=2.0,
        text="first turn",
        text_sentiment="negative",
        text_emotion="angry",
        text_confidence=0.9,
    )

    resp = client.get(f"/calls/{call_id}/transcript")

    assert resp.status_code == 200
    body = resp.json()
    assert body["call_id"] == call_id
    assert body["status"] == "complete"
    assert [t["turn_id"] for t in body["turns"]] == [turn1, turn2]

    first = body["turns"][0]
    assert first["turn_index"] == 0
    assert first["start_time"] == 0.0
    assert first["end_time"] == 2.0
    assert first["text"] == "first turn"
    assert first["text_sentiment"] == "negative"
    assert first["text_emotion"] == "angry"
    assert first["text_confidence"] == 0.9
    # Story 3.1: a turn with no stereo channel-based attribution (mono, or
    # no attribution filter run) returns speaker_label as null, not absent.
    assert first["speaker_label"] is None


def test_transcript_returns_stereo_speaker_label(client):
    """Story 3.1 (AC2): a turn attributed by the stereo channel-based filter
    returns its canonical "Speaker A"/"Speaker B" label."""
    call_id = _make_call(status="complete")
    _seed_turn(
        call_id=call_id,
        turn_index=0,
        start_time=0.0,
        end_time=2.0,
        text="hello",
        speaker_label="Speaker A",
    )

    resp = client.get(f"/calls/{call_id}/transcript")

    assert resp.status_code == 200
    body = resp.json()
    assert body["turns"][0]["speaker_label"] == "Speaker A"


def test_transcript_speaker_label_null_for_unattributed_turn(client):
    """Story 3.1: a mono/unattributed turn's null speaker_label round-trips
    as JSON null, not an absent key — matching the frontend's optional-but-
    present `speaker_label?: string | null` field contract."""
    call_id = _make_call(status="complete")
    _seed_turn(call_id=call_id, turn_index=0, start_time=0.0, end_time=2.0)

    resp = client.get(f"/calls/{call_id}/transcript")

    assert resp.status_code == 200
    body = resp.json()
    assert "speaker_label" in body["turns"][0]
    assert body["turns"][0]["speaker_label"] is None


def test_speaker_uncertain_true_below_threshold(client):
    """Story 3.3 (AC2, AC6): a mono turn whose speaker_confidence is below
    the default 0.5 threshold is flagged speaker_uncertain."""
    call_id = _make_call(status="complete", channel_count=1)
    _seed_turn(
        call_id=call_id,
        turn_index=0,
        start_time=0.0,
        end_time=2.0,
        speaker_label="Speaker A",
        speaker_confidence=0.3,
    )

    resp = client.get(f"/calls/{call_id}/transcript")

    assert resp.status_code == 200
    assert resp.json()["turns"][0]["speaker_uncertain"] is True


def test_speaker_uncertain_false_above_threshold(client):
    call_id = _make_call(status="complete", channel_count=1)
    _seed_turn(
        call_id=call_id,
        turn_index=0,
        start_time=0.0,
        end_time=2.0,
        speaker_label="Speaker A",
        speaker_confidence=0.9,
    )

    resp = client.get(f"/calls/{call_id}/transcript")

    assert resp.status_code == 200
    assert resp.json()["turns"][0]["speaker_uncertain"] is False


def test_speaker_uncertain_false_at_exact_threshold(client):
    """Strict `<` comparison, matching `_low_confidence_flag`'s convention —
    a confidence exactly equal to the threshold is not flagged."""
    call_id = _make_call(status="complete", channel_count=1)
    _seed_turn(
        call_id=call_id,
        turn_index=0,
        start_time=0.0,
        end_time=2.0,
        speaker_label="Speaker A",
        speaker_confidence=0.5,
    )

    resp = client.get(f"/calls/{call_id}/transcript")

    assert resp.status_code == 200
    assert resp.json()["turns"][0]["speaker_uncertain"] is False


def test_speaker_uncertain_false_when_confidence_is_null(client):
    """AC4/AC5/AD-10: a `None` confidence (stereo turns always; mono turns
    diarization never attributed) is never flagged uncertain — "no
    confidence value exists" is not the same claim as "confidence is low"."""
    call_id = _make_call(status="complete", channel_count=2)
    _seed_turn(
        call_id=call_id,
        turn_index=0,
        start_time=0.0,
        end_time=2.0,
        speaker_label="Speaker A",
        speaker_confidence=None,
    )

    resp = client.get(f"/calls/{call_id}/transcript")

    assert resp.status_code == 200
    assert resp.json()["turns"][0]["speaker_uncertain"] is False


def test_custom_speaker_uncertain_threshold_changes_flagging_behavior(client, monkeypatch):
    monkeypatch.setattr("app.routers.calls.SPEAKER_UNCERTAIN_THRESHOLD", 0.85)
    call_id = _make_call(status="complete", channel_count=1)
    _seed_turn(
        call_id=call_id,
        turn_index=0,
        start_time=0.0,
        end_time=2.0,
        speaker_label="Speaker A",
        speaker_confidence=0.8,
    )

    resp = client.get(f"/calls/{call_id}/transcript")

    assert resp.status_code == 200
    assert resp.json()["turns"][0]["speaker_uncertain"] is True


def test_speaker_attribution_unavailable_true_for_mono_call_with_no_labels(client):
    """Story 3.3 (AC1, AC3): a mono Call where every turn lacks
    speaker_label gets the whole-Call unavailable flag."""
    call_id = _make_call(status="complete", channel_count=1)
    _seed_turn(call_id=call_id, turn_index=0, start_time=0.0, end_time=2.0)
    _seed_turn(call_id=call_id, turn_index=1, start_time=2.0, end_time=4.0)

    resp = client.get(f"/calls/{call_id}/transcript")

    assert resp.status_code == 200
    assert resp.json()["speaker_attribution_unavailable"] is True


def test_speaker_attribution_unavailable_false_for_mono_call_with_partial_labels(client):
    """AC1's "no usable speaker split at all" — one attributed turn means
    diarization DID produce a usable split; not the whole-Call state."""
    call_id = _make_call(status="complete", channel_count=1)
    _seed_turn(
        call_id=call_id,
        turn_index=0,
        start_time=0.0,
        end_time=2.0,
        speaker_label="Speaker A",
        speaker_confidence=0.9,
    )
    _seed_turn(call_id=call_id, turn_index=1, start_time=2.0, end_time=4.0)

    resp = client.get(f"/calls/{call_id}/transcript")

    assert resp.status_code == 200
    assert resp.json()["speaker_attribution_unavailable"] is False


def test_speaker_attribution_unavailable_false_for_stereo_call_even_if_all_null(client):
    """AC4: stereo never gets this state, even defensively (should not occur
    in practice per Story 3.1, but must not accidentally flag)."""
    call_id = _make_call(status="complete", channel_count=2)
    _seed_turn(call_id=call_id, turn_index=0, start_time=0.0, end_time=2.0)

    resp = client.get(f"/calls/{call_id}/transcript")

    assert resp.status_code == 200
    assert resp.json()["speaker_attribution_unavailable"] is False


def test_speaker_attribution_unavailable_false_for_stereo_call_with_labels(client):
    call_id = _make_call(status="complete", channel_count=2)
    _seed_turn(
        call_id=call_id,
        turn_index=0,
        start_time=0.0,
        end_time=2.0,
        speaker_label="Speaker A",
    )

    resp = client.get(f"/calls/{call_id}/transcript")

    assert resp.status_code == 200
    assert resp.json()["speaker_attribution_unavailable"] is False


def test_speaker_attribution_unavailable_false_for_zero_turn_mono_call(client):
    """A "no speech detected" mono Call has nothing to have failed
    attribution on — not the "unavailable" state."""
    call_id = _make_call(status="complete", channel_count=1)

    resp = client.get(f"/calls/{call_id}/transcript")

    assert resp.status_code == 200
    body = resp.json()
    assert body["turns"] == []
    assert body["speaker_attribution_unavailable"] is False


def test_speaker_attribution_unavailable_false_when_channel_count_unset(client):
    """Pre-existing Calls with no channel_count recorded (`None`) must not
    be treated as mono — `None == 1` is False, not a crash."""
    call_id = _make_call(status="complete")
    _seed_turn(call_id=call_id, turn_index=0, start_time=0.0, end_time=2.0)

    resp = client.get(f"/calls/{call_id}/transcript")

    assert resp.status_code == 200
    assert resp.json()["speaker_attribution_unavailable"] is False


def test_mixed_state_call_computes_both_new_fields_independently_per_turn(client):
    """Code review (2026-08-17): a realistic mono Call combining a
    confidently-attributed turn, a low-confidence/uncertain turn, and a
    fully unattributed turn in one response — guards against an
    indexing/aggregation bug across turns that a single-turn test wouldn't
    catch. `speaker_attribution_unavailable` is `False` (at least one
    attributed turn), and each turn's `speaker_uncertain` reflects only its
    own `speaker_confidence`."""
    call_id = _make_call(status="complete", channel_count=1)
    confident_id = _seed_turn(
        call_id=call_id,
        turn_index=0,
        start_time=0.0,
        end_time=2.0,
        speaker_label="Speaker A",
        speaker_confidence=0.9,
    )
    uncertain_id = _seed_turn(
        call_id=call_id,
        turn_index=1,
        start_time=2.0,
        end_time=4.0,
        speaker_label="Speaker B",
        speaker_confidence=0.2,
    )
    unattributed_id = _seed_turn(call_id=call_id, turn_index=2, start_time=4.0, end_time=6.0)

    resp = client.get(f"/calls/{call_id}/transcript")

    assert resp.status_code == 200
    body = resp.json()
    assert body["speaker_attribution_unavailable"] is False
    by_id = {t["turn_id"]: t for t in body["turns"]}
    assert by_id[confident_id]["speaker_uncertain"] is False
    assert by_id[uncertain_id]["speaker_uncertain"] is True
    assert by_id[unattributed_id]["speaker_uncertain"] is False
    assert by_id[unattributed_id]["speaker_label"] is None


def test_zero_turn_complete_call_returns_empty_transcript(client):
    """A "no speech detected" Call, or one whose transcript branch never
    completed — a valid, complete result, not an error."""
    call_id = _make_call(status="complete")

    resp = client.get(f"/calls/{call_id}/transcript")

    assert resp.status_code == 200
    body = resp.json()
    assert body["status"] == "complete"
    assert body["turns"] == []


def test_nonexistent_call_returns_404(client):
    resp = client.get(f"/calls/{uuid.uuid4()}/transcript")

    assert resp.status_code == 404
    body = resp.json()
    assert body["error_code"] == "CALL_NOT_FOUND"
    assert set(body.keys()) == {"error_code", "message", "next_step"}
    assert body["next_step"]


@pytest.mark.parametrize("status", ["queued", "processing", "failed"])
def test_non_complete_call_returns_409_naming_actual_status(client, status):
    call_id = _make_call(status=status)

    resp = client.get(f"/calls/{call_id}/transcript")

    assert resp.status_code == 409
    body = resp.json()
    assert body["error_code"] == "CALL_NOT_COMPLETE"
    assert status in body["message"]
    assert body["next_step"]
