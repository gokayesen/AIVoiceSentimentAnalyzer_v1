import { describe, expect, it } from 'vitest'
import { getSegmentAccessibleLabel, getVariant } from './segmentAccessibleLabel'
import type { TimelineSegmentResponse } from '../api/callsApi'

function makeSegment(overrides: Partial<TimelineSegmentResponse> = {}): TimelineSegmentResponse {
  return {
    segment_id: 'seg-1',
    start_time: 0,
    end_time: 10,
    fused_sentiment: 'neutral',
    fused_emotion: 'neutral',
    fused_confidence: 0.7,
    disagreement_flag: false,
    low_confidence_flag: false,
    flag_reason: null,
    acoustic_emotion: null,
    acoustic_confidence: null,
    pitch_mean_hz: null,
    energy_rms_mean: null,
    speaking_rate_estimate: null,
    pause_ratio: null,
    ...overrides,
  }
}

describe('getVariant', () => {
  it('returns "base" when neither flag is set', () => {
    expect(getVariant(makeSegment())).toBe('base')
  })

  it('returns "low-confidence" when only low_confidence_flag is set', () => {
    expect(getVariant(makeSegment({ low_confidence_flag: true }))).toBe('low-confidence')
  })

  it('returns "disagreement" when only disagreement_flag is set', () => {
    expect(getVariant(makeSegment({ disagreement_flag: true }))).toBe('disagreement')
  })

  it('returns "disagreement" (wins the tie-break) when both flags are set', () => {
    expect(getVariant(makeSegment({ disagreement_flag: true, low_confidence_flag: true }))).toBe(
      'disagreement',
    )
  })
})

describe('getSegmentAccessibleLabel', () => {
  it('formats a base-variant segment as "range, Sentiment, confidence N.NN"', () => {
    const label = getSegmentAccessibleLabel(
      makeSegment({ start_time: 0, end_time: 10, fused_sentiment: 'positive', fused_confidence: 0.82 }),
    )
    expect(label).toBe('00:00–00:10, Positive, confidence 0.82')
  })

  it('formats a low-confidence segment with its flag_reason', () => {
    const label = getSegmentAccessibleLabel(
      makeSegment({
        low_confidence_flag: true,
        flag_reason: 'Confidence 0.30 is below the configured low-confidence threshold (0.50).',
      }),
    )
    expect(label).toBe(
      '00:00–00:10, Low confidence: Confidence 0.30 is below the configured low-confidence threshold (0.50).',
    )
  })

  it('formats a low-confidence segment with a fallback reason when flag_reason is null', () => {
    const label = getSegmentAccessibleLabel(makeSegment({ low_confidence_flag: true, flag_reason: null }))
    expect(label).toBe('00:00–00:10, Low confidence: confidence below threshold')
  })

  it('formats a disagreement segment with both confidence values', () => {
    const label = getSegmentAccessibleLabel(
      makeSegment({ disagreement_flag: true, fused_confidence: 0.66, acoustic_confidence: 0.71 }),
    )
    expect(label).toBe('00:00–00:10, Signal disagreement: text 0.66 vs. tone 0.71')
  })

  it('formats a disagreement segment as "unavailable" when acoustic_confidence is null', () => {
    const label = getSegmentAccessibleLabel(
      makeSegment({ disagreement_flag: true, fused_confidence: 0.66, acoustic_confidence: null }),
    )
    expect(label).toBe('00:00–00:10, Signal disagreement: text 0.66 vs. tone unavailable')
  })
})
