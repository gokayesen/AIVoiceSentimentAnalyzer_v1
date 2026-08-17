// Story 2.2: the Session Call List's client-held state model. There is no
// `GET /calls` list endpoint (Story 2.1's Dev Notes, still true) — the
// session is built up row-by-row as files are submitted, each row tracked
// here and updated in place as uploadCall/getCallStatus results arrive.
export type CallRowState = 'validating' | 'queued' | 'processing' | 'complete' | 'failed'

export interface SessionCall {
  // A stable identity for this row, generated once at submitFile-time and
  // never reassigned — used as the React list key so a successful upload
  // (which changes `id` below) doesn't force an unnecessary remount (code
  // review, 2026-08-15).
  key: string
  // The real call_id once known (after a successful uploadCall), otherwise
  // a client-generated temporary id used only while state === 'validating'.
  id: string
  // Kept on every row (not just failed ones) so "Retry" (AC4, AC6) is a
  // one-click resubmit instead of forcing the Analyst to re-pick the file.
  file: File
  filename: string
  state: CallRowState
  // Populated on a 'failed' row, regardless of failure origin (validation
  // rejection vs. processing failure) — see the story's Dev Notes "One
  // `failed` state, two failure origins."
  errorMessage?: string
  errorNextStep?: string
  // Populated only once state === 'complete'. `sentiment`/`emotion`/
  // `confidence` stay undefined for a `noSpeechDetected` row (Story 2.4's
  // Task 2 fix) — see the story's own code review, 2026-08-15: rendering
  // this must show a distinct "No speech detected" state, never a blank/
  // broken sentiment badge.
  sentiment?: string
  emotion?: string
  confidence?: number
  noSpeechDetected?: boolean
  // Story 3.4 (AC4/AC5): populated only once `state === 'complete'`, same
  // whole-Call fact the Dashboard's `speaker_attribution_unavailable`
  // (Story 3.3) carries — sourced here from `CallStatusResponse`'s own
  // field of the same name (Task 1's backend addition).
  speakerAttributionUnavailable?: boolean
  durationSeconds?: number
  // Story 2.3: delete lifecycle, orthogonal to `state` — a delete can be
  // requested on a row in any state, and a delete failure must not force the
  // row into the (upload/processing-only) `failed` visual treatment, so this
  // is deliberately not folded into `state`/`errorMessage`/`errorNextStep`.
  deleting?: boolean
  deleteError?: string
  deleteErrorNextStep?: string
}
