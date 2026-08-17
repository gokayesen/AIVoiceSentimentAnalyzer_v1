import { useState } from 'react'
import { AppHeader } from './components/AppHeader'
import { SessionCallList } from './pages/SessionCallList'
import { AnalysisDashboard } from './pages/AnalysisDashboard'

/**
 * The app loads directly into the Session Call List — no login/account
 * screen, since MVP has no auth (AC1, PRD §2.3). Story 2.4: local view-state
 * (no `react-router-dom` — see that story's Dev Notes "Why local view-state,
 * not a router") toggles between the list and one Call's Analysis
 * Dashboard. The list is never unmounted while the Dashboard is shown (kept
 * mounted, just `hidden`) — it owns the session's entire client-held call
 * state, and unmounting it would wipe that state the instant an Analyst
 * opened a Dashboard and came back.
 */
export function App() {
  const [selectedCallId, setSelectedCallId] = useState<string | null>(null)
  const [dashboardBreadcrumb, setDashboardBreadcrumb] = useState<string | undefined>(undefined)

  const handleSelectCall = (callId: string) => {
    setSelectedCallId(callId)
    setDashboardBreadcrumb(undefined)
  }

  const handleReturnToList = () => {
    setSelectedCallId(null)
    setDashboardBreadcrumb(undefined)
  }

  return (
    <>
      <AppHeader
        breadcrumbLabel={selectedCallId ? dashboardBreadcrumb : undefined}
        onBreadcrumbClick={selectedCallId ? handleReturnToList : undefined}
      />
      <div hidden={selectedCallId !== null}>
        <SessionCallList onSelectCall={handleSelectCall} />
      </div>
      {selectedCallId && (
        <AnalysisDashboard
          callId={selectedCallId}
          onBreadcrumbReady={setDashboardBreadcrumb}
          onBack={handleReturnToList}
        />
      )}
    </>
  )
}
