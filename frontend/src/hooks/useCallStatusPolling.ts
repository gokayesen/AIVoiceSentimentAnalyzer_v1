import { useEffect } from 'react'
import { getCallStatus, type CallStatusResponse } from '../api/callsApi'
import type { SessionCall } from '../types/call'

const POLL_INTERVAL_MS = 2000

// Story 2.2 Task 5: polls every row still in `queued`/`processing` on a
// fixed interval. Kept in exactly one place (not duplicated per-row) and
// cleans up on unmount/dependency change — a background fetch racing after
// the component is gone is a real bug class given React 19 StrictMode's
// double-invoke-effects behavior in dev.
export function useCallStatusPolling(
  calls: SessionCall[],
  onUpdate: (callId: string, status: CallStatusResponse) => void,
) {
  // Story 2.3: a row mid-delete has no reason to keep polling its status —
  // it's about to be removed from the list (or restored on failure), and a
  // late response landing on it is wasted effort at best.
  const pollableIds = calls
    .filter((call) => !call.deleting && (call.state === 'queued' || call.state === 'processing'))
    .map((call) => call.id)
    .join(',')

  useEffect(() => {
    if (pollableIds === '') {
      return
    }
    const ids = pollableIds.split(',')

    const intervalId = setInterval(() => {
      for (const id of ids) {
        getCallStatus(id)
          .then((status) => onUpdate(id, status))
          .catch(() => {
            // A polling request that fails on its own (network error, etc.)
            // must not crash the row or the app — leave the row's
            // last-known state as-is and simply retry on the next tick.
          })
      }
    }, POLL_INTERVAL_MS)

    return () => clearInterval(intervalId)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pollableIds, onUpdate])
}
