import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { Timeline } from './Timeline'
import type { TimelineSegmentResponse } from '../api/callsApi'

function makeSegment(overrides: Partial<TimelineSegmentResponse> = {}): TimelineSegmentResponse {
  return {
    segment_id: 'seg-1',
    start_time: 0,
    end_time: 2,
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

describe('Timeline (Story 2.4, Task 11 — base states)', () => {
  it('renders one element per segment with an id matching segment_id (Segments Flagged anchor target)', () => {
    const { container } = render(
      <Timeline
        segments={[
          makeSegment({ segment_id: 'seg-a', fused_sentiment: 'negative' }),
          makeSegment({ segment_id: 'seg-b', fused_sentiment: 'positive' }),
        ]}
        onSelectSegment={vi.fn()}
      />,
    )

    expect(container.querySelector('#segment-seg-a')).not.toBeNull()
    expect(container.querySelector('#segment-seg-b')).not.toBeNull()
  })

  it('renders the base glyph for each of the four sentiment variants', () => {
    render(
      <Timeline
        segments={[
          makeSegment({ segment_id: 'a', fused_sentiment: 'neutral' }),
          makeSegment({ segment_id: 'b', fused_sentiment: 'positive' }),
          makeSegment({ segment_id: 'c', fused_sentiment: 'mixed' }),
          makeSegment({ segment_id: 'd', fused_sentiment: 'negative' }),
        ]}
        onSelectSegment={vi.fn()}
      />,
    )

    expect(screen.getByText('–')).toBeInTheDocument()
    expect(screen.getByText('▲')).toBeInTheDocument()
    expect(screen.getByText('◆')).toBeInTheDocument()
    expect(screen.getByText('▼')).toBeInTheDocument()
  })

  it('renders no segments without crashing on an empty array', () => {
    const { container } = render(<Timeline segments={[]} onSelectSegment={vi.fn()} />)
    expect(container.querySelectorAll('[id^="segment-"]')).toHaveLength(0)
  })
})

describe('Timeline (Story 2.5, Task 3 — glyph-color fix + flagged variants)', () => {
  it('renders a neutral segment glyph in --color-text (regression test for the Story 2.4 white-glyph bug)', () => {
    const { container } = render(
      <Timeline segments={[makeSegment({ fused_sentiment: 'neutral' })]} onSelectSegment={vi.fn()} />,
    )
    const glyph = container.querySelector('.timeline__glyph')
    expect(glyph).toHaveClass('timeline__glyph--neutral')
  })

  it('renders the low-confidence hatch/dashed-border styling, "?" glyph, and an aria-label with the flag reason', () => {
    const { container } = render(
      <Timeline
        segments={[
          makeSegment({
            segment_id: 'seg-lowconf',
            low_confidence_flag: true,
            flag_reason: 'Confidence 0.30 is below the configured low-confidence threshold (0.50).',
          }),
        ]}
        onSelectSegment={vi.fn()}
      />,
    )

    const el = container.querySelector('#segment-seg-lowconf')
    expect(el).toHaveClass('timeline__segment--low-confidence')
    expect(screen.getByText('?')).toBeInTheDocument()
    expect(el).toHaveAttribute('aria-label', expect.stringContaining('Low confidence'))
    expect(el).toHaveAttribute(
      'aria-label',
      expect.stringContaining('Confidence 0.30 is below the configured low-confidence threshold (0.50).'),
    )
  })

  it('renders the disagreement split-fill styling, "⚠" glyph, and an aria-label mentioning both confidence values', () => {
    const { container } = render(
      <Timeline
        segments={[
          makeSegment({
            segment_id: 'seg-disagree',
            disagreement_flag: true,
            fused_confidence: 0.66,
            acoustic_confidence: 0.71,
          }),
        ]}
        onSelectSegment={vi.fn()}
      />,
    )

    const el = container.querySelector('#segment-seg-disagree')
    expect(el).toHaveClass('timeline__segment--disagreement')
    expect(screen.getByText('⚠')).toBeInTheDocument()
    expect(el).toHaveAttribute('aria-label', expect.stringContaining('disagreement'))
    expect(el).toHaveAttribute('aria-label', expect.stringContaining('0.66'))
    expect(el).toHaveAttribute('aria-label', expect.stringContaining('0.71'))
  })

  it('every segment is individually focusable (tabIndex 0)', () => {
    const { container } = render(
      <Timeline
        segments={[makeSegment({ segment_id: 'a' }), makeSegment({ segment_id: 'b' })]}
        onSelectSegment={vi.fn()}
      />,
    )
    expect(container.querySelector('#segment-a')).toHaveAttribute('tabIndex', '0')
    expect(container.querySelector('#segment-b')).toHaveAttribute('tabIndex', '0')
  })

  it('clicking a segment calls onSelectSegment with its id', () => {
    const onSelectSegment = vi.fn()
    const { container } = render(
      <Timeline segments={[makeSegment({ segment_id: 'seg-x' })]} onSelectSegment={onSelectSegment} />,
    )

    ;(container.querySelector('#segment-seg-x') as HTMLElement).click()

    expect(onSelectSegment).toHaveBeenCalledWith('seg-x')
  })

  it('ArrowRight on a focused non-last segment moves focus to and selects the next segment', async () => {
    const onSelectSegment = vi.fn()
    const { container } = render(
      <Timeline
        segments={[makeSegment({ segment_id: 'a' }), makeSegment({ segment_id: 'b' })]}
        onSelectSegment={onSelectSegment}
      />,
    )

    const first = container.querySelector('#segment-a') as HTMLElement
    first.focus()
    await userEvent.keyboard('{ArrowRight}')

    expect(onSelectSegment).toHaveBeenCalledWith('b')
    expect(document.activeElement?.id).toBe('segment-b')
  })

  it('ArrowRight on the last segment is a no-op', async () => {
    const onSelectSegment = vi.fn()
    const { container } = render(
      <Timeline
        segments={[makeSegment({ segment_id: 'a' }), makeSegment({ segment_id: 'b' })]}
        onSelectSegment={onSelectSegment}
      />,
    )

    const last = container.querySelector('#segment-b') as HTMLElement
    last.focus()
    await userEvent.keyboard('{ArrowRight}')

    expect(onSelectSegment).not.toHaveBeenCalled()
    expect(document.activeElement?.id).toBe('segment-b')
  })
})

describe('Timeline (code review, 2026-08-16 — selected-state class)', () => {
  it('applies timeline__segment--selected to the segment matching selectedSegmentId', () => {
    const { container } = render(
      <Timeline
        segments={[makeSegment({ segment_id: 'a' }), makeSegment({ segment_id: 'b' })]}
        selectedSegmentId="b"
        onSelectSegment={vi.fn()}
      />,
    )

    expect(container.querySelector('#segment-a')).not.toHaveClass('timeline__segment--selected')
    expect(container.querySelector('#segment-b')).toHaveClass('timeline__segment--selected')
  })

  it('applies no --selected class when selectedSegmentId is null/undefined', () => {
    const { container } = render(
      <Timeline segments={[makeSegment({ segment_id: 'a' })]} onSelectSegment={vi.fn()} />,
    )

    expect(container.querySelector('#segment-a')).not.toHaveClass('timeline__segment--selected')
  })
})
