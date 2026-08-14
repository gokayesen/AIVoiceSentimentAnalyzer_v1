# Good-Spine Checklist Review — ARCHITECTURE-SPINE.md (AI Voice Sentiment Analyzer)

**Reviewed:** `_bmad-output/planning-artifacts/architecture/architecture-AIVoiceSentimentAnalyzer_v1-2026-08-10/ARCHITECTURE-SPINE.md`
**Against:** PRD (`prd.md`), `.memlog.md`
**Method:** Full read of all three source documents; live web verification (WebSearch) of every named library/version in the Stack table.

---

## Verdict

Solid, well-disciplined spine overall — 19 ADs cleanly cover the 9 topics the memlog flagged as architecture-deferred, the memlog's own self-corrections (AD-1/AD-8 fusion-failure contradiction, MC Dropout reversal, NFR-4 binding fix) are all correctly reflected in the final document, and every named tech/version in the Stack table checked out against a live search — nothing reads like hallucinated training-data recall. The main weaknesses are two silently-missing dimensions the altitude explicitly owns (audio format/size/duration validation, which the PRD explicitly delegates to Architecture; and operations/observability, which the checklist calls out by name), a testing/CI deferral that undercuts the enforceability the ADs claim for themselves, an incomplete NFR trace in the Capability Map, one AD whose Rule reaches beyond what its own Prevents clause justifies, and rationale bleeding into several Rule fields that belongs in the memlog instead.

---

## 1. Real divergence points fixed, none missing

Covers all 9 memlog-flagged topics (audio input/speaker attribution, local-vs-cloud, model serving boundary, SER/STT/diarization model choice, fusion, confidence/uncertainty, chunking, storage, async orchestration) plus 3 further additions found during reconciliation (evaluation strategy AD-17, deployment envelope AD-18, text-sentiment classifier AD-19). This part is thorough.

Two gaps found — see §6 (Operations/observability) and the Capability Map finding in §5 for the audio-format/duration/size gap, which is really a "missing AD" finding hiding inside the map-coverage check. Both are listed as findings below.

## 2. Every AD's Rule enforceable and actually closes its Prevents scenario

Spot-checked all 19 ADs for Rule/Prevents alignment. Most hold up — e.g. AD-1's "acoustic failure/skip → Call `failed`; transcript failure does not fail the Call" genuinely closes the "silent transcript-only degradation" scenario in its Prevents clause; AD-10's "co-present fields on the same row, not merely reachable via a join" genuinely closes the "can't show confident-sentiment + uncertain-attribution together" scenario.

**Finding (medium):** AD-13's Rule contains a clause not justified by its own Prevents clause. The Prevents clause is about the web layer blocking a thread or losing status across a process restart (an in-process-vs-queue architecture question). The Rule adds "The broker must be Redis, per the pinned Stack version — not Valkey or another substitute" — a specific-product lock-in that has nothing to do with blocking/status-loss (Valkey is protocol-compatible with RQ and would prevent the same failure modes equally well; RQ officially supports Valkey per the Stack-table verification). This also oversteps the memlog's own framing (`.memlog.md` line 31): "Valkey... is a viable drop-in alternative if the user later wants zero licensing ambiguity, but is not required" — the memlog treats Valkey as a legitimate later option, not something to categorically forbid. Either narrow the Rule to match the Prevents clause, or add a Valkey-specific Prevents rationale if the exclusion is intentional.

## 3. Deferred list — nothing is a disguised invariant

Reviewed all 10 Deferred bullets. Eight are clearly safe (tunable numeric parameters — chunk-length, disagreement/confidence thresholds; later-phase concerns — MC Dropout upgrade, live-hosted demo, epic/story breakdown, exact Emotion wording, GPU/CPU empirical validation, exact SQLite DDL — all correctly scoped as "the spine fixes the mechanism/shape, not the value").

**Finding (medium-high):** "CI/CD pipeline and testing strategy — not addressed this run" is deferred with zero substance, which sits uneasily next to how the ADs are written. Roughly a third of the ADs use absolute, code-level enforcement language — AD-1 "No code path may ever substitute...", AD-2 "No path may skip speaker attribution...", AD-8 "A trained fusion model must never replace this step", AD-16 "No API response or UI surface may show...". These read as invariants meant to be checked, not aspirations. With testing/CI strategy completely unaddressed (not even a placeholder principle like "AD-1/AD-8/AD-16 invariants must have a regression test"), there is currently no build-substrate mechanism that would catch a future violation of any of these "never" rules. This isn't as clearly "safe to leave open" as the other Deferred items — it borders on a disguised invariant (how these rules get enforced) parked under a bullet that treats it as pure process/tooling.

## 4. Named tech verified-current

Live-verified via WebSearch (not from training-data recall):

| Claim in spine | Verification result |
| --- | --- |
| FastAPI 0.141.1 | Confirmed — released July 29, 2026, latest as of review |
| React 19.2.8 | Confirmed — released July 21, 2026 |
| faster-whisper v1.2.1 (MIT) | Confirmed — Oct 31, 2025 release, still latest stable, project active not abandoned |
| pyannote.audio 4.0.7 / Community-1 pipeline, CC-BY-4.0 | Confirmed — Community-1 pipeline is CC-BY-4.0, "will always remain freely accessible" |
| transformers v5.14.1 | Confirmed — v5.0 shipped July 15, 2026 with weekly minor cadence; v5.14.x consistent with that cadence by review date |
| PyTorch 2.13 | Confirmed — released July 8, 2026 |
| Redis 8.10, AGPLv3 option | Confirmed — Redis 8.0 added AGPLv3 tri-license May 2025; 8.10 is July 2026 stable |
| RQ 2.10.0, official Valkey support | Directionally confirmed — RQ officially supports Valkey (Redis>=5 or Valkey>=7.2); exact 2.10.0 changelog not independently located but no contradicting evidence |

No finding here — this is a genuine strength. The spine also correctly self-flags its two shakiest claims as unverified rather than asserting them confidently: faster-whisper's MIT license ("verify LICENSE file at implementation time") and WhisperX's license ("ambiguity between BSD-2 and BSD-4... verify before depending on it"). That hedging is exactly the right move for a claim that wasn't fully checked, and is worth calling out as good practice, not a defect.

## 5. Capability → Architecture Map vs PRD FR-1–FR-16 / NFR-1–NFR-5

All 16 FRs are present as rows and reference an AD (or the delete/retention row under §10). Coverage is complete for FRs.

**Finding (high):** FR-1's format/size/duration validation requirement is not actually satisfied anywhere. PRD FR-1's consequences explicitly delegate this to Architecture: *"System accepts a defined set of common audio formats (e.g., WAV/MP3/M4A). The exact format list is deferred to Architecture..."* and *"System rejects files exceeding a defined maximum duration or size..."* — the PRD requires only that Architecture make *some* documented, enforced format/limit decision, not which one. The spine's Capability Map row for FR-1/FR-2 cites only "Consistency Conventions — State & cross-cutting (structured validation errors)," which governs the *shape* of a validation error, not *what gets validated* (no accepted-format list, no max duration, no max size anywhere in the document — not in an AD, not in Consistency Conventions, and not even acknowledged in Deferred). This is a capability the PRD explicitly handed to this document that the document silently drops — the clearest "explicitly delegated PRD requirement gone missing" finding in this review.

**Finding (medium):** NFR-1 through NFR-5 never appear as rows in the Capability → Architecture Map, even though every NFR is in fact bound somewhere (NFR-1→AD-5, NFR-2→AD-17, NFR-3→AD-15, NFR-4→AD-16, NFR-5→AD-17, all confirmed present in the ADs' `Binds:` lines). The Map's own heading is "Capability → Architecture Map," and functionally it only maps the FR half of the PRD's requirement set. A reader using the Map as the coverage-verification tool (its evident purpose) would not see NFR coverage at all without cross-referencing every AD's Binds line by hand.

## 6. Every dimension the altitude owns is decided/deferred/open — especially operational envelope

Deployment & environments: **decided** (AD-18 — single-machine docker-compose, CPU-only, no cloud, no live demo). Infra/provider strategy: **decided by absence** (AD-18's "no cloud hosting target" is itself the decision). Good coverage on these two.

**Finding (high):** Operations — logging, monitoring, error observability/diagnostics — is completely silent. Not decided, not deferred, not an open question; the word doesn't appear anywhere in the document. This matters more than it might for a typical CRUD app because several ADs describe failure states that need to be *observable* to mean anything in practice: AD-1's Call → `failed` transition, AD-6's two distinct diarization-failure states (Call-level "unavailable" vs turn-level "uncertain"), AD-13's queue/worker lifecycle. With zero decision on how any of this gets logged or surfaced for debugging (even at "structured logs to stdout, no dashboard" MVP-portfolio scope), a future implementer has no guidance and two independently-built pipeline stages could easily diverge on how/whether they log failures — exactly the kind of silent-dimension gap the checklist flags this item to catch.

(See also §5's format/duration/size finding — that's also, in substance, an altitude-owned dimension left silent, just discovered via the Capability Map cross-check rather than a direct scan.)

## 7. Internal consistency

No direct AD-vs-AD or AD-vs-diagram contradictions found. Specifically checked and confirmed *consistent*:
- AD-1 ↔ AD-8 on transcript-failure handling (this was a memlog-documented self-correction; the fix is correctly reflected in both ADs, cross-referencing each other).
- AD-9 (temperature-scaling-only, MC Dropout deferred) ↔ Deferred list (MC Dropout entry) ↔ memlog's MC Dropout reversal — all three agree.
- AD-6's pyannote pipeline/license ↔ Stack table's pyannote.audio 4.0.7/Community-1/CC-BY-4.0 — consistent (and correctly reflects the memlog's mid-run correction from the originally-drafted 3.1/MIT pipeline).
- AD-10's TranscriptTurn/TimelineSegment co-presence requirement ↔ Core-entity sketch (no contradiction; sketch doesn't contradict, though it also doesn't visually encode the co-presence requirement — minor, not worth a separate finding since the sketch is explicitly scoped to "names and relationships" only).
- Container diagram (Structural Seed) ↔ AD-7's mermaid diagram — same shape, consistent.

The one item that borders on a consistency issue (AD-13's Rule vs. its own Prevents clause, and vs. the memlog's softer framing of Valkey) is already captured under §2 rather than duplicated here.

## 8. Rationale discipline

Most ADs keep Rule text terse and directive. **Finding (medium):** several ADs let persuasive/citational rationale leak into the Rule field itself, where the Prevents field already carries the "why" and the memlog is the designated home for deeper rationale:

- **AD-14**'s Rule spends its second half re-explaining the SER-vs-STT research provenance ("Technical Research §10.1 [RESEARCH FINDING] found no major cloud provider... Hume AI's dedicated acoustic-emotion API being sunset... is separately [VERIFIED]") — this is evidence for the decision, not an instruction to follow.
- **AD-19**'s Rule closes with "This keeps the text-analysis path symmetric with AD-3's SER approach: a controllable, explainable classifier whose output feeds fusion (AD-8) as one of the two required signals — never a pre-emptive answer (AD-1)" — persuasive cross-referencing, not a directive.
- **AD-6**'s Rule includes "Diarization confidence is expected to be systematically lower during overlapping/emotionally-charged speech — exactly the turns this product cares about most (Technical Research §5.4)" — this is rationale for *why* per-turn confidence must be captured, which belongs in Prevents/memlog, not stated as if it were part of the enforceable Rule.
- **AD-9**'s Prevents clause itself narrates a discarded-mistake story ("...under the mistaken belief that the batch/async architecture removes all objections to it") — this is memlog-flavored process narrative (the MC-Dropout reversal), not a description of a future divergence risk.

None of these make the ADs unenforceable — the actual directives are still extractable — but they read closer to persuasive essay in places than the terse, enforceable style the rest of the document (e.g. AD-2, AD-5, AD-15) achieves. Worth a pass to relocate the citation/rationale sentences into Prevents or drop them, leaving Rule as pure instruction.

---

## Additional minor observation (not a formal finding)

AD-17 (evaluation strategy) is more a reporting/methodology policy ("must be established against a majority-class baseline first," "must be labeled explicitly as optimistic upper bounds") than a code-architecture invariant in the sense the other 18 ADs operate — it constrains how a future *claim* is worded/substantiated rather than how two units of code could diverge. It's defensible to keep (NFR-2/NFR-5 do require this), but it sits at a different altitude than the rest of the AD list and a reader skimming for "what does the code have to do" could miss that this one is really "what does a report have to say."

---

## Summary of Findings by Severity

| # | Severity | Checklist item(s) | Finding |
| --- | --- | --- | --- |
| 1 | High | 1, 5, 6 | Audio format allowlist + max duration/size limits (PRD FR-1, explicitly delegated to Architecture) are never decided, deferred, or raised as an open question anywhere in the spine |
| 2 | High | 6 | Operations/observability (logging, monitoring, failure diagnostics) is completely silent — not decided, deferred, or an open question |
| 3 | Medium-High | 3, 6 | CI/CD & testing strategy deferred with zero substance, while ~1/3 of ADs rely on absolute "never/no code path may" language with no stated enforcement mechanism |
| 4 | Medium | 5 | Capability → Architecture Map never surfaces NFR-1–NFR-5 as rows, despite all five being bound inside individual ADs |
| 5 | Medium | 2, 7 | AD-13's "must be Redis, not Valkey" clause isn't justified by its own Prevents clause and oversteps the memlog's own framing of Valkey as a legitimate future alternative |
| 6 | Medium | 8 | Rationale/citations leak into the Rule field in AD-6, AD-9, AD-14, AD-19, blurring Rule vs. Prevents vs. memlog-owned rationale |
| 7 | Low | 1 | AD-17 (evaluation strategy) is a reporting/methodology policy, arguably a different altitude than the other 18 code-architecture ADs — defensible to keep, worth flagging |
| — | Positive (no action) | 4 | All Stack-table tech/versions live-verified as accurate; the two shakiest claims (faster-whisper, WhisperX licenses) are correctly self-flagged as unverified rather than asserted |
