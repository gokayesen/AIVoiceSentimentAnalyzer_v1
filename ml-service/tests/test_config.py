"""Startup validation for the acoustic confidence thresholds (code review,
2026-08-13): a misconfigured ACOUSTIC_TEMPERATURE<=0 makes softmax output
NaN, and `NaN < ACOUSTIC_SANITY_FLOOR` is always False in Python — silently
bypassing the sanity-floor check entirely rather than raising. Both invariants
must fail loudly at import time instead. Run via subprocess (not a plain
`importlib.reload`) since `app.config` is already imported with valid values
by the time this test module loads, and env vars are only read once at
import time.
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


def test_non_positive_temperature_raises_at_import():
    result = _run_with_env({"ACOUSTIC_TEMPERATURE": "0"})
    assert result.returncode != 0
    assert "ACOUSTIC_TEMPERATURE" in result.stderr


def test_sanity_floor_at_or_above_low_confidence_threshold_raises_at_import():
    result = _run_with_env({"ACOUSTIC_SANITY_FLOOR": "0.5", "LOW_CONFIDENCE_THRESHOLD": "0.5"})
    assert result.returncode != 0
    assert "ACOUSTIC_SANITY_FLOOR" in result.stderr


def test_valid_config_imports_cleanly():
    result = _run_with_env({})
    assert result.returncode == 0, result.stderr


def test_disagreement_threshold_malformed_raises_at_import_naming_the_variable():
    result = _run_with_env({"DISAGREEMENT_THRESHOLD": "0.5x"})
    assert result.returncode != 0
    # Assert on the final traceback line only — Python's default traceback
    # formatting echoes the offending source line (which happens to contain
    # the identifier name) regardless of the actual exception message's
    # content (Story 1.8 Dev Agent Record: this is a documented false-positive
    # trap when asserting against the whole stderr blob instead).
    assert "DISAGREEMENT_THRESHOLD" in result.stderr.strip().splitlines()[-1]


def test_disagreement_threshold_above_one_raises_at_import():
    result = _run_with_env({"DISAGREEMENT_THRESHOLD": "1.5"})
    assert result.returncode != 0
    assert "DISAGREEMENT_THRESHOLD" in result.stderr


def test_disagreement_threshold_below_zero_raises_at_import():
    result = _run_with_env({"DISAGREEMENT_THRESHOLD": "-0.1"})
    assert result.returncode != 0
    assert "DISAGREEMENT_THRESHOLD" in result.stderr


def test_disagreement_threshold_lower_boundary_imports_cleanly():
    result = _run_with_env({"DISAGREEMENT_THRESHOLD": "0"})
    assert result.returncode == 0, result.stderr


def test_disagreement_threshold_upper_boundary_imports_cleanly():
    result = _run_with_env({"DISAGREEMENT_THRESHOLD": "1"})
    assert result.returncode == 0, result.stderr


def test_disagreement_threshold_nan_raises_at_import():
    # float("nan") parses successfully, so this must be caught by the range
    # check, not the malformed-value except block — NaN comparisons are
    # always False in IEEE754, so `0 <= nan <= 1` is False and `not (...)`
    # correctly raises (code review, 2026-08-14: this file's docstring is
    # already NaN-aware for ACOUSTIC_SANITY_FLOOR; this proves the same
    # holds for DISAGREEMENT_THRESHOLD instead of assuming it).
    result = _run_with_env({"DISAGREEMENT_THRESHOLD": "nan"})
    assert result.returncode != 0
    assert "DISAGREEMENT_THRESHOLD" in result.stderr
