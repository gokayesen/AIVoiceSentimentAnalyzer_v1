import type { KeyboardEvent, MouseEvent } from 'react'
import './CallRow.css'
import type { SessionCall } from '../types/call'
import { formatDuration } from '../utils/formatDuration'
import { capitalize } from '../utils/capitalize'

interface CallRowProps {
  call: SessionCall
  onRetry: (call: SessionCall) => void
  onDeleteRequest: (call: SessionCall) => void
  onSelectCall?: (callId: string) => void
}

const STATUS_WORD: Record<'validating' | 'queued' | 'processing', string> = {
  validating: 'Validating…',
  queued: 'Queued',
  processing: 'Processing…',
}

// Story 2.3 (AC1): the trash icon SVG, transcribed verbatim from
// mockups/session-call-list.html — the only visual reference for this
// element.
function DeleteIcon() {
  return (
    <svg viewBox="0 0 16 16" fill="none" aria-hidden="true">
      <path
        d="M3 4H13M6.5 4V2.5H9.5V4M4.5 4L5 13.5H11L11.5 4"
        stroke="currentColor"
        strokeWidth="1.3"
        strokeLinecap="round"
        strokeLinejoin="round"
      />
    </svg>
  )
}

// Story 2.2 AC7: the Analysis Dashboard doesn't exist yet (Story 2.4) — the
// full click/keyboard interaction contract is built now, but `onSelectCall`
// is a stub extension point, same documented pattern Story 2.1 used for
// AppHeader's `onBreadcrumbClick`.
export function CallRow({ call, onRetry, onDeleteRequest, onSelectCall }: CallRowProps) {
  const handleDeleteClick = (event: MouseEvent<HTMLButtonElement>) => {
    // Story 2.3 (Task 4): must not also fire a `complete` row's own onClick
    // (onSelectCall) — the same click-propagation bug class Story 2.2's code
    // review already found once in this codebase (the `submitFile` ApiError
    // cast issue), applied here to a DOM event instead of a caught value.
    event.stopPropagation()
    onDeleteRequest(call)
  }

  const deleteButton = (
    <button
      type="button"
      className="call-row__icon-button"
      aria-label={`Delete ${call.filename}`}
      onClick={handleDeleteClick}
      // Code review (2026-08-15): the click handler's stopPropagation only
      // covers the mouse path — Enter/Space on a focused button fires a
      // `keydown` that still bubbles to the row's own onKeyDown first (which
      // both selects the row and calls preventDefault, suppressing the
      // button's synthesized click entirely). Stop it here too.
      onKeyDown={(event) => event.stopPropagation()}
    >
      <DeleteIcon />
    </button>
  )

  // Story 2.3 (Task 2): a delete failure is orthogonal to `state` — it can
  // happen to a row in any state, and must not force the row into the
  // (upload/processing-only) `failed` visual treatment.
  const deleteErrorNotice = call.deleteError ? (
    <div className="call-row__delete-error">
      <div className="call-row__delete-error-message">{call.deleteError}</div>
      {call.deleteErrorNextStep && (
        <div className="call-row__delete-error-next-step">{call.deleteErrorNextStep}</div>
      )}
    </div>
  ) : null

  // Story 2.3 (Task 5): checked before the `state`-based branches below —
  // a row mid-delete is never selectable regardless of its underlying state.
  if (call.deleting) {
    return (
      <div className="call-row call-row--pending">
        <div className="call-row__main">
          <div className="call-row__filename">{call.filename}</div>
        </div>
        <div className="call-row__status">Deleting…</div>
      </div>
    )
  }

  if (call.state === 'failed') {
    return (
      <div className="call-row call-row--failed">
        <div className="call-row__main">
          <div className="call-row__filename">{call.filename}</div>
          <div className="call-row__error-message">{call.errorMessage}</div>
          <div className="call-row__error-next-step">{call.errorNextStep}</div>
          {deleteErrorNotice}
        </div>
        <button type="button" className="call-row__retry" onClick={() => onRetry(call)}>
          Retry
        </button>
        {deleteButton}
      </div>
    )
  }

  if (call.state !== 'complete') {
    return (
      <div className="call-row call-row--pending">
        <div className="call-row__main">
          <div className="call-row__filename">{call.filename}</div>
          {deleteErrorNotice}
        </div>
        <div className="call-row__status">{STATUS_WORD[call.state]}</div>
        {deleteButton}
      </div>
    )
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelectCall?.(call.id)
    }
  }

  // Code review (2026-08-16, Story 2.7): role="button" makes the accessible
  // name computed from content by default, which recurses into the nested
  // delete <button> and bleeds "Delete <filename>" into the row's own name.
  // An explicit aria-label short-circuits that recursion entirely (per the
  // ARIA accname spec, an aria-label present on an element skips
  // content-based name computation, including from descendants).
  // Code review (2026-08-17, Story 3.4): the attribution-warning div below
  // is a descendant of this row and would otherwise be silently dropped
  // from the accessible name by the same aria-label short-circuit the
  // comment above describes — appended here so screen-reader users get the
  // same "Mono input — turns unattributed" fact sighted users see.
  const attributionSuffix = call.speakerAttributionUnavailable ? ', mono input, turns unattributed' : ''
  const rowAccessibleLabel = call.noSpeechDetected
    ? `${call.filename}, no speech detected, ${formatDuration(call.durationSeconds ?? 0)}${attributionSuffix}`
    : `${call.filename}, ${capitalize(call.sentiment ?? '')} · ${capitalize(call.emotion ?? '')}, confidence ${call.confidence?.toFixed(2)}, ${formatDuration(call.durationSeconds ?? 0)}${attributionSuffix}`

  return (
    <div
      className="call-row call-row--complete"
      role="button"
      aria-label={rowAccessibleLabel}
      tabIndex={0}
      onClick={() => onSelectCall?.(call.id)}
      onKeyDown={handleKeyDown}
    >
      <div className="call-row__main">
        <div className="call-row__filename">{call.filename}</div>
        {/* Code review (2026-08-15, Story 2.4): a no-speech-detected complete
        Call has no sentiment/emotion/confidence to show — rendering the
        badge-dot line for it would print a blank/broken "· " instead of an
        honest state (AD-16: never fabricate certainty over an absence of
        data). */}
        {call.noSpeechDetected ? (
          <div className="call-row__sentiment">No speech detected</div>
        ) : (
          <div className="call-row__sentiment">
            <span className={`call-row__badge-dot call-row__badge-dot--${call.sentiment}`} aria-hidden="true" />
            {capitalize(call.sentiment ?? '')} · {capitalize(call.emotion ?? '')}
          </div>
        )}
        {/* Story 3.4 (AC4/AC5): the same "Mono input — turns unattributed"
        copy the Dashboard shows (Story 2.6), populated only under the real
        whole-Call "attribution unavailable" condition (Story 3.3/3.4) —
        never a default/placeholder shown on every row. */}
        {call.speakerAttributionUnavailable ? (
          <div className="call-row__attribution-warning">Mono input — turns unattributed</div>
        ) : null}
        {deleteErrorNotice}
      </div>
      <div className="call-row__side">
        <div className="call-row__confidence">{call.noSpeechDetected ? null : call.confidence?.toFixed(2)}</div>
        <div className="call-row__duration">{formatDuration(call.durationSeconds ?? 0)}</div>
      </div>
      {deleteButton}
    </div>
  )
}
