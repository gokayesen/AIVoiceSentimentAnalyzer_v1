import { useCallback, useRef, useState, type ChangeEvent, type DragEvent } from 'react'
import './SessionCallList.css'
import { CallRow } from '../components/CallRow'
import { ConfirmDialog } from '../components/ConfirmDialog'
import { ApiError, deleteCall, uploadCall, type CallStatusResponse } from '../api/callsApi'
import { useCallStatusPolling } from '../hooks/useCallStatusPolling'
import type { SessionCall, CallRowState } from '../types/call'

// AD-20 formats — a UX nicety only (bypassable via drag-and-drop), never a
// substitute for web-api's own authoritative validation (Story 1.1).
const ACCEPTED_FILE_EXTENSIONS = '.wav,.mp3,.m4a'

interface SessionCallListProps {
  // Story 2.4 (Task 7): opens the Analysis Dashboard for a `complete` row —
  // `CallRow`'s own click/keyboard wiring (Story 2.2) already gates this to
  // the `complete`-state branch only. Optional so this component still
  // renders standalone in any test/context that doesn't need navigation.
  onSelectCall?: (callId: string) => void
}

/**
 * The Session Call List — default landing surface (AC1). Story 2.2 wires
 * real uploads: the list is client-held session state (Story 2.1's model,
 * unchanged — no `GET /calls` list endpoint exists), built up row-by-row as
 * files are submitted via the file picker or drag-and-drop.
 */
export function SessionCallList({ onSelectCall }: SessionCallListProps = {}) {
  const [calls, setCalls] = useState<SessionCall[]>([])
  const [pendingDeleteCall, setPendingDeleteCall] = useState<SessionCall | null>(null)
  const fileInputRef = useRef<HTMLInputElement>(null)

  const updateCall = useCallback((id: string, patch: Partial<SessionCall>) => {
    setCalls((prev) => prev.map((call) => (call.id === id ? { ...call, ...patch } : call)))
  }, [])

  const submitFile = useCallback((file: File) => {
    const tempId = crypto.randomUUID()
    const newRow: SessionCall = {
      key: tempId,
      id: tempId,
      file,
      filename: file.name,
      state: 'validating',
    }
    setCalls((prev) => [...prev, newRow])

    uploadCall(file)
      .then(({ call_id, status }) => {
        setCalls((prev) =>
          prev.map((call) =>
            call.id === tempId ? { ...call, id: call_id, state: status as CallRowState } : call,
          ),
        )
      })
      .catch((err: unknown) => {
        // A real ApiError (validation rejection) carries backend passthrough
        // copy — anything else (network failure, CORS block, a malformed
        // response body) is not, and must not be rendered as if it were
        // (code review, 2026-08-15: the previous blind cast let a raw
        // browser error string and an undefined next-step reach the row).
        if (err instanceof ApiError) {
          updateCall(tempId, {
            state: 'failed',
            errorMessage: err.message,
            errorNextStep: err.next_step,
          })
        } else {
          updateCall(tempId, {
            state: 'failed',
            errorMessage: 'Could not reach the server.',
            errorNextStep: 'Check your connection and try again.',
          })
        }
      })
  }, [updateCall])

  const handleRetry = useCallback(
    (call: SessionCall) => {
      // Re-submits the same File via the same upload path used for a first
      // attempt — removes the failed row so one logical attempt never
      // leaves two rows behind (Dev Notes "Retry semantics").
      setCalls((prev) => prev.filter((c) => c.id !== call.id))
      submitFile(call.file)
    },
    [submitFile],
  )

  const handlePollUpdate = useCallback(
    (callId: string, status: CallStatusResponse) => {
      if (status.status === 'complete') {
        updateCall(callId, {
          state: 'complete',
          // Code review (2026-08-15): a `no_speech_detected` complete Call
          // (Story 2.4's Task 2 fix) carries no overall_* fields at all —
          // leaving `sentiment`/`emotion`/`confidence` undefined here and
          // threading `noSpeechDetected` through lets CallRow render a
          // distinct, honest state instead of a blank sentiment badge.
          noSpeechDetected: status.no_speech_detected,
          sentiment: status.overall_sentiment,
          emotion: status.overall_emotion,
          confidence: status.overall_confidence,
          durationSeconds: status.duration_seconds,
          // Story 3.4 (AC4): threaded straight through from
          // CallStatusResponse into CallRow's own prop of the same name.
          speakerAttributionUnavailable: status.speaker_attribution_unavailable,
        })
      } else if (status.status === 'failed') {
        // Story 1.2/1.3 never persist a failure reason — this is authored
        // UI copy, not a passthrough (Dev Notes "Processing-failure copy").
        updateCall(callId, {
          state: 'failed',
          errorMessage: 'This call could not be analyzed.',
          errorNextStep: 'Try uploading it again.',
        })
      } else {
        updateCall(callId, { state: status.status as CallRowState })
      }
    },
    [updateCall],
  )

  useCallStatusPolling(calls, handlePollUpdate)

  const handleDeleteRequest = useCallback((call: SessionCall) => {
    // Clear any stale error from a previous failed delete attempt on this
    // row before opening a fresh confirmation.
    updateCall(call.id, { deleteError: undefined, deleteErrorNextStep: undefined })
    setPendingDeleteCall(call)
  }, [updateCall])

  const handleCancelDelete = useCallback(() => {
    setPendingDeleteCall(null)
  }, [])

  const handleConfirmDelete = useCallback(() => {
    const call = pendingDeleteCall
    if (!call) {
      return
    }
    setPendingDeleteCall(null)

    // Code review (2026-08-15): a 'validating' row has no real backend
    // call_id yet (its id is a client-generated temp UUID) — sending it
    // through deleteCall would only ever 404. Remove it locally instead;
    // nothing has been persisted server-side to warn about.
    if (call.state === 'validating') {
      setCalls((prev) => prev.filter((c) => c.id !== call.id))
      return
    }

    updateCall(call.id, { deleting: true })

    deleteCall(call.id)
      .then(() => {
        setCalls((prev) => prev.filter((c) => c.id !== call.id))
      })
      .catch((err: unknown) => {
        // Same instanceof-guard pattern as submitFile's catch block (Story
        // 2.2 code review) — a real ApiError carries real backend copy,
        // anything else gets a generic, non-technical fallback.
        if (err instanceof ApiError) {
          updateCall(call.id, {
            deleting: false,
            deleteError: err.message,
            deleteErrorNextStep: err.next_step,
          })
        } else {
          updateCall(call.id, {
            deleting: false,
            deleteError: 'Could not reach the server.',
            deleteErrorNextStep: 'Check your connection and try again.',
          })
        }
      })
  }, [pendingDeleteCall, updateCall])

  const handleFileInputChange = (event: ChangeEvent<HTMLInputElement>) => {
    const file = event.target.files?.[0]
    if (file) {
      submitFile(file)
    }
    // Reset so re-selecting the same file path still fires onChange.
    event.target.value = ''
  }

  const handleDragOver = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
  }

  const handleDrop = (event: DragEvent<HTMLDivElement>) => {
    event.preventDefault()
    const file = event.dataTransfer.files?.[0]
    if (file) {
      submitFile(file)
    }
  }

  const analyzedCount = calls.filter((call) => call.state === 'complete').length

  return (
    <div className="session-call-list">
      <div className="session-strip">
        <div className="session-strip__row">
          <h1 className="session-strip__title">This Session</h1>
          <button
            type="button"
            className="session-strip__add-call"
            onClick={() => fileInputRef.current?.click()}
          >
            + Add call
          </button>
          <input
            ref={fileInputRef}
            type="file"
            accept={ACCEPTED_FILE_EXTENSIONS}
            onChange={handleFileInputChange}
            hidden
          />
        </div>
        <div className="session-strip__subtitle">
          {analyzedCount} calls analyzed this session · not saved after session ends
        </div>
      </div>
      <div className="session-call-list__content" onDragOver={handleDragOver} onDrop={handleDrop}>
        {calls.length === 0 ? (
          <p className="session-call-list__empty-prompt">No calls yet. Add a call to begin.</p>
        ) : (
          calls.map((call) => (
            <CallRow
              key={call.key}
              call={call}
              onRetry={handleRetry}
              onDeleteRequest={handleDeleteRequest}
              onSelectCall={onSelectCall}
            />
          ))
        )}
      </div>
      {pendingDeleteCall && (
        <ConfirmDialog
          filename={pendingDeleteCall.filename}
          onCancel={handleCancelDelete}
          onConfirm={handleConfirmDelete}
        />
      )}
    </div>
  )
}
