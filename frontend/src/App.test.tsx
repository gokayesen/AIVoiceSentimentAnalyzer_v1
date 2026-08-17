import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import { App } from './App'
import * as callsApi from './api/callsApi'

vi.mock('./api/callsApi', async () => {
  const actual = await vi.importActual<typeof import('./api/callsApi')>('./api/callsApi')
  return {
    ...actual,
    uploadCall: vi.fn(),
    getCallStatus: vi.fn(),
    getTimeline: vi.fn(),
    getTranscript: vi.fn(),
    getAcousticSummary: vi.fn(),
  }
})

function getHiddenFileInput(container: HTMLElement) {
  return container.querySelector('input[type="file"]') as HTMLInputElement
}

function selectFile(input: HTMLInputElement, file: File) {
  Object.defineProperty(input, 'files', { value: [file], configurable: true })
  fireEvent.change(input)
}

describe('App', () => {
  it('loads directly into the Session Call List — no login/account screen (AC1)', () => {
    render(<App />)
    expect(screen.getByRole('heading', { name: /this session/i })).toBeInTheDocument()
    expect(screen.queryByText(/log ?in|sign ?in|sign ?up/i)).not.toBeInTheDocument()
  })

  it('renders the shared AppHeader above the Session Call List', () => {
    render(<App />)
    expect(screen.getByText(/VOICE SENTIMENT/i)).toBeInTheDocument()
  })
})

describe('App — Dashboard navigation (Story 2.4, Task 7)', () => {
  beforeEach(() => {
    vi.mocked(callsApi.uploadCall).mockReset()
    vi.mocked(callsApi.getCallStatus).mockReset()
    vi.mocked(callsApi.getTimeline).mockReset()
    vi.mocked(callsApi.getTranscript).mockReset()
    vi.mocked(callsApi.getAcousticSummary).mockReset()
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('opening a complete Call\'s Dashboard hides (not unmounts) the list, and the breadcrumb returns to it with the row still present', async () => {
    vi.useFakeTimers({ shouldAdvanceTime: true })
    vi.mocked(callsApi.uploadCall).mockResolvedValue({ call_id: 'call-1', status: 'queued' })
    vi.mocked(callsApi.getCallStatus)
      .mockResolvedValueOnce({
        call_id: 'call-1',
        status: 'complete',
        filename: 'case_4471.wav',
        duration_seconds: 402,
        overall_sentiment: 'negative',
        overall_emotion: 'frustration',
        overall_confidence: 0.84,
      })
      .mockResolvedValue({
        call_id: 'call-1',
        status: 'complete',
        filename: 'case_4471.wav',
        duration_seconds: 402,
        completed_at: '2026-08-15T00:00:00.000Z',
        overall_sentiment: 'negative',
        overall_emotion: 'frustration',
        overall_confidence: 0.84,
        secondary_signal_emotion: null,
        secondary_signal_confidence: null,
      })
    vi.mocked(callsApi.getTimeline).mockResolvedValue({ call_id: 'call-1', status: 'complete', segments: [] })
    vi.mocked(callsApi.getTranscript).mockResolvedValue({
      call_id: 'call-1',
      status: 'complete',
      speaker_attribution_unavailable: false,
      turns: [],
    })
    vi.mocked(callsApi.getAcousticSummary).mockResolvedValue({
      call_id: 'call-1',
      status: 'complete',
      segment_count: 0,
      pitch_mean_hz: null,
      energy_rms_mean: null,
      speaking_rate_estimate: null,
      pause_ratio: null,
    })

    const { container } = render(<App />)
    const input = getHiddenFileInput(container)
    selectFile(input, new File(['audio'], 'case_4471.wav', { type: 'audio/wav' }))
    await vi.waitFor(() => expect(screen.getByText(/queued/i)).toBeInTheDocument())
    await vi.advanceTimersByTimeAsync(2000)
    await vi.waitFor(() => expect(screen.getByText('0.84')).toBeInTheDocument())

    fireEvent.click(screen.getByText('case_4471.wav'))

    // Dashboard is now showing; the list is hidden, not unmounted.
    await vi.waitFor(() => expect(screen.getByText(/DURATION/)).toBeInTheDocument())
    expect(screen.getByText('This Session').closest('[hidden]')).not.toBeNull()

    const breadcrumb = await screen.findByRole('button', { name: /queue\/session.*case_4471\.wav/i })
    fireEvent.click(breadcrumb)

    // Back on the list; the earlier row survived (never unmounted).
    expect(screen.getByText('This Session').closest('[hidden]')).toBeNull()
    expect(screen.getByText('case_4471.wav')).toBeInTheDocument()
  })
})
