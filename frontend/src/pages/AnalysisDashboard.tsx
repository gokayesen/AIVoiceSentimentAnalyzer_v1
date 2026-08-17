import { useEffect, useState } from 'react'
import './AnalysisDashboard.css'
import {
  ApiError,
  getAcousticSummary,
  getCallStatus,
  getTimeline,
  getTranscript,
  type AcousticSummaryResponse,
  type CallStatusResponse,
  type TimelineResponse,
  type TranscriptResponse,
} from '../api/callsApi'
import { Timeline } from '../components/Timeline'
import { TranscriptPanel } from '../components/TranscriptPanel'
import { AcousticPanel } from '../components/AcousticPanel'
import { DisclaimerBar } from '../components/DisclaimerBar'
import { formatDuration } from '../utils/formatDuration'
import { formatRelativeTime } from '../utils/formatRelativeTime'
import { capitalize } from '../utils/capitalize'
import { sentimentColorVar, sentimentGlyph } from '../utils/sentimentColor'

interface AnalysisDashboardProps {
  callId: string
  onBreadcrumbReady: (label: string) => void
  onBack: () => void
}

interface FriendlyError {
  message: string
  nextStep: string
}

function toFriendlyError(err: unknown): FriendlyError {
  if (err instanceof ApiError) {
    return { message: err.message, nextStep: err.next_step }
  }
  return {
    message: 'Could not reach the server.',
    nextStep: 'Check your connection and try again.',
  }
}

// Story 2.4: the Analysis Dashboard — Case strip, four summary cells,
// Emotional Timeline, transcript panel, and acoustic insights panel for one
// completed Call, all fetched in parallel. See the story's Dev Notes "What
// this story's Timeline/transcript/acoustic panels do and don't render" —
// this story's own scope is presence of real, evidence-backed content, not
// the interactive drill-down/specialized flagged-state visuals (Story 2.5).
export function AnalysisDashboard({ callId, onBreadcrumbReady, onBack }: AnalysisDashboardProps) {
  const [status, setStatus] = useState<CallStatusResponse | null>(null)
  const [statusError, setStatusError] = useState<FriendlyError | null>(null)
  const [timeline, setTimeline] = useState<TimelineResponse | null>(null)
  const [timelineFailed, setTimelineFailed] = useState(false)
  const [transcript, setTranscript] = useState<TranscriptResponse | null>(null)
  const [transcriptFailed, setTranscriptFailed] = useState(false)
  const [acoustic, setAcoustic] = useState<AcousticSummaryResponse | null>(null)
  const [acousticFailed, setAcousticFailed] = useState(false)
  // Code review (2026-08-15): the loading placeholder now waits for all
  // four requests to settle (Task 8: "while any of the four requests is in
  // flight, render a plain loading placeholder"), tracked via a countdown
  // instead of gating on `status` alone — gating on `status` alone let the
  // three secondary panels render their "unavailable"/empty copy for a
  // moment before their own fetches had actually resolved.
  const [pendingCount, setPendingCount] = useState(4)
  // Story 2.5 (Task 6): the single selection driving all three synchronized
  // panels — see the story's Dev Notes "Selection model."
  const [selectedSegmentId, setSelectedSegmentId] = useState<string | null>(null)

  useEffect(() => {
    let cancelled = false
    setStatus(null)
    setStatusError(null)
    setTimeline(null)
    setTimelineFailed(false)
    setTranscript(null)
    setTranscriptFailed(false)
    setAcoustic(null)
    setAcousticFailed(false)
    setPendingCount(4)

    const settle = () => {
      if (!cancelled) setPendingCount((n) => n - 1)
    }

    getCallStatus(callId)
      .then((result) => {
        if (cancelled) return
        setStatus(result)
        // Dev Notes "Known spec gap — no queue/routing concept exists": no
        // real queue data exists anywhere — the literal `queue/session`
        // prefix mirrors AppHeader's own existing default (Story 2.1).
        onBreadcrumbReady(`queue/session > ${result.filename}`)
      })
      .catch((err: unknown) => {
        if (!cancelled) setStatusError(toFriendlyError(err))
      })
      .finally(settle)

    // Each secondary fetch degrades only its own panel on failure — see Dev
    // Notes "Partial-failure handling". `getCallStatus` failing is the only
    // hard failure (nothing else can render without it). A failure is
    // tracked separately from "still loading"/"genuinely empty" (both of
    // which leave the data state `null`) so a fetch failure renders a
    // distinct "unavailable" message instead of silently looking the same
    // as an honest empty result (code review, 2026-08-15).
    getTimeline(callId)
      .then((result) => {
        if (!cancelled) setTimeline(result)
      })
      .catch(() => {
        if (!cancelled) setTimelineFailed(true)
      })
      .finally(settle)
    getTranscript(callId)
      .then((result) => {
        if (!cancelled) setTranscript(result)
      })
      .catch(() => {
        if (!cancelled) setTranscriptFailed(true)
      })
      .finally(settle)
    getAcousticSummary(callId)
      .then((result) => {
        if (!cancelled) setAcoustic(result)
      })
      .catch(() => {
        if (!cancelled) setAcousticFailed(true)
      })
      .finally(settle)

    return () => {
      cancelled = true
    }
  }, [callId, onBreadcrumbReady])

  if (statusError) {
    return (
      <div className="analysis-dashboard analysis-dashboard--error">
        <p className="analysis-dashboard__error-message" role="status">{statusError.message}</p>
        <p className="analysis-dashboard__error-next-step">{statusError.nextStep}</p>
        <button type="button" className="analysis-dashboard__back-button" onClick={onBack}>
          Back to Session Call List
        </button>
      </div>
    )
  }

  if (pendingCount > 0 || status === null) {
    return (
      <div className="analysis-dashboard analysis-dashboard--loading">
        <p>Loading…</p>
      </div>
    )
  }

  // Timeline segments feed the Segments Flagged summary cell (Task 10) —
  // computed once here, shared by both the cell and the Timeline strip.
  const segments = timeline?.segments ?? []
  const flaggedSegments = segments.filter((s) => s.disagreement_flag || s.low_confidence_flag)
  const lowConfCount = flaggedSegments.filter((s) => s.low_confidence_flag).length
  const disagreementCount = flaggedSegments.filter((s) => s.disagreement_flag).length
  // Story 2.5 (Task 6): resolved once here, passed to AcousticPanel (Task 8)
  // — Timeline/TranscriptPanel only need the id, not the full object.
  const selectedSegment = segments.find((s) => s.segment_id === selectedSegmentId) ?? null
  // Story 3.4 (AC3): the whole-Call "attribution unavailable" fact, read
  // directly from the backend (Story 3.3) — replaces Epic 2's client-side
  // "every turn lacks speaker_label" approximation, which could not
  // distinguish "mono, failed" from "stereo, defensively-all-null".
  const hasNoSpeakerAttribution = !transcriptFailed && (transcript?.speaker_attribution_unavailable ?? false)

  return (
    <div className="analysis-dashboard">
      <div className="analysis-dashboard__case-strip">
        <h2 className="analysis-dashboard__filename">{status.filename}</h2>
        <div className="analysis-dashboard__meta">
          DURATION {formatDuration(status.duration_seconds)} · QUEUE Session
          {status.completed_at ? ` · ANALYZED ${formatRelativeTime(status.completed_at)}` : null}
        </div>
      </div>

      {status.no_speech_detected ? (
        <p className="analysis-dashboard__no-speech" role="status">
          No speech was detected in this Call — there is no Analysis Result to show.
        </p>
      ) : (
        <>
          <div className="analysis-dashboard__summary-row">
            <div className="analysis-dashboard__summary-cell">
              <div className="analysis-dashboard__cell-label">Overall Sentiment</div>
              <div
                className="analysis-dashboard__cell-value"
                style={{ color: sentimentColorVar(status.overall_sentiment ?? '') }}
              >
                {/* Code review (2026-08-15): never color-alone (DESIGN.md
                Accessibility Floor) — same glyph+color pairing Timeline
                already uses, applied here too. */}
                <span aria-hidden="true">{sentimentGlyph(status.overall_sentiment ?? '')} </span>
                <span>{capitalize(status.overall_sentiment ?? '')}</span>
              </div>
            </div>
            <div className="analysis-dashboard__summary-cell">
              <div className="analysis-dashboard__cell-label">Dominant Emotion</div>
              <div
                className="analysis-dashboard__cell-value"
                style={{ color: sentimentColorVar(status.overall_sentiment ?? '') }}
              >
                {/* Glyph reflects `overall_sentiment`, matching this cell's
                own color source (Dev Notes "Dominant Emotion cell color is
                driven by overall_sentiment, not a per-emotion guess"), not
                `overall_emotion` (not a sentiment-keyed value). */}
                <span aria-hidden="true">{sentimentGlyph(status.overall_sentiment ?? '')} </span>
                <span>{capitalize(status.overall_emotion ?? '')}</span>
              </div>
              <div className="analysis-dashboard__cell-sub">
                Confidence: {status.overall_confidence?.toFixed(2)}
              </div>
            </div>
            <div className="analysis-dashboard__summary-cell">
              <div className="analysis-dashboard__cell-label">Secondary Signal</div>
              {status.secondary_signal_emotion ? (
                <>
                  <div className="analysis-dashboard__cell-value">
                    {capitalize(status.secondary_signal_emotion)}
                  </div>
                  <div className="analysis-dashboard__cell-sub">
                    Confidence: {status.secondary_signal_confidence?.toFixed(2)}
                  </div>
                </>
              ) : (
                <div className="analysis-dashboard__cell-value">None flagged</div>
              )}
            </div>
            <div className="analysis-dashboard__summary-cell">
              <div className="analysis-dashboard__cell-label">Segments Flagged</div>
              {timelineFailed ? (
                <div className="analysis-dashboard__cell-value">Unavailable</div>
              ) : flaggedSegments.length > 0 ? (
                <>
                  <div className="analysis-dashboard__cell-value">
                    {/* Code review (2026-08-16): wired to setSelectedSegmentId
                    (kept the anchor href as a graceful-degradation fallback)
                    so this entry point participates in the same
                    selection-sync mechanism as Timeline/TranscriptPanel,
                    instead of only native-scrolling to the segment. */}
                    <a
                      href={`#segment-${flaggedSegments[0].segment_id}`}
                      onClick={(event) => {
                        event.preventDefault()
                        setSelectedSegmentId(flaggedSegments[0].segment_id)
                      }}
                    >
                      {flaggedSegments.length}
                    </a>
                  </div>
                  <div className="analysis-dashboard__cell-sub">
                    {lowConfCount} low-conf · {disagreementCount} signal conflict
                  </div>
                </>
              ) : (
                <div className="analysis-dashboard__cell-value">0</div>
              )}
            </div>
          </div>

          <DisclaimerBar />
          {/* Story 2.6 (Task 3; AC2): `single_modality_flag` was already
          computed/returned by Story 1.6's fusion output but never rendered
          by any prior Epic 2 story — see the story's Dev Notes
          "Single-modality disclosure gap". A single-signal result must
          never look like an ordinary two-signal fused result (AD-1/AD-8). */}
          {status.single_modality_flag ? (
            <p className="analysis-dashboard__signal-note" role="status">
              Single-signal result — no transcript signal was available for this Call; based on the
              acoustic signal only.
            </p>
          ) : null}

          <div className="analysis-dashboard__section-label">Emotional Timeline</div>
          {timelineFailed ? (
            <p className="analysis-dashboard__panel-unavailable" role="status">Emotional Timeline unavailable.</p>
          ) : (
            <Timeline
              segments={segments}
              selectedSegmentId={selectedSegmentId}
              onSelectSegment={setSelectedSegmentId}
            />
          )}

          <div className="analysis-dashboard__main-grid">
            <div>
              <div className="analysis-dashboard__section-label">Transcript</div>
              {/* Story 2.6 (Task 4; AC5, UX-DR13) authored this copy
              contract; Story 3.4 wired it to the real backend field. */}
              {hasNoSpeakerAttribution ? (
                <p className="analysis-dashboard__signal-note" role="status">
                  Mono input — turns unattributed
                </p>
              ) : null}
              {transcriptFailed ? (
                <p className="analysis-dashboard__panel-unavailable" role="status">Transcript unavailable.</p>
              ) : (
                <TranscriptPanel
                  turns={transcript?.turns ?? []}
                  segments={segments}
                  selectedSegmentId={selectedSegmentId}
                  onSelectSegment={setSelectedSegmentId}
                />
              )}
            </div>
            <div>
              <div className="analysis-dashboard__section-label">Acoustic Insights</div>
              {acousticFailed || !acoustic ? (
                <p className="analysis-dashboard__panel-unavailable" role="status">
                  Acoustic insights unavailable.
                </p>
              ) : (
                <AcousticPanel summary={acoustic} selectedSegment={selectedSegment} />
              )}
            </div>
          </div>
        </>
      )}
    </div>
  )
}
