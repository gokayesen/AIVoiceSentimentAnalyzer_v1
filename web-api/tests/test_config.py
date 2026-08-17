"""Startup validation for `LOW_CONFIDENCE_THRESHOLD` (Story 1.8, AC3/AC4).

Mirrors `ml-service/tests/test_config.py`'s subprocess-based import-time
pattern exactly: env vars are only read once at `app.config` import time, and
`app.config` is already imported (with valid values) by the time any other
test module in this session loads — a plain `importlib.reload` would not
reliably re-trigger the validation the same way a fresh subprocess does.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

_APP_ROOT = Path(__file__).resolve().parent.parent


def _run_with_env(extra_env: dict[str, str]) -> subprocess.CompletedProcess:
    env = {**os.environ, **extra_env}
    return subprocess.run(
        [sys.executable, "-c", "import app.config"],
        cwd=_APP_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )


def test_low_confidence_threshold_above_one_raises_at_import():
    result = _run_with_env({"LOW_CONFIDENCE_THRESHOLD": "1.5"})
    assert result.returncode != 0
    assert "LOW_CONFIDENCE_THRESHOLD" in result.stderr


def test_low_confidence_threshold_below_zero_raises_at_import():
    result = _run_with_env({"LOW_CONFIDENCE_THRESHOLD": "-0.1"})
    assert result.returncode != 0
    assert "LOW_CONFIDENCE_THRESHOLD" in result.stderr


def test_low_confidence_threshold_malformed_raises_at_import_naming_the_variable():
    """Code review (2026-08-14): a non-numeric value (an operator typo, the
    most likely real-world mistake) must fail with a message naming
    LOW_CONFIDENCE_THRESHOLD, not Python's raw, unlabeled float() ValueError.
    Asserts on only the final traceback line (the actual exception message)
    — the full stderr blob is not a valid check here, since Python's default
    traceback formatting always echoes the offending source line, which
    would trivially contain the identifier regardless of the exception's own
    message."""
    result = _run_with_env({"LOW_CONFIDENCE_THRESHOLD": "0.5x"})
    assert result.returncode != 0
    final_line = result.stderr.strip().splitlines()[-1]
    assert "LOW_CONFIDENCE_THRESHOLD" in final_line


def test_low_confidence_threshold_lower_boundary_imports_cleanly():
    """Code review (2026-08-14): the range check is inclusive (`0 <= x <= 1`)
    — the boundary value itself must be accepted, not just clearly-out-of-
    range values."""
    result = _run_with_env({"LOW_CONFIDENCE_THRESHOLD": "0"})
    assert result.returncode == 0, result.stderr


def test_low_confidence_threshold_upper_boundary_imports_cleanly():
    result = _run_with_env({"LOW_CONFIDENCE_THRESHOLD": "1"})
    assert result.returncode == 0, result.stderr


def test_valid_config_imports_cleanly():
    """Code review (2026-08-14): LOW_CONFIDENCE_THRESHOLD is pinned explicitly
    (not left to whatever the parent test process's ambient environment
    happens to contain) so this test's pass/fail is deterministic and
    independent of the runner's shell/CI environment."""
    result = _run_with_env({"LOW_CONFIDENCE_THRESHOLD": "0.5"})
    assert result.returncode == 0, result.stderr


# Story 1.10 (AD-12): DELETE_AWAIT_TIMEOUT_SECONDS / DELETE_AWAIT_POLL_INTERVAL_SECONDS.
# Both are plain positive wall-clock seconds (not [0, 1]-bounded domain
# thresholds), so "invalid" here means malformed or <= 0, not out-of-range.


def test_delete_await_timeout_malformed_raises_at_import_naming_the_variable():
    result = _run_with_env({"DELETE_AWAIT_TIMEOUT_SECONDS": "10x"})
    assert result.returncode != 0
    final_line = result.stderr.strip().splitlines()[-1]
    assert "DELETE_AWAIT_TIMEOUT_SECONDS" in final_line


def test_delete_await_timeout_zero_raises_at_import():
    result = _run_with_env({"DELETE_AWAIT_TIMEOUT_SECONDS": "0"})
    assert result.returncode != 0
    assert "DELETE_AWAIT_TIMEOUT_SECONDS" in result.stderr


def test_delete_await_timeout_negative_raises_at_import():
    result = _run_with_env({"DELETE_AWAIT_TIMEOUT_SECONDS": "-1"})
    assert result.returncode != 0
    assert "DELETE_AWAIT_TIMEOUT_SECONDS" in result.stderr


def test_delete_await_timeout_valid_imports_cleanly():
    result = _run_with_env({"DELETE_AWAIT_TIMEOUT_SECONDS": "5"})
    assert result.returncode == 0, result.stderr


def test_delete_await_poll_interval_malformed_raises_at_import_naming_the_variable():
    result = _run_with_env({"DELETE_AWAIT_POLL_INTERVAL_SECONDS": "0.2x"})
    assert result.returncode != 0
    final_line = result.stderr.strip().splitlines()[-1]
    assert "DELETE_AWAIT_POLL_INTERVAL_SECONDS" in final_line


def test_delete_await_poll_interval_zero_raises_at_import():
    result = _run_with_env({"DELETE_AWAIT_POLL_INTERVAL_SECONDS": "0"})
    assert result.returncode != 0
    assert "DELETE_AWAIT_POLL_INTERVAL_SECONDS" in result.stderr


def test_delete_await_poll_interval_negative_raises_at_import():
    result = _run_with_env({"DELETE_AWAIT_POLL_INTERVAL_SECONDS": "-0.1"})
    assert result.returncode != 0
    assert "DELETE_AWAIT_POLL_INTERVAL_SECONDS" in result.stderr


def test_delete_await_poll_interval_valid_imports_cleanly():
    result = _run_with_env({"DELETE_AWAIT_POLL_INTERVAL_SECONDS": "0.1"})
    assert result.returncode == 0, result.stderr


# Story 3.3 (AC6, AD-10): SPEAKER_UNCERTAIN_THRESHOLD — a [0, 1]-bounded
# domain threshold, same validation shape as LOW_CONFIDENCE_THRESHOLD above,
# but a fully independent variable (never conflated with the Sentiment/
# Emotion confidence axis).


def test_speaker_uncertain_threshold_above_one_raises_at_import():
    result = _run_with_env({"SPEAKER_UNCERTAIN_THRESHOLD": "1.5"})
    assert result.returncode != 0
    assert "SPEAKER_UNCERTAIN_THRESHOLD" in result.stderr


def test_speaker_uncertain_threshold_below_zero_raises_at_import():
    result = _run_with_env({"SPEAKER_UNCERTAIN_THRESHOLD": "-0.1"})
    assert result.returncode != 0
    assert "SPEAKER_UNCERTAIN_THRESHOLD" in result.stderr


def test_speaker_uncertain_threshold_malformed_raises_at_import_naming_the_variable():
    result = _run_with_env({"SPEAKER_UNCERTAIN_THRESHOLD": "0.5x"})
    assert result.returncode != 0
    final_line = result.stderr.strip().splitlines()[-1]
    assert "SPEAKER_UNCERTAIN_THRESHOLD" in final_line


def test_speaker_uncertain_threshold_lower_boundary_imports_cleanly():
    result = _run_with_env({"SPEAKER_UNCERTAIN_THRESHOLD": "0"})
    assert result.returncode == 0, result.stderr


def test_speaker_uncertain_threshold_upper_boundary_imports_cleanly():
    result = _run_with_env({"SPEAKER_UNCERTAIN_THRESHOLD": "1"})
    assert result.returncode == 0, result.stderr


def test_speaker_uncertain_threshold_is_independent_of_low_confidence_threshold():
    """Code review (2026-08-17, AD-10): the two confidence-axis thresholds
    must never be aliased or accidentally coupled — set both env vars to
    different values simultaneously and confirm each parsed variable holds
    its own distinct value, not the other's."""
    env = {**os.environ, "LOW_CONFIDENCE_THRESHOLD": "0.3", "SPEAKER_UNCERTAIN_THRESHOLD": "0.7"}
    result = subprocess.run(
        [sys.executable, "-c", "import app.config as c; print(c.LOW_CONFIDENCE_THRESHOLD, c.SPEAKER_UNCERTAIN_THRESHOLD)"],
        cwd=_APP_ROOT,
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    low_confidence, speaker_uncertain = result.stdout.split()
    assert float(low_confidence) == 0.3
    assert float(speaker_uncertain) == 0.7
