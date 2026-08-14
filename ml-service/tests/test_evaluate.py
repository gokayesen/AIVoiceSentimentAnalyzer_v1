"""Tests for the baseline-evaluation utility (Story 1.3, AC 10)."""

from __future__ import annotations

import pytest

from app.pipeline.acoustic.evaluate import majority_class_baseline_uar


def test_majority_class_baseline_uar_known_example():
    # A x4, B x2, C x2. Majority = A. recall(A)=1.0, recall(B)=0, recall(C)=0.
    # UAR = (1.0 + 0 + 0) / 3.
    labels = ["A", "A", "A", "A", "B", "B", "C", "C"]
    assert majority_class_baseline_uar(labels) == pytest.approx(1 / 3)


def test_majority_class_baseline_uar_single_class_is_perfect():
    assert majority_class_baseline_uar(["X", "X", "X"]) == pytest.approx(1.0)


def test_majority_class_baseline_uar_empty_raises():
    with pytest.raises(ValueError):
        majority_class_baseline_uar([])
