---
name: AI Voice Sentiment Analyzer
status: final
sources:
  - '{planning_artifacts}/prds/prd-AIVoiceSentimentAnalyzer_v1-2026-08-10/prd.md'
  - '{planning_artifacts}/briefs/brief-AIVoiceSentimentAnalyzer_v1-2026-08-09/brief.md'
  - '{planning_artifacts}/research/technical-voice-sentiment-analyzer-research-2026-08-10.md'
updated: 2026-08-10
---

# AI Voice Sentiment Analyzer — Experience Spine

Single-primary-persona, capability-first web console for a QA/Customer Experience Analyst (Elif, per the PRD) reviewing AI-analyzed customer service calls. Realizes PRD FR-1 through FR-16; term usage (Call, Analyst, Acoustic Analysis, Transcript Analysis, Emotion, Sentiment, Fusion, Confidence, Low-Confidence Segment, Emotional Timeline, Analysis Result, Human Review) follows the PRD Glossary exactly — this spine does not redefine them.

## Foundation

Single-surface responsive web application, light mode only for MVP (confirmed decision — see `.memlog.md`). No UI system inherited; this is a custom-built visual system, fully specified in `DESIGN.md`. No authentication/accounts (PRD §2.3) — the app opens directly into the analyst's working session. No native mobile/desktop surface for MVP.

`DESIGN.md` is the visual identity reference (Clinical/Data-Dense direction) — this document specifies only behavior: what exists, what it does, and what state it's in.

## Information Architecture

| Surface | Reached from | Purpose | Mock |
|---|---|---|---|
| Session Call List | App open (default landing surface) | The analyst's working queue for this session: every Call uploaded and analyzed so far, at-a-glance sentiment/emotion/confidence, entry point for uploading a new Call. Realizes the JTBD "when I finish a batch of recorded calls..." framing. | `mockups/session-call-list.html` |
| Upload | "+ Add call" action from Session Call List | A Call enters the system here: file selection, format/duration validation (FR-1, FR-2), processing status (FR-3). Not a separate page — an in-place state of the Session Call List (see Component Patterns, State Patterns). | spine-only (transient row states — see State Patterns) |
| Analysis Dashboard | Selecting a completed Call row in the Session Call List | The full Analysis Result for one Call: summary, Emotional Timeline, transcript, acoustic insights, evidence drill-down (FR-8 through FR-16). Realizes UJ-1 steps 2–4. | `mockups/analysis-dashboard.html` |
| Confirm dialog (overlay, not a navigable surface) | Delete action from Call row or Dashboard | Confirms the destructive, unrecoverable delete of a Call (§10). | `mockups/confirm-dialog.html` |

This is a two-surface product by design (Session Call List + Analysis Dashboard) — timeline drill-down (FR-13) is a state within the Dashboard, not a third navigable surface, since the evidence it reveals only makes sense in the context of the Call it belongs to. IA closes here: every stated PRD need (upload, monitor processing, review results, drill into evidence, move to the next call) has a surface, and every surface is reached by a Call in UJ-1.

→ **Mocks vs. spine:** the three `mockups/*.html` files above are 1:1 renders of the load-bearing surfaces, built from the current (post-accessibility-fix) `DESIGN.md` tokens. `.working/directions-1.html` is preserved as Discovery-phase provenance only (superseded by post-accessibility-fix tokens) — not a current visual reference. The Upload surface's transient states (validating/processing/failed) are spine-only (State Patterns) — simple row-level text/status changes that don't need a dedicated visual mock. **The spine (this document + `DESIGN.md`) always wins on conflict with a mock.**

**Out of scope surfaces** (confirmed against PRD Non-Goals — do not add): no account/settings screen (no auth), no cross-call analytics/trend view (§5), no annotation or "mark reviewed" UI (§5, Open Question 7), no AI-generated summary or "important moments" screen (§5, Open Question 4 — deferred).

## Responsive & Platform

Desktop-width browser viewport is the primary and only fully-specified target for MVP — the analyst's core task (reviewing a timeline, transcript, and acoustic evidence side by side) assumes enough width for the Dashboard's two-column grid (transcript ~60% / acoustic ~40%, per `DESIGN.md` Layout & Spacing) and the four-cell summary row. Below a practical minimum width (viewport narrower than ~960px), the layout degrades as follows rather than being pixel-pushed into unreadability:

- The Dashboard's two-column grid (transcript / acoustic insights) stacks to a single column, transcript first, acoustic insights below it.
- The four-cell summary row wraps to a 2×2 grid.
- The Session Call List's right-aligned confidence/duration column remains, but the row's hit-target and hover-revealed delete `icon-button` become always-visible rather than hover-only (no reliable hover on touch/narrow viewports).

No dedicated mobile/tablet-optimized layout is designed for MVP — this is a narrower-desktop-window fallback, not a touch-first redesign, consistent with the "not a touch-first surface" stance stated under Interaction Primitives.

## Voice and Tone

Brand voice lives structurally in `DESIGN.md` (Brand & Style: "an analyst's instrument, not a consumer app... produces evidence, not verdicts"). This section specifies the resulting microcopy rules — realizes PRD NFR-2 (confidence honesty), NFR-3 (terminology discipline), NFR-4 (human-in-the-loop framing), NFR-5 (evaluation transparency):

- **Never assert certainty.** No copy states an emotional or sentiment reading as settled fact. "Emotion: Frustration — Confidence: 0.84," never "The customer is frustrated." This applies everywhere a reading appears — summary cells, timeline tooltips, Call rows, copy-pasted text (there is no dedicated export feature — see PRD Non-Goals).
- **Any performance/accuracy claim states its basis.** If the product ever surfaces a number that looks like a performance claim (not a per-Call Confidence value, but something like a general accuracy statement), it must state what it was measured against, per NFR-5. In practice, for MVP this means: no aggregate/marketing-style accuracy claim appears anywhere in the product — the only numbers shown are per-Call Confidence values (already governed by the rule above), because no in-domain evaluation data exists yet to support a stronger claim (Technical Research §8.3–§8.4).
- **The standing disclaimer is fixed, not optional.** Every Analysis Dashboard shows the following text, without warning styling: *"Model output — acoustic + lexical estimate, not a determination. Analyst review required before action."* This is boilerplate on purpose — it must read identically on every Call, not be paraphrased per-instance, so the analyst reads it as a permanent fact about the tool rather than a situational alert.
- **"Sentiment" and "Emotion" are never interchangeable labels.** A field labeled "Emotion" always shows an Emotion value (e.g., Frustration, Calm, Resignation); a field labeled "Sentiment" always shows a polarity (Negative/Positive/Neutral). No UI string uses one word to mean the other.
- **Flag reasons are always stated, never just the flag.** A `low` or `conflict` tag is never shown bare — it is always paired with a one-line, specific reason ("utterance < 1.2s, overlapping cross-talk — insufficient acoustic signal"), consistent with NFR-1 (explainability) and NFR-5 (no unqualified claims).
- **Missing capability is stated plainly, not hidden.** When speaker attribution isn't available for a Call (mono input), the UI says so directly ("Mono input — turns unattributed") rather than omitting speaker labels silently.
- **No hype register.** No exclamation points, no "Great news!" framing on positive results, no anthropomorphizing the system ("I think..."). The tool reports; the analyst judges.

## Component Patterns

Visual specs for each of these live in `DESIGN.md` Components; this section specifies their behavior.

- **Timeline** (`{components.timeline-segment}` variants) — a horizontal, chronologically-ordered strip covering the full Call duration (FR-9). Each segment represents a contiguous span of consistent reading, shown with both its semantic-color fill and its fixed glyph (`–`/`◆`/`▼`/`▲` for the four base readings, `?`/`⚠` for low-confidence/disagreement) — the glyph is what makes the strip readable at a glance without depending on hue discrimination. Hovering/selecting a segment opens that moment's evidence in the transcript + acoustic panels below (FR-13) — the timeline is the primary navigation device into the Call's evidence, not a passive chart.
- **Summary cells** — always exactly four: Overall Sentiment, Dominant Emotion (+ Confidence), Secondary Signal, Segments Flagged. **Secondary Signal** is a second, lower-weight Emotion/Sentiment reading contributed by Acoustic Analysis or Transcript Analysis when it doesn't dominate the fused result but is still distinct enough to report (FR-5, FR-8) — its purpose is to keep a non-dominant modality's contribution visible even when it "lost" the fusion, which is part of what makes SM-2 (voice-first check: neither modality is a decorative pass-through) verifiable by looking at the dashboard alone. When no such secondary reading exists, the cell states "None flagged," never left visually empty/broken. **Segments Flagged** is a count (low-confidence + disagreement segments combined) that is itself a link/anchor to the first flagged segment when greater than zero; at zero it displays "0" as plain, non-linked `data` typography — not a broken or missing link.
- **Transcript turn** — one row per speaker turn. Default state shows timestamp, speaker (when attributed), and text. `low-confidence` and `disagreement` variants (see DESIGN.md) are not decorative — clicking either scrolls the acoustic panel to the corresponding evidence, keeping transcript and acoustic evidence synchronized (realizes NFR-1).
- **Dual-signal panel** (`{components.dual-signal-panel}`, rendered inside a `disagreement` transcript turn) — the canonical rendering of FR-11. Always two labeled halves, "Text signal" and "Tone signal," each with its own value and confidence. Never collapses to one blended number under any state (loading, error, or otherwise).
- **Acoustic metric bar** — always paired with a short note connecting the metric back to a specific transcript timestamp ("elevated @ 04:05") — an acoustic reading floating with no transcript anchor is not a valid state; every acoustic insight shown must be traceable to a moment (NFR-1). **Metric labels must name an actual acoustic feature** — pitch/F0, energy, speaking rate, or pauses/voice-activity (the feature set Technical Research §3.1/§3.3 identifies as both established and MVP-realistic) — never a generic "acoustic score" or unnamed composite. This is what makes the panel real, inspectable evidence rather than a decorative gauge, per the Product Brief's technical-depth principle and NFR-1.
- **Call row** — filename, Sentiment/Emotion + Confidence (with `badge-dot`, see below), duration. Selecting a row (any part of it, full-row hit target) opens the Analysis Dashboard for that Call. A hover/focus-revealed delete action removes the Call from the session (realizes PRD §10's "must be deletable" requirement), routing through the `confirm-dialog` (see below) before deletion occurs, since it's destructive and there is no persistent history to recover from (§10, minimal retention).
- **Badge dot** — always rendered immediately adjacent to its Sentiment/Emotion text value in the Call row, using the same four-color mapping as the Timeline; it is reinforcement, never the sole carrier of meaning — the analyst reads the text ("Negative · Frustration"), not the dot color, as the source of truth (see Accessibility Floor).
- **Confirm dialog** (`{components.confirm-dialog}`) — triggered by any delete action (Call row or Dashboard). States the Call's filename and that deletion is immediate and unrecoverable (§10). Two actions: Cancel (default focus, dismisses with no change) and Delete (destructive-styled, confirms). Also dismissible via Escape or clicking the overlay, equivalent to Cancel.

## State Patterns

- **Empty session** — Session Call List with zero Calls: a plain prompt to upload the first Call. No illustration/mascot (register mismatch with the clinical direction) — a single clear instruction and the upload control.
- **Uploading / validating** — inline in the Session Call List as a new row in a transient "validating" state (FR-1). On failure (FR-2), the row shows the specific validation error (format, duration, corrupt file) and a retry/re-upload action — it does not silently disappear or block the rest of the list.
- **Processing** — after validation passes, the row shows a "processing" status (FR-3) distinct from both "validating" and "complete" — the analyst can keep working with other Calls in the list while this one processes; processing is never a full-screen blocking state.
- **Processing failed** — the row states the Call could not be analyzed (FR-3) with a clear, non-blaming message and a retry action; it is never shown as if it silently completed.
- **Complete** — the row is selectable and opens the Analysis Dashboard.
- **Deleting** — triggered from the Call row's or Dashboard's delete action; opens the `confirm-dialog` first (Component Patterns). On confirm, the Call and its Analysis Result are removed from the session immediately (no undo — see §10 minimal retention); if the deleted Call was open in the Analysis Dashboard, the analyst returns to the Session Call List. On cancel/dismiss, nothing changes.
- **Low-confidence segment** (Dashboard) — hatch pattern + dashed border + `?` glyph on the timeline; paired transcript turn shows the `low` tag and flag reason. This state can never be visually confused with an actual "Neutral" reading (see DESIGN.md Do's and Don'ts).
- **Disagreement segment** (Dashboard) — split-fill timeline segment + `⚠` glyph; paired transcript turn shows the `conflict` tag and the dual-signal panel.
- **Speaker attribution unavailable** (Dashboard + Call row) — transcript turns render without speaker labels; a visible inline note states why ("Mono input — turns unattributed"), consistent with PRD FR-16 being conditional, not guaranteed. This is a whole-Call state (the input format either supports attribution or it doesn't).
- **Speaker attribution uncertain** (Dashboard, per-turn) — distinct from the whole-Call state above: even when attribution is nominally available, Technical Research §5.4 finds diarization confidence drops specifically during overlapping or emotionally charged speech — exactly the turns this product cares most about. A transcript turn whose speaker label is low-confidence shows the label with a *dotted* underline (`speaker-label.uncertain` in DESIGN.md) — deliberately a different line style than the transcript-turn `low-confidence` variant's *dashed* border, so the two kinds of uncertainty are never visually conflated even if only line style, not color, is perceivable — plus a one-line reason ("overlapping speech — speaker attribution uncertain"). This state can co-occur with a confident Sentiment/Emotion reading on the same turn — the two are independent axes of uncertainty and must be legible independently.

## Interaction Primitives

- **Upload** — file picker and drag-and-drop onto the Session Call List are both accepted; drag-and-drop is a progressive enhancement, not the only path (keyboard/click-based file selection must always work).
- **Timeline scrub/select** — click or keyboard-navigate (arrow keys, when focused) between segments; selecting a segment scrolls the transcript panel to the corresponding turn and highlights the relevant acoustic metrics — a single action synchronizes all three panels (FR-13). Each segment is individually focusable (see Accessibility Floor).
- **Row selection (Call row, transcript turn)** — full hit-target click; every clickable row/turn is also a focusable, keyboard-activatable element (Enter/Space) — this is a keyboard-driven analyst tool by nature (dense data, fast triage), not a touch-first surface.
- **Delete a Call** — available both from its Call row (hover/focus-revealed `icon-button`) and from within its Analysis Dashboard (equivalent action, same `confirm-dialog`) — an analyst reviewing a Call shouldn't need to return to the list just to remove it.
- **Return to Session Call List** — clicking the `app-header` breadcrumb (queue/case path) from anywhere in the Analysis Dashboard returns the analyst to the Session Call List; this is the normal (non-delete) path implied by UJ-1 step 4.

## Accessibility Floor

- **Never color-alone.** Every semantic color use is paired with a non-color signal: the four base Sentiment/Emotion states each carry a fixed glyph (`–`/`◆`/`▼`/`▲`) independent of their fill color, not just the two special states; the low-confidence hatch pattern is additionally paired with a dashed border and a `?` glyph; the disagreement split-fill is paired with a `⚠` glyph and the explicit dual-signal text panel; `tag` elements carry text labels ("LOW CONF 0.38," "CONFLICT") on every flagged element; `badge-dot` is never shown without its adjacent Sentiment/Emotion text. A colorblind analyst must be able to identify every state — including the ordinary, most-common ones, not just the flagged ones — from shape/pattern/text alone, with color as reinforcement only. This is a hard requirement given the product's own honesty principle would be undermined by a state that's only legible to some readers.
- **Visible focus state, everywhere.** Every focusable element (Call row, transcript turn, individually-focusable timeline segment, `icon-button`, `confirm-dialog` actions, the `app-header` breadcrumb) shows the `focus-ring` treatment from DESIGN.md — a browser default is not sufficient given how dense the hairline-bordered layout is. "Keyboard-complete" (below) is a functional claim; this is what makes it also a *visible* one.
- **Keyboard-complete.** Every interaction in Interaction Primitives has a keyboard path; the timeline, transcript, and acoustic panels are not mouse-only.
- **Timeline segments are screen-reader-legible, not just keyboard-focusable.** Each timeline segment carries an accessible name stating its time range, its Sentiment/Emotion reading, and — when applicable — its flagged state and reason (e.g., "02:14–02:40, Negative, confidence 0.71" or "03:00–03:30, Low confidence: overlapping cross-talk, insufficient acoustic signal"). The transcript panel, where every turn carries the same tag/reason text, is the guaranteed complete non-visual equivalent to the timeline — a screen-reader user can reach everything the timeline conveys by reading the transcript list turn by turn, without depending on the timeline's spatial/visual interaction.
- **Text scaling.** Every typographic role in this system is 11px or larger (`DESIGN.md` Typography — 11px is the system floor). This scale must remain legible and non-overlapping at up to 200% OS-level text scaling (the WCAG 1.4.4 benchmark, not just browser zoom) — validate specifically on the transcript panel and Session Call List, the two most spacing-dense structures (`DESIGN.md` Layout & Spacing).
- **Disclaimer and flag reasons are real text**, not baked into an image or icon-only — always available to a screen reader.

## Key Flows

**UJ-1. An analyst decides whether a call needs full review, without listening to it end-to-end.** *(Mirrors PRD UJ-1 verbatim — reproduced here as the spine's own reference, per BMAD UX convention.)*

- **Persona + context:** Elif, a QA/Customer Experience Analyst, has a queue of recorded Calls from the previous day and limited time to review them.
- **Entry state:** Elif opens the app directly into the Session Call List (no login). She has a recorded Call file ready to upload.
- **Path:**
  1. Elif uploads the Call from the Session Call List. The row shows validating, then processing status while analysis runs.
  2. Once complete, Elif selects the row, opening the Analysis Dashboard: overall Sentiment, dominant Emotion, Confidence, and the Emotional Timeline.
  3. She notices a low-confidence (hatched, `?`-glyph) segment partway through the timeline and selects it — the transcript scrolls to the corresponding turn, tagged and flagged with its reason, and the acoustic panel highlights the relevant metrics.
  4. She judges the shift is well-supported by both signals and returns to the Session Call List via the breadcrumb, selecting the next Call.
- **Climax:** Elif trusts (or appropriately distrusts) the system's judgment because the timeline, transcript, and acoustic evidence stay synchronized and evidence-linked — never a bare label.
- **Resolution:** Elif is back at the Session Call List and opens the next Call, having spent a fraction of the listening time she would have otherwise. Nothing about this Call persists beyond the session (confirmed retention decision).
- **Edge case (signal disagreement):** On a different Call, at the 04:05 mark the transcript reads "Okay, that's fine" (neutral-to-positive text) while the acoustic signal reads Frustration. The timeline shows a split-fill, `⚠`-glyph disagreement segment; selecting it opens the dual-signal panel showing both readings side by side rather than one blended number — Elif listens to that specific moment herself before deciding.
- **Failure branch:** If Elif's upload fails validation (FR-2) or processing fails after validation (FR-3), the Call's row states the specific problem in place — she is never blocked from working the rest of her queue, and re-upload/retry is always available from the same row (see State Patterns: Uploading/validating, Processing failed).
