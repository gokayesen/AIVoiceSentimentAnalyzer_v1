---
baseline_commit: NO_VCS
---

# Story 1.2: Async Processing Lifecycle & Audio Ingest

Status: done

<!-- Note: Validation is optional. Run validate-create-story for quality check before dev-story. -->

## Story

As an Analyst,
I want to see a Call's status move from `queued` to `processing`,
so that I know my upload is being handled and isn't stuck.

## Acceptance Criteria

1. **Given** a Call in `queued`, **when** the ML service's RQ worker picks up the job, **then** status transitions to `processing`, written only by the worker process — never by `web-api` (AD-13). [Source: epics.md#Story 1.2; AD-13]
2. **Given** a Call in `processing`, **when** ingest runs, **then** the system detects channel count (mono/stereo) and persists it as internal metadata (AD-2). [Source: epics.md#Story 1.2; AD-2]
3. **Given** a Call's audio, **when** VAD/chunk-boundary detection runs, **then** the system computes one chunk-boundary set and persists it as ordered `TimelineSegment` rows — this exact set is reused, unmodified, for both model-input chunking and the Emotional Timeline (AD-11). [Source: epics.md#Story 1.2; AD-11]
4. **Given** chunk boundaries exist, **then** they are persisted as a strictly ordered, gapless-within-the-Call sequence (sequential `segment_index`, contiguous `start_time`/`end_time`) so that adjacent-segment lookups are possible — the mechanism later stages (Story 1.3+) need to carry rolling context across boundaries (AD-11). Actually carrying rolling context into a model's inference is exercised starting Story 1.3, once a real filter consumes segments; this story's scope is the ordered data model that makes that possible, not a consuming filter. [Source: epics.md#Story 1.2; AD-11]
5. **Given** ingest completes successfully, **then** the Call remains `processing` — ingest alone does not complete a Call. [Source: epics.md#Story 1.2]
6. **Given** ingest fails, **when** the failure occurs, **then** status transitions to `failed` and the Analyst sees a clear "could not be analyzed" message, never a partial/misleading result (FR-3). [Source: epics.md#Story 1.2; FR-3]
7. **And** `web-api`'s only Call-related DB writes remain upload/ingest metadata — it never writes `Call.status`; all analysis is dispatched via RQ/Redis, never in-process (AD-13, AD-7). [Source: epics.md#Story 1.2; AD-13, AD-7]
8. **And** the ML/audio service is one consolidated service, never directly reachable from the frontend (AD-7); the full stack runs via docker-compose, CPU-only (AD-18). [Source: epics.md#Story 1.2; AD-7, AD-18]
9. **And** the ingest module has independently-runnable unit tests (AD-21). [Source: epics.md#Story 1.2; AD-21]
10. **And** Call deletion (atomic dual-store removal, in-flight RQ job cancellation) is a separate concern, out of this story's scope — see Story 1.10. [Source: epics.md#Story 1.2]

## Tasks / Subtasks

- [x] Task 1: Scaffold `ml-service` as a real Python package (AC: 8, 9)
  - [x] Replace the `ml-service/` placeholder (`README.md` + `.gitkeep` files from Story 1.1) with a real `pyproject.toml` pinned to the Stack table: **Python 3.13.15**, **RQ 2.10.0**, PyTorch 2.13, torchaudio 2.11.0 (already Architecture-pinned for AD-3's Story 1.3 use — reused here for audio loading/channel detection, not a new dependency). Do not add librosa yet; it is unused until Story 1.3.
  - [x] Add `redis` (the Python client library, e.g. `redis>=5,<6` — not itself Stack-pinned since the Stack table pins the Redis *server* version, 8.10, not a client library version; treat the exact client version as a dev-agent implementation decision like Story 1.1's decodability-library choice, and note it in Dev Agent Record) and dev deps (`pytest`, `ruff`, `fakeredis` — test-only, for RQ's `is_async=False` + `FakeStrictRedis()` synchronous-testing pattern, never imported by non-test code).
  - [x] Create `ml-service/pipeline/ingest/` module (replacing its `.gitkeep`) implementing this story's logic; leave `acoustic/`, `transcript/`, `fusion/`, `calibration/` as placeholders — still out of scope (Stories 1.3–1.6).
  - [x] Add a `ml-service/Dockerfile` (`FROM python:3.13.15-slim`, same pin discipline as `web-api/Dockerfile`) whose `CMD` starts the RQ worker process (e.g. `rq worker --url $REDIS_URL ingest`).
- [x] Task 2: Make `redis` and `ml-service` functional docker-compose services (AC: 8)
  - [x] Remove `profiles: ["full"]` from the `redis` and `ml-service` service definitions in `docker-compose.yml` (they were placeholders gated behind that profile specifically until this story per their existing inline comments — `frontend` stays gated, since it remains a placeholder until Story 2.1).
  - [x] Add a `REDIS_URL` environment variable (e.g. `redis://redis:6379/0`) to both `web-api` and `ml-service` services pointing at the compose-network `redis` hostname.
  - [x] Re-validate with `docker compose config` (no live daemon available in this sandbox per Story 1.1's Dev Agent Record — static validation is the available check, same caveat applies here).
- [x] Task 3: `web-api` enqueues an RQ job on successful upload (AC: 1, 7) — **modifies `web-api/app/routers/calls.py` from Story 1.1**
  - [x] Before touching this file, read it in full and confirm current behavior: it validates the upload, then (only after validation passes) writes the file to `storage/{call_id}/original.<ext>` and inserts the `Call` row with `status="queued"`, wrapping that persist step in cleanup-on-failure (Story 1.1's code-review remediation). This story's change must slot in *after* that successful persist, not before or in place of it — do not disturb the validate-before-persist ordering or the cleanup-on-failure wrapping.
  - [x] Add an `enqueue_ingest(call_id: str)` call immediately after the DB insert succeeds (inside the same `try` block, before `return`), using `Queue(connection=...).enqueue("app.pipeline.run_ingest", call_id)` (a string import-path reference, so `web-api` never imports `ml-service` pipeline code in-process — RQ resolves the function by name inside the worker process, preserving AD-7's service boundary). If the enqueue call itself raises, it must be treated the same as any other post-persist failure: cleaned up (storage removed) and returned as the existing `INTERNAL_ERROR` (500), not silently swallowed and left as an orphaned `queued` Call with no worker ever picking it up.
  - [x] Add `rq` and `redis` to `web-api/pyproject.toml` (web-api needs only the client library to enqueue — never RQ's `Worker` class, which belongs to `ml-service` only).
  - [x] Read `REDIS_URL` from environment via `web-api/app/config.py` (same env-var-with-local-fallback pattern already established there for `STORAGE_DIR`/`DB_PATH`), not hardcoded.
- [x] Task 4: `Call` schema — add channel-count metadata (AC: 2) — **modifies `web-api/app/db.py` from Story 1.1**
  - [x] Read the current `_CREATE_CALL_TABLE` DDL and `insert_call()` signature in full before changing them.
  - [x] Add a `channel_count INTEGER` column to `Call` (nullable at insert time — `web-api`'s `insert_call()` at upload time does not yet know channel count; only ingest, running later in `ml-service`, determines and writes it). This is a greenfield schema change (no persisted rows survive between test runs, no migration framework needed per AD-12's session-scoped-storage posture) — extend the existing `CREATE TABLE IF NOT EXISTS` statement directly rather than adding `ALTER TABLE` migration logic.
  - [x] Do not add columns for anything beyond `channel_count` — `TranscriptTurn`/`AnalysisResult`/`ACOUSTIC_EVIDENCE` remain out of scope (Stories 1.3, 1.4, 1.6).
- [x] Task 5: `TimelineSegment` table (AC: 3, 4)
  - [x] Create the `TimelineSegment` entity in SQLite (stdlib `sqlite3`) with, at minimum: an identifier, `call_id` (FK to `Call.id`), `segment_index` (0-based, defines the strict order), `start_time`/`end_time` (float seconds relative to Call start, per Consistency Conventions' timestamp-unit rule — native VAD-boundary unit, not a new one).
  - [x] `ml-service` needs its own SQLite access layer pointed at the same `DB_PATH` (shared volume) — it must not import `web-api/app/db.py` in-process (AD-7 service boundary: the two services share a database file via the filesystem volume, never a shared Python module). Create `ml-service`'s own minimal `db.py` with its own `TimelineSegment`/`Call.status`/`Call.channel_count` write functions; keep it schema-compatible with `web-api/app/db.py`'s `Call` table definition (same table/column names) without importing it.
  - [x] `ml-service`'s `db.py` must include its own idempotent `init_db()` (`CREATE TABLE IF NOT EXISTS` for both `Call` and `TimelineSegment`, mirroring `web-api`'s DDL exactly for `Call`), called once at RQ worker process startup (e.g. top of the worker entrypoint script, before `rq worker` starts consuming). Startup order between the two containers is not guaranteed by docker-compose — the worker must not assume `web-api` has already run its own `init_db()` first.
  - [x] Use `TimelineSegment` as the literal entity/table name (PRD Glossary term reuse, per Consistency Conventions and Story 1.1's established naming discipline) — never a synonym.
- [x] Task 6: Implement the ingest job (AC: 1, 2, 3, 5, 6) — new `ml-service/pipeline/ingest/` code
  - [x] `run_ingest(call_id: str)` — the RQ job function `web-api` enqueues by name (Task 3): on job start, write `Call.status = "processing"` (the *only* place in the system that writes this transition, per AD-13 — `web-api` must never write it, confirmed absent from Task 3/4's `web-api` changes above).
  - [x] Load the Call's audio from `storage/{call_id}/original.<ext>` via `torchaudio.load()` (or `torchaudio.info()` first for channel count, then `.load()` for VAD — avoid decoding twice if `torchaudio.load()` alone suffices for both; a dev-agent implementation-time call, not an Architecture mandate).
  - [x] Detect channel count from the loaded tensor's channel dimension; persist to `Call.channel_count` (AC 2). Per AD-2, this story only detects and persists channel count — it does **not** implement the downstream stereo-channel-index-based speaker assignment or mono diarization dispatch; those are Story 3.1/3.2's scope (Epic 3). Do not build speaker-attribution logic here.
  - [x] Run VAD to get speech-boundary timestamps. **Recommended library (dev-agent decision, not an Architecture mandate — same "no story silently adds a new architecture-level dependency without documenting it" discipline Story 1.1 established):** Silero VAD (MIT-licensed, ~1-2MB, CPU-fast), explicitly recommended by Technical Research §3.2/§11 for exactly this purpose and not covered by any Stack-pinned alternative. Add `silero-vad` to `ml-service/pyproject.toml` and document the choice in this story's Dev Agent Record, mirroring how Story 1.1 documented `soundfile`+`mutagen`.
  - [x] Convert VAD speech timestamps into the Call's ordered `TimelineSegment` set (AC 3, 4) and persist via Task 5's `TimelineSegment` writer — sequential `segment_index` starting at 0, `start_time`/`end_time` in float seconds.
  - [x] On success: leave `Call.status = "processing"` (AC 5) — do not write `"complete"`; no downstream filter exists yet to complete the Call (Stories 1.3–1.6).
  - [x] On failure (audio load error, VAD failure, any unexpected exception): write `Call.status = "failed"` with a clear, Analyst-facing message (AC 6, FR-3) — use RQ's `on_failure` callback (registered on `queue.enqueue(..., on_failure=...)`) or an in-job `try/except` that writes `"failed"` before re-raising, either is acceptable; pick one and use it consistently. Never leave a Call silently stuck in `processing` after a real failure.
- [x] Task 7: Structured JSON logging in `ml-service` (AC: 8; AD-21 baseline)
  - [x] `ml-service` is a brand-new service as of this story (no prior code to preserve) — establish structured JSON logging for the ingest job's key events (job start, channel count detected, segment count persisted, failure with reason) at genesis, per AD-21's "both `web-api` and `ml-service` emit structured JSON logs" baseline. Python stdlib `logging` with a JSON formatter is sufficient — no new logging framework dependency needed for this.
  - [x] `web-api` does not currently emit structured logs either (a Story 1.1 gap, not introduced by this story) — out of scope to retrofit here; do not touch `web-api`'s logging in this story.
- [x] Task 8: CI for `ml-service` (AC: 9)
  - [x] Add an `ml-service` job to `.github/workflows/ci.yml` alongside the existing `web-api` job (lint via `ruff`, test via `pytest`), same Python 3.13.15 pin. Per AD-21, this must run independently — the `is_async=False` + `fakeredis` pattern (Task 9) means no live Redis service container is needed in CI.
- [x] Task 9: Tests (AC: 1, 2, 3, 4, 5, 6, 7, 9)
  - [x] `ml-service` unit tests for `run_ingest()`: channel detection (mono fixture, stereo fixture — reuse/extend Story 1.1's synthetic-fixture-generation approach via `imageio-ffmpeg`, now also generating a 2-channel WAV), VAD/`TimelineSegment` persistence (ordered, sequential `segment_index`), success path leaves `status="processing"`, failure path (e.g. corrupt/unreadable audio) writes `status="failed"` with a message and never leaves the Call stuck. Run these against a real SQLite temp DB (same fixture-isolation pattern as Story 1.1's `conftest.py`), not mocks, so the actual DDL/writes are exercised.
  - [x] `web-api` test additions: confirm a successful upload now enqueues exactly one job (assert via RQ's job registry on a `Queue(is_async=False, connection=FakeStrictRedis())` test double — no real Redis needed, consistent with Story 1.1's "independently runnable" testing standard) with the correct `call_id` argument; confirm `web-api` still never writes anything to `Call.status` beyond the initial `"queued"` insert (extend Story 1.1's DB-assertion pattern).
  - [x] Confirm both test suites run via their respective CI jobs (Task 8).

### Review Findings

- [x] [Review][Patch] TimelineSegment kayıtları AC4'ün gerektirdiği gibi gapless/contiguous değil — Silero VAD yalnızca konuşma içeren aralıkları döndürüyor (`vad.py:22-32`), `run.py:60-65` bunları hiçbir boşluk-doldurma adımı olmadan olduğu gibi persist ediyor. **Karar (kullanıcı, 2026-08-12):** her segmentin `end_time`'ı bir sonraki segmentin `start_time`'ına (son segment için Call'ın toplam süresine) kadar genişletilerek dizi gerçekten gapless/contiguous hale getirilecek — post-processing adımı `run.py`'de, VAD çıktısı persist edilmeden önce. **Uygulandı:** `_fill_gaps()` helper'ı eklendi (`run.py`), ilk segment 0.0'dan başlıyor, her segment bir sonrakinin başlangıcına kadar uzatılıyor, son segment Call'ın toplam süresine kadar uzatılıyor; `test_ingest_persists_ordered_timeline_segments` contiguity assertion'larıyla güncellendi.
- [x] [Review][Defer] `vad.py`'deki modül seviyesi `_model` önbelleği RQ'nun varsayılan fork-eden `Worker`'ı altında hiçbir fayda sağlamıyor — her job yeni bir forklanmış alt süreçte çalıştığından model her seferinde sıfırdan yükleniyor; CPU-only dağıtım hedefinde (AD-18) gerçek ama ölçülmemiş bir gecikme maliyeti. — deferred: performans/verimlilik konusu, doğruluğu etkilemiyor; düzeltmesi (SimpleWorker'a geçiş) crash-izolasyonunu kaybettiren bir mimari trade-off kararı gerektiriyor — performans/ölçekleme ihtiyacı doğduğunda ele alınacak.
- [x] [Review][Patch] `run_ingest`'te `insert_timeline_segments`'ın `executemany`'si yarıda başarısız olursa, commit edilmemiş satırlar except bloğundaki `set_call_status(..., "failed")`'in commit'iyle birlikte sessizce kalıcı hale geliyor — rollback yok [ml-service/app/pipeline/ingest/run.py:73-79; ml-service/app/db.py:82-97]. **Uygulandı:** except bloğunun başına `conn.rollback()` eklendi.
- [x] [Review][Patch] `.github/workflows/ci.yml`'deki `ml-service` job'u, `torchaudio.load()`'ın (TorchCodec üzerinden) çalışma zamanında ihtiyaç duyduğu sistem ffmpeg'ini kurmuyor — Dockerfile'daki `apt-get install ffmpeg` adımı CI'ya taşınmamış [.github/workflows/ci.yml:30-51]. **Uygulandı:** `ml-service` job'una "Install ffmpeg" adımı eklendi.
- [x] [Review][Patch] `run_ingest`'in except bloğunda `db.set_call_status(..., status="failed")` çağrısının kendisi patlarsa orijinal hata maskeleniyor ve Call sonsuza dek "processing" durumunda kalıyor [ml-service/app/pipeline/ingest/run.py:73-79]. **Uygulandı:** iç içe try/except eklendi; iç `except` `logger.exception(...)` ile logluyor, dış `except` orijinal hatayı loglayıp yeniden fırlatmaya devam ediyor.
- [x] [Review][Patch] `torch`/`torchaudio`, varsayılan PyPI index'i üzerinden kuruluyor — CPU-only dağıtım zarfına (AD-18) rağmen büyük olasılıkla gereksiz CUDA runtime bağımlılıklarını imaja çekiyor [ml-service/Dockerfile:15]. **Uygulandı:** `pip install --extra-index-url https://download.pytorch.org/whl/cpu` eklendi; imaj yeniden derlenip `torch-2.13.0+cpu`/`torchaudio-2.11.0+cpu`/`torchcodec-0.15.0+cpu` kurulumu doğrulandı.
- [x] [Review][Patch] `calls.py`'nin except bloğundaki telafi edici `db.delete_call()` çağrısının kendi try/except'i yok — patlarsa yapısal olmayan bir 500 döner ve sesi zaten silinmiş bir Call satırı DB'de öksüz kalır [web-api/app/routers/calls.py:115-121]. **Uygulandı:** `db.delete_call()` kendi try/except'ine alındı, `logger.exception(...)` ile loglanıyor, yapılandırılmış `INTERNAL_ERROR` yanıtı hâlâ dönüyor.
- [x] [Review][Patch] `shutil.rmtree(call_dir, ignore_errors=True)` temizlik başarısız olursa sessizce yutuluyor, hiçbir log satırı yok [web-api/app/routers/calls.py:110]. **Uygulandı:** rmtree sonrası `call_dir.exists()` kontrolü ile `logger.warning(...)` eklendi.
- [x] [Review][Defer] `detect_channel_count`, 2'den fazla kanal için üst sınır doğrulaması yapmıyor [ml-service/app/pipeline/ingest/channel.py:10-12] — deferred, pre-existing scope boundary: Epic 3 (hoparlör atama) konusu, şu an channel_count>2'yi tüketen hiçbir kod yok
- [x] [Review][Defer] `docker-compose.yml`'de `redis` için `depends_on`, healthcheck/`condition: service_healthy` içermiyor — soğuk başlangıçta yarış durumu mümkün [docker-compose.yml:13-14,38-39] — deferred, pre-existing altyapı deseni (Story 1.1'den), pratik etkisi düşük (yükleme isteği gelene kadar redis zaten hazır oluyor)

## Dev Notes

### Previous story intelligence (Story 1.1)

- **Python pin discipline:** local sandbox previously needed `brew install python@3.13` to get the exact 3.13.15 pin; that interpreter now exists at `/usr/local/Cellar/python@3.13/3.13.15/bin/python3.13` — reuse it directly for `ml-service/.venv` rather than repeating the resolution process.
- **"Dev-agent library decision, not an Architecture mandate" pattern:** Story 1.1 established the convention of choosing a reasonable library when the Architecture leaves a gap (there: `soundfile`+`mutagen` for decodability), documenting the choice and rationale transparently in Dev Agent Record rather than treating it as silently expanding the Stack table. This story has two such gaps (VAD library, `redis` client library version) — follow the same documentation discipline.
- **Validate-before-persist / cleanup-on-failure pattern in `calls.py`:** the code-review remediation pass rewrote the upload endpoint so validation runs entirely before any write to `storage/` or the DB, and only the final persist block (storage write + DB insert) is wrapped in try/except-cleanup. This story's enqueue call must be added *inside* that same wrapped block (Task 3) so an enqueue failure is cleaned up identically to a DB-insert failure — don't reintroduce a partially-wrapped state.
- **WAL mode + busy timeout on `get_connection()`:** `web-api/app/db.py`'s connection helper already opens with `PRAGMA journal_mode=WAL` and a 30s busy timeout for concurrent-write safety. `ml-service`'s own `db.py` (Task 5) should use the same `PRAGMA journal_mode=WAL` + timeout pattern when opening its connection to the same DB file, since the worker process and `web-api` process now write concurrently to the same SQLite file for the first time.
- **Structured error/status contract:** `web-api`'s existing `{error_code, message, next_step}` shape is for *upload validation* rejections only (Story 1.1's AC 2–5) and is unrelated to `Call.status = "failed"` (this story's AC 6, a state written by the worker, not an HTTP error response) — do not conflate the two; no new HTTP error contract is needed for ingest failures in this story (the Analyst-facing "could not be analyzed" message is surfaced via `Call.status`/a status field, which the polling/results API — not yet built, later stories — will expose).

### Architecture compliance (non-negotiable)

- **Service boundary (AD-7):** `ml-service` is one consolidated Python service; `web-api` must never import pipeline code in-process, and `ml-service` must never be reachable from the frontend. The two services cross only via RQ/Redis (job dispatch) and the shared SQLite file + filesystem volume (never a shared Python import).
- **Status-write ownership (AD-13):** Only the RQ worker (`ml-service`) writes `Call.status` transitions, at job start (`processing`) and on completion/failure. `web-api`'s only Call-related write remains the initial `queued` insert at upload time (Story 1.1) — verify this is still true after Task 3's changes; do not add any status-writing code to `web-api`.
- **One VAD boundary set (AD-11):** the boundary set computed here is later reused unmodified for both model-input chunking (Stories 1.3–1.5) and the Emotional Timeline (Story 1.7) — never recomputed independently by a later stage.
- **Naming (Consistency Conventions):** `TimelineSegment` (not `Segment`/`Chunk`/`EmotionalTimelineSegment`), reusing the PRD Glossary term directly, matching Story 1.1's established discipline.

### Latest tech information (verified via Context7, 2026-08-12)

- **RQ 2.10.0 enqueue pattern** (`/rq/rq`): `from rq import Queue; from redis import Redis; q = Queue(connection=Redis.from_url(REDIS_URL)); job = q.enqueue("app.pipeline.run_ingest", call_id)` — passing the function as an import-path string (rather than an imported reference) is what lets `web-api` enqueue without importing `ml-service` code (AD-7).
- **RQ failure handling**: register via `q.enqueue(..., on_failure=report_failure)` where `report_failure(job, connection, type, value, traceback)` — or an in-job `try/except`; Task 6 leaves the choice open but requires one consistent approach.
- **RQ worker startup**: `rq worker --url $REDIS_URL ingest` (CLI) is the simplest `ml-service` Dockerfile `CMD`; no custom worker bootstrap script needed for this story's scope.
- **RQ synchronous testing** (`/rq/rq`, `docs/testing.md`): `Queue(is_async=False, connection=FakeStrictRedis())` executes jobs in-thread with no live Redis and no separate worker process — this is the AD-21 "independently runnable without the full docker-compose stack" pattern for both `web-api`'s enqueue-assertion tests and `ml-service`'s job-logic tests. `fakeredis` is a test-only dependency, never imported by application code.
- **Silero VAD** (`/snakers4/silero-vad`): `from silero_vad import load_silero_vad, get_speech_timestamps; model = load_silero_vad(); speech_timestamps = get_speech_timestamps(wav_tensor, model, sampling_rate=16000, return_seconds=True)` — natively supports 8kHz/16kHz; other rates are cast to 16kHz internally by the JIT model. `wav` must be a mono float tensor — if channel detection (Task 6) finds stereo input, decide per-channel or downmixed VAD input consistently and document the choice (AD-2 governs the separate concern of stereo *speaker* assignment, not VAD input shape — keep these two decisions distinct in the implementation).

### What NOT to build in this story

- No acoustic/transcript/fusion pipeline code — Stories 1.3–1.6 (the `pipeline/acoustic/`, `transcript/`, `fusion/`, `calibration/` directories stay placeholders).
- No stereo-channel-index speaker assignment or mono diarization dispatch — Stories 3.1/3.2 (Epic 3). This story only detects and persists channel count (AC 2).
- No `Call.status = "complete"` — no stage in the system can complete a Call until fusion (Story 1.6) exists.
- No delete endpoint or in-flight-job cancellation — Story 1.10.
- No frontend/UI — Epic 2. Nothing in this story is Analyst-visible yet; the user-story framing describes the capability being built (status will actually reach the Analyst once Epic 2's polling UI exists).
- No retry logic beyond what RQ provides by default — AD-13 mentions retry as bound by FR-3 but does not mandate a specific retry policy for this story; do not invent one (e.g. a custom exponential-backoff wrapper) beyond RQ's built-in job lifecycle.

### Testing Standards

- `pytest` for both `web-api` (existing) and the new `ml-service` suite, per the Stack's Python pairing.
- Per AD-21: each pipeline stage has independently-runnable unit tests — `pytest ml-service/` must succeed with no live Redis and no live docker-compose stack, using the `is_async=False` + `fakeredis` pattern.
- Extend Story 1.1's real-fixture-generation approach (`imageio-ffmpeg`-synthesized audio, never imported by app code) rather than hand-crafting fixture bytes, for consistency with the established pattern.

### Project Structure Notes

- This is the first story to write real code into `ml-service/` — no existing structure to conform to there. Follow the Structural Seed's `ml-service/pipeline/ingest/` path exactly.
- This story modifies two `web-api` files from Story 1.1 (`app/routers/calls.py`, `app/db.py`) — both must be read in full before editing (see Task 3/Task 4 notes above) so the validate-before-persist ordering and cleanup-on-failure wrapping established in Story 1.1's code-review remediation are preserved, not regressed.
- `docker-compose.yml`'s `redis`/`ml-service` services already exist as placeholders (Story 1.1) with inline comments marking them "becomes functional in Story 1.2" — this story fulfills that comment; update/remove the now-stale placeholder comments when editing.

### References

- [Source: _bmad-output/planning-artifacts/epics.md#Story 1.2: Async Processing Lifecycle & Audio Ingest]
- [Source: _bmad-output/planning-artifacts/epics.md#Requirements Inventory — FR-3]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#AD-2 Audio input channel detection & speaker attribution]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#AD-7 Model serving boundary]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#AD-11 Chunking/timeline unification]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#AD-13 Async orchestration]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#AD-18 Deployment envelope]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#AD-21 CI, testing, and logging baseline]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#Consistency Conventions]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#Stack]
- [Source: _bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md#Structural Seed]
- [Source: _bmad-output/planning-artifacts/research/technical-voice-sentiment-analyzer-research-2026-08-10.md#§3.2, §11 — Silero VAD, chunking/rolling-context recommendation]
- [Source: _bmad-output/implementation-artifacts/1-1-call-upload-and-validation.md — previous story intelligence]
- [Source: RQ official docs, retrieved via Context7 (2026-08-12) — enqueue, failure handling, worker startup, synchronous testing]
- [Source: Silero VAD official docs, retrieved via Context7 (2026-08-12) — pip usage, get_speech_timestamps]

## Dev Agent Record

### Agent Model Used

Claude Sonnet 5 (claude-sonnet-5)

### Debug Log References

- **Platform blocker discovered and resolved:** this sandbox is an Intel Mac (x86_64). PyTorch dropped macOS x86_64 wheel publishing after 2.2.2, and no version — at any Python level — ships a `cp313`/x86_64/macOS wheel; the Architecture-pinned `torch==2.13.0`/`torchaudio==2.11.0` (both real, current, verified-on-PyPI pins matching the Stack table) simply cannot run natively in this local environment. This is a sandbox-hardware limitation, not a pin problem — the real deployment target (`python:3.13.15-slim`, Linux x86_64, per the Dockerfile/AD-18) has full wheel support. Resolved by using the Docker daemon (confirmed available this session, started via `open -a Docker`) to build and run `ml-service` in a real Linux container for all development, linting, and testing — never guessed or skipped.
- **Real bug found via empirical testing, not caught by docs alone:** `torchaudio.load()` in the pinned 2.11.0 is a thin wrapper delegating to TorchCodec's `AudioDecoder` (confirmed by running it inside the container and reading the actual traceback — Context7's docs hinted at this but weren't decisive since they reflect `pytorch/audio`'s `main` branch, not necessarily the exact pinned release). TorchCodec is a **separate required runtime dependency**, and it in turn requires FFmpeg's shared libraries (versions 4–8) on the system — neither is in the Architecture Stack table. Fixed by adding `torchcodec>=0.15,<1.0` to `ml-service/pyproject.toml` and `apt-get install ffmpeg` to `ml-service/Dockerfile`, then re-verified empirically (all tests re-run and passed after the fix).
- `docker build -f ml-service/Dockerfile.dev ...` (a local-only, non-committed dev image with `[dev]` extras) → `docker run --rm ml-service-dev:latest pytest tests/ -v`: **5 passed**. `ruff check .`: all checks passed. (`Dockerfile.dev` was deleted after use — not part of the story's deliverables, `ml-service/Dockerfile` is the real artifact.)
- `PYTHONPATH=. .venv/bin/pytest -v` (web-api, native — no torch dependency, ran natively without the container): **26 passed** (up from 23 in Story 1.1: +3 new: enqueue-on-success, no-enqueue-on-rejection, enqueue-failure-cleanup). `.venv/bin/ruff check .`: all checks passed.
- **Full live end-to-end smoke test** (`docker compose up -d` — real `web-api` + `redis:8.10` + `ml-service` containers, not `TestClient`/unit tests): uploaded a real speech recording via `curl -X POST http://localhost:8000/calls`, got `201` + `call_id`, then polled the shared SQLite DB directly (`docker compose exec ml-service python -c ...`). Confirmed the full pipeline: `Call.status` transitioned `queued` → `processing` (written only by the worker, never by `web-api`, per the structured JSON worker logs), `channel_count` correctly detected as `1` (mono), and **19 ordered `TimelineSegment` rows** persisted with strictly increasing `start_time`/sequential `segment_index`. Status correctly remained `processing` after success (AC5 — no premature completion). `docker compose down` afterward; scratch smoke-test audio and the `ml-service-dev` image were removed, no artifacts left behind.
- `docker compose config` (post Task 2 edit): validated — `redis`/`ml-service` now render as default (unprofiled) services alongside `web-api`; `frontend` correctly remains behind `profiles: ["full"]`.

### Completion Notes List

- **All 9 ACs implemented and verified twice over**: once via unit tests (26 web-api + 5 ml-service, all passing) and independently via a live `docker compose up` smoke test exercising the real upload → enqueue → worker → DB flow end-to-end — not test-suite-only verification, consistent with Story 1.1's discipline.
- **Two dev-agent library decisions**, both documented per Story 1.1's established pattern:
  - **Silero VAD** (`silero-vad>=6.2,<7`) for VAD/chunk-boundary detection (AC3/AC4) — MIT-licensed, matches Technical Research §3.2/§11's explicit recommendation, not in the Stack table. Verified empirically against Silero's own official example speech recording (a synthesized sine tone was tried first and correctly produced zero VAD segments — not a bug, just proof a pure tone isn't speech-like; switched the segment-persistence test fixture to the real recording instead).
  - **`torchcodec>=0.15,<1.0`** — not a discretionary choice but a *required* transitive runtime dependency of the pinned `torchaudio==2.11.0`, discovered empirically (see Debug Log). `redis` (Python client library, `>=5.0,<6`) was also an undocumented-in-Stack version decision, same rationale as Story 1.1's `soundfile`/`mutagen`.
  - **Package layout deviation:** the Structural Seed sketches `ml-service/pipeline/{ingest,...}` at the top level; implemented instead as `ml-service/app/pipeline/{ingest,...}` (mirroring `web-api/app/`'s existing convention) because a hyphenated top-level directory name (`ml-service`) cannot itself be a valid Python package for the shared `db.py`/`config.py`/`worker.py` modules to live alongside `pipeline/`. Story 1.1's placeholder `.gitkeep` files for `acoustic/transcript/fusion/calibration` were moved under `app/pipeline/` accordingly — no code depended on the old empty paths.
  - **RQ failure-handling choice:** used an in-job `try/except` (writes `Call.status="failed"` then re-raises) rather than RQ's `on_failure=` callback — both were left open by the story; the in-job approach keeps all status-writing logic in one place (`run_ingest`) rather than split across two functions.
- **A real, non-obvious bug was caught and fixed during testing, not just implementation**: the first version of `calls.py`'s enqueue-failure handling only cleaned up `storage/`, not the already-committed `Call` DB row (`insert_call()` commits immediately, so a later enqueue failure in the same request couldn't be rolled back by SQLite itself). A dedicated test (`test_enqueue_failure_cleans_up_and_returns_structured_error`) caught this — `after_count == before_count` failed with `5 == 4`. Fixed by adding `db.delete_call()` as an explicit compensating action in `calls.py`'s exception handler, tracked via a `call_inserted` flag. This is exactly the class of bug Task 3's Dev Notes warned about ("not silently left as an orphaned `queued` Call") — it was still worth writing the test rather than trusting the description.
- **Web-api test double correction:** the story's Dev Notes suggested asserting enqueue behavior via `Queue(is_async=False, connection=FakeStrictRedis())`. Implemented with `is_async` left at its default (`True`/async) instead — `is_async=False` executes jobs synchronously in-thread, which would try to import `app.pipeline.ingest.run` (an `ml-service`-only module) from inside `web-api`'s test process and fail. `is_async=False` is correctly used in `ml-service`'s own tests, where that module genuinely exists. Caught before running, not after a failure.
- **Docker image not built via `docker build` for the production `ml-service/Dockerfile` alone** — it *was* built as part of `docker compose build` (see Debug Log) and run as part of the full-stack smoke test, so it is verified. Only the separate ad hoc `ml-service-dev:latest` image (used for fast iterative unit-test runs before committing to a full compose cycle) was local-only and has been deleted.
- No new architecture-level dependency was silently introduced: `torch`/`torchaudio` were already Stack-pinned (AD-3, reused here — not new); `rq`/`redis` (AD-13, Stack-pinned server version); `torchcodec`, `silero-vad`, and the exact `redis` client version are all documented above with rationale.

### File List

**Created:**
- `ml-service/pyproject.toml`
- `ml-service/Dockerfile`
- `ml-service/app/__init__.py`
- `ml-service/app/config.py`
- `ml-service/app/db.py`
- `ml-service/app/logging_config.py`
- `ml-service/app/worker.py`
- `ml-service/app/pipeline/__init__.py`
- `ml-service/app/pipeline/ingest/__init__.py`
- `ml-service/app/pipeline/ingest/channel.py`
- `ml-service/app/pipeline/ingest/vad.py`
- `ml-service/app/pipeline/ingest/run.py`
- `ml-service/tests/__init__.py`
- `ml-service/tests/conftest.py`
- `ml-service/tests/test_ingest.py`
- `web-api/app/queue.py`

**Moved:**
- `ml-service/pipeline/{acoustic,transcript,fusion,calibration}/.gitkeep` → `ml-service/app/pipeline/{acoustic,transcript,fusion,calibration}/.gitkeep` (package-layout deviation, see Completion Notes)

**Modified:**
- `web-api/app/routers/calls.py` — enqueues an RQ ingest job after successful persist (AD-13); added `call_inserted`-tracked compensating `db.delete_call()` so an enqueue failure can no longer leave an orphaned `queued` Call (see Completion Notes' bug-caught-by-testing note).
- `web-api/app/db.py` — added nullable `channel_count INTEGER` column to `Call`; added `delete_call()`.
- `web-api/app/config.py` — added `REDIS_URL`/`INGEST_QUEUE_NAME`.
- `web-api/pyproject.toml` — added `rq==2.10.0`, `redis>=5.0,<6`, `fakeredis>=2.37,<3.0` (dev).
- `web-api/Dockerfile` — added baked-in `ENV REDIS_URL=redis://redis:6379/0` default (same rationale as Story 1.1's `STORAGE_DIR`/`DB_PATH` bake-in).
- `web-api/tests/conftest.py` — added `fake_queue` fixture (real `Queue` + `fakeredis`, monkeypatches `app.queue.get_queue`); `client` fixture now depends on it.
- `web-api/tests/test_upload.py` — added `test_valid_upload_enqueues_ingest_job`, `test_rejection_never_enqueues_a_job`, `test_enqueue_failure_cleans_up_and_returns_structured_error`.
- `docker-compose.yml` — `redis`/`ml-service` un-gated from `profiles: ["full"]` (now default services); added `REDIS_URL` to `web-api`/`ml-service`; added `depends_on: redis`.
- `.github/workflows/ci.yml` — added the `ml-service` job (lint + test, same Python 3.13.15 pin, no Redis service container needed).

## Change Log

- 2026-08-12: Story 1.2 implemented — `ml-service` scaffolded as a real Python package with an RQ worker (AD-13); `web-api` enqueues an ingest job after successful upload; ingest job detects channel count (AD-2), runs Silero VAD to compute ordered `TimelineSegment` boundaries (AD-11), and transitions `Call.status` `queued → processing` (success) or `→ failed` (error) — the only writer of those transitions. `redis`/`ml-service` made functional in docker-compose (un-gated from `profiles: ["full"]`). 26 web-api tests + 5 ml-service tests passing (all in a real Linux container, since this sandbox is an Intel Mac with no compatible PyTorch wheel); `ruff check` clean on both services; full `docker compose up` live smoke test confirmed the real upload → enqueue → worker → DB flow end-to-end. A real transitive-dependency gap (`torchcodec` + system FFmpeg, required by pinned `torchaudio==2.11.0`) and a real orphaned-Call-row bug (enqueue failure after DB commit) were both found empirically during testing and fixed. Status moved to `review`.
- 2026-08-12: Code review (bmad-code-review, 8-angle adversarial + acceptance-audit review of all 25 story files, no git repo so reviewed as full-content diff) found 10 real issues: 2 decision-needed, 6 patch, 2 defer (after triage; dropped 12 as noise/dismissed/pre-existing). User resolved both decision-needed items: (1) AC4's "gapless/contiguous" TimelineSegment requirement — chose to gap-fill segments (extend each `end_time` to the next segment's `start_time`, first segment starts at 0.0, last extends to Call duration) rather than reinterpret the AC or defer it; (2) the VAD model's per-job reload under RQ's forking `Worker` — deferred as a performance trade-off (fixing it means switching to `SimpleWorker`, losing crash isolation). All 7 resulting patches applied: AC4 gap-fill (`run.py` + `_fill_gaps()` + updated contiguity test), `conn.rollback()` before writing `failed` status so a mid-`executemany` failure can't leave partial `TimelineSegment` rows committed, a nested try/except around the `failed`-status write itself (via `logger.exception`, doesn't mask the original error), CI's `ml-service` job now installs system ffmpeg (was silently relying on the `ubuntu-latest` image happening to ship it), `ml-service/Dockerfile`'s pip install now targets PyTorch's CPU-only wheel index (verified: `torch-2.13.0+cpu`/`torchaudio-2.11.0+cpu`/`torchcodec-0.15.0+cpu`, no more incidental CUDA runtime deps, AD-18), `web-api`'s compensating `db.delete_call()` now has its own try/except (logged, still returns the structured `INTERNAL_ERROR`), and `shutil.rmtree`'s silent-failure path now logs a warning if cleanup leaves residue. Re-verified after patches: 26 web-api tests passing, 5 ml-service tests passing (including new contiguity assertions), `ruff check` clean on both services, `docker compose config` valid. 2 items deferred to `_bmad-output/implementation-artifacts/deferred-work.md` (channel-count upper-bound validation — Epic 3 scope; VAD model cache trade-off — see above). Status moved to `done`.
