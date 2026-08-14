# Adversarial Review — Two-Units-One-Level-Down Attack

**Target:** `ARCHITECTURE-SPINE.md` (AI Voice Sentiment Analyzer, initiative altitude)
**Lens:** Construct pairs of independently-built units, each obeying every AD to the letter, that still produce incompatible systems — clashing data shapes, dual ownership of one entity, conflicting state-mutation paths. Every pair found is a hole in the spine, not a bug in an implementer.

**Method:** For each pipeline boundary (ingest→VAD→acoustic/transcript→fusion→calibration), each entity in the Core-entity sketch, and each state-mutating rule (status, delete), I asked: could two engineers reading only this spine build parts that both pass every literal AD check yet cannot be wired together? Seven such pairs survived scrutiny, ranked by blast radius.

---

## Finding 1 [CRITICAL] — Sentiment/Emotion storage granularity is undefined and the spine's own text pulls two ways

**The ambiguity:** Nothing in the spine states whether a Sentiment/Emotion value+confidence is a **single Call-level fact** (one row, produced once by fusion) or a **per-segment time series** (one value per `TimelineSegment`, needed to render the Emotional Timeline). The document contains genuine internal tension, not just silence:

- The Core-entity sketch fixes `CALL ||--|| ANALYSIS_RESULT : "produces"` — a strict **one-to-one**, singular relationship.
- AD-15 speaks entirely in singular/Call terms: *"Fusion output must carry a Sentiment value + confidence and an Emotion value + confidence side by side."*
- AD-8 speaks of "a standing field on **every fused result**" for Secondary Signal, explicitly calling it "**per-Call**," but in the same sentence distinguishes it from "**the per-segment disagreement flag above**" — confirming a per-segment fusion output also exists, with no entity named to hold it.
- AD-10 flatly requires: *"On `TranscriptTurn` and `TimelineSegment` records specifically, both fields must be co-present on the same row"* — where "both fields" = Sentiment/Emotion confidence + speaker-attribution confidence. This only makes sense if `TimelineSegment` (and `TranscriptTurn`) carry their **own** Sentiment/Emotion confidence, not just a copy of a Call-level number.
- FR-9 (Emotional Timeline) is unimplementable without per-segment Sentiment/Emotion — a timeline that doesn't vary per segment isn't a timeline.

**Two units that would both pass every AD literally:**

- **Unit A (fusion/calibration engineer, reading AD-15 + the ER diagram literally):** Implements fusion to run once per Call. `ANALYSIS_RESULT` is the sole Sentiment/Emotion authority (Call-level Sentiment+confidence, Emotion+confidence, disagreement flag, Secondary Signal). `TimelineSegment` rows get a denormalized *copy* of the single Call-level confidence value to satisfy AD-10's "co-present on the same row" literally, without any independent per-segment sentiment computation.
- **Unit B (timeline engineer, reading AD-10 + AD-11 + FR-9 literally):** Implements fusion to run once per VAD chunk/segment (since AD-11 makes VAD boundaries "a technical necessity" for model-input chunking, and per-chunk analysis is rolling-context-aware per AD-11). Each `TimelineSegment` gets its own independently-computed Sentiment/Emotion+confidence+disagreement-flag. `ANALYSIS_RESULT` becomes a rollup/aggregate computed by some unspecified reduction (majority vote? last segment? weighted mean?) over the segments.

These two units cannot be integrated: Unit A's `TimelineSegment` rows are inert copies with no real per-segment signal (breaks FR-9's timeline and the disagreement flag's per-segment semantics); Unit B's `ANALYSIS_RESULT` needs an aggregation rule Unit A never built and AD-8/AD-15 never specify. Whichever one the other engineer assumed exists, doesn't.

**What would close it:** A new/tightened AD stating explicitly: (a) fusion executes once per VAD/timeline segment, producing a full Sentiment+Emotion+confidence+disagreement-flag tuple on every `TimelineSegment` row; (b) `ANALYSIS_RESULT` is a defined, named reduction over those segment-level tuples (state the reduction rule — e.g., confidence-weighted aggregate across segments, or "last non-degraded segment," or explicit majority-class-of-segments) plus the Call-level-only fields (Secondary Signal, single-modality flag); (c) the reduction rule itself must be deterministic and specified enough that two implementers compute the same `ANALYSIS_RESULT.Sentiment` from the same segment set.

---

## Finding 2 [CRITICAL] — "Acoustic-evidence record" is referenced twice but never defined as an entity

**The ambiguity:** AD-3 mandates the SER stage "must also compute and persist a handcrafted acoustic-feature set (pitch/F0, energy, speaking rate, pauses/voice-activity)... never conditional, never debug-only." The Consistency Conventions table then names a `segment_id` join key connecting "a TimelineSegment to its TranscriptTurn(s) **and acoustic-evidence record**." AD-16 requires every result be "evidence-linked (traceable to a timeline segment, transcript span, and **acoustic evidence**)." So the spine clearly intends an acoustic-evidence artifact to exist and be joinable via `segment_id` — but the Core-entity sketch's ER diagram lists exactly four entities (`CALL`, `TRANSCRIPT_TURN`, `TIMELINE_SEGMENT`, `ANALYSIS_RESULT`) and none of them is named as, or documented to contain, this acoustic-evidence record. Its cardinality (per-Call? per-segment?) and its home table are both unstated.

**Two units that would both pass every AD literally:**

- **Unit A (acoustic-filter engineer):** Adds the handcrafted-feature columns (pitch, energy, rate, pauses) directly onto `TimelineSegment` — one set of values per segment, matching the `segment_id`-join language and enabling per-segment evidence drill-down (FR-13).
- **Unit B (schema/storage engineer building `ANALYSIS_RESULT`):** Persists the handcrafted-feature set as a single JSON blob column on `ANALYSIS_RESULT` — one set of values for the whole Call — reading AD-3's "for every Call" (not "for every segment") as the binding cardinality, and treating `ANALYSIS_RESULT` as the natural home for "the SER stage's... required evidence" since AD-3 binds to FR-13 the same way AD-12's evidence rules bind to `ANALYSIS_RESULT`.

Both satisfy AD-3's literal text ("mandatory... for every Call"). They are structurally incompatible: Unit A's UI can render a per-segment acoustic-metric bar; Unit B's cannot (only one Call-wide number exists), and the `segment_id` join the Consistency Conventions promises for "acoustic-evidence record" has no target in Unit B's schema at all.

**What would close it:** Name the acoustic-evidence record as a fifth first-class entity in the Core-entity sketch (e.g., `ACOUSTIC_EVIDENCE`), state its cardinality explicitly (one row per `TimelineSegment`, keyed by `segment_id` — matching AD-11's per-chunk analysis and the timeline drill-down use case), and add it to the ER diagram's relationships.

---

## Finding 3 [HIGH] — TranscriptTurn's own segmentation boundary is never bound to the VAD/TimelineSegment boundary set

**The ambiguity:** AD-11 fixes VAD-detected boundaries as "the single source of chunk boundaries" and forbids "a second, independently-computed **timeline**-boundary set." But `TranscriptTurn` is not a timeline artifact by name — it's the transcript stage's own unit, naturally produced by diarization/STT segmentation (a speaker-turn boundary set derived from pyannote/WhisperX, which has no reason to coincide with VAD chunk edges). AD-11's prohibition, read literally, only binds the *TimelineSegment* boundary set to VAD — it says nothing about whether `TranscriptTurn` start/end times must themselves be clipped/aligned to VAD boundaries, or may run on their own independent (diarization-native) segmentation that merely gets tagged with a `segment_id` after the fact.

**Two units that would both pass every AD literally:**

- **Unit A (transcript-stage engineer):** Emits `TranscriptTurn` rows on diarization's natural turn boundaries (a turn = one continuous speaker utterance, however long), then assigns each turn's `segment_id` to whichever VAD segment its midpoint falls in — a genuine many-`TranscriptTurn`-to-one-`TimelineSegment` join, exactly as the Consistency Conventions' "TranscriptTurn(s)" plural implies.
- **Unit B (fusion/storage engineer, aiming for a clean drill-down join):** Requires the transcript stage to re-clip/split any diarized turn that crosses a VAD boundary, so every `TranscriptTurn` fits inside exactly one `TimelineSegment` with a strict 1:1-per-segment relationship — reading AD-11's "single source of chunk boundaries" as binding to *all* segmentation in the system, not just the timeline.

Unit A ships turns that can span multiple `segment_id`s (violating Unit B's assumed invariant that a `TranscriptTurn.segment_id` is a single scalar FK, which most naive schemas would encode as exactly that). Unit B ships artificially fragmented turns that break natural utterance boundaries fusion may want for text-sentiment context. Neither implementer can tell from the spine which is "wrong."

**What would close it:** Extend AD-11 (or add a new AD) to state explicitly whether `TranscriptTurn.segment_id` is a single scalar FK (requiring turns to be clipped to VAD boundaries) or a set/join-table relationship (turns may span multiple segments), and which stage owns the clipping/mapping logic.

---

## Finding 4 [HIGH] — Two boxes with DB write access, one status field, no assigned writer

**The ambiguity:** The container diagram (both AD-7's mermaid and the Structural Seed's) draws **two** arrows into `DB`: `API --> DB` and `ML --> DB`. AD-12 says processing status "live[s] in SQLite." AD-13 says status transitions are "driven only by the RQ/Redis job lifecycle... not by ad hoc state written from the web process" — which rules out the web process inventing status independently, but does not say which process **executes the SQL write** that persists a transition, nor whether there is exactly one writer.

**Two units that would both pass every AD literally:**

- **Unit A (web-api engineer):** Registers RQ callback/exception handlers *inside the web-api process* (a common RQ pattern — `Callback` classes or a listener) that observe job lifecycle events and write `status` to the Call row. Justification: "driven by the queue/worker lifecycle" describes the *trigger source* (RQ events), not which process holds the DB connection; web-api already owns `API --> DB`.
- **Unit B (ML-service engineer):** Writes `status` directly from within the RQ job function itself (`ml-service` process), at job start (`processing`) and completion/exception (`complete`/`failed`), since the job function is literally where "queue/worker lifecycle" transitions happen and `ML --> DB` is a drawn arrow.

If both are built independently (each is a perfectly reasonable, literal reading of AD-13), you get two processes racing to write the same status column — e.g., web-api's listener marking `processing` at dequeue while the ML job hasn't started model load yet, or both writing `complete` from different code paths with different completion-detection logic (one from RQ's own success signal, one from the pipeline's own final calibration step finishing) — producing inconsistent status under retry/failure edge cases neither engineer tested against the other's assumption.

**What would close it:** Tighten AD-13 to name exactly one writer of the `status` column (e.g., "only the ML/audio service's job wrapper writes Call.status; the web/API layer only reads it") and state explicitly that `API --> DB` in the container diagram is read/results-only for the Call-status field, never a write path for it.

---

## Finding 5 [MEDIUM] — Delete-vs-in-flight-job race is unaddressed by either AD-12 or AD-13

**The ambiguity:** AD-12 requires delete to be atomic and "complete[s] immediately" (DB rows + filesystem artifacts together). AD-13 implies the ML worker owns a Call's processing artifacts for the duration of its job (it writes intermediates to the session-scoped FS and to SQLite mid-pipeline). Neither AD states what happens if a delete request for a Call arrives while an RQ job for that same Call is still running.

**Two units that would both pass every AD literally:**

- **Unit A (web-api delete-endpoint engineer):** Implements delete exactly as written — "immediate and unrecoverable" — by purging the Call's SQLite rows and FS directory synchronously on request, with no check for an in-flight RQ job, because AD-12 never mentions job state as a precondition.
- **Unit B (ML-worker engineer):** Assumes, per AD-7/AD-13's framing of the ML service as the exclusive owner of pipeline execution once a job is dequeued, that a Call's rows/FS directory are stable for the job's lifetime and writes intermediate artifacts (new `TimelineSegment`/`TranscriptTurn` rows, FS files) without re-checking the Call still exists.

Combined: a mid-job delete under Unit A silently orphans Unit B's in-flight writes (FK writes against a deleted Call, or files written into a directory Unit A already removed), and neither engineer's code path detects or handles the other's assumption — a state-mutation conflict the "single delete action" language never anticipates.

**What would close it:** A new rule (attached to AD-12 or AD-13) stating whether delete must first cancel/await any in-flight job for that Call before purging (and how that's signaled to the ML worker), or conversely that the ML worker must re-validate the Call still exists before each write and abort/no-op cleanly if not.

---

## Finding 6 [MEDIUM] — No one is assigned to detect a "quiet" (non-exception) acoustic failure

**The ambiguity:** AD-1's rule is airtight against a *deliberate* skip, but silent on detection: "if it fails or is skipped, the Call's processing status is `failed`." Whether "fails" means "the acoustic stage's code raised/RQ recorded a job failure" or "the acoustic stage produced no usable/degraded output despite exiting cleanly" is unstated, and no AD assigns responsibility for catching the second case.

**Two units that would both pass every AD literally:**

- **Unit A (acoustic-filter engineer):** Treats "fails" as synonymous with "raises an exception." If the SER model runs but returns a degenerate/empty result (e.g., model produces near-uniform low-confidence output on a corrupted chunk) without erroring, the function returns normally — RQ reports the job as successful, so per AD-13 the Call status becomes `complete`.
- **Unit B (fusion-filter engineer):** Assumes, per AD-1's "no acoustic-skip fallback path" language, that *someone downstream* validates the acoustic signal is real before treating a Call as viable — but builds this check into fusion's *disagreement* logic (AD-8) rather than as an explicit "is acoustic output valid at all" gate, so a degenerate-but-present acoustic value still flows through fusion as if legitimate (it has a value and a confidence number, just a meaningless one).

Neither engineer implements the "quiet failure → status=failed" enforcement the spine's prose clearly wants (AD-1's whole point is that a degraded result must never be "indistinguishable from a real voice-first analysis"), because the spine never assigns which stage owns detecting a clean-exit-but-invalid-output condition.

**What would close it:** Tighten AD-1 to name the validation gate explicitly — e.g., "the acoustic filter must itself raise a job failure (not merely return) whenever its output fails a defined minimum-validity check (e.g., non-null feature vector, non-degenerate confidence distribution); fusion must never be the first place this is checked."

---

## Finding 7 [LOW/MEDIUM] — Speaker-attribution label semantics differ across the stereo/mono fork by construction

**The ambiguity:** AD-2 fixes *strategy* (stereo → channel-index, mono → diarization) but not the resulting label's semantic shape. Stereo channel-index naturally yields a positional label ("channel 0"/"channel 1"); mono diarization naturally yields an arbitrary cluster label ("SPEAKER_00"/"SPEAKER_01" from pyannote). Nothing requires these to resolve to a common semantic space (e.g., "Agent"/"Customer").

**Two units that would both pass every AD literally:**

- **Unit A (stereo/ingest engineer):** Stores `speaker` as a raw positional token (`"channel_0"`, `"channel_1"`), uniform and simple, satisfying AD-2's "assigned deterministically by channel index."
- **Unit B (mono/diarization engineer):** Stores `speaker` as a semantic role guess (`"Agent"`, `"Customer"`) derived from a heuristic (e.g., "first speaker after a greeting-pattern match = Agent"), because FR-16 is about "speaker attribution" for a call-center product where role, not position, is the useful signal.

A Call processed via the stereo path and one via the mono path would carry differently-typed values in the same `speaker` field — breaking any UI or downstream logic (filter-by-agent, cross-call analytics) that assumes one consistent label space across all Calls, and AD-2 gives no basis to say either is wrong.

**What would close it:** Add to AD-2 (or a new AD) the exact label vocabulary `speaker` must take across both paths — either "purely positional in both paths, role-mapping is a UI-layer concern" or "both paths must resolve to a fixed role enum, with the mono path's resolution heuristic specified or deferred explicitly as an open decision."

---

## Summary Table

| # | Severity | Two colliding units | Root cause |
| --- | --- | --- | --- |
| 1 | CRITICAL | Call-level-only fusion vs per-segment fusion | Sentiment/Emotion storage granularity undefined; AD-8/AD-10/AD-15/ER diagram pull in different directions |
| 2 | CRITICAL | Per-segment acoustic-feature columns vs one Call-level JSON blob | "Acoustic-evidence record" named in prose, absent from Core-entity sketch |
| 3 | HIGH | Turn-native (many-to-one) `segment_id` vs boundary-clipped (1:1) `TranscriptTurn` | AD-11 binds VAD boundaries to the "timeline," not explicitly to `TranscriptTurn`'s own segmentation |
| 4 | HIGH | Web-api RQ-listener writes status vs ML-worker writes status | Both `API-->DB` and `ML-->DB` are drawn; AD-13 never names the single writer |
| 5 | MEDIUM | Immediate unconditional delete vs job assumes exclusive artifact ownership through completion | No AD reconciles delete with an in-flight RQ job for the same Call |
| 6 | MEDIUM | Acoustic stage relies on RQ exception detection vs fusion assumed to gate validity | No AD assigns ownership of detecting a clean-exit-but-degenerate acoustic result |
| 7 | LOW/MEDIUM | Positional speaker labels (stereo) vs role-guessed labels (mono) | AD-2 fixes strategy, not the resulting label's semantic vocabulary |
