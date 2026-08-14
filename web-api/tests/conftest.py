"""Pytest fixtures: isolated storage/DB per test session, and synthetic audio fixtures.

STORAGE_DIR/DB_PATH env vars must be set before `app.config` is first imported
(it reads them at module load time), so this happens at conftest module scope —
before any test module imports anything from `app`.
"""

from __future__ import annotations

import os
import subprocess
import tempfile
from pathlib import Path

_TEST_ROOT = Path(tempfile.mkdtemp(prefix="web_api_test_"))
os.environ["STORAGE_DIR"] = str(_TEST_ROOT / "storage")
os.environ["DB_PATH"] = str(_TEST_ROOT / "test.db")

import fakeredis
import pytest
from fastapi.testclient import TestClient
from rq import Queue

from app import queue as queue_module
from app.config import INGEST_QUEUE_NAME
from app.main import app


@pytest.fixture()
def fake_queue(monkeypatch):
    """A real (fake-backed) RQ Queue, not a Mock — enqueue() actually
    serializes a job into fakeredis, so tests assert against RQ's own job
    registry. `is_async` is deliberately left at its default (True/async):
    web-api's tests only need to confirm a job was *enqueued* with the right
    function reference and args — running `is_async=False` here would try to
    import and execute `app.pipeline.ingest.run.run_ingest` in-process, which
    doesn't exist in web-api's environment (that's ml-service's own module,
    tested separately in ml-service's suite, AD-7 service boundary)."""
    conn = fakeredis.FakeStrictRedis()
    q = Queue(INGEST_QUEUE_NAME, connection=conn)
    monkeypatch.setattr(queue_module, "get_queue", lambda: q)
    return q


@pytest.fixture()
def client(fake_queue):
    with TestClient(app) as c:
        yield c


@pytest.fixture(scope="session")
def ffmpeg_exe() -> str:
    import imageio_ffmpeg

    return imageio_ffmpeg.get_ffmpeg_exe()


@pytest.fixture(scope="session")
def fixtures_dir(ffmpeg_exe: str) -> Path:
    """Generate synthetic WAV/MP3/M4A audio + corrupt/oversized/over-duration files once per session."""
    d = _TEST_ROOT / "fixtures"
    d.mkdir(parents=True, exist_ok=True)

    def _encode(name: str, duration_s: int, extra_args: list[str] | None = None) -> Path:
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
            "1",
            *(extra_args or []),
            str(out),
        ]
        subprocess.run(cmd, check=True, capture_output=True)
        return out

    _encode("valid.wav", 2)
    _encode("valid.mp3", 2)
    _encode("valid.m4a", 2, ["-c:a", "aac"])
    # ~31 minutes > 30 minute (1800s) ceiling — AC3 duration case.
    _encode("over_duration.wav", 1860)

    # Real MP3-encoded content saved under a .wav extension — decodable, but
    # its content doesn't match what the extension claims.
    mp3_bytes = (d / "valid.mp3").read_bytes()
    (d / "mismatched_extension.wav").write_bytes(mp3_bytes)

    for name in ("corrupt.wav", "corrupt.mp3", "corrupt.m4a"):
        (d / name).write_bytes(b"not a real audio file" * 20)

    (d / "unsupported.ogg").write_bytes(b"OggS" + b"\x00" * 100)

    # Oversized: a valid small WAV padded past the 200MB ceiling. Size rejection
    # happens before any decode attempt, so the padding need not stay decodable.
    small = _encode("_seed_for_oversized.wav", 1)
    oversized = d / "oversized.wav"
    oversized.write_bytes(small.read_bytes())
    target_size = 200 * 1024 * 1024 + 1024
    with oversized.open("ab") as f:
        remaining = target_size - oversized.stat().st_size
        f.write(b"\x00" * remaining)

    return d
