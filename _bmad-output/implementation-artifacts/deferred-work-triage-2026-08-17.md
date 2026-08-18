# Deferred-Work Triage — 2026-08-17

Full triage of every item in `deferred-work.md` (69 distinct entries across Epics 1-3, including "Update" sub-notes) plus the two escalated process gates from the Epic 3 retrospective. No code changes made. No item silently closed — items verified resolved in code are marked **No longer applicable** with the verification evidence, not deleted.

Categories: **Must resolve before next epic** · **Next epic candidate** · **AD-17 / calibration-dependent** · **Long-term / optional** · **No longer applicable**

---

## Part A — The 5 Specially-Requested Focus Areas

### A1. Schema migration (no `ALTER TABLE` path)

**Items:** text_* columns (1.5), `completed_at` (2.4), `speaker_label`/`speaker_channel_index` (3.1), `speaker_cluster_id`/`speaker_confidence` (3.2) — plus the original `TimelineSegment`/`AcousticEvidence`/four Story-1.10 tables never had one either.

**Architecture/PRD impact:** AD-12 explicitly frames persistence as "dev/demo resilience only... not a product promise of durable storage" — so the *product* doesn't require migrations. But the *engineering process* impact is real and now proven recurring: **every single schema-touching story across all 3 epics** (8 of them) hit this identical gap. It has stopped being a one-off acceptable risk and become a structural tax on every future story that touches the DB.

**Category: Must resolve before next epic** (if the next epic touches schema at all, which is nearly certain) — recommended, not mandated. The alternative is accepting an identical 9th, 10th, 11th... occurrence. A minimal fix (a `migrations/` folder with numbered `ALTER TABLE` scripts run at `get_connection()` startup, or even just a documented "reset your volume" runbook step) is small relative to the recurring cost of rediscovering this every story.

### A2. `ACOUSTIC_SANITY_FLOOR` (0.15, mathematically unreachable for the 4-class model)

**Architecture/PRD impact:** This is AD-1's core safety mechanism ("voice-first can never be bypassed... a degenerate/low-confidence acoustic result must be flagged"). It is currently dead code — real risk to a stated architecture invariant, not cosmetic.

**Category: AD-17 / calibration-dependent** — confirmed correct per its own repeated deferral reasoning (Epic 1 review, reaffirmed in the Epic 1 retrospective). Do **not** bump the threshold to an arbitrary reachable value (e.g. 0.35) without real evaluation data backing it — already agreed in the Epic 1 retrospective. **Flagging for visibility, not downgrading:** this is the single highest-severity open item in the whole project because it's a silently-dead safety gate, not just missing robustness. It should be the first thing addressed whenever AD-17 calibration/evaluation work is actually scheduled — recommend giving it more visible priority than the rest of the AD-17 bucket, consistent with what was already agreed in the Epic 1 retrospective.

### A3. Misleading/weak regression tests

**Not a `deferred-work.md` item** — this is a *pattern* observed across Stories 3.1, 3.2, 3.3's code reviews (tests that would pass identically even if the guarded behavior regressed), not a single itemized piece of open work. It is already captured as **Epic 3 action item 5** (owner: Dana, QA Engineer — add a review-checklist check for "would this test actually fail if the behavior regressed"). No separate triage entry needed; tracked via `sprint-status.yaml`'s `action_items`, not `deferred-work.md`.

### A4. DB connection lifecycle / foreign keys / retry idempotency / finite-confidence validation

**Items bundled:** `conn = db.get_connection()` outside try/except (5 instances: ingest, acoustic, transcript, text_sentiment, fusion) · `PRAGMA foreign_keys` never enabled (both services) · no idempotency/upsert guard on ingest/acoustic/transcript/text-sentiment writes · confidence values never validated finite/non-NaN before fusion arithmetic.

**Architecture/PRD impact:** None of these are reachable *today* — no RQ `Retry()` policy exists anywhere, so idempotency never gets exercised; the one real delete path (Story 1.10) already handles cascade cleanup correctly, so `PRAGMA foreign_keys` is defense-in-depth, not an active gap; NaN confidence has never been observed from either shipped classifier. But this is the exact systemic pattern the Epic 1 retrospective already flagged (action item 5, owners Dana + Amelia) as needing a **shared utility/pattern**, not five-plus independent point fixes.

**Category: Must resolve before next epic** if that epic adds a 6th pipeline stage or touches `run_*` entrypoints again (near-certain to recur otherwise, same as A1). If the next work is purely frontend/UI, this can slide to **Next epic candidate**. Already owned (Epic 1 action item 5) — this triage doesn't change ownership, only confirms severity.

### A5. Epic 2's 3 remaining cross-story items

| Item | Verified current state | Category |
|---|---|---|
| `CallRow` state-transition `aria-live` | Still genuinely open — Story 2.7 deliberately left it (new feature, not a verification-pass fix). No code found implementing it. | **Next epic candidate** (small, well-scoped, no design decision needed — just needs a story slot) |
| Duplicate-filename ambiguous accessible name | Still genuinely open — needs a product/UX decision (disambiguate by timestamp/id?) neither DESIGN.md nor EXPERIENCE.md makes today. | **Next epic candidate**, but blocked on a UX decision first — recommend routing to Sally (UX) before it can become a story |
| Story 2.3 AC2 (Dashboard delete action) | Still genuinely open — no story in `epics.md` has ever been assigned to it, confirmed unresolved as of Epic 3's completion. | **Next epic candidate** (or formally descope AC2 if the product no longer wants Dashboard-level delete — a real product decision, not obviously "yes, build it") |

---

## Part B — Everything Else

### Resolved — verified in code, deferred-work.md just never got a closure note

| Item | Originally deferred by | Verified resolved by |
|---|---|---|
| `GET /calls/{call_id}` 404-during-poll retried forever | Story 2.2 | Story 2.3 (its own Update note already confirms this) |
| `ConfirmDialog` no focus trap | Story 2.3 | Story 2.7 — verified in code: `handleTabTrap` present, `ConfirmDialog.tsx:41-49` |
| `ConfirmDialog` no `aria-labelledby`/`aria-describedby` | Story 2.3 | Story 2.7 — verified in code: both attributes present, `ConfirmDialog.tsx:59-60` |
| Delete affordance hover-only, no touch fallback | Story 2.3 | Story 2.7's responsive-breakpoint work (per Epic 2 retro's own synthesis) |
| `CallRow` no `role="button"`/accessible name (the non-`aria-live` half) | Story 2.2 | Story 2.7 — the `aria-live` half remains open, tracked separately in Part A5 |
| AC10 non-visual parity for unflagged transcript turns | Story 2.5 | Story 2.7 |
| No `aria-live`/`role="status"` on Dashboard notices | Story 2.6 | Story 2.7 (its own Update note confirms) |
| `speaker_confidence` no minimum-evidence floor | Story 3.2 | Not "fixed," but formally **decided closed** — Story 3.3 deliberately declined to add one per its own AC6 scope. This is a resolved decision, not open work. |
| Mono-input copy `.every()`/whitespace-only edge case | Story 2.6 | Story 3.4 — the client-side `.every()` heuristic this worried about was fully replaced by a direct read of the backend's `speaker_attribution_unavailable` field (verified in `AnalysisDashboard.tsx:166-170`); the mechanism no longer exists to have the bug |

**Recommendation:** add one-line "Update" closure notes to `deferred-work.md` for these (light bookkeeping, no behavior change) so future readers don't re-discover them as if still open — this is the same convention gap the Epic 2 retrospective already caught once.

### AD-17 / calibration-dependent

- Shipped SER model is a frozen-backbone linear probe, not a fine-tune (Story 1.3)
- CREMA-D spot-check is a 4-sample anecdote (Story 1.3)
- Debatable polarity judgment calls in `sentiment_taxonomy.py`'s lookup table (Story 1.5)
- Temperature-scaled softmax has no OOD/entropy signal (Story 1.5)
- `resolve_text_signal`'s "largest-overlap-wins" per-segment weighting (Story 1.6)

All five share the same trigger: real in-domain evaluation work against call-center-style audio, not yet done anywhere in the project. Bundle with `ACOUSTIC_SANITY_FLOOR` (A2) as one evaluation-phase initiative rather than five separate ones.

### Next epic candidate (beyond A1/A4/A5 above)

- **AD-11 duplicate transcript text on overlapping context-margin slices** (Story 1.4) — the one item here with real user-visible impact (an analyst would actually see duplicated transcript text). AD-11 forbids the simple fix; the real fix needs a whole-call-transcription redesign. Recommend prioritizing this above the other "next epic candidate" items given it's the only one with a live correctness/data-quality symptom rather than a robustness/edge-case gap.
- **AD-13's write-boundary enforced only by docstrings, no automated guard** (Story 1.7) — cheap to fix (one architecture-fitness test), protects a real invariant.
- **Hand-synced DDL across 6 tables, no drift-detection** (Story 1.10) — same class as the item above; consider bundling both into one "architecture invariant fitness tests" story.
- **`detect_channel_count` no upper-bound for >2 channels** + **`speaker_attribution_unavailable` never fires for >2-channel Calls** (Stories 1.2, 3.3) — these are the same underlying gap. Note: PRD's Glossary scopes `Call` to "one two-party (agent + customer) conversation," so >2-channel input is arguably out of product scope entirely, not just deferred. Recommend treating as a product-scope question first (does the product want to explicitly reject >2-channel uploads, or explicitly support them?) before it becomes a story.

### Long-term / optional (everything else — all explicitly low-severity, low-likelihood, or deliberate accepted tradeoffs in their own original review text)

Docker healthcheck on redis · VAD/SER model cache not reused under forking worker (explicit accepted tradeoff) · very short calls' context slice · RQ worker queue-priority starvation · text-sentiment model-name/label-set validation · Dockerfile pre-fetch hardcoding · no batching in text-sentiment · `_get_model()` singleton ordering · no index on `TimelineSegment` · `ORDER BY` tiebreaker · missing `CHECK` constraint · hardcoded status strings · `LOW_CONFIDENCE_THRESHOLD` cross-service drift · two config docstring contradictions · config validation-style inconsistency · blocking `time.sleep` wait loop · canceled RQ jobs not deleted from Redis · no concurrency test for overlapping deletes · crashed-worker un-deletable Call (deliberate safe-by-design) · retry-position-not-preserved · stale/out-of-order poll response (self-healing) · no `AbortController` guards · delete-button DOM position vs mockup (cosmetic) · narrow polling race window (self-healing) · TOCTOU concurrent-delete pattern · missing 500-test coverage for two endpoints · Timeline/TranscriptPanel tie-break inconsistency · `fused_confidence` nullable-in-DB/non-nullable-in-type · narrative code comments convention · AcousticPanel can't distinguish two null-reasons · unpaginated timeline/transcript arrays · Timeline keyboard nav missing Home/End · `get_acoustic_summary` per-field averaging · `AnalysisDashboard` loading-gate gap (unreachable via real UI) · TranscriptPanel scroll-sync-to-first-turn · `callsApi.ts` no fetch timeout · no `HF_TOKEN` onboarding docs · `get_call_status` double-fetching `TranscriptTurn` · "Flag reason:" prefix copy inconsistency

None of these were flagged as blocking, none showed evidence of recurring/systemic impact the way A1/A4 did, and each one's own original review text already frames it as low-priority/accepted.

---

## Summary for Decision

| Category | Count |
|---|---|
| Must resolve before next epic (recommended) | 2 groups (A1 schema migration, A4 DB reliability) |
| Next epic candidate | 6 items/groups (AD-11 duplication, AD-13 guard, DDL drift, >2-channel scope question, Epic 2's 3 cross-story items) |
| AD-17 / calibration-dependent | 6 items (including `ACOUSTIC_SANITY_FLOOR`, flagged highest-priority within this bucket) |
| Long-term / optional | ~36 items |
| No longer applicable (resolved, needs a bookkeeping note only) | 9 items |

This triage is a recommendation set, not a decision — nothing here has been scoped into a story or epic. Awaiting your review before any of this becomes sprint planning.
