"""Pytest fixtures: isolated storage/DB per test session, and audio fixtures.

STORAGE_DIR/DB_PATH env vars must be set before `app.config` is first imported
(it reads them at module load time), so this happens at conftest module scope
— before any test module imports anything from `app`. Same pattern as
web-api/tests/conftest.py.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
import urllib.request
from pathlib import Path

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="ml_service_test_"))
os.environ["STORAGE_DIR"] = str(_TEST_ROOT / "storage")
os.environ["DB_PATH"] = str(_TEST_ROOT / "test.db")

import fakeredis
import pytest
from rq import Queue

from app import config, db
from app.config import STORAGE_DIR


@pytest.fixture(scope="session", autouse=True)
def _init_db():
    db.init_db()


@pytest.fixture(autouse=True)
def fake_acoustic_queue(monkeypatch):
    """run_ingest (Story 1.3) unconditionally enqueues onto the acoustic
    queue on success — without this, every ingest test would try to reach a
    real Redis server (none exists in this sandbox/CI, per AD-21). Mirrors
    web-api/tests/conftest.py's `fake_queue` fixture. `is_async=True`
    (default) so enqueuing is exercised without actually executing
    run_acoustic as a side effect of unrelated ingest tests."""
    import app.queue as queue_module

    fake_queue = Queue(config.ACOUSTIC_QUEUE_NAME, connection=fakeredis.FakeStrictRedis())
    monkeypatch.setattr(queue_module, "get_acoustic_queue", lambda: fake_queue)
    return fake_queue


@pytest.fixture(autouse=True)
def fake_transcript_queue(monkeypatch):
    """Story 1.4: run_acoustic unconditionally enqueues onto the transcript
    queue on success — same rationale as fake_acoustic_queue above, now one
    stage further down the chain."""
    import app.queue as queue_module

    fake_queue = Queue(config.TRANSCRIPT_QUEUE_NAME, connection=fakeredis.FakeStrictRedis())
    monkeypatch.setattr(queue_module, "get_transcript_queue", lambda: fake_queue)
    return fake_queue


@pytest.fixture(autouse=True)
def fake_text_sentiment_queue(monkeypatch):
    """Story 1.5: run_transcript unconditionally enqueues onto the
    text-sentiment queue on success — same rationale as
    fake_acoustic_queue/fake_transcript_queue above, now one stage further
    down the chain."""
    import app.queue as queue_module

    fake_queue = Queue(config.TEXT_SENTIMENT_QUEUE_NAME, connection=fakeredis.FakeStrictRedis())
    monkeypatch.setattr(queue_module, "get_text_sentiment_queue", lambda: fake_queue)
    return fake_queue


@pytest.fixture(autouse=True)
def fake_fusion_queue(monkeypatch):
    """Story 1.6: run_text_sentiment (and several earlier-stage failure
    paths, see fusion/run.py's module docstring) unconditionally enqueues
    onto the fusion queue — same rationale as the fake queue fixtures
    above, now the final stage of the chain."""
    import app.queue as queue_module

    fake_queue = Queue(config.FUSION_QUEUE_NAME, connection=fakeredis.FakeStrictRedis())
    monkeypatch.setattr(queue_module, "get_fusion_queue", lambda: fake_queue)
    return fake_queue


@pytest.fixture(scope="session")
def ffmpeg_exe() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


@pytest.fixture(scope="session")
def fixtures_dir(ffmpeg_exe: str) -> Path:
    """Synthetic sine-tone WAVs (mono/stereo, for channel-count checks) plus
    Silero VAD's own official example speech recording (downloaded once —
    needed because VAD is a neural speech detector: a synthesized sine tone
    is decodable audio but not speech-like, so it correctly yields zero VAD
    segments, which is useless for verifying segment *persistence*)."""
    d = _TEST_ROOT / "audio_fixtures"
    d.mkdir(parents=True, exist_ok=True)

    def _encode(name: str, duration_s: int, channels: int) -> Path:
        out = d / name
        cmd = [
            ffmpeg_exe,
            "-y",
            "-f",
            "lavfi",
            "-i",
            f"sine=frequency=440:duration={duration_s}",
            "-ar",
            "16000",
            "-ac",
            str(channels),
            str(out),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return out

    _encode("mono.wav", 3, 1)
    _encode("stereo.wav", 3, 2)

    def _encode_channel_dominant(name: str, duration_s: int, *, loud_channel: int) -> Path:
        """Story 3.1: unlike `stereo.wav` above (identical sine tone
        duplicated onto both channels via `-ac 2` — every per-channel energy
        comparison on it is a tie, useless for proving correct channel
        selection), this produces a genuinely asymmetric stereo file: a
        full-amplitude tone on `loud_channel` (0 or 1), silence on the
        other — via ffmpeg's `join` filter, which places each input stream
        onto its own output channel in argument order."""
        out = d / name
        tone = f"sine=frequency=440:duration={duration_s}"
        silence = f"anullsrc=r=16000:cl=mono:d={duration_s}"
        inputs = [tone, silence] if loud_channel == 0 else [silence, tone]
        cmd = [
            ffmpeg_exe,
            "-y",
            "-f",
            "lavfi",
            "-i",
            inputs[0],
            "-f",
            "lavfi",
            "-i",
            inputs[1],
            "-filter_complex",
            "[0:a][1:a]join=inputs=2:channel_layout=stereo[a]",
            "-map",
            "[a]",
            "-ar",
            "16000",
            str(out),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return out

    _encode_channel_dominant("stereo_channel0_louder.wav", 3, loud_channel=0)
    _encode_channel_dominant("stereo_channel1_louder.wav", 3, loud_channel=1)

    def _encode_silence(name: str, duration_s: int) -> Path:
        out = d / name
        cmd = [
            ffmpeg_exe,
            "-y",
            "-f",
            "lavfi",
            "-i",
            "anullsrc=r=16000:cl=mono",
            "-t",
            str(duration_s),
            str(out),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return out

    _encode_silence("silence.wav", 2)

    speech = d / "speech.wav"
    urllib.request.urlretrieve("https://models.silero.ai/vad_models/en.wav", speech)

    return d


def _insert_queued_call(call_id: str) -> None:
    conn = db.get_connection()
    try:
        conn.execute(
            """
            INSERT INTO Call (id, status, filename, format, duration_seconds, size_bytes, created_at)
            VALUES (?, 'queued', 'test.wav', 'wav', 3.0, 1000, '2026-08-12T00:00:00Z')
            """,
            (call_id,),
        )
        conn.commit()
    finally:
        conn.close()


@pytest.fixture()
def make_call():
    """Returns a function(call_id, audio_src=Path|None) that inserts a
    `queued` Call row and, if given a source file, copies it to
    storage/{call_id}/original.wav — mirroring what web-api's upload
    endpoint would have already done before this job ever runs."""

    def _make(call_id: str, *, audio_src: Path | None) -> None:
        call_dir = STORAGE_DIR / call_id
        call_dir.mkdir(parents=True, exist_ok=True)
        if audio_src is not None:
            (call_dir / "original.wav").write_bytes(audio_src.read_bytes())
        _insert_queued_call(call_id)

    return _make


@pytest.fixture()
def call_row():
    def _fetch(call_id: str):
        conn = db.get_connection()
        try:
            return conn.execute("SELECT * FROM Call WHERE id = ?", (call_id,)).fetchone()
        finally:
            conn.close()

    return _fetch


@pytest.fixture()
def timeline_segments():
    def _fetch(call_id: str):
        conn = db.get_connection()
        try:
            return conn.execute(
                "SELECT id, segment_index, start_time, end_time, acoustic_emotion, acoustic_confidence "
                "FROM TimelineSegment WHERE call_id = ? ORDER BY segment_index",
                (call_id,),
            ).fetchall()
        finally:
            conn.close()

    return _fetch


@pytest.fixture()
def acoustic_evidence_rows():
    """Fetches AcousticEvidence rows for a call via a join through
    TimelineSegment (AcousticEvidence itself has no call_id column, by
    design — see db.py's schema comment)."""

    def _fetch(call_id: str):
        conn = db.get_connection()
        try:
            return conn.execute(
                """
                SELECT ae.* FROM AcousticEvidence ae
                JOIN TimelineSegment ts ON ts.id = ae.segment_id
                WHERE ts.call_id = ?
                ORDER BY ts.segment_index
                """,
                (call_id,),
            ).fetchall()
        finally:
            conn.close()

    return _fetch
