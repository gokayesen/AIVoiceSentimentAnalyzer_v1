import type { KeyboardEvent } from 'react'
import './Timeline.css'
import type { TimelineSegmentResponse } from '../api/callsApi'
import { sentimentColorVar, sentimentGlyph } from '../utils/sentimentColor'
import { getSegmentAccessibleLabel, getVariant } from '../utils/segmentAccessibleLabel'

interface TimelineProps {
  segments: TimelineSegmentResponse[]
  selectedSegmentId?: string | null
  onSelectSegment: (segmentId: string) => void
}

// Story 2.4 (Task 11) base states; Story 2.5 (Task 3) adds the
// low-confidence/disagreement flagged variants, keyboard selection
// (click/Enter/Space/ArrowLeft/ArrowRight), and the AC9 accessible name.
// Code review (2026-08-16): a `--selected` class was added below — the
// native focus-ring alone only reflects selection made via Timeline's own
// click/arrow-key handlers, not selection driven from TranscriptPanel or
// the Segments Flagged link, which never move DOM focus here.
export function Timeline({ segments, selectedSegmentId, onSelectSegment }: TimelineProps) {
  if (segments.length === 0) {
    return <p className="timeline__empty">No timeline segments for this Call.</p>
  }

  const focusSegment = (segmentId: string) => {
    document.getElementById(`segment-${segmentId}`)?.focus()
  }

  const handleKeyDown = (event: KeyboardEvent<HTMLDivElement>, index: number) => {
    if (event.key === 'Enter' || event.key === ' ') {
      event.preventDefault()
      onSelectSegment(segments[index].segment_id)
      return
    }
    if (event.key === 'ArrowRight' || event.key === 'ArrowLeft') {
      event.preventDefault()
      const nextIndex = index + (event.key === 'ArrowRight' ? 1 : -1)
      if (nextIndex < 0 || nextIndex >= segments.length) return
      const nextSegment = segments[nextIndex]
      onSelectSegment(nextSegment.segment_id)
      focusSegment(nextSegment.segment_id)
    }
  }

  return (
    <div className="timeline__track">
      {segments.map((segment, index) => {
        const duration = segment.end_time - segment.start_time
        const variant = getVariant(segment)
        const isBase = variant === 'base'
        const isSelected = segment.segment_id === selectedSegmentId
        return (
          <div
            key={segment.segment_id}
            id={`segment-${segment.segment_id}`}
            className={`timeline__segment${variant !== 'base' ? ` timeline__segment--${variant}` : ''}${isSelected ? ' timeline__segment--selected' : ''}`}
            style={{
              flexGrow: duration > 0 ? duration : 0.01,
              ...(isBase ? { backgroundColor: sentimentColorVar(segment.fused_sentiment) } : {}),
            }}
            title={getSegmentAccessibleLabel(segment)}
            aria-label={getSegmentAccessibleLabel(segment)}
            role="button"
            tabIndex={0}
            onClick={() => onSelectSegment(segment.segment_id)}
            onKeyDown={(event) => handleKeyDown(event, index)}
          >
            <span
              className={`timeline__glyph${
                variant === 'low-confidence'
                  ? ' timeline__glyph--low-confidence'
                  : isBase && segment.fused_sentiment === 'neutral'
                    ? ' timeline__glyph--neutral'
                    : ''
              }`}
              aria-hidden="true"
            >
              {variant === 'low-confidence' ? '?' : variant === 'disagreement' ? '⚠' : sentimentGlyph(segment.fused_sentiment)}
            </span>
          </div>
        )
      })}
    </div>
  )
}
