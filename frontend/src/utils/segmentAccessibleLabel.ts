import type { TimelineSegmentResponse } from '../api/callsApi'
import { formatDuration } from './formatDuration'
import { capitalize } from './capitalize'

export type Variant = 'low-confidence' | 'disagreement' | 'base'

// Story 2.5 (Task 3, AC9) originally defined this inline in Timeline.tsx;
// extracted here in Story 2.7 (Task 5; AC8) so TranscriptPanel can give its
// own turns the same accessible name Timeline segments already carry,
// closing Story 2.5's own AC10 "guaranteed complete non-visual equivalent"
// gap for unflagged turns. Disagreement wins when a segment somehow has
// both flags set.
// Code review (2026-08-16): exported (was Timeline.tsx-local, duplicated
// verbatim in this file) so Timeline's visual variant and this file's
// accessible-name variant can never desync — single source of truth for
// segment-state classification.
export function getVariant(segment: TimelineSegmentResponse): Variant {
  if (segment.disagreement_flag) return 'disagreement'
  if (segment.low_confidence_flag) return 'low-confidence'
  return 'base'
}

// The accessible name a screen reader announces — time range + reading +
// flagged state/reason, mirroring mockups/analysis-dashboard.html's own
// title-attribute phrasing exactly (DESIGN.md/EXPERIENCE.md's own worked
// example of this copy).
export function getSegmentAccessibleLabel(segment: TimelineSegmentResponse): string {
  const range = `${formatDuration(segment.start_time)}–${formatDuration(segment.end_time)}`
  const variant = getVariant(segment)
  if (variant === 'low-confidence') {
    return `${range}, Low confidence: ${segment.flag_reason ?? 'confidence below threshold'}`
  }
  if (variant === 'disagreement') {
    const tone =
      segment.acoustic_confidence === null ? 'unavailable' : segment.acoustic_confidence.toFixed(2)
    return `${range}, Signal disagreement: text ${segment.fused_confidence.toFixed(2)} vs. tone ${tone}`
  }
  return `${range}, ${capitalize(segment.fused_sentiment)}, confidence ${segment.fused_confidence.toFixed(2)}`
}
