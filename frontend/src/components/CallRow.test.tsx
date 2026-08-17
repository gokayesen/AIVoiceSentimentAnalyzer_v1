import { describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { CallRow } from './CallRow'
import type { SessionCall } from '../types/call'

function makeCall(overrides: Partial<SessionCall> = {}): SessionCall {
  return {
    key: 'call-1',
    id: 'call-1',
    file: new File(['x'], 'case_4471.wav'),
    filename: 'case_4471.wav',
    state: 'validating',
    ...overrides,
  }
}

function renderRow(call: SessionCall, overrides: Partial<Parameters<typeof CallRow>[0]> = {}) {
  return render(<CallRow call={call} onRetry={vi.fn()} onDeleteRequest={vi.fn()} {...overrides} />)
}

describe('CallRow — non-complete states', () => {
  it.each([
    ['validating', /validating/i],
    ['queued', /queued/i],
    ['processing', /processing/i],
  ] as const)('renders filename and a "%s" status word', (state, expectedText) => {
    renderRow(makeCall({ state }))
    expect(screen.getByText('case_4471.wav')).toBeInTheDocument()
    expect(screen.getByText(expectedText)).toBeInTheDocument()
  })

  it.each(['validating', 'queued', 'processing'] as const)(
    'is not selectable in the "%s" state (no tabIndex, click is a no-op)',
    async (state) => {
      const onSelectCall = vi.fn()
      const { container } = renderRow(makeCall({ state }), { onSelectCall })
      const row = container.firstElementChild as HTMLElement
      expect(row).not.toHaveAttribute('tabIndex')
      await userEvent.click(row)
      expect(onSelectCall).not.toHaveBeenCalled()
    },
  )

  it('failed state shows the error message, next step, and a Retry action', async () => {
    const onRetry = vi.fn()
    const call = makeCall({
      state: 'failed',
      errorMessage: 'Unsupported audio format: .ogg. Accepted formats are WAV, MP3, and M4A.',
      errorNextStep: 'Re-export the recording as WAV, MP3, or M4A and upload again.',
    })
    renderRow(call, { onRetry })

    expect(screen.getByText(/unsupported audio format/i)).toBeInTheDocument()
    expect(screen.getByText(/re-export the recording/i)).toBeInTheDocument()
    const retryButton = screen.getByRole('button', { name: /retry/i })

    await userEvent.click(retryButton)
    expect(onRetry).toHaveBeenCalledWith(call)
  })

  it('failed state is not selectable (no tabIndex, click is a no-op)', async () => {
    const onSelectCall = vi.fn()
    const { container } = renderRow(
      makeCall({ state: 'failed', errorMessage: 'x', errorNextStep: 'y' }),
      { onSelectCall },
    )
    const row = container.firstElementChild as HTMLElement
    expect(row).not.toHaveAttribute('tabIndex')
    await userEvent.click(row)
    expect(onSelectCall).not.toHaveBeenCalled()
  })
})

describe('CallRow — complete state', () => {
  function makeCompleteCall(overrides: Partial<SessionCall> = {}): SessionCall {
    return makeCall({
      state: 'complete',
      sentiment: 'negative',
      emotion: 'frustration',
      confidence: 0.84,
      durationSeconds: 402,
      ...overrides,
    })
  }

  it('renders filename, Sentiment · Emotion text, confidence, and duration', () => {
    renderRow(makeCompleteCall())
    expect(screen.getByText('case_4471.wav')).toBeInTheDocument()
    expect(screen.getByText(/negative/i)).toBeInTheDocument()
    expect(screen.getByText(/frustration/i)).toBeInTheDocument()
    expect(screen.getByText('0.84')).toBeInTheDocument()
    expect(screen.getByText('06:42')).toBeInTheDocument()
  })

  it('renders a badge-dot whose modifier class matches the sentiment', () => {
    const { container } = renderRow(makeCompleteCall({ sentiment: 'positive' }))
    expect(container.querySelector('.call-row__badge-dot--positive')).toBeInTheDocument()
  })

  it('is a focusable, full-row hit target', () => {
    const { container } = renderRow(makeCompleteCall())
    const row = container.firstElementChild as HTMLElement
    expect(row).toHaveAttribute('tabIndex', '0')
  })

  // Story 2.7 (Task 2; AC2/AC8): role="button" matches the same pattern
  // Timeline.tsx/TranscriptPanel.tsx already use on their own interactive
  // divs.
  it('has role="button" (deferred-work.md, Story 2.3 review)', () => {
    const { container } = renderRow(makeCompleteCall())
    const row = container.firstElementChild as HTMLElement
    expect(row).toHaveAttribute('role', 'button')
  })

  // Code review (2026-08-16, Story 2.7): role="button" makes the row's
  // accessible name computed from content by default, which recurses into
  // the nested delete <button> and bleeds its own "Delete <filename>" label
  // into the row's name. An explicit aria-label short-circuits that
  // recursion — this test proves the row's computed accessible name is
  // clean (row info only), not polluted by the nested button's label.
  it('has a clean accessible name, not polluted by the nested delete button\'s label', () => {
    renderRow(makeCompleteCall({ sentiment: 'positive', emotion: 'happy', confidence: 0.87 }))
    // Anchored to the start: the delete button's own name ("Delete
    // case_4471.wav") also contains the filename, so an unanchored match
    // would ambiguously match both elements.
    const row = screen.getByRole('button', { name: /^case_4471\.wav/i })
    expect(row.getAttribute('aria-label')).not.toContain('Delete')
  })

  it('calls onSelectCall on click', async () => {
    const onSelectCall = vi.fn()
    const { container } = renderRow(makeCompleteCall(), { onSelectCall })
    await userEvent.click(container.firstElementChild as HTMLElement)
    expect(onSelectCall).toHaveBeenCalledWith('call-1')
  })

  it.each(['{Enter}', ' '])('calls onSelectCall on keyboard activation (%s)', async (key) => {
    const onSelectCall = vi.fn()
    const { container } = renderRow(makeCompleteCall(), { onSelectCall })
    const row = container.firstElementChild as HTMLElement
    row.focus()
    await userEvent.keyboard(key)
    expect(onSelectCall).toHaveBeenCalledWith('call-1')
  })

  it('renders the "Mono input — turns unattributed" warning when speakerAttributionUnavailable is true (Story 3.4, AC4)', () => {
    renderRow(makeCompleteCall({ speakerAttributionUnavailable: true }))
    expect(screen.getByText('Mono input — turns unattributed')).toBeInTheDocument()
  })

  it('does not render the warning when speakerAttributionUnavailable is explicitly false (Story 3.4, AC5)', () => {
    renderRow(makeCompleteCall({ speakerAttributionUnavailable: false }))
    expect(screen.queryByText('Mono input — turns unattributed')).not.toBeInTheDocument()
  })

  it('does not render the warning when speakerAttributionUnavailable is absent (Story 3.4, AC5)', () => {
    renderRow(makeCompleteCall())
    expect(screen.queryByText('Mono input — turns unattributed')).not.toBeInTheDocument()
  })

  // Code review (2026-08-17, Story 3.4): the warning div is a descendant of
  // the row's role="button" element, which computes its accessible name
  // from an explicit aria-label (Story 2.7) that would otherwise silently
  // drop the warning text from what screen readers announce.
  it('includes the attribution warning in the row\'s accessible name when speakerAttributionUnavailable is true', () => {
    renderRow(makeCompleteCall({ speakerAttributionUnavailable: true }))
    expect(screen.getByRole('button', { name: /mono input, turns unattributed/i })).toBeInTheDocument()
  })

  it('does not mention the attribution warning in the accessible name when speakerAttributionUnavailable is false or absent', () => {
    renderRow(makeCompleteCall())
    const row = screen.getByRole('button', { name: /^case_4471\.wav/i })
    expect(row.getAttribute('aria-label')).not.toMatch(/mono input/i)
  })
})

describe('CallRow — delete affordance (Story 2.3, AC1)', () => {
  it.each([
    ['validating', makeCall({ state: 'validating' })],
    ['queued', makeCall({ state: 'queued' })],
    ['processing', makeCall({ state: 'processing' })],
    ['failed', makeCall({ state: 'failed', errorMessage: 'x', errorNextStep: 'y' })],
    [
      'complete',
      makeCall({ state: 'complete', sentiment: 'negative', emotion: 'frustration', confidence: 0.84, durationSeconds: 402 }),
    ],
  ] as const)('renders a delete icon-button with the correct aria-label in the "%s" state', (_label, call) => {
    renderRow(call)
    expect(screen.getByRole('button', { name: 'Delete case_4471.wav' })).toBeInTheDocument()
  })

  it('clicking the delete icon-button calls onDeleteRequest with the row\'s call', async () => {
    const onDeleteRequest = vi.fn()
    const call = makeCall({ state: 'queued' })
    renderRow(call, { onDeleteRequest })

    await userEvent.click(screen.getByRole('button', { name: 'Delete case_4471.wav' }))
    expect(onDeleteRequest).toHaveBeenCalledWith(call)
  })

  it('keyboard activation (Enter) of the delete icon-button on a complete row does not also trigger onSelectCall', async () => {
    const onDeleteRequest = vi.fn()
    const onSelectCall = vi.fn()
    const call = makeCall({
      state: 'complete',
      sentiment: 'negative',
      emotion: 'frustration',
      confidence: 0.84,
      durationSeconds: 402,
    })
    renderRow(call, { onDeleteRequest, onSelectCall })

    screen.getByRole('button', { name: 'Delete case_4471.wav' }).focus()
    await userEvent.keyboard('{Enter}')

    expect(onDeleteRequest).toHaveBeenCalledWith(call)
    expect(onSelectCall).not.toHaveBeenCalled()
  })

  it('clicking the delete icon-button on a complete row does not also trigger onSelectCall', async () => {
    const onDeleteRequest = vi.fn()
    const onSelectCall = vi.fn()
    const call = makeCall({
      state: 'complete',
      sentiment: 'negative',
      emotion: 'frustration',
      confidence: 0.84,
      durationSeconds: 402,
    })
    renderRow(call, { onDeleteRequest, onSelectCall })

    await userEvent.click(screen.getByRole('button', { name: 'Delete case_4471.wav' }))
    expect(onDeleteRequest).toHaveBeenCalledWith(call)
    expect(onSelectCall).not.toHaveBeenCalled()
  })

  it('a deleting row shows "Deleting…" and is not selectable, regardless of underlying state', async () => {
    const onSelectCall = vi.fn()
    const call = makeCall({
      state: 'complete',
      sentiment: 'negative',
      emotion: 'frustration',
      confidence: 0.84,
      durationSeconds: 402,
      deleting: true,
    })
    const { container } = renderRow(call, { onSelectCall })

    expect(screen.getByText('case_4471.wav')).toBeInTheDocument()
    expect(screen.getByText(/deleting/i)).toBeInTheDocument()
    expect(screen.queryByRole('button', { name: /delete case_4471/i })).not.toBeInTheDocument()
    const row = container.firstElementChild as HTMLElement
    expect(row).not.toHaveAttribute('tabIndex')
    await userEvent.click(row)
    expect(onSelectCall).not.toHaveBeenCalled()
  })

  it('a deleteError renders inline without altering the rest of a complete row\'s content', () => {
    const call = makeCall({
      state: 'complete',
      sentiment: 'negative',
      emotion: 'frustration',
      confidence: 0.84,
      durationSeconds: 402,
      deleteError: 'Call abc-123 is still being processed and could not be safely deleted.',
      deleteErrorNextStep: 'Retry the delete request shortly, once processing has finished.',
    })
    renderRow(call)

    expect(screen.getByText(/could not be safely deleted/i)).toBeInTheDocument()
    expect(screen.getByText(/retry the delete request shortly/i)).toBeInTheDocument()
    // Normal complete-row content is still fully present.
    expect(screen.getByText('case_4471.wav')).toBeInTheDocument()
    expect(screen.getByText(/negative/i)).toBeInTheDocument()
    expect(screen.getByText('0.84')).toBeInTheDocument()
    expect(screen.getByText('06:42')).toBeInTheDocument()
  })
})
