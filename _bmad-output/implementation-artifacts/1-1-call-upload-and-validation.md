---
baseline_commit: NO_VCS
---

# Story 1.1: Call Upload & Validation

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an Analyst,
I want to upload a Call recording and receive clear validation feedback,
so that I can begin analysis only with a valid audio file and understand immediately if something is wrong.

## Acceptance Criteria

1. **Given** a WAV, MP3, or M4A file under 200MB and under 30 minutes, **when** the Analyst uploads it, **then** the system accepts it, creates a `Call` record with status `queued`, and returns a Call identifier. [Source: epics.md#Story 1.1; AD-20]
2. **Given** a file in an unsupported format, **when** uploaded, **then** the system rejects it with a structured error naming the specific unsupported format, and no `Call` record is created. [Source: epics.md#Story 1.1; FR-2]
3. **Given** a file exceeding 200MB or 30 minutes, **when** uploaded, **then** the system rejects it with a structured error naming the specific limit exceeded (size or duration). [Source: epics.md#Story 1.1; AD-20]
4. **Given** a non-decodable/corrupt file, **when** uploaded, **then** the system rejects it with a structured error identifying it as undecodable, before any analysis begins. [Source: epics.md#Story 1.1; FR-1]
5. **Given** any rejection above, **then** the error message tells the Analyst what to do next (e.g., "re-export in WAV, MP3, or M4A"). [Source: epics.md#Story 1.1; FR-2]
6. **Given** this is the first story of the project, **then** the repo is scaffolded per the Architecture source tree (`web-api/`, `ml-service/`, `frontend/`, `storage/`, `docker-compose.yml`); a `Call` table exists in SQLite; a GitHub Actions workflow runs lint+tests on every push (AD-21); the docker-compose stack serves the upload endpoint (AD-18). [Source: epics.md#Story 1.1; ARCHITECTURE-SPINE.md#Structural Seed, AD-18, AD-21]

## Tasks / Subtasks

- [x] Task 1: Scaffold the repository per the Architecture source tree (AC: 6)
  - [x] Create top-level directories: `web-api/`, `ml-service/pipeline/{ingest,acoustic,transcript,fusion,calibration}/`, `frontend/`, `storage/` — empty pipeline/frontend dirs get a placeholder (e.g. `.gitkeep` or minimal `README.md`) since their code lands in later stories (1.2+, 2.1). Do not implement pipeline or frontend logic in this story.
  - [x] Create `docker-compose.yml` defining, at minimum, a fully working `web-api` service (build + port + volume mount to `storage/`); `frontend`, `ml-service`, and `redis` services may be stubs/placeholders matching the Structural Seed but are not required to be functional until Stories 2.1 and 1.2 respectively.
  - [x] Pin `web-api`'s Python dependency to **Python 3.13.15** and **FastAPI 0.141.1** per the Stack table — do not substitute other versions.
- [x] Task 2: Set up CI (AC: 6)
  - [x] Add a GitHub Actions workflow that runs lint (e.g. `ruff`) and `pytest` for `web-api/` on every push — no deploy step (AD-21 explicitly excludes deployment; AD-18 confirms no live hosting target).
- [x] Task 3: Define the `Call` table and minimal SQLite access layer (AC: 1, 6)
  - [x] Create the `Call` entity in SQLite (stdlib `sqlite3`, per Stack table) with, at minimum: an identifier, `status` (state machine value, starts `queued`), `filename`, `format`, `duration_seconds`, `size_bytes`, and a record-level `created_at` timestamp in ISO 8601 UTC (per Consistency Conventions). Exact DDL/column types are an implementation-time decision (Architecture's Deferred section explicitly leaves schema DDL to code) — do not add columns for `TranscriptTurn`/`TimelineSegment`/`AnalysisResult`/`ACOUSTIC_EVIDENCE`; those tables belong to later stories (1.2–1.6) per the "create tables only when needed" convention already validated for this epic.
  - [x] Use `Call` as the literal entity/table name (PRD Glossary term reuse, per Consistency Conventions) — never a synonym.
- [x] Task 4: Implement the upload endpoint (AC: 1, 2, 3, 4, 5)
  - [x] `POST` endpoint in `web-api/` accepting `multipart/form-data` with a single audio file, using FastAPI's `UploadFile` parameter type (spooled temp file — safe for the 200MB ceiling without loading the whole file into memory). See Dev Notes for FastAPI-specific guidance.
  - [x] Validate format by file extension/content-type against the fixed set `{WAV, MP3, M4A}` (AD-20 — this list is an adopted decision, not deferred; do not add or remove formats).
  - [x] Validate size against the fixed 200MB ceiling and duration against the fixed 30-minute ceiling (AD-20).
  - [x] Validate decodability (file actually opens as valid audio) before creating any `Call` record — see Dev Notes for the recommended check.
  - [x] On success: persist the raw audio to `storage/` under a path keyed by the generated `Call` id (e.g. `storage/{call_id}/original.<ext>`) — never the client-supplied filename verbatim (see Dev Notes security note). This is the file later pipeline stages (Story 1.2 ingest onward) will read from.
  - [x] On success: create the `Call` row with status `queued`, return `{call_id, status}` (or equivalent) to the client.
  - [x] On any validation failure: return a structured, rule-specific error object (machine-readable `error_code` + human message + "what to do next" guidance) per the Consistency Conventions — see Dev Notes for the proposed shape. No `Call` record is created on any rejection path.
- [x] Task 5: Tests (AC: 1, 2, 3, 4, 5, 6)
  - [x] Unit/integration tests (pytest + FastAPI `TestClient`) covering: valid upload (each of WAV/MP3/M4A), oversized file, over-duration file, unsupported format, corrupt/undecodable file, and the exact shape of each error response.
  - [x] Confirm tests run via the GitHub Actions workflow added in Task 2.

## Dev Notes

**This is the first story of the project — greenfield, no existing code, not yet a git repository.** There is no previous story and no prior commit history to learn from; you are establishing the initial patterns every later story will follow. Be deliberate.

### Architecture compliance (non-negotiable)

- **Service boundary (AD-7):** This story lives entirely in `web-api/`. Do not write any pipeline/analysis code here, and do not have `web-api` import anything from `ml-service`. `web-api`'s only job this story is: validate the upload, write `Call` metadata, serve the endpoint. Analysis dispatch (RQ enqueue) is Story 1.2's scope, not this one — this story ends with the Call sitting in `queued`.
- **DB write scope (AD-13):** `web-api` may only ever write Call *metadata* (never `Call.status` transitions beyond the initial `queued` insert at creation). All later status transitions (`processing`/`complete`/`failed`) are written exclusively by the ML service's RQ worker starting in Story 1.2 — do not build any status-transition logic here beyond the single initial `queued` write.
- **Fixed ingest constants (AD-20):** formats `{WAV, MP3, M4A}`, max duration 30 minutes, max size 200MB. These are adopted architecture decisions, not deferred/tunable — hardcode or config them as fixed values, not as something an operator is expected to change.
- **Error shape (Consistency Conventions, "State & cross-cutting"):** "Upload/ingest validation failures (FR-2) return structured, rule-specific error objects (machine-readable error code + message per failed rule), not a generic validation error." Recommended concrete shape (not itself an Architecture mandate, but the natural fit for the convention above and this story's AC 2–5):
  ```json
  {
    "error_code": "UNSUPPORTED_FORMAT | FILE_TOO_LARGE | DURATION_EXCEEDED | UNDECODABLE_FILE",
    "message": "human-readable, names the specific failed rule",
    "next_step": "actionable guidance, e.g. 're-export in WAV, MP3, or M4A'"
  }
  ```
- **Naming (Consistency Conventions):** reuse PRD Glossary terms directly in code/schema/API — `Call`, never a synonym. Record-level timestamps are ISO 8601 UTC.
- **No starter template (Architecture "No external starter template"):** scaffold the source tree natively yourself per the Structural Seed below — do not run `create-react-app`, a FastAPI cookiecutter, or any other scaffolding tool.
- **Security note (file storage):** never use the client-supplied filename to construct a filesystem path directly (path-traversal / overwrite risk). Persist uploaded audio under a server-generated `Call` id, e.g. `storage/{call_id}/original.<ext>`; keep the original filename only as a metadata field on the `Call` row for display purposes (Epic 2's Call row shows it).

### Source tree to create (Structural Seed)

```text
{root}/
  web-api/              # FastAPI app: upload/ingest endpoint (this story), status polling + results API (later stories)
  ml-service/
    pipeline/
      ingest/            # placeholder only — Story 1.2
      acoustic/          # placeholder only — Story 1.3
      transcript/        # placeholder only — Stories 1.4/1.5
      fusion/            # placeholder only — Story 1.6
      calibration/       # placeholder only — Stories 1.3/1.5/1.6
  frontend/              # placeholder only — Story 2.1 (React 19 app)
  storage/               # session-scoped filesystem volume: uploaded audio + intermediate artifacts (used starting this story for the raw upload)
  docker-compose.yml     # web-api (functional this story) + frontend/ml-service/redis (stubs, functional in later stories)
```
[Source: ARCHITECTURE-SPINE.md#Structural Seed]

### FastAPI upload/validation specifics (verified against current FastAPI docs)

- Use `UploadFile` (not raw `bytes`), e.g.:
  ```python
  from typing import Annotated
  from fastapi import FastAPI, File, UploadFile

  @app.post("/calls")
  async def upload_call(file: UploadFile):
      ...
  ```
  `UploadFile` wraps a spooled temp file (memory up to a limit, then disk) — this is the efficient choice for files up to 200MB; avoid `Annotated[bytes, File()]`, which loads the whole file into memory.
- `UploadFile` exposes `.filename`, `.size`, `.content_type`, and an async `.read(size=-1)` — use `.filename` for extension-based format pre-check and `.size` for the size-ceiling check before doing any heavier work.
- For structured error responses, define a custom exception (e.g. `UploadValidationError(error_code, message, next_step)`) and register it with `@app.exception_handler(UploadValidationError)` returning a `JSONResponse` with the shape above — this is the FastAPI-idiomatic way to get a consistent, structured error contract across all four rejection rules, rather than ad hoc `HTTPException(detail=...)` calls with inconsistent shapes per route.
  [Source: FastAPI docs — Handling Errors / custom exception handlers, retrieved via Context7 for current API shape]

### Decodability check (Task 4, AC 4) — dev agent decision, not an Architecture mandate

Architecture pins `librosa` 0.11.0 and `torchaudio` 2.11.0 in the Stack table, but assigns them to `ml-service`'s handcrafted-feature extraction (AD-3) — it does not assign a decode-check library to `web-api`. Recommended default: reuse `torchaudio.info()` (a lightweight header/metadata probe, not a full decode) or `soundfile`, since `torchaudio` is already a pinned project dependency and avoids adding a new one solely for this check. Do not add a new audio library to the Stack table without noting it in this story's Dev Agent Record — the goal is "no story may build cross-session/durable retention beyond what a session/demo requires" discipline extended here to "no story silently adds new architecture-level dependencies."

### What NOT to build in this story

- No RQ/Redis job enqueue, no async processing lifecycle (`processing`/`complete`/`failed` transitions) — Story 1.2.
- No acoustic/transcript/fusion pipeline code of any kind — Stories 1.3–1.9.
- No delete endpoint — Story 1.10 (split out specifically to keep this story and Story 1.2 scoped to upload/ingest only).
- No frontend/UI of any kind — Epic 2. The Analyst-facing framing in this story's user-story statement describes the *capability* being built, not a UI; the response contract from this endpoint (`call_id`, `status`, structured errors) is what Epic 2's Story 2.2 will consume later, so keep it clean and stable rather than ad hoc.

### Testing Standards

- `pytest` + FastAPI's `TestClient` (httpx-based) for endpoint tests, per the Stack's Python/FastAPI pairing.
- Per AD-21: this module's tests must be independently runnable (`pytest web-api/`) without requiring the full docker-compose stack up.
- Cover every AC explicitly: 3 valid-format acceptances, 1 oversized, 1 over-duration, 1 unsupported-format, 1 corrupt-file, plus assertions on the exact `error_code`/`message`/`next_step` shape for each rejection path.

### Project Structure Notes

- This story creates the *first* code in the repository — there is no existing structure to conform to or conflict with. All structure decisions here become the baseline for every subsequent story.
- Only the `Call` table is created this story (Task 3) — `TranscriptTurn`, `TimelineSegment`, `AnalysisResult`, `ACOUSTIC_EVIDENCE` are introduced incrementally by Stories 1.2, 1.3, 1.4, and 1.6 respectively, per the epic's validated "tables created only when needed" pattern. Do not pre-create them here.
- No git repository exists yet at the project root; initializing one (if not already done by tooling) is an environment-setup concern, not itself an AC of this story.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.1: Call Upload & Validation]
- [Source: _bmad-output/planning-artifacts/epics.md#Requirements Inventory — FR-1, FR-2]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#AD-20 Audio ingest constraints]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#AD-18 Deployment envelope]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#AD-21 CI, testing, and logging baseline]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#AD-7 Model serving boundary]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#AD-13 Async orchestration]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#Consistency Conventions]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#Structural Seed]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#Stack]
- [Source: _bmad-output/planning-artifacts/prds/prd-AIVoiceSentimentAnalyzer_v1-2026-08-10/prd.md#4.1 Audio Upload & Validation]
- [Source: FastAPI official docs, retrieved via Context7 (2026-08-11) — UploadFile reference, custom exception handlers]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5 (claude-sonnet-5)

### Debug Log References

- `PYTHONPATH=. .venv/bin/pytest -v` — final run **under Python 3.13.15** (exact Architecture pin): 15 passed, 1 warning, 17.13s.
- `.venv/bin/ruff check .` — final run under Python 3.13.15: all checks passed.
- `docker compose config` — validated `docker-compose.yml` renders correctly; confirms only `web-api` runs by default (frontend/redis/ml-service correctly gated behind `--profile full`), satisfying AC6 without requiring stub services to build.
- Live smoke test: started `uvicorn app.main:app` directly and exercised `POST /calls` with `curl` against real generated WAV fixtures (valid + corrupt) outside of `TestClient` — confirmed real end-to-end behavior (SQLite row written, file persisted under `storage/{call_id}/`, corrupt-file storage cleanup verified via `find`), not just in-process test-client behavior.

### Completion Notes List

- **All 6 ACs implemented and verified** by 15 passing tests plus an independent live smoke test (uvicorn + curl + sqlite3 CLI inspection), not test-suite-only verification.
- **Python interpreter — resolved to exact pin.** Architecture pins Python 3.13.15. Local system Python was initially 3.14.6, so `brew install python@3.13` was started (compiling from source, no prebuilt bottle for this platform) and testing proceeded on 3.14.6 in the interim, with no 3.14-exclusive syntax used anywhere in `app/`. The brew build later completed; `web-api/.venv` was rebuilt from `/usr/local/Cellar/python@3.13/3.13.15/bin/python3.13` (`pip install -e ".[dev]"`, satisfying `requires-python = ">=3.13,<3.14"` exactly, no workaround needed), and the full suite (15 passed) plus `ruff check .` (all checks passed) were re-run and reconfirmed under the exact pinned interpreter. `web-api/Dockerfile` (`FROM python:3.13.15-slim`) and `.github/workflows/ci.yml` (`python-version: "3.13.15"`) were already correctly pinned throughout.
- **Decodability check implementation choice:** the story's Dev Notes offered `torchaudio.info()` or `soundfile` as options. Chose **`soundfile`** (WAV/MP3 — real libsndfile-backed decode probe) **+ `mutagen.mp4.MP4`** (M4A — container/AAC-stream validation) instead of `torchaudio` alone, because libsndfile has no M4A/AAC support at all (verified empirically), so `soundfile` alone cannot cover all three required formats, and pulling in full `torchaudio`/PyTorch merely for a lightweight header probe would be a heavy, undocumented addition to `web-api`'s dependency footprint for a service that Architecture (AD-3) scopes those libraries to `ml-service` only. Verified against real generated fixtures (via a test-only `imageio-ffmpeg`-provided ffmpeg binary — never imported by app code) that both libraries correctly accept valid WAV/MP3/M4A and reject corrupted versions of each.
- **Docker image not built in this sandbox:** no Docker daemon is running here (`docker info` confirms), so the actual `docker build`/`docker compose up` could not be executed end-to-end. Mitigated by (a) `docker compose config` static validation of the compose file, and (b) direct-execution smoke testing of the identical application code the Dockerfile packages (same `pyproject.toml`, same `app/` source). The Dockerfile and compose service definition should be validated with a real `docker compose up web-api` the first time a Docker daemon is available.
- **`FastAPI`'s `@app.on_event("startup")` was not used** (initial draft) — confirmed via Context7 against current FastAPI docs that `on_event` is deprecated in favor of the `lifespan` async-context-manager pattern; implemented with `lifespan` instead.
- No new architecture-level dependency was silently introduced: `soundfile`, `mutagen` (runtime) and `imageio-ffmpeg` (test-fixture-generation only, never imported by `app/`) are all documented here and in the story's Dev Notes rationale.
- A harmless `StarletteDeprecationWarning` ("install httpx2 instead") appears during test collection. Left as-is: current official FastAPI testing docs (verified via Context7) still specify `httpx` as the required TestClient dependency; no official guidance yet recommends `httpx2`. Worth revisiting in a later story if the warning becomes an error in a future Starlette release.

### File List

**Created:**
- `web-api/pyproject.toml`
- `web-api/Dockerfile`
- `web-api/app/__init__.py`
- `web-api/app/main.py`
- `web-api/app/config.py`
- `web-api/app/db.py`
- `web-api/app/errors.py`
- `web-api/app/audio_validation.py`
- `web-api/app/routers/__init__.py`
- `web-api/app/routers/calls.py`
- `web-api/tests/__init__.py`
- `web-api/tests/conftest.py`
- `web-api/tests/test_upload.py`
- `docker-compose.yml`
- `.github/workflows/ci.yml`
- `.gitignore`
- `storage/.gitkeep`
- `ml-service/README.md`
- `ml-service/pipeline/ingest/.gitkeep`
- `ml-service/pipeline/acoustic/.gitkeep`
- `ml-service/pipeline/transcript/.gitkeep`
- `ml-service/pipeline/fusion/.gitkeep`
- `ml-service/pipeline/calibration/.gitkeep`
- `frontend/README.md`

**Modified (code-review remediation, 2026-08-12):**
- `web-api/app/errors.py` — `UploadValidationError` gained a `status_code` field; added `internal_error()` factory; `file_too_large()` now derives its MB figure from `max_bytes` instead of a hardcoded "200MB".
- `web-api/app/audio_validation.py` — `probe_audio()` now takes a file-like object instead of a `Path` (probes the spooled upload directly, before any disk write); added a content-vs-extension cross-check for WAV/MP3 via `soundfile`'s detected `format`.
- `web-api/app/routers/calls.py` — validation (format/size/decode/duration) now runs entirely before anything touches `storage/` or the DB; endpoint changed from `async def` to `def` so FastAPI dispatches it to a worker thread instead of blocking the event loop; the persist step (write + DB insert) is now the only part wrapped in cleanup-on-failure, and any unexpected exception there is cleaned up and returned as a structured `INTERNAL_ERROR` (500) instead of an unstructured 500.
- `web-api/app/db.py` — `get_connection()` now opens with a 30s busy timeout and enables WAL journal mode, reducing "database is locked" risk under concurrent uploads.
- `web-api/Dockerfile` — added baked-in `ENV STORAGE_DIR=/storage` / `ENV DB_PATH=/storage/app.db` and a `VOLUME ["/storage"]` declaration, so the image's own defaults are correct even when run without docker-compose's environment override (previously, `config.py`'s path-derived fallback only happened to be correct inside a container by coincidence of directory depth).
- `web-api/tests/conftest.py` — added a `mismatched_extension.wav` fixture (real MP3 bytes under a `.wav` name).
- `web-api/tests/test_upload.py` — `test_rejection_never_creates_a_call_record` and `test_rejection_leaves_no_orphaned_storage` are now parametrized across all four rejection types (previously only one each); added `test_mismatched_extension_rejected` and `test_persist_failure_cleans_up_and_returns_structured_error`. Test count: 15 → 23, all passing.

## Change Log

- 2026-08-11: Story 1.1 implemented — repo scaffolded per Structural Seed; `Call` SQLite table; `POST /calls` upload/validation endpoint (format, size, duration, decodability checks; structured `error_code`/`message`/`next_step` responses; safe call-id-keyed storage); GitHub Actions CI (ruff + pytest); 15 passing tests plus a live smoke test. Status moved to `review`.
- 2026-08-12: Code review (10 findings, high effort, recall-biased) run against the full implementation; all 10 confirmed and fixed — see File List "Modified" entries above for specifics. Key fixes: DB-insert failures and non-validation exceptions now trigger storage cleanup + a structured `INTERNAL_ERROR` response (previously orphaned storage + unstructured 500); validation now runs before any disk write (was write-then-validate-then-delete); endpoint no longer blocks the event loop; SQLite connections use WAL + busy timeout; content-vs-extension mismatches are now caught; Docker image has correct baked-in storage defaults; hardcoded "200MB" error text now derives from config; two test-coverage gaps closed. Full suite (23 tests) and `ruff check .` re-verified passing under Python 3.13.15; live smoke test re-run against the fixed endpoint.
- 2026-08-12: All ACs satisfied, all tasks complete, code-review findings resolved and re-verified. The general-purpose `code-review` skill's finder/verifier pipeline stood in for dev-story's own "Senior Developer Review (AI)" step (no separate run of that step occurred). Status moved to `done`.
