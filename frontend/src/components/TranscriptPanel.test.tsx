import { beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { TranscriptPanel } from './TranscriptPanel'
import { Timeline } from './Timeline'
import type { TimelineSegmentResponse, TranscriptTurnResponse } from '../api/callsApi'

// jsdom does not implement scrollIntoView (Story 2.5, Task 6) — no global
// polyfill exists in setupTests.ts, so it's mocked here, test-file-local.
beforeEach(() => {
  Element.prototype.scrollIntoView = vi.fn()
})

function makeTurn(overrides: Partial<TranscriptTurnResponse> = {}): TranscriptTurnResponse {
  return {
    turn_id: 'turn-1',
    turn_index: 0,
    start_time: 12,
    end_time: 15,
    text: 'Thanks for holding.',
    text_sentiment: 'neutral',
    text_emotion: 'neutral',
    text_confidence: 0.7,
    ...overrides,
  }
}

function makeSegment(overrides: Partial<TimelineSegmentResponse> = {}): TimelineSegmentResponse {
  return {
    segment_id: 'seg-1',
    start_time: 0,
    end_time: 20,
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

describe('TranscriptPanel (Story 2.4, Task 12 — plain turns)', () => {
  it('renders turn text and a formatted timestamp', () => {
    render(
      <TranscriptPanel
        turns={[makeTurn({ text: 'Thanks for holding.', start_time: 12 })]}
        segments={[]}
        onSelectSegment={vi.fn()}
      />,
    )

    expect(screen.getByText('Thanks for holding.')).toBeInTheDocument()
    expect(screen.getByText('00:12')).toBeInTheDocument()
  })

  it('shows a plain message when there are zero turns', () => {
    render(<TranscriptPanel turns={[]} segments={[]} onSelectSegment={vi.fn()} />)
    expect(screen.getByText(/no transcript available/i)).toBeInTheDocument()
  })
})

describe('TranscriptPanel (Story 2.5, Task 4 — turn state derivation)', () => {
  it('renders a turn overlapping no segment as default and non-interactive', () => {
    const { container } = render(
      <TranscriptPanel turns={[makeTurn({ turn_id: 't1' })]} segments={[]} onSelectSegment={vi.fn()} />,
    )
    const turnEl = container.querySelector('#turn-t1') as HTMLElement
    expect(turnEl.className).not.toMatch(/lowconf|disagree/i)
    expect(turnEl).not.toHaveAttribute('tabIndex')
  })

  it('renders a low-confidence turn with the tag and stated reason from the overlapping segment', () => {
    render(
      <TranscriptPanel
        turns={[makeTurn({ turn_id: 't1', start_time: 5, end_time: 8 })]}
        segments={[
          makeSegment({
            segment_id: 'seg-lc',
            start_time: 0,
            end_time: 10,
            low_confidence_flag: true,
            fused_confidence: 0.3,
            flag_reason: 'Confidence 0.30 is below the configured low-confidence threshold (0.50).',
          }),
        ]}
        onSelectSegment={vi.fn()}
      />,
    )

    expect(screen.getByText(/LOW CONF 0\.30/)).toBeInTheDocument()
    expect(
      screen.getByText('Confidence 0.30 is below the configured low-confidence threshold (0.50).'),
    ).toBeInTheDocument()
  })

  it('renders a disagreement turn with the conflict tag and the Dual-signal panel', () => {
    render(
      <TranscriptPanel
        turns={[
          makeTurn({
            turn_id: 't1',
            start_time: 5,
            end_time: 8,
            text_sentiment: 'neutral',
            text_confidence: 0.66,
          }),
        ]}
        segments={[
          makeSegment({
            segment_id: 'seg-d',
            start_time: 0,
            end_time: 10,
            disagreement_flag: true,
            acoustic_emotion: 'frustration',
            acoustic_confidence: 0.71,
          }),
        ]}
        onSelectSegment={vi.fn()}
      />,
    )

    expect(screen.getByText('CONFLICT')).toBeInTheDocument()
    expect(screen.getByText('Text signal')).toBeInTheDocument()
    expect(screen.getByText('Tone signal')).toBeInTheDocument()
    expect(screen.getByText('Neutral · 0.66')).toBeInTheDocument()
    expect(screen.getByText('Frustration · 0.71')).toBeInTheDocument()
  })

  it('renders SpeakerLabel only when speaker_label is present (Story 3.1/3.2 now populate this with real data)', () => {
    const { rerender } = render(
      <TranscriptPanel turns={[makeTurn({ turn_id: 't1' })]} segments={[]} onSelectSegment={vi.fn()} />,
    )
    expect(screen.queryByText('Agent')).not.toBeInTheDocument()

    rerender(
      <TranscriptPanel
        turns={[makeTurn({ turn_id: 't1', speaker_label: 'Agent' })]}
        segments={[]}
        onSelectSegment={vi.fn()}
      />,
    )
    expect(screen.getByText('Agent')).toBeInTheDocument()
  })

  it('renders the speaker-uncertain flag reason when speaker_uncertain is true (Story 3.4, AC2)', () => {
    render(
      <TranscriptPanel
        turns={[makeTurn({ turn_id: 't1', speaker_label: 'Agent', speaker_uncertain: true })]}
        segments={[]}
        onSelectSegment={vi.fn()}
      />,
    )
    expect(screen.getByText('Agent')).toHaveClass('speaker-label--uncertain')
    expect(
      screen.getByText('Flag reason: overlapping speech — speaker attribution uncertain.'),
    ).toBeInTheDocument()
  })

  it('does not render the speaker-uncertain flag reason when speaker_uncertain is explicitly false', () => {
    render(
      <TranscriptPanel
        turns={[makeTurn({ turn_id: 't1', speaker_label: 'Agent', speaker_uncertain: false })]}
        segments={[]}
        onSelectSegment={vi.fn()}
      />,
    )
    expect(
      screen.queryByText('Flag reason: overlapping speech — speaker attribution uncertain.'),
    ).not.toBeInTheDocument()
  })

  it('does not render the speaker-uncertain flag reason when speaker_uncertain is absent', () => {
    render(
      <TranscriptPanel
        turns={[makeTurn({ turn_id: 't1', speaker_label: 'Agent' })]}
        segments={[]}
        onSelectSegment={vi.fn()}
      />,
    )
    expect(
      screen.queryByText('Flag reason: overlapping speech — speaker attribution uncertain.'),
    ).not.toBeInTheDocument()
  })

  it('a turn with an overlapping segment is clickable and calls onSelectSegment with the segment id', async () => {
    const onSelectSegment = vi.fn()
    const { container } = render(
      <TranscriptPanel
        turns={[makeTurn({ turn_id: 't1', start_time: 5, end_time: 8 })]}
        segments={[makeSegment({ segment_id: 'seg-x', start_time: 0, end_time: 10 })]}
        onSelectSegment={onSelectSegment}
      />,
    )

    await userEvent.click(container.querySelector('#turn-t1') as HTMLElement)

    expect(onSelectSegment).toHaveBeenCalledWith('seg-x')
  })

  it.each(['{Enter}', ' '])(
    'a turn with an overlapping segment is keyboard-activatable (%s)',
    async (key) => {
      const onSelectSegment = vi.fn()
      const { container } = render(
        <TranscriptPanel
          turns={[makeTurn({ turn_id: 't1', start_time: 5, end_time: 8 })]}
          segments={[makeSegment({ segment_id: 'seg-x', start_time: 0, end_time: 10 })]}
          onSelectSegment={onSelectSegment}
        />,
      )
      const turnEl = container.querySelector('#turn-t1') as HTMLElement
      turnEl.focus()
      await userEvent.keyboard(key)

      expect(onSelectSegment).toHaveBeenCalledWith('seg-x')
    },
  )
})

describe('TranscriptPanel (Story 2.5, Task 10 — screen-reader parity with Timeline)', () => {
  it('a flagged turn carries the same flag-reason text its overlapping Timeline segment exposes via aria-label', () => {
    const flaggedSegment = makeSegment({
      segment_id: 'seg-lc',
      start_time: 0,
      end_time: 10,
      low_confidence_flag: true,
      fused_confidence: 0.3,
      flag_reason: 'Confidence 0.30 is below the configured low-confidence threshold (0.50).',
    })

    const { container: timelineContainer } = render(
      <Timeline segments={[flaggedSegment]} onSelectSegment={vi.fn()} />,
    )
    const { container: transcriptContainer } = render(
      <TranscriptPanel
        turns={[makeTurn({ turn_id: 't1', start_time: 5, end_time: 8 })]}
        segments={[flaggedSegment]}
        onSelectSegment={vi.fn()}
      />,
    )

    const segmentAriaLabel = timelineContainer.querySelector('#segment-seg-lc')?.getAttribute('aria-label')
    const turnReasonText = transcriptContainer.querySelector('.transcript-panel__reason')?.textContent

    expect(segmentAriaLabel).toContain(flaggedSegment.flag_reason)
    expect(turnReasonText).toBe(flaggedSegment.flag_reason)
  })

  // Story 2.7 (Task 5; AC8 — deferred-work.md, Story 2.5 review): the
  // previously-untested common case — an ordinary (base-variant) turn gets
  // the same accessible info its overlapping Timeline segment already
  // exposes, closing the "guaranteed complete non-visual equivalent" gap
  // (Story 2.5's own AC10) that only ever held for flagged turns before.
  // Code review (2026-08-16): uses aria-describedby (a visually-hidden
  // summary span), not aria-label — aria-label would replace the turn's
  // own accessible name (its actual transcript text), which is the exact
  // regression this patch fixes.
  it('a base-variant (unflagged) turn is described by the same info its overlapping Timeline segment exposes via aria-label, without losing its own text as its accessible name', () => {
    const baseSegment = makeSegment({
      segment_id: 'seg-base',
      start_time: 0,
      end_time: 10,
      fused_sentiment: 'positive',
      fused_confidence: 0.82,
    })

    const { container: timelineContainer } = render(
      <Timeline segments={[baseSegment]} onSelectSegment={vi.fn()} />,
    )
    const { container: transcriptContainer } = render(
      <TranscriptPanel
        turns={[makeTurn({ turn_id: 't1', start_time: 5, end_time: 8, text: 'Thanks for holding.' })]}
        segments={[baseSegment]}
        onSelectSegment={vi.fn()}
      />,
    )

    const segmentAriaLabel = timelineContainer.querySelector('#segment-seg-base')?.getAttribute('aria-label')
    const turnEl = transcriptContainer.querySelector('#turn-t1') as HTMLElement

    expect(segmentAriaLabel).toBeTruthy()
    expect(turnEl).not.toHaveAttribute('aria-label')
    const describedbyId = turnEl.getAttribute('aria-describedby')
    expect(describedbyId).toBeTruthy()
    expect(transcriptContainer.querySelector(`#${describedbyId}`)?.textContent).toBe(segmentAriaLabel)
    // The turn's own visible text remains its accessible name (unchanged).
    expect(turnEl).toHaveAccessibleName(/Thanks for holding\./)
  })
})

describe('TranscriptPanel (Story 2.5, Task 6 — scroll sync)', () => {
  it('scrolls the overlapping turn into view when selectedSegmentId changes', () => {
    const segment = makeSegment({ segment_id: 'seg-x', start_time: 0, end_time: 10 })
    const { rerender } = render(
      <TranscriptPanel
        turns={[makeTurn({ turn_id: 't1', start_time: 5, end_time: 8 })]}
        segments={[segment]}
        onSelectSegment={vi.fn()}
        selectedSegmentId={null}
      />,
    )

    expect(Element.prototype.scrollIntoView).not.toHaveBeenCalled()

    rerender(
      <TranscriptPanel
        turns={[makeTurn({ turn_id: 't1', start_time: 5, end_time: 8 })]}
        segments={[segment]}
        onSelectSegment={vi.fn()}
        selectedSegmentId="seg-x"
      />,
    )

    expect(Element.prototype.scrollIntoView).toHaveBeenCalledWith({ block: 'nearest' })
  })
})
