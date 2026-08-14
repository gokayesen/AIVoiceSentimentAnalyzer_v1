---
name: AI Voice Sentiment Analyzer
description: Clinical, data-dense analyst console for reviewing AI voice/sentiment analysis of customer service calls. Near-black monitoring-console chrome over light data panels; monospaced numerals for every score, confidence value, and timestamp so figures read like instrument readouts. Light mode only for MVP.
status: final
sources:
  - '{planning_artifacts}/prds/prd-AIVoiceSentimentAnalyzer_v1-2026-08-10/prd.md'
  - '{planning_artifacts}/briefs/brief-AIVoiceSentimentAnalyzer_v1-2026-08-09/brief.md'
  - '{planning_artifacts}/research/technical-voice-sentiment-analyzer-research-2026-08-10.md'
updated: 2026-08-10
colors:
  bg: '#F3F5F7'
  panel: '#FFFFFF'
  panel-subtle: '#F7F8F9'
  chrome: '#0B0F14'
  chrome-secondary: '#161C24'
  chrome-text: '#B9C3CC'
  chrome-text-strong: '#E7ECF1'
  border: '#D8DEE4'
  border-subtle: '#EEF1F3'
  text: '#12181F'
  text-dim: '#5B6672'
  text-faint: '#6E7686'
  text-label: '#5F6B77'
  negative: '#C1352A'
  negative-bg: '#FBE9E7'
  negative-border: '#D89890'
  mixed: '#96650C'
  positive: '#23795A'
  neutral-signal: '#7C8894'
  low-confidence: '#AEB6BE'
  low-confidence-border: '#7C868F'
  low-confidence-hatch-a: '#F2F4F6'
  low-confidence-hatch-b: '#8A939C'
  focus-ring: '#0B0F14'
  focus-ring-on-chrome: '#E7ECF1'
typography:
  body:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    fontSize: 13px
    lineHeight: '1.45'
  label:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    fontSize: 11px
    fontWeight: '700'
    letterSpacing: 0.07em
  heading-sm:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    fontSize: 15px
    fontWeight: '700'
  heading-md:
    fontFamily: '-apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif'
    fontSize: 20px
    fontWeight: '700'
  data:
    fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace'
    fontSize: 18px
    fontWeight: '600'
  data-sm:
    fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace'
    fontSize: 11px
    fontWeight: '600'
  data-inline:
    fontFamily: 'ui-monospace, SFMono-Regular, "SF Mono", Menlo, Consolas, monospace'
    fontSize: 11px
    fontWeight: '400'
rounded:
  sm: 2px
  md: 3px
  lg: 4px
  DEFAULT: 3px
  full: 9999px
spacing:
  '1': 4px
  '2': 6px
  '3': 8px
  '4': 10px
  '5': 12px
  '6': 14px
  '7': 16px
  '8': 18px
  panel-padding: '{spacing.8}'
  row-padding: '{spacing.5}'
components:
  app-header:
    background: '{colors.chrome}'
    foreground: '{colors.chrome-text}'
    foreground-wordmark: '{colors.chrome-text-strong}'
    padding: '{spacing.4} {spacing.8}'
    breadcrumb: 'clickable — returns analyst to Session Call List; see EXPERIENCE.md Interaction Primitives'
  case-strip:
    background: '{colors.panel}'
    border-bottom: '1px solid {colors.border}'
    padding: '{spacing.5} {spacing.8}'
  summary-cell:
    background: '{colors.panel}'
    label-color: '{colors.text-label}'
    value-typography: '{typography.data}'
  disclaimer-bar:
    background: '{colors.bg}'
    foreground: '{colors.text-faint}'
    fontSize: '11px'
    border-bottom: '1px solid {colors.border}'
  timeline-segment:
    radius: '{rounded.sm}'
    variants:
      neutral: 'fill {colors.neutral-signal}; glyph "–" (flat line), foreground {colors.text}'
      mixed: 'fill {colors.mixed}; glyph "◆" (diamond), foreground {colors.panel}'
      negative: 'fill {colors.negative}; glyph "▼" (down triangle), foreground {colors.panel}'
      positive: 'fill {colors.positive}; glyph "▲" (up triangle), foreground {colors.panel}'
      low-confidence: 'repeating 45deg hatch, {colors.low-confidence-hatch-a} / {colors.low-confidence-hatch-b}, dashed border {colors.low-confidence-border}; glyph "?" '
      disagreement: 'split fill 50/50, {colors.neutral-signal} / {colors.negative}; glyph "⚠"'
    note: 'The four base-polarity glyphs (–/◆/▼/▲) are a shape/texture axis independent of hue — required so the base scale is never color-alone, matching the treatment already given to low-confidence and disagreement. Glyphs render small, top-center of each segment, in a fixed ink color (not the segment fill color) so they stay legible regardless of the underlying hue.'
  dual-signal-panel:
    layout: 'two equal-width halves, {spacing.2} gap, each in a bordered box: background {colors.panel-subtle}, border 1px solid {colors.border-subtle}, radius {rounded.md}'
    half-label-typography: '{typography.label}, foreground {colors.text-faint}'
    half-value-typography: '{typography.data-inline}'
    labels: '"Text signal" / "Tone signal" — fixed, never renamed per instance'
  transcript-turn:
    padding: '{spacing.2} {spacing.8}'
    border-bottom: '1px solid {colors.border-subtle}'
    variants:
      default: 'no accent'
      low-confidence: 'left border 2px dashed {colors.low-confidence-border}, background {colors.panel-subtle}'
      disagreement: 'left border 2px solid {colors.negative}'
  tag:
    radius: '{rounded.md}'
    typography: '{typography.data-inline}'
    variants:
      low: 'background {colors.low-confidence-hatch-a}, foreground {colors.text-dim}, border {colors.low-confidence-border}'
      conflict: 'background {colors.negative-bg}, foreground {colors.negative}, border {colors.negative-border}'
  acoustic-metric-bar:
    track-background: '{colors.low-confidence-hatch-a}'
    fill-default: '{colors.text-dim}'
    fill-warn: '{colors.negative}'
    height: 6px
    radius: '{rounded.md}'
  call-row:
    padding: '{spacing.5} {spacing.6}'
    border-bottom: '1px solid {colors.border-subtle}'
    active-background: '{colors.bg}'
    active-accent: '2px solid {colors.chrome}'
  badge-dot:
    size: 7px
    radius: '{rounded.full}'
    variants:
      negative: '{colors.negative}'
      mixed: '{colors.mixed}'
      positive: '{colors.positive}'
      neutral: '{colors.neutral-signal}'
    note: 'Always rendered immediately adjacent to its Sentiment/Emotion text value (never shown alone) — the text, not the dot color, is the source of truth. See EXPERIENCE.md Accessibility Floor.'
  speaker-label:
    typography: '{typography.label}'
    variants:
      default: 'foreground {colors.text-dim}'
      uncertain: 'foreground {colors.text-faint}, dotted underline {colors.low-confidence-border}'
    note: 'The `uncertain` variant uses a dotted underline (vs. transcript-turn low-confidence''s dashed border) so the two independent uncertainty axes stay distinguishable by line style, not just position.'
  icon-button:
    size: 22px
    radius: '{rounded.md}'
    foreground-default: '{colors.text-faint}'
    foreground-hover: '{colors.text}'
    foreground-destructive-hover: '{colors.negative}'
    background: 'transparent, {colors.panel-subtle} on hover'
  confirm-dialog:
    surface: '{colors.panel}'
    overlay: 'rgba(11,15,20,0.4)'
    radius: '{rounded.lg}'
    elevation: '0 8px 24px rgba(11,15,20,0.18)'
    padding: '{spacing.8}'
    note: 'The one elevated surface in the product — see Elevation & Depth. Used for the delete-Call confirmation; no other modal exists in MVP.'
  focus-ring:
    on-light-surface: '2px solid {colors.focus-ring}, 2px offset'
    on-chrome-surface: '2px solid {colors.focus-ring-on-chrome}, 2px offset'
    applies-to: 'call-row, transcript-turn, timeline-segment (individually focusable), icon-button, confirm-dialog actions, app-header breadcrumb'
---

## Brand & Style

This is an analyst's instrument, not a consumer app. The console reads like a monitoring or observability tool: near-black chrome, hairline borders, dense tabular layout, and monospaced numerals on every score, confidence value, and timestamp so figures scan like readouts rather than decoration. Density is intentional — an analyst working a queue of calls needs to triage fast, and this register signals precision over warmth.

Every visual choice reinforces the product's core discipline: this tool produces evidence, not verdicts. Nothing in the interface should look more certain than the underlying analysis is — a design instinct that shows up concretely in how low-confidence and disagreement states are rendered (never hidden, never smoothed over; see Components).

This register (Direction 1 of four rendered options) was selected during Discovery from `.working/directions-1.html`; the token set here reflects that direction plus the accessibility-driven contrast/glyph/focus corrections made at Reviewer Gate (see Do's and Don'ts). Current 1:1 surface renders live in `mockups/` — see EXPERIENCE.md Information Architecture for the full mock-to-surface mapping.

## Colors

The palette is built around a light data surface with dark instrument-panel chrome, not a fully dark theme (light mode only for MVP — see EXPERIENCE.md Foundation). **All text/background pairs target WCAG AA: 4.5:1 for text under ~18px, 3:1 for large text and non-text UI/graphical objects (segment fills, borders, focus rings)** — see Do's and Don'ts.

- **`chrome` / `chrome-secondary` / `chrome-text`** — the app header and the session-list header. This is the only near-black surface in the product; it signals "you are inside the instrument," distinct from the light content panels underneath. Never used for body content — only top-level navigation chrome. **`chrome-text-strong`** is the higher-emphasis tone within that same chrome surface, for the single most prominent element in the chrome (the product wordmark — see Components, App header); `chrome-text` is the default for everything else on chrome (breadcrumb, analyst identity).
- **`border` / `border-subtle`** — hairline dividers, the product's primary hierarchy device in place of shadows (see Elevation & Depth). `border` separates major regions (e.g., header from content); `border-subtle` is the quieter tone used between repeating rows (transcript turns, call-list rows, panel borders).
- **`bg` / `panel` / `panel-subtle`** — the working surface. `panel` (white) is card/row content; `bg` (light gray-blue) is the page background and disclaimer strips; `panel-subtle` is a slightly recessed background for de-emphasized rows (e.g., a low-confidence transcript turn).
- **`negative` / `mixed` / `positive` / `neutral-signal`** — the sentiment/emotion semantic scale. `negative` (red) and `positive` (green) are reserved *exclusively* for Sentiment/Emotion readouts and their direct visual echoes (timeline segments, `badge-dot`) — never used for arbitrary UI accents, so their meaning stays unambiguous. `mixed` (amber, darkened from a typical amber to meet 4.5:1 contrast as text) marks building/secondary signals. `neutral-signal` (gray) is a real semantic value (calm/neutral emotion), not a disabled or placeholder state — kept visually distinct from `text-faint`. Every one of these four also carries a fixed glyph (see `components.timeline-segment`) so the scale is never color-alone.
- **`low-confidence` / `low-confidence-border` / hatch pair** — deliberately *not* a color on the sentiment scale. `low-confidence` is the lighter fill/background tone; `low-confidence-border` is a separate, darker tone reserved for line-art (borders, underlines) where contrast against a light surface matters more than it does for a fill. The hatch pair (`low-confidence-hatch-a`/`-b`) is a deliberately wide light/mid-gray gap so the diagonal texture reads as a visible pattern, not a flat swatch, at small segment sizes. Together these ensure low confidence is never misread as "a calm reading" (which would use `neutral-signal`) or blended with the red/amber/green scale. This is a hard accessibility requirement, not a style choice — see Do's and Don'ts.
- **`negative-bg` / `negative-border`** — the "conflict" tag surface only. A deliberately louder, higher-alarm treatment than a plain negative reading — a signal *disagreement* is a different kind of event entirely (see NFR-1/FR-11 in the PRD). The tag's legibility comes from its text/fill contrast, not the border, which is a subtle boundary only.
- **`text` / `text-dim` / `text-faint` / `text-label`** — a four-step gray scale for hierarchy: primary content, secondary content, disclaimers/metadata, and all-caps section labels, in that descending order of emphasis. All four are calibrated to clear 4.5:1 against both `bg` and `panel`.
- **`focus-ring` / `focus-ring-on-chrome`** — see Do's and Don'ts and `components.focus-ring`. Two tokens because the product has two base surfaces (light panels, near-black chrome) that need different-contrast rings.

## Typography

No display/brand typeface — this product does not need a decorative voice; it needs to be trusted. Two families carry the entire interface:

- **`body` / `label` / `heading-*`** — the system UI font stack, used for everything a human reads as prose or a UI label: transcript text, section headers, disclaimers, navigation. `heading-sm`/`heading-md` are reserved headroom in the scale — no MVP surface in this spec currently needs a heading larger than `label`; both stay defined for a future surface (e.g., a page-level title) rather than assigned to a component today.
- **`data` / `data-sm` / `data-inline`** — a monospaced stack, used *exclusively* for numeric/measured values: confidence scores, timestamps, percentages, acoustic metric readouts. This is the product's one strong typographic signal: if it's in monospace, it's a measured value coming from the system; if it's in the system font, it's either human-authored (transcript) or descriptive UI copy. Never mix the two roles.

`label` (11px, 700 weight, uppercase, wide letter-spacing) marks every section header and field label — it's what gives the dense layout scannability without needing larger type. 11px is the floor for any role in this system — nothing goes smaller, given this is an all-day analyst tool, not a glanceable widget (see EXPERIENCE.md Accessibility Floor for the OS text-scaling target).

## Layout & Spacing

A tight 2px-based scale (`{spacing.1}` through `{spacing.8}`, 4px–18px) — deliberately finer-grained than a typical 8px/4px-based product scale, because this is a data-dense console where an analyst benefits from seeing more at once, not a spacious marketing surface. `panel-padding` (18px) is the outer breathing room for cards and headers; `row-padding` (12px) is used inside dense repeating structures (transcript turns, call-list rows, acoustic metrics).

The Analysis Dashboard's main content uses a two-column grid (transcript ~60%, acoustic insights ~40%) below a full-width timeline and a four-cell summary row — see EXPERIENCE.md Information Architecture for the surface-level layout, Component Patterns for how each region behaves, and Responsive & Platform for narrower-viewport behavior.

## Elevation & Depth

Flat by design everywhere except one: `confirm-dialog` (the delete-Call confirmation) is the only elevated surface in the product — a soft shadow (`0 8px 24px rgba(11,15,20,0.18)`) over a dimmed overlay (`rgba(11,15,20,0.4)`), lifting it clearly above the otherwise flat, bordered-panel visual language everywhere else. No other component in this system uses a shadow; hierarchy elsewhere is carried entirely by hairline borders (`border`/`border-subtle`) and background-tone shifts (`panel`/`panel-subtle`/`bg`), consistent with the clinical, instrument-panel register.

## Shapes

Corners stay small and consistent: `{rounded.sm}` (2px) for the tightest elements (timeline segment joins), `{rounded.md}`/`{rounded.lg}` (3–4px) for cards, tags, metric bars, and the confirm-dialog. Nothing in this product uses a large or pill-shaped radius — soft, rounded shapes read as approachable/consumer-grade, which works against the clinical-instrument register this product deliberately adopts. The one exception is `{rounded.full}` for the small `badge-dot` status indicators, where a true circle is the clearest way to read "status dot" at 7px.

## Components

- **App header** — near-black chrome bar. Left: product wordmark (`chrome-text-strong`). Center: a monospace breadcrumb (queue/case path) — click behavior specified in EXPERIENCE.md Interaction Primitives. Right: analyst identity (name + role, no login/account UI — MVP has no auth per PRD §2.3).
- **Case strip** — the case identifier row directly under the header: filename, duration, queue name, "analyzed N ago," all in `label`/`data-sm` typography.
- **Summary cells** — a four-cell row: Overall Sentiment, Dominant Emotion (+ Confidence), Secondary Signal, Segments Flagged. Each cell is `label` over `data` — this is the only place large (18px) monospace numerals appear, reserved for the single most important reading on the page.
- **Disclaimer bar** — a persistent, quiet strip directly under the summary cells stating the output is a model estimate requiring analyst review (exact copy owned by EXPERIENCE.md Voice and Tone) — always present, never dismissible, never styled as an alert (it's a standing fact about the product, not a warning).
- **Timeline segment** — the four base Sentiment/Emotion variants (`neutral`/`mixed`/`negative`/`positive`) each carry both a fill color *and* a fixed glyph (`–`/`◆`/`▼`/`▲`) — the glyph, not the color, is the primary signal a colorblind analyst reads. The two special states (`low-confidence` hatch, `disagreement` split-fill) layer on top of this same glyph system (`?` and `⚠` respectively) and remain visually distinct from every base variant *and* from each other — a low-confidence segment must never be mistaken for a disagreement segment or a neutral reading.
- **Dual-signal panel** (`{components.dual-signal-panel}`) — the canonical rendering of FR-11 (disagreement), promoted to its own spec since it's the mechanism keeping a load-bearing PRD requirement visually legible: two equal, bordered halves labeled "Text signal" / "Tone signal," each showing its own value and confidence in `data-inline`. Never collapses to one blended number.
- **Transcript turn** — timestamp (`data-inline`) + speaker label (`label`) + text (`body`). The `low-confidence` variant uses a dashed left border in `low-confidence-border`; the `disagreement` variant uses a solid `negative` left border and contains the `dual-signal-panel`.
- **Tag** (`low`, `conflict`) — small inline badges attached to a flagged transcript turn, always paired with a one-line flag reason in `text-faint` (e.g., "utterance < 1.2s, overlapping cross-talk").
- **Acoustic metric bar** — label + measured value (`data-inline`) over a horizontal bar; `fill-warn` (red) is used when a metric is cited as contributing evidence to a negative/conflict reading, `fill-default` (gray) otherwise. Always paired with a short note tying the acoustic panel back to the specific transcript moment it supports.
- **Call row** — session call-list row: filename (`data-sm`), sentiment/emotion with `badge-dot` (see below), confidence + duration right-aligned, a trailing `icon-button` (delete/remove) revealed on hover/focus rather than permanently visible, to keep the dense list quiet by default. An `active` row gets a background shift and a left accent bar. A row without available speaker attribution shows a small `mixed`-colored inline warning ("Mono input — turns unattributed") rather than hiding the limitation (see EXPERIENCE.md State Patterns).
- **Badge dot** (`{components.badge-dot}`) — four color variants matching the Sentiment/Emotion scale, always rendered immediately next to its Sentiment/Emotion text label in the Call row; never used without that adjacent text (see EXPERIENCE.md Accessibility Floor).
- **Speaker label** (`{components.speaker-label}`) — the "Agent"/"Customer" label inside a transcript turn. Its `uncertain` variant (muted color + *dotted* underline in `low-confidence-border`) is deliberately both a lighter-weight *and* a differently-styled treatment than the transcript-turn `low-confidence` variant's *dashed* border — the two must never look identical, since they flag independent kinds of uncertainty (diarization confidence vs. Sentiment/Emotion confidence; see EXPERIENCE.md State Patterns).
- **Icon button** (`{components.icon-button}`) — the only non-data-dense interactive control in the system (used for the Call row / Dashboard delete action). Transparent by default so it doesn't compete with the dense data around it; a destructive-hover state (red foreground) only on the delete action — the icon shape itself (not just the hover color) already identifies the action as delete.
- **Confirm dialog** (`{components.confirm-dialog}`) — the delete-Call confirmation. The only modal in the product (see Elevation & Depth). Contains the Call's filename, a warning that deletion is immediate and unrecoverable (no persistent history — PRD §10), and two actions (Cancel / Delete).
- **Focus ring** (`{components.focus-ring}`) — applies uniformly to every interactive element (`call-row`, `transcript-turn`, `timeline-segment` — individually focusable — `icon-button`, `confirm-dialog` actions, the `app-header` breadcrumb). Two variants for the two base surfaces (see Colors).

## Do's and Don'ts

- **Do** keep `negative`/`mixed`/`positive`/`neutral-signal` reserved exclusively for actual Sentiment/Emotion readings — never repurpose them as generic UI accent colors.
- **Do** render every one of the four base timeline-segment variants with its fixed glyph, not fill color alone — the glyph is the primary signal for a colorblind reader; color is reinforcement.
- **Do** always pair the `low-confidence` hatch pattern with its `low-confidence-border` dashed border and `?` glyph — the pattern must survive grayscale/colorblind viewing on its own, not rely on hue alone (see EXPERIENCE.md Accessibility Floor).
- **Do** render every disagreement (FR-11) as the `dual-signal-panel` — never average acoustic and text signals into a single displayed number.
- **Do** target WCAG AA (4.5:1 text, 3:1 large-text/UI-boundary) for every color pair in this spec — every token above was calibrated against this bar; any new token added downstream must be checked against it too, not assumed safe by eye.
- **Don't** use the monospace `data` family for anything that isn't a measured/numeric system output — mixing it into prose or labels breaks the one typographic signal the product relies on.
- **Don't** style the disclaimer bar as a warning/alert — it is a standing, permanent statement about the product's nature (NFR-2, NFR-4), not a transient notification.
- **Don't** introduce a large or pill-shaped corner radius anywhere — it conflicts with the clinical register this direction was chosen for.
- **Don't** add a dark-mode variant for MVP — light mode only (confirmed decision; chrome bars are near-black by design, not a dark-theme toggle).
- **Don't** ship any focusable element without its `focus-ring` treatment — a browser-default outline is not sufficient given the layout's dense hairline borders (outlines can be visually lost between 1px borders); every interactive element must show one of the two specified ring variants.
