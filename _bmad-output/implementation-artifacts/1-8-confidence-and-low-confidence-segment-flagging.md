---
baseline_commit: NO_VCS
---

# Story 1.8: Confidence & Low-Confidence Segment Flagging

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an Analyst,
I want every Sentiment/Emotion value to show its confidence, and to be told plainly when confidence is low,
so that I don't mistake a shaky guess for a confident finding.

## Acceptance Criteria

1. **Given** any Sentiment/Emotion value (overall or per-segment), **When** returned by the API, **Then** it always carries a Confidence indicator — never returned without one (FR-10, AD-16).
2. **Given** a segment's calibrated confidence falls below a defined, configurable threshold, **Then** it is marked a Low-Confidence Segment with a paired `flag_reason` string — never a bare float on a flagged item.
3. **Given** a segment's confidence is at or above the acoustic sanity floor (Story 1.3, AD-1) but below the low-confidence threshold, **Then** it is a valid result — flagged as Low-Confidence, never invalidated or failed. The sanity floor and the low-confidence threshold are separate, independently-configured values serving different purposes (invalidity gate vs. flagging gate) and must never be conflated into one config key.
4. **Given** the threshold, **Then** it lives in config as `low_confidence_threshold`, never hardcoded in pipeline code.
5. **Given** a row carries both confidence axes, **Then** they are co-present as two separate fields on the same row — not merely reachable via a join (AD-10).
6. **And** this story does not itself claim the Confidence values are statistically calibrated or ground-truth-validated (NFR-2) — only that a documented threshold and calibration mechanism exist.

**Dependency (from epics.md):** requires Story 1.6 (fusion, for per-segment `fused_confidence`) and Story 1.7 (the `GET /calls/{call_id}/timeline` endpoint this story extends). No new endpoint is created — this story adds a flagging layer on top of Story 1.7's existing response shape, exactly as Story 1.7's own Dev Notes anticipated ("Story 1.8 will add the flagging layer on top later without changing this endpoint's core shape").

## Tasks / Subtasks

- [x] Task 1: `LOW_CONFIDENCE_THRESHOLD` config in `web-api` (AC: 3, 4)
  - [x] In `web-api/app/config.py`, add `LOW_CONFIDENCE_THRESHOLD = float(os.environ.get("LOW_CONFIDENCE_THRESHOLD", "0.5"))`. Use the **same env var name and default (`0.5`)** as `ml-service/app/config.py`'s existing `LOW_CONFIDENCE_THRESHOLD` (added in Story 1.3, unconsumed by any pipeline code there — see Dev Notes) so operators configure one value across both services' environment, hand-synced the same way `STORAGE_DIR`/`DB_PATH`/`REDIS_URL` already are between the two config files. Do **not** import `ml-service`'s config module (AD-7 service boundary — same rule as the `db.py` schema hand-sync).
  - [x] Add a startup validation: `if not 0 <= LOW_CONFIDENCE_THRESHOLD <= 1: raise ValueError(...)` — mirrors `ml-service/app/config.py`'s own import-time validation pattern (Consistency Conventions: "Confidence values are calibrated floats in `[0, 1]`"). Do **not** replicate `ml-service`'s `ACOUSTIC_SANITY_FLOOR < LOW_CONFIDENCE_THRESHOLD` ordering check here — `web-api` has no concept of the sanity floor (that gate is entirely internal to `ml-service`'s acoustic stage, AD-1) and never receives it; inventing a second copy of that check in `web-api` would be undocumented scope creep with nothing real to validate against.
  - [x] Create `web-api/tests/test_config.py`, mirroring `ml-service/tests/test_config.py`'s subprocess-based import-time pattern exactly (`import app.config` via `subprocess.run([sys.executable, "-c", ...])`, since env vars are only read once at module import and `app.config` is already imported with valid values by the time any test module loads). Cover: out-of-range threshold (e.g. `LOW_CONFIDENCE_THRESHOLD=1.5` or `-0.1`) raises at import with `LOW_CONFIDENCE_THRESHOLD` in stderr; a valid config imports cleanly.

- [x] Task 2: Low-confidence flagging logic (AC: 1, 2, 3)
  - [x] In `web-api/app/routers/calls.py`, add a small local helper (not a new module — this story's logic is a single two-line comparison, not a pipeline stage; no AD-21 "independently-runnable module" requirement applies here the way it does to `ml-service`'s pipeline filters) that, given a segment's `fused_confidence` and `config.LOW_CONFIDENCE_THRESHOLD`, returns whether it's low-confidence and, if so, a `flag_reason` string naming the actual confidence and threshold values (mirror `errors.py`'s message style — state the concrete numbers, not a generic phrase). Comparison is **strictly less than** (`confidence < threshold`) — AC2 says "falls below," and a value exactly at the threshold is not below it.
  - [x] `flag_reason` is `None` when the segment is not low-confidence — never an empty string or a placeholder message for a segment that isn't flagged (AC2's "never a bare float on a flagged item" only constrains the flagged case; an unflagged segment has nothing to explain).

- [x] Task 3: Extend `GET /calls/{call_id}/timeline`'s response (AC: 1, 2, 5)
  - [x] In `get_timeline` (`web-api/app/routers/calls.py`), add two fields to each segment dict: `low_confidence_flag` (bool) and `flag_reason` (str | None), computed via Task 2's helper from that segment's already-read `fused_confidence`. `fused_confidence` itself is already returned (Story 1.7) and is guaranteed non-`NULL` on every segment of a `complete` Call (Story 1.6's `persist_fusion_results` atomicity guarantee — see Story 1.7 Dev Notes) — AC1's "always carries a Confidence indicator" is already satisfied for the per-segment case by construction; this task only adds the flagging layer on top, it does not touch how `fused_confidence` itself is read or returned.
  - [x] Do **not** change the endpoint's route, method, 404/409 error behavior, or any other existing field — this is a pure additive change to the segment shape, per Story 1.7's own forward-decoupling note.
  - [x] `low_confidence_flag`/`fused_confidence` are two separate fields on the same segment dict (AC5) — never merged or only reachable by re-deriving one from the other.

- [x] Task 4: Tests (AC: 1, 2, 3, 4, 5)
  - [x] Extend `web-api/tests/test_timeline.py` (same file Story 1.7 created — this story augments the same endpoint, not a new one).
  - [x] New test: a segment seeded with `fused_confidence` below the default threshold (e.g. `0.3`) — assert `low_confidence_flag is True` and `flag_reason` is a non-empty string naming the actual confidence value.
  - [x] New test: a segment seeded with `fused_confidence` exactly equal to the default threshold (`0.5`) — assert `low_confidence_flag is False` and `flag_reason is None` (AC2's "falls below" is strict `<`, not `<=`).
  - [x] Above-threshold case: already covered implicitly by every existing test's `0.6`–`0.9` seeded `fused_confidence` values (none should regress to `low_confidence_flag: True`) — add an explicit `low_confidence_flag is False` assertion to the existing `test_complete_call_returns_multimodal_and_single_modality_segments` test on both its already-seeded segments, so the new field is verified in the same happy-path test that already exercises the rest of the shape.
  - [x] AC4/config: `web-api/tests/test_config.py` from Task 1 covers this — no additional endpoint-level test needed for the config mechanism itself.
  - [x] No test changes needed for AC3/AC5 beyond the above — both are structural invariants already satisfied by the existing schema and this story's additive-only change (see Task 3); confirm by inspection, not by inventing a new test with nothing new to assert.

- [x] Task 5: Full verification pass
  - [x] Run natively: `cd web-api && .venv/bin/pytest` (no Docker needed — same rationale as Story 1.7, `web-api` has no PyTorch/heavy-ML dependency).
  - [x] Run `.venv/bin/ruff check .` from `web-api/` — clean.
  - [x] Run `docker compose config --quiet` from the repo root — valid (no `docker-compose.yml` changes expected; `LOW_CONFIDENCE_THRESHOLD` is not added to the compose file since neither service overrides it there today — both already default to `"0.5"` in their respective `config.py`, so no compose change is needed for the two to agree. Confirm none were needed).

### Review Findings (AI)

- [x] [Review][Patch] `LOW_CONFIDENCE_THRESHOLD` env var parse failure produces an unlabeled `ValueError` for a malformed (non-numeric) value instead of a message naming the variable — the `float()` call isn't wrapped, so a typo like `"0.5x"` raises Python's raw `could not convert string to float` error before the custom range-check message is ever reached. [web-api/app/config.py:30] — **Fixed:** `float()` parse now wrapped in `try/except ValueError`, re-raising with a message naming `LOW_CONFIDENCE_THRESHOLD` and the raw offending value; new `test_low_confidence_threshold_malformed_raises_at_import_naming_the_variable` asserts on the final traceback line specifically (not the whole stderr blob, which trivially echoes the source line regardless).
- [x] [Review][Patch] `test_config.py` never tests the accepted boundary values (`0`, `1`) of the inclusive `[0, 1]` range — only clearly-out-of-range values (`1.5`, `-0.1`) are covered, leaving the range check's inclusivity unverified. [web-api/tests/test_config.py] — **Fixed:** added `test_low_confidence_threshold_lower_boundary_imports_cleanly` and `..._upper_boundary_imports_cleanly`.
- [x] [Review][Patch] No test exercises `GET /calls/{call_id}/timeline`'s flagging behavior with a non-default `LOW_CONFIDENCE_THRESHOLD` — every test relies on the default `0.5`; the endpoint's "operator-tunable" threshold (AC4) is untested where it actually matters. [web-api/tests/test_timeline.py] — **Fixed:** added `test_custom_low_confidence_threshold_changes_flagging_behavior`, using `monkeypatch.setattr(calls_module, "LOW_CONFIDENCE_THRESHOLD", 0.85)`.
- [x] [Review][Patch] The deliberate choice to compute `low_confidence_flag`/`flag_reason` live at read-time (never persisted on `TimelineSegment`) is explained at length in the story's Dev Notes but not documented anywhere in the code itself — a future reader of `calls.py`/`config.py` alone has no way to know this is intentional. [web-api/app/routers/calls.py] — **Fixed:** expanded `_low_confidence_flag`'s docstring with the rationale (AD-7 hand-sync cost, no benefit to persisting a pure function of an already-stored column, accepted retroactive-reflagging tradeoff).
- [x] [Review][Patch] `test_valid_config_imports_cleanly` doesn't explicitly pin `LOW_CONFIDENCE_THRESHOLD` in its env, relying on whatever value (if any) happens to be in the parent test process's ambient environment — a latent flakiness risk if an unrelated env var pollutes the run. [web-api/tests/test_config.py] — **Fixed:** now passes `{"LOW_CONFIDENCE_THRESHOLD": "0.5"}` explicitly.
- [x] [Review][Defer] `web-api`'s `LOW_CONFIDENCE_THRESHOLD` can silently drift from `ml-service`'s independently-configured copy (e.g. an operator setting it only in `web-api`'s environment) with no cross-service validation catching the mismatch [web-api/app/config.py] — deferred, pre-existing: same category of already-accepted architectural risk as every other hand-synced config value between the two services (`STORAGE_DIR`/`DB_PATH`/`REDIS_URL`); fixing it would require a cross-service consistency mechanism touching `ml-service`, which this story is explicitly forbidden from modifying. Mirrors Story 1.7's deferred finding about AD-13's boundary being enforced only by docstrings, no automated guard.
- [x] [Review][Defer] `web-api/app/config.py`'s module docstring ("Fixed ingest constants... not operator-tunable") is now further contradicted by the new operator-tunable `LOW_CONFIDENCE_THRESHOLD` [web-api/app/config.py:1] — deferred, pre-existing: the same docstring already misdescribed `STORAGE_DIR`/`DB_PATH`/`REDIS_URL` (all operator-tunable via env vars) before this story; not caused by this diff.

## Dev Notes

### Critical context — this story extends Story 1.7's endpoint, it does not build a new one

`web-api/app/routers/calls.py` currently has exactly two routes: `POST /calls` (Story 1.1) and `GET /calls/{call_id}/timeline` (Story 1.7). Story 1.7's own Dev Notes explicitly reserved this exact work: *"No low-confidence flagging/threshold (`flag_reason`, `low_confidence_threshold`) — that's Story 1.8, not built here. `fused_confidence` is returned as a bare float; Story 1.8 will add the flagging layer on top later without changing this endpoint's core shape (same forward-decoupling pattern as the disagreement flag)."* This story is that promised follow-up: add `low_confidence_flag`/`flag_reason` to the existing per-segment response dict. Do not create a second endpoint, a new router, or a new response shape — extend the one that exists.

### Where the flagging logic lives — `web-api`, not `ml-service` (confirmed by the architecture's own traceability table)

The Architecture spine's Capability → Architecture Map states explicitly: *"FR-14 / FR-15 (low-confidence flagging, no-certainty language) | `web-api` response contract | AD-16, AD-9."* This is authoritative: the flag is computed at API-response time in `web-api`, not persisted as a new column on `TimelineSegment` in `ml-service`. This was a deliberate architectural choice this story must not second-guess:
- Adding a new `TimelineSegment.low_confidence_flag` column would require the same AD-7 hand-sync-DDL discipline already carrying deferred risk from Stories 1.3/1.7 reviews (`PRAGMA foreign_keys`, no index, no `ORDER BY` tiebreaker, no `CHECK` constraint — see `deferred-work.md`) — one more column to keep byte-for-byte identical across two hand-maintained schema files, for a value that is a **pure, stateless function of an already-stored column** (`fused_confidence`). There is nothing to gain from persisting it.
- Computing it at read-time in `web-api` means the flag is always consistent with whatever `LOW_CONFIDENCE_THRESHOLD` is currently configured — no backfill/migration concern for Calls that completed under a different threshold value, and no risk of `ml-service` and `web-api` disagreeing about the threshold at write-time vs. read-time.
- `ml-service/app/config.py`'s own `LOW_CONFIDENCE_THRESHOLD` (added in Story 1.3, see its comment: *"not consumed by any code in this story"*) remains genuinely unconsumed by any `ml-service` pipeline code even after this story — it exists there only to (a) validate the `ACOUSTIC_SANITY_FLOOR < LOW_CONFIDENCE_THRESHOLD` ordering invariant at `ml-service` import time (AC3's ordering requirement) and (b) document the two thresholds' distinct semantics side by side. This story adds a **second, independent** `LOW_CONFIDENCE_THRESHOLD` constant to `web-api/app/config.py` — same env var name/default so operators set one value, but a structurally separate Python constant (AD-7: no cross-service import). Do not attempt to "fix" `ml-service`'s copy into being consumed, or to delete it as dead code — both are intentional per the ordering-validation rationale above, and removing `ml-service`'s copy would break its own `test_config.py::test_sanity_floor_at_or_above_low_confidence_threshold_raises_at_import` test.

### The acoustic sanity floor (AD-1) is structurally out of `web-api`'s reach — and that's fine

AC3 talks about the sanity floor vs. the low-confidence threshold, but `web-api` never sees a segment that failed the sanity floor: `GET /calls/{call_id}/timeline` only ever returns segments for a Call whose `status == "complete"` (Story 1.7's 409 gate), and per AD-1, a Call whose acoustic confidence fell below `ACOUSTIC_SANITY_FLOOR` never reaches `complete` at all — it fails outright, entirely inside `ml-service`, before `web-api` ever has anything to read. So by construction, every segment this endpoint returns already has confidence `>= ACOUSTIC_SANITY_FLOOR`; `web-api` does not need to check this itself, and has no `ACOUSTIC_SANITY_FLOOR` value to check against even if it wanted to (that constant lives only in `ml-service/app/config.py`, never shared). AC3 is satisfied by the existing cross-service architecture, not by new code in this story — do not add a redundant floor check in `web-api`.

### What NOT to build in this story

- **No new endpoint.** See "Critical context" above — this is an additive change to Story 1.7's existing response.
- **No `overall`/Call-level confidence endpoint.** AC1 mentions "overall or per-segment," but there is currently no Epic-1 API surface that returns the Call-level `AnalysisResult` (`overall_confidence` etc.) — `web-api/app/db.py` has no `AnalysisResult` reader at all, and epics.md's own Capability map assigns FR-12 ("full Analysis Result view") to Story 2.4 (Epic 2, dashboard), not any Epic 1 story. Building a new `GET /calls/{call_id}/result`-style endpoint is out of scope here — it is not in this story's Task list and inventing one would be undocumented scope creep. This story enforces AC1's confidence-indicator invariant on every API surface that **currently exists** (the timeline endpoint); whenever Epic 2 eventually builds a full-result endpoint, it inherits the same invariant (`overall_confidence` must always be present — it already is, `AnalysisResult.overall_confidence` is `NOT NULL` in `ml-service/app/db.py`'s schema) and should follow this story's exact `low_confidence_flag`/`flag_reason` pattern for `AnalysisResult`-level flagging if that's ever required — not this story's problem to solve now.
- **No persisted `low_confidence_flag` column** on `TimelineSegment` or `AnalysisResult` — see "Where the flagging logic lives" above.
- **No changes to `ml-service`.** This story is entirely `web-api`-side, same as Story 1.7. `ml-service/app/config.py`'s existing `LOW_CONFIDENCE_THRESHOLD` is read-only reference material here — read to confirm the env var name/default to mirror, never modified.
- **No real calibration work.** AC6/NFR-2: this story does not claim `fused_confidence` is statistically calibrated — it already carries `ml-service`'s AD-9 temperature-scaling placeholder (a documented no-op for MVP, see `ml-service/app/config.py`'s `ACOUSTIC_TEMPERATURE`/`TEXT_SENTIMENT_TEMPERATURE` comments); this story only adds threshold comparison and flagging on top of whatever confidence value is already there, not a new calibration mechanism.
- **No UI/visual distinction.** FR-14 ("Dashboard visually distinguishes Low-Confidence Segments") is Epic 2 territory (Story 2.4/2.5), consuming the `low_confidence_flag` field this story produces — not built here.

### AD-10 (AC5) — already satisfied, verify don't violate

`fused_confidence` and `low_confidence_flag` are two separate fields on the same segment dict (this story adds `low_confidence_flag` alongside, not instead of, `fused_confidence`) — satisfies AC5's letter directly. AD-10's deeper concern (Sentiment/Emotion confidence vs. speaker-attribution/diarization confidence never conflated) doesn't yet have a second confidence axis to guard against in Epic 1's built scope — diarization/speaker-attribution confidence is Epic 3 (Story 3.2) territory, not yet implemented. Nothing to build here beyond not regressing the one axis that exists; Epic 3 will need to add its own confidence field alongside these, never merged, when it lands.

### Previous story intelligence (Story 1.7)

- Story 1.7 built `GET /calls/{call_id}/timeline`, returning per-segment `segment_id`, `start_time`, `end_time`, `fused_sentiment`, `fused_emotion`, `fused_confidence`, `disagreement_flag`. This story adds `low_confidence_flag`/`flag_reason` to that same list — five existing tests in `test_timeline.py` already seed segments with `fused_confidence` values (`0.9`, `0.6`, `0.75` default, `0.8`, `0.7`) all comfortably above the `0.5` default threshold; none of them should start returning `low_confidence_flag: True` as a side effect of this story — verify this explicitly (Task 4) rather than assuming it.
- Story 1.7's code review deferred (not fixed) several `TimelineSegment`-schema gaps (missing index, `PRAGMA foreign_keys`, `ORDER BY` tiebreaker, no `CHECK` constraint) specifically because fixing them asymmetrically across `web-api`/`ml-service`'s hand-synced DDL would itself introduce schema divergence (AD-7). This story doesn't touch the DDL at all (see "Where the flagging logic lives" above), so none of those deferred items are this story's concern — do not attempt to fix them here as a "while I'm in this file" cleanup.
- Story 1.7 established the native-`.venv` verification path for `web-api` (no Docker needed, unlike every `ml-service` story) — this story follows the same path (Task 5).
- Story 1.7's `_make_call`/`_seed_segment` local test helpers in `test_timeline.py` already accept `fused_confidence` as a keyword argument (default `0.75`) — reuse them as-is for this story's new tests; no new test helper needed.

### Architecture compliance (non-negotiable)

- **AD-1** — the acoustic sanity floor remains entirely `ml-service`-internal; this story does not duplicate or check it in `web-api` (see dedicated section above).
- **AD-7** — no cross-service import; `web-api/app/config.py`'s `LOW_CONFIDENCE_THRESHOLD` is a hand-synced mirror of `ml-service`'s (same env var/default), not a shared import.
- **AD-9** — `fused_confidence` is already calibrated (temperature scaling, MVP no-op) before this story ever sees it; this story adds no new calibration step.
- **AD-10** — `low_confidence_flag` and `fused_confidence` co-present as separate fields on the same segment (AC5).
- **AD-13** — no change to `web-api`'s DB access pattern; this story reads no new table and writes nothing new, it only adds a computed (non-persisted) field to an existing read response.
- **AD-16** — a flagged segment always carries its `flag_reason` alongside; no segment's Sentiment/Emotion is ever presented without its accompanying confidence (already true since Story 1.7; unchanged here).
- **AD-21** — covered by this story's endpoint-level tests in `test_timeline.py` (Task 4) and `test_config.py` (Task 1); no separate pipeline-style module is introduced that would need its own dedicated unit-test file.
- **FR-10** — Confidence indicator always present (per-segment, already true) + low-confidence threshold marking (this story's core addition).
- **NFR-2** — no calibration claim made; see "What NOT to build."

### Testing Standards

- Extend `web-api/tests/test_timeline.py` (Story 1.7's file) — do not create a second timeline test file.
- Create `web-api/tests/test_config.py`, mirroring `ml-service/tests/test_config.py`'s subprocess-import pattern exactly (env vars are read once at `app.config` import time; a plain `importlib.reload` is insufficient once `app.config` has already been imported elsewhere in the test session with valid values).
- Run natively: `cd web-api && .venv/bin/pytest` (no Docker, no model downloads).
- `.venv/bin/ruff check .` from `web-api/`.
- `docker compose config --quiet` from repo root (sanity check only — no compose changes expected).

### Project Structure Notes

- Modify: `web-api/app/config.py` (add `LOW_CONFIDENCE_THRESHOLD` + `[0, 1]` bounds validation).
- Modify: `web-api/app/routers/calls.py` (add the flagging helper; extend `get_timeline`'s per-segment response dict with `low_confidence_flag`/`flag_reason`).
- Modify: `web-api/tests/test_timeline.py` (new/extended tests for the two new fields).
- Create: `web-api/tests/test_config.py`.
- No changes to `web-api/app/db.py`, `web-api/app/errors.py`, `web-api/app/main.py`, `web-api/app/queue.py`, `web-api/app/audio_validation.py`, `docker-compose.yml`, or anything under `ml-service/`.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.8: Confidence & Low-Confidence Segment Flagging] (lines 265–278, AC text)
- [Source: _bmad-output/planning-artifacts/epics.md#FR-10] (line 29, exact FR text: "Every Sentiment/Emotion judgment (overall and per-timeline-segment) carries a Confidence indicator; segments below a defined threshold are marked Low-Confidence Segments")
- [Source: epics.md#FR-14] (line 33, Epic 2 UI-visual-distinction — out of this story's scope)
- [Source: epics.md#NFR-2] (line 40, Confidence honesty — no calibration claim)
- [Source: epics.md#Story 1.3: Mandatory Acoustic Analysis (SER)] (line 192, the sanity-floor-vs-low-confidence-threshold distinction, verbatim origin of this story's AC3)
- [Source: epics.md#Story 2.4: Analysis Dashboard — Summary Cells & Full Result View] (lines 372–390, confirms FR-12/the "overall" retrieval surface is Epic 2, not Epic 1)
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#AD-1] (line 35, acoustic sanity floor, entirely ml-service-internal)
- [Source: ARCHITECTURE-SPINE.md#AD-9] (lines 102–106, temperature-scaling-only calibration, MVP no-op)
- [Source: ARCHITECTURE-SPINE.md#AD-10] (lines 108–112, two confidence axes never conflated)
- [Source: ARCHITECTURE-SPINE.md#AD-16] (lines 144–148, no autonomous final verdicts — confidence+evidence always paired)
- [Source: ARCHITECTURE-SPINE.md#Consistency Conventions] (line 185, "Confidence values are calibrated floats in `[0, 1]`; any confidence that crosses a flagging threshold is paired with a `flag_reason` string — never a bare float on a flagged item" — verbatim origin of AC2's wording)
- [Source: ARCHITECTURE-SPINE.md#Capability → Architecture Map] (line 274, "FR-10 (confidence + threshold) | `ml-service/pipeline/calibration` | AD-9, AD-10" — confirms calibration itself is ml-service's concern, already done by Story 1.5/1.3; line ~277, "FR-14/FR-15 ... | `web-api` response contract | AD-16, AD-9" — confirms flagging itself belongs in `web-api`)
- [Source: web-api/app/config.py] (full file read — existing env-var-with-local-fallback pattern to extend)
- [Source: ml-service/app/config.py] (full file read — existing `LOW_CONFIDENCE_THRESHOLD`/`ACOUSTIC_SANITY_FLOOR` definitions and ordering-validation precedent to mirror, lines 54–100)
- [Source: ml-service/tests/test_config.py] (full file read — subprocess-based import-time validation test pattern to mirror)
- [Source: web-api/app/errors.py] (full file read — message-with-actual-values style to mirror in `flag_reason`)
- [Source: web-api/app/routers/calls.py] (full file read — current `get_timeline` implementation this story extends)
- [Source: web-api/app/db.py] (full file read — confirms `fused_confidence` is `REAL` with no `NOT NULL` at the DDL level, but is guaranteed populated on any `complete` Call's segments by `ml-service`'s `persist_fusion_results` atomicity, per Story 1.7 Dev Notes)
- [Source: web-api/tests/test_timeline.py] (full file read — existing `_make_call`/`_seed_segment` helpers and seeded confidence values to reuse/verify against)
- [Source: _bmad-output/implementation-artifacts/1-7-emotional-timeline-retrieval.md] (Dev Notes' "What NOT to build" section — verbatim forward-reservation of this story's scope; Review Findings — deferred `TimelineSegment` schema gaps this story must not touch)

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5

### Debug Log References

- Followed strict RED-GREEN per task: wrote `web-api/tests/test_config.py` first (mirroring `ml-service/tests/test_config.py`'s subprocess-import pattern), confirmed 2/3 tests failed (`LOW_CONFIDENCE_THRESHOLD` not yet defined, so out-of-range values didn't raise), then added the config constant + `[0, 1]` bounds validation — all 3 passed.
- Extended `web-api/tests/test_timeline.py` with 2 new tests (below-threshold, exactly-at-threshold) plus new assertions on the existing happy-path test — confirmed 3/12 failed (`KeyError: 'low_confidence_flag'`) before implementing `_low_confidence_flag()` and wiring it into `get_timeline`'s response — all 12 passed after.
- Verified by direct inspection of `ml-service/app/config.py` that its own `LOW_CONFIDENCE_THRESHOLD` remains genuinely unconsumed by any pipeline code even after this story (it only guards the `ACOUSTIC_SANITY_FLOOR` ordering check there) — confirmed no `ml-service` changes were needed or made.
- Confirmed via the architecture spine's Capability → Architecture Map that flagging belongs in `web-api`'s response contract (not a new `ml-service`-side persisted column) before choosing the read-time-computation design — no schema/DDL changes were made to either service's `db.py`.

### Completion Notes List

- Added `LOW_CONFIDENCE_THRESHOLD` to `web-api/app/config.py` (same env var name/default `0.5` as `ml-service`'s existing, unconsumed copy — hand-synced per AD-7, not imported), with `[0, 1]` bounds validation at import time.
- Added `_low_confidence_flag()` helper and wired `low_confidence_flag`/`flag_reason` into `GET /calls/{call_id}/timeline`'s existing per-segment response (Story 1.7's endpoint) — no new route, no schema/DDL changes in either service.
- Comparison is strictly `<` threshold (AC2 "falls below"); `flag_reason` is `None` when not flagged, otherwise a message naming the actual confidence and threshold values.
- All verification ran natively via `web-api/.venv` (no Docker needed, same as Story 1.7). Full suite: 41 passed (12 in `test_timeline.py` + 3 new in `test_config.py` + 26 pre-existing in `test_upload.py`, no regressions). `ruff check .`: clean. `docker compose config --quiet`: valid, no compose changes needed.

### File List

**Modified:**
- `web-api/app/config.py` — added `LOW_CONFIDENCE_THRESHOLD` (env-var-with-default, `[0, 1]` bounds validation).
- `web-api/app/routers/calls.py` — added `_low_confidence_flag()` helper; extended `get_timeline`'s per-segment response with `low_confidence_flag`/`flag_reason`; updated module docstring.
- `web-api/tests/test_timeline.py` — added `test_below_threshold_confidence_is_flagged_low_confidence`, `test_confidence_exactly_at_threshold_is_not_flagged`; extended the existing happy-path test with `low_confidence_flag`/`flag_reason` assertions on both segments.

**Created:**
- `web-api/tests/test_config.py` — 6 tests covering `LOW_CONFIDENCE_THRESHOLD` validation (above 1, below 0, malformed non-numeric, lower/upper inclusive boundary, valid import), mirroring `ml-service/tests/test_config.py`'s pattern.

### Code review follow-up (2026-08-14)

3-layer adversarial review (Blind Hunter, Edge Case Hunter, Acceptance Auditor) ran against the full NO_VCS diff (1 new + 3 modified files, 582-line scratchpad representation). Outcome: 0 decision-needed, 5 patch, 2 defer, 6 dismissed as noise.

- **Acceptance Auditor**: 6/6 ACs individually confirmed PASS, plus every explicitly-flagged binding constraint (strict `<` comparison, `flag_reason is None` when unflagged, no route/schema/`ml-service` changes, `[0, 1]` import-time validation, no sanity-floor check in `web-api`). One non-blocking cosmetic observation (config.py's module docstring) became a defer.
- **Blind Hunter / Edge Case Hunter**: raised 15 items across both; after dedup (NULL-confidence and malformed-threshold and ambient-env each raised by both layers, merged to 1 each) → 12 unique findings. 5 became patches, 2 became new `deferred-work.md` entries (cross-service threshold-drift risk, stale module docstring), and 6 were dismissed after actually re-reading the code: NULL `fused_confidence` reachability was refuted by re-reading `ml-service/app/pipeline/fusion/run.py` directly — confirmed the *only* two paths to `Call.status = "complete"` are the zero-segment early-return (where `get_timeline`'s segment loop never executes at all) and `persist_fusion_results` (which writes every segment's `fused_confidence` and the status transition in one atomic transaction) — no reachable path leaves a `complete` Call's segment with a NULL `fused_confidence`. A claimed "provenance comment contradiction" between `web-api`'s and `ml-service`'s config comments was refuted by re-reading `ml-service/app/config.py` directly — "this story" in its comment refers to Story 1.3 (which wrote that file), not Story 1.8; both comments agree the constant was declared in Story 1.3 and remains unconsumed by `ml-service` code. The remaining three dismissals (flag_reason not machine-readable, subprocess test pattern "copy-fitted," float-epsilon boundary comparison) were refuted as out-of-AC-scope, already-justified-by-design, and no-concrete-failure-scenario respectively.
- Applied all 5 patches: wrapped `LOW_CONFIDENCE_THRESHOLD`'s `float()` parse to name the variable on a malformed value, added boundary-value tests (`0`, `1`), added an end-to-end non-default-threshold test via `monkeypatch`, expanded `_low_confidence_flag`'s docstring with the live-recompute-not-persisted rationale, and pinned `LOW_CONFIDENCE_THRESHOLD` explicitly in the previously-ambient-env-dependent test.
- Re-verified after patches: 45/45 tests passed (41 + 4 new — 3 in `test_config.py`, 1 in `test_timeline.py`), `ruff check .` clean, `docker compose config --quiet` valid.

## Change Log

### 2026-08-14 — Initial implementation

Added `LOW_CONFIDENCE_THRESHOLD` config to `web-api` (hand-synced with `ml-service`'s existing, unconsumed copy per AD-7) and a `low_confidence_flag`/`flag_reason` layer on top of Story 1.7's `GET /calls/{call_id}/timeline` response — no new endpoint, no schema changes in either service, matching Story 1.7's own forward-decoupling note. All 6 ACs covered by 5 new tests (3 in `test_config.py`, 2 in `test_timeline.py`) plus extended assertions on the existing happy-path test. Full `web-api` suite: 41/41 passed (native `.venv`, no Docker required). `ruff check .` clean, `docker compose config --quiet` valid. Status: ready-for-dev → review.

### 2026-08-14 — Code review

3-layer adversarial review resolved: 5 patch findings fixed (clear malformed-config error message, boundary-value tests, non-default-threshold end-to-end test, live-recompute design-rationale code comment, deterministic ambient-env-independent test). 2 findings deferred to `deferred-work.md` (cross-service `LOW_CONFIDENCE_THRESHOLD` drift risk, stale config-module docstring). 6 dismissed as refuted after re-reading `ml-service/app/pipeline/fusion/run.py` and `ml-service/app/config.py` directly. Re-verified: 45/45 tests passed, `ruff check .` clean, `docker compose config --quiet` valid. Status: review → done.
