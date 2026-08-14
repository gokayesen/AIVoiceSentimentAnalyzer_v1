# Accessibility-Focused Adversarial Review — DESIGN.md / EXPERIENCE.md

**Scope:** `ux-AIVoiceSentimentAnalyzer_v1-2026-08-10/DESIGN.md` and `EXPERIENCE.md`
**Frame:** The product's stated integrity claim is that it never hides uncertainty from any analyst. Every finding below is scored against how much it undermines that claim specifically for a colorblind, low-vision, screen-reader, or keyboard-only analyst — not against generic WCAG compliance for its own sake.

**Verdict up front:** The spine's *intent* is genuinely strong — it is one of the few UX specs that names accessibility as a correctness property rather than a checkbox, and several mechanisms (hatch pattern, split-fill, dual-signal panel, tag text) are real, well-reasoned non-color signals. But the color palette chosen to implement that intent frequently fails to deliver it: several of the specific tokens used *for* the "never color alone" and "always legible" guarantees are themselves too low-contrast to be reliably perceived, and the base 4-color sentiment scale — the thing an analyst reads first, on the timeline, before clicking anything — has no non-color encoding at all. There is also a real, unaddressed gap between "keyboard-complete" (claimed) and "visible focus state" (unspecified).

---

## Method note on contrast numbers

WCAG 2.x relative-luminance contrast ratios computed directly from the frontmatter `colors` hex values (sRGB → linear → relative luminance → contrast ratio; standard WCAG formula). AA thresholds used: **4.5:1** for normal text, **3:1** for large text (≥18.66px bold / ≥24px regular) and for non-text UI components / graphical objects that convey information (WCAG 1.4.11). None of this product's small type (10–13px) qualifies as "large text," so 4.5:1 is the applicable bar for all body/label/data text below ~18px.

---

## Findings

### F1 — [CRITICAL] Base 4-color Sentiment/Emotion scale is color-alone on the timeline

**Where:** DESIGN.md frontmatter `components.timeline-segment.variants` (lines 100–104: `neutral`, `mixed`, `negative`, `positive` are each a single hex color, no pattern/shape); DESIGN.md Components prose line 190 ("These two special states [`low-confidence`, `disagreement`] are visually distinct from every semantic-color variant *and* from each other"); EXPERIENCE.md Accessibility Floor line 78 ("Every semantic color use (Sentiment/Emotion scale, low-confidence, disagreement) is paired with a non-color signal").

**The gap:** Line 78's claim explicitly names "the Sentiment/Emotion scale" as covered by the never-color-alone guarantee, but no non-color signal is ever specified for it. Only the two *special* states get one: `low-confidence` gets a hatch pattern + dashed border, `disagreement` gets a split-fill shape + dual-signal text panel on interaction. The plain `negative`/`mixed`/`positive`/`neutral` segments (the vast majority of the timeline, in normal operation) are solid, undifferentiated color fills with no shape, icon, texture, or always-visible text distinguishing one from another. EXPERIENCE.md line 49 confirms the timeline is meant to work as an at-a-glance instrument ("the primary navigation device… not a passive chart") — but at-a-glance is exactly the mode a colorblind analyst cannot use here: red/green/amber/gray are only reliably separable by clicking every single segment to reveal its text label in the transcript panel below (FR-13). That defeats the timeline's actual purpose (fast triage) for that analyst even though the information is technically reachable via another surface.

**Severity: CRITICAL.** This is the base case the product's whole "never hides uncertainty from any analyst" claim exists to prevent, and it's the most-used state, not an edge case.

**Fix:** Give the 4-way scale a shape or texture axis independent of hue — e.g., distinct edge/notch shapes per polarity, a small glyph baked into each segment (▲ mixed, ▽ negative, etc.), or differing fill density/texture per state (not just the two special states). At minimum, add a persistent (not hover-only) tick/icon row beneath the timeline showing polarity per segment in text-legible form.

---

### F2 — [CRITICAL] The low-confidence hatch pattern's own two fill colors are almost indistinguishable from each other (1.19:1)

**Where:** DESIGN.md frontmatter, `low-confidence-hatch-a: '#E4E8EC'` / `low-confidence-hatch-b: '#CFD6DC'` (lines 31–32); used in `components.timeline-segment.variants.low-confidence` (line 105) and `components.tag.variants.low` background (line 118).

**Computed:** contrast between `low-confidence-hatch-a` and `low-confidence-hatch-b` = **1.19:1**.

**The gap:** DESIGN.md Do's and Don'ts (line 201) states: "the pattern must survive grayscale/colorblind viewing on its own, not rely on hue alone." But the hatch pattern is made of two grays 1.19:1 apart — at small timeline-segment sizes this will very likely render as visually flat, not as a perceptible diagonal texture, for *any* viewer, not just colorblind ones. If the pattern itself isn't visible, the product's one designated non-color signal for low-confidence collapses back to relying on the dashed border alone — which (see F8) is also low-contrast. This is the mechanism specifically built to satisfy the "hard accessibility requirement" language in DESIGN.md line 161, and as specified it likely fails to render as a perceivable pattern at all.

**Severity: CRITICAL.** This is a self-defeating implementation of the product's own stated hard requirement.

**Fix:** Widen the hatch pair to at least 3:1 contrast (e.g., pair `low-confidence-hatch-a` with something closer to `border` #D8DEE4 vs. a mid gray like `text-faint` #8A939C would give ~2.85:1 — still short; better to pair against `low-confidence` #AEB6BE lightened/darkened, or simply use `panel` white against a genuinely mid-gray, e.g. `#F7F8F9` / `#9AA4AD`, targeting ≥3:1). Validate the pattern is visible at actual rendered segment width (some segments may be only a few px wide), not just as a swatch.

---

### F3 — [HIGH] `badge-dot` in the Call row has no documented color mapping and is not named in the Accessibility Floor's enumeration

**Where:** DESIGN.md frontmatter `components.badge-dot` (lines 131–133: only `size` and `radius` — no `variants`, no colors, unlike `timeline-segment` and `tag` which both explicitly enumerate their color variants); DESIGN.md Components prose line 194 ("Call row — … sentiment/emotion with `badge-dot` …"); EXPERIENCE.md Component Patterns line 54 ("Call row — filename, Sentiment/Emotion + confidence, duration"); EXPERIENCE.md Accessibility Floor line 78 (enumerates "the low-confidence hatch pattern… the disagreement split-fill… the `tag` text labels" as the never-color-alone mechanisms — `badge-dot` is never mentioned).

**The gap:** As specified, `badge-dot` is the one colored, meaningful UI element in the entire system with zero documented color-to-state mapping and zero explicit non-color pairing. Cross-referencing EXPERIENCE.md's Voice and Tone section (line 37: "'Emotion: Frustration — Confidence: 0.84'… applies everywhere a reading appears — summary cells, timeline tooltips, **call-list rows**…") strongly implies a text label accompanies the dot in practice — so this is likely *not* a literal color-alone instance in intent. But that's an inference from a different section written for a different purpose (microcopy rules), not a confirmed visual pairing, and the Accessibility Floor's own checklist — the section whose entire job is to enumerate every color-alone risk — omits it entirely. An implementer working from DESIGN.md Components + frontmatter alone has no confirmation that text accompanies the dot, and no defined dot-to-sentiment color mapping to implement in the first place.

**Severity: HIGH** (not critical, because of the mitigating cross-reference in Voice and Tone, but a real, checkable gap in exactly the section designed to prevent this class of gap).

**Fix:** Add `badge-dot` variants to the frontmatter (`negative`/`mixed`/`positive`/`neutral-signal`, reusing the sentiment palette) and explicitly state in Components prose that the dot is always paired with the adjacent Sentiment/Emotion text value, never shown alone. Add `badge-dot` by name to the Accessibility Floor's enumeration in EXPERIENCE.md line 78.

---

### F4 — [HIGH] `text-label` (10px bold, all-caps) fails AA body-text contrast: 3.62:1 on panel, 3.31:1 on bg

**Where:** DESIGN.md frontmatter `text-label: '#7C8894'` (line 23); `typography.label` (lines 38–42, 10px/700/uppercase); used per DESIGN.md Colors prose line 163 ("`text-label`… all-caps section labels") and Components prose line 172 ("`label`… marks every section header and field label"). Used in `summary-cell.label-color` (line 91), `speaker-label` default foreground implicitly inherits `label` typography (line 135).

**Computed:** `text-label` on `panel` (#FFFFFF) = **3.62:1**; on `bg` (#F3F5F7) = **3.31:1**. Both fail the 4.5:1 AA threshold for normal text. 10px bold does not qualify as "large text" under WCAG (needs ≥18.66px bold), so the 3:1 large-text exception does not apply.

**The gap:** This is the single most widely-used text role in the system — every section header, every field label (including summary-cell labels for "Overall Sentiment," "Dominant Emotion," etc.) and the default speaker-label typography all use it. It sits directly under the Accessibility Floor's "Text scaling" bullet (line 80) but the floor never checks color contrast for this role, only size.

**Severity: HIGH.** Not state-specific (doesn't itself hide an uncertainty signal), but it degrades legibility of the labels an analyst needs to orient the whole dashboard, for low-vision readers specifically — the same population most affected by the low-contrast findings below.

**Fix:** Darken `text-label` to at least `#5F6B77` (≈4.5:1 on panel) or bump weight/size, or accept as "large text" only if size increases to ≥18.66px (not desirable given density goals) — darkening the token is the cleaner fix and doesn't disturb layout.

---

### F5 — [HIGH] `text-faint` fails AA: 3.12:1 on panel, 2.85:1 on bg — used for the disclaimer bar and every flag reason

**Where:** DESIGN.md frontmatter `text-faint: '#8A939C'` (line 22); `disclaimer-bar.foreground` (line 95, "the output is a model estimate requiring analyst review"); Tag component prose line 192 ("always paired with a one-line flag reason in `text-faint`"); `icon-button.foreground-default` (line 142); Colors prose line 163 (`text-faint`: "disclaimers/metadata").

**Computed:** `text-faint` on `panel` = **3.12:1**; on `bg` = **2.85:1**; on `panel-subtle` = **2.93:1**. All fail 4.5:1 AA for text, and the `bg`/`panel-subtle` cases even fail the looser 3:1 non-text threshold.

**The gap:** This is not a cosmetic miss. `text-faint` is the color used for exactly the two things EXPERIENCE.md's Accessibility Floor calls out by name as load-bearing: the standing disclaimer (line 39, line 81: "Disclaimer and flag reasons are real text… always available to a screen reader") and every flag reason on a `low`/`conflict` tag (line 41, "Flag reasons are always stated, never just the flag"). The Floor guarantees these are present as *text* (good, for screen readers) but doesn't check that they're *visible* at adequate contrast for a sighted low-vision reader — the same "legible to every analyst" principle the color-alone rule is built around, applied to contrast instead of hue.

**Severity: HIGH.** Directly touches the mechanisms the spine relies on to satisfy NFR-1 (explainability) and the disclaimer requirement.

**Fix:** Darken `text-faint` to ~`#71798A`-`#6B7480` range (targets ≈4.5:1 on both `panel` and `bg`); keep a separate, even-lighter token only for genuinely decorative/non-informational chrome if needed.

---

### F6 — [HIGH] `mixed` (amber) fails AA body-text contrast: 3.70:1 on panel, 3.38:1 on bg

**Where:** DESIGN.md frontmatter `mixed: '#B4790F'` (line 27); used as one of the 4 sentiment scale colors (`timeline-segment.variants.mixed`, line 102) and, per Call row prose (line 194), for the inline "Mono input — turns unattributed" warning text color.

**Computed:** `mixed` on `panel` = **3.70:1**; on `bg` = **3.38:1**. Fails 4.5:1 AA whenever used as text (e.g., the mono-input warning), passes the looser 3:1 threshold only for large/UI-graphical use (e.g., as a segment fill, which is acceptable).

**The gap:** `mixed` is fine as a solid fill (UI component, 3:1 threshold, passes) but is documented as *also* coloring inline warning text ("Mono input…"), where the 4.5:1 text threshold applies and it fails. `negative` (5.51/5.04) and `positive` (5.31/4.86) both clear 4.5:1 comfortably as text; `mixed` is the outlier of the three "real" polarity colors.

**Severity: HIGH.** One of the four core sentiment states is measurably harder to read as text than its siblings — an inconsistency that matters given the scale's whole job is equal legibility across states.

**Fix:** Darken `mixed` slightly for text contexts (e.g., `#96650C`, ≈4.6:1 on panel) or restrict `mixed` to fills/badges only and use a separate darker amber (or `text` + an amber icon) wherever it appears as inline warning copy.

---

### F7 — [HIGH] No visible focus state is specified anywhere, despite a "keyboard-complete" claim

**Where:** EXPERIENCE.md Accessibility Floor line 79 ("Keyboard-complete. Every interaction in Interaction Primitives has a keyboard path; the timeline, transcript, and acoustic panels are not mouse-only"); Interaction Primitives lines 71–74 (arrow-key timeline nav, Enter/Space row activation); DESIGN.md frontmatter — no `focus` color token, no outline/ring spec anywhere in `colors`, `components`, or prose; the only appearance of the word "focus" in DESIGN.md is `icon-button`'s hover/focus-*reveal* trigger (line 196, "revealed on hover/focus"), which is about visibility of the control, not what focus looks like once revealed.

**The gap:** "Keyboard-complete" is a functional claim (every interactive element reachable and operable by keyboard) but the spine never specifies what a keyboard user *sees* when focus lands somewhere — no focus ring color, width, offset, or `:focus-visible` treatment for call rows, transcript turns, timeline segments, or the icon-button. This matters more than usual here because: (a) the layout is unusually dense (2px-based spacing scale, `row-padding` 12px) so a default browser outline risks being clipped or visually lost between hairline borders (`border-subtle` at 1.13:1 contrast is already nearly invisible itself); (b) the near-black `chrome` header and light `panel` content areas would need two different focus treatments to stay visible against both; (c) EXPERIENCE.md calls this "a keyboard-driven analyst tool by nature" (line 73) — a claim contradicted by having no visual keyboard-state spec at all.

**Severity: HIGH.** Doesn't itself hide an uncertainty *state*, but it's a specified-but-unimplementable accessibility claim — a downstream implementer has nothing to build against, and the likely failure mode (relying on browser defaults, or worse, a reset stylesheet that suppresses outlines) is common enough to flag explicitly.

**Fix:** Add a `focus` token (e.g., a 2px solid ring in a color that meets 3:1 against both `panel` and `chrome` — `chrome` itself, at 8.4:1 against panel per the negative/positive text checks' neighborhood, would work well as a focus-ring color on light surfaces; `chrome-text-strong` or a dedicated accent would be needed on the dark header) and specify it applies uniformly to call rows, transcript turns, timeline segments (each segment individually focusable per the arrow-key requirement), and icon-button.

---

### F8 — [HIGH] `low-confidence` token itself is very low contrast: 2.05:1 on panel, 1.88:1 on bg — the border/underline meant to signal it is nearly invisible

**Where:** DESIGN.md frontmatter `low-confidence: '#AEB6BE'` (line 30); used in `transcript-turn.variants.low-confidence` ("left border 2px dashed {colors.low-confidence}", line 112), `speaker-label.variants.uncertain` ("dashed underline {colors.low-confidence}", line 138), `tag.variants.low` border (line 118).

**Computed:** `low-confidence` on `panel` = **2.05:1**; on `bg` = **1.88:1**; against `low-confidence-hatch-a` (its own tag background) = **1.67:1**. All fail the 3:1 UI-component/graphical-object threshold, several fail it badly.

**The gap:** This is the actual line-art used to flag low-confidence in the two places the Accessibility Floor most needs it to be visible: a transcript turn's left border (which a sighted analyst scans down a long list looking for) and a speaker label's underline. At ~2:1 contrast, a low-vision analyst — someone the "never hides uncertainty from any analyst" principle explicitly exists to protect — is likely to miss both. Combined with F2 (the hatch pattern colors being 1.19:1 apart), essentially every rendering of "low-confidence" in this palette is under-contrast relative to its surface.

**Severity: HIGH.** Same category as F2: undermines the specific mechanism built to satisfy the product's own hard accessibility requirement.

**Fix:** Introduce a second, higher-contrast gray for line-art/borders distinct from the current `low-confidence` fill token (e.g., a border-specific `low-confidence-border: #7C868F`, ≈3.3:1 on panel) while keeping the existing lighter tone for fills/backgrounds where large-area contrast matters less.

---

### F9 — [MEDIUM] `neutral-signal` fails the 3:1 UI-component threshold: 2.59:1 on panel, 2.37:1 on bg

**Where:** DESIGN.md frontmatter `neutral-signal: '#98A2AC'` (line 29); `timeline-segment.variants.neutral` (line 101); Colors prose line 160 ("`neutral-signal` (gray) is a real semantic value (calm/neutral emotion)… kept visually distinct from `text-faint`").

**Computed:** `neutral-signal` on `panel` = **2.59:1**; on `bg` = **2.37:1**; both fail 3:1.

**The gap:** DESIGN.md is explicit that `neutral-signal` must read as a *real reading*, not a disabled/placeholder gray — but at this contrast, a "neutral" timeline segment risks visually reading as empty/unfilled/disabled space, especially adjacent to the higher-contrast `negative`/`positive`/`mixed` segments (5.5/5.3/3.7:1 respectively), which is precisely the misreading the prose says it's trying to avoid. It's also numerically closer to `text-faint` (2.85:1 self-contrast between the two — barely distinguishable) than the "kept visually distinct from text-faint" claim implies for a low-vision viewer, even though the hex values are different.

**Severity: MEDIUM.** Doesn't hide a state outright (it's still a distinct hue for colorblind-safe hue separation isn't relied on here since this is about contrast, not hue confusion), but works against the component's own explicit design intent.

**Fix:** Darken `neutral-signal` toward `#7C8894`–`#828C96` (~3.3–3.6:1 on panel) to clear the 3:1 UI threshold and increase separation from `text-faint`.

---

### F10 — [MEDIUM] Timeline keyboard navigation is specified; screen-reader announcement of segment state is not

**Where:** EXPERIENCE.md Interaction Primitives line 72 ("Timeline scrub/select — click or keyboard-navigate (arrow keys, when focused) between segments; selecting a segment scrolls the transcript panel… and highlights… a single action synchronizes all three panels"); Component Patterns line 49 (timeline as "primary navigation device"); Accessibility Floor lines 78–79 (color-alone and keyboard-complete claims, no ARIA/announcement language anywhere in either document).

**The gap:** Keyboard *operability* of the timeline is specified (arrow keys move focus between segments), which is good, but keyboard-focusable is not the same as screen-reader-legible. Neither document says what a screen reader announces when focus lands on a segment — its time range, its sentiment/emotion state, its confidence, whether it's flagged low-confidence or disagreement. Without an accessible name/description per segment (e.g., "Segment 3 of 12, 02:14–02:40, Negative, confidence 0.71" or "…, Low confidence, reason: overlapping cross-talk"), a screen-reader user can tab through the timeline and hear nothing that conveys what the sighted hatch/split-fill/color encoding conveys. The transcript panel (turn-by-turn, with `tag` text) is a plausible redundant path to the same information, but the two structures aren't guaranteed to align 1:1 — "each segment represents a contiguous span of consistent reading" (Component Patterns, line 49 context) vs. "one row per speaker turn" (line 51) are different units of granularity, so segment-level state isn't guaranteed to be fully recoverable by reading the transcript alone.

**Severity: MEDIUM.** Real gap in non-visual access to the product's headline evidence surface, but partially mitigated by the transcript being a plausible (if unconfirmed) redundant path.

**Fix:** Specify that each timeline segment carries an accessible name stating time range, state, and (when applicable) flag reason, and explicitly state in EXPERIENCE.md that the transcript list is a guaranteed complete non-visual equivalent to the timeline (or, if segment/turn granularity can diverge, that segment boundaries are also individually announced).

---

### F11 — [MEDIUM] Speaker-label `uncertain` vs. transcript-turn `low-confidence` are structurally distinct but share the same low-contrast token and dash style

**Where:** DESIGN.md frontmatter `speaker-label.variants.uncertain`: "foreground {colors.text-faint}, dashed underline {colors.low-confidence}" (line 138); `transcript-turn.variants.low-confidence`: "left border 2px dashed {colors.low-confidence}, background {colors.panel-subtle}" (line 112); Components prose line 195 ("deliberately a *lighter-weight* treatment… the two must never look identical"); EXPERIENCE.md State Patterns line 67 (must be "legible independently").

**The gap:** The two states genuinely differ in structure — position (underline on a ~2-word label vs. a border running the full height of a transcript row), scope (name-only vs. whole-turn), and an added background shift (`panel-subtle`) for the sentiment case only — so this is not "just a different color intensity of the same idea" as literally read; there is a real shape/scope distinction. However, both indicators are rendered in the *same* dash style and the *same* `low-confidence` color token, which per F8 is only ~2:1 contrast against panel/bg. If that token is hard to see at all for a low-vision reader, the distinguishing structural cues (underline vs. border) may not register either, since both depend on perceiving the same faint dashed line. At that point the only remaining differentiator is `text-faint` foreground on the speaker name — a subtle, easily-missed cue on its own.

**Severity: MEDIUM.** Design intent is sound and correctly separates the two uncertainty axes; the shared low-contrast palette is what puts the "must never look identical" guarantee at risk for exactly the population (low vision) the guarantee is supposed to protect.

**Fix:** Once `low-confidence` contrast is fixed (F8), also differentiate the *line style* itself (e.g., dotted underline for speaker uncertainty vs. dashed border for sentiment low-confidence, not the same dash pattern in two places) so the two remain distinguishable even for a viewer who can only perceive shape, not fine hue/weight differences.

---

### F12 — [MEDIUM] Small text sizes vs. the Accessibility Floor's own "Text scaling" requirement

**Where:** DESIGN.md frontmatter `typography.label` (10px, line 40), `typography.data-inline` (10.5px, line 61), `typography.data-sm` (11px, line 57); EXPERIENCE.md Accessibility Floor line 80 ("Text scaling. The dense typographic scale (10–13px body/data) must remain legible and non-overlapping up to standard OS-level text-scaling… validate this specifically given how tight the spacing scale is").

**Correction to the brief's premise:** the smallest size actually present in the frontmatter is **10px** (`label`), not 8.5px — there is no 8.5px value anywhere in the typography scale as documented. Flagging this discrepancy for accuracy; the substantive tension below holds regardless.

**The gap:** EXPERIENCE.md is unusually self-aware here — it names the tension directly ("validate this specifically") rather than ignoring it, which is good practice. But "must remain legible… up to standard OS-level text-scaling" is asserted as a requirement without a concrete target (e.g., "legible and non-overlapping at 200% OS text scaling," which is the actual WCAG 1.4.4 benchmark) and without any accompanying layout guidance for what happens to the tight 2px-based spacing scale (`spacing.1`–`spacing.8`, 4–18px) when text at 10px grows to 20px under scaling — dense structures like `transcript-turn` (`row-padding` 8px per spacing scale) and `call-row` are the most exposed. For an "all-day analyst tool," 10px/10.5px base sizes are already below common practical minimums (~12–14px) even before scaling is considered.

**Severity: MEDIUM.** Honestly, this is a real, named tension in the spine as written, not a hypothetical — EXPERIENCE.md flags it but doesn't resolve it, which is better than silence but still leaves it unresolved for implementation.

**Fix:** Set an explicit validation target (e.g., "legible and non-overlapping at 200% OS-level text scaling on the transcript and call-list views specifically") and consider raising the 10px `label` floor to 11–12px given the product's all-day, high-stakes-review use case; reserve the tightest sizes for genuinely secondary metadata only.

---

### F13 — [LOW] `negative-border` is very low contrast against its own tag background and against panel (1.50:1 / 1.76:1)

**Where:** DESIGN.md frontmatter `negative-border: '#E8B8B2'` (line 26); `tag.variants.conflict` border (line 119); Colors prose line 162.

**The gap:** The `conflict` tag's border is nearly invisible against both its own `negative-bg` fill and the surrounding `panel`. However, the tag's foreground text ("CONFLICT") is rendered in `negative` at 4.70:1 against `negative-bg` (passes AA), so the tag remains legible via its text and fill regardless of the border. Border is a "nice to have" outline here, not the primary legibility mechanism.

**Severity: LOW.** Cosmetic/definition-boundary issue, not an uncertainty-hiding one, since text carries the meaning.

**Fix:** Darken `negative-border` if a visible outline is desired (e.g., toward `#D89890`), or accept it as a subtle boundary since the tag doesn't depend on it for legibility.

---

### F14 — [LOW] Icon-button destructive-hover relies on a color shift, but the icon shape itself is stable

**Where:** DESIGN.md frontmatter `icon-button.foreground-destructive-hover: '{colors.negative}'` (line 144); Components prose line 196 ("a destructive-hover state (red foreground) only on the delete action").

**The gap:** The hover-state color change (default gray → red on hover) is, in isolation, a color-only signal. But the button's icon (presumably a trash/delete glyph) and its function are constant and already identify it as "delete" independent of color — the red hover is reinforcement/confirmation, not the sole conveyor of "this is destructive." This is a materially different situation from F1/F2/F3/F8, where color is doing the entire identification job.

**Severity: LOW.** Minor, but flagged for completeness since the review explicitly asked about this control.

**Fix:** No urgent change needed; optionally add a `:focus-visible`/hover text tooltip ("Delete call") for extra clarity, consistent with F7's broader focus-state gap.

---

## Summary table

| # | Finding | Severity |
|---|---|---|
| F1 | Base 4-color Sentiment/Emotion scale is color-alone on the timeline | Critical |
| F2 | Low-confidence hatch pattern's two fill colors are 1.19:1 apart — pattern likely invisible | Critical |
| F3 | `badge-dot` has no documented color mapping and isn't named in the Accessibility Floor | High |
| F4 | `text-label` fails AA text contrast (3.62:1 / 3.31:1) — used site-wide for section/field labels | High |
| F5 | `text-faint` fails AA text contrast (3.12:1 / 2.85:1) — disclaimer bar + flag reasons | High |
| F6 | `mixed` (amber) fails AA text contrast (3.70:1 / 3.38:1) as inline warning copy | High |
| F7 | No visible focus state specified anywhere, despite "keyboard-complete" claim | High |
| F8 | `low-confidence` token itself is 2.05:1/1.88:1 — border/underline nearly invisible | High |
| F9 | `neutral-signal` fails 3:1 UI-component threshold (2.59:1 / 2.37:1) | Medium |
| F10 | No specified screen-reader announcement for timeline segment state | Medium |
| F11 | Speaker-uncertain vs. sentiment-low-confidence share the same low-contrast token/dash style | Medium |
| F12 | Small text sizes (10–10.5px) vs. Text-scaling requirement — named tension, unresolved target | Medium |
| F13 | `negative-border` low contrast, but mitigated by tag text contrast | Low |
| F14 | Icon-button destructive-hover is color-reinforced but not color-dependent (icon stays stable) | Low |

**Totals:** 2 Critical, 6 High, 4 Medium, 2 Low.

---

## Bottom line

The spine's stated principle — no analyst should be silently excluded from an uncertainty signal — is real and specific, and the *design* of the two special states (hatch pattern, split-fill + dual-signal panel) is the right shape of solution: structural/shape encoding, not just hue. The failure is in execution, concentrated in two places: (1) the base 4-color sentiment scale was never given the same non-color treatment the special states got, so the single most common thing an analyst reads relies on color alone at the moment it matters most (fast triage), and (2) the specific gray tokens chosen to carry the "non-color" signals (`low-confidence`, `low-confidence-hatch-a/b`, `text-faint`, `text-label`, `neutral-signal`) are themselves too low-contrast to reliably render for low-vision readers — so the accessibility mechanisms the spine is proud of are, as specified, at risk of being nearly invisible rather than just "not colorblind-safe." Fixing the palette contrast (F2, F4–F6, F8, F9) is mechanical and low-risk; fixing F1 (giving the base scale a real non-color encoding) and F7 (specifying a focus state) require actual design decisions and should be prioritized first since they're both Critical/High and neither has an existing partial mechanism to extend.
