"""Shared config for the ml-service RQ worker. Mirrors web-api/app/config.py's
env-var-with-local-fallback pattern (AD-12: shared SQLite file + filesystem
volume, never a shared Python import)."""

import os
from pathlib import Path

# AD-12: session-scoped filesystem storage for uploaded audio + intermediate
# artifacts — same volume web-api writes uploads into.
STORAGE_DIR = Path(os.environ.get("STORAGE_DIR", Path(__file__).resolve().parents[2] / "storage"))

# SQLite: same file web-api's Call table lives in (AD-12).
DB_PATH = Path(os.environ.get("DB_PATH", STORAGE_DIR / "app.db"))

# AD-13: RQ + Redis job queue. Default matches docker-compose's `redis` service.
REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

# Queue name shared between web-api's enqueue call and this worker.
INGEST_QUEUE_NAME = "ingest"

# Story 1.3: intra-service stage-chaining queue — run_ingest enqueues onto
# this queue on success; the same Worker process consumes both (AD-7).
ACOUSTIC_QUEUE_NAME = "acoustic"

# Story 1.4: intra-service stage-chaining queue — run_acoustic enqueues onto
# this queue on success; the same Worker process consumes all three (AD-7).
TRANSCRIPT_QUEUE_NAME = "transcript"

# Story 1.5: intra-service stage-chaining queue — run_transcript enqueues
# onto this queue on success; the same Worker process consumes all four
# stages (AD-7).
TEXT_SENTIMENT_QUEUE_NAME = "text_sentiment"

# Story 1.6: fusion's trigger queue. Unlike every previous stage, this queue
# is enqueued onto from five different call sites (not a single linear
# predecessor) — see fusion/run.py's module docstring for the fan-in
# rationale (AD-1: fusion must run whenever acoustic succeeded, regardless
# of where/whether the transcript branch completed). The same Worker
# process consumes all five stages (AD-7).
FUSION_QUEUE_NAME = "fusion"

# AD-3: dev-agent model decision (not an Architecture mandate) — see story
# 1-3's Dev Agent Record for the full rationale (apache-2.0, empirically
# verified to load its classifier head correctly under the pinned
# transformers version — a real alternative did not, see Debug Log).
ACOUSTIC_MODEL_NAME = os.environ.get("ACOUSTIC_MODEL_NAME", "superb/wav2vec2-base-superb-er")

# AD-9: temperature-scaling calibration. 1.0 is an honest no-op placeholder —
# real calibration against a held-out set is future evaluation work (AD-17);
# a value >1 here would silently bias confidence downward before any real
# calibration has been fitted, which is worse than an honest no-op.
ACOUSTIC_TEMPERATURE = float(os.environ.get("ACOUSTIC_TEMPERATURE", "1.0"))

# AD-1/AC7: two distinct, differently-owned thresholds — never conflate them.
# `ACOUSTIC_SANITY_FLOOR` (this story): below this, a result is invalid/
# degenerate and fails the whole Call outright.
# `LOW_CONFIDENCE_THRESHOLD` (Story 1.8, not consumed by any code in this
# story): at/above the sanity floor but below this, a result is valid and
# retained, just flagged as low-confidence downstream.
# Required ordering: ACOUSTIC_SANITY_FLOOR < LOW_CONFIDENCE_THRESHOLD.
# Both are placeholders pending real evaluation (AD-17) — not tuned values.
ACOUSTIC_SANITY_FLOOR = float(os.environ.get("ACOUSTIC_SANITY_FLOOR", "0.15"))
LOW_CONFIDENCE_THRESHOLD = float(os.environ.get("LOW_CONFIDENCE_THRESHOLD", "0.5"))

# Story 1.9 (AD-8, AC1/AC2): a third, independently-configured threshold,
# distinct from both thresholds above and never interchangeable with them —
# a segment is flagged as cross-modal disagreement only when the acoustic and
# text polarities differ AND both raw per-modality confidences individually
# exceed this value (see fusion/fuse.py's fuse_segment). Unlike
# LOW_CONFIDENCE_THRESHOLD above (still unconsumed by any ml-service pipeline
# code), this one is actually consumed here, so its parse is wrapped for a
# clear error message naming the variable on a malformed value.
_disagreement_threshold_raw = os.environ.get("DISAGREEMENT_THRESHOLD", "0.5")
try:
    DISAGREEMENT_THRESHOLD = float(_disagreement_threshold_raw)
except ValueError as exc:
    raise ValueError(
        f"DISAGREEMENT_THRESHOLD must be a float, got {_disagreement_threshold_raw!r}"
    ) from exc
if not 0 <= DISAGREEMENT_THRESHOLD <= 1:
    raise ValueError(
        f"DISAGREEMENT_THRESHOLD must be in [0, 1], got {DISAGREEMENT_THRESHOLD}"
    )
# Code review (2026-08-14): both ends of this otherwise-valid [0, 1] range are
# degenerate operator configurations, not rejected here since the spec places
# no stronger bound and this file's existing threshold checks (e.g.
# ACOUSTIC_SANITY_FLOOR) don't second-guess extreme-but-valid values either.
# == 1 makes the disagreement flag structurally unreachable (fuse.py's check
# is strict `>`, and no calibrated confidence exceeds 1). == 0 degenerates the
# check to a bare polarity mismatch, since virtually any nonzero confidence
# "exceeds" it.

# Fixed outside any story's scope (2026-08-18, real-world bug report): RQ's
# own class-level default (`Queue.DEFAULT_TIMEOUT = 180`, rq/queue.py) is too
# low specifically for the acoustic stage — `run_acoustic` classifies every
# VAD-bounded segment sequentially with a CPU wav2vec2 forward pass (Story
# 1.3), so total job duration scales with segment *count*, not just Call
# duration; a pause-heavy 6-minute call reproduced 147 segments and blew the
# 180s default just as reliably as a 10.8-minute one did. 900s (5x the
# default) is a deliberately generous empirical margin, not a tuned value —
# chosen to comfortably clear the worst segment-count case observed so far
# on this project's CPU-only target (AD-18) without masking a real hang
# indefinitely. This raises this ONE job's timeout only (passed explicitly
# to its `enqueue()` call) — RQ's global/other-queues' default stays 180s.
# Does not fix the underlying slow-CPU-inference cause (see deferred-work.md
# for that side of it); revisit if a Call is ever observed needing >900s.
ACOUSTIC_JOB_TIMEOUT_SECONDS = int(os.environ.get("ACOUSTIC_JOB_TIMEOUT_SECONDS", "900"))

# AD-5: STT engine is locked to faster-whisper; only the model *size* is a
# dev-agent decision (see story 1-4's Dev Agent Record for rationale) — "base"
# is a reasonable CPU int8 accuracy/speed starting point for a batch pipeline
# with no sub-second-latency requirement (AD-18, PRD).
WHISPER_MODEL_SIZE = os.environ.get("WHISPER_MODEL_SIZE", "base")
# AD-18: CPU-only baseline — int8 quantization keeps CPU inference viable.
WHISPER_COMPUTE_TYPE = os.environ.get("WHISPER_COMPUTE_TYPE", "int8")
WHISPER_DEVICE = os.environ.get("WHISPER_DEVICE", "cpu")

# Fixed outside any story's scope (2026-08-18, same real-world bug report as
# ACOUSTIC_JOB_TIMEOUT_SECONDS above, discovered immediately after that fix
# shipped): `run_transcript` has the identical shape — `transcribe_segment`
# runs faster-whisper's beam-search decode sequentially per VAD-bounded
# segment (Story 1.4), so this job's total duration also scales with segment
# *count*, and it was still bare-enqueued with no `job_timeout` override, so
# it inherited the same RQ 180s class default and died the same way (worked
# in acoustic's 244-segment Call, immediately died in transcript for that
# same Call). Sized by the same method as ACOUSTIC_JOB_TIMEOUT_SECONDS
# (measured real per-segment rate x a segment-count headroom factor over the
# largest segment count observed on this project to date), NOT copied from
# it verbatim — faster-whisper's beam-search decode is measurably slower and
# more variable per segment than wav2vec2's single forward pass. Benchmarked
# directly against this project's own model/hardware (`transcribe_segment`,
# real speech audio, 3-sample spot check): 5.39s-6.28s per ~2.5-4s
# context-padded segment (~6.3s/segment worst case). 244 segments is the
# largest segment count observed on this project to date (this same bug
# report's own reproduction call) — using the same ~1.6x segment-count
# headroom acoustic's 900s implies over its own 244-segment worst case
# (900s / ~2.3s measured-worst-case-rate ~= 391 segments ~= 1.6x), headroom
# target here is ~390 segments x 6.3s/segment ~= 2460s, rounded up to 2700s
# (45 min) for a clean number and slightly more slack given this stage's
# higher per-segment variance. Still an empirical safety margin, not a
# tuned/measured ceiling — like the acoustic fix, this raises the timeout
# ceiling only; it does not make per-segment decoding any faster. Revisit
# (both this and ACOUSTIC_JOB_TIMEOUT_SECONDS) if a Call is ever observed
# needing more, or once real batching/latency work is prioritized (see
# deferred-work.md's "No batching in run_text_sentiment" entry, Story 1.5
# review, for the same class of gap already flagged one stage over).
TRANSCRIPT_JOB_TIMEOUT_SECONDS = int(os.environ.get("TRANSCRIPT_JOB_TIMEOUT_SECONDS", "2700"))

# Story 1.5 (AD-19): dev-agent model decision, not an Architecture mandate —
# RoBERTa-base fine-tuned on GoEmotions (28-class, MIT-licensed). The
# originally-considered `j-hartmann/emotion-english-distilroberta-base`
# (7-class Ekman-style) was rejected during implementation: its model card
# states no license at all (not merely ambiguous, like WhisperX's BSD-2-vs-
# BSD-4 note — an unstated license grants no usage permission), which this
# project's own AD-3 precedent (rejecting openSMILE/Praat over license
# concerns) treats as disqualifying. `SamLowe/roberta-base-go_emotions` has
# a clear MIT license, verified at implementation time (see story 1-5's Dev
# Agent Record for the full rationale, same empirical-verification
# discipline as story 1-3's classifier).
TEXT_SENTIMENT_MODEL_NAME = os.environ.get(
    "TEXT_SENTIMENT_MODEL_NAME", "SamLowe/roberta-base-go_emotions"
)

# AD-9: temperature-scaling calibration for the text-sentiment classifier,
# mirrors ACOUSTIC_TEMPERATURE exactly — 1.0 is an honest no-op placeholder,
# real calibration is future evaluation work (AD-17).
TEXT_SENTIMENT_TEMPERATURE = float(os.environ.get("TEXT_SENTIMENT_TEMPERATURE", "1.0"))

if ACOUSTIC_TEMPERATURE <= 0:
    raise ValueError(f"ACOUSTIC_TEMPERATURE must be > 0, got {ACOUSTIC_TEMPERATURE}")
if not ACOUSTIC_SANITY_FLOOR < LOW_CONFIDENCE_THRESHOLD:
    raise ValueError(
        f"ACOUSTIC_SANITY_FLOOR ({ACOUSTIC_SANITY_FLOOR}) must be < "
        f"LOW_CONFIDENCE_THRESHOLD ({LOW_CONFIDENCE_THRESHOLD})"
    )
if TEXT_SENTIMENT_TEMPERATURE <= 0:
    raise ValueError(f"TEXT_SENTIMENT_TEMPERATURE must be > 0, got {TEXT_SENTIMENT_TEMPERATURE}")

# Story 3.2 (AD-6): pyannote's Community-1 diarization pipeline is HF-gated —
# downloading its weights requires a Hugging Face access token for an account
# that has accepted the model's usage conditions. No default: unset (None) is
# valid at import time (unlike the thresholds above) because a missing/invalid
# token must surface as this story's own per-Call diarization failure
# (run_transcript's try/except around the whole diarization step), never a
# whole-service startup crash.
HF_TOKEN = os.environ.get("HF_TOKEN")
