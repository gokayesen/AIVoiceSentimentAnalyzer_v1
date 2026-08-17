---
baseline_commit: b3a0fce76bb52714607081122b1bcb11d210a4b8
---

# Story 3.3: Speaker-Attribution Failure & Uncertainty States

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an Analyst,
I want to be told plainly when speaker attribution isn't available at all, and separately when a specific turn's attribution is uncertain,
so that I can trust the labels I do see and know exactly which ones to question.

## Acceptance Criteria

1. **Given** a mono Call where diarization produces no usable speaker split at all (every `TranscriptTurn.speaker_label` is `NULL` for that Call), **When** this occurs, **Then** the whole Call gets a Call-level "attribution unavailable" state — the Call still produces a full Analysis Result per FR-16, just without a per-speaker breakdown (AD-6).
2. **Given** a mono Call where diarization succeeds overall but a specific turn's `speaker_confidence` (Story 3.2) is low, **When** this occurs, **Then** that turn gets a per-turn "uncertain" state, while the rest of the Call's attribution stands unaffected (AD-6).
3. **Given** these two states, **Then** they are represented distinctly, never conflated — a whole-Call "unavailable" state is not the same data/state as a per-turn "uncertain" state (AD-6).
4. **Given** a stereo Call, **Then** neither the whole-Call "unavailable" state nor the per-turn "uncertain" state ever applies — stereo channel-based attribution (Story 3.1) remains deterministic and always available, a decision this story does not reopen (AD-2). (Stereo turns' `speaker_confidence` is always `NULL`, Story 3.1 AC5 — never reopened here.)
5. **Given** a turn's diarization confidence (Story 3.2) and its Sentiment/Emotion confidence (Epic 1), **When** both exist on the same row, **Then** they remain two separate fields, never combined into a single score (AD-10) — already true since Story 3.2; this story does not change `TranscriptTurn`'s column shape.
6. **Given** the per-turn "uncertain" state, **When** it is triggered, **Then** it is based on the `speaker_confidence` value already captured in Story 3.2 being assessed as low, per AD-6's rule — this story introduces no new confidence-scoring algorithm, threshold model, or fallback mechanism; exact threshold mechanics remain implementation/config-level detail, not a new architectural decision.
7. **And** this story does not touch how these states are displayed — no frontend component, page, or copy string is authored or modified. It exposes both states as new fields in `GET /calls/{call_id}/transcript`'s response so Story 3.4 can wire them into the UI.

**Traceability:** FR-16; AD-6, AD-10.

## Tasks / Subtasks

- [x] Task 1: `SPEAKER_UNCERTAIN_THRESHOLD` config (AC 6)
  - [x] Add to `web-api/app/config.py`, directly mirroring `LOW_CONFIDENCE_THRESHOLD`'s existing pattern (lines 23-41): `os.environ.get("SPEAKER_UNCERTAIN_THRESHOLD", "0.5")`, parsed to `float` with a `try/except ValueError` raising a clear message naming the variable, then validated `0 <= SPEAKER_UNCERTAIN_THRESHOLD <= 1` raising if not. **Do not** reuse or rename `LOW_CONFIDENCE_THRESHOLD` — AD-10 requires the speaker-attribution confidence axis to stay a fully independent, separately-configured threshold from the Sentiment/Emotion one, exactly like `DISAGREEMENT_THRESHOLD` is already kept independent from it.
  - [x] No equivalent variable is needed in `ml-service/app/config.py` — unlike `LOW_CONFIDENCE_THRESHOLD` (which has an unconsumed placeholder copy there for an unrelated ordering check, see that file's own comment), this threshold's only consumer is web-api's response-building code (Task 2). Do not add an unused copy.

- [x] Task 2: Per-turn `speaker_uncertain` flag in `get_transcript` (AC 2, 3, 4, 6, 7)
  - [x] In `web-api/app/routers/calls.py`, add a small helper (same shape as the existing `_low_confidence_flag` at line 80 — read it first) e.g. `_speaker_uncertain_flag(speaker_confidence: float | None) -> bool`: returns `True` only when `speaker_confidence is not None and speaker_confidence < SPEAKER_UNCERTAIN_THRESHOLD`, else `False`. A `None` confidence (stereo turns always, per AC4/AC5; mono turns diarization never attributed) must return `False`, not `True` — "no confidence value exists" is not the same claim as "confidence is low" (AD-10's "never conflate" spirit extends to this derived value too).
  - [x] Import `SPEAKER_UNCERTAIN_THRESHOLD` alongside the existing `LOW_CONFIDENCE_THRESHOLD` import at the top of `calls.py`.
  - [x] In `get_transcript` (`calls.py:339-400`), add `"speaker_uncertain": _speaker_uncertain_flag(turn["speaker_confidence"])` to each turn's response dict. `turn["speaker_confidence"]` is already readable via the existing `SELECT *` in `db.get_transcript_turns` (Story 3.2's column) — no `db.py` change needed in either service. Follow `_low_confidence_flag`'s established rationale exactly: compute at read time from the already-stored column, never persist a redundant DB column (same "one hand-synced DDL column with nothing gained by storing it" reasoning, see that function's own docstring).
  - [x] Threshold comparison is strict `<` (matches `_low_confidence_flag`'s "strictly less than" convention) — a confidence exactly equal to the threshold is not flagged uncertain.

- [x] Task 3: Call-level `speaker_attribution_unavailable` flag in `get_transcript` (AC 1, 3, 4, 7)
  - [x] In the same `get_transcript` handler, after fetching `turns`, compute: `speaker_attribution_unavailable = bool(call["channel_count"] == 1 and turns and all(t["speaker_label"] is None for t in turns))`. `call` is already fetched via `db.get_call` earlier in the same function (line ~367) and its `channel_count` column is already selected via that function's existing `SELECT *`-style read — verify this before assuming a `db.py` change is needed (it should not be).
  - [x] Add `"speaker_attribution_unavailable": speaker_attribution_unavailable` as a **top-level** key in the response dict (alongside `call_id`/`status`/`turns`, not nested inside a turn) — this is a Call-level fact per AC1/AC3, structurally distinct from the per-turn `speaker_uncertain` flag (Task 2). Never conflate the two in one field.
  - [x] Stereo Calls (`channel_count == 2`) always compute `False` here structurally (the `channel_count == 1` guard), satisfying AC4 without any stereo-specific branch. A zero-turn complete Call (`turns == []` — "no speech detected", pre-existing case) must also compute `False` (guarded by `turns` being truthy) — there is nothing to have failed attribution on, so this is not the "unavailable" state; do not flag it.
  - [x] Update this endpoint's docstring (`calls.py:339-363`) to remove the now-stale "No `speaker_uncertain` key is added by this story either — that field belongs to Story 3.3's mono/diarization uncertainty state" sentence (currently line ~361-362) and describe both new fields instead, mirroring the docstring style already used for `speaker_label`.

- [x] Task 4: Doc-comment sync (AC 5)
  - [x] `web-api/app/db.py`'s `_CREATE_TRANSCRIPT_TURN_TABLE` comment (lines 108-118) currently ends with "turning it into the API-visible `speaker_uncertain` flag is Story 3.3's job, not this one's" — update it to state this story now does exactly that (query-time only, no new column), matching Task 2's actual implementation.
  - [x] No `ml-service/app/db.py` change is needed — `speaker_confidence`'s storage/comment there is unaffected; only the web-api read-side response contract changes.

- [x] Task 5: Tests
  - [x] `web-api/tests/test_transcript.py`: extend the local `_seed_turn` helper (line 36) with a `speaker_confidence: float | None = None` parameter, inserted into the existing raw-SQL `INSERT INTO TranscriptTurn` (add the column/placeholder). Extend the local `_make_call` helper (line 17) to optionally set `channel_count` — `db.insert_call` doesn't accept it (by design, Story 1.2/1.10 — only ml-service's ingest writes it); seed it via a direct `conn.execute("UPDATE Call SET channel_count = ? WHERE id = ?", ...)` after `insert_call`, mirroring how other tests in this file already issue raw SQL for fields `insert_call` doesn't cover.
  - [x] New tests for `speaker_uncertain` (Task 2): (a) a mono turn with `speaker_confidence` below the default threshold (e.g. `0.3`) returns `speaker_uncertain: true`; (b) a mono turn with `speaker_confidence` at or above threshold (e.g. `0.9`) returns `false`; (c) a turn with `speaker_confidence=None` (stereo, or unattributed mono) returns `false`, never `true`; (d) confidence exactly equal to the threshold returns `false` (strict `<`); (e) a custom `SPEAKER_UNCERTAIN_THRESHOLD` env var (via `monkeypatch`, same pattern as `test_custom_low_confidence_threshold_changes_flagging_behavior` at `test_timeline.py:211`) changes the flagging outcome.
  - [x] New tests for `speaker_attribution_unavailable` (Task 3): (a) mono Call (`channel_count=1`), all turns have `speaker_label=None` → `true`; (b) mono Call, at least one turn has a real `speaker_label` (others `None`) → `false` (diarization produced *some* usable split — AC1's "no usable speaker split at all" wording); (c) stereo Call (`channel_count=2`), all turns have `speaker_label=None` (a contrived/defensive case — should not occur in practice per Story 3.1, but must not accidentally flag) → `false`; (d) stereo Call with real `speaker_label` values → `false`; (e) mono Call with zero turns (`turns == []`) → `false`, not `true`.
  - [x] Confirm existing tests in this file (`test_complete_call_returns_turns_in_order_with_all_fields`, `test_transcript_returns_stereo_speaker_label`, `test_transcript_speaker_label_null_for_unattributed_turn`, `test_zero_turn_complete_call_returns_empty_transcript`) still pass — none of them set `channel_count`, so `call["channel_count"]` is `NULL`/`None` there; confirm `None == 1` correctly evaluates `False` in the `speaker_attribution_unavailable` computation (Python: `None == 1` is `False`, not a `TypeError` — safe as written, but verify with a real test run, not just by inspection).
  - [x] No `ml-service` test changes are needed — this story touches only `web-api`'s response-building code, not any ml-service pipeline stage or its own tests.

### Review Findings

- [x] [Review][Patch] `web-api/app/db.py`'s top-of-file module docstring still claims `speaker_confidence` is "never read or returned by `get_transcript`" — directly contradicted by the DDL-comment update a few dozen lines below (and by `get_transcript` itself), both now disagreeing within the same file [web-api/app/db.py:34-38]
- [x] [Review][Patch] `deferred-work.md`'s existing "no minimum-evidence floor" entry explicitly names this story ("Revisit when Story 3.3 designs the low-confidence/'uncertain' threshold logic...") as its trigger, and this story's own Dev Notes commit to "log it forward again... if still unaddressed" — the entry was never updated, left dangling with no acknowledgment that Story 3.3 shipped and (per AC6) deliberately declined to add one [_bmad-output/implementation-artifacts/deferred-work.md:131]
- [x] [Review][Patch] No test exercises a realistic mixed-state Call combining a confidently-attributed turn, a low-confidence/uncertain turn, and a fully unattributed turn together — every existing test varies at most one turn's fields, so an indexing/aggregation bug across multiple turns wouldn't be caught [web-api/tests/test_transcript.py]
- [x] [Review][Patch] No test proves `LOW_CONFIDENCE_THRESHOLD` and `SPEAKER_UNCERTAIN_THRESHOLD` actually stay independent (AD-10) — a future accidental aliasing of the two variables would pass every existing test in both `test_config.py` and `test_transcript.py` [web-api/tests/test_transcript.py, web-api/tests/test_config.py]
- [x] [Review][Defer] `speaker_attribution_unavailable`'s `channel_count == 1` guard never fires for a >2-channel Call — such a Call's turns are equally left unattributed by the pipeline (pre-existing gap, `deferred-work.md` line 3), but AC1's wording is explicitly scoped to "a mono Call," so extending the flag to cover it is a product-scope question outside this story's ACs, not a bug this diff introduced — deferred, pre-existing
- [x] [Review][Defer] `web-api/app/config.py`'s top-of-file docstring ("Fixed ingest constants (AD-20)... not operator-tunable") was already contradicted by `LOW_CONFIDENCE_THRESHOLD`/`DELETE_AWAIT_*` before this story added a fourth tunable — pre-existing drift, cosmetic, not this story's to fix — deferred, pre-existing

## Dev Notes

### Architecture compliance (binding, do not deviate)

- **AD-6** governs both new states (Call-level "attribution unavailable" and per-turn "uncertain"), **AD-10** governs keeping the two confidence axes (and their two derived flags) structurally separate. Neither AD is reopened or contradicted by this story's design — see the field-shape reasoning in Tasks 2/3 above.
- **This story is response-contract-only.** No new pipeline stage, no ml-service change, no new DB column in either service. It is the smallest possible change that satisfies the ACs: two new keys computed at `GET /calls/{call_id}/transcript` read time from columns Story 3.2 already persists (`speaker_label`, `speaker_confidence`) plus a Call column Story 1.2 already persists (`channel_count`).
- **AC6 explicitly forbids inventing a new confidence-scoring algorithm.** The `speaker_uncertain` flag is a bare threshold comparison against the existing `speaker_confidence` value — nothing more. Do not add a "minimum evidence floor" or any other refinement to how `speaker_confidence` itself is computed (that logic lives in `ml-service/app/pipeline/transcript/diarize.py`, untouched by this story) — a prior code review on Story 3.2 explicitly deferred that exact idea *to* this story's threshold design, and this story's own AC6 explicitly declines it. Log it forward again in `deferred-work.md` if still unaddressed (see Task list — no task currently asks for this, confirming it stays deferred).

### Where the flagging logic lives — reuse Story 1.8's established precedent exactly

`web-api/app/routers/calls.py`'s `_low_confidence_flag` (line 80) is the **direct precedent** for this story's `speaker_uncertain` flag: a threshold-driven boolean+optional-reason computed at API-response time from an already-stored, already-calibrated confidence column, deliberately never persisted to its own DB column. Its docstring (lines 90-97) explains why: "the flag is a pure function of an already-stored column... persisting it would mean one more hand-synced DDL column to keep byte-for-byte identical across web-api/ml-service (AD-7) for a value with nothing gained by storing it." Follow this exactly for `speaker_uncertain` — do not persist it, do not add it to either `db.py`'s DDL. (Unlike `_low_confidence_flag`, `speaker_uncertain` does not also need a `flag_reason` string — epics' AC/Story 3.4's UI contract only calls for the existing `uncertain` boolean variant on `SpeakerLabel`, populated with EXPERIENCE.md's already-defined static reason text ("overlapping speech — speaker attribution uncertain"), not a computed string. Do not invent a `flag_reason`-shaped field for this one; that would be scope creep beyond AC6/AC7.)

`web-api/app/db.py`'s own DDL comment (lines 116-118) already names this exact story ("turning it into the API-visible `speaker_uncertain` flag is Story 3.3's job") as the intended owner of this logic — confirming the placement (web-api response layer, not ml-service pipeline) is not a new design decision, it was reserved by Story 3.2.

### `speaker_attribution_unavailable` has no existing precedent to copy verbatim — reasoned from AD-6's exact wording

Unlike `speaker_uncertain`, no prior story computed an analogous whole-Call boolean from `channel_count` + an aggregate over `turns`. Derive it exactly as AD-6/AC1 state: "no usable speaker split for the Call **at all**" — i.e., *every* turn lacks `speaker_label`, not merely "the majority" or "some." A mono Call with even one successfully-attributed turn is not in this state (diarization *did* produce a usable split; other turns are just individually unattributed, an unrelated, already-handled `None` case predating this story — see Story 3.1/2.5's null-safe `SpeakerLabel` rendering). Do not build a percentage/majority threshold here — AC1's wording is exact ("no usable speaker split at all"), and any softer trigger would be a new, unrequested algorithm (out of scope, same AC6 discipline as the per-turn flag).

**Note for whoever picks up Story 3.4:** the frontend's current `AnalysisDashboard.tsx` (`hasNoSpeakerAttribution`, line 172) computes its own client-side approximation of this exact fact today (`turns.length > 0 && turns.every(t => !t.speaker_label)`) as an honest Epic-2-era placeholder, explicitly documented in that story's Dev Notes as "Epic 3 (`backlog`) supplies the real data." This story's new `speaker_attribution_unavailable` field is the real, channel-count-aware version of that same fact (the frontend's placeholder cannot distinguish "mono, failed" from "stereo, defensively-all-null," which should never happen but isn't structurally impossible without server-side channel-count knowledge) — Story 3.4 should replace the client-side heuristic with this field, not merely add to it. This story does not make that change itself (AC7).

### Previous Story Intelligence (Story 3.2 — the diarization/confidence producer this story consumes)

- Story 3.2 added `TranscriptTurn.speaker_cluster_id`/`speaker_confidence`. `speaker_confidence` is `NULL` for every stereo-attributed turn (Story 3.1 AC5, deterministic path, no confidence concept) and `NULL` for any mono turn diarization didn't attribute a speaker to at all (distinct from a turn that got attributed with a *low* confidence — the latter is exactly this story's per-turn "uncertain" trigger).
- Story 3.2's own code review deferred two items relevant here (`_bmad-output/implementation-artifacts/deferred-work.md`, "Deferred from: code review of 3-2..."): (1) `speaker_confidence` having no minimum-evidence floor — explicitly named as "Revisit when Story 3.3 designs the low-confidence/'uncertain' threshold logic" — resolved by this story's decision to *not* add one (AC6 forbids new scoring algorithms; a bare threshold on the existing value is the correct scope); (2) no `HF_TOKEN` onboarding docs — unrelated to this story, do not address it here.
- Story 3.2 verified all `ml-service` tests inside a `python:3.13.15-slim` Docker container (`torch==2.13.0` has no macOS x86_64/Intel wheel) — **not relevant to this story**, which touches zero ml-service code and zero ml-service tests. `web-api` has no such constraint; its test suite already runs natively in this dev environment's `.venv` (Story 3.1/3.2 both confirmed 87/87 passing there with no container).
- Story 3.1/3.2 both left `deferred-work.md` entries for the `TranscriptTurn` schema-migration gap (`speaker_label`/`speaker_channel_index`, then `speaker_cluster_id`/`speaker_confidence`) — **not applicable to this story**, which adds zero new DB columns.

### File List (expected)

- `web-api/app/config.py` — `SPEAKER_UNCERTAIN_THRESHOLD` (Task 1)
- `web-api/app/routers/calls.py` — `_speaker_uncertain_flag` helper, `get_transcript` response fields + docstring update (Task 2, 3)
- `web-api/app/db.py` — DDL comment sync only, no schema change (Task 4)
- `web-api/tests/test_transcript.py` — extended (Task 5)

No `ml-service` files are expected to change. No `frontend` files are expected to change (AC7).

### Project Structure Notes

- Everything in scope lives inside `web-api` — consistent with the Architecture's Capability → Architecture Map row for FR-16 ("`ml-service/pipeline/ingest` (channel detection) + `transcript` (diarization)" for the *producing* side; the *consuming/flagging* side for confidence-threshold logic was already established in `web-api`'s response contract by Story 1.8, per that story's own Dev Notes "Where the flagging logic lives").
- No new config/threshold value beyond `SPEAKER_UNCERTAIN_THRESHOLD` — same "tunable thresholds live in config, never hardcoded" rule (`ARCHITECTURE-SPINE.md` line 186) already followed by `LOW_CONFIDENCE_THRESHOLD`/`DISAGREEMENT_THRESHOLD`.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.3: Speaker-Attribution Failure & Uncertainty States]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#AD-6, AD-10]
- [Source: _bmad-output/implementation-artifacts/3-2-mono-diarization-via-whisperx-and-pyannote.md — full Dev Agent Record, Review Findings, deferred-work.md pointer]
- [Source: web-api/app/routers/calls.py — `_low_confidence_flag` (Story 1.8 precedent), `get_transcript` (Story 2.4/3.1/3.2)]
- [Source: web-api/app/config.py — `LOW_CONFIDENCE_THRESHOLD` (Story 1.8 precedent pattern to mirror)]
- [Source: web-api/app/db.py — `TranscriptTurn` DDL + comments (Story 3.1/3.2)]
- [Source: web-api/tests/test_transcript.py, web-api/tests/test_timeline.py — existing seeding/threshold-override test patterns]
- [Source: frontend/src/pages/AnalysisDashboard.tsx (`hasNoSpeakerAttribution`, line 172), frontend/src/api/callsApi.ts (`speaker_uncertain?: boolean`, line 95) — pre-existing Epic 2 placeholders this story's new fields are the real backend counterpart to, for Story 3.4 to wire up]
- [Source: _bmad-output/implementation-artifacts/deferred-work.md — "Deferred from: code review of 3-2-mono-diarization-via-whisperx-and-pyannote" section]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5 (claude-sonnet-5)

### Debug Log References

- No blockers encountered. Implementation matched the story's Dev Notes exactly: two new `get_transcript` response fields computed at read time from columns Story 3.2/1.2 already persist, no schema change, no ml-service change, no frontend change.
- Added `SPEAKER_UNCERTAIN_THRESHOLD` import/config-validation tests to `web-api/tests/test_config.py` (mirroring `LOW_CONFIDENCE_THRESHOLD`'s existing 5-test pattern exactly) even though not explicitly itemized as a Task 5 subtask — this repo's established convention is that every `[0,1]`-bounded config threshold gets its own subprocess-import-time boundary/malformed/valid test set (see that file's own docstring), and the story's own Task 1 introduces exactly such a threshold.

### Completion Notes List

- Implemented both states end-to-end as pure `web-api` response-contract additions: `SPEAKER_UNCERTAIN_THRESHOLD` config (mirrors `LOW_CONFIDENCE_THRESHOLD`'s validation pattern, kept fully independent per AD-10), `_speaker_uncertain_flag` (per-turn, strict `<` threshold on `speaker_confidence`, `None` → always `False`), and `speaker_attribution_unavailable` (Call-level, `channel_count == 1 AND turns non-empty AND every turn's speaker_label is None`) — both computed at `get_transcript` read time, never persisted, following `_low_confidence_flag`'s established Story-1.8 precedent exactly.
- All 7 Acceptance Criteria are met: AC1 (whole-Call unavailable state, mono + zero usable split), AC2 (per-turn uncertain state from `speaker_confidence`), AC3 (two structurally distinct fields — one top-level Call fact, one per-turn), AC4 (stereo never gets either state — `channel_count == 1` guard + `speaker_confidence` always `None` for stereo turns), AC5 (confidence axes stay separate — no schema change, verified unaffected), AC6 (no new confidence-scoring algorithm — bare threshold comparison only, independently configured), AC7 (zero frontend files touched — response-contract-only change, verified via `git diff --stat`).
- Updated `web-api/app/db.py`'s `TranscriptTurn` DDL comment (previously named this exact story as the owner of turning `speaker_confidence` into an API-visible flag) and `get_transcript`'s own docstring to describe both new fields, removing the now-stale forward-reference sentence.
- **Test verification:** `web-api` — 103/103 tests pass (`ruff check` clean), run in the existing host `.venv` (no Docker needed — this story touches zero ml-service/torch-dependent code). No `ml-service` tests were added or run; not applicable to this story's scope.

### File List

- `web-api/app/config.py` — `SPEAKER_UNCERTAIN_THRESHOLD` (Task 1)
- `web-api/app/routers/calls.py` — `_speaker_uncertain_flag` helper, `get_transcript` response fields + docstring (Task 2, 3)
- `web-api/app/db.py` — DDL comment sync only, no schema change (Task 4)
- `web-api/tests/test_transcript.py` — extended (Task 5)
- `web-api/tests/test_config.py` — extended (unplanned, but same established per-threshold test convention as `LOW_CONFIDENCE_THRESHOLD`; see Debug Log)

## Change Log

- 2026-08-17: Story implemented — `speaker_uncertain` (per-turn) and `speaker_attribution_unavailable` (Call-level) added to `GET /calls/{call_id}/transcript`, both computed at read time from Story 3.2/1.2's already-persisted columns, never persisted themselves (Task 1-5 complete, all ACs met). Pure `web-api` change: no ml-service, DB schema, or frontend files touched. Full regression suite green: 103/103, ruff-clean. Status: ready-for-dev → review.
- 2026-08-17: Code review (Blind Hunter + Edge Case Hunter + Acceptance Auditor, parallel, scoped to this story's own changes). 4 patch findings applied (fixed a self-contradicting `web-api/app/db.py` module docstring about `speaker_confidence` being read by `get_transcript`, closed the dangling `deferred-work.md` cross-reference this story's own Dev Notes committed to updating, added a mixed-state test combining confident/uncertain/unattributed turns in one Call, added a test proving `LOW_CONFIDENCE_THRESHOLD`/`SPEAKER_UNCERTAIN_THRESHOLD` stay independent). 2 findings deferred (`speaker_attribution_unavailable` doesn't cover >2-channel Calls — pre-existing gap, out of AC1's mono-only scope; `web-api/app/config.py`'s stale "not operator-tunable" docstring — pre-existing drift), both logged in `deferred-work.md`. 7 findings dismissed as noise (deliberate design choices already justified in Dev Notes, systemic pre-existing patterns not this story's to fix, and two Edge Case Hunter findings whose quoted code didn't match the actual implementation). Full regression suite re-verified green: 105/105, ruff-clean. Status: review → done.
