---
baseline_commit: NO_VCS
---

# Story 1.6: Multimodal Fusion into a Single Analysis Result

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an Analyst,
I want the acoustic and transcript signals combined into one Analysis Result per Call,
so that I get one coherent, evidence-based judgment instead of two disconnected outputs.

## Acceptance Criteria

1. **Given** a Call has a valid acoustic-Emotion signal (Story 1.3), **When** the fusion filter runs, **Then** it runs regardless of whether the transcript-Sentiment signal (Story 1.5) exists or succeeded — fusion's only hard precondition is a valid acoustic signal, never transcript availability (AD-1).
2. **Given** fusion runs with both a valid acoustic signal and a valid transcript signal, **Then** it executes once per `TimelineSegment` — not once per Call — using confidence-weighted averaging of the two calibrated signals as a fixed rule; a trained/learned fusion model must never be used (AD-8), producing a multimodal Analysis Result.
3. **Given** fusion runs with a valid acoustic signal but the transcript signal is unavailable or failed (Story 1.4 or 1.5), **Then** it outputs the acoustic-emotion signal alone with an explicit single-modality flag on the affected segments and on `ANALYSIS_RESULT` — never presented as an ordinary two-signal fused result (AD-1, AD-8).
4. **Given** fusion completes (multimodal or single-modality) for all segments, **When** it finishes, **Then** `ANALYSIS_RESULT` is computed as a deterministic reduction over the Call's `TimelineSegment` rows (confidence-weighted mean); `ANALYSIS_RESULT` never runs an independent fusion pass of its own (AD-8).
5. **Given** Sentiment and Emotion values are generated, **Then** they remain separately-addressable fields end-to-end — in the ML service's output, the job payload, the SQLite schema, and the API response; no code merges them into one composite field at generation time (AD-15).
6. **Given** a row carries both Sentiment/Emotion confidence and speaker-attribution confidence, **Then** they are two separate fields, never combined into one composite score (AD-10).
7. **Given** fusion completes for all segments, **When** the last stage finishes, **Then** the Call's status transitions to `complete` (FR-3).
8. **Given** fusion is evaluated for accuracy, **Then** it is benchmarked against a majority-class baseline, then single-modality baselines, before crediting fusion with any benefit (AD-17).
9. **And** the fusion module has independently-runnable unit tests (AD-21).

## Tasks / Subtasks

- [x] Task 1: SQLite schema — fusion columns + `ANALYSIS_RESULT` table (AC: 2, 3, 4, 5, 6)
  - [x] Add `fused_sentiment TEXT`, `fused_emotion TEXT`, `fused_confidence REAL`, `single_modality_flag INTEGER`, `disagreement_flag INTEGER` to `TimelineSegment` in `ml-service/app/db.py`'s `_CREATE_TIMELINE_SEGMENT_TABLE` DDL. All nullable/default-absent until fusion runs. `disagreement_flag` always persisted as `0` by this story (see Dev Notes — Story 1.9 owns real detection); do not invent a `disagreement_threshold` config value here.
  - [x] Add a new `_CREATE_ANALYSIS_RESULT_TABLE` DDL: `call_id TEXT PRIMARY KEY REFERENCES Call(id)`, `overall_sentiment TEXT`, `overall_emotion TEXT`, `overall_confidence REAL`, `single_modality_flag INTEGER`, `secondary_signal_emotion TEXT` (nullable), `secondary_signal_confidence REAL` (nullable), `segments_flagged_count INTEGER`. Register it in `init_db()`.
  - [x] Add `persist_fusion_results(conn, *, segment_results: list[...], analysis_result: ...)` writing both the per-segment `UPDATE TimelineSegment` batch and the single `ANALYSIS_RESULT` upsert (`INSERT ... ON CONFLICT(call_id) DO UPDATE`) in one transaction (mirrors `persist_acoustic_results`'s single-commit atomicity).
  - [x] Add `get_analysis_result(conn, *, call_id)` read helper for tests.

- [x] Task 2: Config, queue, worker wiring (AC: 1, 7)
  - [x] Add `FUSION_QUEUE_NAME = "fusion"` to `ml-service/app/config.py`, following the exact comment style of `TEXT_SENTIMENT_QUEUE_NAME`. No new threshold/model config is needed — fusion has no ML model and no tunable cutoff in this story's scope.
  - [x] Add `get_fusion_queue()` to `ml-service/app/queue.py`.
  - [x] Register `FUSION_QUEUE_NAME` in the `Worker([...])` list in `ml-service/app/worker.py` (now five stages).

- [x] Task 3: Pure fusion computation logic (AC: 2, 3, 4, 5, 6, 8)
  - [x] Create `ml-service/app/pipeline/fusion/__init__.py`.
  - [x] Create `ml-service/app/pipeline/fusion/fuse.py` with pure, DB-free, queue-free functions (unit-testable without SQLite/Redis, mirroring `acoustic/classifier.py` + `taxonomy.py`'s separation of pure logic from I/O):
    - `fuse_segment(acoustic_emotion, acoustic_confidence, text_emotion, text_sentiment, text_confidence) -> FusedSegment` — `text_*` args are `None` when no usable text signal exists for this segment (see Task 5). Implements the exact algorithm in Dev Notes: self-weighted confidence average; dominant-modality label selection; single-modality flag. Internally imports `emotion_to_polarity` from `app.pipeline.acoustic.taxonomy` to derive the acoustic reading's polarity (`TimelineSegment` has no `acoustic_sentiment` column — only `acoustic_emotion`); the text reading's polarity is already computed (`TranscriptTurn.text_sentiment`). See "Two Emotion taxonomies, one shared polarity vocabulary" in Dev Notes before implementing this — `fused_emotion`'s label space depends on which modality wins.
    - `reduce_call(fused_segments: list[FusedSegment]) -> AnalysisResultReduction` — confidence-weighted vote for `overall_sentiment`/`overall_emotion`, self-weighted mean for `overall_confidence`, whole-call `single_modality_flag` (true only if every segment is single-modality), `secondary_signal_emotion`/`secondary_signal_confidence` (weighted vote among segments' non-dominant readings; `None`/`None` if no segment ever had two signals), `segments_flagged_count` (sum of `disagreement_flag`, always `0` this story).
    - Raise `ValueError` on an empty `fused_segments` list passed to `reduce_call` — a Call with zero `TimelineSegment` rows should never reach fusion (VAD/ingest always produces at least one segment for accepted audio); treat it as a bug, not a data condition, matching this codebase's existing "unknown taxonomy label" precedent (`raise`, never silently default).
  - [x] Create `ml-service/app/pipeline/fusion/overlap.py` (or a private helper inside `run.py` if smaller than expected) implementing the AD-11 time-range-overlap join: for a given `TimelineSegment`, find all overlapping `TranscriptTurn` rows (`segment.start_time < turn.end_time AND segment.end_time > turn.start_time`) that have a non-null `text_sentiment`, and select the one with the largest overlap duration as that segment's representative text signal (tie-break: lowest `turn_index`). Document this tie-break rule explicitly — AD-11 fixes the *boundary* relationship (many-to-many, time-range overlap) but does not fix a segment-level *aggregation* rule when multiple turns overlap one segment; this story must pick one, and "largest overlap wins" is the dev-agent's documented choice.

- [x] Task 4: `run_fusion` orchestration job (AC: 1, 2, 3, 4, 7)
  - [x] Create `ml-service/app/pipeline/fusion/run.py` with `run_fusion(call_id: str) -> None`.
  - [x] Read all `TimelineSegment` rows and all `TranscriptTurn` rows for the Call.
  - [x] For each segment: resolve its representative text signal via Task 3's overlap helper (or `None` if none), call `fuse_segment`, collect results in memory (compute-everything-then-write-once, mirroring every prior stage's atomicity discipline).
  - [x] Call `reduce_call` on the collected per-segment results to get the `ANALYSIS_RESULT` row.
  - [x] `db.persist_fusion_results(...)` — single transaction for both `TimelineSegment` updates and the `ANALYSIS_RESULT` upsert.
  - [x] `db.set_call_status(conn, call_id=call_id, status="complete")` (FR-3) — this is the **only** place in the whole pipeline that writes `complete`.
  - [x] **Fail-hard semantics** (deliberately unlike `run_transcript`/`run_text_sentiment`): wrap the body in the same rollback-then-`failed`-then-re-raise pattern `run_ingest`/`run_acoustic` use. Fusion is the mandatory terminal stage — if it cannot complete, the Call can never reach `complete`, and FR-3's state machine (`queued → processing → complete → failed`) has no legitimate "stuck at processing forever" state. See Dev Notes for the full rationale.
  - [x] No audio/model loading of any kind in this job — it only reads already-computed values from SQLite and writes back, unlike every previous stage.

- [x] Task 5: Wire the five fusion-trigger call sites (AC: 1, 3, 7)
  - [x] `ml-service/app/pipeline/acoustic/run.py`: in the existing isolated `except` block around the transcript-queue enqueue call, also enqueue fusion (`"app.pipeline.fusion.run.run_fusion"`), isolated in its own nested `try`/`except`. This is the fallback for "transcript stage never even got the chance to start."
  - [x] `ml-service/app/pipeline/transcript/run.py`: in the existing isolated `except` block around the text-sentiment-queue enqueue call, enqueue fusion as a fallback (isolated `try`/`except`).
  - [x] `ml-service/app/pipeline/transcript/run.py`: in `run_transcript`'s own outer `except` block (whole-transcript-stage failure), enqueue fusion (isolated `try`/`except`) — this path currently never enqueues anything downstream at all.
  - [x] `ml-service/app/pipeline/transcript/sentiment_run.py`: at the end of `run_text_sentiment`'s success path (after persisting results), enqueue fusion, isolated `try`/`except`, same pattern as every prior stage-chaining enqueue.
  - [x] `ml-service/app/pipeline/transcript/sentiment_run.py`: in `run_text_sentiment`'s own outer `except` block, also enqueue fusion (isolated `try`/`except`).
  - [x] Verify (by code-reading, and by the tests in Task 7) that these five sites are mutually exclusive for any single Call — exactly one fires, so fusion is enqueued exactly once. Do **not** add a defensive re-entrancy guard inside `run_fusion` itself for double-invocation — no other stage in this codebase guards against that, and the mutual-exclusivity argument in Dev Notes is the actual correctness mechanism, not a runtime check.

- [x] Task 6: Baseline evaluation harness (AC: 8, 9)
  - [x] Create `ml-service/app/pipeline/fusion/evaluate.py`. Import and reuse `majority_class_baseline_uar` from `app.pipeline.acoustic.evaluate` (do not duplicate it).
  - [x] Add `single_modality_baseline_uar(true_labels: list[str], acoustic_only_predictions: list[str], text_only_predictions: list[str]) -> tuple[float, float]` — returns each single-modality baseline's UAR, dependency-free, pure-Python, same shape/spirit as `majority_class_baseline_uar`.
  - [x] Document explicitly (module docstring) that no automatable, license-clear, in-domain (call-center) multimodal dataset with paired audio+transcript+ground-truth labels exists for MVP — unlike Story 1.3, which had a real CREMA-D acoustic-only spot-check, this story does **not** attempt a real fusion spot-check; it ships the reusable baseline-comparison utilities only, per AD-17's own text ("pending in-domain validation against a small manually-annotated in-domain validation set" — that validation set does not exist yet). This is future evaluation work, not this story's scope.

- [x] Task 7: Tests (AC: 9)
  - [x] `test_fuse.py`: unit tests for `fuse_segment`/`reduce_call` — dominant-modality selection (higher confidence wins), the exact confidence-weighting formula, single-modality path (text args all `None`), whole-call single-modality flag (all-single vs. mixed vs. none-single), secondary-signal computation and its `None` fallback, `segments_flagged_count` is always 0, `reduce_call([])` raises.
  - [x] `test_overlap.py` (or folded into `test_fuse.py`/`test_fusion_run.py` if the helper stayed small): overlap detection correctness, largest-overlap-wins tie-break, zero-overlapping-turns case.
  - [x] `test_fusion_run.py`: real end-to-end chain (seed via `run_ingest`→`run_acoustic`→`run_transcript`→`run_text_sentiment` fixtures, mirroring Story 1.5's `_seed_transcript` pattern) asserting `run_fusion` persists valid `TimelineSegment` fusion columns and a valid `ANALYSIS_RESULT` row, and that `Call.status == "complete"`. Also: a transcript-failure path (mock `run_transcript`'s internals to fail) still reaches `run_fusion` with `single_modality_flag=1` throughout and `Call.status == "complete"`. Also: a `run_fusion` internal failure sets `Call.status == "failed"` and re-raises (fail-hard, unlike Story 1.4/1.5). Also: each of the five enqueue sites from Task 5 individually verified (mirroring Story 1.4/1.5's own enqueue-success/enqueue-failure test pairs).
  - [x] `test_evaluate.py` additions (or a new `test_fusion_evaluate.py`): `single_modality_baseline_uar` correctness on a small synthetic labeled example.
  - [x] Extend `ml-service/tests/conftest.py` with a `fake_fusion_queue` autouse fixture, mirroring `fake_acoustic_queue`/`fake_transcript_queue`/`fake_text_sentiment_queue` exactly.

- [x] Task 8: Structured logging (AC: 9, cross-cutting AD-21)
  - [x] `run_fusion` logs start/completion (`call_id`, `segment_count`, whether the Call ended up single-modality) via the existing `logger.info(..., extra={"extra_fields": {...}})` pattern used by every prior stage. Failure path logs via `logger.error`/`logger.exception` per the fail-hard pattern (mirrors `run_acoustic`, not `run_transcript`).

- [x] Task 9: Full verification pass
  - [x] Run the full `ml-service` test suite (Docker CPU verification, same workflow as Stories 1.3–1.5) — all tests pass, including the pre-existing suite (no regressions).
  - [x] Run `ruff check .` — clean.
  - [x] Run `docker compose config --quiet` — valid (no Dockerfile changes expected this story, since fusion needs no new model/dependency, but the worker/queue wiring still touches `docker-compose.yml`-relevant env if any threshold were added — confirm none were).

### Review Findings (AI)

- [x] [Review][Decision] Zero-`TimelineSegment` Calls (silence/no-speech audio) are marked `status="failed"` instead of a legitimate "no speech detected" outcome — a Call whose VAD/ingest stage genuinely detects zero speech segments (the `silence.wav` test fixture exists specifically for this scenario) sails through acoustic/transcript/text-sentiment as a no-op, then reaches `run_fusion` with an empty segment list, trips `reduce_call([])`'s `ValueError`, and gets marked `failed` via the fail-hard path — indistinguishable from a genuine technical failure. No AC, the PRD, or the architecture spine specifies the desired behavior for a Call with zero detected speech. [ml-service/app/pipeline/fusion/run.py, fuse.py] — **Resolved (user decision, 2026-08-14):** mark `Call.status = "complete"` with no `AnalysisResult` row produced; `db.get_analysis_result(...)` returning `None` is the "no speech detected" signal.
- [x] [Review][Patch] `run_fusion`'s success path is not atomic end-to-end — `db.persist_fusion_results(...)` commits, then a separate `db.set_call_status(..., status="complete")` call follows; if that second call raises (e.g. a transient SQLite lock under concurrent WAL writes, AD-12), execution falls into the outer `except`, which marks the Call `failed` despite the `AnalysisResult`/fused `TimelineSegment` rows already being fully and validly committed — an internally inconsistent Call. [ml-service/app/pipeline/fusion/run.py] — **Fixed:** the status write is now inside `persist_fusion_results`'s own transaction.
- [x] [Review][Patch] `_weighted_vote`'s tie-break behavior (equal-weight labels resolve to whichever was encountered first — i.e. the earliest `segment_index`, via Python dict insertion order + `max()`'s first-wins-on-tie semantics) is real and deterministic but undocumented, unlike `fuse_segment`'s explicit "ties favor acoustic" and `overlap.py`'s explicit "ties favor lowest turn_index" comments. [ml-service/app/pipeline/fusion/fuse.py] — **Fixed:** documented in the function's docstring.
- [x] [Review][Patch] The comment "ties favor acoustic (voice-first priority, AD-1)" in `fuse_segment` misattributes an implementation-level tie-break choice to AD-1, which governs acoustic being mandatory for fusion to run at all, not per-segment tie-break priority — risks a future maintainer treating an arbitrary dev-agent choice as an architecture mandate. [ml-service/app/pipeline/fusion/fuse.py] — **Fixed:** comment reworded to stop citing AD-1 as the tie-break's source.
- [x] [Review][Patch] No test exercises `reduce_call` with genuinely mixed-taxonomy segments (some acoustic-dominant, some text-dominant, with real different-taxonomy emotion labels) to prove the documented "expected, not a bug" cross-taxonomy vote-pooling behavior is intentional and stable rather than accidental. Bundle with correcting the stale "test_fuse.py: 14" count in the Dev Agent Record's Completion Notes (actual count is higher). [ml-service/tests/test_fuse.py] — **Fixed:** added `test_reduce_call_handles_genuinely_mixed_taxonomy_segments`; count corrected.
- [x] [Review][Defer] `conn = db.get_connection()` sits outside `run_fusion`'s try/except [ml-service/app/pipeline/fusion/run.py] — deferred, pre-existing: identical shape already deferred from Story 1.5's review (`run_ingest`/`run_acoustic`/`run_transcript`/`run_text_sentiment`); `run_fusion` is now a fifth instance of the same cross-cutting gap. Revisit as one cross-cutting fix across all five `run_*` entrypoints.
- [x] [Review][Defer] `acoustic_confidence`/`text_confidence` are never validated as finite/non-NaN before use in fusion's arithmetic [ml-service/app/pipeline/fusion/fuse.py] — deferred, pre-existing: a NaN confidence would silently bypass `run_acoustic`'s existing `if confidence < ACOUSTIC_SANITY_FLOOR` sanity check (NaN comparisons are always `False` in IEEE754) from Story 1.3; fusion only consumes the already-unvalidated value, it doesn't introduce the gap. Revisit alongside a Story 1.3 sanity-check hardening pass.
- [x] [Review][Defer] `resolve_text_signal`'s "largest-overlap-wins" per-segment resolution means one long `TranscriptTurn` spanning several short acoustic segments contributes to the Call-level weighted vote once per overlapping segment rather than once per turn, over-weighting turns that span many segments [ml-service/app/pipeline/fusion/overlap.py] — deferred, defensible-as-designed: consistent with AD-8's per-segment reduction-unit model (a turn influencing more of the Call's duration arguably should carry proportionally more weight), not an unambiguous bug. Revisit once real evaluation work (AD-17) can measure the actual effect on aggregate accuracy.

## Dev Notes

### Critical design decision — how fusion gets triggered (read before writing any code)

Every prior stage (`ingest → acoustic → transcript → text_sentiment`) is a strict linear chain: each stage enqueues exactly one successor, and only on its own success. **Fusion breaks that pattern.** AC 1 / AD-1 require fusion to run whenever acoustic succeeded, *regardless* of whether the transcript branch ever produced a usable signal — including cases where the transcript branch fails so early it never gets the chance to enqueue anything downstream at all (e.g. `run_transcript` throws before ever reaching its own enqueue call, or `run_acoustic`'s own attempt to enqueue `run_transcript` fails).

If fusion were chained the same simple way (only from `run_text_sentiment`'s success path), any transcript-branch failure upstream of that single enqueue point would mean fusion — and therefore `Call.status = "complete"` — **never happens**, leaving the Call stuck at `processing` forever. That would violate AC 7/FR-3 for exactly the Calls AD-1 most cares about (acoustic succeeded, transcript failed).

The fix (detailed in Task 5) is a **fan-in**: five call sites, one in each place the transcript branch can terminate without reaching the next stage, all enqueueing fusion. These five sites are mutually exclusive for any given Call — tracing the control flow of `acoustic/run.py` → `transcript/run.py` → `sentiment_run.py` shows exactly one of them executes per Call, so fusion is enqueued exactly once, never zero times, never more than once. Do not simplify this to a single chained call from `run_text_sentiment` alone — that is the one design that silently breaks AC 1.

### Two Emotion taxonomies, one shared polarity vocabulary — the single easiest mistake to make in this story

`TimelineSegment.acoustic_emotion` is drawn from `acoustic/taxonomy.py`'s 4-class vocabulary (`neutral`/`happy`/`sad`/`angry`). `TranscriptTurn.text_emotion` is drawn from `sentiment_taxonomy.py`'s 28-class GoEmotions-derived vocabulary (`admiring`/`amused`/.../`surprised`). **These are two intentionally different label spaces** (AD-4 only fixes one *shared* vocabulary — the 4-value polarity — as cross-modal-comparable; per-modality Emotion taxonomies are explicitly allowed to differ). `TimelineSegment` has **no `acoustic_sentiment` column** — only Story 1.5 added a directly-stored polarity (`text_sentiment`); the acoustic polarity must be derived on the fly via `emotion_to_polarity(acoustic_emotion)`.

Consequences for this story's fields:
- `fused_sentiment` is **always** one of the four shared polarity values, regardless of which modality dominates — computed via `emotion_to_polarity(acoustic_emotion)` when acoustic dominates, or read directly from the already-computed `text_sentiment` when text dominates. This is the one field that is always safely cross-modal-comparable.
- `fused_emotion` (and `secondary_signal_emotion`) carries **whichever taxonomy the winning modality happens to use** — do not try to normalize it into one unified Emotion vocabulary; that would be inventing a third taxonomy this story has no mandate to build. A Call's `overall_emotion` can therefore legitimately end up drawn from either taxonomy depending on which segments' readings accumulated more weighted support — this is expected, not a bug, and must not be "fixed" by coercing one taxonomy into the other.
- `reduce_call`'s confidence-weighted vote for `overall_sentiment` is always comparing like-with-like (polarity values only). Its vote for `overall_emotion` is comparing raw emotion-label strings across segments that may come from either taxonomy — accept this as-is.

### Fusion algorithm (AD-8 fixes the *shape* — rule-based, confidence-weighted, never trained — not the exact formula; this section is the dev-agent's required, documented choice)

**Per-segment fusion (`fuse_segment`):**
- Acoustic reading always exists (AD-1: acoustic is mandatory). Text reading is either present (this segment overlaps a turn with a non-null `text_sentiment`, per Task 3's overlap rule) or absent.
- **Single-modality case** (no text reading): `fused_emotion = acoustic_emotion`, `fused_sentiment = emotion_to_polarity(acoustic_emotion)`, `fused_confidence = acoustic_confidence`, `single_modality_flag = True`. No averaging happens — there is nothing to average against.
- **Multimodal case:** the **dominant modality** is whichever of `acoustic_confidence`/`text_confidence` is higher (acoustic wins ties, consistent with voice-first priority, AD-1). `fused_emotion`/`fused_sentiment` = the dominant modality's own reading, using the mapping in "Two Emotion taxonomies" above (fusion picks a winner's *label*, it does not synthesize a new label — there is no "average" of two Emotion strings). `fused_confidence` is a genuine numeric confidence-weighted average, self-weighted by each signal's own confidence: `fused_confidence = (acoustic_confidence² + text_confidence²) / (acoustic_confidence + text_confidence)`. This is standard confidence-weighted averaging (each value weighted by itself) — more confident signal pulls the result toward itself more, and it degrades gracefully to the acoustic-only case as `text_confidence → 0`. `single_modality_flag = False`. The **secondary (non-dominant) modality's own reading is retained**, not discarded (AD-8) — `fuse_segment` returns it alongside the fused result for `reduce_call` to use.
- `disagreement_flag = False` always, this story (see below).

**Call-level reduction (`reduce_call`):**
- `overall_confidence`: the same self-weighted-average formula applied across all segments (weight = each segment's own `fused_confidence`), never a plain arithmetic mean — mirrors the per-segment formula's philosophy at Call scope.
- `overall_sentiment`/`overall_emotion`: categorical, so "confidence-weighted mean" cannot mean numeric averaging here either. Use a **confidence-weighted vote**: sum each segment's `fused_confidence` grouped by its `fused_sentiment`/`fused_emotion` value; the value with the largest summed weight wins. This is the direct categorical analogue of a weighted mean and stays fully deterministic.
- `single_modality_flag` (Call-level): **true only when every segment in the Call is single-modality.** A Call with a mix of multimodal and single-modality segments still produced a genuine, if partial, multimodal fusion result and must not be mislabeled as a wholesale single-modality Call — AC 3's "never presented as an ordinary two-signal fused result" language describes the fully-failed-transcript scenario specifically. Per-segment flags remain individually accurate regardless.
- `secondary_signal_emotion`/`secondary_signal_confidence`: the same confidence-weighted-vote reduction as `overall_emotion`, but applied only over the **non-dominant** reading of segments that had one (multimodal segments only). If no segment in the Call ever had a non-dominant reading (i.e. the Call ended up fully single-modality), both are `None` — this is the "None flagged" state, reachable without needing any not-yet-invented threshold. Story 1.9 later adds a "distinct enough to report" gate on top of this baseline (per its own AC4/AC5 and Epic 2 Story 2.4's AC) — that gate is explicitly **not** this story's scope; ship the always-retain-if-present baseline.
- `segments_flagged_count`: `sum(1 for s in fused_segments if s.disagreement_flag)` — always `0` this story, since `disagreement_flag` is always `False` (see below). Wire the field so Story 1.9 only has to change the flag-setting logic, not the counting/aggregation.

### Disagreement flag — deliberately a no-op in this story (do not build Story 1.9's logic here)

AD-8's architecture text describes fusion setting a real per-segment disagreement flag "when the two modalities disagree in polarity and both exceed a configurable confidence floor." That configurable floor is `disagreement_threshold` — and **Story 1.9 (Cross-Modal Disagreement Surfacing)** is the story that introduces that config value and the real detection logic, not this one. Confirmation of this split is explicit in Story 1.7's own dependency note (epics.md): *"the disagreement flag field returned in AC1 below is owned by Story 1.9 ... until Story 1.9 is implemented, every segment's disagreement flag defaults to false/absent, and this story is fully completable and testable against that default ... does not need to be re-opened once Story 1.9 lands — the field's shape is unchanged, only its populated value."*

So for Story 1.6: add the `disagreement_flag` column (Task 1), always persist `0`/`False` (Task 3/4), and count it correctly in `segments_flagged_count` (which will therefore always be `0` for now). Do **not** add a `disagreement_threshold` config value, do **not** compare polarities against any floor, and do **not** try to anticipate Story 1.9's exact comparison logic — that would be building a future story's scope into this one, and is very likely to be built wrong without Story 1.9's own full context (the threshold's exact value and comparison semantics are explicitly deferred in the Architecture spine's own "Deferred" section).

### Why `run_fusion` fails hard (rollback + `Call.status = "failed"` + re-raise) unlike `run_transcript`/`run_text_sentiment`

Stories 1.4 and 1.5 both established a **fail-soft** pattern (log via `logger.exception`, return normally, never touch `Call.status`) specifically because transcript/text-sentiment are optional enrichments — AD-1 guarantees the acoustic signal remains independently valid regardless of their outcome, so their failure is never a Call-level failure.

Fusion is different: it is the **only** stage that can ever move `Call.status` to `complete` (AC 7/FR-3). If `run_fusion` itself throws (a DB error, a genuinely malformed `TimelineSegment`/`TranscriptTurn` state, etc.) and it swallowed the exception the way Story 1.4/1.5 do, the Call would be left at `processing` forever with no path to `complete` or `failed` — a stuck state FR-3's `queued → processing → complete → failed` machine does not define and the Analyst-facing status polling has no way to represent ("Analyst is never left looking at an unchanging screen with no indication"). So `run_fusion` instead follows `run_ingest`/`run_acoustic`'s **fail-hard** pattern: `conn.rollback()`, best-effort `db.set_call_status(..., status="failed")`, log via `logger.error`, re-raise. This is a deliberate divergence from the two immediately-preceding stories, not an oversight — call it out explicitly in code comments the way Story 1.4/1.5 called out their own divergence from `run_ingest`/`run_acoustic`.

### Previous story intelligence (Story 1.5)

- **Atomicity discipline**: every persistence function in `db.py` computes nothing partially — callers gather all results in memory across the whole Call, then call one persistence function that does everything in a single transaction/commit. `persist_fusion_results` must follow this exactly (Task 1).
- **Isolated enqueue try/except**: every stage-chaining `queue.get_X_queue().enqueue(...)` call has always lived inside its own nested `try`/`except Exception: logger.exception(...)`, separate from the stage's own success/failure handling, so a Redis-reachability problem is never misreported as an analysis failure. Story 1.5 built this in from the start (per its own story file's guidance) rather than needing a code-review pass to add it, unlike Story 1.4. Task 5 must do the same from the start.
- **`NamedTuple` for structured persistence inputs**: Story 1.5's code review flagged a positional-tuple footgun in `persist_text_sentiment_results` and replaced it with `db.TextSentimentResult`, a `NamedTuple`. Use the same pattern for any new structured persistence input this story introduces (e.g. a `FusedSegmentResult`/`AnalysisResultRow` `NamedTuple` in `db.py` or `fuse.py`) rather than a raw positional tuple — do not wait for a code-review pass to catch this again.
- **Per-item isolation / skip-and-continue**: Story 1.4/1.5 both isolate each item's (segment's/turn's) processing so one bad item doesn't discard the whole Call's results. Fusion's per-segment loop (Task 4) should follow the same shape, though note fusion reads already-validated, already-persisted upstream values (no new external I/O, no new failure surface per item beyond a possible data anomaly) — the isolation is cheap insurance, not defense against a likely failure mode.
- **Docker dev workflow**: Intel Mac sandbox, no native PyTorch wheel — verification requires the same `Dockerfile.dev` + `docker run` (volume-mounted `app/`/`tests/` over a previously-built image to skip the ~200s pip-install phase when no new dependency is added, which is the case this story) workflow used for Stories 1.3–1.5. This story adds **no new PyPI dependency and no new model** — the fastest correct verification path is almost certainly the volume-mount-over-existing-image shortcut, without even needing a fresh `Dockerfile.dev` build, since `ml-service-dev:latest` from Story 1.5's verification should still be usable if it wasn't removed. If it was removed, one fresh `Dockerfile.dev` build is still required (no shortcut around the first build).
- **License-verification discipline (WebFetch before trusting any suggested model)**: not applicable this story — no new model is introduced. Flagging its absence here only to confirm it was considered, not skipped.

### Architecture compliance (non-negotiable)

- **AD-1**: fusion's only hard precondition is a valid acoustic signal (see the fan-in design above). Never substitute a transcript-only signal for a missing/failed acoustic one — not applicable in practice here since fusion never runs at all unless acoustic already succeeded (see Task 5's enqueue sites, all downstream of `run_acoustic`'s own success path).
- **AD-7**: fusion lives in the same consolidated `ml-service` (this story adds `app/pipeline/fusion/`, not a new service). All fusion work is dispatched via the RQ job queue (Task 2), consumed by the same `Worker` process (now five queues).
- **AD-8**: rule-based, confidence-weighted, never a trained/learned model (see algorithm above). Disagreement flag exists but is a documented no-op this story (Story 1.9's scope). Secondary Signal is always retained when a non-dominant reading exists.
- **AD-9**: fusion consumes `acoustic_confidence`/`text_confidence`, both of which are *already* temperature-scaled/calibrated by their respective upstream stages (Story 1.3/1.5) — fusion itself performs no new calibration, it only combines two already-calibrated numbers.
- **AD-10**: `TimelineSegment`/`ANALYSIS_RESULT`'s Sentiment/Emotion confidence (`fused_confidence`/`overall_confidence`) is a wholly separate concept/column from any future speaker-attribution confidence (Epic 3, not yet built) — this story does not add a speaker-attribution column, so there is nothing to conflate yet; the guardrail is about not inventing a combined field later.
- **AD-11**: the segment↔turn relationship is consumed here for the first time as a real many-to-many time-range-overlap join (Task 3's `overlap.py`) — `TranscriptTurn` boundaries are never clipped/resplit to fit `TimelineSegment` boundaries; the overlap helper reads both tables' boundaries as-is.
- **AD-13**: `Call.status` transitions are written only by the RQ worker (this was already true; fusion just adds the final transition, `→ complete`).
- **AD-15**: `fused_sentiment`/`overall_sentiment` and `fused_emotion`/`overall_emotion` are separate columns throughout — never merged into one composite field, mirroring `TranscriptTurn.text_sentiment`/`text_emotion`'s existing separation.
- **AD-16**: not directly exercised by this story (no API/UI surface yet — that's Epic 1's later stories/Epic 2) but the data this story produces (confidence + evidence-linkable via `segment_id`) is what makes AD-16 satisfiable once an API exists.
- **AD-17**: baseline-first evaluation harness (Task 6) — majority-class UAR reused, single-modality UAR added, no unproven fusion-benefit claim made or implied by this story.
- **AD-18**: no GPU assumption — this story adds no ML inference at all (pure Python arithmetic over already-computed numbers), so it is trivially CPU-only.
- **AD-21**: independently-runnable unit tests for the fusion module (Task 7), structured JSON logging (Task 8).

### What NOT to build in this story

- **No API endpoint.** `ANALYSIS_RESULT`/fused `TimelineSegment` retrieval is Story 1.7 (Emotional Timeline Retrieval) and later Epic 2 work. This story only computes and persists.
- **No `disagreement_threshold` config value or real disagreement detection.** `disagreement_flag` is always persisted `False`. Story 1.9's scope, not this one (see dedicated section above).
- **No "distinct enough to report" gating on Secondary Signal.** Ship the always-retain-non-dominant-reading baseline; Story 1.9/Epic 2 Story 2.4 add the threshold-based omission logic later.
- **No `low_confidence_threshold` consumption.** That's Story 1.8's concern (flagging low-confidence results for display) — this story stores confidence values, it does not classify them as low/high.
- **No speaker-attribution confidence column.** Epic 3 (diarization) doesn't exist yet in this codebase; AD-10's guardrail is about not conflating it with Sentiment/Emotion confidence *when it eventually arrives*, not a requirement to add a placeholder column now.
- **No schema-migration tooling.** Like every prior story, new columns are added directly to the `CREATE TABLE IF NOT EXISTS` DDL strings in `db.py`. This is a known, already-deferred gap (see `deferred-work.md`'s entries from Story 1.5's code review) — not this story's problem to solve.
- **No real in-domain multimodal evaluation/spot-check dataset.** AD-17 explicitly defers real in-domain validation to future evaluation work; this story ships the baseline-comparison *utilities* only (Task 6).
- **No changes to `Dockerfile`** (only `docker-compose.yml`/worker queue list, if anything) — fusion introduces no new PyPI dependency and no new model to pre-fetch.

### Testing Standards

- Same Docker-based CPU verification workflow as Stories 1.3–1.5 (Intel Mac sandbox, no native PyTorch wheel): `pytest tests/ -v` and `ruff check .` inside the `ml-service-dev` container, `docker compose config --quiet` from the repo root.
- Pure-logic tests (`fuse.py`, `overlap.py`, `evaluate.py`) need no DB, no queue, no audio — fast, dependency-free, exactly mirroring `test_taxonomy.py`/`test_sentiment_taxonomy.py`'s style.
- Integration tests (`run.py`) reuse the established `make_call`/`call_row`/fake-queue fixture pattern from `conftest.py`; add `fake_fusion_queue` alongside the existing three fake-queue fixtures.
- Real end-to-end chaining test (seed via the real Story 1.3/1.4/1.5 stages) plus fast mocked/deterministic tests, mirroring Story 1.5's `_seed_transcript` (real) + `_seed_turns_directly` (mocked) split — do not make every test depend on real model inference; only one or two representative tests need to.

### Project Structure Notes

- New: `ml-service/app/pipeline/fusion/__init__.py`, `fuse.py`, `overlap.py`, `run.py`, `evaluate.py`.
- New: `ml-service/tests/test_fuse.py`, `test_overlap.py` (or folded in), `test_fusion_run.py`, fusion-evaluate tests.
- Modified: `ml-service/app/db.py` (schema + persistence functions), `ml-service/app/config.py` (queue name only), `ml-service/app/queue.py`, `ml-service/app/worker.py`, `ml-service/app/pipeline/acoustic/run.py`, `ml-service/app/pipeline/transcript/run.py`, `ml-service/app/pipeline/transcript/sentiment_run.py`, `ml-service/tests/conftest.py`.
- No changes expected to `web-api/`, `ml-service/Dockerfile`, `ml-service/pyproject.toml` (no new dependency).

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.6: Multimodal Fusion into a Single Analysis Result] (lines 232–248)
- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.7: Emotional Timeline Retrieval] (lines 250–264, dependency note establishing the disagreement-flag default/Story 1.9 split)
- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.9: Cross-Modal Disagreement Surfacing] (lines 280–294)
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#AD-1] (lines 35–43)
- [Source: .../ARCHITECTURE-SPINE.md#AD-7] (lines 75–89)
- [Source: .../ARCHITECTURE-SPINE.md#AD-8] (lines 91–100)
- [Source: .../ARCHITECTURE-SPINE.md#AD-9] (lines 102–106)
- [Source: .../ARCHITECTURE-SPINE.md#AD-10] (lines 108–112)
- [Source: .../ARCHITECTURE-SPINE.md#AD-11] (lines 114–118)
- [Source: .../ARCHITECTURE-SPINE.md#AD-15] (lines 138–142)
- [Source: .../ARCHITECTURE-SPINE.md#AD-17] (lines 150–154)
- [Source: .../ARCHITECTURE-SPINE.md#Core-entity sketch] (lines 248–259, `ANALYSIS_RESULT` is the Call-level aggregate, `TIMELINE_SEGMENT }o--o{ TRANSCRIPT_TURN` overlap relationship)
- [Source: _bmad-output/planning-artifacts/prds/prd-AIVoiceSentimentAnalyzer_v1-2026-08-10/prd.md#FR-3] (lines 99–105)
- [Source: .../prd.md#FR-8] (lines 153–158)
- [Source: .../prd.md#FR-11] (lines 174–179)
- [Source: _bmad-output/implementation-artifacts/1-5-transcript-sentiment-and-context-analysis.md] (previous story, full file — atomicity/enqueue/NamedTuple/Docker-workflow precedent)
- [Source: ml-service/app/db.py] (existing schema — `TimelineSegment`, `TranscriptTurn`, `AcousticEvidence` DDL and persistence functions read in full at story-creation time)
- [Source: ml-service/app/pipeline/acoustic/run.py, evaluate.py, taxonomy.py] (fail-hard pattern, `majority_class_baseline_uar` reuse target, pure-logic/I/O separation pattern)
- [Source: ml-service/app/pipeline/transcript/run.py, sentiment_run.py, sentiment_taxonomy.py] (fail-soft pattern, five-site enqueue fan-in analysis)
- [Source: ml-service/app/queue.py, worker.py, config.py] (existing queue/worker wiring pattern to extend)
- [Source: ml-service/tests/conftest.py] (fixture patterns: `make_call`, `call_row`, `timeline_segments`, fake-queue fixtures)

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5 (claude-sonnet-5)

### Debug Log References

- **Fan-in trigger design (the story's central risk).** Traced control flow through `acoustic/run.py` → `transcript/run.py` → `sentiment_run.py` by hand to confirm the five fusion-enqueue call sites are mutually exclusive per Call (exactly one fires): (1) `run_acoustic`'s transcript-enqueue `except`, (2) `run_transcript`'s text-sentiment-enqueue `except`, (3) `run_transcript`'s own outer `except`, (4) `run_text_sentiment`'s success path, (5) `run_text_sentiment`'s own outer `except`. Verified empirically with 5 dedicated tests (one per site) plus a real end-to-end chain test — all pass.
- **Confidence-weighting formula**: implemented `fused_confidence = (a² + b²) / (a + b)` (self-weighted average) per the Dev Notes' documented formula — verified via `test_fuse_segment_confidence_weighting_formula` (exact formula match) and `test_fuse_segment_confidence_weighting_pulls_toward_more_confident_signal` (sits strictly between the plain mean and the dominant value).
- **Two-taxonomy `fused_emotion`**: `fuse_segment` derives the acoustic reading's polarity on the fly via `acoustic.taxonomy.emotion_to_polarity` (no stored `acoustic_sentiment` column exists) rather than assuming one exists — caught during story creation's self-validation pass, not during implementation.
- **`AnalysisResult` upsert**: used `INSERT ... ON CONFLICT(call_id) DO UPDATE` rather than a plain `INSERT`, since RQ's delivery semantics are at-least-once, not exactly-once — a retried `run_fusion` invocation must not raise a `PRIMARY KEY` violation on the second attempt.
- **`run_transcript`'s outer-except test needed the missing-audio path, not a mocked `transcribe_segment` failure**: initially planned to trigger `run_transcript`'s own outer `except` block by mocking `transcribe_segment` to raise, but re-reading the existing code confirmed that failure is caught by the *per-segment* inner `try`/`except` (skip-and-continue) and never reaches the outer block. Switched the test to the missing-audio scenario (`load_mono_waveform` raises before the loop even starts), mirroring the existing `test_run_transcript_missing_audio_does_not_fail_the_call` test's precondition — verified correct by inspection before writing the test, not by trial and error.
- **Docker verification**: `Dockerfile.dev` recreated fresh (Story 1.5's own copy had already been cleaned up), full `pip install --extra-index-url ... ".[dev]"` build (~355s, no model pre-fetch needed — this story adds no new dependency/model). Full suite: `docker run --rm ml-service-dev:latest bash -c "pytest tests/ -v; ruff check ."` — **92 passed, 1 pre-existing warning, ruff clean** (1746s wall time — noticeably slower than Story 1.5's 460s for a similarly-sized suite, apparently sandbox/host load rather than anything in this story: `docker stats` showed the container actively using CPU and network throughout, not stalled). `docker compose config --quiet` — valid. `Dockerfile.dev` and the `ml-service-dev:latest` image were removed after verification, per established per-story cleanup precedent.

### Code review follow-up (2026-08-14)

3-layer adversarial review (Blind Hunter, Edge Case Hunter, Acceptance Auditor) ran against the full NO_VCS diff (9 new + 12 modified files, ~3177 lines). Outcome: 1 decision-needed, 4 patch, 3 defer (pre-existing/defensible, cross-referenced in `deferred-work.md`), 5 dismissed as noise (2 mathematically/factually refuted, 3 already-in-scope per this story's own Dev Notes).

- **Decision (user, 2026-08-14):** a Call with zero `TimelineSegment` rows (silence/no-speech audio) now completes with `Call.status = "complete"` and **no** `AnalysisResult` row — `db.get_analysis_result(...)` returning `None` is the well-defined "no speech detected" signal for downstream consumers, rather than the previous behavior (`reduce_call([])` raising, Call marked `"failed"`). Implemented as an early-return guard at the top of `run_fusion`, before the main per-segment loop.
- **Patch — atomicity**: folded `Call.status = "complete"` into `db.persist_fusion_results`'s own transaction (single commit covering `TimelineSegment` updates + `AnalysisResult` upsert + the status write) instead of a separate `db.set_call_status(...)` call after `persist_fusion_results` returned — a failure in that second call could previously mark the Call `"failed"` despite fully valid, already-committed fusion results.
- **Patch — `_weighted_vote` tie-break documented**: added an explicit docstring note explaining the (real, deterministic, previously-undocumented) earliest-segment-wins tie-break behavior, mirroring `fuse_segment`'s and `overlap.py`'s own explicit tie-break comments.
- **Patch — AD-1 citation corrected**: reworded `fuse_segment`'s "ties favor acoustic (voice-first priority, AD-1)" comment to stop citing AD-1 as the source of the tie-break rule itself (AD-1 mandates acoustic as mandatory for fusion to run, not per-segment tie-break priority) — now framed as a dev-agent choice thematically consistent with AD-1, not an AD-1 requirement.
- **Patch — test coverage added**: `test_reduce_call_handles_genuinely_mixed_taxonomy_segments` (proves the documented cross-taxonomy vote-pooling behavior resolves deterministically without crashing) and `test_run_fusion_zero_segments_completes_with_no_analysis_result` (covers the new decision above).
- **Deferred** (added to `deferred-work.md`, cross-referenced to pre-existing patterns): `conn = db.get_connection()` outside `run_fusion`'s try/except (5th instance of the Story 1.5-deferred cross-cutting gap); `acoustic_confidence`/`text_confidence` not validated as finite/non-NaN (originates in Story 1.3's sanity-floor check, not this story); `resolve_text_signal`'s per-segment (not per-turn) weighting of wide `TranscriptTurn`s (defensible under AD-8's per-segment reduction-unit design).
- **Dismissed**: cross-taxonomy vote pooling itself (matches this story's own Dev Notes, explicitly documented as "expected, not a bug"); `ZeroDivisionError` in `_self_weighted_average` (refuted — softmax's max-probability-≥-1/N property makes a zero-weight input mathematically unreachable from either classifier); "exactly-once fan-in" RQ-retry concern (refuted — no `retry=` policy is configured on any `enqueue()` call anywhere in this codebase, so automatic redelivery cannot occur); AD-17 baseline utilities not wired into CI (matches this story's own Dev Notes, explicitly scoped as future evaluation work); quadratic `resolve_text_signal` complexity (non-urgent at MVP scale, per the reviewer's own caveat).
- Re-verified via a second full Docker pass after all patches: **94 passed** (92 + 2 new tests), ruff clean.

### Completion Notes List

- All 9 tasks complete, all acceptance criteria satisfied.
- Implemented the full `app/pipeline/fusion/` module: `fuse.py` (pure confidence-weighted fusion + Call-level reduction), `overlap.py` (AD-11 time-range-overlap resolution, largest-overlap-wins tie-break), `run.py` (the `run_fusion` RQ job, fail-hard unlike Stories 1.4/1.5), `evaluate.py` (majority-class UAR reuse + new single-modality-baseline UAR utility, AD-17).
- Schema: `TimelineSegment` gained `fused_sentiment`/`fused_emotion`/`fused_confidence`/`single_modality_flag`/`disagreement_flag`; new `AnalysisResult` table (Call-level 1:1 aggregate). `disagreement_flag` is always persisted `0` — Story 1.9's scope, not this one, per Story 1.7's own explicit forward-decoupling dependency note.
- The fan-in trigger design (5 mutually-exclusive enqueue call sites feeding `run_fusion`, replacing the simple linear chaining every prior stage used) was the single most architecturally significant decision in this story — required because AD-1 mandates fusion runs whenever acoustic succeeds, regardless of where/whether the transcript branch completes. Fully covered by dedicated tests, one per site.
- `run_fusion` deliberately follows `run_ingest`/`run_acoustic`'s fail-hard pattern (rollback, `Call.status = "failed"`, re-raise) rather than Stories 1.4/1.5's fail-soft pattern — it is the only stage that can move `Call.status` to `complete`, so an internal failure here is a genuine Call-level failure, not an optional-enrichment failure.
- No new PyPI dependency, no new ML model, no `Dockerfile` changes — fusion is pure Python arithmetic/logic over already-computed, already-calibrated values from Stories 1.3/1.5.
- Test suite (initial implementation pass): `test_fuse.py`: 16, `test_overlap.py`: 6, `test_fusion_run.py`: 5, `test_fusion_evaluate.py`: 4, plus 5 fan-in enqueue tests folded into the existing `test_acoustic_run.py`/`test_transcript_run.py`/`test_sentiment_run.py` files. Full suite: 92 passed, ruff clean, `docker compose config --quiet` valid. (Code review, 2026-08-14: two more tests added during the patch round — see below — for a final total of 94.)

### File List

**Created:**
- `ml-service/app/pipeline/fusion/__init__.py`
- `ml-service/app/pipeline/fusion/fuse.py`
- `ml-service/app/pipeline/fusion/overlap.py`
- `ml-service/app/pipeline/fusion/run.py`
- `ml-service/app/pipeline/fusion/evaluate.py`
- `ml-service/tests/test_fuse.py`
- `ml-service/tests/test_overlap.py`
- `ml-service/tests/test_fusion_run.py`
- `ml-service/tests/test_fusion_evaluate.py`

**Modified:**
- `ml-service/app/db.py` (fusion schema + `FusedSegmentResult`/`AnalysisResultRow` NamedTuples + `persist_fusion_results`/`get_analysis_result`)
- `ml-service/app/config.py` (`FUSION_QUEUE_NAME`)
- `ml-service/app/queue.py` (`get_fusion_queue`)
- `ml-service/app/worker.py` (fifth queue registered)
- `ml-service/app/pipeline/acoustic/run.py` (fan-in site 1: transcript-enqueue-failure fallback)
- `ml-service/app/pipeline/transcript/run.py` (fan-in sites 2/3: text-sentiment-enqueue-failure fallback + outer-except fallback)
- `ml-service/app/pipeline/transcript/sentiment_run.py` (fan-in sites 4/5: success path + outer-except)
- `ml-service/tests/conftest.py` (`fake_fusion_queue` fixture)
- `ml-service/tests/test_acoustic_run.py` (fan-in site 1 test)
- `ml-service/tests/test_transcript_run.py` (fan-in sites 2/3 tests)
- `ml-service/tests/test_sentiment_run.py` (fan-in sites 4/5 tests)
- `docker-compose.yml` (comment accuracy: `ml-service` is now fully functional through Story 1.6, not "still placeholders")

**Temporary (created and removed during verification, not part of the final change set):**
- `ml-service/Dockerfile.dev`

## Change Log

### 2026-08-14 — Initial implementation

Implemented Story 1.6 (Multimodal Fusion into a Single Analysis Result): the `app/pipeline/fusion/` module (rule-based, confidence-weighted per-segment fusion + Call-level `AnalysisResult` reduction, AD-8), new `TimelineSegment` fusion columns and `AnalysisResult` table, the `run_fusion` RQ job (fail-hard, the only stage that writes `Call.status = "complete"`, FR-3), and the five-site enqueue fan-in that guarantees fusion always runs whenever acoustic succeeds regardless of the transcript branch's outcome (AD-1). `disagreement_flag` is wired but always `False` this story — Story 1.9's scope. 92/92 tests passing (20 new + 5 fan-in tests added to existing files), ruff clean, `docker compose config --quiet` valid. Status → review.

### 2026-08-14 — Code review

3-layer adversarial review (Blind Hunter, Edge Case Hunter, Acceptance Auditor): 1 decision-needed, 4 patch, 3 defer (added to `deferred-work.md`), 5 dismissed. User decision: zero-`TimelineSegment` Calls now complete with no `AnalysisResult` row (`None` = "no speech detected") instead of being marked `failed`. Patches applied: `run_fusion`'s success path made truly atomic (status write folded into `persist_fusion_results`'s own transaction); `_weighted_vote`'s tie-break behavior documented; a misattributed AD-1 citation corrected; a new test proving the documented cross-taxonomy vote-pooling behavior is stable. Re-verified: 94/94 tests passing, ruff clean, `docker compose config --quiet` valid. Status → done.
