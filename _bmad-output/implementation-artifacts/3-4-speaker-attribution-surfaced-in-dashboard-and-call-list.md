---
baseline_commit: b3a0fce76bb52714607081122b1bcb11d210a4b8
---

# Story 3.4: Speaker Attribution Surfaced in Dashboard & Call List

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an Analyst,
I want to see real speaker attribution (or a clear note when it isn't available) directly in the Dashboard and Call list,
so that I don't have to guess whether a label I'm looking at is trustworthy.

## Acceptance Criteria

1. **Given** a Call with stereo channel-based attribution (Story 3.1) or successful mono diarization (Story 3.2), **When** the Analyst views its Dashboard, **Then** each transcript turn's Speaker label (Story 2.5's existing `SpeakerLabel` component) renders the real "Speaker A"/"Speaker B" value for that turn — no new label UI introduced, only real data populated into the existing component.
2. **Given** a turn in the per-turn "uncertain" state (`speaker_uncertain: true`, Story 3.3), **When** rendered, **Then** the Speaker label shows the existing `uncertain` variant (dotted underline, Story 2.5) **and** a one-line reason is shown, reusing EXPERIENCE.md's already-defined static copy ("overlapping speech — speaker attribution uncertain") — no new copy authored.
3. **Given** a Call in the whole-Call "attribution unavailable" state (`speaker_attribution_unavailable: true`, Story 3.3), **When** the Analyst views its Dashboard, **Then** transcript turns render without speaker labels and the existing inline note ("Mono input — turns unattributed", Story 2.6's copy contract) is shown — populated only for Calls actually in this state, never shown for a Call with successful stereo or mono attribution.
4. **Given** a Call in the whole-Call "attribution unavailable" state, **When** the Analyst views the Session Call List, **Then** its Call row shows the existing small inline warning ("Mono input — turns unattributed") per the Call row component spec (DESIGN.md `components.call-row`) — populated only under this real condition, never shown as a default/placeholder on every row.
5. **Given** a Call with successful attribution (stereo or mono, no whole-Call failure), **When** the Analyst views its Call row, **Then** no "Mono input — turns unattributed" warning is shown.
6. **And** this story authors no new UI component, variant, or copy string — it exclusively wires Stories 3.1–3.3's real backend data into the UI contracts Epic 2 (Stories 2.5, 2.6) already built.

**Traceability:** FR-16; UX-DR7, UX-DR10, UX-DR13.

## Tasks / Subtasks

- [x] Task 1: Backend — expose `speaker_attribution_unavailable` on `GET /calls/{call_id}` (AC4 precondition)
  - [x] **Read `web-api/app/routers/calls.py` fully before editing** (`get_call_status` at line ~202, `get_transcript` at line ~355). This is the critical gap the story requires closing: `SessionCallList`'s Call rows are built exclusively from `getCallStatus`/`uploadCall` polling (`frontend/src/hooks/useCallStatusPolling.ts` → `GET /calls/{call_id}`) — there is no `GET /calls` list endpoint and the Call List page never calls `/transcript`. Story 3.3 only added `speaker_attribution_unavailable` to `get_transcript`'s response, so AC4 is structurally unreachable from the Call List today without this backend addition — this is a required system-consistency change, not scope creep (see the create-story workflow's own rule: "a story must leave the system working end-to-end, not just satisfy its literal ACs").
  - [x] Extract `get_transcript`'s existing inline computation (`calls.py:411-413`: `speaker_attribution_unavailable = bool(call["channel_count"] == 1 and turns and all(turn["speaker_label"] is None for turn in turns))`) into a small module-level helper, e.g. `_speaker_attribution_unavailable_flag(channel_count: int | None, turns: list[sqlite3.Row]) -> bool`, placed near `_speaker_uncertain_flag`. Update `get_transcript` to call it. This avoids duplicating the exact same boolean expression in two endpoints (the same "one hand-synced source of truth" discipline already used for `_low_confidence_flag`/`_speaker_uncertain_flag`).
  - [x] In `get_call_status`'s `if call["status"] == "complete":` branch (line ~251), alongside the existing `db.get_analysis_result(...)` read, also call `db.get_transcript_turns(conn, call_id=call_id)` (already used by `get_transcript`, no `db.py` change needed — `call["channel_count"]` is already selected by `db.get_call`'s existing `SELECT *`-style read, same as `get_transcript` already relies on) and set `result["speaker_attribution_unavailable"] = _speaker_attribution_unavailable_flag(call["channel_count"], turns)`. Set this **unconditionally for every `complete` Call** (both the `no_speech_detected` branch and the normal branch) — a zero-turn Call naturally computes `False` via the helper's own `turns` truthiness guard, so no special-casing is needed. Wrap the new read in the same `try/except sqlite3.Error: raise errors.internal_error(...)` pattern already used for the two existing reads in this function.
  - [x] Update `get_call_status`'s docstring to mention the new field, mirroring how `get_transcript`'s docstring documents its own Story 3.3 fields.
  - [x] Do not add `speaker_uncertain`/per-turn fields to `get_call_status` — the Call List only ever needs the whole-Call fact (AC4/AC5); per-turn detail belongs to the Dashboard's `/transcript` fetch only (AC1/AC2), already returned there.

- [x] Task 2: Frontend types — thread the new/existing backend fields through `callsApi.ts` (AC1, AC3, AC4)
  - [x] `frontend/src/api/callsApi.ts`: add `speaker_attribution_unavailable: boolean` to the `TranscriptResponse` interface (line ~98) — Story 3.3 already returns this field on the wire; the frontend type just never declared it. Non-optional: `get_transcript` always includes it for any `complete` Call.
  - [x] Add `speaker_attribution_unavailable?: boolean` to the `CallStatusResponse` interface (line ~37) — optional, since Task 1 only populates it once `status === "complete"` (mirrors how `overall_sentiment` etc. are already optional there for the same reason).
  - [x] No change needed to `TranscriptTurnResponse`'s existing `speaker_label?: string | null` / `speaker_uncertain?: boolean` fields (already correctly shaped from Story 2.5/3.3) — do not touch them.

- [x] Task 3: Dashboard — replace the client-side "no speaker attribution" heuristic with the real backend field (AC3)
  - [x] `frontend/src/pages/AnalysisDashboard.tsx` (line ~166-173): delete the `turnsForAttributionCheck`/`hasNoSpeakerAttribution` client-side heuristic entirely (`!transcriptFailed && turnsForAttributionCheck.length > 0 && turnsForAttributionCheck.every((t) => !t.speaker_label)`) — this was Epic 2's honest Epic-3-still-`backlog` placeholder, explicitly flagged in Story 3.3's own Dev Notes ("Story 3.4 should replace the client-side heuristic with this field, not merely add to it") and in this component's own current comment ("Epic 3 (`backlog`) supplies the real data").
  - [x] Replace every use of `hasNoSpeakerAttribution` (currently one: the `{hasNoSpeakerAttribution ? <p className="analysis-dashboard__signal-note">Mono input — turns unattributed</p> : null}` block, line ~300) with `!transcriptFailed && (transcript?.speaker_attribution_unavailable ?? false)`. Keep the existing JSX/CSS class (`analysis-dashboard__signal-note`) and copy string unchanged — no new component or copy (AC6).

- [x] Task 4: TranscriptPanel — render the uncertain-turn flag reason (AC2)
  - [x] `frontend/src/components/TranscriptPanel.tsx` (turn body, line ~93-95): where `<SpeakerLabel label={turn.speaker_label} uncertain={turn.speaker_uncertain} />` is rendered, add a sibling reason element **when `turn.speaker_uncertain` is true**, reusing the existing `.transcript-panel__reason` CSS class/visual pattern already used for the low-confidence flag reason (line ~105-107: `{isLowConfidence && overlappingSegment!.flag_reason && (<span className="transcript-panel__reason">{overlappingSegment!.flag_reason}</span>)}`) — this exact placement/markup (a `.reason` span inside the turn's text block) is also what the UX mockup (`ux-designs/.../mockups/analysis-dashboard.html`, the `who uncertain` example around line 287-290) shows for this exact state, confirming this is the intended rendering, not a new pattern.
  - [x] The reason text is a **fixed string**, not derived from any backend field (unlike `flag_reason`, which is computed server-side per confidence value) — hardcode exactly: `"Flag reason: overlapping speech — speaker attribution uncertain."` (verbatim from EXPERIENCE.md's State Patterns section and the mockup). Render it only when `turn.speaker_uncertain` is true, regardless of `isLowConfidence`/`isDisagreement` state (the two uncertainty axes are independent per AD-10 — a turn can be both `speaker_uncertain` and `low_confidence`/`disagreement` at once, and both reasons must render, not one suppressing the other).
  - [x] Do not add this reason inside `SpeakerLabel.tsx` itself — `SpeakerLabel` stays a pure label component (its own test suite already covers it in isolation); the reason is turn-level UI, same layering `TranscriptPanel` already uses for the low-confidence/disagreement reasons.

- [x] Task 5: Session Call List — thread the whole-Call flag from status polling into `CallRow` (AC4, AC5)
  - [x] `frontend/src/types/call.ts`: add `speakerAttributionUnavailable?: boolean` to the `SessionCall` interface, alongside the existing `noSpeechDetected?: boolean` (same "populated only once `state === 'complete'`" comment convention already used there).
  - [x] `frontend/src/pages/SessionCallList.tsx`'s `handlePollUpdate` (line ~88-117), in the `status.status === 'complete'` branch: add `speakerAttributionUnavailable: status.speaker_attribution_unavailable` to the `updateCall(...)` patch object, alongside the existing `noSpeechDetected`/`sentiment`/`emotion`/`confidence` fields.
  - [x] `frontend/src/components/CallRow.tsx`'s `complete`-state branch (the final `return` block, line ~140-172): render the inline warning when `call.speakerAttributionUnavailable` is true. Place it inside `.call-row__main`, after the existing sentiment/no-speech line and `deleteErrorNotice` (same relative position DESIGN.md's Call row description implies — a secondary note line under the primary sentiment line), using copy identical to the Dashboard's: `"Mono input — turns unattributed"`. Do not gate this on `call.noSpeechDetected` — the two are independent facts (a no-speech Call has no turns at all, so `speaker_attribution_unavailable` from Task 1's helper is `False` for it via the same `turns`-truthiness guard Task 1 relies on; this is a defensive note, not a code branch to add).
  - [x] `frontend/src/components/CallRow.css`: add a new rule for the warning (e.g. `.call-row__attribution-warning`), styled `color: var(--color-mixed)` at `var(--font-data-inline-size)`, directly matching DESIGN.md's "small `mixed`-colored inline warning" wording (`DESIGN.md` Components → Call row) and the same token `AnalysisDashboard.css`'s `.analysis-dashboard__signal-note` already uses for the identical fact on the Dashboard side (`AnalysisDashboard.css:151-159` — read this rule first and mirror its token choices, not the exact class name, since Call row's DOM structure is flat, not nested like the Dashboard's).

- [x] Task 6: Tests
  - [x] `web-api/tests/test_status.py` (Task 1): add tests mirroring `test_transcript.py`'s existing `speaker_attribution_unavailable` coverage, adapted to `GET /calls/{call_id}`: (a) mono complete Call (`channel_count=1`), all turns `speaker_label=None` → `speaker_attribution_unavailable: true`; (b) mono complete Call with at least one attributed turn → `false`; (c) stereo complete Call (`channel_count=2`) → `false` regardless of label values; (d) a `no_speech_detected` complete Call (zero turns, zero `AnalysisResult`) → `speaker_attribution_unavailable: false`, and the response still has `no_speech_detected: true` alongside it (both facts co-present, never one suppressing the other); (e) `queued`/`processing`/`failed` Calls never include the key at all (mirrors the existing `"overall_sentiment" not in body` assertion style in this file). Reuse/extend `test_transcript.py`'s `_make_call(channel_count=...)` and `_seed_turn(speaker_label=...)` raw-SQL seeding pattern — copy locally into `test_status.py`, per this test suite's own established "helpers are copied per-file, not imported across test files" convention (see `test_status.py`'s own docstring).
  - [x] `web-api/tests/test_transcript.py`: add one test confirming the extracted `_speaker_attribution_unavailable_flag` helper didn't change `get_transcript`'s existing behavior (a straightforward regression check — the existing 3.3 tests for this field should already catch any behavior change, but re-run the full file and confirm all pass unmodified).
  - [x] `frontend/src/pages/AnalysisDashboard.test.tsx`: the `EMPTY_TRANSCRIPT` constant (line ~35) currently omits `speaker_attribution_unavailable` — add `speaker_attribution_unavailable: false` to it (required field now, per Task 2). Add a new test: mock `getTranscript` to resolve with `speaker_attribution_unavailable: true` and at least one turn, assert the "Mono input — turns unattributed" note renders; add a second test with `speaker_attribution_unavailable: false` and turns carrying real `speaker_label` values, asserting the note does **not** render.
  - [x] `frontend/src/components/TranscriptPanel.test.tsx`: update the existing test at line ~136 (`'renders SpeakerLabel only when speaker_label is present (unreachable with real data today)'`) — its docstring is now false (Story 3.4 makes this reachable with real data); reword it to drop the "unreachable" framing. Add a new test: a turn with `speaker_label: 'Agent', speaker_uncertain: true` renders both the `speaker-label--uncertain` class (already covered by `SpeakerLabel.test.tsx` in isolation) **and** the visible text `"Flag reason: overlapping speech — speaker attribution uncertain."` inside the turn. Add a companion test: `speaker_uncertain: false` (or absent) renders the label with no such reason text.
  - [x] `frontend/src/components/CallRow.test.tsx`: add two tests to the "CallRow — complete state" describe block: (a) `speakerAttributionUnavailable: true` renders the "Mono input — turns unattributed" text; (b) `speakerAttributionUnavailable: false`/absent (the existing `makeCompleteCall()` default) does **not** render it — extend the existing "renders filename, Sentiment · Emotion text..." test's assertions, or add a standalone test, either is fine as long as both polarities are covered.
  - [x] `frontend/src/pages/SessionCallList.test.tsx`: add one integration test — mock `getCallStatus`'s polled resolution to include `speaker_attribution_unavailable: true` on a Call that reaches `complete`, and assert the rendered row shows the warning text. Follow this file's existing `overall_sentiment`-bearing mock-status object pattern (lines ~178, ~281) as the template for the new mock's shape.

### Review Findings

- [x] [Review][Patch] `CallRow`'s whole-Call attribution warning is invisible to screen readers — `rowAccessibleLabel` never includes it, and the surrounding `role="button"`/`aria-label` short-circuits all descendant content from the row's computed accessible name (same mechanism this file's own Story 2.7 comment documents) [frontend/src/components/CallRow.tsx:136-138] — fixed: `rowAccessibleLabel` now appends `, mono input, turns unattributed` when `call.speakerAttributionUnavailable` is true, mirroring the existing `noSpeechDetected` pattern.
- [x] [Review][Patch] `_speaker_attribution_unavailable_flag`'s docstring first sentence is confusingly worded — "with at least one turn where *every* turn's `speaker_label` is `None`" conflates "at least one turn exists" and "every turn's label is None" into one hard-to-parse clause [web-api/app/routers/calls.py:122] — fixed: reworded to two separate clauses ("that has at least one turn, where *every* one of those turns has `speaker_label is None`").
- [x] [Review][Patch] `test_status.py` has no test for the legacy/unset `channel_count IS NULL` case with non-empty turns — `test_transcript.py` already covers this exact case for the same shared helper, so the "both endpoints compute this identically" claim is only proven at one of the two call sites [web-api/tests/test_status.py] — fixed: added `test_complete_call_includes_speaker_attribution_unavailable_false_when_channel_count_unset`.
- [x] [Review][Patch] The `no_speech_detected` test for `speaker_attribution_unavailable` seeds zero turns and never sets `channel_count`, so it can't isolate whether `False` comes from the turns-empty guard or the channel_count guard [web-api/tests/test_status.py:188-199] — **re-verified against the actual current code**: the test already sets `channel_count=1` explicitly (this finding misread the diff hunk, per the triage rule to read real code before rating); no code change was needed, only a clarifying docstring line added to the existing test noting why `channel_count=1` isolates the turns-empty guard.
- [x] [Review][Patch] "false or absent" test titles in `CallRow.test.tsx` and `TranscriptPanel.test.tsx` each only exercise one of the two named cases (CallRow's test only covers the absent case; TranscriptPanel's only covers explicit `false`) [frontend/src/components/CallRow.test.tsx:147-150, frontend/src/components/TranscriptPanel.test.tsx] — fixed: split each into two precisely-named tests (explicit-`false` and absent), one per case, in both files.
- [x] [Review][Defer] `get_call_status` now fetches full `TranscriptTurn` rows via `db.get_transcript_turns` just to compute one boolean, unconditionally even on the `no_speech_detected` branch where turns are provably empty; since the Dashboard calls both `getCallStatus` and `getTranscript`, TranscriptTurn rows are fetched twice per Dashboard load [web-api/app/routers/calls.py:277-286] — deferred, pre-existing tradeoff explicitly directed by this story's own Task 1 instructions (reuse `db.get_transcript_turns`), low impact given this is a local SQLite dev/demo tool (AD-12), not scaled infra
- [x] [Review][Defer] The new speaker-uncertain reason text uses a "Flag reason:" prefix (matching the UX mockup verbatim) while the existing `flag_reason` backend string (Story 1.8) has no such prefix, so the two reasons read inconsistently when stacked on the same turn [frontend/src/components/TranscriptPanel.tsx, web-api/app/routers/calls.py:99-103] — deferred, pre-existing drift between the mockup and Story 1.8's actual implementation, predates this story

## Dev Notes

### Architecture compliance (binding, do not deviate)

- **This story is UI-wiring only, per its own AC6** — no new component, no new copy string, no new confidence/threshold logic. The one exception the story's own research surfaced is Task 1 (a small, mechanical backend addition): AC4 cannot be satisfied without it, because the Session Call List's data source (`GET /calls/{call_id}` via polling) never included the field Story 3.3 added only to `GET /calls/{call_id}/transcript`. This is not new business logic — it reuses the exact boolean `get_transcript` already computes (Story 3.3), extracted into a shared helper and called from a second endpoint. Do not invent a different computation for the Call-row case.
- **AD-2/AD-6/AD-10 are unaffected** — this story reads already-computed, already-tested flags (`speaker_label`, `speaker_uncertain`, `speaker_attribution_unavailable`) and displays them through components/copy contracts Epic 2 already built (`SpeakerLabel`, the `analysis-dashboard__signal-note` pattern, `CallRow`). No confidence axis is touched, combined, or re-derived.
- **No `ml-service` change, no DB schema change, no new config value.** Every field this story consumes already exists on the wire (Story 3.1/3.2/3.3); Task 1 only re-exposes one existing computation on a second read-only endpoint.

### The Call List data-source gap (why Task 1 exists — read this before assuming AC4 is "just" a frontend change)

`frontend/src/types/call.ts`'s own header comment states the ground truth: **"There is no `GET /calls` list endpoint"** — `SessionCallList.tsx` builds its rows entirely from `uploadCall()` (initial) and `getCallStatus()` (polled via `useCallStatusPolling`, which hits `GET /calls/{call_id}`). The Dashboard's `/transcript` endpoint — where Story 3.3 put `speaker_attribution_unavailable` — is **never fetched by the Call List page at all**. Without Task 1, AC4 has literally no data path to satisfy it; a frontend-only implementation would either be unable to show the warning correctly or would have to fetch `/transcript` per row (a much larger, unrequested change: N extra HTTP calls per session, against a resource — the transcript — the list view has no other use for). Extending `get_call_status`'s existing complete-branch payload by one boolean, reusing Story 3.3's already-proven computation, is the smallest correct fix.

### Where each AC is satisfied — map before coding

| AC | Data already exists? | Code change needed |
|----|----|----|
| AC1 (real Speaker label in Dashboard) | Yes — `get_transcript` already returns real `speaker_label` (Story 3.1/3.2); `TranscriptPanel`/`SpeakerLabel` already render it unconditionally when present | **None** in production code — verify via Task 6's updated test only |
| AC2 (uncertain reason text) | Yes — `speaker_uncertain` boolean already returned (Story 3.3); reason text is a static string already documented in EXPERIENCE.md, never wired to any component | `TranscriptPanel.tsx` (Task 4) |
| AC3 (Dashboard whole-Call note, real data) | Yes — `speaker_attribution_unavailable` already returned by `get_transcript` (Story 3.3); frontend type + Dashboard logic never consume it | `callsApi.ts` type (Task 2), `AnalysisDashboard.tsx` (Task 3) |
| AC4 (Call List row warning) | **No** — not returned by `get_call_status`, the only endpoint the Call List consumes | `calls.py`/`get_call_status` (Task 1), `callsApi.ts` type (Task 2), `types/call.ts`, `SessionCallList.tsx`, `CallRow.tsx`/`.css` (Task 5) |
| AC5 (no false-positive warning) | Same data as AC4 | Covered by Task 5's boolean gate; verified by Task 6 tests |

### Previous Story Intelligence (Story 3.3 — the field producer this story consumes)

- Story 3.3 added `speaker_uncertain` (per-turn) and `speaker_attribution_unavailable` (Call-level) to `GET /calls/{call_id}/transcript` only — its own AC7 explicitly scoped it to backend-only, zero frontend files touched, and its Dev Notes explicitly named this story (3.4) as the one that wires the data in.
- Story 3.3's Dev Notes flagged the exact `AnalysisDashboard.tsx` heuristic this story must replace (`hasNoSpeakerAttribution`) and warned it "cannot distinguish 'mono, failed' from 'stereo, defensively-all-null'" — confirming the fix is a full replacement, not an additive change (Task 3 above).
- Story 3.3's review found and fixed two dismissed Edge Case Hunter findings whose quoted code snippets didn't match the real implementation — a reminder for this story's own code-review pass: **read the actual current file at review time**, never trust a diff hunk or a subagent's quoted snippet at face value.
- `web-api` test suite currently at 105/105 passing, ruff-clean (post Story 3.3 review). No Docker/container needed for `web-api` tests (pure Python, no torch dependency) — only `ml-service` tests need the pinned container, and this story touches zero `ml-service` code.

### Previous Story Intelligence (Story 2.5/2.6 — the UI contracts this story populates)

- Story 2.5 built `SpeakerLabel` (`default`/`uncertain` variants, dotted underline) and wired it into `TranscriptPanel` already — its own test suite and comments already flagged it as "unreachable with real data today" pending Epic 3. This story is exactly what makes it reachable; no changes to `SpeakerLabel.tsx`/`SpeakerLabel.css` are needed (AC6 — variant already exists).
- Story 2.6 authored the exact "Mono input — turns unattributed" copy string and its `analysis-dashboard__signal-note` (mixed-colored) styling for the Dashboard, and DESIGN.md's Call row spec already documents the identical warning for the Call row (`components.call-row`: "A row without available speaker attribution shows a small `mixed`-colored inline warning"). This story reuses both copy instances verbatim — do not reword either.

### File List (expected)

- `web-api/app/routers/calls.py` — `_speaker_attribution_unavailable_flag` helper (extracted), `get_call_status` response field + docstring (Task 1)
- `web-api/tests/test_status.py` — extended (Task 6)
- `web-api/tests/test_transcript.py` — regression check only, likely no diff (Task 6)
- `frontend/src/api/callsApi.ts` — `TranscriptResponse`/`CallStatusResponse` type additions (Task 2)
- `frontend/src/pages/AnalysisDashboard.tsx` — heuristic removed, real field wired (Task 3)
- `frontend/src/pages/AnalysisDashboard.test.tsx` — extended (Task 6)
- `frontend/src/components/TranscriptPanel.tsx` — uncertain-reason rendering (Task 4)
- `frontend/src/components/TranscriptPanel.test.tsx` — extended (Task 6)
- `frontend/src/types/call.ts` — `SessionCall.speakerAttributionUnavailable` (Task 5)
- `frontend/src/pages/SessionCallList.tsx` — `handlePollUpdate` field threading (Task 5)
- `frontend/src/pages/SessionCallList.test.tsx` — extended (Task 6)
- `frontend/src/components/CallRow.tsx` — inline warning rendering (Task 5)
- `frontend/src/components/CallRow.css` — new warning style rule (Task 5)
- `frontend/src/components/CallRow.test.tsx` — extended (Task 6)

No `ml-service` files are expected to change. No DB schema change in either service. No new config value.

### Project Structure Notes

- Backend change stays inside `web-api`'s existing response-building layer (`routers/calls.py`), consistent with Story 3.3's own precedent of computing derived flags at read time, never persisting them.
- Frontend changes span the exact files Epic 2 already established for these surfaces (`AnalysisDashboard.tsx`, `TranscriptPanel.tsx`, `SessionCallList.tsx`, `CallRow.tsx`) — no new file, no new directory.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 3.4: Speaker Attribution Surfaced in Dashboard & Call List]
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-AIVoiceSentimentAnalyzer_v1-2026-08-10/EXPERIENCE.md — State Patterns section, "Speaker attribution unavailable"/"Speaker attribution uncertain" entries]
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-AIVoiceSentimentAnalyzer_v1-2026-08-10/DESIGN.md — `components.speaker-label`, `components.call-row`]
- [Source: _bmad-output/planning-artifacts/ux-designs/ux-AIVoiceSentimentAnalyzer_v1-2026-08-10/mockups/analysis-dashboard.html — lines ~280-290, the `who uncertain` + `.reason` markup pattern this story's Task 4 mirrors]
- [Source: _bmad-output/implementation-artifacts/3-3-speaker-attribution-failure-and-uncertainty-states.md — full Dev Notes, especially "Note for whoever picks up Story 3.4"]
- [Source: web-api/app/routers/calls.py — `get_call_status` (line ~202), `get_transcript` (line ~355), `_low_confidence_flag`/`_speaker_uncertain_flag` (helper precedent)]
- [Source: web-api/tests/test_status.py, web-api/tests/test_transcript.py — existing seeding/test patterns to extend]
- [Source: frontend/src/pages/AnalysisDashboard.tsx (`hasNoSpeakerAttribution`, to be removed), frontend/src/components/TranscriptPanel.tsx, frontend/src/components/SpeakerLabel.tsx, frontend/src/components/CallRow.tsx, frontend/src/pages/SessionCallList.tsx, frontend/src/types/call.ts, frontend/src/api/callsApi.ts]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5 (claude-sonnet-5)

### Debug Log References

- No blockers encountered. Task 1's backend addition matched the story's own upfront research exactly: `get_call_status` needed `speaker_attribution_unavailable` because the Session Call List never fetches `/transcript` — confirmed by reading `frontend/src/types/call.ts`'s own header comment ("There is no `GET /calls` list endpoint") before writing any code.
- TDD followed per task: RED (failing test against pre-implementation code) confirmed before each implementation, GREEN confirmed after, for Task 1 (backend), Task 3 (Dashboard heuristic replacement), Task 4 (uncertain-reason text), and Task 5 (Call row warning + SessionCallList wiring). Task 2 (pure TypeScript type additions) has no independent runtime behavior to RED-test; its correctness was verified via `tsc -b` after all consuming code was in place.
- One extra fix beyond the story's literal task list: after all tasks were implemented, `tsc -b` caught two more call sites (`App.test.tsx`, and a second `getTranscript` mock inside `AnalysisDashboard.test.tsx` itself, in a describe block Task 6's own edits didn't touch) that were missing the now-required `speaker_attribution_unavailable` field on `TranscriptResponse` mocks — fixed both; not a design change, just completing Task 2's type-tightening consistently across the test suite.

### Completion Notes List

- All 6 Acceptance Criteria met: AC1 (real Speaker label already worked end-to-end once Story 3.1-3.3's data flowed through — verified via TranscriptPanel's existing unconditional render, no production code change needed there), AC2 (uncertain-turn flag reason now rendered, fixed EXPERIENCE.md copy, independent of low-confidence/disagreement state per AD-10), AC3 (Dashboard's whole-Call note now reads the real `speaker_attribution_unavailable` field from `/transcript` instead of the Epic-2 client-side `every turn lacks speaker_label` heuristic), AC4 (Call List row warning wired end-to-end: new backend field on `GET /calls/{call_id}` → `CallStatusResponse` type → `SessionCall` state → `CallRow` render), AC5 (verified false-positive-free via tests: no warning for successfully-attributed Calls, no warning when only a heuristic would have (incorrectly) suggested one), AC6 (no new component/variant/copy — `SpeakerLabel`, `.transcript-panel__reason`, `.analysis-dashboard__signal-note`'s copy string, and the mockup's own EXPERIENCE.md-defined uncertain-reason string were all reused verbatim).
- Task 1 required one backend change beyond the story's own "UI-wiring only" framing (documented in the story's own Dev Notes as a required system-consistency fix, not scope creep): extracted `get_transcript`'s inline `speaker_attribution_unavailable` computation into a shared `_speaker_attribution_unavailable_flag` helper and called it from `get_call_status` too, since the Session Call List only ever polls the latter.
- No `ml-service` change, no DB schema change, no new config value — confirmed via `git status`/`git diff --stat`.
- **Test verification:** `web-api` — 112/112 tests pass, `ruff check` clean (native `.venv`, no Docker needed — zero ml-service/torch-dependent code touched). `frontend` — 180/180 tests pass (`vitest run`), `tsc -b` clean, `oxlint` clean.

### File List

- `web-api/app/routers/calls.py` — `_speaker_attribution_unavailable_flag` helper (extracted from `get_transcript`), `get_call_status` response field + docstring (Task 1)
- `web-api/tests/test_status.py` — extended: `_make_call(channel_count=...)`, local `_seed_turn`, 6 new tests (Task 6)
- `frontend/src/api/callsApi.ts` — `TranscriptResponse.speaker_attribution_unavailable` (required), `CallStatusResponse.speaker_attribution_unavailable` (optional) (Task 2)
- `frontend/src/pages/AnalysisDashboard.tsx` — `hasNoSpeakerAttribution` now reads the real backend field, heuristic removed (Task 3)
- `frontend/src/pages/AnalysisDashboard.test.tsx` — `EMPTY_TRANSCRIPT` updated, describe block rewritten/extended (5 tests), 2 mocks fixed for the new required field (Task 6)
- `frontend/src/components/TranscriptPanel.tsx` — uncertain-turn flag-reason rendering (Task 4)
- `frontend/src/components/TranscriptPanel.test.tsx` — docstring reworded, 2 new tests (Task 6)
- `frontend/src/types/call.ts` — `SessionCall.speakerAttributionUnavailable` (Task 5)
- `frontend/src/pages/SessionCallList.tsx` — `handlePollUpdate` threads the field into `updateCall` (Task 5)
- `frontend/src/pages/SessionCallList.test.tsx` — 1 new polling integration test (Task 6)
- `frontend/src/components/CallRow.tsx` — inline "Mono input — turns unattributed" warning (Task 5)
- `frontend/src/components/CallRow.css` — `.call-row__attribution-warning` rule (Task 5)
- `frontend/src/components/CallRow.test.tsx` — 2 new tests (Task 6)
- `frontend/src/App.test.tsx` — 1 mock fixed for the new required `TranscriptResponse` field (unplanned, `tsc -b` regression fix)

No `ml-service` files changed. No DB schema change. No new config value.

## Change Log

- 2026-08-17: Story implemented — Tasks 1-6 complete, all 6 ACs met. Backend: `speaker_attribution_unavailable` extracted into a shared helper and exposed on `GET /calls/{call_id}` (previously only on `/transcript`), since the Session Call List only polls the former. Frontend: Dashboard's whole-Call note now reads the real backend field instead of Epic 2's client-side heuristic; TranscriptPanel renders the uncertain-turn flag reason (fixed EXPERIENCE.md copy); Call List rows now show the same "Mono input — turns unattributed" warning the Dashboard already had. No ml-service, DB schema, or new-config changes. Full regression green: `web-api` 112/112 (ruff clean), `frontend` 180/180 (`tsc -b` clean, `oxlint` clean). Status: ready-for-dev → review.
- 2026-08-17: Code review (Blind Hunter + Edge Case Hunter + Acceptance Auditor, parallel, scoped to this story's own changes via a reconstructed pre-3.4 baseline). 4 real patch findings applied (fixed `CallRow`'s accessible-name gap for the attribution warning — a real UX-DR16 accessibility-floor regression this diff introduced, confirmed by all three review layers independently; reworded a confusing helper docstring; added the missing `channel_count`-unset test to `test_status.py`; split two under-named "false or absent" tests into precise explicit-false/absent pairs in both `CallRow.test.tsx` and `TranscriptPanel.test.tsx`). 1 finding re-verified against the real current code and found already correct — no change needed (a reviewer misread a diff hunk; the `no_speech_detected` test already set `channel_count=1`), only a clarifying comment added. 2 findings deferred (`get_call_status`'s extra `TranscriptTurn` fetch — an explicit, story-directed tradeoff, low impact on a local SQLite dev tool; a "Flag reason:" copy-prefix inconsistency predating this story, inherited from a Story 1.8/mockup drift), both logged in `deferred-work.md`. 9 findings dismissed as noise (systemic patterns already established across the whole codebase — manual snake_case/camelCase field mapping, unit-tests-mock-the-API-boundary test architecture — and one auditor finding whose own analysis confirmed it matched the story's explicit hedge). Full regression suite re-verified green: `web-api` 113/113 (ruff clean), `frontend` 184/184 (`tsc -b` clean, `oxlint` clean). Status: review → done.
