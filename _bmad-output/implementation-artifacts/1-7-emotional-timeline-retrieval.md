---
baseline_commit: NO_VCS
---

# Story 1.7: Emotional Timeline Retrieval

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an Analyst,
I want to retrieve a chronological view of how Sentiment and Emotion evolve across a Call,
so that I see the shape of the conversation, not just one aggregate score.

## Acceptance Criteria

1. **Given** a Call is `complete`, **When** the timeline is requested, **Then** the system returns all `TimelineSegment` rows in chronological order, each with its fused Sentiment, Emotion, confidence, and disagreement flag — the disagreement flag defaults to `false`/absent until Story 1.9's threshold logic is implemented.
2. **Given** the returned timeline, **Then** its resolution is granular enough to distinguish two distinct emotional shifts within the same Call — never a single aggregate score presented as a timeline (FR-9).
3. **Given** the timeline's segment boundaries, **Then** they are identical to the model-input chunk boundaries from Story 1.2 — never a second, independently-computed boundary set (AD-11).
4. **And** the endpoint has independently-runnable unit tests (AD-21).

**Dependency (from epics.md):** requires Story 1.6 (fusion) for per-segment confidence and Sentiment/Emotion values. The `disagreement flag` field is owned by Story 1.9 (Cross-Modal Disagreement Surfacing) — until Story 1.9 is implemented, every segment's disagreement flag defaults to `false`/absent, and this story is fully completable and testable against that default. This story does not need to be re-opened once Story 1.9 lands — the field's shape is unchanged, only its populated value.

## Tasks / Subtasks

- [x] Task 1: Read-only SQLite access for `Call`/`TimelineSegment` in `web-api` (AC: 1, 3)
  - [x] In `web-api/app/db.py`, add a `_CREATE_TIMELINE_SEGMENT_TABLE` DDL **mirroring `ml-service/app/db.py`'s definition column-for-column** (`id`, `call_id`, `segment_index`, `start_time`, `end_time`, `acoustic_emotion`, `acoustic_confidence`, `fused_sentiment`, `fused_emotion`, `fused_confidence`, `single_modality_flag`, `disagreement_flag`) — hand-synced, not imported (AD-7 service boundary; same pattern already used for the `Call` table, see the existing module docstring). Register it in `init_db()` alongside `_CREATE_CALL_TABLE`. This is required so `web-api`'s own test suite can create a self-contained SQLite file without `ml-service` ever running — in production, whichever service's `init_db()` runs first at container startup creates the table (`CREATE TABLE IF NOT EXISTS` is idempotent either way, container start order is not guaranteed).
  - [x] Add `get_call(conn, *, call_id: str) -> sqlite3.Row | None` — reads the full `Call` row (status, filename, duration, etc.).
  - [x] Add `get_timeline_segments(conn, *, call_id: str) -> list[sqlite3.Row]` — `SELECT * FROM TimelineSegment WHERE call_id = ? ORDER BY segment_index` (identical query shape to `ml-service`'s own `get_timeline_segments`).
  - [x] Do **not** add a `set_call_status()` or any `TimelineSegment`/`AnalysisResult` write function to `web-api/app/db.py` — AD-13 reserves all `Call.status` writes and all analysis-data writes exclusively for `ml-service`'s RQ worker; `web-api`'s DB access must remain metadata-write + status/results-**read** only. This is an architectural boundary, not an oversight — do not "helpfully" add a status setter even for test convenience (see Task 3 for how tests seed data instead).

- [x] Task 2: Structured errors for the new failure states (AC: 1)
  - [x] In `web-api/app/errors.py`, add `call_not_found(call_id: str) -> UploadValidationError` (`error_code="CALL_NOT_FOUND"`, `status_code=404`) and `call_not_complete(call_id: str, status: str) -> UploadValidationError` (`error_code="CALL_NOT_COMPLETE"`, `status_code=409`, message states the Call's actual current status so the Analyst/frontend knows what's happening, per FR-3's "never leaves the Analyst looking at an unchanging screen" spirit). Reuse the existing `UploadValidationError` class and its already-registered exception handler as-is (`error_code`/`message`/`next_step` envelope) — its name is a Story 1.1 holdover, but its shape is fully generic; do not rename the class in this story, that is an unrelated cleanup out of scope here.

- [x] Task 3: `GET /calls/{call_id}/timeline` endpoint (AC: 1, 2, 3)
  - [x] Add the route to the existing `web-api/app/routers/calls.py` (same file as `POST /calls` — one router for the `Call` resource, not a new router module).
  - [x] Declare as a plain `def` (not `async def`), matching `upload_call`'s documented rationale — this handler's only work is blocking SQLite reads, and FastAPI runs `def` path operations in a worker thread pool automatically.
  - [x] Look up the Call via `db.get_call`. If `None`, raise `errors.call_not_found(call_id)` (404).
  - [x] If the Call's `status != "complete"`, raise `errors.call_not_complete(call_id, call["status"])` (409) — this applies uniformly to `queued`, `processing`, and `failed`; do not special-case `failed` differently in this story (no AC requires it, and inventing a distinct behavior here would be undocumented scope creep).
  - [x] Otherwise, read segments via `db.get_timeline_segments` (already chronologically ordered by `segment_index` — AC1/AC3) and return:
    ```json
    {
      "call_id": "...",
      "status": "complete",
      "segments": [
        {
          "segment_id": "...",
          "start_time": 0.0,
          "end_time": 2.0,
          "fused_sentiment": "negative",
          "fused_emotion": "angry",
          "fused_confidence": 0.83,
          "disagreement_flag": false
        }
      ]
    }
    ```
    Map `TimelineSegment.id` → `segment_id`, cast `disagreement_flag` to `bool()` (stored as SQLite `INTEGER` 0/1). A Call with zero `TimelineSegment` rows (Story 1.6's "no speech detected" outcome — silence/no-speech audio, `Call.status` still reaches `complete` with no `AnalysisResult` row) is a **valid** result here too: return `"segments": []`, not an error — do not treat an empty list as a not-found or not-ready condition.
  - [x] Return a plain `dict` (no Pydantic response model) — matches `upload_call`'s existing convention exactly; the `models/` package is currently empty, do not populate it in this story.
  - [x] No pagination, no query-string filtering (e.g. by time range) — a Call is capped at 30 minutes (AD-20) with VAD-bounded segment counts; out of scope until real usage data suggests otherwise.

- [x] Task 4: Tests (AC: 1, 2, 3, 4)
  - [x] Create `web-api/tests/test_timeline.py`. Define local helpers (not added to `conftest.py` — mirrors `ml-service` tests' own `_seed_*` local-helper style): a helper that inserts a `Call` row directly via `db.insert_call(..., status=<desired status>)`, and a helper that inserts `TimelineSegment` rows via a **raw `conn.execute(INSERT INTO TimelineSegment ...)`** — deliberately not a new `db.py` write function (Task 1's boundary rule: `web-api` production code never writes this table, but test setup may poke the schema directly since it's the same physical SQLite file `ml-service` would otherwise populate).
  - [x] AC1 — happy path: a `complete` Call with 2+ segments, one multimodal (`disagreement_flag=0`) and one single-modality — assert the response returns both segments with `fused_sentiment`/`fused_emotion`/`fused_confidence`/`disagreement_flag` populated and `disagreement_flag is False`.
  - [x] AC1 — zero-segment `complete` Call (Story 1.6's silence/no-speech case): assert `200` with `"segments": []`, not an error.
  - [x] AC2 — granularity: 2 segments with **different** `fused_sentiment` values on the same Call — assert both appear distinctly in the response (never merged/aggregated into one entry).
  - [x] AC3 — boundary pass-through: assert the response's `start_time`/`end_time` for each segment exactly equal the values that were inserted (no recomputation).
  - [x] Chronological ordering: insert segments with `segment_index` out of insertion order — assert the response array is ordered by `segment_index` regardless of insertion order.
  - [x] 404: request a `call_id` that does not exist — assert `404`, `error_code == "CALL_NOT_FOUND"`, and the standard `error_code`/`message`/`next_step` envelope shape.
  - [x] 409: parametrize over `queued`, `processing`, `failed` — assert `409`, `error_code == "CALL_NOT_COMPLETE"`, and that `message` names the Call's actual current status.
  - [x] AC4: this whole file is independently runnable via `pytest web-api/tests/test_timeline.py` with no external services (no Redis/queue needed — this endpoint touches only SQLite).

- [x] Task 5: Full verification pass
  - [x] Run the full `web-api` test suite. Unlike `ml-service` (PyTorch, no native wheel on this Intel Mac sandbox — Docker-only), `web-api` has **no heavy ML dependency** and an already-populated `.venv` (`fastapi`, `pytest`, `ruff`, `fakeredis`, etc. all installed) — run tests **natively**: `cd web-api && .venv/bin/pytest`. Do not spin up a Docker container for this story; that would be needless overhead specific to `ml-service`'s PyTorch constraint, which does not apply here.
  - [x] Run `.venv/bin/ruff check .` from `web-api/` — clean.
  - [x] Run `docker compose config --quiet` from the repo root — valid (no `docker-compose.yml` changes expected this story; confirm none were needed).

### Review Findings (AI)

- [x] [Review][Patch] `get_timeline` never catches `sqlite3.Error` — a genuine DB failure (e.g. a lock timeout under concurrent WAL writes, a scenario this very file's own comments call out) propagates as an unhandled exception, surfacing FastAPI's raw default 500 instead of this app's `error_code`/`message`/`next_step` contract that every other endpoint (`upload_call`) uses. [web-api/app/routers/calls.py:144-152] — **Fixed:** both `db.get_call`/`db.get_timeline_segments` calls now wrapped in `except sqlite3.Error as exc: raise errors.internal_error(...)`, kept distinct from the `call_not_found`/`call_not_complete` business-logic raises.
- [x] [Review][Patch] `acoustic_emotion`/`acoustic_confidence` are read via `SELECT *` in `get_timeline_segments` but silently dropped when building the response, with no comment stating this is a deliberate FR-13/Epic-2 scope cut rather than an oversight. [web-api/app/routers/calls.py:159-170] — **Fixed:** added an inline comment in the response dict comprehension.
- [x] [Review][Patch] `calls.py`'s module docstring still describes the file as only the upload endpoint — no mention that it now also owns `GET /calls/{call_id}/timeline`. [web-api/app/routers/calls.py:1-21] — **Fixed:** docstring rewritten to describe both endpoints.
- [x] [Review][Patch] `test_complete_call_returns_multimodal_and_single_modality_segments` seeds `single_modality_flag=1` on its second segment (implying that behavior is under test) but never asserts on it — and since `single_modality_flag` is intentionally excluded from the response per this story's own spec, there is nothing to assert; leaves a misleading impression of coverage. [web-api/tests/test_timeline.py] — **Fixed:** added a clarifying comment; also added a `disagreement_flag is False` assertion on that same second segment (previously unchecked).
- [x] [Review][Patch] No test exercises `disagreement_flag=True` — every seeded segment across all 9 tests uses the default `0`/`False`, and the existing happy-path test never asserts `disagreement_flag` on its second segment either. [web-api/tests/test_timeline.py] — **Fixed:** added `test_disagreement_flag_true_is_returned`.
- [x] [Review][Defer] No index on `TimelineSegment(call_id, segment_index)` [web-api/app/db.py] — deferred, low priority: `get_timeline_segments` does a full scan per request, but Call duration is capped at 30 minutes with VAD-bounded segment counts (AD-20), so table size stays small for MVP. Revisit if real usage data shows this mattering.
- [x] [Review][Defer] `PRAGMA foreign_keys` is never enabled, so `TimelineSegment.call_id REFERENCES Call(id)` is decorative only [web-api/app/db.py] — deferred, pre-existing: identical gap already deferred from Story 1.3's review for `ml-service/app/db.py`; this story's mirrored DDL now carries the same unenforced pattern. See `deferred-work.md`'s Story 1.3 entry (updated below).
- [x] [Review][Defer] AD-13's "web-api never writes `Call.status`/`TimelineSegment`/`AnalysisResult`" boundary is enforced only by docstrings/comments, with no automated test or lint rule guarding against a future regression [web-api/app/db.py] — deferred, cross-cutting: would need a dedicated architecture-guard test or lint rule, out of scope for a single story. Revisit if a future change ever threatens this boundary.
- [x] [Review][Defer] `ORDER BY segment_index` has no tiebreaker for duplicate indices [web-api/app/db.py, get_timeline_segments] — deferred, mirrors `ml-service/app/db.py`'s own `get_timeline_segments` query exactly (identical missing tiebreaker, never flagged in Stories 1.2/1.3/1.6 reviews). Fixing only the web-api copy would violate this story's own column-for-column/query-for-query mirroring requirement (AD-7) by making the two diverge. Revisit both together if ever addressed.
- [x] [Review][Defer] No `CHECK (end_time >= start_time)` constraint on `TimelineSegment` [web-api/app/db.py] — deferred, same mirroring rationale as the `ORDER BY` tiebreaker above: the DDL is a hand-synced mirror of `ml-service`'s own schema, which lacks this constraint too; this story is not the schema's owner. Revisit both together if ever addressed.
- [x] [Review][Defer] Call status strings (`"complete"`, `"queued"`, `"processing"`, `"failed"`) are hardcoded with no shared enum/constant, now repeated once more across `errors.py`/`calls.py`/tests [web-api/app/errors.py, web-api/app/routers/calls.py] — deferred, pre-existing: both services have used raw string literals for status since Story 1.1; a shared status enum would be a cross-cutting change touching both `web-api` and `ml-service`, not this story's to make alone.

## Dev Notes

### Critical context — this is the first read/retrieval endpoint in the whole project

Every prior Epic 1 story (1.1–1.6) only ever wrote data (`POST /calls` in Story 1.1; everything else runs inside `ml-service`'s RQ worker, invisible to HTTP). As of Story 1.6, `web-api/app/routers/calls.py` contains **exactly one route**: `POST /calls`. There is no status-polling endpoint, no results endpoint, nothing — confirmed by grepping the whole repo for `@router.` / `APIRouter()` / `FastAPI(`. This story is the first to add a `GET` route and the first to make `web-api` read analysis data that only `ml-service` ever writes. There is no existing GET-endpoint pattern in this codebase to copy beyond FastAPI's own idioms (path param as a plain typed function argument, structured-exception-handler pattern already established by `errors.py`/`main.py`) — verified current against FastAPI 0.141.1's own docs (`fastapi.tiangolo.com/tutorial/handling-errors`, `fastapi.tiangolo.com/reference/parameters`): `@app.exception_handler(CustomException)` + a plain path parameter is still the idiomatic approach, matching what Story 1.1 already built. No new pattern is being introduced.

### The `web-api` / `ml-service` DB boundary (AD-7, AD-13) — the one rule this story must not violate

`web-api` and `ml-service` are two separate Python processes/containers that share one SQLite file via a filesystem volume — never a shared Python import (`ml-service/app/db.py`'s own docstring: "Deliberately does NOT import web-api/app/db.py... kept schema-compatible by hand"). AD-13 is explicit: *"Only the ML/audio service's RQ worker process writes `Call.status` transitions... the web/API process never writes `Call.status`... `API --> DB` in the container diagram is a metadata-write and status/results-**read** path only, never a status-write path."*

Concretely for this story:
- `web-api/app/db.py` gains **read-only** access to `TimelineSegment` (`get_timeline_segments`) and a general `Call` reader (`get_call`).
- `web-api/app/db.py` must **not** gain a `TimelineSegment`/`AnalysisResult` writer, nor a `Call.status` writer. `ml-service/app/db.py` already has `set_call_status` — that capability must never be duplicated into `web-api`, even for test convenience. Tests seed status via `insert_call(..., status=<whatever status the test needs>)` directly (that function already accepts any status string — it's not restricted to `"queued"`) and seed `TimelineSegment` rows via a raw SQL `INSERT` written inline in the test file, not a new production helper.
- The `TimelineSegment` DDL added to `web-api/app/db.py` must match `ml-service/app/db.py`'s column-for-column — this repo already has one precedent for this exact hand-sync discipline (the `Call` table, present in both files today with an explicit comment in each explaining why). Follow that precedent, don't invent a new one.

### Response contract (this story's own design decision — no prior art in this codebase to follow)

No epics/architecture text specifies the exact HTTP method, path, or JSON shape — only the *content* requirements (AC1–3). This is a genuine design decision; the following was decided by this story-context pass:

- **Route:** `GET /calls/{call_id}/timeline` — a sub-resource of the existing `/calls` collection, consistent REST shape with `POST /calls`.
- **Success (200):** `{"call_id": ..., "status": "complete", "segments": [...]}`. Each segment: `segment_id` (the `TimelineSegment.id`, the AD-11/NFR-1 evidence-linkage join key — future stories, e.g. FR-13 drill-down in Epic 2, need this to correlate a timeline point back to transcript/acoustic evidence, so it must be present even though AC1 doesn't spell it out by name), `start_time`, `end_time`, `fused_sentiment`, `fused_emotion`, `fused_confidence`, `disagreement_flag` (bool). Field names reuse the DB column names verbatim — Consistency Conventions' naming rule ("reuse Glossary-term naming... wherever the concept matches directly") — no invented API-only aliases.
- **Not found (404):** Call id does not exist at all. `error_code="CALL_NOT_FOUND"`.
- **Not ready (409):** Call exists but `status != "complete"` (covers `queued`, `processing`, and `failed` uniformly — no AC distinguishes them, don't invent a distinction). `error_code="CALL_NOT_COMPLETE"`, message states the actual status.
- **Zero-segment Call:** `200` with `"segments": []` — a *valid* result, not an error. This directly continues Story 1.6's own code-review decision (2026-08-14): a Call with zero `TimelineSegment` rows (silence/no-speech audio) reaches `status="complete"` with no `AnalysisResult` row; `get_analysis_result(...)` returning `None` was already established as the well-defined "no speech detected" signal there. This endpoint doesn't touch `AnalysisResult` at all (out of scope, see below) but must not misinterpret an empty segment list as an error state — the Call really did complete, it just has nothing to show on the timeline.
- No Pydantic response model — `models/` is empty and `upload_call` already returns a bare `dict`; stay consistent, don't introduce a new response-typing pattern in this story.

### What NOT to build in this story

- **No `AnalysisResult` data in the response.** FR-12 (full Analysis Result view) and the Call-level Summary cells are Epic 2 (dashboard) territory, consuming a *later* endpoint this story does not build. This story returns per-segment timeline data only.
- **No transcript or acoustic-evidence drill-down data** (FR-13) — that's the Dashboard's evidence panel, a separate future capability keyed by the same `segment_id` this story exposes, not built here.
- **No real disagreement-threshold logic.** `disagreement_flag` is already persisted as `0`/`False` on every segment by Story 1.6 (Story 1.9 owns the real detection) — this endpoint is a pure pass-through of whatever is stored; do not add threshold config or comparison logic.
- **No low-confidence flagging/threshold** (`flag_reason`, `low_confidence_threshold`) — that's Story 1.8, not built here. `fused_confidence` is returned as a bare float; Story 1.8 will add the flagging layer on top later without changing this endpoint's core shape (same forward-decoupling pattern as the disagreement flag).
- **No pagination, filtering, or partial responses** — see Task 3.
- **No changes to `ml-service`** — this story is entirely `web-api`-side; `ml-service`'s `db.py`/pipeline code is read-only reference material here, never modified.

### Previous story intelligence (Story 1.6)

- Story 1.6 explicitly deferred this exact work: *"No API endpoint. `ANALYSIS_RESULT`/fused `TimelineSegment` retrieval is Story 1.7 (Emotional Timeline Retrieval) and later Epic 2 work. This story only computes and persists."* — confirms this story is unblocked and starting from a clean slate on the `web-api` side.
- Story 1.6 added `fused_sentiment`, `fused_emotion`, `fused_confidence`, `single_modality_flag`, `disagreement_flag` to `TimelineSegment` and a new `AnalysisResult` table, all via `ml-service/app/db.py`. `disagreement_flag` is unconditionally `0` (Story 1.9's scope). A `complete` Call's segments are **always** fully populated (`fused_*` never `NULL`) once fusion has run — `persist_fusion_results` updates every segment in one transaction before the Call is marked `complete`, so there is no partial-fusion state to defend against when this endpoint reads a `complete` Call's segments.
- Story 1.6's code review (2026-08-14) established the zero-segment-Call precedent this story must respect (see Response contract above) — read `_bmad-output/implementation-artifacts/1-6-multimodal-fusion-into-a-single-analysis-result.md`'s `test_run_fusion_zero_segments_completes_with_no_analysis_result` test for the exact scenario shape to mirror on the read side.
- Story 1.6 (and 1.3, 1.4, 1.5 before it) deferred a recurring pattern: `conn = db.get_connection()` sitting outside its own `try`/`except`. That pattern is `ml-service`-side and doesn't apply to a read-only `web-api` `def` handler the same way — FastAPI's own exception handling wraps the whole request; no action needed here, noted only so it isn't mistakenly "fixed" in the wrong service.
- Story 1.6 ran all verification in Docker because `ml-service` depends on PyTorch (no native wheel on this Intel Mac sandbox). **That constraint does not apply to `web-api`** — its `.venv` already has every dev dependency installed natively (verified: `python 3.13.15`, `pytest 8.4.2` runnable directly). Use the native path (Task 5); don't default to Docker out of habit from the last six stories.

### Architecture compliance (non-negotiable)

- **AD-7** — `web-api` and `ml-service` remain separate deployables; this story adds no import between them, only a hand-synced schema mirror (same technique already used for `Call`).
- **AD-11** — segment boundaries returned are the exact `start_time`/`end_time` already persisted on `TimelineSegment` by Story 1.2's ingest stage; this endpoint computes nothing, it only reads.
- **AD-13** — `web-api`'s DB access stays read-only for status/results; see the DB boundary section above.
- **AD-15** — `fused_sentiment`/`fused_emotion` are returned as separate JSON fields, never merged.
- **AD-21** — this story's endpoint gets its own independently-runnable test file (`test_timeline.py`), consistent with every pipeline stage's own test file.
- **NFR-1 (explainability/evidence-linkage)** — `segment_id` is included in every returned segment specifically so later evidence-drill-down work (FR-13) has a join key; omitting it would silently break that forward path.
- **FR-9** — resolution: this endpoint returns every persisted segment, so granularity is inherited entirely from Story 1.2's VAD chunking — nothing here needs to "ensure" granularity beyond passing through what's stored.

### Testing Standards

- Test file: `web-api/tests/test_timeline.py`, following `test_upload.py`'s existing style (module-level helper functions, `client` fixture from `conftest.py`, direct `db`-module access for setup/assertions).
- No new fixtures needed in `conftest.py` — the existing `client`/`fixtures_dir` fixtures are upload-specific and irrelevant here; this story's tests only need direct SQLite setup (see Task 4) and the FastAPI `TestClient`.
- Run natively: `cd web-api && .venv/bin/pytest` (fast — no Docker, no model downloads, unlike every `ml-service` story so far).
- `.venv/bin/ruff check .` from `web-api/`.
- `docker compose config --quiet` from repo root (sanity check only — no compose changes expected).

### Project Structure Notes

- Modify: `web-api/app/db.py` (add `TimelineSegment` DDL, `get_call`, `get_timeline_segments`).
- Modify: `web-api/app/errors.py` (add `call_not_found`, `call_not_complete`).
- Modify: `web-api/app/routers/calls.py` (add the `GET /calls/{call_id}/timeline` route).
- Create: `web-api/tests/test_timeline.py`.
- No changes to `web-api/app/main.py` (the route is registered automatically via the existing `calls_router` include — no new router object to wire in), `web-api/app/config.py`, `web-api/app/queue.py`, `web-api/app/audio_validation.py`, or anything under `ml-service/`.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.7: Emotional Timeline Retrieval] (lines 250–264, AC + dependency note)
- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.6: Multimodal Fusion into a Single Analysis Result] (lines 232–248, upstream data producer)
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#AD-7] (lines 75–89, consolidated ML service boundary / job-queue-only crossing)
- [Source: ARCHITECTURE-SPINE.md#AD-11] (lines 114–118, one VAD boundary set, two consumers, many-to-many TranscriptTurn overlap)
- [Source: ARCHITECTURE-SPINE.md#AD-13] (lines 126–130, "API --> DB... status/results-read path only, never a status-write path")
- [Source: ARCHITECTURE-SPINE.md#AD-15] (lines 138–142, Sentiment/Emotion separately-addressable fields)
- [Source: ARCHITECTURE-SPINE.md#Consistency Conventions] (lines 180–186, naming reuse, `segment_id` evidence-linkage join key)
- [Source: ARCHITECTURE-SPINE.md#Capability → Architecture Map] (lines 263–285: FR-9 → `ml-service/pipeline/ingest`; FR-12/FR-13 → "SQLite storage schema + evidence-linkage join"; source tree sketch line 235: `web-api/` owns "results API")
- [Source: web-api/app/db.py] (full file read — current `Call`-only schema, hand-sync-with-`ml-service` precedent/docstring)
- [Source: web-api/app/routers/calls.py] (full file read — only existing route, plain-`def`-for-blocking-I/O rationale, structured-error-on-failure pattern)
- [Source: web-api/app/errors.py] (full file read — `UploadValidationError` class/handler shape to reuse)
- [Source: web-api/app/main.py], [Source: web-api/app/config.py] (full files read — router registration, no `TimelineSegment`-relevant config needed)
- [Source: web-api/tests/conftest.py], [Source: web-api/tests/test_upload.py] (full files read — existing test conventions, native `.venv` availability)
- [Source: ml-service/app/db.py] (full file read — authoritative current `TimelineSegment`/`AnalysisResult`/`Call` schema to mirror; `persist_fusion_results` atomicity comment confirming a `complete` Call's segments are always fully populated)
- [Source: _bmad-output/implementation-artifacts/1-6-multimodal-fusion-into-a-single-analysis-result.md] (Dev Notes, Review Findings, and Change Log sections — zero-segment-Call decision, "No API endpoint" scope note, fusion schema additions)
- [Source: FastAPI 0.141.1 official docs via Context7 (`/websites/fastapi_tiangolo`), "Handling Errors" and "Path Parameters" pages — confirmed `@app.exception_handler`-based custom exceptions and plain typed path parameters remain the current idiomatic approach, matching what Story 1.1 already built; no new pattern needed]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5

### Debug Log References

- Confirmed via repo-wide grep (`@router\.|APIRouter|FastAPI(`) that `POST /calls` was the only existing HTTP route in the project before this story — no prior GET-endpoint pattern to follow, so the route/response/error contract was designed fresh in the story-context pass and implemented as specified.
- Confirmed `web-api`'s `.venv` already has `fastapi`/`pytest`/`ruff`/`fakeredis` installed natively (`python 3.13.15`, `pytest 8.4.2`) — ran all verification natively, no Docker container needed (unlike every `ml-service` story so far, which requires Docker due to PyTorch having no native wheel on this Intel Mac sandbox).
- Verified FastAPI 0.141.1's current idiomatic pattern for custom exception handlers + path parameters via Context7 (`/websites/fastapi_tiangolo`) before implementing — confirmed `@app.exception_handler(CustomException)` (already used by `errors.py`/`main.py`) and a plain typed path-parameter argument are still current; no new pattern introduced.
- Verified by direct inspection of `ml-service/app/db.py`'s `persist_fusion_results` that a `complete` Call's `TimelineSegment` rows are always fully fusion-populated (single transaction, status write folded in per Story 1.6's code review) — so this endpoint's read path never needs to defend against a partially-fused `complete` Call.
- Wrote `test_timeline.py` before running it to confirm all 9 new tests pass against the implementation in one pass (endpoint, DB layer, and errors were implemented together as a small, tightly-coupled unit — RED phase was implicit: the tests import `db.get_call`/`get_timeline_segments` and the `/timeline` route, none of which existed before this task).

### Completion Notes List

- Implemented `GET /calls/{call_id}/timeline` (Story 1.7) — the first read/retrieval HTTP endpoint in the project. Added read-only `TimelineSegment` access to `web-api` (hand-synced DDL mirroring `ml-service`'s schema, per the established `Call`-table precedent) without adding any write capability for that table or for `Call.status`, preserving AD-13's web-api/ml-service DB boundary.
- Response contract (route, JSON shape, 404/409 error codes) was a genuine design decision with no prior art in this codebase — documented in the story's Dev Notes and implemented exactly as specified there.
- Zero-`TimelineSegment` `complete` Calls (Story 1.6's "no speech detected" outcome) return `200` with `"segments": []`, continuing that story's precedent rather than treating an empty result as an error.
- All verification ran natively via `web-api/.venv` (no Docker needed — `web-api` has no PyTorch/heavy-ML dependency, unlike `ml-service`). Full suite: 35 passed (9 new + 26 pre-existing, no regressions). `ruff check .`: clean. `docker compose config --quiet`: valid.

### Code review follow-up (2026-08-14)

3-layer adversarial review (Blind Hunter, Edge Case Hunter, Acceptance Auditor) ran against the full NO_VCS diff (1 new + 3 modified files, ~634 lines). Outcome: 0 decision-needed, 5 patch, 6 defer (mostly cross-referencing pre-existing `ml-service`/prior-story patterns, or explicit AD-7 mirroring-consistency tradeoffs), 9 dismissed as noise (5 refuted by re-reading the actual code/re-running tests, 4 matching this story's own explicitly-documented scope decisions).

- **Acceptance Auditor**: no blocking violations — verified all 4 ACs and every Dev Notes constraint (AD-7 hand-sync confirmed column-for-column and query-text-identical against `ml-service/app/db.py`, AD-11/AD-13/AD-15 respected, response contract matches spec exactly). Two cosmetic observations became patches (see below).
- **Blind Hunter / Edge Case Hunter**: raised 14 items; 5 became patches, 4 became new `deferred-work.md` entries (index, ORDER BY tiebreaker, CHECK constraint, status-string enum — the latter two explicitly justified by *not* wanting to unilaterally diverge from `ml-service`'s hand-synced schema/query), 1 updated an existing Story 1.3 deferred entry (`PRAGMA foreign_keys`), and the rest were refuted: NULL fused-field reachability (refuted by Story 1.6's `persist_fusion_results` atomicity invariant — a `complete` Call's segments are always fully populated), case-insensitive `call_id` lookup (refuted — exact-match UUID lookup is correct, not a bug), non-0/1 `disagreement_flag` values (refuted — every writer passes a Python `bool`, `sqlite3` only ever stores `0`/`1`), test hermeticity (refuted — actually re-ran the suite, 36/36 passed), and float `==` in tests (refuted — pure storage/retrieval round-trip, no arithmetic, IEEE-754 doubles round-trip exactly).
- Applied all 5 patches: `sqlite3.Error` handling in `get_timeline` (kept distinct from the `call_not_found`/`call_not_complete` business raises), a comment explaining the deliberate `acoustic_*` response exclusion, an updated module docstring, a clarifying comment + missed assertion in the existing happy-path test, and a new `test_disagreement_flag_true_is_returned` test.
- Re-verified after patches: 36/36 tests passed (35 + 1 new), `ruff check .` clean, `docker compose config --quiet` valid.

### File List

**Modified:**
- `web-api/app/db.py` — added `_CREATE_TIMELINE_SEGMENT_TABLE` DDL (registered in `init_db()`), `get_call()`, `get_timeline_segments()`.
- `web-api/app/errors.py` — added `call_not_found()`, `call_not_complete()`.
- `web-api/app/routers/calls.py` — added `GET /calls/{call_id}/timeline` route.

**Created:**
- `web-api/tests/test_timeline.py` — 9 tests covering AC1 (multimodal + single-modality segments, zero-segment call), AC2 (distinct segments never merged), AC3 (boundary pass-through), chronological ordering, 404, and 409 (parametrized over `queued`/`processing`/`failed`).

## Change Log

### 2026-08-14 — Initial implementation

Implemented `GET /calls/{call_id}/timeline` — the project's first read/retrieval endpoint. Added read-only `TimelineSegment` access to `web-api/app/db.py` (schema hand-synced with `ml-service`, AD-7/AD-13 boundary preserved — no write capability added), structured `CALL_NOT_FOUND`/`CALL_NOT_COMPLETE` errors, and the endpoint itself in `web-api/app/routers/calls.py`. All 4 ACs covered by 9 new tests in `web-api/tests/test_timeline.py`. Full `web-api` suite: 35/35 passed (native `.venv`, no Docker required — no PyTorch dependency in this service). `ruff check .` clean, `docker compose config --quiet` valid. Status: ready-for-dev → review.

### 2026-08-14 — Code review

3-layer adversarial review resolved: 5 patch findings fixed (structured error handling for SQLite failures, a documentation comment for the deliberate `acoustic_*` response exclusion, an updated module docstring, and two test-coverage gaps — `disagreement_flag=True` and a missed assertion). 6 findings deferred to `deferred-work.md` (index, FK enforcement, `ORDER BY` tiebreaker, `CHECK` constraint, status-string enum, AD-13 automated-guard gap). 9 dismissed as refuted or already-decided-in-spec. Re-verified: 36/36 tests passed, `ruff check .` clean, `docker compose config --quiet` valid. Status: review → done.
