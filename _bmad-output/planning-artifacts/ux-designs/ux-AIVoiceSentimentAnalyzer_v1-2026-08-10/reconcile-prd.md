---
title: UX-finalize input reconciliation — PRD vs. UX Spines
generated: 2026-08-10
compares:
  - '{planning_artifacts}/prds/prd-AIVoiceSentimentAnalyzer_v1-2026-08-10/prd.md'
  - '{planning_artifacts}/ux-designs/ux-AIVoiceSentimentAnalyzer_v1-2026-08-10/DESIGN.md'
  - '{planning_artifacts}/ux-designs/ux-AIVoiceSentimentAnalyzer_v1-2026-08-10/EXPERIENCE.md'
---

# PRD → UX Reconciliation

## Method

Checked every FR-1..FR-16, NFR-1..NFR-5, §5 Non-Goals, §10 Constraints (Privacy, Cost/Processing), §11 Known Risks, and UJ-1 against DESIGN.md/EXPERIENCE.md. Full FR/NFR coverage matrix and UJ-1 comparison are clean — no silent omissions found there. FR-1 through FR-16 each map to an explicit surface/state/component (FR-4/FR-5 map implicitly via the always-present two-column transcript/acoustic layout rather than an explicit citation, but the behavioral intent — acoustic signal never optional, always presented distinctly from text — is satisfied). NFR-1/3/4 have explicit, concrete UX rules. UJ-1 is faithfully mirrored (not paraphrased into something different) with consistent elaboration. No Non-Goal items were reintroduced; no dark mode/auth/annotations/cross-call-analytics contradictions found; disagreement/low-confidence treatment (dual-signal panel, split-fill, hatch pattern) genuinely operationalizes the "voice-first vs. evidence tension" risk (§11), not just claims to.

The items below are the exceptions — real gaps or under-specified spots worth closing before build.

## Findings

### 1. Gap: No UI affordance for the PRD's "must be deletable" retention requirement
- **Description:** PRD §10 Constraints › Privacy requires: "Uploaded Calls and their Analysis Results are retained only for the duration of the session/demo use and must be deletable." EXPERIENCE.md correctly captures session-only, non-persistent retention (Key Flows › Resolution: "Nothing about this Call persists beyond the session"), but never specifies a delete/remove/clear action anywhere — not on the Call row, not in State Patterns, not in Interaction Primitives. (Confirmed via full-text search: no occurrence of "delete," "remove," or "clear session" in either file.)
- **Location:** EXPERIENCE.md — Component Patterns › Call row; State Patterns.
- **Suggested fix:** Add an explicit delete/remove affordance (e.g., a per-row remove action on the Call row, and/or a "clear session" control) so "must be deletable" has a concrete UI realization, not just an implicit end-of-session wipe.

### 2. Minor gap: NFR-5 (Evaluation transparency) has no genuine concrete UX rule
- **Description:** NFR-5 requires that any accuracy/performance/reliability claim state what it was measured against (dataset, method, conditions). The only citation of NFR-5 in EXPERIENCE.md is Voice and Tone's "Flag reasons are always stated, never just the flag... consistent with NFR-1 (explainability) and NFR-5 (no unqualified claims)" — but that rule is about explaining *why a segment is flagged*, not about qualifying accuracy/performance claims with their measurement basis. It's a mismatched citation, not a rule that actually satisfies NFR-5. In practice this may be a non-issue since the product doesn't appear to surface any aggregate accuracy/performance figures anywhere — but if that's the intent, EXPERIENCE.md should say so explicitly rather than leave NFR-5 covered only by a tenuous citation.
- **Location:** EXPERIENCE.md — Voice and Tone, line ~40 (flag-reason bullet).
- **Suggested fix:** Either add a real NFR-5 rule (e.g., "if the product ever surfaces an accuracy/performance figure in-app or in docs, it must be paired with what it was measured against") or drop the NFR-5 citation from the flag-reason bullet and note NFR-5 is satisfied by omission (no such claims are surfaced in MVP).

### 3. Ambiguity: "Secondary Signal" summary cell is undefined
- **Description:** EXPERIENCE.md Component Patterns lists the four permanent Summary cells as "Overall Sentiment, Dominant Emotion (+ Confidence), Secondary Signal (when present; otherwise 'None flagged'), Segments Flagged" — but "Secondary Signal" is never defined anywhere in either document (not in DESIGN.md's `summary-cells` component spec either). It's unclear whether this is meant to show the non-dominant modality's reading (tying to SM-2's voice-first check / FR-5's distinctness requirement) or something else (secondary emotion, disagreement flag, etc.). Given it's one of only four fixed top-level readouts, this ambiguity is worth closing before it's built two different ways by design and implementation.
- **Location:** EXPERIENCE.md — Component Patterns › Summary cells; DESIGN.md — `components.summary-cell`.
- **Suggested fix:** Define precisely what data populates "Secondary Signal" and its relationship (if any) to FR-5's acoustic/text distinctness requirement.

### 4. Minor: undefined "exported/copied text" surface referenced once
- **Description:** Voice and Tone's "Never assert certainty" rule lists "exported/copied text" as a surface the rule applies to, but no Export feature or surface is defined anywhere in Information Architecture or Component Patterns, and the PRD neither commits to nor excludes an export capability. Likely just meant as "if an analyst copies text out of the browser, the copied text should still read as evidence-linked," but as written it reads like a stray reference to an undefined feature.
- **Location:** EXPERIENCE.md — Voice and Tone, line 37.
- **Suggested fix:** Clarify the phrase means browser text-selection/copy (no dedicated Export button/surface exists), or remove it if not intended.

## Summary

No contradictions of PRD decisions found (light-mode-only, no auth, no annotations, no cross-call analytics, no AI summary — all correctly respected). No FR is silently unaddressed. UJ-1 is mirrored accurately. The four items above are gaps/ambiguities to close, not scope violations.
