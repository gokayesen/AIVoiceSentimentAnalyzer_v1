---
baseline_commit: b3a0fce76bb52714607081122b1bcb11d210a4b8
---

# Story 3.1: Stereo Channel-Based Speaker Attribution

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an Analyst,
I want stereo Calls to have their speech automatically attributed to agent/customer by channel,
So that I see a per-speaker breakdown without needing a diarization model to run.

## Acceptance Criteria

1. **Given** a Call detected as stereo (`channel_count == 2`, from Story 1.2's `detect_channel_count`), **When** speaker attribution runs, **Then** speaker identity is assigned deterministically by channel index — no diarization model runs for this Call (AD-2).
2. **Given** stereo channel-based attribution, **When** speaker identity is exposed to the API/UI, **Then** it uses a canonical generic label (`"Speaker A"` / `"Speaker B"`), never the raw channel index directly (AD-2).
3. **Given** stereo channel-based attribution, **When** the channel index is used internally, **Then** it is stored as separate internal provenance metadata, never as the display-facing label itself (AD-2).
4. **Given** a stereo Call, **When** attribution completes, **Then** it applies to every `TranscriptTurn` in the Call — no path may skip attribution and silently label all speech as one undifferentiated speaker (AD-2).
5. **Given** stereo channel-based attribution is deterministic, **Then** it carries no per-turn confidence/uncertainty state — only the mono/diarization path (Stories 3.2/3.3) can produce a low-confidence or uncertain attribution outcome; this decision is preserved as-is, not reopened by this story.
6. **And** this story does not implement mono-path diarization (Story 3.2) or any failure/uncertainty state (Story 3.3).

**Traceability:** FR-16; AD-2.

## Tasks / Subtasks

- [x] Task 1: Schema — add `speaker_label`/`speaker_channel_index` to `TranscriptTurn` (AC 2, 3)
  - [x] In `ml-service/app/db.py`'s `_CREATE_TRANSCRIPT_TURN_TABLE`, add two nullable columns: `speaker_label TEXT` (the canonical `"Speaker A"`/`"Speaker B"` display value) and `speaker_channel_index INTEGER` (internal provenance only — never returned by any API endpoint). Follow the exact same "edit the `CREATE TABLE IF NOT EXISTS` string in place" pattern every prior story used for this table (Story 1.5's `text_*` columns, Story 1.4's base columns) — this codebase has no `ALTER TABLE` migration mechanism (see Dev Notes).
  - [x] Mirror the identical DDL change, column-for-column, in `web-api/app/db.py`'s `_CREATE_TRANSCRIPT_TURN_TABLE` (AD-7 hand-sync discipline — web-api never imports ml-service's `db.py`).
  - [x] Update both files' module/table docstrings to note "Story 3.1 added `speaker_label`/`speaker_channel_index`", matching the existing changelog-in-comments convention at the top of `ml-service/app/db.py`.

- [x] Task 2: `assign_stereo_speaker` — deterministic per-turn channel attribution (AC 1, 2, 3)
  - [x] Create `ml-service/app/pipeline/transcript/speaker.py`. Implement `assign_stereo_speaker(raw_waveform: torch.Tensor, sample_rate: int, *, start_time: float, end_time: float) -> tuple[int, str] | None`: slices `raw_waveform[:, start_sample:end_sample]` (converting `start_time`/`end_time` — Call-absolute float seconds — to sample indices via `sample_rate`, the *original* audio sample rate, not `VAD_SAMPLE_RATE`), computes mean-squared energy per channel (`.pow(2).mean(dim=-1)`), and returns `(channel_index, label)` for the higher-energy channel via `argmax`. Returns `None` for a degenerate (zero/negative-width, after clipping to `[0, raw_waveform.shape[-1]]`) window — mirror `transcript/run.py`'s existing zero-width-segment guard rather than raising.
  - [x] Define the canonical label lookup as a fixed 2-element table (`("Speaker A", "Speaker B")`), consistent with AD-4's "fixed lookup table" convention elsewhere in this pipeline. Do not build anything that accepts more than 2 channels — see Dev Notes on the `channel_count > 2` gap.
  - [x] Write direct unit tests for `assign_stereo_speaker` against synthetic 2-channel `torch.Tensor`s with known per-channel energy (no audio file I/O needed) — this is the fast, precise way to prove the channel→label mapping and the degenerate-window `None` case, independent of STT.

- [x] Task 3: Wire attribution into `run_transcript` (AC 1, 4, 6)
  - [x] In `ml-service/app/pipeline/transcript/run.py`, capture the `raw_waveform` and `sample_rate` returned by `load_mono_waveform` (currently discarded as `_raw_waveform`/`_sample_rate` — see Dev Notes) and determine `channel_count` by reusing `app.pipeline.ingest.channel.detect_channel_count(raw_waveform)` (do **not** add a new DB read of `Call.channel_count` — this avoids an extra query and keeps the channel-count source-of-truth identical to what `run_ingest` itself persisted from the very same tensor shape).
  - [x] Only when `channel_count == 2`: for every `TurnResult` produced by `transcribe_segment` (per segment, inside the existing loop), call `assign_stereo_speaker(raw_waveform, sample_rate, start_time=turn.start_time, end_time=turn.end_time)` and carry the `(channel_index, label)` (or `None`) through into `turn_rows`. When `channel_count != 2` (mono, or >2 — see Dev Notes), every turn's `speaker_label`/`speaker_channel_index` stay `None` — this story does not touch the mono path (AC 6).
  - [x] Extend `turn_rows` tuples from `(id, call_id, turn_index, start_time, end_time, text)` to `(id, call_id, turn_index, start_time, end_time, text, speaker_label, speaker_channel_index)`.

- [x] Task 4: Persist the two new columns (AC 1, 2, 3, 4)
  - [x] Update `ml-service/app/db.py`'s `persist_transcript_turns`: extend its `turns` parameter's documented tuple shape and its `INSERT INTO TranscriptTurn (...)` column list/placeholders to include `speaker_label, speaker_channel_index`. Keep the existing single-transaction/one-commit-with-words atomicity guarantee unchanged.

- [x] Task 5: Expose `speaker_label` via the transcript API (AC 2)
  - [x] In `web-api/app/routers/calls.py`'s `get_transcript`, add `"speaker_label": turn["speaker_label"]` to each turn's response dict. Do **not** add `speaker_channel_index` or a `speaker_uncertain` key in this story — the frontend's `TranscriptTurn` type (`frontend/src/api/callsApi.ts`) already declares `speaker_label?: string | null` and `speaker_uncertain?: boolean` as optional; `speaker_uncertain` is Story 3.3's field to populate (mono/diarization uncertainty only — AC5 of this story explicitly forbids inventing a confidence/uncertainty state for the deterministic stereo path). Omitting the key entirely (rather than sending `speaker_uncertain: false`) keeps this story's diff minimal and matches the field's `?` optionality.

- [x] Task 6: Tests
  - [x] `ml-service/tests/test_speaker.py` (new): unit tests for `assign_stereo_speaker` per Task 2.
  - [x] `ml-service/tests/test_transcript_run.py`: add a stereo end-to-end test that monkeypatches `transcribe_segment` (same technique as the existing `_flaky`/canned-`TurnResult` tests in this file) to return known turns, supplies a real 2-channel waveform fixture with distinguishable per-channel energy (see Dev Notes — the existing `stereo.wav` fixture is *not* usable for this, both channels are identical), and asserts the persisted `TranscriptTurn` rows carry the expected `speaker_label`. Add a companion mono test asserting `speaker_label` stays `None` (regression guard that this story doesn't touch the mono path).
  - [x] `web-api/tests/test_transcript.py`: extend `_seed_turn`'s `INSERT` and add a test asserting `get_transcript`'s response includes the seeded `speaker_label`, plus a test asserting a `None` `speaker_label` round-trips as JSON `null` (mono/no-attribution case, matching this file's existing `test_zero_turn_complete_call_returns_empty_transcript`-style precedent for "valid, not an error" absence states).

### Review Findings

- [x] [Review][Patch] `assign_stereo_speaker` has no defensive guard against non-finite turn timestamps or unexpected channel counts; an exception there discards the whole Call's already-computed transcript [ml-service/app/pipeline/transcript/speaker.py, ml-service/app/pipeline/transcript/run.py]
- [x] [Review][Patch] Tie-break behavior (equal per-channel energy resolves to channel 0/"Speaker A" via `argmax`) is undocumented — deserves an explanatory comment given AC5 forbids any uncertainty signal here [ml-service/app/pipeline/transcript/speaker.py]
- [x] [Review][Patch] `web-api/app/db.py`'s top-of-file changelog docstring was not updated with a Story 3.1 entry (Task 1's third bullet) — only a local DDL comment was added [web-api/app/db.py:1]
- [x] [Review][Patch] No test proves stereo attribution applies to every `TranscriptTurn` when a Call has multiple turns (AC4) — all three new tests seed a single turn [ml-service/tests/test_transcript_run.py]
- [x] [Review][Patch] No regression test proves a >2-channel Call falls through to unattributed behavior (the `channel_count == 2` gate, not `>= 2`) [ml-service/tests/test_transcript_run.py]
- [x] [Review][Patch] `deferred-work.md` was not updated: no new entry logging the pre-existing-local-DB break window for the new columns (every prior schema-adding story logged this), and the Story-2.6-review entry that named "Story 3.1" as its trigger was never updated now that this story has landed [_bmad-output/implementation-artifacts/deferred-work.md]
- [x] [Review][Defer] Test fixtures only cover the trivial best case (full-amplitude tone vs. pure silence per channel) — no crosstalk/near-tie scenario is tested, which is where this energy-comparison heuristic is most likely to misbehave on real captured audio [ml-service/tests/conftest.py, ml-service/tests/test_speaker.py] — deferred, pre-existing test-fidelity pattern; building a realistic crosstalk fixture is disproportionate effort for MVP, same category as AD-17's "evaluation-phase tuning" deferrals

## Dev Notes

### Architecture compliance (binding, do not deviate)

- **AD-2** is the sole governing rule for this story. Stereo → channel-index assignment, no diarization; the display label is always the canonical `"Speaker A"`/`"Speaker B"`, never the raw channel index; the channel index is retained only as internal provenance.
- **Label text conflict — use `"Speaker A"`/`"Speaker B"`, not `"Agent"`/`"Customer"`.** `DESIGN.md` (line 234) describes the Speaker label component as showing "Agent"/"Customer", but `ARCHITECTURE-SPINE.md`'s AD-2 and every one of this epic's Acceptance Criteria (Stories 3.1's AC2, 3.2's AC4, 3.4's AC1) explicitly and repeatedly specify `"Speaker A"`/`"Speaker B"` as the canonical label — a deliberate later Architecture decision that a channel/cluster index alone cannot reliably be mapped to a real-world "agent" vs. "customer" role. Treat the Architecture spine + epics.md as authoritative over the earlier UX copy; do not "fix" this by writing "Agent"/"Customer" anywhere in this story's code. This is a known, pre-existing documentation drift — not something for this story to resolve.
- **This story does not build or wire a live UI.** `frontend/src/components/SpeakerLabel.tsx`, `frontend/src/components/TranscriptPanel.tsx`, and `frontend/src/api/callsApi.ts`'s `speaker_label`/`speaker_uncertain` fields already exist (built by Story 2.5, currently unreachable — see "Previous Story Intelligence" below). This story's job is exclusively to make `web-api`'s `GET /calls/{call_id}/transcript` response start returning real, non-null `speaker_label` values for stereo Calls; wiring/verifying the frontend's *reaction* to that real data (e.g. re-checking `AnalysisDashboard.tsx`'s `hasNoSpeakerAttribution` logic) is explicitly Story 3.4's scope, not this one's.

### The `channel_count > 2` gap (deferred-work.md, Story 1.2 review) is now actionable

`deferred-work.md`'s Story-1.2 entry for `ml-service/app/pipeline/ingest/channel.py`'s `detect_channel_count` flagged: *"a recording with more than 2 channels is silently accepted and persisted as-is... nothing reads channel_count>2 yet... Revisit when Epic 3 work begins."* That revisit is now. Neither AD-2 nor this epic's ACs define behavior for >2 channels — only "stereo" (2) and "mono" (1) are named paths. This story's `channel_count == 2` gate (Task 3) means a >2-channel Call simply gets no speaker attribution at all (every turn's `speaker_label` stays `None`, same as today) — it does **not** crash, and it is **not** treated as stereo. Do not attempt to guess a >2-channel policy beyond "leave unattributed" — that is out of this story's scope (no AC covers it), and inventing one risks conflicting with whatever Story 3.2/3.3 eventually decide for non-stereo, non-standard-mono inputs.

### Why `channel_count` is read from the waveform tensor, not the DB

`ingest/run.py`'s `run_ingest` already computes `channel_count = detect_channel_count(waveform)` from the exact same `torchaudio.load()` result `transcript/run.py`'s `load_mono_waveform` will re-load, and persists it via `db.set_call_channel_count`. `ml-service/app/db.py` currently has **no** `get_call`/Call-reader function at all (only `set_call_status`/`set_call_channel_count` writers) — adding one just to re-read a value already derivable for free from data `run_transcript` loads anyway would be a needless DB round-trip and a second source of truth. Reuse `detect_channel_count` (already exported from `app.pipeline.ingest.channel`) directly on the `raw_waveform` tensor `run_transcript` already has in hand.

### `run_transcript`'s existing raw waveform/sample rate are currently discarded — this story needs both

`transcript/run.py`'s current line `_raw_waveform, mono_waveform, _sample_rate = load_mono_waveform(call_id)` throws away exactly the two values (`raw_waveform`, original `sample_rate`) this story needs for per-channel energy comparison. `audio.py`'s own `load_mono_waveform` docstring already anticipates this: *"AD-2's stereo-channel speaker assignment is a separate, later concern — Story 3.1 — not decided here."* Capture both (rename away from the underscore-prefixed placeholders) rather than reloading the audio a second time.

### Turn timestamps are in seconds; the raw waveform's channel axis needs the *original* sample rate

`TurnResult.start_time`/`end_time` (from `stt.py`) are Call-absolute float seconds, produced against the VAD-resampled 16kHz mono mix — but seconds are sample-rate-independent, so converting to a sample index into `raw_waveform` (still at its original, possibly non-16kHz, sample rate) must multiply by `sample_rate` (the *original* rate `load_mono_waveform` returns), never `VAD_SAMPLE_RATE`. Getting this wrong silently reads the wrong audio window and biases every channel-energy comparison.

### Test fixture gap: the existing `stereo.wav` fixture cannot exercise this story

`ml-service/tests/conftest.py`'s `fixtures_dir`'s `_encode("stereo.wav", 3, 2)` runs ffmpeg's `sine=frequency=440` mono generator through `-ac 2`, which duplicates the identical signal onto both channels — every energy comparison on it is a tie, proving nothing about correct channel selection. Build a new, purpose-made 2-channel fixture (or a small helper alongside the existing `_encode`/`_encode_silence` pattern) with genuinely different per-channel content — e.g. an ffmpeg `filter_complex` `join`ing a loud `sine=` source on one channel with `anullsrc` (silence) on the other, and its mirror image — so a test can assert "the louder channel wins" deterministically. This does not need to be VAD-detectable speech (Task 2's unit tests don't invoke VAD at all); it only needs distinguishable per-channel energy over a known time window.

### Previous Story Intelligence (Story 2.5/2.6, Epic 2 — the consuming side already exists)

- Story 2.5 built `SpeakerLabel` (`default`/`uncertain` variants) and wired it into `TranscriptPanel`, but its own Dev Notes state it is "unreachable with real data from any current fetch in this codebase (no such DB column exists yet, Epic 3 still `backlog`)" — this story is what closes that gap for the stereo half.
- Story 2.6 built the `"Mono input — turns unattributed"` copy contract in `AnalysisDashboard.tsx`, gated on `turnsForAttributionCheck.every((t) => !t.speaker_label)`. Once this story starts returning real `speaker_label` values, that condition will correctly evaluate to `false` for stereo Calls with turns — no frontend change needed for that to work, but also not a claim this story should test end-to-end (Story 3.4's job).
- `deferred-work.md`'s Story-2.6-review entry explicitly names this exact gap and says it will be "revisit[ed] once Epic 3 starts populating `speaker_label` (stereo channel-based first, per epics Story 3.1)" — confirming this story is understood project-wide as the first real populator of this field.

### File List (expected)

- `ml-service/app/db.py` — `TranscriptTurn` DDL + `persist_transcript_turns` (Task 1, 4)
- `web-api/app/db.py` — `TranscriptTurn` DDL, hand-synced (Task 1)
- `ml-service/app/pipeline/transcript/speaker.py` — new (Task 2)
- `ml-service/app/pipeline/transcript/run.py` — wiring (Task 3)
- `web-api/app/routers/calls.py` — `get_transcript` response field (Task 5)
- `ml-service/tests/test_speaker.py` — new (Task 6)
- `ml-service/tests/test_transcript_run.py` — extended (Task 6)
- `ml-service/tests/conftest.py` — new stereo fixture helper, if added here rather than inline in the test (Task 6)
- `web-api/tests/test_transcript.py` — extended (Task 6)

Two files outside this list needed a one-line fix each once the full regression suite ran — see Completion Notes below: `ml-service/tests/test_fusion_run.py` and `ml-service/tests/test_sentiment_run.py`.

### Project Structure Notes

- No new top-level module/package — `speaker.py` lives inside the existing `ml-service/app/pipeline/transcript/` package, alongside `stt.py`/`sentiment.py`, consistent with the Capability → Architecture Map's mapping of speaker-attribution work to both `ingest` (channel *detection*, already built) and `transcript` (this story's channel *attribution*, and Story 3.2's mono diarization) — keeping stereo and mono attribution symmetric under the same package.
- No new config/threshold value is introduced by this story (unlike `LOW_CONFIDENCE_THRESHOLD`/`DISAGREEMENT_THRESHOLD`/`ACOUSTIC_SANITY_FLOOR`) — channel-energy comparison is a plain `argmax`, not a tunable gate.
- Follows the established "edit the `CREATE TABLE IF NOT EXISTS` string in place, no `ALTER TABLE`" pattern for schema changes in this codebase (see every prior Epic 1/2 story's DDL additions) — this is a known, already-accepted limitation (`deferred-work.md`, Story 1.5/2.4 entries): a pre-existing local/Docker DB predating this story will need its volume/file reset to pick up the new columns.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.1: Stereo Channel-Based Speaker Attribution]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#AD-2 — Audio input channel detection & speaker attribution]
- [Source: ml-service/app/pipeline/ingest/channel.py]
- [Source: ml-service/app/pipeline/transcript/run.py]
- [Source: ml-service/app/audio.py]
- [Source: ml-service/app/db.py]
- [Source: web-api/app/routers/calls.py#get_transcript]
- [Source: frontend/src/api/callsApi.ts (speaker_label/speaker_uncertain field contract, already declared)]
- [Source: _bmad-output/implementation-artifacts/deferred-work.md (Story 1.2 review — channel_count>2 gap; Story 2.6 review — speaker_label population trigger)]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5 (claude-sonnet-5)

### Debug Log References

- Local venv install of `ml-service`'s pinned `torch==2.13.0` failed on this dev machine (macOS 13.7.8, x86_64/Intel): PyTorch's wheel index publishes `torch==2.13.0` for macOS only as `macosx_14_0_arm64` (Apple Silicon, macOS 14+) — no x86_64 macOS wheel exists for this pinned version at all. Verified PyPI/download.pytorch.org connectivity was otherwise fine (a plain `requests` install and an index query both succeeded); the gap is platform-wheel availability, not network access.
- Resolved by building an ephemeral `python:3.13.15-slim` Docker container (matching this project's own CI runner and production `Dockerfile`) and installing via `pip install --extra-index-url https://download.pytorch.org/whl/cpu -e ".[dev]"` — the Linux x86_64 CPU wheel for `torch==2.13.0` does exist. All ml-service tests in this story were run and verified inside that container, not the host.
- First full-suite run inside the container caught 6 failures, all `sqlite3.ProgrammingError: Incorrect number of bindings supplied` — `ml-service/tests/test_fusion_run.py` and `ml-service/tests/test_sentiment_run.py` each have their own local helper that calls `db.persist_transcript_turns` directly with the pre-Story-3.1 6-field tuple shape, outside this story's own Task 1–6 scope. Fixed both call sites to pass `(..., None, None)` for the two new `speaker_label`/`speaker_channel_index` positions (mono/no-attribution seed data — those two test files aren't exercising stereo attribution, so `None` is the correct value, not a placeholder). Re-ran both files (16/16 pass) and then the full suite again (121/121 pass) to confirm.

### Completion Notes List

- Implemented AD-2's stereo channel-based speaker attribution end-to-end: `TranscriptTurn.speaker_label`/`speaker_channel_index` schema (hand-synced across `ml-service`/`web-api`), the deterministic `assign_stereo_speaker` per-channel-energy comparison, wiring into `run_transcript` (gated to `channel_count == 2` only — mono and >2-channel Calls are left unattributed, per this story's explicit scope and the now-addressed `deferred-work.md` Story 1.2 gap), and exposure of `speaker_label` (only) via `GET /calls/{call_id}/transcript`.
- Reused `app.pipeline.ingest.channel.detect_channel_count` on the same `raw_waveform` tensor `run_transcript` already loads, instead of adding a new `Call`-reader to `ml-service/app/db.py` — avoids a second source of truth for channel count and an unneeded DB round-trip.
- Added a new stereo test-audio fixture pair (`stereo_channel0_louder.wav`/`stereo_channel1_louder.wav`, via ffmpeg's `join` filter) since the pre-existing `stereo.wav` fixture duplicates identical audio onto both channels and cannot prove correct channel selection.
- No frontend changes — `frontend/src/components/SpeakerLabel.tsx`/`TranscriptPanel.tsx`/`callsApi.ts` already declared the `speaker_label`/`speaker_uncertain` contract this story starts populating (Story 2.5); reacting to real data end-to-end is Story 3.4's scope.
- **Test verification:** `ml-service` — 121/121 tests pass (`ruff check` clean), run inside a Docker container mirroring CI/production (see Debug Log — host-machine install was not possible for this pinned `torch` version/platform combination). `web-api` — 87/87 tests pass (`ruff check` clean), run in the existing host `.venv`.
- Two pre-existing test files outside this story's own File List (`test_fusion_run.py`, `test_sentiment_run.py`) needed a one-line fix each to their local `persist_transcript_turns` helper call sites after Task 4's signature change — flagged and fixed as part of the mandatory full-regression-suite pass (Step 7/8 of this workflow), not deferred.
- All 6 Acceptance Criteria are met: AC1/AC4 (deterministic per-turn stereo attribution, every turn), AC2 (canonical `"Speaker A"`/`"Speaker B"` label via the API), AC3 (channel index kept internal, never returned), AC5 (no confidence/uncertainty field invented for the deterministic path), AC6 (mono/diarization/failure states untouched — Stories 3.2/3.3's scope).

### File List

- `ml-service/app/db.py`
- `web-api/app/db.py`
- `ml-service/app/pipeline/transcript/speaker.py` (new)
- `ml-service/app/pipeline/transcript/run.py`
- `web-api/app/routers/calls.py`
- `ml-service/tests/test_speaker.py` (new)
- `ml-service/tests/test_transcript_run.py`
- `ml-service/tests/conftest.py`
- `web-api/tests/test_transcript.py`
- `ml-service/tests/test_fusion_run.py` (unplanned — stale `persist_transcript_turns` call site fixed after Task 4's signature change; see Debug Log)
- `ml-service/tests/test_sentiment_run.py` (unplanned — same fix as above)
- `_bmad-output/implementation-artifacts/deferred-work.md` (code review round — new entry + Story 2.6 cross-reference update)

## Change Log

- 2026-08-17: Story implemented — stereo channel-based speaker attribution (Task 1–6 complete, all ACs met). Full regression suite green: ml-service 121/121, web-api 87/87. Status: ready-for-dev → review.
- 2026-08-17: Code review (Blind Hunter + Edge Case Hunter + Acceptance Auditor, parallel). 6 patch findings applied (defensive guards in `assign_stereo_speaker` + isolated exception handling in `run_transcript`, tie-break documentation, `web-api/app/db.py` changelog docstring, multi-turn AC4 regression test, >2-channel fallback regression test, `deferred-work.md` updates), 1 finding deferred (crosstalk/near-tie test-fixture realism — logged in `deferred-work.md`), 4 dismissed as noise. Full regression suite re-verified green: ml-service 123/123, web-api 87/87, both ruff-clean. Status: review → done.
