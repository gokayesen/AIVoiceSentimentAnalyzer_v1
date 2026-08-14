"""Baseline evaluation utilities (AD-17, AC 8). Reuses
`majority_class_baseline_uar` from `acoustic/evaluate.py` (Story 1.3) rather
than duplicating it, and adds its single-modality-baseline sibling.

**No real fusion spot-check in this story.** Story 1.3 had a real CREMA-D
acoustic-only spot-check because a suitable public acoustic-only dataset
exists (`run_public_benchmark_spot_check`). No equivalent automatable,
license-clear, in-domain (call-center) *multimodal* dataset — paired audio,
transcript, and ground-truth Sentiment/Emotion labels — exists for MVP. AD-17
itself defers real in-domain validation to future evaluation work ("pending
in-domain validation against a small manually-annotated in-domain validation
set" — that set does not exist yet). This module therefore ships only the
reusable baseline-comparison *utilities*; running them against a real
labeled fusion dataset is future evaluation work, not this story's scope.
"""

from __future__ import annotations

from app.pipeline.acoustic.evaluate import majority_class_baseline_uar

__all__ = ["majority_class_baseline_uar", "single_modality_baseline_uar"]


def single_modality_baseline_uar(
    true_labels: list[str],
    acoustic_only_predictions: list[str],
    text_only_predictions: list[str],
) -> tuple[float, float]:
    """Returns `(acoustic_only_uar, text_only_uar)` — the per-class-averaged
    recall (UAR) each single-modality signal would achieve alone, computed
    against the same `true_labels`. AD-17 requires fusion's accuracy claim to
    clear this pair of baselines (after the majority-class baseline) before
    crediting fusion with any benefit; this function only computes the two
    numbers; the comparison/judgment itself is evaluation-time work."""
    if not true_labels:
        raise ValueError("true_labels must be non-empty")
    if len(acoustic_only_predictions) != len(true_labels) or len(text_only_predictions) != len(
        true_labels
    ):
        raise ValueError(
            "acoustic_only_predictions and text_only_predictions must be the "
            "same length as true_labels"
        )

    return (
        _uar(true_labels, acoustic_only_predictions),
        _uar(true_labels, text_only_predictions),
    )


def _uar(true_labels: list[str], predictions: list[str]) -> float:
    """Per-class-averaged recall (UAR) of `predictions` against
    `true_labels` — the same headline metric `majority_class_baseline_uar`
    reports (AD-17), computed for a real (non-majority-only) prediction set."""
    classes = sorted(set(true_labels))
    recalls = []
    for cls in classes:
        indices = [i for i, label in enumerate(true_labels) if label == cls]
        correct = sum(1 for i in indices if predictions[i] == cls)
        recalls.append(correct / len(indices))
    return sum(recalls) / len(recalls)
