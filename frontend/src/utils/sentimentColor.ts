// Shared polarity → token-color mapping (Story 2.4) — the same four
// polarity values CallRow's badge-dot variants already color
// (negative/mixed/positive/neutral, AD-4), reused wherever the Dashboard
// needs a sentiment-driven color without a badge-dot element.
const SENTIMENT_COLOR_VAR: Record<string, string> = {
  negative: 'var(--color-negative)',
  mixed: 'var(--color-mixed)',
  positive: 'var(--color-positive)',
  neutral: 'var(--color-neutral-signal)',
}

export function sentimentColorVar(sentiment: string): string {
  return SENTIMENT_COLOR_VAR[sentiment] ?? 'var(--color-text)'
}

// Fixed glyph per base Timeline variant (mockups/analysis-dashboard.html) —
// never color-alone (DESIGN.md Accessibility Floor).
const SENTIMENT_GLYPH: Record<string, string> = {
  neutral: '–',
  positive: '▲',
  mixed: '◆',
  negative: '▼',
}

export function sentimentGlyph(sentiment: string): string {
  return SENTIMENT_GLYPH[sentiment] ?? '–'
}
