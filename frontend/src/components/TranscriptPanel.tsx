import type { KeyboardEvent } from 'react'
import { useEffect } from 'react'
import './TranscriptPanel.css'
import type { TimelineSegmentResponse, TranscriptTurnResponse } from '../api/callsApi'
import { formatDuration } from '../utils/formatDuration'
import { findOverlappingSegment, overlaps } from '../utils/timeOverlap'
import { getSegmentAccessibleLabel } from '../utils/segmentAccessibleLabel'
import { DualSignalPanel } from './DualSignalPanel'
import { SpeakerLabel } from './SpeakerLabel'

interface TranscriptPanelProps {
  turns: TranscriptTurnResponse[]
  segments: TimelineSegmentResponse[]
  selectedSegmentId?: string | null
  onSelectSegment: (segmentId: string) => void
}

// Story 2.4 (Task 12) plain turns; Story 2.5 (Task 4) adds turn-state
// derivation (default/low-confidence/disagreement) from the turn's
// time-range overlap with /timeline's already-flagged segments — TranscriptTurn
// has no flag columns of its own (AD-11) — plus selection (Task 4) and
// scroll-sync (Task 6). See the story's Dev Notes "Turn state is derived
// from overlapping segments" and "Turn selection is uniform, not
// flagged-only."
export function TranscriptPanel({ turns, segments, selectedSegmentId, onSelectSegment }: TranscriptPanelProps) {
  useEffect(() => {
    if (!selectedSegmentId) return
    const selectedSegment = segments.find((s) => s.segment_id === selectedSegmentId)
    if (!selectedSegment) return
    const turn = turns.find((t) => overlaps(t, selectedSegment))
    if (!turn) return
    document.getElementById(`turn-${turn.turn_id}`)?.scrollIntoView({ block: 'nearest' })
    // Only re-run when the selection itself changes — turns/segments arrays
    // are re-fetched once per Call, not per selection.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [selectedSegmentId])

  if (turns.length === 0) {
    return <p className="transcript-panel__empty">No transcript available for this Call.</p>
  }

  return (
    <div className="transcript-panel">
      {turns.map((turn) => {
        const overlappingSegment = findOverlappingSegment(turn, segments)
        const isDisagreement = overlappingSegment?.disagreement_flag ?? false
        const isLowConfidence = !isDisagreement && (overlappingSegment?.low_confidence_flag ?? false)
        const variantClass = isDisagreement
          ? ' transcript-panel__turn--disagreement'
          : isLowConfidence
            ? ' transcript-panel__turn--low-confidence'
            : ''

        const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>) => {
          if (!overlappingSegment) return
          if (event.key === 'Enter' || event.key === ' ') {
            event.preventDefault()
            onSelectSegment(overlappingSegment.segment_id)
          }
        }

        return (
          <div
            key={turn.turn_id}
            id={`turn-${turn.turn_id}`}
            className={`transcript-panel__turn${variantClass}`}
            {...(overlappingSegment
              ? {
                  tabIndex: 0,
                  role: 'button',
                  // Code review (2026-08-16, Story 2.7): aria-describedby,
                  // not aria-label — aria-label would replace the turn's
                  // own accessible name (computed from its visible text,
                  // tags, and reason) instead of supplementing it, hiding
                  // the actual transcript content from screen readers.
                  // aria-describedby adds the segment's summary as a
                  // description, announced after the name, without losing
                  // anything. Closes Story 2.5's own AC10 non-visual-parity
                  // gap for every overlapping turn, not just flagged ones.
                  'aria-describedby': `turn-${turn.turn_id}-summary`,
                  onClick: () => onSelectSegment(overlappingSegment.segment_id),
                  onKeyDown: handleKeyDown,
                }
              : {})}
          >
            {overlappingSegment ? (
              <span id={`turn-${turn.turn_id}-summary`} className="sr-only">
                {getSegmentAccessibleLabel(overlappingSegment)}
              </span>
            ) : null}
            <div className="transcript-panel__time">{formatDuration(turn.start_time)}</div>
            <div className="transcript-panel__body">
              {turn.speaker_label ? (
                <SpeakerLabel label={turn.speaker_label} uncertain={turn.speaker_uncertain} />
              ) : null}
              <div className="transcript-panel__text">
                {turn.text}
                {isLowConfidence && (
                  <span className="tag tag--low">
                    LOW CONF {overlappingSegment!.fused_confidence.toFixed(2)}
                  </span>
                )}
                {isDisagreement && <span className="tag tag--conflict">CONFLICT</span>}
              </div>
              {isLowConfidence && overlappingSegment!.flag_reason && (
                <span className="transcript-panel__reason">{overlappingSegment!.flag_reason}</span>
              )}
              {/* Story 3.4 (AC2): a fixed, EXPERIENCE.md-defined string —
              never computed, unlike `flag_reason` above (a server-computed
              per-confidence message). Independent of isLowConfidence/
              isDisagreement (AD-10): a turn can be both speaker_uncertain
              and low-confidence/disagreement at once, and both reasons
              must render. */}
              {turn.speaker_uncertain && (
                <span className="transcript-panel__reason">
                  Flag reason: overlapping speech — speaker attribution uncertain.
                </span>
              )}
              {isDisagreement && (
                <DualSignalPanel
                  textSentiment={turn.text_sentiment}
                  textConfidence={turn.text_confidence}
                  toneEmotion={overlappingSegment!.acoustic_emotion}
                  toneConfidence={overlappingSegment!.acoustic_confidence}
                />
              )}
            </div>
          </div>
        )
      })}
    </div>
  )
}
