import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AcousticPanel } from './AcousticPanel'
import type { AcousticSummaryResponse, TimelineSegmentResponse } from '../api/callsApi'

function makeSummary(overrides: Partial<AcousticSummaryResponse> = {}): AcousticSummaryResponse {
  return {
    call_id: 'abc-123',
    status: 'complete',
    segment_count: 3,
    pitch_mean_hz: 142.3,
    energy_rms_mean: 0.041,
    speaking_rate_estimate: 2.7,
    pause_ratio: 0.18,
    ...overrides,
  }
}

function makeSegment(overrides: Partial<TimelineSegmentResponse> = {}): TimelineSegmentResponse {
  return {
    segment_id: 'seg-1',
    start_time: 65,
    end_time: 95,
    fused_sentiment: 'neutral',
    fused_emotion: 'neutral',
    fused_confidence: 0.7,
    disagreement_flag: false,
    low_confidence_flag: false,
    flag_reason: null,
    acoustic_emotion: null,
    acoustic_confidence: null,
    pitch_mean_hz: 210.5,
    energy_rms_mean: 0.061,
    speaking_rate_estimate: 4.1,
    pause_ratio: 0.15,
    ...overrides,
  }
}

describe('AcousticPanel (Story 2.4, Task 13 — call-level aggregates only)', () => {
  it('renders the four labeled metrics with real computed values', () => {
    render(<AcousticPanel summary={makeSummary()} />)

    expect(screen.getByText(/pitch/i)).toBeInTheDocument()
    expect(screen.getByText('142 Hz')).toBeInTheDocument()
    expect(screen.getByText(/energy/i)).toBeInTheDocument()
    expect(screen.getByText('0.041')).toBeInTheDocument()
    expect(screen.getByText(/speaking rate/i)).toBeInTheDocument()
    expect(screen.getByText('2.70 onsets/sec')).toBeInTheDocument()
    expect(screen.getByText(/pauses/i)).toBeInTheDocument()
    expect(screen.getByText('18% of call')).toBeInTheDocument()
  })

  it('shows a fallback for a null pitch (no voiced audio detected)', () => {
    render(<AcousticPanel summary={makeSummary({ pitch_mean_hz: null })} />)

    expect(screen.getByText(/no voiced audio detected/i)).toBeInTheDocument()
  })

  it('renders no narrative/anchor comparison text (Story 2.5 scope)', () => {
    const { container } = render(<AcousticPanel summary={makeSummary()} />)
    expect(container.innerHTML).not.toMatch(/baseline|vs\.|see \d/i)
  })

  it('renders the call-level aggregate when selectedSegment is absent (unchanged default)', () => {
    render(<AcousticPanel summary={makeSummary()} selectedSegment={null} />)
    expect(screen.getByText('142 Hz')).toBeInTheDocument()
  })
})

describe('AcousticPanel (Story 2.5, Task 8 — per-segment highlight mode)', () => {
  it("renders the selected segment's own four metrics instead of the aggregate, anchored by its time range", () => {
    render(<AcousticPanel summary={makeSummary()} selectedSegment={makeSegment()} />)

    expect(screen.getByText('211 Hz')).toBeInTheDocument()
    expect(screen.getByText('0.061')).toBeInTheDocument()
    expect(screen.getByText('4.10 onsets/sec')).toBeInTheDocument()
    expect(screen.getByText('15% of call')).toBeInTheDocument()
    // Aggregate's own values must not be shown alongside the segment's.
    expect(screen.queryByText('142 Hz')).not.toBeInTheDocument()
    expect(screen.getByText(/01:05.*01:35/)).toBeInTheDocument()
  })

  it('falls back to the null-pitch copy for a selected segment with no voiced audio', () => {
    render(<AcousticPanel summary={makeSummary()} selectedSegment={makeSegment({ pitch_mean_hz: null })} />)
    expect(screen.getByText(/no voiced audio detected/i)).toBeInTheDocument()
  })
})
