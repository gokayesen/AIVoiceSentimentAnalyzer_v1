---
title: AI Voice Sentiment Analyzer
status: final
created: 2026-08-10
updated: 2026-08-10
---

# PRD: AI Voice Sentiment Analyzer

## 0. Document Purpose

This PRD defines the product requirements and scope for the AI Voice Sentiment Analyzer MVP. It builds directly on two prior artifacts and does not duplicate their content: the [Product Brief](../../briefs/brief-AIVoiceSentimentAnalyzer_v1-2026-08-09/brief.md) (vision, problem, target user, guiding principles, MVP boundaries) and the [Technical Research](../../research/technical-voice-sentiment-analyzer-research-2026-08-10.md) (evidence on speech emotion recognition (SER), fusion, datasets, Turkish support, and deployment tradeoffs). Technical Research findings are used here only at the level of product requirements and scope constraints — implementation-level decisions (model choice, fusion mechanism, local vs. cloud, dataset selection) are explicitly deferred to the Architecture phase.

This document is structured around Glossary-anchored vocabulary (§3 — terms used informally in §2 are formally defined there; read §3 first if a term in §2 is unclear), features with globally-numbered Functional Requirements (§4), and inline `[ASSUMPTION]` tags resolved and indexed in §8. It is written for the product owner, and for the downstream UX and Architecture workflows that will consume it next.

This PRD also carries forward, deliberately, a goal from the Product Brief that doesn't reduce to a Functional Requirement: the finished product should meaningfully demonstrate technical depth across audio processing, speech emotion recognition, acoustic feature analysis, multimodal fusion, and confidence/uncertainty handling — not as a stated feature, but as a lens on *how* the FRs in §4 should be satisfied. See §7 SM-6 and §11.

## 1. Vision

Understand *how* something was said, not only *what* was said.

AI Voice Sentiment Analyzer is a post-call analysis tool that determines sentiment, emotion, and emotional dynamics directly from spoken audio, treating the acoustic/voice signal as a first-class analytical input alongside — never subordinate to — transcript-based text analysis. It exists because a QA / Customer Experience analyst reviewing a call today either listens end-to-end (slow, inconsistent) or uses a transcript-only sentiment tool (blind to tone, sarcasm, and vocal escalation).

The product does not replace the analyst's judgment. It produces an evidence-linked, confidence-qualified analysis — overall sentiment, dominant emotion, an emotional timeline, and the acoustic and textual signals behind each judgment — so the analyst can decide, in a fraction of the listening time, which calls need a full manual review.

## 2. Target User

### 2.1 Jobs To Be Done

- When I finish a batch of recorded calls, I want to see which ones show meaningful emotional escalation or distress, so I can prioritize my limited review time on the calls that matter most.
- When a call is flagged, I want to see *why* — which moments, which signals — so I can trust the flag instead of treating the system as a black box I either blindly accept or ignore.
- When the system isn't sure, I want it to say so, so I don't mistake a shaky guess for a confident finding.
- When text and tone disagree (a customer says "fine" in a clipped, frustrated tone), I want to see both readings, not one number that quietly picked a winner.

**Persona validation note:** Elif (§2.3) and the pain points above are grounded in domain/landscape research into how QA analysts and vendors describe this work (Product Brief), not a direct interview with a practicing QA analyst. Treat the persona as a well-reasoned working model to design against, not a validated one — this is a candidate to close during UX research, not a fact this PRD asserts.

### 2.2 Non-Users (v1)

- **Contact-center customers** — not a customer-facing product; customers are the subject of analysis, not a user of the tool.
- **Live agents needing real-time assistance** — real-time/live coaching is explicitly out of scope (Product Brief non-goal).
- **Team leads/coaches as a designed-for primary audience** — they may consume an analyst's findings secondhand, but the product is not designed around their workflow in v1 (Product Brief).
- **Enterprise IT/CRM administrators** — no integration surface exists in MVP; there is nothing for this role to administer.

### 2.3 Key User Journeys

**UJ-1. An analyst decides whether a call needs full review, without listening to it end-to-end.**

- **Persona + context:** Elif, a QA/Customer Experience analyst, has a queue of recorded calls from the previous day and limited time to review them.
- **Entry state:** Elif has a recorded call file. MVP requires no analyst authentication or accounts — a single-session tool (confirmed, §8 Open Question 3).
- **Path:**
  1. Elif uploads the call recording. The system validates it and shows a processing status while analysis runs (FR-3).
  2. Once complete, Elif opens the Analysis Result: overall sentiment, dominant emotion, confidence, and an emotional timeline (FR-8, FR-9).
  3. She notices a low-confidence spike partway through the call and expands that point on the timeline, seeing the transcript excerpt and the acoustic signal that triggered it side-by-side (FR-12, FR-13).
  4. She judges the shift is well-supported by both signals — text and tone agree — and moves on without a full manual listen.
- **Climax:** Elif trusts (or appropriately distrusts) the system's judgment because she can see the evidence and confidence behind it, not just a label.
- **Resolution:** Elif moves to the next call in her queue, having spent a fraction of the listening time she would have otherwise.
- **Edge case:** On a different call, the transcript reads neutral but the acoustic signal reads high-arousal-negative. The system surfaces both readings distinctly rather than silently averaging them, and confidence is lowered for that segment — Elif is prompted to listen to that specific moment herself (FR-10, FR-11).

## 3. Glossary

- **Call** — a single uploaded audio file representing one two-party (agent + customer) conversation, submitted for post-call analysis.
- **Analyst** — the primary user role (QA / Customer Experience Analyst) who uploads a Call and reviews its Analysis Result. Retains final judgment (see Human Review).
- **Acoustic Analysis** — extraction and interpretation of non-linguistic voice signal characteristics (e.g., pitch, energy, speaking rate, pauses, voice activity) from a Call's audio.
- **Transcript Analysis** — text-based sentiment/emotion/keyword analysis performed on a Call's transcribed text, produced via speech-to-text.
- **Emotion** — a discrete or dimensional affective state (e.g., anger, frustration, calm) inferred by the system. Distinct from Sentiment; the two are never used interchangeably in this product (see NFR-3).
- **Sentiment** — a polarity judgment (positive/negative/neutral, optionally with intensity) about a portion of a Call, informed by both Acoustic Analysis and Transcript Analysis.
- **Fusion** — the process by which Acoustic Analysis and Transcript Analysis outputs are combined into a single Analysis Result. The specific mechanism is an Architecture decision, not defined by this PRD.
- **Confidence** — a system-reported indication of how certain the system is about a given Emotion or Sentiment judgment. Must accompany every analysis output; never implies a validated accuracy/calibration guarantee (see NFR-2).
- **Low-Confidence Segment** — a portion of an Analysis Result where Confidence falls below a defined threshold, explicitly flagged rather than presented as a definitive judgment.
- **Emotional Timeline** — a chronological representation of how Emotion and Sentiment evolve across a Call's duration.
- **Analysis Result** — the complete system output for a given Call: overall Sentiment, dominant Emotion, Confidence, Emotional Timeline, transcript, and acoustic insights.
- **Human Review** — the Analyst's process of examining an Analysis Result (and, where needed, the underlying Call) to make the final quality, coaching, or escalation judgment. The system supports this process; it never substitutes for it.

## 4. Features

### 4.1 Audio Upload & Validation

**Description:** The entry point to the product. An Analyst submits a Call for analysis; the system validates it and keeps the Analyst informed while processing runs, since analysis is not instantaneous. Realizes UJ-1 (steps 1-2).

**Functional Requirements:**

#### FR-1: Analyst can upload a Call for analysis

Analyst can upload a single audio file recording of a two-party (agent + customer) conversation. Realizes UJ-1.

**Consequences (testable):**
- System accepts a defined set of common audio formats (e.g., WAV/MP3/M4A). The exact format list is deferred to Architecture per Technical Research §11 — this FR requires only that *some* explicit, documented, enforced format set exists, not which formats.
- System rejects files exceeding a defined maximum duration or size with a clear, specific error message rather than a silent failure or generic error.
- System validates that the uploaded file is a decodable audio file before beginning analysis.

#### FR-2: System communicates upload/validation errors clearly

Analyst receives a plain-language error when a Call fails validation (e.g., unsupported format, corrupt file, exceeds duration limit).

**Consequences (testable):**
- The error message names the specific validation rule that failed (e.g., which format was rejected, or which limit was exceeded), not a generic "upload failed."
- The error message tells the Analyst what to do next (e.g., re-export in a supported format) rather than only stating that something went wrong.

#### FR-3: System communicates processing status while a Call is being analyzed

Analyst can see that a Call is queued, processing, or complete, since analysis takes meaningful time.

**Consequences (testable):**
- Analyst is never left looking at an unchanging screen with no indication that processing is underway.
- If processing fails partway through, the Analyst is told the Call could not be analyzed, not shown a partial or misleading result.

### 4.2 Acoustic Analysis

**Description:** The system's voice-first commitment made concrete: acoustic signal analysis is a mandatory, independent stage of the pipeline for every accepted Call — never optional, never skipped, never replaced by transcript-only analysis. Realizes the Product Brief's voice-first guiding principle.

**Functional Requirements:**

#### FR-4: System performs Acoustic Analysis on every accepted Call

System extracts acoustic/voice signal characteristics from the Call's audio as a first-class analytical input, independent of and prior to Transcript Analysis.

**Consequences (testable):**
- Acoustic Analysis output exists and is inspectable (§4.5) for every Call that passes FR-1 validation.
- Acoustic Analysis is never skipped, bypassed, or replaced by transcript-only analysis, including in a degraded or fallback state.
- Acoustic Analysis produces output independently of whether Transcript Analysis (§4.3) succeeds — a transcript failure does not remove the acoustic signal from the Analysis Result.

**Out of Scope:** Which specific acoustic features or models are used — an Architecture decision informed by Technical Research §1 and §3.

#### FR-5: System derives an Emotion signal from Acoustic Analysis

System produces an Emotion judgment (and/or emotional-intensity signal) from the Call's acoustic signal, kept and presented as a distinct output from any text-derived Sentiment (see Glossary).

### 4.3 Transcript Generation & Analysis

**Description:** The supporting, not primary, analytical path: the Call's audio is transcribed and the resulting text is analyzed for sentiment and conversational context. This feature exists to inform Fusion (§4.4) — it is never presented as the whole analysis on its own.

**Functional Requirements:**

#### FR-6: System generates a transcript of the Call

System produces a text transcript of the Call's audio via speech-to-text, for use in Transcript Analysis and for direct display to the Analyst (§4.5).

**Notes:** MVP scope is English-language audio only. Turkish is explicitly deferred to a future version, not offered as an experimental MVP capability — Technical Research found no direct evidence base for reliable Turkish speech emotion recognition, so promising it even as "best-effort" would be an unsupported claim at this stage.

#### FR-7: System analyzes the transcript for Sentiment and conversational context

System derives text-based Sentiment, Emotion indicators, and relevant keywords/context from the Call's transcript.

**Consequences (testable):**
- Transcript Analysis output is kept distinct from Acoustic Analysis output through Fusion (§4.4) — it is a contributing signal, not a pre-emptive final answer.

### 4.4 Multimodal Fusion & Analysis Result

**Description:** Where Acoustic Analysis (§4.2) and Transcript Analysis (§4.3) are combined into the Analyst-facing Analysis Result. This is the product's multimodal commitment: both signals may contribute; neither is discarded; disagreement between them is preserved and surfaced, not silently resolved. The fusion mechanism itself is an Architecture decision (Technical Research §6) — this section defines only the required *product-level behavior* of whatever mechanism Architecture selects.

**Functional Requirements:**

#### FR-8: System combines Acoustic Analysis and Transcript Analysis into a single Analysis Result

System produces, for each Call, an Analysis Result containing overall Sentiment, dominant Emotion, and Confidence, informed by both Acoustic Analysis and Transcript Analysis. Realizes UJ-1 (step 2).

**Out of Scope:** The specific fusion mechanism (rule-based vs. learned, early vs. late fusion) — an Architecture decision per Technical Research §6.

#### FR-9: System generates an Emotional Timeline for each Call

System produces a chronological view of how Sentiment and Emotion evolve across the Call's duration. Realizes UJ-1 (step 2-3).

**Consequences (testable):**
- The timeline's resolution is granular enough for the Analyst to distinguish two distinct emotional shifts occurring within the same Call, not just report one value for the whole Call. The exact granularity/windowing is deferred to Architecture; this FR requires only that the timeline is genuinely chronological and multi-point, not a single aggregate score presented as if it were a timeline.

#### FR-10: Every Sentiment/Emotion judgment carries a Confidence indicator

Every value in the Analysis Result — overall and per-timeline-segment — is accompanied by a Confidence indicator. Segments below a defined confidence threshold are marked as Low-Confidence Segments rather than presented as equivalent to high-confidence findings. The threshold's exact value is deferred to Architecture/evaluation work (Technical Research §8) — this FR requires only that some documented, applied threshold exists, matching the deferral pattern used in FR-1 for audio formats.

**Consequences (testable):**
- No Sentiment or Emotion value in the Analysis Result is ever displayed without an accompanying Confidence indicator.
- This FR requires only that some confidence threshold and presentation exist — it does not itself claim calibration; see NFR-2.

#### FR-11: System surfaces disagreement between Acoustic Analysis and Transcript Analysis

When Acoustic Analysis and Transcript Analysis meaningfully disagree for a given Call segment, the system presents both signals distinctly to the Analyst rather than silently resolving the disagreement into a single number. Realizes UJ-1 (edge case).

**Consequences (testable):**
- A segment with strong cross-modal disagreement is identifiable by the Analyst as such, not indistinguishable from a segment where both signals agreed.

### 4.5 Analysis Dashboard

**Description:** Where the Analyst does their work: reviewing a completed Call's Analysis Result, inspecting evidence, and forming their own judgment. This is a web application (confirmed for MVP). Realizes UJ-1 (steps 2-4).

**Functional Requirements:**

#### FR-12: Analyst can view the full Analysis Result for a completed Call

Analyst can view, for any completed Call: overall Sentiment, dominant Emotion, Confidence, Emotional Timeline, full transcript, and the acoustic insights supporting the result.

**Out of Scope:** AI-generated conversation summary and "important moments" highlighting — the Product Brief listed these as possible future dashboard elements but did not confirm them as MVP-committed. Treated as deferred pending confirmation — see Open Question 4.

#### FR-13: Analyst can inspect a specific Emotional Timeline point and see its supporting evidence

Analyst can select a point or segment on the Emotional Timeline and see the corresponding transcript excerpt and acoustic evidence displayed together. Realizes UJ-1 (step 3) and the product's explainability commitment (NFR-1).

#### FR-14: Dashboard visually distinguishes Low-Confidence Segments from high-confidence ones

Analyst can tell, without additional interpretation, which parts of the Analysis Result the system is less certain about.

#### FR-15: System never presents an Analysis Result using language that asserts certainty

All Analysis Result language is probabilistic and evidence-linked (e.g., "Emotion: Frustration, Confidence: 0.84") — never a flat assertion (e.g., "the customer is definitely frustrated"). Realizes the Product Brief's human-in-the-loop and confidence/uncertainty principles.

**Consequences (testable):**
- No UI copy, label, or generated text anywhere in the Analysis Result asserts an emotional or sentiment state as settled fact.

### 4.6 Speaker Attribution (Conditional)

**Description:** Whether the Analysis Result can be broken down by speaker (agent vs. customer) depends on what the input audio actually allows — this is treated as a conditional capability, not an assumed one, per Technical Research §5's finding that diarization may or may not be necessary depending on input channel format.

**Functional Requirements:**

#### FR-16: System attributes Analysis Result segments to a speaker when the input audio allows it

When a Call's audio allows reliable separation of agent and customer speech, the system attributes relevant portions of the Analysis Result to the appropriate speaker.

**Out of Scope:** Whether this is achieved via audio-channel separation or a diarization model — an Architecture decision (Technical Research §5). Speaker attribution is confirmed as a best-effort, conditional capability for MVP, not a guaranteed one — Calls where reliable separation isn't possible from the input audio still produce a full Analysis Result (FR-8 through FR-15), just without a per-speaker breakdown.

## 5. Non-Goals (Explicit)

- **Real-time call analysis or live agent assistance** — this product analyzes completed calls only.
- **CRM, telephony, or call-center platform integrations** — a standalone analysis tool, not embedded in a live operational workflow.
- **Automated customer responses** — the product analyzes; it does not act on a customer's behalf.
- **Voice cloning or voice generation** — unrelated capability.
- **Enterprise-scale infrastructure or multi-tenant SaaS architecture** — a single-analyst-scale tool for MVP.
- **Cross-call analytics or trend dashboards** — each Call is analyzed independently; aggregate/portfolio-level reporting across many Calls is not MVP.
- **Speaker identification or voiceprint-based re-identification of individuals** — Speaker Attribution (§4.6) distinguishes "agent" from "customer" within a single Call; it does not identify *who* a speaker is across Calls or against any external record. This is a deliberate privacy boundary (see §10 Constraints and Guardrails › Privacy), not a capability gap to fill later.
- **AI-generated conversation summaries and "important moments" highlighting** — considered but not committed for MVP; see Open Question 4.
- **Coaching notes, annotations, or any analyst-authored record-keeping within the tool** — not requested in the Product Brief; the Analyst's judgment and any resulting action happen outside this product for MVP.

## 6. MVP Scope

### 6.1 In Scope

- Single audio file upload of a two-party, call-center-style conversation (FR-1 through FR-3).
- Acoustic Analysis as a mandatory, independent pipeline stage (FR-4, FR-5).
- Transcript generation and text-based analysis as a supporting pipeline stage (FR-6, FR-7).
- Fusion of Acoustic Analysis and Transcript Analysis into a single Analysis Result, with Confidence and disagreement surfaced (FR-8 through FR-11).
- A web-based Analysis Dashboard presenting the Analysis Result with drill-down evidence and confidence framing (FR-12 through FR-15).
- Conditional speaker attribution where input audio allows it (FR-16).

### 6.2 Out of Scope for MVP

- Everything listed under §5 Non-Goals.
- AI-generated conversation summary and "important moments" — deferred pending confirmation (Open Question 4).
- Turkish (or any non-English) language support — MVP is English-only; Turkish is deferred to a future version pending stronger evidence for Turkish speech emotion recognition.
- Any numeric accuracy/precision target for Emotion or Sentiment classification — no such target is established at the PRD level (see §7, Success Metrics).
- Analyst accounts, authentication, or multi-user access control — treated as a single-session tool pending confirmation (Open Question 3).

## 7. Success Metrics

**Primary**
- **SM-1**: End-to-end completion — a Call submitted through FR-1 reaches a displayed Analysis Result (FR-12) without manual intervention, for realistic call-length audio. Validates FR-1 through FR-12.
- **SM-2**: Voice-first check — for a representative sample of analyzed Calls, both Acoustic Analysis and Transcript Analysis are demonstrably, independently reflected in the Analysis Result (neither is a no-op or decorative pass-through). Validates FR-4, FR-5, FR-8.
- **SM-3**: Confidence is present and distinguishable — every displayed Sentiment/Emotion value carries a Confidence indicator, and Low-Confidence Segments are visually distinguishable from high-confidence ones on inspection. Validates FR-10, FR-14.

**Secondary**
- **SM-4**: Plausibility on manual spot-check — Analysis Results are judged plausible and defensible by the product owner on manual review, even without a formal ground-truth evaluation set. Validates FR-8, FR-9.
- **SM-5**: Explainability reachability — for any Analysis Result, the Analyst can reach the specific transcript and acoustic evidence behind a given judgment within the dashboard, without leaving the tool. Validates FR-13.
- **SM-6**: Technical-depth demonstration — the shipped FR set, taken together, gives a concrete, inspectable example of each of: audio processing, acoustic feature analysis, speech-to-text integration, NLP sentiment analysis, multimodal fusion, and confidence/uncertainty handling. Carried forward from the Product Brief's fourth guiding principle (technical depth as a deliberate, non-decorative goal alongside analyst value); validated qualitatively (is each competency genuinely present and inspectable, not claimed), not by a score. Validates FR-4 through FR-11.

**Counter-metrics (do not optimize)**
- **SM-C1**: Displayed Confidence should not be optimized to be uniformly high. A system that reports high confidence indiscriminately is a failure of this product's core principle even if it looks more "finished" — Confidence must reflect genuine uncertainty, including reporting low confidence often if that is the honest state of the system. Counterbalances SM-3.
- **SM-C2**: Do not optimize for reducing the frequency of surfaced modality disagreement (FR-11) to make the dashboard look cleaner. A drop in surfaced disagreements should prompt investigation into whether disagreement detection quietly broke, not be read as a quality improvement by default. Counterbalances SM-2.

## 8. Open Questions

All product-level questions identified while drafting this PRD were resolved with the product owner during the elicitation pass (see `.memlog.md` for the full decision trail). None remain blocking as of this draft. For traceability, the questions raised and how each was resolved:

1. **Language scope for MVP** — resolved: English-only (§4.3 FR-6, §6.2). *Gives up:* Turkish-speaking customers/agents are unsupported at MVP launch, not just "lower quality" — this is a real market/coverage limitation, accepted because Technical Research found no evidence base to support even an experimental claim.
2. **Guaranteed vs. best-effort speaker attribution** — resolved: best-effort/conditional, as originally drafted (§4.6 FR-16). *Gives up:* the product cannot promise per-speaker breakdown in the UX or in any success metric — dashboard design (UX phase) must handle the "no speaker attribution available" case as a normal, expected state, not an edge case.
3. **Analyst accounts/authentication** — resolved: none for MVP; single-session tool (§2.3 UJ-1).
4. **AI-generated summary / "important moments"** — resolved: deferred, not MVP (§4.5 FR-12, §5, §6.2).
5. **Audio input constraints (formats/duration/size)** — resolved: no PRD-level decision needed; FR-1 already correctly requires that *some* explicit, documented limit exists, with exact values deferred to Architecture per Technical Research §11.
6. **Data retention and deletion** — resolved: minimal retention posture; no persistent-storage guarantee (§10 Constraints and Guardrails › Privacy). *Gives up:* the Analyst cannot rely on the tool as a historical record — no re-visiting an old Call's Analysis Result after the session ends, no audit trail. Acceptable for MVP because record-keeping was never a requested capability (§5), but worth naming since it forecloses a plausible future feature by default.
7. **Call-level "reviewed" state tracking** — resolved: none for MVP; each Analysis Result stands alone, consistent with the existing exclusion of annotations/record-keeping (§5).

Should new open questions surface during UX or Architecture work, they should be logged against this PRD via the Update intent rather than resolved silently downstream.

No unresolved `[ASSUMPTION]` tags remain in this document as of finalize — the ones raised during drafting (§2.3 entry state, §4.1 audio formats, §4.5 summary/moments) are exactly Open Questions 3, 5, and 4 above, and were folded into §2.3, §4.1, and §4.5 respectively once resolved.

## 9. Cross-Cutting NFRs

- **NFR-1 (Explainability):** Every Emotion or Sentiment output in the Analysis Result must be traceable, within the dashboard, to at least one supporting signal (acoustic evidence, transcript excerpt, or both). No output may be presented as unexplainable or evidence-free. Realizes FR-13.
- **NFR-2 (Confidence honesty):** The product may report Confidence values, but this PRD makes no claim that those values are statistically calibrated or independently validated against ground truth — that evaluation work is a prerequisite to any stronger claim, and is explicitly not assumed complete for MVP (Technical Research found no in-domain evaluation data yet exists). Product copy and documentation must not imply a calibration guarantee that hasn't been established.
- **NFR-3 (Terminology discipline):** "Emotion" and "Sentiment" are used per the Glossary (§3) consistently across all UI copy, API/data contracts, and generated output. No synonym or interchangeable use is permitted anywhere in the product surface.
- **NFR-4 (Human-in-the-loop framing):** No product surface (dashboard copy, exported output, error states) may frame the system's output as a final decision. Language must consistently position the Analyst as the final reviewer (Glossary: Human Review).
- **NFR-5 (Evaluation transparency):** Any accuracy, performance, or reliability claim the product surfaces (in-app or in documentation) must state what it was measured against (dataset, method, conditions). Unqualified accuracy claims are not permitted, consistent with Technical Research's finding of significant domain-shift risk between lab/acted datasets and real call-center audio.

## 10. Constraints and Guardrails

### Privacy
Call audio is sensitive, potentially re-identifiable personal data (Technical Research §12: voice retains re-identification risk even after nominal anonymization; both GDPR and Turkish KVKK treat biometric-adjacent voice data as requiring heightened care). Product-level requirements, not implementation choices:
- Retention posture (decided): the product makes no persistent-storage guarantee. Uploaded Calls and their Analysis Results are retained only for the duration of the session/demo use and must be deletable; the product must not silently accumulate real people's voice recordings by default.
- The product must not perform speaker identification or voiceprint-based re-identification across Calls (§5 Non-Goals) — Speaker Attribution (§4.6) is scoped strictly within a single Call.
- Where representative demo audio is needed, synthetic or consented recordings should be preferred over real, unconsented call recordings — a product/process constraint, not an architecture one.

*This is a product-requirements framing of the privacy constraint, not legal advice; Technical Research §12 is informational only.*

### Cost and Processing Expectations
- This is a single-developer, portfolio-scale project with no dedicated production infrastructure budget. Architecture should treat this as a real constraint on scale assumptions, without the PRD prescribing a local-vs-cloud implementation choice (Technical Research §10 captures the relevant tradeoffs).
- Because analysis is post-call/batch, not real-time, there is no sub-second latency requirement. The product-level requirement is that the Analyst is never left without status feedback during processing (FR-3), not a specific processing-time target.

## 11. Known Risks (Carried Forward)

These risks originate in the Product Brief and Technical Research and are not resolved by this PRD — they're recorded here so a reader working from this document alone isn't blindsided, and so UX/Architecture know to actively watch for them rather than assume they were handled upstream.

- **Persona validation gap.** The Analyst persona (§2) is grounded in domain/vendor-landscape research, not a direct interview with a practicing QA analyst. If UX research surfaces a materially different picture of how analysts actually work, this PRD's Target User and Key User Journey should be revisited via the Update intent, not patched silently downstream.
- **Voice-first vs. evidence tension.** Technical Research (§2.2) found a published call-center-domain study (AlloSat) where transcript content was the dominant contributor to satisfaction prediction and the benefit of acoustic+text fusion was "not obvious." This PRD still commits to voice-first (§1, FR-4) as a deliberate design principle, not because the literature guarantees it improves accuracy. FR-11 (disagreement surfacing) and SM-2 (voice-first check) exist specifically to make this tension observable in the finished product rather than assumed away — if acoustic signal turns out to add little value in practice, that should show up as a measurable finding, not be hidden by a fusion step that quietly leans on text.
- **Silent principle erosion.** Carried forward directly from the Product Brief: under implementation pressure, it is easier to build a transcript-only pipeline than a genuinely voice-first one, and the shortcut may not be obvious from the outside (the dashboard can look identical either way). FR-4's "never skipped, bypassed, or replaced" language and SM-2/SM-C2 exist as concrete, testable guardrails against this — but the risk is a discipline problem, not something a requirement alone eliminates, and should be actively checked during Architecture and implementation review, not assumed solved by having been written down here.

