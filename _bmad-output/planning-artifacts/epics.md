---
stepsCompleted: [1, 2, 3, 4]
inputDocuments:
  - '{planning_artifacts}/prds/prd-AIVoiceSentimentAnalyzer_v1-2026-08-10/prd.md'
  - '{planning_artifacts}/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md'
  - '{planning_artifacts}/ux-designs/ux-AIVoiceSentimentAnalyzer_v1-2026-08-10/DESIGN.md'
  - '{planning_artifacts}/ux-designs/ux-AIVoiceSentimentAnalyzer_v1-2026-08-10/EXPERIENCE.md'
---

# AIVoiceSentimentAnalyzer_v1 - Epic Breakdown

## Overview

This document provides the complete epic and story breakdown for AIVoiceSentimentAnalyzer_v1, decomposing the requirements from the PRD, UX Design (DESIGN.md + EXPERIENCE.md), and Architecture Spine (ARCHITECTURE-SPINE.md, 21 ADs) into implementable stories.

## Requirements Inventory

### Functional Requirements

FR-1: Analyst can upload a single audio file recording of a two-party (agent + customer) conversation. System accepts a defined, documented, enforced format/size/duration set; rejects out-of-bounds or non-decodable files with a specific error rather than silent/generic failure.
FR-2: System communicates upload/validation errors clearly — names the specific failed rule and tells the Analyst what to do next.
FR-3: System communicates processing status (queued/processing/complete/failed) while a Call is being analyzed; never leaves the Analyst looking at an unchanging screen; a mid-processing failure is reported, not shown as a partial/misleading result.
FR-4: System performs Acoustic Analysis on every accepted Call — mandatory, independent of and prior to Transcript Analysis; never skipped/bypassed/replaced by transcript-only analysis, including in a degraded state; produces output independently of whether Transcript Analysis succeeds.
FR-5: System derives an Emotion signal from Acoustic Analysis, kept and presented as a distinct output from any text-derived Sentiment.
FR-6: System generates a transcript of the Call's audio via speech-to-text (English-only for MVP), for Transcript Analysis and direct display.
FR-7: System analyzes the transcript for Sentiment, Emotion indicators, and relevant keywords/context; kept distinct from Acoustic Analysis output through Fusion — a contributing signal, not a pre-emptive final answer.
FR-8: System combines Acoustic Analysis and Transcript Analysis into a single Analysis Result per Call (overall Sentiment, dominant Emotion, Confidence).
FR-9: System generates a chronological, multi-point Emotional Timeline for each Call, granular enough to distinguish two distinct emotional shifts within the same Call.
FR-10: Every Sentiment/Emotion judgment (overall and per-timeline-segment) carries a Confidence indicator; segments below a defined threshold are marked Low-Confidence Segments rather than presented as equivalent to high-confidence findings.
FR-11: System surfaces meaningful disagreement between Acoustic Analysis and Transcript Analysis per segment — both signals shown distinctly, never silently resolved into one number; a disagreeing segment is identifiable as such.
FR-12: Analyst can view the full Analysis Result for a completed Call: overall Sentiment, dominant Emotion, Confidence, Emotional Timeline, full transcript, and acoustic insights.
FR-13: Analyst can select a point/segment on the Emotional Timeline and see the corresponding transcript excerpt and acoustic evidence displayed together.
FR-14: Dashboard visually distinguishes Low-Confidence Segments from high-confidence ones without additional interpretation.
FR-15: System never presents an Analysis Result using language that asserts certainty — all language is probabilistic and evidence-linked; no UI copy/label/generated text asserts a settled emotional/sentiment fact.
FR-16: System attributes Analysis Result segments to a speaker (agent/customer) when the input audio allows it (best-effort/conditional, not guaranteed); Calls without reliable separation still produce a full Analysis Result, just without per-speaker breakdown.

### NonFunctional Requirements

NFR-1 (Explainability): Every Emotion/Sentiment output must be traceable, within the dashboard, to at least one supporting signal (acoustic evidence, transcript excerpt, or both). No output may be unexplainable or evidence-free.
NFR-2 (Confidence honesty): Confidence values are not claimed to be statistically calibrated or independently validated against ground truth for MVP; product copy/documentation must not imply an unestablished calibration guarantee.
NFR-3 (Terminology discipline): "Emotion" and "Sentiment" are used per the Glossary consistently across all UI copy, API/data contracts, and generated output — never interchangeable.
NFR-4 (Human-in-the-loop framing): No product surface may frame system output as a final decision; language consistently positions the Analyst as final reviewer.
NFR-5 (Evaluation transparency): Any accuracy/performance/reliability claim the product surfaces must state what it was measured against (dataset, method, conditions); no unqualified accuracy claims.

### Additional Requirements

- **No external starter template** — Architecture defines its own source tree directly (`web-api/`, `ml-service/`, `frontend/`, `storage/`, `docker-compose.yml`); Epic 1 Story 1 scaffolds this structure natively, no scaffolding tool assumed (Structural Seed, Source tree sketch).
- **Pipes-and-filters pipeline with separately testable stages** — `ingest` (channel detection + VAD/chunk-boundary) → `acoustic` (SER + handcrafted-feature explainability) → `transcript` (STT + diarization + text-sentiment) → `fusion` (rule-based + disagreement flag + Secondary Signal) → `calibration` (temperature scaling); stages don't reach around each other (Design Paradigm; AD-1, AD-3, AD-5, AD-6, AD-8, AD-9, AD-11, AD-19).
- **Voice-first failure handling is fully specified, not just "acoustic is mandatory"** — if the acoustic-analysis filter fails, is skipped, or its own calibrated confidence falls below a defined sanity floor, the Call's processing status must go to `failed`; there is no acoustic-skip / transcript-only fallback path under any condition. Conversely, if only the transcript-analysis filter fails, the Call does NOT fail — fusion proceeds on the acoustic-emotion signal alone, and the resulting Analysis Result must carry an explicit single-modality flag, never presented as an ordinary two-signal fused result (AD-1, AD-8 rule 4).
- **Text-sentiment classifier is constrained, not open-ended** — Transcript Sentiment/Emotion (FR-7) is produced by a small, fine-tuned or pretrained transformer classifier (RoBERTa/DistilBERT-family); a general-purpose LLM or cloud LLM API must never be used for this stage, consistent with the local/CPU-only posture (AD-14/AD-18) and specifically to prevent an "audio → STT → LLM → sentiment" pattern where acoustic features become decorative (AD-19).
- **SER stage has a fixed model family and a mandatory explainability layer** — the primary classifier is an embedding-based model (Wav2Vec2/HuBERT/WavLM-family fine-tune). Independently of that classifier, a handcrafted acoustic-feature set (pitch/F0, energy, speaking rate, pauses/voice-activity) must also be computed and persisted for every Call — mandatory, never optional or debug-only. Handcrafted-feature extraction must use license-safe libraries only (librosa/torchaudio) — openSMILE/eGeMAPS (research-only license) and Praat/parselmouth (GPLv3 copyleft) must never be used (AD-3).
- **Emotion taxonomy is fixed, not left to the model layer** — Emotion is a small, coarse category set (CREMA-D-style, 4-6 classes); every category maps through one fixed lookup table to exactly one of the four Sentiment polarity colors (negative/mixed/positive/neutral); adding a category requires extending this lookup table in the same change. Emotion must never be collapsed onto the polarity scale at generation time (AD-4).
- **Fusion mechanism is rule-based by requirement, not an implementation detail** — the per-segment fusion step (FR-8) is confidence-weighted averaging of the two calibrated modality signals, computed with a fixed rule, not a trained/learned fusion model; a future trained black-box fusion replacement is explicitly out of scope for this architecture (AD-8).
- **Sentiment and Emotion are separate fields at the data-model level, not only in UI copy** — distinct from NFR-3 (which governs UI/API *terminology*): Sentiment and Emotion must remain separately-addressable fields end-to-end — in the ML service's output, the job payload, the SQLite schema, and the API response. No code may merge them into one composite field at generation time, even where the UI never mislabels one as the other (AD-15).
- **Consolidated ML/audio service boundary** — STT+SER+fusion+calibration live in one deployable Python service, architecturally distinct from the web/API layer; web/API never imports pipeline code in-process; ML service never reachable directly from the frontend; crossing happens only via the job queue (AD-7).
- **Async orchestration via RQ+Redis** — web/API enqueues on upload and never performs analysis itself; only the ML service's RQ worker writes `Call.status`; web/API's DB writes are metadata-only (AD-13).
- **STT output is deterministic and locked to one engine** — faster-whisper produces word-level timestamps for every transcript turn, load-bearing for evidence-linkage (`segment_id` joins, NFR-1); no alternate STT engine may be substituted without amending the Architecture spine (AD-5).
- **Chunk-boundary continuity is required, not just boundary reuse** — rolling context must be carried across chunk boundaries so per-chunk acoustic/transcript analysis is not artificially discontinuous at VAD boundary edges (AD-11).
- **Storage boundary: SQLite + session-scoped filesystem** — structured data (Call, AnalysisResult, TranscriptTurn, TimelineSegment) in SQLite; audio + intermediates in a session-scoped filesystem directory; atomic dual-store delete (SQLite rows + filesystem artifacts together); delete must cancel/await an in-flight RQ job before purging. This persistence exists for dev/demo resilience only — it is not a product promise of durable, permanent storage, consistent with PRD §10's minimal-retention posture; no story may build cross-session/durable retention beyond what a session/demo requires (AD-12).
- **Core data model** — `CALL`, `TRANSCRIPT_TURN`, `TIMELINE_SEGMENT`, `ANALYSIS_RESULT` (Call-level deterministic aggregate, never an independent fusion pass), `ACOUSTIC_EVIDENCE` (one row per `TimelineSegment`); `TimelineSegment`↔`TranscriptTurn` is many-to-many via time-range overlap, not a scalar FK; Sentiment/Emotion confidence and speaker-attribution confidence are two separate fields, co-present on the same row, never conflated (AD-8, AD-10, AD-11).
- **Speaker attribution path split** — stereo input: channel-index-based, no diarization; mono input: WhisperX + pyannote.audio 4.0 Community-1 diarization; canonical display label is a generic "Speaker A/B" regardless of path, with path-specific provenance stored separately (AD-2, AD-6).
- **Local-only inference** — no cloud SER/STT API calls anywhere in the pipeline; all inference runs locally against open-weight models (AD-14).
- **Deployment envelope** — single-machine docker-compose (web-api, frontend build, ml-service+worker, redis, sqlite+filesystem volume); CPU-only baseline, no GPU assumption; no cloud hosting target; no live public demo URL (AD-18).
- **CI, testing, logging baseline** — each pipeline stage has independently runnable unit tests; GitHub Actions runs tests+lint on every push (no deploy step); both services emit structured JSON logs; no metrics/monitoring stack (AD-21).
- **Evaluation strategy** — any accuracy/performance claim about SER or fusion must be benchmarked against a majority-class baseline, then single-modality baselines, before crediting fusion; public benchmark numbers (IEMOCAP/CREMA-D) labeled as optimistic upper bounds pending in-domain validation; UAR and macro-F1 as headline metrics (AD-17).
- **Audio ingest constraints** — WAV/MP3/M4A only; max 30 min duration; max 200MB size; structured, rule-identifying rejection errors (AD-20).
- **Pinned stack versions** — Python 3.13.15, FastAPI 0.141.1, React 19.2.8, faster-whisper v1.2.1, WhisperX 3.8.6, pyannote.audio 4.0.7 (Community-1, CC-BY-4.0, HF-gated), transformers v5.14.1, PyTorch 2.13, librosa 0.11.0, torchaudio 2.11.0, RQ 2.10.0, Redis 8.10, SQLite stdlib (Stack table) — faster-whisper/WhisperX license files flagged for verification at implementation time.
- **Confidence/uncertainty generation** — every modality's native softmax confidence calibrated via temperature scaling before use (sole MVP mechanism); modality disagreement is the fusion stage's uncertainty signal; MC Dropout/ensemble-disagreement explicitly deferred, not MVP (AD-9).
- **Consistency conventions** — Glossary-term naming reused in code/schema/API (`Call`, `Analyst`, `TranscriptTurn`, `AnalysisResult`, `TimelineSegment`); confidence values are calibrated floats in `[0,1]`, any flagging threshold crossing paired with a `flag_reason` string; timestamps are float seconds relative to Call start (in-audio) / ISO 8601 UTC (record-level); evidence-linkage via shared `segment_id`; tunable thresholds live in config, never hardcoded (Consistency Conventions table).

### UX Design Requirements

UX-DR1: Implement the two-surface IA — Session Call List (default landing/work queue) and Analysis Dashboard (full Analysis Result) — with Upload as an in-place transient state of the Session Call List (not a separate route) and Confirm dialog as a non-navigable overlay.
UX-DR2: Implement the Timeline component — 4 base variants (neutral/mixed/negative/positive), each with a fixed glyph (`–`/`◆`/`▼`/`▲`) independent of fill color, plus `low-confidence` (hatch + dashed border + `?`) and `disagreement` (split-fill + `⚠`) variants; each segment individually focusable and keyboard-navigable (arrow keys); selecting a segment synchronizes transcript scroll + acoustic panel highlight (FR-13).
UX-DR3: Implement the 4-cell Summary row — Overall Sentiment, Dominant Emotion (+Confidence), Secondary Signal (with a "None flagged" fallback, never visually empty/broken), Segments Flagged (count; linked to the first flagged segment when >0; plain non-linked "0" when zero).
UX-DR4: Implement the Transcript turn component — default/`low-confidence`/`disagreement` variants; `low-confidence` shows dashed left border + `low` tag + stated reason; `disagreement` shows solid negative left border + `conflict` tag + embedded Dual-signal panel; clicking a flagged turn synchronizes the acoustic panel.
UX-DR5: Implement the Dual-signal panel — two fixed-labeled halves ("Text signal" / "Tone signal"), each with its own value + confidence in `data-inline`; never collapses to one blended number in any state (loading, error, or otherwise).
UX-DR6: Implement the Acoustic metric bar — metric label must name an actual acoustic feature (pitch/F0, energy, speaking rate, or pauses/voice-activity only — never a generic "acoustic score"); measured value; `fill-warn`/`fill-default` states; always paired with a short note anchoring it to a specific transcript timestamp.
UX-DR7: Implement the Call row — filename, Sentiment/Emotion + Confidence with `badge-dot`, duration, hover/focus-revealed delete `icon-button`, full-row click target opening the Dashboard, and an inline "Mono input — turns unattributed" note when speaker attribution is unavailable for that Call.
UX-DR8: Implement the Badge dot — 4 color variants matching the Sentiment/Emotion scale, always rendered immediately adjacent to its text value, never the sole carrier of meaning.
UX-DR9: Implement the Confirm dialog — states the Call's filename and that deletion is immediate/unrecoverable; Cancel (default focus) / Delete (destructive-styled) actions; Escape or overlay-click behaves as Cancel; identical component reused from both the Call row and the Dashboard delete actions.
UX-DR10: Implement the Speaker label component with `default`/`uncertain` variants — `uncertain` uses a *dotted* underline, a deliberately different line style from the transcript-turn `low-confidence` variant's *dashed* border, so the two independent uncertainty axes (speaker-attribution confidence vs. Sentiment/Emotion confidence) are never visually conflated even when co-occurring on the same turn.
UX-DR11: Implement the full Session Call List row-state set: empty session (plain upload prompt, no illustration), uploading/validating (with format/duration/corrupt-file error + retry on failure), processing (non-blocking — other Calls remain usable), processing failed (clear non-blaming message + retry), complete (selectable), deleting (via confirm-dialog; no undo; redirect to list if the deleted Call was open in the Dashboard).
UX-DR12: Implement the Dashboard's Low-confidence segment state and Disagreement segment state (timeline + paired transcript turn) so each is visually distinguishable both from each other and from an ordinary Neutral reading.
UX-DR13: Implement the whole-Call "Speaker attribution unavailable" state (mono input, no diarization split) as distinct from the per-turn "Speaker attribution uncertain" state (low-confidence diarization on an otherwise-attributed Call) — the two must be independently legible and able to co-occur with a confident Sentiment/Emotion reading on the same turn.
UX-DR14: Implement the standing disclaimer bar on every Analysis Dashboard — fixed, non-dismissible, never styled as an alert, identical text on every Call: "Model output — acoustic + lexical estimate, not a determination. Analyst review required before action."
UX-DR15: Enforce voice/tone microcopy rules across all surfaces: never assert certainty as flat fact; "Sentiment" and "Emotion" labels never interchangeable; any `low`/`conflict` tag always paired with a one-line stated reason; missing capability (e.g., no speaker attribution) stated plainly, never hidden; no hype register (no exclamation points, no anthropomorphizing).
UX-DR16: Implement the Accessibility Floor: never-color-alone across every semantic-color use (glyph + pattern + text-label reinforcement); visible `focus-ring` (on-light-surface and on-chrome-surface variants) on every focusable element; full keyboard-completeness for every Interaction Primitive; screen-reader-legible timeline segments with accessible names (time range + reading + flagged state/reason) with the transcript panel as the guaranteed complete non-visual equivalent; text scaling support to 200% OS-level without overlap, validated on the transcript panel and Session Call List; disclaimer and flag-reason text is real text, never image/icon-only.
UX-DR17: Implement the responsive fallback below ~960px viewport width: Dashboard's two-column grid (transcript/acoustic) stacks to a single column (transcript first), the 4-cell summary row wraps to 2×2, and the Call row's delete `icon-button` becomes always-visible instead of hover-only.
UX-DR18: Implement Interaction Primitives: Upload via file picker (required path) + drag-and-drop onto the Session Call List (progressive enhancement, not the only path); full-hit-target click AND keyboard (Enter/Space) activation on every Call row / transcript turn; delete-a-Call available equivalently from the Call row and the Dashboard; return-to-list via the `app-header` breadcrumb.
UX-DR19: Implement the DESIGN.md token system: color palette calibrated to WCAG AA (4.5:1 text under ~18px, 3:1 large-text/non-text UI-boundary); two-family typography (system UI font for prose/labels; monospaced `data`/`data-sm`/`data-inline` used exclusively for measured/numeric values, never mixed into prose/labels); 2px-based spacing scale (`spacing.1`–`spacing.8`); small/consistent corner radii (no large/pill radius except `badge-dot`'s `rounded.full`); flat elevation everywhere except the `confirm-dialog`'s single elevated surface.
UX-DR20: Implement the App header (near-black chrome; wordmark; clickable monospace breadcrumb; analyst identity, no login/account UI) and Case strip (filename, duration, queue name, "analyzed N ago") components per DESIGN.md Components.
UX-DR21: Enforce the Do's and Don'ts guardrails as implementation constraints: no dark-mode variant for MVP; `negative`/`mixed`/`positive`/`neutral-signal` reserved exclusively for actual Sentiment/Emotion readings, never generic accents; any new color token added downstream must be checked against the WCAG AA bar before use, not assumed safe.

### FR Coverage Map

FR-1: Epic 1 - Upload validation
FR-2: Epic 1 - Upload/validation error messaging
FR-3: Epic 1 - Processing status tracking
FR-4: Epic 1 - Mandatory acoustic analysis
FR-5: Epic 1 - Acoustic-derived Emotion signal
FR-6: Epic 1 - Transcript generation (STT)
FR-7: Epic 1 - Transcript sentiment/context analysis
FR-8: Epic 1 - Fusion into single Analysis Result
FR-9: Epic 1 - Emotional Timeline generation
FR-10: Epic 1 - Confidence indicator + low-confidence threshold
FR-11: Epic 1 - Cross-modal disagreement surfacing
FR-12: Epic 2 - Full Analysis Result view
FR-13: Epic 2 - Timeline point evidence drill-down
FR-14: Epic 2 - Low-confidence visual distinction
FR-15: Epic 2 - No-certainty language
FR-16: Epic 3 - Best-effort speaker attribution

## Epic List

### Epic 1: Call Intake & Multimodal Analysis Pipeline

An analyst uploads a Call; the system independently analyzes its acoustic voice signal and its transcribed text, fuses both into a single confidence-qualified, evidence-linked Analysis Result with a chronological Emotional Timeline and explicit cross-modal disagreement flags — retrievable end-to-end via the system's API, with full processing-status visibility (queued/processing/complete/failed) throughout.

**FRs covered:** FR-1, FR-2, FR-3, FR-4, FR-5, FR-6, FR-7, FR-8, FR-9, FR-10, FR-11

**Dependencies:** None (foundational epic).

### Epic 2: Analysis Dashboard

An analyst opens any completed Call and visually reviews its full Analysis Result — summary, Emotional Timeline, transcript, acoustic evidence — drilling into any timeline point to see synchronized supporting evidence, with low-confidence and disagreement segments always visually distinguishable and no language ever asserting settled certainty.

**FRs covered:** FR-12, FR-13, FR-14, FR-15

**Dependencies:** Epic 1 (consumes its API/data output only; no shared runtime process).

### Epic 3: Speaker Attribution

When the input audio allows it, speaker attribution enriches the Analysis Result with agent/customer segment labels — direct channel mapping for stereo input, diarization for mono input. Calls without reliable separation still produce a full, undegraded Analysis Result (FR-16 is best-effort/conditional by design, never guaranteed).

**FRs covered:** FR-16

**Dependencies:** Epic 1 (extends its ingest/transcript pipeline stages) and Epic 2 (populates already-present display slots) — but as **optional data enrichment, not a runtime dependency**. Epic 2's Dashboard already renders "no speaker attribution available" as its default, expected state (per FR-16's conditional framing and UX-DR13), so Epic 2 is fully complete and functional with zero Epic 3 stories built. Epic 3 adds value by populating fields/labels Epic 2 already has a display contract for; it requires no changes to Epic 2's code, and Epic 2 never blocks on or calls into Epic 3 at runtime.

## Epic 1: Call Intake & Multimodal Analysis Pipeline

An analyst uploads a Call; the system independently analyzes its acoustic voice signal and its transcribed text, fuses both into a single confidence-qualified, evidence-linked Analysis Result with a chronological Emotional Timeline and explicit cross-modal disagreement flags — retrievable end-to-end via the system's API, with full processing-status visibility (queued/processing/complete/failed) throughout.

### Story 1.1: Call Upload & Validation

As an Analyst,
I want to upload a Call recording and receive clear validation feedback,
So that I can begin analysis only with a valid audio file and understand immediately if something is wrong.

**Acceptance Criteria:**

**Given** a WAV, MP3, or M4A file under 200MB and under 30 minutes, **When** the Analyst uploads it, **Then** the system accepts it, creates a `Call` record with status `queued`, and returns a Call identifier.
**Given** a file in an unsupported format, **When** uploaded, **Then** the system rejects it with a structured error naming the specific unsupported format, and no Call record is created.
**Given** a file exceeding 200MB or 30 minutes, **When** uploaded, **Then** the system rejects it with a structured error naming the specific limit exceeded (size or duration).
**Given** a non-decodable/corrupt file, **When** uploaded, **Then** the system rejects it with a structured error identifying it as undecodable, before any analysis begins.
**Given** any rejection above, **Then** the error message tells the Analyst what to do next (e.g., "re-export in WAV, MP3, or M4A").
**And** the repo is scaffolded per the Architecture source tree (`web-api/`, `ml-service/`, `frontend/`, `storage/`, `docker-compose.yml`); a `Call` table exists in SQLite; a GitHub Actions workflow runs lint+tests on every push (AD-21); the docker-compose stack serves the upload endpoint (AD-18).

### Story 1.2: Async Processing Lifecycle & Audio Ingest

As an Analyst,
I want to see a Call's status move from queued to processing,
So that I know my upload is being handled and isn't stuck.

**Acceptance Criteria:**

**Given** a Call in `queued`, **When** the ML service's RQ worker picks up the job, **Then** status transitions to `processing`, written only by the worker process — never by web-api (AD-13).
**Given** a Call in `processing`, **When** ingest runs, **Then** the system detects channel count (mono/stereo) and persists it as internal metadata (AD-2).
**Given** a Call's audio, **When** VAD/chunk-boundary detection runs, **Then** the system computes one chunk-boundary set and persists it as ordered `TimelineSegment` rows — this exact set is reused, unmodified, for both model-input chunking and the Emotional Timeline (AD-11).
**Given** chunk boundaries exist, **When** adjacent chunks are later processed, **Then** rolling context is carried across boundaries so downstream analysis is not artificially discontinuous (AD-11).
**Given** ingest completes successfully, **Then** the Call remains `processing` — ingest alone does not complete a Call.
**Given** ingest fails, **When** the failure occurs, **Then** status transitions to `failed` and the Analyst sees a clear "could not be analyzed" message, never a partial/misleading result (FR-3).
**And** web-api's only Call-related DB writes are upload/ingest metadata — it never writes `Call.status`; all analysis is dispatched via RQ/Redis, never in-process (AD-13, AD-7).
**And** the ML/audio service is one consolidated service, never directly reachable from the frontend (AD-7); the full stack runs via docker-compose, CPU-only (AD-18).
**And** the ingest module has independently-runnable unit tests (AD-21).
**And** Call deletion (atomic dual-store removal, in-flight RQ job cancellation) is a separate concern, out of this story's scope — see Story 1.10.

### Story 1.3: Mandatory Acoustic Analysis (SER)

As an Analyst,
I want every Call analyzed for its acoustic/voice signal,
So that tone and vocal delivery are always part of the analysis — never skipped or silently replaced by text-only analysis.

**Acceptance Criteria:**

**Given** a Call has completed ingest, **When** the acoustic-analysis filter runs, **Then** it runs for every `TimelineSegment` using an embedding-based model (Wav2Vec2/HuBERT/WavLM-family fine-tune), producing an Emotion output kept distinct from any text-derived Sentiment (AD-3, FR-5).
**Given** the filter runs, **When** it produces its Emotion output, **Then** it also computes and persists a handcrafted acoustic-feature set (pitch/F0, energy, speaking rate, pauses/voice-activity) as a mandatory `ACOUSTIC_EVIDENCE` row per segment — never optional or debug-only (AD-3).
**Given** handcrafted-feature extraction, **Then** it uses only librosa/torchaudio — openSMILE/eGeMAPS and Praat/parselmouth must never be used (AD-3, license constraint).
**Given** an acoustic Emotion classification, **Then** it maps through one fixed lookup table to exactly one of the four Sentiment polarity colors, using a small coarse category set (AD-4).
**Given** the filter's native softmax confidence, **Then** it is calibrated via temperature scaling before use downstream (AD-9).
**Given** the acoustic filter fails, is skipped, or its calibrated confidence falls below a defined sanity floor, **When** this occurs, **Then** the filter itself raises a job failure, the Call's status goes to `failed`, and there is no fallback path (AD-1).
**Given** the acoustic filter's calibrated confidence, **Then** the **sanity floor** (AD-1, config key `acoustic_sanity_floor`) is a distinct concept from the **low-confidence threshold** (Story 1.8, config key `low_confidence_threshold`): falling below the sanity floor means the result is invalid/degenerate and fails the Call outright — it is never merely flagged and shown. A result at or above the sanity floor but still below the low-confidence threshold is valid, retained, and passed downstream as a Low-Confidence Segment (Story 1.8), never discarded or failed.
**And** both thresholds are documented in config with their distinct semantics and their relative ordering (`acoustic_sanity_floor` set lower than `low_confidence_threshold`, since a valid-but-low-confidence result must first clear the sanity floor to exist at all) — never hardcoded in pipeline code, and never treated as the same value or purpose.
**Given** this failure state, **Then** the Call is never completed using a transcript-only or degraded-acoustic result — **acoustic analysis can never be bypassed, and a transcript-only fallback is forbidden under any condition**, including when transcript analysis (Story 1.5) would otherwise succeed (AD-1).
**Given** a Call successfully completes acoustic analysis, **When** transcript analysis has not yet run or later fails, **Then** the acoustic Emotion signal still exists and is independently valid (FR-4).
**Given** the acoustic classifier, **When** evaluated, **Then** its accuracy is benchmarked against a majority-class baseline first, and any public-benchmark figure (IEMOCAP/CREMA-D) is labeled an optimistic upper bound pending in-domain validation (AD-17).
**And** acoustic inference runs locally only — no cloud SER API call is made (AD-14).
**And** the acoustic module has independently-runnable unit tests (AD-21).

### Story 1.4: Transcript Generation (STT)

As an Analyst,
I want the Call's audio transcribed,
So that I have a text record and text-based analysis has input to work from.

**Acceptance Criteria:**

**Given** a Call has completed ingest, **When** the transcript-generation filter runs, **Then** it produces a text transcript of the English-language audio via faster-whisper, running locally (AD-5, FR-6).
**Given** transcript generation runs, **Then** every `TranscriptTurn` carries word-level timestamps (AD-5).
**Given** this stage is implemented, **Then** no alternate STT engine may be substituted without amending the Architecture spine (AD-5).
**Given** the transcript-generation filter fails, **When** this occurs, **Then** the Call's transcript path is marked failed for this Call, but this does not fail the Call overall — the acoustic signal (Story 1.3) remains valid and usable independently (AD-1).
**And** the transcript module has independently-runnable unit tests (AD-21).

### Story 1.5: Transcript Sentiment & Context Analysis

As an Analyst,
I want the transcript analyzed for sentiment and conversational context,
So that the text signal contributes to the Analysis Result alongside the acoustic signal, without overriding it.

**Dependency:** requires Story 1.4's transcript output. Does not require Story 1.3 — Stories 1.3 and 1.4 remain independent signal producers, each consumed separately by Story 1.6.

**Acceptance Criteria:**

**Given** a Call has a completed transcript (Story 1.4), **When** the transcript-sentiment filter runs, **Then** it derives text-based Sentiment, Emotion indicators, and keywords/context per `TranscriptTurn`/`TimelineSegment` using a small, fine-tuned or pretrained transformer classifier (RoBERTa/DistilBERT-family) (AD-19, FR-7).
**Given** this stage is implemented, **Then** a general-purpose LLM (local or cloud) and any cloud LLM API must never be used for this stage — the classifier must be a small, controllable, explainable transformer, never part of an "audio → STT → LLM → sentiment" pattern (AD-19).
**Given** the filter's native softmax confidence, **Then** it is calibrated via temperature scaling before use downstream (AD-9).
**Given** transcript Sentiment/Emotion output, **Then** it is kept distinct from Acoustic Analysis output — a contributing signal for Fusion (Story 1.6), never a pre-emptive final answer on its own (FR-7).
**Given** the transcript-sentiment filter fails, **When** this occurs, **Then** the Call's transcript path is marked failed without failing the Call overall, consistent with Story 1.4 and AD-1.
**And** inference runs locally — no cloud API call is made (AD-14).
**And** the module has independently-runnable unit tests (AD-21).

### Story 1.6: Multimodal Fusion into a Single Analysis Result

As an Analyst,
I want the acoustic and transcript signals combined into one Analysis Result per Call,
So that I get one coherent, evidence-based judgment instead of two disconnected outputs.

**Acceptance Criteria:**

**Given** a Call has a valid acoustic-Emotion signal (Story 1.3), **When** the fusion filter runs, **Then** it runs regardless of whether the transcript-Sentiment signal (Story 1.5) exists or succeeded — fusion's only hard precondition is a valid acoustic signal, never transcript availability (AD-1).
**Given** fusion runs with both a valid acoustic signal and a valid transcript signal, **Then** it executes once per `TimelineSegment` — not once per Call — using confidence-weighted averaging of the two calibrated signals as a fixed rule; a trained/learned fusion model must never be used (AD-8), producing a multimodal Analysis Result.
**Given** fusion runs with a valid acoustic signal but the transcript signal is unavailable or failed (Story 1.4 or 1.5), **Then** it outputs the acoustic-emotion signal alone with an explicit single-modality flag on the affected segments and on `ANALYSIS_RESULT` — never presented as an ordinary two-signal fused result (AD-1, AD-8).
**Given** fusion completes (multimodal or single-modality) for all segments, **When** it finishes, **Then** `ANALYSIS_RESULT` is computed as a deterministic reduction over the Call's `TimelineSegment` rows (confidence-weighted mean); `ANALYSIS_RESULT` never runs an independent fusion pass of its own (AD-8).
**Given** Sentiment and Emotion values are generated, **Then** they remain separately-addressable fields end-to-end — in the ML service's output, the job payload, the SQLite schema, and the API response; no code merges them into one composite field at generation time (AD-15).
**Given** a row carries both Sentiment/Emotion confidence and speaker-attribution confidence, **Then** they are two separate fields, never combined into one composite score (AD-10).
**Given** fusion completes for all segments, **When** the last stage finishes, **Then** the Call's status transitions to `complete` (FR-3).
**Given** fusion is evaluated for accuracy, **Then** it is benchmarked against a majority-class baseline, then single-modality baselines, before crediting fusion with any benefit (AD-17).
**And** the fusion module has independently-runnable unit tests (AD-21).

### Story 1.7: Emotional Timeline Retrieval

As an Analyst,
I want to retrieve a chronological view of how Sentiment and Emotion evolve across a Call,
So that I see the shape of the conversation, not just one aggregate score.

**Dependency:** requires Story 1.6 (fusion) for per-segment confidence and Sentiment/Emotion values. The `disagreement flag` field returned in AC1 below is owned by Story 1.9 (Cross-Modal Disagreement Surfacing) — until Story 1.9 is implemented, every segment's disagreement flag defaults to `false`/absent, and this story is fully completable and testable against that default, per the same forward-decoupling pattern Story 2.5 uses for its Epic 3 dependency. This story does not need to be re-opened once Story 1.9 lands — the field's shape is unchanged, only its populated value.

**Acceptance Criteria:**

**Given** a Call is `complete`, **When** the timeline is requested, **Then** the system returns all `TimelineSegment` rows in chronological order, each with its fused Sentiment, Emotion, confidence, and disagreement flag — the disagreement flag defaults to `false`/absent until Story 1.9's threshold logic is implemented (see Dependency above).
**Given** the returned timeline, **Then** its resolution is granular enough to distinguish two distinct emotional shifts within the same Call — never a single aggregate score presented as a timeline (FR-9).
**Given** the timeline's segment boundaries, **Then** they are identical to the model-input chunk boundaries from Story 1.2 — never a second, independently-computed boundary set (AD-11).
**And** the endpoint has independently-runnable unit tests (AD-21).

### Story 1.8: Confidence & Low-Confidence Segment Flagging

As an Analyst,
I want every Sentiment/Emotion value to show its confidence, and to be told plainly when confidence is low,
So that I don't mistake a shaky guess for a confident finding.

**Acceptance Criteria:**

**Given** any Sentiment/Emotion value (overall or per-segment), **When** returned by the API, **Then** it always carries a Confidence indicator — never returned without one (FR-10, AD-16).
**Given** a segment's calibrated confidence falls below a defined, configurable threshold, **Then** it is marked a Low-Confidence Segment with a paired `flag_reason` string — never a bare float on a flagged item.
**Given** a segment's confidence is at or above the acoustic sanity floor (Story 1.3, AD-1) but below the low-confidence threshold, **Then** it is a valid result — flagged as Low-Confidence, never invalidated or failed. The sanity floor and the low-confidence threshold are separate, independently-configured values serving different purposes (invalidity gate vs. flagging gate) and must never be conflated into one config key.
**Given** the threshold, **Then** it lives in config as `low_confidence_threshold`, never hardcoded in pipeline code.
**Given** a row carries both confidence axes, **Then** they are co-present as two separate fields on the same row — not merely reachable via a join (AD-10).
**And** this story does not itself claim the Confidence values are statistically calibrated or ground-truth-validated (NFR-2) — only that a documented threshold and calibration mechanism exist.

### Story 1.9: Cross-Modal Disagreement Surfacing

As an Analyst,
I want to be told when the acoustic and transcript signals disagree about a moment,
So that I can look closer instead of trusting a silently-blended number.

**Acceptance Criteria:**

**Given** a segment where the two modalities disagree in polarity and both exceed the **disagreement threshold** (AD-8; named alongside the low-confidence threshold in Architecture's Consistency Conventions as one of the two cross-cutting tunable thresholds — not a newly invented third value), **When** fusion evaluates it, **Then** an explicit per-segment disagreement flag is set and both signals are preserved and retrievable — never collapsed into one blended value (AD-8, FR-11).
**Given** the disagreement threshold, **Then** it is configured and documented as `disagreement_threshold`, kept separate from `low_confidence_threshold` (Story 1.8) and `acoustic_sanity_floor` (Story 1.3) — three distinct, independently-configured thresholds serving three distinct purposes (disagreement-trigger, flagging, invalidity), none interchangeable, none hardcoded in pipeline code.
**Given** a flagged segment, **When** retrieved via the API, **Then** it is distinguishable from a segment where both signals agreed.
**Given** the non-dominant modality's reading is distinct enough to report, **Then** it is retained and exposed as a "Secondary Signal" on `ANALYSIS_RESULT`, separate from the per-segment disagreement flag — never simply discarded (AD-8).
**Given** no distinct-enough secondary reading exists, **When** requested, **Then** the API returns an explicit "none" state, not empty/null.
**And** this logic has independently-runnable unit tests (AD-21).
**And** Story 1.7's timeline-retrieval endpoint already exposes the `disagreement flag` field by contract (defaulting to `false`/absent — see Story 1.7 Dependency note); this story populates its real value, requiring no API shape change.

### Story 1.10: Call Deletion (Backend)

As an Analyst,
I want a Call and everything it produced to be permanently and atomically removable,
So that I can keep my session's data minimal, consistent with the product's no-persistent-retention posture, and trust that "delete" means fully gone.

**Dependency:** requires Story 1.1 (Call exists to be deleted) and Story 1.2 (RQ job queue/worker lifecycle, for in-flight job cancellation). Split out of Story 1.2 to isolate deletion as its own independently testable concern, distinct from async processing/ingest — Epic 2's Story 2.3 is the UI consumer of this endpoint.

**Acceptance Criteria:**

**Given** a Call (in any status) is deleted, **When** the delete endpoint is invoked, **Then** the Call's SQLite rows (Call, AnalysisResult, TranscriptTurn, TimelineSegment) and its filesystem artifacts (audio, intermediates) are removed together, atomically — never one without the other (AD-12).
**Given** a Call with an in-flight (`queued` or `processing`) RQ job is deleted, **When** the delete request arrives, **Then** the system first cancels or awaits that job's completion before removing the Call's rows and artifacts — delete must never race a live job's writes (AD-12).
**And** delete is exposed as a backend endpoint only in this story (no UI) — the Delete UI (action trigger, confirm dialog, deleting state, success/error feedback) is Epic 2's Story 2.3, which calls this endpoint.
**And** this endpoint has independently-runnable unit tests (AD-21).

## Epic 2: Analysis Dashboard

An analyst opens any completed Call and visually reviews its full Analysis Result — summary, Emotional Timeline, transcript, acoustic evidence — drilling into any timeline point to see synchronized supporting evidence, with low-confidence and disagreement segments always visually distinguishable and no language ever asserting settled certainty. Also delivers the Session Call List frontend (the product's front door, consuming Epic 1's upload/status API) and the Delete UI (consuming Epic 1's atomic delete endpoint), since this is the epic that establishes the React frontend.

### Story 2.1: Web Console Frontend Foundation & Session Call List Shell

As an Analyst,
I want to open the application into a working console shell with my session's call list,
So that I have a starting point to begin uploading and reviewing calls.

**Acceptance Criteria:**

**Given** the frontend is built, **When** the Analyst opens the application, **Then** a React 19 app loads directly into the Session Call List (default landing surface) — no login/account screen, since MVP has no auth (PRD §2.3).
**Given** the app loads, **When** the App header renders, **Then** it shows the near-black chrome bar with the product wordmark (left, `chrome-text-strong`), a monospace breadcrumb (center, queue/case path), and analyst identity (right, name+role, no login UI).
**Given** the app renders any surface, **When** any color, typography, spacing, or shape is applied, **Then** it is sourced from DESIGN.md's token system — no ad hoc values.
**Given** the Session Call List has zero Calls, **When** the Analyst views it, **Then** it shows a plain prompt to upload the first Call — no illustration/mascot.
**Given** a viewport narrower than ~960px, **Then** this story does not implement the responsive fallback — that is Story 2.7's scope; this story only needs to render correctly at the primary desktop-width target.
**And** this story establishes the frontend build/serve pipeline within the existing docker-compose stack — no new deployment target beyond what AD-18 already defines.

**Traceability:** UX-DR1, UX-DR19, UX-DR20, UX-DR21 (token-sourced-only rendering, no ad hoc values); AD-18 (frontend build container, not a new decision).

### Story 2.2: Call Upload & Processing-Status Feedback

As an Analyst,
I want to upload a Call from the Session Call List and watch it move through validation and processing,
So that I know exactly what's happening to my upload without leaving my queue.

**Acceptance Criteria:**

**Given** the Session Call List, **When** the Analyst clicks "+ Add call" or uses the file picker, **Then** a native file-selection dialog opens — file picker is the required, always-available path.
**Given** the Session Call List, **When** the Analyst drags a file onto it, **Then** the same upload flow triggers — drag-and-drop is a progressive enhancement, not the only path.
**Given** a file is submitted, **When** it is sent to Epic 1's upload endpoint (Story 1.1), **Then** a new row appears in the list in a "validating" state (FR-1).
**Given** the upload fails validation (per Story 1.1's API), **When** the error is returned, **Then** the row shows the specific validation error and a retry/re-upload action — it does not disappear or block the rest of the list (FR-2).
**Given** validation passes, **When** the Call is queued and picked up by the worker (Story 1.2), **Then** the row shows a "processing" status distinct from "validating" and "complete" (FR-3) — the Analyst can keep working with other Calls; processing is never full-screen blocking.
**Given** processing fails (Story 1.2/1.3), **When** the row updates, **Then** it states the Call could not be analyzed with a clear, non-blaming message and a retry action — never shown as if it silently completed (FR-3).
**Given** a Call reaches `complete`, **When** the Analyst views its row, **Then** the row is selectable (full-row hit target, click or keyboard Enter/Space) and opens the Analysis Dashboard.
**Given** a Call row, **When** rendered, **Then** it shows filename, Sentiment/Emotion + Confidence with `badge-dot`, and duration — populated once `complete`; earlier states show status text in place of result fields.
**And** this story only consumes Epic 1's existing upload/status API (Stories 1.1, 1.2) — no new backend endpoint or status semantics introduced.

**Traceability:** FR-1, FR-2, FR-3; UX-DR7, UX-DR8, UX-DR11, UX-DR18.

### Story 2.3: Delete a Call (UI only)

As an Analyst,
I want to delete a Call I no longer need from either the Call row or its Dashboard,
So that I can keep my session's list relevant without carrying data I don't need.

**Acceptance Criteria:**

**Given** a Call row, **When** the Analyst hovers or focuses it, **Then** a delete `icon-button` is revealed (transparent by default, destructive-hover red foreground) — hidden otherwise.
**Given** the Analyst is viewing a Call's Dashboard, **When** they choose to delete it, **Then** the same delete action is available there, using the identical `confirm-dialog` component as the Call row's.
**Given** delete is triggered (either surface), **When** the confirm dialog opens, **Then** it states the Call's filename and that deletion is immediate and unrecoverable, with Cancel (default focus, no change) and Delete (destructive-styled, confirms).
**Given** the dialog is open, **When** the Analyst presses Escape or clicks the overlay, **Then** it behaves identically to Cancel.
**Given** the Analyst confirms Delete, **When** the request is sent, **Then** it calls Story 1.10's backend delete endpoint — no delete/atomic-store logic is implemented in this story.
**Given** the delete request is in flight, **When** the UI reflects it, **Then** the row (or Dashboard) shows a "deleting" state.
**Given** the delete succeeds, **When** the response returns, **Then** the Call is removed from the list immediately (no undo); if it was open in the Dashboard, the Analyst returns to the Session Call List.
**Given** the delete request fails, **When** the response returns, **Then** the UI shows a clear error and the Call remains in the list, undeleted.
**Given** the Analyst cancels or dismisses the dialog, **Then** nothing changes.

**Traceability:** UX-DR9; consumes AD-12 (Story 1.10) — not re-implemented here.

### Story 2.4: Analysis Dashboard — Summary Cells & Full Result View

As an Analyst,
I want to view the full Analysis Result for a completed Call in one place,
So that I can see the overall picture before deciding whether to dig deeper.

**Acceptance Criteria:**

**Given** a completed Call, **When** the Analyst opens its Dashboard, **Then** they can view overall Sentiment, dominant Emotion, Confidence, Emotional Timeline, full transcript, and acoustic insights — all within this one surface, without leaving the tool (FR-12).
**Given** the Dashboard header area, **When** rendered, **Then** the Case strip shows filename, duration, queue name, and "analyzed N ago."
**Given** the summary area, **When** rendered, **Then** it shows exactly four cells — Overall Sentiment, Dominant Emotion (+ Confidence), Secondary Signal, Segments Flagged — with the Confidence value in that cell unambiguously tied to the Dominant Emotion reading, per the Analysis Result's data contract (Story 1.6/1.8) — never a separate, generically-labeled confidence figure that could be read as belonging to Overall Sentiment instead.
**Given** the Secondary Signal cell, **When** no distinct-enough secondary reading exists (Story 1.9's "none" state), **Then** it displays "None flagged," never left empty/broken.
**Given** the Segments Flagged cell, **When** its count is greater than zero, **Then** it links to the first flagged segment; **when** zero, **Then** it displays plain, non-linked "0."
**Given** the main content area, **When** rendered, **Then** the full transcript panel and acoustic insights panel are both present in the two-column grid (~60%/~40%).
**Given** this story's components, **When** rendered, **Then** `badge-dot` is always adjacent to its text value, never alone, and all text/background pairs meet WCAG AA (4.5:1 text, 3:1 large-text/UI-boundary).
**Given** the Analyst is viewing a Call's Dashboard, **When** they click the `app-header` breadcrumb (established in Story 2.1), **Then** they are returned to the Session Call List — the normal, non-delete path back to the list from the Dashboard.
**And** per-segment drill-down interaction, low-confidence/disagreement states, and the dual-signal panel are Story 2.5's scope, not this story's.

**Traceability:** FR-12; NFR-1 (partial — evidence reachable, detail in 2.5); AD-16 (Confidence co-present with the Dominant Emotion reading, never shown unqualified); UX-DR3, UX-DR8, UX-DR18 (breadcrumb return-to-list), UX-DR20, UX-DR21 (WCAG AA token-sourced pairing).

### Story 2.5: Timeline, Transcript & Acoustic Evidence Drill-Down (low-confidence + disagreement states)

As an Analyst,
I want to select any point on the Emotional Timeline and see its exact supporting evidence, with low-confidence and disagreement moments impossible to miss,
So that I can judge each moment on real evidence instead of a bare label.

**Acceptance Criteria:**

**Given** a completed Call's Dashboard, **When** the Timeline renders, **Then** it is a chronologically-ordered strip covering the full Call, each segment showing its fill color and fixed glyph (`–`/`◆`/`▼`/`▲`).
**Given** a Low-Confidence segment, **When** rendered, **Then** it shows the hatch pattern, dashed border, and `?` glyph — never confusable with a "Neutral" reading (FR-14).
**Given** a Disagreement segment, **When** rendered, **Then** it shows the split-fill and `⚠` glyph.
**Given** the Analyst selects a Timeline segment (click or arrow-key when focused), **When** selected, **Then** the transcript panel scrolls to the corresponding turn and the acoustic panel highlights the relevant metrics — one action synchronizes all three panels (FR-13).
**Given** a transcript turn, **When** rendered, **Then** it shows `default`, `low-confidence` (dashed left border, `low` tag + stated reason), or `disagreement` (solid negative left border, `conflict` tag, embedded Dual-signal panel) matching its segment's state.
**Given** a `disagreement` turn, **When** rendered, **Then** it contains the Dual-signal panel — two fixed-labeled halves ("Text signal"/"Tone signal"), each with its own value+confidence — never collapsed to one blended number.
**Given** the acoustic panel displays a metric, **When** rendered, **Then** it names an actual acoustic feature (pitch/F0, energy, speaking rate, or pauses/voice-activity — never a generic "acoustic score"), shows the measured value, and is anchored to a specific transcript timestamp.
**Given** a transcript turn whose Analysis Result speaker-attribution data indicates the `uncertain` state (per the predefined speaker-attribution contract — see Architecture AD-6/AD-10), **When** rendered, **Then** its Speaker label shows the `uncertain` variant (dotted underline) — visually distinct from the transcript-turn `low-confidence` dashed border, so the two uncertainty axes are never conflated. This story renders the UI contract against that existing data shape only; populating real diarization values into that contract is Epic 3's responsibility, not a dependency this story waits on.
**Given** every Timeline segment, **When** accessed by a screen reader, **Then** it carries an accessible name stating time range, reading, and — when applicable — flagged state/reason.
**Given** the transcript panel, **When** used by a screen reader, **Then** it is the guaranteed complete non-visual equivalent to the Timeline.
**Given** every Timeline segment, **When** focused via keyboard, **Then** it is individually focusable with the `focus-ring` treatment.
**And** this story does not implement the whole-Call "Speaker attribution unavailable" state or Epic 3's diarization data itself — only the UI contract Epic 3 will populate.

**Traceability:** FR-9 (UI realization), FR-11 (UI realization), FR-13, FR-14; NFR-1; AD-16 (evidence linkage — timeline/transcript/acoustic synchronization is the evidence-linked drill-down AD-16 requires); UX-DR2, UX-DR4, UX-DR5, UX-DR6, UX-DR10, UX-DR12; partial UX-DR16 (screen-reader/focus items owned here).

### Story 2.6: No-Certainty Language, Standing Disclaimer & Terminology Discipline

As an Analyst,
I want every reading phrased as an estimate, not a fact, with a constant reminder that I am the final reviewer,
So that I never mistake the tool's output for a settled verdict.

**Acceptance Criteria:**

**Given** every Dashboard, **When** it renders, **Then** it shows the standing disclaimer bar under the summary cells, with the fixed, non-dismissible, non-alert-styled copy: "Model output — acoustic + lexical estimate, not a determination. Analyst review required before action." — identical on every Call (NFR-4).
**Given** any Sentiment/Emotion reading anywhere in the Dashboard, **When** displayed, **Then** it is presented as an estimate, not a factual determination, and is evidence-linked where applicable — never a flat assertion of settled fact (e.g., never "the customer is frustrated") (FR-15; NFR-2 confidence honesty — this AC does not require numeric/probabilistic phrasing everywhere, only that certainty is never asserted).
**Given** a field labeled "Sentiment," **Then** it always shows a polarity; **given** a field labeled "Emotion," **Then** it always shows an Emotion value — no UI string uses one to mean the other (NFR-3).
**Given** any `low`/`conflict` tag, **When** rendered, **Then** it is never shown bare — always paired with its stated reason.
**Given** a Call without available speaker attribution, **When** its Dashboard renders, **Then** it states this plainly ("Mono input — turns unattributed") — this AC establishes the copy contract; Epic 3 supplies the actual data.
**Given** any accuracy, performance, or reliability claim, **When** it would be surfaced anywhere in the product (in-app copy or documentation), **Then** it must state what it was measured against (dataset, method, conditions); for MVP, this means no aggregate or unqualified accuracy/performance claim is displayed anywhere in the product — the only numbers shown are per-Call Confidence values, already governed by the certainty AC above (NFR-5).
**Given** any Dashboard copy, **When** authored, **Then** it uses no exclamation points, no "Great news!" framing, no anthropomorphizing language.
**Given** the disclaimer bar and every flag-reason string, **When** rendered, **Then** they are real text, never image/icon-only.
**And** this story governs copy/language only — it does not alter Story 2.4/2.5's visual/interaction contracts.

**Traceability:** FR-15; NFR-2, NFR-3, NFR-4, NFR-5; UX-DR14, UX-DR15; partial UX-DR16 (real-text requirement owned here).

### Story 2.7: Accessibility Floor & Responsive Fallback (cross-cutting verification)

As an Analyst,
I want the entire console to remain fully usable by keyboard, at larger text sizes, and on a narrower browser window,
So that the tool works reliably regardless of how I access it.

**Acceptance Criteria:**

**Given** every focusable element built across Stories 2.1–2.6, **When** focused, **Then** each shows the `focus-ring` treatment — verified app-wide, not per-component in isolation.
**Given** every Interaction Primitive defined across Epic 2, **When** attempted via keyboard only, **Then** each completes successfully end-to-end with no mouse-only step.
**Given** the transcript panel and Session Call List, **When** text is resized up to 200% (per the WCAG 1.4.4 benchmark), **Then** no content or functionality is lost and no text overlaps — stated as a requirement outcome, independent of which specific resizing mechanism (OS-level, browser zoom, or otherwise) is used to verify it.
**Given** a viewport narrower than ~960px, **When** the Dashboard renders, **Then** its two-column grid stacks to a single column, transcript first.
**Given** a viewport narrower than ~960px, **When** the summary row renders, **Then** it wraps to a 2×2 grid.
**Given** a viewport narrower than ~960px, **When** the Session Call List renders, **Then** the delete `icon-button` becomes always-visible rather than hover-only.
**Given** this fallback, **When** compared to a dedicated mobile/tablet layout, **Then** no such layout is implemented — narrower-desktop-window fallback only, not a touch-first redesign.
**And** this story introduces no new accessibility requirement beyond what Stories 2.1–2.6 already committed to — verification pass plus the responsive-fallback behavior itself.

**Traceability:** UX-DR16, UX-DR17.

## Epic 3: Speaker Attribution

When the input audio allows it, speaker attribution enriches the Analysis Result with agent/customer segment labels — direct channel mapping for stereo input, diarization for mono input. Calls without reliable separation still produce a full, undegraded Analysis Result (FR-16 is best-effort/conditional by design, never guaranteed). Optional data enrichment on top of Epic 1's pipeline and Epic 2's already-built display slots — not a runtime dependency for either.

### Story 3.1: Stereo Channel-Based Speaker Attribution

As an Analyst,
I want stereo Calls to have their speech automatically attributed to agent/customer by channel,
So that I see a per-speaker breakdown without needing a diarization model to run.

**Acceptance Criteria:**

**Given** a Call detected as stereo (channel detection from Story 1.2), **When** speaker attribution runs, **Then** speaker identity is assigned deterministically by channel index — no diarization model runs for this Call (AD-2).
**Given** stereo channel-based attribution, **When** speaker identity is exposed to the API/UI, **Then** it uses a canonical generic label ("Speaker A"/"Speaker B"), never the raw channel index directly (AD-2).
**Given** stereo channel-based attribution, **When** the channel index is used internally, **Then** it is stored as separate internal provenance metadata, never as the display-facing label itself (AD-2).
**Given** a stereo Call, **When** attribution completes, **Then** it applies to every `TranscriptTurn` in the Call — no path may skip attribution and silently label all speech as one undifferentiated speaker (AD-2).
**Given** stereo channel-based attribution is deterministic, **Then** it carries no per-turn confidence/uncertainty state — only the mono/diarization path (Stories 3.2/3.3) can produce a low-confidence or uncertain attribution outcome; this decision is preserved as-is, not reopened by this story.
**And** this story does not implement mono-path diarization (Story 3.2) or any failure/uncertainty state (Story 3.3).

**Traceability:** FR-16; AD-2.

### Story 3.2: Mono Diarization via WhisperX + pyannote

As an Analyst,
I want mono Calls to be diarized into distinct speakers where possible,
So that I still get a per-speaker breakdown even when the input audio doesn't have a dedicated channel per speaker.

**Acceptance Criteria:**

**Given** a Call detected as mono (channel detection from Story 1.2), **When** speaker attribution runs, **Then** diarization is performed by WhisperX orchestrating faster-whisper transcription (Story 1.4), forced alignment, and pyannote.audio's 4.0 Community-1 pipeline (AD-6).
**Given** mono diarization, **Then** the commercial precision-2 tier, or any tier requiring a paid license, is never used (AD-6).
**Given** a stereo Call, **Then** this story's diarization logic never runs for it — stereo input never invokes WhisperX or diarization (AD-2, AD-6).
**Given** diarization produces speaker clusters, **When** speaker identity is exposed to the API/UI, **Then** each cluster maps to a canonical generic label ("Speaker A"/"Speaker B"), consistent in shape with the stereo path's labels (AD-2).
**Given** diarization produces speaker clusters, **When** the cluster id is used internally, **Then** it is stored as separate internal provenance metadata, never as the display-facing label itself (AD-2).
**Given** diarization runs, **When** it produces a per-turn speaker label, **Then** it also produces a per-turn diarization confidence value, captured and stored — never discarded (AD-6, AD-10).
**And** this story does not implement the whole-Call "unavailable" or per-turn "uncertain" failure/uncertainty states — that is Story 3.3's scope.

**Traceability:** FR-16; AD-6.

### Story 3.3: Speaker-Attribution Failure & Uncertainty States

As an Analyst,
I want to be told plainly when speaker attribution isn't available at all, and separately when a specific turn's attribution is uncertain,
So that I can trust the labels I do see and know exactly which ones to question.

**Acceptance Criteria:**

**Given** a mono Call where diarization produces no usable speaker split at all, **When** this occurs, **Then** the whole Call gets a Call-level "attribution unavailable" state — the Call still produces a full Analysis Result per FR-16, just without a per-speaker breakdown (AD-6).
**Given** a mono Call where diarization succeeds overall but a specific turn's speaker label is low-confidence, **When** this occurs, **Then** that turn gets a per-turn "uncertain" state, while the rest of the Call's attribution stands unaffected (AD-6).
**Given** these two states, **Then** they are represented distinctly, never conflated — a whole-Call "unavailable" state is not the same data/state as a per-turn "uncertain" state (AD-6).
**Given** a stereo Call, **Then** neither the whole-Call "unavailable" state nor the per-turn "uncertain" state ever applies — stereo channel-based attribution (Story 3.1) remains deterministic and always available, a decision this story does not reopen (AD-2).
**Given** a turn's diarization confidence (Story 3.2) and its Sentiment/Emotion confidence (Epic 1), **When** both exist on the same row, **Then** they remain two separate fields, never combined into a single score (AD-10).
**Given** the per-turn "uncertain" state, **When** it is triggered, **Then** it is based on the diarization confidence value already captured in Story 3.2 being assessed as low, per AD-6's rule — this story introduces no new confidence-scoring algorithm, threshold model, or fallback mechanism; exact threshold mechanics remain implementation/config-level detail, not a new architectural decision (consistent with Architecture's Deferred section already treating exact threshold values as deferred, not fixed at the spine level).
**And** this story does not touch how these states are displayed — that is Story 3.4's scope.

**Traceability:** FR-16; AD-6, AD-10.

### Story 3.4: Speaker Attribution Surfaced in Dashboard & Call List

As an Analyst,
I want to see real speaker attribution (or a clear note when it isn't available) directly in the Dashboard and Call list,
So that I don't have to guess whether a label I'm looking at is trustworthy.

**Acceptance Criteria:**

**Given** a Call with stereo channel-based attribution (Story 3.1) or successful mono diarization (Story 3.2), **When** the Analyst views its Dashboard, **Then** each transcript turn's Speaker label (Story 2.5's existing UI contract) renders the real "Speaker A"/"Speaker B" value for that turn — no new label UI introduced, only real data populated into the existing component.
**Given** a turn in the per-turn "uncertain" state (Story 3.3), **When** rendered, **Then** the Speaker label shows the existing `uncertain` variant (dotted underline, Story 2.5) populated with the reason text already defined in EXPERIENCE.md ("overlapping speech — speaker attribution uncertain") — no new copy authored.
**Given** a Call in the whole-Call "attribution unavailable" state (Story 3.3), **When** the Analyst views its Dashboard, **Then** transcript turns render without speaker labels and the existing inline note ("Mono input — turns unattributed", Story 2.6's copy contract) is shown — populated only for Calls actually in this state, never shown for a Call with successful stereo or mono attribution.
**Given** a Call in the whole-Call "attribution unavailable" state, **When** the Analyst views the Session Call List, **Then** its Call row shows the existing small inline warning ("Mono input — turns unattributed") per the Call row component spec — populated only under this real condition, not as a default/placeholder shown on every row.
**Given** a Call with successful attribution (stereo or mono, no whole-Call failure), **When** the Analyst views its Call row, **Then** no "Mono input — turns unattributed" warning is shown.
**And** this story authors no new UI component, variant, or copy string — it exclusively wires Stories 3.1–3.3's real backend data into the UI contracts Epic 2 (Stories 2.5, 2.6) already built.

**Traceability:** FR-16; UX-DR7, UX-DR10, UX-DR13.
