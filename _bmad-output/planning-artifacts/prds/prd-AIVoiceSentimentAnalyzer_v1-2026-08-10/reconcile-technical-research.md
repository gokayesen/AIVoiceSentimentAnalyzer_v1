# Input Reconciliation: Technical Research → PRD

**Source:** `research/technical-voice-sentiment-analyzer-research-2026-08-10.md`
**Downstream artifact checked:** `prds/prd-AIVoiceSentimentAnalyzer_v1-2026-08-10/prd.md`

## Method

Read both documents in full. Checked (1) whether the PRD ever states/implies a specific technology, model, dataset, or implementation approach as decided rather than deferred to Architecture (grepped for model/library/vendor names and for numeric accuracy/WER/UAR figures — none found outside of generic terms like "API/data contracts"); (2) whether product-level scoping decisions (language, speaker attribution, confidence framing, constraints) correctly reflect — without over- or under-claiming — the specific research findings behind them; (3) whether any significant, product-relevant research finding is missing from the PRD such that a future reader would be blindsided.

## Gaps Found

### 1. The AlloSat "voice-first vs. evidence" tension is never acknowledged anywhere in the PRD

**Description:** The research's Executive Summary and Technical Risk #2 both flag a genuine, published, on-domain finding: in the AlloSat call-center satisfaction study, transcript content was the dominant contributor and "the benefit of fusing acoustic and linguistic modalities is not as obvious" (research §2.2, §Technical Risks #2). The research explicitly frames this as "a genuine, published tension exists for the voice-first principle" and says it "should be stated honestly, not glossed over." The PRD's Vision (§1) states voice-first as a firm, unqualified commitment ("treating the acoustic/voice signal as a first-class analytical input alongside — never subordinate to — transcript-based text analysis") and nowhere — not in Vision, Constraints (§11), NFRs (§10), or Success Metrics (§7) — acknowledges that the literature does not guarantee acoustic signal will add measurable value over text alone. FR-11 (surface disagreement) and SM-2 (voice-first check: acoustic analysis isn't a "no-op or decorative pass-through") are good *operational* responses to this tension, but they don't state the tension itself. A future reader (UX or Architecture) has no signal in the PRD that this is a known, evidenced open risk rather than settled ground.

**Location:** PRD §1 Vision (line 21); absent from §7 Success Metrics, §10 Cross-Cutting NFRs, §11 Constraints and Guardrails.

**Suggested fix:** Add a short note — most naturally in §10 (Cross-Cutting NFRs, alongside NFR-2/NFR-5) or as a new bullet in §11 Constraints — stating that voice-first is a deliberate design commitment, not a claim that acoustic signal is proven to improve sentiment accuracy over transcript alone; cite Technical Research §2.2/Technical Risk #2 (AlloSat finding) so downstream readers understand FR-11/SM-2 exist precisely because this is unresolved, not decorative.

## Checks That Passed (no gap/violation found)

- **Implementation-decision leakage (most important check):** No specific model, dataset, STT engine, fusion algorithm, or local-vs-cloud choice is named or implied as decided anywhere in the PRD. Grepped for Whisper/Wav2Vec2/HuBERT/WavLM/pyannote/librosa/openSMILE/NeMo/Vosk/Deepgram/cloud vendor names/IEMOCAP/CREMA-D/etc. — zero matches in prd.md. Every place the PRD touches a technical unknown (FR-4 acoustic models, FR-8 fusion mechanism, FR-16 diarization vs. channel-split), it explicitly labels the choice "Out of Scope" / "an Architecture decision" and cites the relevant Technical Research section. This is the correct pattern throughout.
- **No numeric accuracy/calibration targets:** Grepped for %, WER, UAR, F1, "accuracy of," etc. — no invented targets found. §6.2 explicitly states no numeric accuracy/precision target is established at PRD level; NFR-2 explicitly disclaims any calibration guarantee; NFR-5 requires any future accuracy claim to state what it was measured against — directly consistent with research's domain-shift finding (IEMOCAP→CEMO drop) and the "no in-domain evaluation data yet" finding.
- **Turkish language scope (FR-6, §6.2):** PRD goes further than research's minimum bar — research offered two defensible options (experimental/best-effort Turkish mode, or English-only), and the PRD picks the more conservative one (full exclusion, not even labeled "experimental"), citing the same "no direct evidence base" finding as justification. This does not overclaim (no Turkish capability is promised) and does not misrepresent the research (research never said Turkish must be offered, only that if offered it must be labeled experimental). Correctly scoped.
- **Speaker attribution (FR-16, §4.6):** Correctly framed as conditional/best-effort, explicitly tied to "what the input audio actually allows," citing Technical Research §5's mono-vs-stereo finding. Does not name diarization technology; "Out of Scope" note correctly defers channel-separation-vs-diarization-model choice to Architecture.
- **Constraints — Privacy (§11):** Correctly carries forward the GDPR/KVKK biometric-adjacent-data finding and the re-identification-risk finding as product-level requirements (retention posture, no cross-call speaker ID, prefer synthetic/consented demo audio) without resolving into a specific technical control. Explicitly disclaims itself as "not legal advice."
- **Constraints — Cost (§11):** Correctly states portfolio/no-budget as a real constraint for Architecture to weigh "without the PRD prescribing a local-vs-cloud implementation choice," directly matching research's own framing (§10.4: "a reasoned recommendation for Architecture to weigh — not a final decision").

## Summary

One gap found, moderate severity: the PRD operationalizes the AlloSat/voice-first tension (via FR-11 and SM-2) but never states the underlying evidentiary risk in prose, so a future reader isn't told *why* those requirements exist. No instances of the PRD adopting a research recommendation as a final implementation/architecture decision were found — the "Out of Scope: ... Architecture decision" pattern is applied consistently and correctly everywhere a technical unknown surfaces.
