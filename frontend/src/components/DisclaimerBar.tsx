import './DisclaimerBar.css'

// Code review (2026-08-16): single source of truth for the fixed disclaimer
// copy, exported so tests assert against this value instead of a second
// hardcoded copy of the string (EXPERIENCE.md Voice and Tone: this text must
// stay byte-identical on every Call, never paraphrased per-instance).
export const DISCLAIMER_TEXT =
  'Model output — acoustic + lexical estimate, not a determination. Analyst review required before action.'

// Story 2.6 (Task 1; AC1): the standing, non-dismissible disclaimer required
// on every Analysis Dashboard that has a result — fixed copy, never
// paraphrased per-instance (EXPERIENCE.md Voice and Tone), never styled as
// a warning/alert (DESIGN.md Do's and Don'ts). No props by design.
export function DisclaimerBar() {
  return <div className="disclaimer-bar">{DISCLAIMER_TEXT}</div>
}
