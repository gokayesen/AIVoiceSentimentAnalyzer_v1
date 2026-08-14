"""Tests for the fusion RQ job (Story 1.6, AC 1,2,3,4,6,7,9)."""

from __future__ import annotations

import uuid

import pytest

from app import db
from app.pipeline.acoustic.run import run_acoustic
from app.pipeline.fusion.run import run_fusion
from app.pipeline.transcript.run import run_transcript
from app.pipeline.transcript.sentiment_run import run_text_sentiment

_KNOWN_POLARITIES = {"negative", "mixed", "positive", "neutral"}


def _seed_segments_with_acoustic(call_id: str, segments: list[dict]) -> list[str]:
    """Directly seeds `TimelineSegment` rows with `acoustic_emotion`/
    `acoustic_confidence` already set — bypassing real acoustic model
    inference (mirrors Story 1.5's `_seed_turns_directly` pattern, applied
    one pipeline stage further down) so fusion-only tests are fast and
    deterministic. `segments` is a list of dicts with keys start_time,
    end_time, acoustic_emotion, acoustic_confidence. Returns the inserted
    segment ids in persisted (segment_index) order."""
    conn = db.get_connection()
    try:
        segment_ids = [str(uuid.uuid4()) for _ in segments]
        db.insert_timeline_segments(
            conn,
            call_id=call_id,
            segments=[
                (seg_id, idx, s["start_time"], s["end_time"])
                for idx, (seg_id, s) in enumerate(zip(segment_ids, segments, strict=True))
            ],
        )
        conn.executemany(
            "UPDATE TimelineSegment SET acoustic_emotion = ?, acoustic_confidence = ? WHERE id = ?",
            [
                (s["acoustic_emotion"], s["acoustic_confidence"], seg_id)
                for seg_id, s in zip(segment_ids, segments, strict=True)
            ],
        )
        conn.commit()
        # run_fusion is always chained after acoustic (and, when present,
        # transcript/text-sentiment) succeeded — none of which ever move
        # Call.status away from "processing" — simulate that precondition.
        db.set_call_status(conn, call_id=call_id, status="processing")
    finally:
        conn.close()
    return segment_ids


def _seed_transcript_turn(
    call_id: str,
    *,
    turn_index: int,
    start_time: float,
    end_time: float,
    text_sentiment: str,
    text_emotion: str,
    text_confidence: float,
) -> None:
    """Directly seeds one `TranscriptTurn` row with its text-sentiment
    output already set — bypassing real STT/text-sentiment inference, same
    rationale as `_seed_segments_with_acoustic` above."""
    conn = db.get_connection()
    try:
        turn_id = str(uuid.uuid4())
        db.persist_transcript_turns(
            conn,
            turns=[(turn_id, call_id, turn_index, start_time, end_time, "some turn text")],
            words=[],
        )
        conn.execute(
            "UPDATE TranscriptTurn SET text_sentiment = ?, text_emotion = ?, text_confidence = ? "
            "WHERE id = ?",
            (text_sentiment, text_emotion, text_confidence, turn_id),
        )
        conn.commit()
    finally:
        conn.close()


def test_run_fusion_multimodal_segment_persists_valid_output_and_completes_the_call(
    make_call, call_row
):
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=None)
    (segment_id,) = _seed_segments_with_acoustic(
        call_id,
        [{"start_time": 0.0, "end_time": 2.0, "acoustic_emotion": "angry", "acoustic_confidence": 0.9}],
    )
    _seed_transcript_turn(
        call_id,
        turn_index=0,
        start_time=0.0,
        end_time=2.0,
        text_sentiment="negative",
        text_emotion="disappointed",
        text_confidence=0.4,
    )

    run_fusion(call_id)

    conn = db.get_connection()
    try:
        segment = conn.execute(
            "SELECT * FROM TimelineSegment WHERE id = ?", (segment_id,)
        ).fetchone()
        result = db.get_analysis_result(conn, call_id=call_id)
    finally:
        conn.close()

    assert segment["fused_sentiment"] == "negative"
    assert segment["fused_emotion"] == "angry"  # acoustic dominant (0.9 > 0.4)
    assert segment["single_modality_flag"] == 0
    assert segment["disagreement_flag"] == 0
    assert segment["fused_confidence"] > 0.0

    assert result is not None
    assert result["overall_sentiment"] in _KNOWN_POLARITIES
    assert result["single_modality_flag"] == 0
    assert result["secondary_signal_emotion"] == "disappointed"
    assert result["segments_flagged_count"] == 0

    assert call_row(call_id)["status"] == "complete"


def test_run_fusion_disagreeing_segment_sets_disagreement_flag_and_counts_it(
    make_call, call_row
):
    """Story 1.9 (AC1): a real polarity mismatch with both raw modality
    confidences above the default DISAGREEMENT_THRESHOLD (0.5) is persisted
    as a real disagreement, end-to-end through the RQ job."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=None)
    (segment_id,) = _seed_segments_with_acoustic(
        call_id,
        [{"start_time": 0.0, "end_time": 2.0, "acoustic_emotion": "sad", "acoustic_confidence": 0.7}],
    )
    _seed_transcript_turn(
        call_id,
        turn_index=0,
        start_time=0.0,
        end_time=2.0,
        text_sentiment="positive",
        text_emotion="admiring",
        text_confidence=0.6,
    )

    run_fusion(call_id)

    conn = db.get_connection()
    try:
        segment = conn.execute(
            "SELECT * FROM TimelineSegment WHERE id = ?", (segment_id,)
        ).fetchone()
        result = db.get_analysis_result(conn, call_id=call_id)
    finally:
        conn.close()

    assert segment["disagreement_flag"] == 1
    assert result is not None
    # This Call has exactly one segment, so == 1 is the only correct value
    # (code review, 2026-08-14: a loose >= 1 would still pass if reduce_call
    # double-counted).
    assert result["segments_flagged_count"] == 1


def test_run_fusion_weak_signal_does_not_set_disagreement_flag_despite_polarity_mismatch(
    make_call, call_row
):
    """Story 1.9: a polarity mismatch alone is not enough — one modality's
    confidence (0.4) below the default threshold (0.5) must not trigger a
    flagged disagreement."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=None)
    (segment_id,) = _seed_segments_with_acoustic(
        call_id,
        [{"start_time": 0.0, "end_time": 2.0, "acoustic_emotion": "angry", "acoustic_confidence": 0.9}],
    )
    _seed_transcript_turn(
        call_id,
        turn_index=0,
        start_time=0.0,
        end_time=2.0,
        text_sentiment="positive",
        text_emotion="admiring",
        text_confidence=0.4,
    )

    run_fusion(call_id)

    conn = db.get_connection()
    try:
        segment = conn.execute(
            "SELECT * FROM TimelineSegment WHERE id = ?", (segment_id,)
        ).fetchone()
        result = db.get_analysis_result(conn, call_id=call_id)
    finally:
        conn.close()

    assert segment["disagreement_flag"] == 0
    assert result is not None
    assert result["segments_flagged_count"] == 0


def test_run_fusion_single_modality_when_no_text_signal_exists(make_call, call_row):
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=None)
    (segment_id,) = _seed_segments_with_acoustic(
        call_id,
        [{"start_time": 0.0, "end_time": 1.0, "acoustic_emotion": "happy", "acoustic_confidence": 0.7}],
    )
    # No TranscriptTurn rows at all — the transcript branch failed entirely.

    run_fusion(call_id)

    conn = db.get_connection()
    try:
        segment = conn.execute(
            "SELECT * FROM TimelineSegment WHERE id = ?", (segment_id,)
        ).fetchone()
        result = db.get_analysis_result(conn, call_id=call_id)
    finally:
        conn.close()

    assert segment["fused_emotion"] == "happy"
    assert segment["fused_sentiment"] == "positive"
    assert segment["fused_confidence"] == 0.7
    assert segment["single_modality_flag"] == 1

    assert result["single_modality_flag"] == 1
    assert result["secondary_signal_emotion"] is None
    assert result["secondary_signal_confidence"] is None

    assert call_row(call_id)["status"] == "complete"


def test_run_fusion_mixed_call_is_not_flagged_single_modality_at_call_level(make_call):
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=None)
    segment_ids = _seed_segments_with_acoustic(
        call_id,
        [
            {"start_time": 0.0, "end_time": 1.0, "acoustic_emotion": "happy", "acoustic_confidence": 0.7},
            {"start_time": 1.0, "end_time": 2.0, "acoustic_emotion": "sad", "acoustic_confidence": 0.6},
        ],
    )
    # Only the second segment gets an overlapping text signal.
    _seed_transcript_turn(
        call_id,
        turn_index=0,
        start_time=1.0,
        end_time=2.0,
        text_sentiment="negative",
        text_emotion="disappointed",
        text_confidence=0.5,
    )

    run_fusion(call_id)

    conn = db.get_connection()
    try:
        segments = {
            row["id"]: row
            for row in conn.execute(
                "SELECT * FROM TimelineSegment WHERE call_id = ?", (call_id,)
            ).fetchall()
        }
        result = db.get_analysis_result(conn, call_id=call_id)
    finally:
        conn.close()

    assert segments[segment_ids[0]]["single_modality_flag"] == 1
    assert segments[segment_ids[1]]["single_modality_flag"] == 0
    # Call-level flag reflects a genuine partial multimodal result, not a
    # wholesale single-modality Call (see Story 1.6 Dev Notes).
    assert result["single_modality_flag"] == 0


def test_run_fusion_zero_segments_completes_with_no_analysis_result(make_call, call_row):
    """Code review (2026-08-14) / user decision: a Call with zero
    TimelineSegment rows (e.g. silence/no-speech audio) is a valid outcome,
    not a failure — it completes with no AnalysisResult row at all, rather
    than tripping reduce_call([])'s ValueError and being marked "failed"."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=None)
    conn = db.get_connection()
    try:
        db.set_call_status(conn, call_id=call_id, status="processing")
    finally:
        conn.close()
    # No TimelineSegment rows seeded at all.

    run_fusion(call_id)  # must not raise

    assert call_row(call_id)["status"] == "complete"
    conn = db.get_connection()
    try:
        result = db.get_analysis_result(conn, call_id=call_id)
    finally:
        conn.close()
    assert result is None


def test_run_fusion_internal_failure_sets_status_failed_and_reraises(monkeypatch, make_call, call_row):
    """Fail-hard (unlike run_transcript/run_text_sentiment): fusion is the
    only stage that can move Call.status to complete, so an internal
    failure here must fail the Call outright rather than leaving it stuck
    at "processing" forever."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=None)
    _seed_segments_with_acoustic(
        call_id,
        [{"start_time": 0.0, "end_time": 1.0, "acoustic_emotion": "happy", "acoustic_confidence": 0.7}],
    )

    def _raise(*_args, **_kwargs):
        raise RuntimeError("boom")

    monkeypatch.setattr("app.pipeline.fusion.run.db.persist_fusion_results", _raise)

    with pytest.raises(RuntimeError):
        run_fusion(call_id)

    assert call_row(call_id)["status"] == "failed"


def test_run_fusion_real_end_to_end_chain_produces_a_complete_call(make_call, call_row, fixtures_dir):
    """Real (unmocked) full chain: run_acoustic -> run_transcript ->
    run_text_sentiment -> run_fusion, against the real speech fixture —
    complements the fast/deterministic tests above the way Story 1.5's own
    real-vs-mocked split does."""
    call_id = str(uuid.uuid4())
    make_call(call_id, audio_src=fixtures_dir / "speech.wav")

    conn = db.get_connection()
    try:
        segments = [(str(uuid.uuid4()), idx, start, end) for idx, (start, end) in enumerate([(0.0, 1.5), (1.5, 3.0)])]
        db.insert_timeline_segments(conn, call_id=call_id, segments=segments)
        db.set_call_status(conn, call_id=call_id, status="processing")
    finally:
        conn.close()

    run_acoustic(call_id)
    run_transcript(call_id)
    run_text_sentiment(call_id)
    run_fusion(call_id)

    conn = db.get_connection()
    try:
        fused_segments = conn.execute(
            "SELECT * FROM TimelineSegment WHERE call_id = ? ORDER BY segment_index", (call_id,)
        ).fetchall()
        result = db.get_analysis_result(conn, call_id=call_id)
    finally:
        conn.close()

    assert len(fused_segments) == 2
    for segment in fused_segments:
        assert segment["fused_sentiment"] in _KNOWN_POLARITIES
        assert segment["fused_emotion"]
        assert 0.0 <= segment["fused_confidence"] <= 1.0
        assert segment["single_modality_flag"] in (0, 1)
        # Story 1.9: disagreement_flag is now real, data-dependent output —
        # a real model run against real audio could legitimately produce a
        # polarity mismatch with both confidences above threshold, so a
        # hardcoded exact-value assertion here would be flaky. Same loose-
        # assertion pattern already used for single_modality_flag above.
        assert segment["disagreement_flag"] in (0, 1)

    assert result is not None
    assert result["overall_sentiment"] in _KNOWN_POLARITIES
    assert result["overall_emotion"]
    assert 0.0 <= result["overall_confidence"] <= 1.0
    assert result["segments_flagged_count"] >= 0

    assert call_row(call_id)["status"] == "complete"
