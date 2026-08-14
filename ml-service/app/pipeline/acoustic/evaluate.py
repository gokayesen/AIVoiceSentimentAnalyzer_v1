"""Baseline evaluation (AD-17, AC 10). `majority_class_baseline_uar` is a
fast, dependency-free utility used both by tests and by the CREMA-D
spot-check below. `run_public_benchmark_spot_check` is a deliberately
**manual, CLI-only** operation (`python -m app.pipeline.acoustic.evaluate`)
— it does real network I/O and model inference, so it stays out of the
default `pytest` suite (AD-21's "independently-runnable" tests must not
depend on network access).

IEMOCAP is never used here — it requires a signed USC SAIL release and is
non-commercially licensed, so it is not automatable (Technical Research
§7.1/§7.4). CREMA-D is different: ODbL 1.0 + DbCL 1.0, open, share-alike,
commercial use permitted, no signed release required. Only the canonical
source (github.com/CheyneyComputerScience/CREMA-D) is used — not an
unofficial third-party mirror, whose license fidelity to the canonical
ODbL/DbCL terms is unverified.
"""

from __future__ import annotations

import subprocess
import tempfile
from collections import Counter
from pathlib import Path


def majority_class_baseline_uar(labels: list[str]) -> float:
    """Predicts the most frequent label always; returns the resulting
    per-class-averaged recall (UAR) — near-zero-informative by construction
    (1/num_classes when exactly one class is ever predicted), the floor any
    real evaluation must clear (AD-17/Technical Research §8.4)."""
    if not labels:
        raise ValueError("labels must be non-empty")
    counts = Counter(labels)
    majority_class, _ = counts.most_common(1)[0]
    recalls = []
    for cls, true_count in counts.items():
        correct = true_count if cls == majority_class else 0
        recalls.append(correct / true_count)
    return sum(recalls) / len(recalls)


# One clip per emotion code, all from the same actor/sentence/intensity-level
# combination, so the sample is deterministic and small (4 files). Only the
# 4 codes our classifier's taxonomy actually models are used (NEU/HAP/SAD/
# ANG) — CREMA-D's FEA (fearful) and DIS (disgust) codes have no matching
# category in this system's coarse 4-class taxonomy (see taxonomy.py) and
# would be structurally unanswerable (the classifier can never predict a
# category it doesn't have), which would depress the accuracy number for
# taxonomy-coverage reasons unrelated to model quality — excluded rather
# than silently scored as wrong.
_CREMA_D_ACTOR_ID = "1001"
_CREMA_D_SENTENCE = "DFA"  # "Don't forget a jacket" — recorded at a single
# ("XX", unspecified) intensity level for every actor/emotion; unlike "IEO"
# (only recorded at HI/MD/LO), verified empirically against the real repo.
_CREMA_D_LEVEL = "XX"
_CREMA_D_EMOTION_CODES = ["NEU", "HAP", "SAD", "ANG"]

_CREMA_D_CODE_TO_EMOTION = {
    "NEU": "neutral",
    "HAP": "happy",
    "SAD": "sad",
    "ANG": "angry",
}


def _clip_paths(repo_dir: Path) -> list[tuple[Path, str]]:
    return [
        (
            repo_dir / "AudioWAV" / f"{_CREMA_D_ACTOR_ID}_{_CREMA_D_SENTENCE}_{code}_{_CREMA_D_LEVEL}.wav",
            code,
        )
        for code in _CREMA_D_EMOTION_CODES
    ]


def _fetch_crema_d_sample(dest_dir: Path) -> list[tuple[Path, str]]:
    """Sparse/shallow-clones the canonical CREMA-D repo and returns
    [(clip_path, emotion_code), ...]. The repo's `.wav` files are Git-LFS
    tracked (verified empirically — `.gitattributes` marks `*.wav`), so a
    plain sparse checkout yields small LFS pointer-stub text files, not real
    audio; `git lfs pull` is run automatically to materialize the real
    bytes. Raises FileNotFoundError with a clear remediation hint if a clip
    is still missing/undersized after that (e.g. `git-lfs` not installed)."""
    repo_dir = dest_dir / "CREMA-D"
    if not repo_dir.exists():
        subprocess.run(
            [
                "git",
                "clone",
                "--depth",
                "1",
                "--filter=blob:none",
                "--sparse",
                "https://github.com/CheyneyComputerScience/CREMA-D.git",
                str(repo_dir),
            ],
            check=True,
        )
        subprocess.run(
            ["git", "-C", str(repo_dir), "sparse-checkout", "set", "AudioWAV"], check=True
        )

    paths = _clip_paths(repo_dir)
    if any(not p.exists() or p.stat().st_size < 1024 for p, _code in paths):
        subprocess.run(
            ["git", "-C", str(repo_dir), "lfs", "pull", "--include=AudioWAV/*"], check=True
        )

    files = []
    for path, code in paths:
        if not path.exists() or path.stat().st_size < 1024:
            raise FileNotFoundError(
                f"expected CREMA-D clip missing or suspiciously small even after "
                f"`git lfs pull`: {path}. Verify `git-lfs` is installed, or that the "
                f"actor/sentence/level combination above is still present upstream."
            )
        files.append((path, code))
    return files


def run_public_benchmark_spot_check(dest_dir: Path | None = None) -> None:
    import torchaudio

    from app.pipeline.acoustic.classifier import classify_segment
    from app.pipeline.acoustic.taxonomy import raw_label_to_emotion
    from app.pipeline.ingest.vad import VAD_SAMPLE_RATE

    dest_dir = dest_dir or Path(tempfile.mkdtemp(prefix="crema_d_spot_check_"))
    samples = _fetch_crema_d_sample(dest_dir)

    true_emotions = []
    predicted_emotions = []
    for path, code in samples:
        waveform, sr = torchaudio.load(str(path))
        mono = waveform.mean(dim=0)
        if sr != VAD_SAMPLE_RATE:
            mono = torchaudio.functional.resample(mono, orig_freq=sr, new_freq=VAD_SAMPLE_RATE)
        raw_label, _confidence = classify_segment(mono.numpy(), VAD_SAMPLE_RATE)
        predicted_emotions.append(raw_label_to_emotion(raw_label))
        true_emotions.append(_CREMA_D_CODE_TO_EMOTION[code])

    baseline_uar = majority_class_baseline_uar(true_emotions)
    correct = sum(1 for t, p in zip(true_emotions, predicted_emotions, strict=True) if t == p)
    accuracy = correct / len(true_emotions)

    print(
        f"CREMA-D spot-check (n={len(true_emotions)}) — public-benchmark, "
        f"acted/non-call-center-domain: OPTIMISTIC UPPER BOUND, not validated "
        f"in-domain (AD-17)."
    )
    print(f"  majority-class baseline UAR: {baseline_uar:.3f}")
    print(f"  classifier accuracy on this sample: {accuracy:.3f}")


if __name__ == "__main__":
    run_public_benchmark_spot_check()
