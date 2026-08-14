---
title: "Reconciliation: PRD vs. Product Brief"
created: 2026-08-10
---

# Reconciliation Report: PRD vs. Product Brief (Input Fidelity Check)

Scope: checks whether `prd.md` faithfully carries forward everything load-bearing from `brief.md` and `addendum.md`. Not a quality review of the PRD itself.

## Gaps Found

### 1. Guiding Principle #4 ("deliberate technical depth / portfolio principle") is dropped entirely
The Brief names four *non-negotiable* Guiding Principles that "carry forward into every downstream artifact (PRD, UX, Architecture)." GP1 (voice-first), GP2 (explainability/confidence), and GP3 (human-in-the-loop) are all clearly realized in the PRD (§4.2/NFR-1..2, §10 NFR-1/2/5, §10 NFR-4). GP4 — that audio processing, SER, fusion, STT, NLP, and confidence handling should each show up meaningfully "as a portfolio project, not a call-center SaaS product" — has no counterpart anywhere in the PRD. The word "portfolio" appears only incidentally (§5 "aggregate/portfolio-level reporting," §11 "portfolio-scale project" as a cost constraint), never as the stated *purpose* of the project.
**Suggested fix:** Add a short line to §0 Document Purpose or §1 Vision acknowledging the project's dual goal (serving the analyst persona genuinely *and* deliberately demonstrating technical depth), so downstream UX/Architecture readers don't lose the "why" behind decisions like FR-4's insistence on acoustic analysis as a mandatory, non-skippable stage.

### 2. Brief's portfolio-demonstration Success Criterion is missing from PRD Success Metrics
The Brief's Success Criteria (which the PRD's §7 is meant to operationalize) includes: "The finished project can meaningfully demonstrate, in a portfolio/interview context, each of: audio processing, acoustic feature engineering, speech-to-text integration, NLP sentiment analysis, multimodal fusion design, and confidence/uncertainty handling." PRD §7 (SM-1 through SM-5, SM-C1/C2) covers functional completion, voice-first balance, confidence presence, plausibility, and explainability reachability — but never states the portfolio-demonstration criterion, even as a secondary metric. This is a direct, uncarried Success Criteria item (same root cause as Gap 1).
**Suggested fix:** Add a secondary success metric (e.g., "SM-6: Each of the six named technical components is identifiable and independently inspectable in the finished system") to §7, or explicitly note in §0/§9 that this criterion was consciously left non-numeric/non-testable and omitted by PRD-level decision (if that was in fact decided during elicitation — the PRD gives no indication either way).

### 3. Persona-validation-gap risk is not carried forward, and Target User section reads more confidently than the Brief supports
The Brief's Major Risks explicitly flags: "Persona validation gap... the problem statement here is grounded in vendor-marketing patterns and domain research, not a direct user interview" — a caveat the Brief treats as important enough to name as a Major Risk. The PRD's §2 Target User (including the named persona "Elif" and four confidently-stated JTBD items) carries no trace of this caveat. A reader of the PRD alone would have no way to know the persona is unvalidated by direct interview.
**Suggested fix:** Add a brief caveat near §2.1 or in §0 Document Purpose noting the persona is derived from landscape/vendor research, not direct analyst interviews, consistent with the Brief's Major Risks.

### 4. No Risks section or equivalent — "silent principle erosion" and other Major Risks have no PRD trace
The Brief has a dedicated Major Risks section covering five risks (SER reliability, Turkish-language support, persona validation gap, scope creep, silent principle erosion). The PRD has no Risks section at all. Some risks are reasonably absorbed into other mechanisms (Turkish → resolved via Open Question 1; scope creep → guarded by explicit Non-Goals in §5/§6.2; SER reliability → echoed in NFR-2/NFR-5). However, "**Silent principle erosion**" — the risk that voice-first discipline could be quietly abandoned under implementation time pressure "without being obvious in a demo" — is not referenced anywhere, even though it is precisely the risk that FR-4's "never skipped, bypassed, or replaced" language and NFR-3 (terminology discipline) exist to guard against. Its absence means a future Architecture/dev reader has no explicit warning that this discipline requires active enforcement, not just documentation.
**Suggested fix:** Either add a lightweight "Risks Carried Forward" pointer in §0 or §11 referencing the Brief's Major Risks section by name, or fold "silent principle erosion" into NFR-1/FR-4 as an explicit rationale line (e.g., "This requirement exists specifically to guard against silent principle erosion under implementation time pressure — see Product Brief, Major Risks").

## Not Gaps (Checked and Confirmed Preserved)

- Four Guiding Principles: GP1–GP3 fully realized; GP4 is the one gap (Gap 1/2 above).
- MVP Scope and Non-Goals: all Brief non-goals present in PRD §5/§6.2; PRD additions (speaker-ID/voiceprint exclusion, AI-summary deferral, coaching-notes exclusion) are traceable to Brief content (Major Risks' "rich feature wishlist" line, general non-request) rather than being fabricated — no silent scope expansion found.
- Persona and primary use case: QA/CX Analyst and two-party call-center-style conversation are accurately preserved; secondary "team leads/coaches, not designed-for in MVP" note is explicitly carried into §2.2.
- Success Criteria "no numeric accuracy target" / functional+qualitative stance: preserved (§6.2, §7), except for the one missing portfolio-demonstration item (Gap 2).
- The "okay, that's fine" illustrative example: preserved in substance via PRD §2.1 JTBD #4 ("a customer says 'fine' in a clipped, frustrated tone") — not verbatim but faithfully carried.
- "What Makes This Different" honest-differentiation framing (no category-invention claim, comparison to CallMiner/Verint/Cogito/etc., no accuracy-superiority claim): not present in the PRD in any form. Related to Gap 1 — since it explains *why* the portfolio framing matters, the same fix (a short acknowledgment in §0) would address both.
