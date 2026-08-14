"""Tests for the fusion baseline-evaluation utilities (Story 1.6, AC 8, 9)."""

from __future__ import annotations

import pytest

from app.pipeline.fusion.evaluate import single_modality_baseline_uar


def test_single_modality_baseline_uar_perfect_predictions_score_one():
    true_labels = ["positive", "positive", "negative", "negative"]
    acoustic_uar, text_uar = single_modality_baseline_uar(
        true_labels,
        acoustic_only_predictions=true_labels,
        text_only_predictions=true_labels,
    )
    assert acoustic_uar == pytest.approx(1.0)
    assert text_uar == pytest.approx(1.0)


def test_single_modality_baseline_uar_computes_per_class_averaged_recall():
    true_labels = ["positive", "positive", "negative", "negative"]
    # Acoustic-only: gets both "positive" right, both "negative" wrong.
    acoustic_predictions = ["positive", "positive", "positive", "positive"]
    # Text-only: gets everything right.
    text_predictions = true_labels

    acoustic_uar, text_uar = single_modality_baseline_uar(
        true_labels,
        acoustic_only_predictions=acoustic_predictions,
        text_only_predictions=text_predictions,
    )
    # UAR = mean(recall per class) = mean(1.0, 0.0) = 0.5
    assert acoustic_uar == pytest.approx(0.5)
    assert text_uar == pytest.approx(1.0)


def test_single_modality_baseline_uar_raises_on_empty_true_labels():
    with pytest.raises(ValueError):
        single_modality_baseline_uar([], acoustic_only_predictions=[], text_only_predictions=[])


def test_single_modality_baseline_uar_raises_on_mismatched_lengths():
    with pytest.raises(ValueError):
        single_modality_baseline_uar(
            ["positive", "negative"],
            acoustic_only_predictions=["positive"],
            text_only_predictions=["positive", "negative"],
        )
