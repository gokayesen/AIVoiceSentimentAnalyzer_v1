# Requirements Coverage & Consistency Review — epics.md (pre-Epic-design gate)

**Scope note:** This review runs against `epics.md` as it exists after Step 1 (Requirements Extraction) of `bmad-create-epics-and-stories`. **No epics or stories have been created yet** (Step 2 "Design Epics" and Step 3 "Create Stories" have not run). This means:

- Checks 1, 2, 3, 4, 5, 6, 7, 8 (requested items) — evaluated below, against the Requirements Inventory itself.
- Checks 9 and 10 (Epic/Story-level traceability, reverse invented-requirement check) — **cannot be performed yet**; there is nothing to trace to or check against. These are exactly what the workflow's own **Step 4: Final Validation** is built to do once Step 2/3 produce content. Recommend re-running this same rigor at that point.

The findings below are about the Requirements Inventory's fidelity to its sources — fixing them now matters because Step 2 (Design Epics) will draft epics primarily from this inventory, not by re-reading all 21 ADs from scratch. A gap here becomes a silently-dropped epic/story later.

---

## Coverage Table

### Functional Requirements (PRD §4)

| Requirement | Source | Covered by Epic/Story | Status | Gap |
|---|---|---|---|---|
| FR-1 | PRD §4.1 | Pending (Step 2/3) | Fully Captured | — |
| FR-2 | PRD §4.1 | Pending | Fully Captured | — |
| FR-3 | PRD §4.1 | Pending | Fully Captured | — |
| FR-4 | PRD §4.2 | Pending | Fully Captured | — |
| FR-5 | PRD §4.2 | Pending | Fully Captured | — |
| FR-6 | PRD §4.3 | Pending | Fully Captured | — |
| FR-7 | PRD §4.3 | Pending | Fully Captured | — |
| FR-8 | PRD §4.4 | Pending | Fully Captured | — |
| FR-9 | PRD §4.4 | Pending | Minor gap | "not a single aggregate score presented as if it were a timeline" phrasing dropped; low severity, implied by "multi-point" |
| FR-10 | PRD §4.4 | Pending | Minor gap | PRD's explicit "does not itself claim calibration" disclaimer not restated inline; mitigated by NFR-2 being adjacent in the same inventory, but a story-writer reading FR-10 alone could over-claim |
| FR-11 | PRD §4.4 | Pending | Fully Captured | — |
| FR-12 | PRD §4.5 | Pending | Fully Captured (watch item) | PRD's explicit "Out of Scope: AI-generated summary / important moments" note was dropped during extraction (not a requirement, so correctly excluded — but re-verify in Step 2 that no epic invents this; also watch for "Summary cells" (UX-DR3, the 4-cell row) being confused with "AI-generated summary" — different concepts, same word) |
| FR-13 | PRD §4.5 | Pending | Fully Captured | — |
| FR-14 | PRD §4.5 | Pending | Fully Captured | — |
| FR-15 | PRD §4.5 | Pending | Fully Captured | — |
| FR-16 | PRD §4.6 | Pending | Fully Captured | — |

**Result: all 16 FRs represented with no meaning loss that changes what must be built.** Two minor phrasing losses (FR-9, FR-10) noted for awareness, not blocking.

### Non-Functional Requirements (PRD §9)

| Requirement | Source | Covered by Epic/Story | Status | Gap |
|---|---|---|---|---|
| NFR-1 | PRD §9 | Pending | Fully Captured | — |
| NFR-2 | PRD §9 | Pending | Fully Captured | Rationale ("Technical Research found no in-domain evaluation data") trimmed — correct, rationale belongs upstream not in epics.md |
| NFR-3 | PRD §9 | Pending | Fully Captured | — |
| NFR-4 | PRD §9 | Pending | Fully Captured | — |
| NFR-5 | PRD §9 | Pending | Fully Captured | — |

**Result: all 5 NFRs fully preserved.**

### Architecture Decisions (ARCHITECTURE-SPINE.md) — the core ask

| AD | Binds | Covered by Epic/Story | Status | Gap |
|---|---|---|---|---|
| AD-1 (voice-first mandatory) | FR-4, FR-5, FR-7 | Pending | **Partially Captured** | The acoustic-mandatory / never-bypassed core is in FR-4. But two load-bearing sub-rules are absent from Additional Requirements: (a) the **sanity-floor mechanism** — the acoustic filter must itself raise a job failure when its own calibrated confidence falls below a defined floor, not silently pass a degenerate result downstream; (b) the **single-modality flag** requirement when transcript fails (shared with AD-8 rule 4, see below) |
| AD-2 (channel detection / speaker attribution) | FR-16 | Pending | Fully Captured | — |
| AD-3 (SER: embedding model + mandatory handcrafted-feature layer) | FR-5, FR-13 | Pending | **Missing** | Only the resulting `ACOUSTIC_EVIDENCE` entity is captured (via the data-model bullet). The embedding-model requirement (Wav2Vec2/HuBERT/WavLM-family), the license constraint (librosa/torchaudio only — never openSMILE/eGeMAPS or Praat/parselmouth), and "handcrafted features are mandatory, never optional/debug-only" are not stated anywhere |
| AD-4 (Emotion taxonomy) | FR-5, FR-9 | Pending | **Missing** | The coarse CREMA-D-style category set and its fixed lookup table to the 4 Sentiment polarity colors is not stated anywhere in Additional Requirements |
| AD-5 (STT: faster-whisper) | FR-4, FR-13, NFR-1 | Pending | Partially Captured | faster-whisper is pinned in the Stack list, but the word-level-timestamp requirement (load-bearing for evidence-linkage) and "no alternate STT engine substitution" rule aren't stated as requirements |
| AD-6 (diarization: WhisperX + pyannote 4.0, mono only) | FR-16, AD-2 | Pending | Partially Captured | Stack pinned correctly. Paid-tier (precision-2) prohibition not explicit (low severity — implied by pinning Community-1). The two-distinct-failure-states rule (Call-level "unavailable" vs. per-turn "uncertain") is functionally covered via UX-DR13, but not independently stated as a *data-model* requirement — it currently only exists because the UX side needs it, which is backwards |
| AD-7 (consolidated ML/audio service boundary) | all pipeline FRs, FR-3 | Pending | Fully Captured | — |
| AD-8 (fusion: rule-based, confidence-weighted, disagreement flag) | FR-8, FR-11 | Pending | **Partially Captured** | The `ANALYSIS_RESULT`-as-deterministic-aggregate nuance is captured. But the "rule-based, confidence-weighted, **never a trained black-box model**" mechanism choice is not stated as its own requirement — nothing in epics.md today would catch a future story substituting a trained fusion model. Also see AD-1 above: the single-modality-flag rule (AD-8 rule 4) is missing |
| AD-9 (temperature scaling only, no MC Dropout) | FR-10, FR-14 | Pending | Fully Captured | — |
| AD-10 (two confidence axes never conflated) | FR-10, FR-14, FR-16 | Pending | Fully Captured | — |
| AD-11 (chunking/timeline unification) | FR-9 | Pending | Partially Captured | VAD-boundary-reuse and the `TranscriptTurn`↔`TimelineSegment` many-to-many relationship are captured. "Rolling context must be carried across chunk boundaries so per-chunk analysis is not artificially discontinuous" is missing |
| AD-12 (storage boundary) | FR-3, FR-12, FR-13, §10 | Pending | **Partially Captured** | Dual-store delete + in-flight-job-cancel-before-purge captured well. But the explicit framing "this persistence exists for dev/demo resilience only — **not a product promise of durable storage**" was dropped — without it, "SQLite" reads as ordinary durable storage, risking over-building persistence against PRD §10's minimal-retention posture. (Demo-audio-must-be-synthetic/consented is a process constraint outside epics.md's scope — correctly not carried, flagged for awareness only) |
| AD-13 (RQ + Redis async orchestration) | FR-3 | Pending | Fully Captured | — |
| AD-14 (local-only inference) | FR-4, FR-5 | Pending | Fully Captured | — |
| AD-15 (Sentiment/Emotion distinct fields end-to-end) | FR-5, NFR-3 | Pending | **Missing** | This is a data-model/code-level invariant ("no code may merge them into one composite field **at generation time**") distinct from NFR-3 (which governs UI/API *terminology*, not internal field separation). A story could satisfy NFR-3's labeling rule while still violating AD-15's field-separation rule internally. Not stated anywhere in epics.md |
| AD-16 (human-in-the-loop, no autonomous verdicts) | FR-13, FR-14, FR-15, NFR-4 | Pending | Partially Captured | Substantially covered via the FR-15 + NFR-1 + NFR-4 composite, but AD-16's API-contract-level specificity ("no API response may show a value without confidence+evidence linkage") is thinner than the AD's own language — worth an explicit bullet since it constrains the API layer, not just the UI |
| AD-17 (evaluation strategy) | NFR-2, NFR-5 | Pending | Fully Captured | — |
| AD-18 (deployment envelope) | all components | Pending | Fully Captured | — |
| AD-19 (text-sentiment: fine-tuned/pretrained transformer) | FR-7 | Pending | **Missing** | Only cited by AD number in a parenthetical, never stated as content. This is the single mechanism preventing the exact anti-pattern the Product Brief names ("audio → STT → LLM → sentiment," acoustic features as decoration) — the highest-value gap to close before Step 2, since a story-writer with no other guidance could reach for an LLM-based sentiment call and nothing here would stop them |
| AD-20 (audio ingest constraints) | FR-1, FR-2 | Pending | Fully Captured | — |
| AD-21 (CI/testing/logging baseline) | all components | Pending | Fully Captured | — |

**Result: 10 of 21 ADs fully captured, 7 partially captured, 4 missing outright** (AD-3, AD-4, AD-15, AD-19). No AD was silently dropped in the sense of "never mentioned" — all 21 are at least cited by number somewhere — but citation is not the same as the binding rule surviving into an actionable requirement, and that's the gap.

---

## Adversarial checks (requested items 4–8)

**4. Voice-first constraint:**
- Acoustic mandatory for every Call — ✅ FR-4.
- Acoustic stage never bypassed under any condition — ✅ FR-4 ("never skipped, bypassed, or replaced... including in a degraded state").
- Transcript failure → acoustic-only possible — ✅ FR-4 ("produces output independently of whether Transcript Analysis succeeds").
- Acoustic failure → transcript-only fallback forbidden — ⚠️ Implied by FR-4's "never... replaced by transcript-only," but AD-1's explicit consequence ("Call's processing status is `failed` — there is no acoustic-skip fallback path") isn't spelled out as a requirement.
- Single-modality result explicitly marked — ❌ **Missing.** Neither AD-1's nor AD-8's single-modality-flag requirement made it into Additional Requirements. This is the one adversarial-check item with a real, unambiguous gap — recommend fixing before Step 2.

**5. Confidence/uncertainty:** No MC Dropout in MVP ✅, temperature scaling preserved ✅, no calibration guarantee claimed ✅ (NFR-2), low-confidence UX behavior matches (FR-10/FR-14/UX-DR12/UX-DR16 all consistent) ✅. **No gaps found.**

**6. Speaker attribution best-effort + unavailable/uncertain states:** FR-16 states best-effort ✅; stereo/mono path split captured ✅; UX-DR13 explicitly and correctly distinguishes whole-Call "unavailable" from per-turn "uncertain" ✅. Minor: the *data-model*-side requirement to represent both states independently isn't stated except as inferred backward from the UX requirement (see AD-6 row above) — low severity, functionally covered.

**7. Disagreement surfacing chain (FR → Architecture → UX):** FR-11 ✅ strong. UX side is thoroughly covered (UX-DR2, UX-DR4, UX-DR5, UX-DR12) ✅ strong. The Architecture mid-link is thin — AD-8's disagreement-flag mechanism and its "confidence floor" trigger condition aren't independently stated (same finding as the AD-8 row above, not a new issue). Story-level link: pending Step 2/3.

**8. Deferred/non-goal leakage check:**
- Turkish — ✅ correctly excluded (FR-6 states English-only; nothing elsewhere reintroduces it).
- AI summary / important moments — ✅ correctly excluded from requirements; naming-collision risk with "Summary cells" flagged above as a Step-2 watch-item, not a current defect.
- Auth/accounts — ✅ correctly excluded (UX-DR20 explicitly states no login/account UI).
- Call-level "reviewed" state tracking — ✅ correctly excluded, not mentioned anywhere.
- Persistent retention — ⚠️ **Partial leak risk.** The "not a durable storage promise, dev/demo-resilience only" framing from AD-12 was dropped (see AD-12 row above). Without it, nothing in epics.md currently stops a story from building durable, cross-session persistence, which would contradict PRD §10.

---

## Findings summary

### Missing requirements
1. AD-1's acoustic sanity-floor-must-fail-job mechanism.
2. AD-1/AD-8's single-modality-flag requirement (transcript-unavailable state must be explicitly marked, never presented as an ordinary fused result) — **the one clear gap in the voice-first adversarial check.**
3. AD-3's embedding-model requirement + license constraint (librosa/torchaudio only) + "handcrafted features mandatory, never debug-only."
4. AD-4's Emotion taxonomy (coarse category set + fixed lookup table to polarity colors).
5. AD-8's "rule-based, confidence-weighted, never a trained black-box model" mechanism constraint.
6. AD-11's rolling-context-across-chunk-boundaries requirement.
7. AD-12's "not a durable-storage promise" framing (retention-scope risk).
8. AD-15's Sentiment/Emotion field-separation-at-generation-time invariant (distinct from NFR-3's terminology rule).
9. AD-19's text-sentiment classifier constraint (small transformer, never a general LLM, never a cloud API) — **highest-value gap**, directly guards against the Product Brief's named anti-pattern.

### Misrepresented requirements
None found. Every requirement currently in epics.md accurately reflects its source — all issues found are omissions or under-specification, not incorrect statements.

### Over-scoped requirements
None found in the current Requirements Inventory. (One forward-looking watch-item: "Summary cells" vs. "AI-generated summary" naming collision, see FR-12 row — not a current defect, worth a sanity check once Step 2 drafts the Dashboard epic.)

### Invented requirements
None found — cannot be fully assessed until Step 2/3 exist (item 10), but nothing in the current inventory traces to anything outside PRD/Architecture/UX; every bullet cites its source.

### Traceability gaps
- Items 9 and 10 (Epic/Story-level traceability, reverse invented-requirement check) are **not yet checkable** — Step 2 (Design Epics) and Step 3 (Create Stories) haven't run. Re-run this same review rigor as part of (or alongside) the workflow's own Step 4: Final Validation once stories exist.
- The 9 missing/partial items above are Architecture→Requirements-Inventory traceability gaps: if not fixed now, they're unlikely to surface as their own story in Step 2, since Step 2 will draft epics from this inventory rather than re-deriving all 21 ADs from the spine directly.

---

## Recommendation

Before proceeding to Step 2 (Design Epics), add explicit Additional Requirements bullets to `epics.md` for the 9 missing items above. All are small, targeted additions — this is a fix to the extraction, not a re-scoping of the product. Once added, re-confirm the inventory, then proceed to epic design.

## Resolution (2026-08-11)

Applied as Architecture-coverage corrections to `epics.md`'s Additional Requirements section — no FR/NFR text changed, no new product capability introduced, no new technical decision made beyond what `ARCHITECTURE-SPINE.md` already states. Seven items were fixed exactly as scoped by the user:

- AD-1 / AD-8 rule 4 — voice-first failure handling (sanity-floor-triggers-failed, single-modality flag) now stated explicitly.
- AD-19 — text-sentiment transformer-classifier constraint (no general LLM / cloud LLM) now stated explicitly.
- AD-3 — SER embedding-model family + license constraint + mandatory handcrafted-feature layer now stated explicitly.
- AD-4 — Emotion taxonomy + fixed polarity lookup table now stated explicitly.
- AD-8 (mechanism) — fusion is rule-based, never a trained black-box model, now stated explicitly.
- AD-15 — Sentiment/Emotion field separation at the data-model level (distinct from NFR-3's UI-terminology rule) now stated explicitly.
- AD-12 — "not a durable-storage promise" framing restored, closing the retention-scope leak risk.

For the "other two" partial gaps, judgment was applied rather than fixing all four remaining partials (AD-5, AD-6, AD-11, AD-16) to avoid padding low-severity items:

- **Fixed:** AD-5 (STT word-level-timestamp requirement + no-engine-substitution) and AD-11 (rolling context across chunk boundaries) — both are real, load-bearing technical requirements with no existing coverage elsewhere in the inventory.
- **Left as-is:** AD-6's two-distinct-failure-states requirement was judged already functionally covered via UX-DR13 (which independently forces both states to exist for the UI to render them), and AD-16's API-contract specificity was judged already substantially covered via the FR-15 + NFR-1 + NFR-4 composite. Flagging this choice explicitly — if the intent was these two instead of AD-5/AD-11, say so and they'll be added the same way.

All 21 ADs are now either Fully Captured or explicitly, individually stated as a requirement in `epics.md`. Proceeding to Step 2 (Design Epics).
