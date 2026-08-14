# Final Validation — epics.md (Step 4)

Runs the workflow's own Step 4 checks (FR coverage, story quality, epic structure, dependency validation) plus the user's originally-scoped extras (full NFR/AD/UX-DR traceability, not just FR).

## 1. Epic / Story List

- **Epic 1: Call Intake & Multimodal Analysis Pipeline** — Stories 1.1–1.9 (backend: upload/validation, async lifecycle + ingest, acoustic analysis, transcript generation, transcript sentiment, fusion, timeline retrieval, confidence/low-confidence flagging, disagreement surfacing)
- **Epic 2: Analysis Dashboard** — Stories 2.1–2.7 (frontend: console foundation + Session Call List, upload/status UI, delete UI, dashboard summary, evidence drill-down, no-certainty language, accessibility/responsive verification)
- **Epic 3: Speaker Attribution** — Stories 3.1–3.4 (stereo channel attribution, mono diarization, failure/uncertainty states, UI wiring)

**17 stories total.**

## 2. FR → Epic/Story Mapping

| FR | Epic/Story | Coverage |
|---|---|---|
| FR-1 | 1.1 (backend), 2.2 (frontend) | Full |
| FR-2 | 1.1, 2.2 | Full |
| FR-3 | 1.2, 2.2 | Full |
| FR-4 | 1.3 | Full |
| FR-5 | 1.3 | Full |
| FR-6 | 1.4 | Full |
| FR-7 | 1.5 | Full |
| FR-8 | 1.6 | Full |
| FR-9 | 1.7 (data), 2.5 (UI) | Full |
| FR-10 | 1.8 | Full |
| FR-11 | 1.9 (data), 2.5 (UI) | Full |
| FR-12 | 2.4 | Full |
| FR-13 | 2.5 | Full |
| FR-14 | 2.5 | Full |
| FR-15 | 2.6 | Full |
| FR-16 | 3.1, 3.2, 3.3, 3.4 | Full |

**All 16 FRs covered, each traceable to at least one story with testable ACs.**

## 3. NFR → Story Mapping

| NFR | Story | Coverage |
|---|---|---|
| NFR-1 (Explainability) | 1.3 (evidence persisted), 2.4/2.5 (evidence reachable) | Full |
| NFR-2 (Confidence honesty) | 1.8, 2.6 | Full |
| NFR-3 (Terminology discipline) | 1.6 (data-model), 2.6 (UI copy) | Full |
| NFR-4 (Human-in-the-loop) | 2.6 | Full |
| NFR-5 (Evaluation transparency) | 1.3, 1.6 | Full |

## 4. Architecture AD → Story Mapping

| AD | Story | Coverage |
|---|---|---|
| AD-1 | 1.2, 1.3, 1.6 | Full — sanity floor, mandatory-fail, transcript-only-fallback-forbidden, single-modality flag all explicit |
| AD-2 | 1.2, 3.1, 3.2 | Full |
| AD-3 | 1.3 | Full |
| AD-4 | 1.3 | Full |
| AD-5 | 1.4 | Full |
| AD-6 | 3.2, 3.3 | Full |
| AD-7 | 1.2 | Full |
| AD-8 | 1.6, 1.9 | Full |
| AD-9 | 1.3, 1.5, 1.8 | Full |
| AD-10 | 1.6, 1.8, 3.3 | Full |
| AD-11 | 1.2, 1.7 | Full |
| AD-12 | 1.2 (backend), 2.3 (UI) | Full |
| AD-13 | 1.2 | Full |
| AD-14 | 1.3, 1.5 | Full |
| AD-15 | 1.6 | Full |
| AD-16 | 1.8, 2.4, 2.5 | Full — closed 2026-08-11 (see §11) |
| AD-17 | 1.3, 1.6 | Full |
| AD-18 | 1.1, 1.2, 2.1 | Full |
| AD-19 | 1.5 | Full |
| AD-20 | 1.1 | Full |
| AD-21 | 1.1–1.9 (each story's own unit-test AC) | Full |

**21 of 21 ADs explicitly cited in at least one story.** (AD-16 closed 2026-08-11 — see §11.)

## 5. UX-DR → Story Mapping

**All 21 UX-DRs explicitly cited by tag in a story's Traceability line.** (UX-DR21 closed 2026-08-11 — see §11.)

## 6. Coverage Gaps

None remaining. Gap 1 (AD-16) and Gap 2 (UX-DR21) — both citation-only labeling gaps, never functional gaps — were closed on 2026-08-11 by adding explicit tags to the stories that already satisfied them; see §11 for the record.

No other gaps found. No FR, NFR, or Additional Requirement is uncovered. No story invents a requirement absent from PRD/Architecture/UX (verified per Story Quality Validation below).

## 7. Story Quality Validation

- **Single dev agent completable:** yes for all 17. Stories 1.6 (Fusion) and 2.5 (Timeline/Evidence Drill-Down) carry the most ACs — largest but still one cohesive capability each; worth knowing they're the two densest stories if further splitting is ever wanted at actual dev-story time, not a defect now.
- **Clear, testable ACs:** yes, Given/When/Then throughout.
- **Reference specific FRs/ADs/UX-DRs:** yes, explicit Traceability lines (Epic 2/3) and inline citations (Epic 1).
- **No forward dependencies:** verified — 1.1→1.9, 2.1→2.7 are strictly sequential with no story requiring a later one; 3.1/3.2 are parallel (mutually exclusive per Call), 3.3 depends only on 3.2 (earlier), 3.4 depends only on 3.1–3.3 (all earlier).
- **Tables/entities created only when needed:** yes — `Call` in 1.1, `TimelineSegment` in 1.2, `ACOUSTIC_EVIDENCE` in 1.3, `TranscriptTurn` in 1.4, `ANALYSIS_RESULT` in 1.6 — no upfront full-schema story.

## 8. Epic Structure Validation

- **User-value organization, not technical layers:** confirmed per the elicitation record — Epic 1 delivers a real, API-testable multimodal Analysis Result; Epic 2 delivers the human-usable console; Epic 3 delivers an additive, optional enrichment.
- **File Churn Check:** Epic 1 and Epic 3 do both touch `ingest/`/`transcript/` — flagged and consciously accepted during epic design (Epic 3 kept separate per explicit user decision, framed as genuine incremental scope, not repeated modification of the same logic).
- **Dependency direction:** Epic 2 depends only on Epic 1's API (no reverse dependency). Epic 3 depends on Epic 1 and Epic 2 but as optional data enrichment, not a runtime dependency — Epic 2 is fully functional with zero Epic 3 stories built (explicitly re-confirmed during Epic 2 design).

## 9. Critical Decisions Flagged for Review

These are the decisions with the highest blast radius if wrong — worth a final human sanity-check before this backlog is handed to implementation:

1. **AD-1's absolute rule (Story 1.3): acoustic failure always fails the Call; transcript failure never does.** This is the single most load-bearing rule in the whole backlog — it's what makes "voice-first" real rather than aspirational. If any future implementation quietly softens this (e.g., "retry with transcript-only as a temporary workaround"), the product's core differentiator silently erodes exactly as PRD §11 warns.
2. **Story 1.6's fusion-gating rule: fusion runs whenever acoustic is valid, regardless of transcript.** This was explicitly re-derived this session (originally implied, then made the primary framing per your correction) — worth a last look since it inverts the "both signals required" assumption a less careful reading of FR-8 might suggest.
3. **AD-8/AD-15: fusion must stay rule-based (never a trained model) and Sentiment/Emotion must stay separate fields at generation time.** Both are easy to violate under normal engineering pressure (a trained fusion model or a merged field are both simpler to build) without breaking any test that only checks FR-level behavior — these are exactly the kind of invariant an Architecture spine exists to protect, and now exist as explicit story-level ACs (Story 1.6) that a future implementer can't miss.
4. **Epic 1/Epic 3 file overlap (`ingest/`, `transcript/`) — accepted, not eliminated.** If Epic 3 is ever deprioritized or dropped post-MVP, Epic 1's ingest/transcript modules remain fully functional on their own (channel detection already produces a usable, if generic, result without diarization) — worth confirming this is still the intended fallback posture.
5. **Gaps 1 and 2 (AD-16, UX-DR21 citation-only gaps) — closed 2026-08-11, see §11.** Retained here as a record that they were caught and deliberately closed, not silently dropped.

## 10. Recommendation

Backlog is implementation-ready. All 21 ADs and all 21 UX-DRs are now explicitly, traceably cited in the stories that satisfy them; no open coverage gaps remain.

## 11. Gap Closure Record (2026-08-11)

Per user instruction, Gaps 1 and 2 were closed as a **traceability/labeling correction only** — no acceptance criterion, requirement, or scope was added, changed, or reworded.

- **AD-16** added to: Story 1.8's existing FR-10 AC citation (now `FR-10, AD-16`) and to Stories 2.4 and 2.5's Traceability lines, each with a short parenthetical tying the tag to the AC content that already satisfied it (Confidence always co-present; evidence-linked drill-down).
- **UX-DR21** added to: Story 2.1's and Story 2.4's Traceability lines, each with a short parenthetical tying the tag to the existing AC content (token-sourced-only rendering; WCAG AA pairing).

**Targeted verification:**
- AD-16 explicit and traceable — yes, in Stories 1.8, 2.4, 2.5.
- UX-DR21 explicit and traceable — yes, in Stories 2.1, 2.4.
- FR-1..16 coverage unchanged — confirmed; no FR tag was added, removed, or altered (FR-10, FR-12, FR-9, FR-11, FR-13, FR-14 citations verified byte-for-byte identical apart from the appended AD-16 tag on the FR-10 line).
- No new requirement or scope introduced — confirmed; all edits were additive tags inside existing Traceability lines / existing citation parentheses, zero AC text rewritten or added.
