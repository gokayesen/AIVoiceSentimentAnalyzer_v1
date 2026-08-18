# Next-Epic Preparation — 2026-08-17

Follow-up to `deferred-work-triage-2026-08-17.md` (reviewed and confirmed by Project Lead). Covers the two items the Project Lead asked for before any epic/sprint planning starts:

1. How the two escalated process gates (API-contract preflight, ML preflight) actually get applied.
2. Proposed technical scope and story boundaries for the two "Must resolve before next epic" groups (schema migration, DB reliability).

**Status: content approved by Project Lead (2026-08-17).** Approval covers: the `deferred-work.md` bookkeeping closures, the two gate-operationalization designs (Part 1), and the two proposed technical scopes/story boundaries (Parts 2-3), including the deliberate exclusion of idempotency from the DB reliability scope.

**This approval is explicitly not an Epic 4 authorization and does not start sprint planning.** All three planned epics (1-3) are complete; MVP scope is closed. Nothing in this document is implemented or scoped into a formal story. This document stays as **future-planning input**, to be picked back up only once a new product/development need is identified — not on any other trigger. No epic, sprint plan, or story file should be created from it, and none of the two "must resolve" technical items should be implemented, until the Project Lead explicitly revisits this document for that purpose.

---

## Part 1 — Operationalizing the Two Process Gates

Both gates were agreed in principle during the Epic 3 retrospective (action items 2 and 3) but, per the Epic 3 retrospective's own readiness assessment, "must actually be exercised before the next epic begins, not merely exist as agreed items." This section defines *when* they run, *who* runs them, *what* they produce, and *what they block*.

### Gate 1 — API-Contract-Gap Preflight

- **Owners:** Alice (Product Owner) + Winston (Architect)
- **Trigger point:** After the next epic's stories are drafted in `epics.md` (rough scope known) but *before* any story is created via `create-story` / moved to `ready-for-dev`. Sits between epic drafting and story creation — not before epic drafting (too early, ACs don't exist yet) and not during individual story review (too late, per Epic 2's repeated pattern of retrofitting endpoints mid-story).
- **Process:**
  1. For every story planned in the new epic, list the backend contract it will need: endpoint, method, request/response fields.
  2. Check each against the current `web-api` router surface (`web-api/app/routers/calls.py` and any future routers) and `ARCHITECTURE-SPINE.md`'s documented API surface.
  3. Mark each as *exists*, *needs extension* (e.g. a new field on an existing response), or *needs a new endpoint*.
  4. Anything marked *needs extension*/*needs a new endpoint* gets folded into the relevant story's scope (or, if it spans multiple stories, called out as a shared prerequisite) — not discovered mid-implementation as an unplanned "minimal correcting endpoint," which is exactly the pattern that recurred through Epic 2.
- **Deliverable:** `_bmad-output/implementation-artifacts/epic-{N}-api-contract-preflight.md` — one row per planned story, contract needed, exists/gap, and (if gap) which story absorbs the fix.
- **Gate condition:** Story creation for the new epic does not begin until this document exists and Alice + Winston have signed off on it. This is a hard gate, not an advisory checklist — consistent with the retrospective's escalation.

### Gate 2 — ML Preflight

- **Owner:** Charlie (Senior Dev)
- **Trigger point:** Before implementation starts on *any* story that introduces a new model, a new library, or a version change to an existing pinned ML dependency (torch, transformers, pyannote, faster-whisper, etc.). Does not apply to stories with no ML/dependency surface.
- **Process (time-boxed empirical spike, not implementation):**
  1. In a disposable branch/venv, attempt to install the full proposed dependency set together (not just the new package in isolation) — this is exactly what Story 3.2 skipped, and it's what actually broke (whisperx vs. torch).
  2. Load the actual checkpoint/model referenced by the architecture doc or story and run one real inference call.
  3. Walk the architecture-specified pipeline steps for this component (e.g. "forced alignment," "diarization + clustering") and confirm each step is actually reachable with the resolved library versions — not just that *a* version of the library installs.
  4. Record pass/fail with evidence (resolved version pins, command output, or the specific incompatibility found).
- **Deliverable:** A short preflight note appended to the story's own Dev Notes *before* its Tasks section is written — pass/fail plus evidence. If it fails, this triggers an architecture reconciliation conversation (the AD-6 pattern) *before* the story is scoped, not after implementation has already deviated silently.
- **Gate condition:** No story with an ML/dependency surface moves to `ready-for-dev` without this note present.

### Where these plug into the BMad workflow

Both gates sit at the same point: after epic-level scope is drafted, before `create-story` runs for that epic's stories.

**Decided (Project Lead, 2026-08-17): enforced by convention, not tooling.** No new automation/checklist tooling is being built for this. Enforcement is: the two preflight artifacts (`epic-{N}-api-contract-preflight.md`, and the per-story ML preflight note in Dev Notes) must exist and show a PASS before the relevant story's implementation begins — checked by whoever creates/starts that story, the same way every other process gate in this project (DoD checklist, code-review workflow) is already enforced by convention rather than by tooling. If a preflight artifact is missing or shows FAIL, implementation does not start until it's resolved.

---

## Part 2 — Proposed Scope: Schema Migration Path

**Confirmed by Project Lead as "Must resolve before next epic."**

### Problem restated

8 of the project's stories across 3 epics (1.2, 1.3, 1.5, 1.10, 2.4, 3.1, 3.2, plus the original Story 1.2 tables) each added columns/tables via `CREATE TABLE IF NOT EXISTS`, which never retrofits an already-existing local/Docker-volume database. Every occurrence has been individually deferred with the same note. It is now a structural, recurring engineering tax, independent of AD-12's "not a durable storage product" framing — the *product* doesn't need migrations, but the *engineering workflow* around every schema-touching story does.

### Proposed technical scope

- A lightweight, numbered-script migration runner — **not** an ORM/migration framework (Alembic, etc. is disproportionate to AD-12's dev/demo scope).
- Mechanism: a `schema_version` value (SQLite `PRAGMA user_version` is sufficient — no new table needed) checked at `get_connection()` startup in both `ml-service/app/db.py` and `web-api/app/db.py`. If the stored version is behind the latest known migration, apply pending numbered `ALTER TABLE`/`CREATE TABLE` scripts in order, then bump the version.
- Applies to **both services**, consistent with AD-7's existing hand-synced-DDL mirroring convention — a single migration wouldn't be complete if only one service's schema advanced.
- Migration 001 should retroactively cover the accumulated gap: `TranscriptTurn.text_*` (1.5), `Call.completed_at` (2.4), `TranscriptTurn.speaker_label`/`speaker_channel_index` (3.1), `TranscriptTurn.speaker_cluster_id`/`speaker_confidence` (3.2) — so existing dev/Docker volumes catch up in one pass rather than needing a fresh reset.
- Explicitly out of scope: rollback tooling, down-migrations, zero-downtime concerns, migration testing infrastructure beyond "does it apply cleanly to a pre-migration-001 database and a fresh one."

### Proposed story boundary

- **One story**, scoped to `ml-service/app/db.py` + `web-api/app/db.py` + a new `migrations/` (or similarly named) folder with the runner and the retroactive script. No pipeline/business logic changes.
- Suggested acceptance shape (not final ACs): (1) a fresh DB initializes at the latest schema version with no behavior change, (2) a DB frozen at any prior story's schema state, when started against current code, ends up at the latest schema version with all data intact, (3) the runner is exercised by both services' test suites via a fixture that seeds an old-shape DB.
- Not bundled with the DB-reliability story below — different failure mode (missing columns vs. connection/validation robustness), different test strategy (schema-state fixtures vs. exception-injection), and this one has a clear, closeable scope on its own.

---

## Part 3 — Proposed Scope: DB Reliability Group

**Confirmed by Project Lead as "Must resolve before next epic," bundled per Epic 1 action item 5's original framing ("shared utility/pattern, not point fixes").**

### Problem restated (4 recurring items, all previously deferred individually)

1. `conn = db.get_connection()` sits outside `try/except` in 5 `run_*` entrypoints (ingest, acoustic, transcript, text_sentiment, fusion) — a connection-acquisition failure propagates uncaught, violating each stage's "never raise" contract.
2. `PRAGMA foreign_keys` is never enabled in either service's `get_connection()` — `REFERENCES` clauses are declared but not enforced by SQLite.
3. No idempotency/upsert guard on ingest/acoustic/transcript/text-sentiment writes — a retried job hits a `PRIMARY KEY` violation or duplicates rows.
4. Confidence values (`acoustic_confidence`/`text_confidence`) are never validated as finite/non-NaN before fusion's arithmetic — a NaN would silently bypass the (currently also-broken) acoustic sanity check and corrupt weighted-average/disagreement calculations.

### What's actually reachable today (confirmed in the triage)

Items 1, 2, and 4 have no live trigger today: no RQ `Retry()` policy exists anywhere in the codebase (item 3's precondition), the one real delete path already handles cascades correctly (item 2's active risk), and neither shipped classifier has ever produced NaN (item 4's precondition). This bundle is being scoped now because it's a *systemic pattern flagged as recurring* (Epic 1 action item 5), not because any instance is an active bug — worth stating plainly so this doesn't get treated as more urgent than it is.

### Proposed technical scope

- **Connection handling:** introduce a shared context-manager helper in each service's `db.py` (e.g. `db.connection()` yielding a connection inside its own try/except/finally), and migrate all 5 `run_*` entrypoints plus web-api's router functions to use it instead of the current bare `conn = db.get_connection()` pattern. One helper per service (no cross-service shared code, consistent with the project's existing per-service `db.py` duplication convention).
- **Foreign keys:** add `PRAGMA foreign_keys=ON` to both services' `get_connection()`. Low risk, single-line change per service, but needs the existing test suites re-run in full since enabling enforcement could surface latent test-data ordering issues that were previously silently tolerated.
- **Finite-confidence validation:** add a `math.isfinite()` guard at the two points identified — `run_acoustic`'s sanity-floor check and `fuse_segment`'s inputs in `fuse.py` — treating a non-finite confidence the same as any other acoustic-pipeline failure (AD-1's "never fail the Call, flag instead" pattern).
- **Idempotency:** **excluded from this story's scope.** Its precondition (an RQ retry policy) doesn't exist yet. Only pull this into scope if the next epic actually introduces retry/reprocessing — otherwise this would be building a guard against a mechanism that isn't there, which the project's own review history has already flagged as premature every time it came up.

### Proposed story boundary

- **One story**, touching `ml-service/app/db.py`, `web-api/app/db.py`, the 5 `run_*.py` stage entrypoints, and `fuse.py`. No schema changes (keeps it independent of the migration story above).
- Suggested acceptance shape (not final ACs): (1) every `run_*` entrypoint acquires its connection through the shared helper, (2) a simulated connection-acquisition failure is caught and results in the existing "flag, don't crash" behavior rather than an uncaught exception, (3) `PRAGMA foreign_keys=ON` is verified active and the full existing test suite still passes, (4) a NaN/inf confidence input to `fuse_segment` and to the acoustic sanity check is caught and handled the same way an out-of-range value already is.
- Explicitly does **not** include: idempotency/upsert guards (excluded above), the `ORDER BY` tiebreaker / missing `CHECK` constraint items (Part A of the triage placed these in Long-term/optional, not this bundle).

---

## Summary

| Item | Status |
|---|---|
| API-contract preflight gate | Approved — enforced by convention + explicit preflight artifact, no new tooling. Not yet exercised (no epic in flight). |
| ML preflight gate | Approved — enforced by convention + explicit preflight artifact, no new tooling. Not yet exercised (no epic in flight). |
| Schema migration | Scope + story boundary approved. Not implemented, not written as a formal story. |
| DB reliability group | Scope + story boundary approved (idempotency excluded). Not implemented, not written as a formal story. |
| `deferred-work.md` bookkeeping closures | Approved and applied (6 closure notes added 2026-08-17). |

**Project status as of 2026-08-17:** all 3 planned epics complete, MVP scope closed. This document is confirmed future-planning input only — no Epic 4, sprint plan, or implementation follows from it. Revisit only when a new product/development need is identified.
