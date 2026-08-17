import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { AnalysisDashboard } from './AnalysisDashboard'
import * as callsApi from '../api/callsApi'
import { ApiError } from '../api/callsApi'
import { DISCLAIMER_TEXT } from '../components/DisclaimerBar'

vi.mock('../api/callsApi', async () => {
  const actual = await vi.importActual<typeof import('../api/callsApi')>('../api/callsApi')
  return {
    ...actual,
    getCallStatus: vi.fn(),
    getTimeline: vi.fn(),
    getTranscript: vi.fn(),
    getAcousticSummary: vi.fn(),
  }
})

const COMPLETE_STATUS: callsApi.CallStatusResponse = {
  call_id: 'call-1',
  status: 'complete',
  filename: 'case_4471.wav',
  duration_seconds: 402,
  completed_at: '2026-08-15T00:00:00.000Z',
  overall_sentiment: 'negative',
  overall_emotion: 'frustration',
  overall_confidence: 0.84,
  single_modality_flag: false,
  secondary_signal_emotion: 'resignation',
  secondary_signal_confidence: 0.41,
}

const EMPTY_TIMELINE: callsApi.TimelineResponse = { call_id: 'call-1', status: 'complete', segments: [] }
const EMPTY_TRANSCRIPT: callsApi.TranscriptResponse = {
  call_id: 'call-1',
  status: 'complete',
  speaker_attribution_unavailable: false,
  turns: [],
}
const EMPTY_ACOUSTIC: callsApi.AcousticSummaryResponse = {
  call_id: 'call-1',
  status: 'complete',
  segment_count: 0,
  pitch_mean_hz: null,
  energy_rms_mean: null,
  speaking_rate_estimate: null,
  pause_ratio: null,
}

function mockAllSuccess(overrides: Partial<callsApi.CallStatusResponse> = {}) {
  vi.mocked(callsApi.getCallStatus).mockResolvedValue({ ...COMPLETE_STATUS, ...overrides })
  vi.mocked(callsApi.getTimeline).mockResolvedValue(EMPTY_TIMELINE)
  vi.mocked(callsApi.getTranscript).mockResolvedValue(EMPTY_TRANSCRIPT)
  vi.mocked(callsApi.getAcousticSummary).mockResolvedValue(EMPTY_ACOUSTIC)
}

beforeEach(() => {
  vi.mocked(callsApi.getCallStatus).mockReset()
  vi.mocked(callsApi.getTimeline).mockReset()
  vi.mocked(callsApi.getTranscript).mockReset()
  vi.mocked(callsApi.getAcousticSummary).mockReset()
})

afterEach(() => {
  vi.restoreAllMocks()
})

describe('AnalysisDashboard — loading and data states (Story 2.4, Task 8)', () => {
  it('renders a loading placeholder before data arrives', () => {
    vi.mocked(callsApi.getCallStatus).mockReturnValue(new Promise(() => {}))
    vi.mocked(callsApi.getTimeline).mockReturnValue(new Promise(() => {}))
    vi.mocked(callsApi.getTranscript).mockReturnValue(new Promise(() => {}))
    vi.mocked(callsApi.getAcousticSummary).mockReturnValue(new Promise(() => {}))

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    expect(screen.getByText(/loading/i)).toBeInTheDocument()
  })

  it('renders the Case strip and calls onBreadcrumbReady once status loads', async () => {
    mockAllSuccess()
    const onBreadcrumbReady = vi.fn()

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={onBreadcrumbReady} onBack={vi.fn()} />)

    expect(await screen.findByText('case_4471.wav')).toBeInTheDocument()
    expect(screen.getByText(/06:42/)).toBeInTheDocument()
    expect(screen.getByText(/QUEUE Session/)).toBeInTheDocument()
    expect(screen.getByText(/ANALYZED/)).toBeInTheDocument()
    expect(onBreadcrumbReady).toHaveBeenCalledWith('queue/session > case_4471.wav')
  })

  it('shows the ApiError message and a working back escape when getCallStatus rejects', async () => {
    vi.mocked(callsApi.getCallStatus).mockRejectedValue(
      new ApiError({
        error_code: 'CALL_NOT_FOUND',
        message: 'No Call found with id call-1.',
        next_step: 'Verify the Call id and try again.',
      }),
    )
    vi.mocked(callsApi.getTimeline).mockRejectedValue(new Error('irrelevant'))
    vi.mocked(callsApi.getTranscript).mockRejectedValue(new Error('irrelevant'))
    vi.mocked(callsApi.getAcousticSummary).mockRejectedValue(new Error('irrelevant'))
    const onBack = vi.fn()

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={onBack} />)

    expect(await screen.findByText('No Call found with id call-1.')).toBeInTheDocument()
    screen.getByRole('button', { name: /back/i }).click()
    expect(onBack).toHaveBeenCalled()
  })

  it('shows a generic fallback (never a raw error string) for a non-ApiError rejection', async () => {
    vi.mocked(callsApi.getCallStatus).mockRejectedValue(new TypeError('Failed to fetch'))
    vi.mocked(callsApi.getTimeline).mockRejectedValue(new Error('irrelevant'))
    vi.mocked(callsApi.getTranscript).mockRejectedValue(new Error('irrelevant'))
    vi.mocked(callsApi.getAcousticSummary).mockRejectedValue(new Error('irrelevant'))

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    expect(await screen.findByText('Could not reach the server.')).toBeInTheDocument()
    expect(screen.queryByText(/Failed to fetch/)).not.toBeInTheDocument()
  })

  it('renders the no-speech-detected state and none of the four summary cells', async () => {
    vi.mocked(callsApi.getCallStatus).mockResolvedValue({
      call_id: 'call-1',
      status: 'complete',
      filename: 'silence.wav',
      duration_seconds: 5,
      completed_at: '2026-08-15T00:00:00.000Z',
      no_speech_detected: true,
    })
    vi.mocked(callsApi.getTimeline).mockResolvedValue(EMPTY_TIMELINE)
    vi.mocked(callsApi.getTranscript).mockResolvedValue(EMPTY_TRANSCRIPT)
    vi.mocked(callsApi.getAcousticSummary).mockResolvedValue(EMPTY_ACOUSTIC)

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    expect(await screen.findByText(/no speech.*detected/i)).toBeInTheDocument()
    expect(screen.queryByText('Overall Sentiment')).not.toBeInTheDocument()
    expect(screen.queryByText('Segments Flagged')).not.toBeInTheDocument()
  })

  it('still renders the Case strip and summary cells when one secondary fetch (getTimeline) rejects, showing an honest "Unavailable" rather than a fabricated "0" for Segments Flagged', async () => {
    vi.mocked(callsApi.getCallStatus).mockResolvedValue(COMPLETE_STATUS)
    vi.mocked(callsApi.getTimeline).mockRejectedValue(new Error('network blip'))
    vi.mocked(callsApi.getTranscript).mockResolvedValue(EMPTY_TRANSCRIPT)
    vi.mocked(callsApi.getAcousticSummary).mockResolvedValue(EMPTY_ACOUSTIC)

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    expect(await screen.findByText('case_4471.wav')).toBeInTheDocument()
    expect(screen.getByText('Overall Sentiment')).toBeInTheDocument()
    expect(screen.getByText('Unavailable')).toBeInTheDocument()
    expect(screen.getByText('Emotional Timeline unavailable.')).toBeInTheDocument()
    expect(screen.queryByText('0')).not.toBeInTheDocument()
  })

  it('waits for all four requests to settle before rendering content, not just getCallStatus', async () => {
    vi.mocked(callsApi.getCallStatus).mockResolvedValue(COMPLETE_STATUS)
    let resolveTimeline: (value: callsApi.TimelineResponse) => void = () => {}
    vi.mocked(callsApi.getTimeline).mockReturnValue(
      new Promise((resolve) => {
        resolveTimeline = resolve
      }),
    )
    vi.mocked(callsApi.getTranscript).mockResolvedValue(EMPTY_TRANSCRIPT)
    vi.mocked(callsApi.getAcousticSummary).mockResolvedValue(EMPTY_ACOUSTIC)

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    await screen.findByText(/loading/i)
    expect(screen.queryByText('Overall Sentiment')).not.toBeInTheDocument()

    resolveTimeline(EMPTY_TIMELINE)

    expect(await screen.findByText('Overall Sentiment')).toBeInTheDocument()
  })
})

describe('AnalysisDashboard — summary cells (Story 2.4, Task 10)', () => {
  it('renders Overall Sentiment and Dominant Emotion with Confidence in the same cell', async () => {
    mockAllSuccess()

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    expect(await screen.findByText('Negative')).toBeInTheDocument()
    expect(screen.getByText('Frustration')).toBeInTheDocument()
    expect(screen.getByText('Confidence: 0.84')).toBeInTheDocument()
  })

  it('pairs Overall Sentiment/Dominant Emotion color with a glyph, never color alone', async () => {
    mockAllSuccess()

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    await screen.findByText('Negative')
    // 'negative' -> '▼' per sentimentGlyph; two cells (Overall Sentiment,
    // Dominant Emotion) both key their glyph off `overall_sentiment`.
    expect(screen.getAllByText('▼', { exact: false })).toHaveLength(2)
  })

  it('renders the real secondary signal reading with its own confidence', async () => {
    mockAllSuccess()

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    expect(await screen.findByText('Resignation')).toBeInTheDocument()
    expect(screen.getByText('Confidence: 0.41')).toBeInTheDocument()
  })

  it('renders "None flagged" when no secondary signal exists', async () => {
    mockAllSuccess({ secondary_signal_emotion: null, secondary_signal_confidence: null })

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    expect(await screen.findByText('None flagged')).toBeInTheDocument()
  })

  it('renders plain non-linked "0" for Segments Flagged when no segments are flagged', async () => {
    mockAllSuccess()

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    const zero = await screen.findByText('0')
    expect(zero.tagName).not.toBe('A')
  })

  it('renders a linked count for Segments Flagged combining low-confidence and disagreement segments', async () => {
    vi.mocked(callsApi.getCallStatus).mockResolvedValue(COMPLETE_STATUS)
    vi.mocked(callsApi.getTimeline).mockResolvedValue({
      call_id: 'call-1',
      status: 'complete',
      segments: [
        {
          segment_id: 'seg-lowconf',
          start_time: 0,
          end_time: 2,
          fused_sentiment: 'neutral',
          fused_emotion: 'neutral',
          fused_confidence: 0.3,
          disagreement_flag: false,
          low_confidence_flag: true,
          flag_reason: 'Confidence 0.30 is below the configured low-confidence threshold (0.50).',
          acoustic_emotion: null,
          acoustic_confidence: null,
          pitch_mean_hz: null,
          energy_rms_mean: null,
          speaking_rate_estimate: null,
          pause_ratio: null,
        },
        {
          segment_id: 'seg-disagree',
          start_time: 2,
          end_time: 4,
          fused_sentiment: 'negative',
          fused_emotion: 'angry',
          fused_confidence: 0.8,
          disagreement_flag: true,
          low_confidence_flag: false,
          flag_reason: null,
          acoustic_emotion: 'frustration',
          acoustic_confidence: 0.71,
          pitch_mean_hz: null,
          energy_rms_mean: null,
          speaking_rate_estimate: null,
          pause_ratio: null,
        },
        {
          segment_id: 'seg-clean',
          start_time: 4,
          end_time: 6,
          fused_sentiment: 'positive',
          fused_emotion: 'happy',
          fused_confidence: 0.9,
          disagreement_flag: false,
          low_confidence_flag: false,
          flag_reason: null,
          acoustic_emotion: null,
          acoustic_confidence: null,
          pitch_mean_hz: null,
          energy_rms_mean: null,
          speaking_rate_estimate: null,
          pause_ratio: null,
        },
      ],
    })
    vi.mocked(callsApi.getTranscript).mockResolvedValue(EMPTY_TRANSCRIPT)
    vi.mocked(callsApi.getAcousticSummary).mockResolvedValue(EMPTY_ACOUSTIC)

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    const link = await screen.findByRole('link', { name: '2' })
    expect(link).toHaveAttribute('href', '#segment-seg-lowconf')
  })

  it('code review (2026-08-16): clicking the Segments Flagged link selects the segment (Timeline shows it as --selected)', async () => {
    vi.mocked(callsApi.getCallStatus).mockResolvedValue(COMPLETE_STATUS)
    vi.mocked(callsApi.getTimeline).mockResolvedValue({
      call_id: 'call-1',
      status: 'complete',
      segments: [
        {
          segment_id: 'seg-lowconf',
          start_time: 0,
          end_time: 2,
          fused_sentiment: 'neutral',
          fused_emotion: 'neutral',
          fused_confidence: 0.3,
          disagreement_flag: false,
          low_confidence_flag: true,
          flag_reason: 'Confidence 0.30 is below the configured low-confidence threshold (0.50).',
          acoustic_emotion: null,
          acoustic_confidence: null,
          pitch_mean_hz: null,
          energy_rms_mean: null,
          speaking_rate_estimate: null,
          pause_ratio: null,
        },
      ],
    })
    vi.mocked(callsApi.getTranscript).mockResolvedValue(EMPTY_TRANSCRIPT)
    vi.mocked(callsApi.getAcousticSummary).mockResolvedValue(EMPTY_ACOUSTIC)

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    const link = await screen.findByRole('link', { name: '1' })
    await userEvent.click(link)

    expect(document.getElementById('segment-seg-lowconf')).toHaveClass('timeline__segment--selected')
  })
})

describe('AnalysisDashboard — Timeline/Transcript/Acoustic panels present (Story 2.4, Task 1/6)', () => {
  it('renders the Timeline, Transcript, and Acoustic panels', async () => {
    vi.mocked(callsApi.getCallStatus).mockResolvedValue(COMPLETE_STATUS)
    vi.mocked(callsApi.getTimeline).mockResolvedValue({
      call_id: 'call-1',
      status: 'complete',
      segments: [
        {
          segment_id: 'seg-1',
          start_time: 0,
          end_time: 2,
          fused_sentiment: 'negative',
          fused_emotion: 'angry',
          fused_confidence: 0.9,
          disagreement_flag: false,
          low_confidence_flag: false,
          flag_reason: null,
          acoustic_emotion: null,
          acoustic_confidence: null,
          pitch_mean_hz: null,
          energy_rms_mean: null,
          speaking_rate_estimate: null,
          pause_ratio: null,
        },
      ],
    })
    vi.mocked(callsApi.getTranscript).mockResolvedValue({
      call_id: 'call-1',
      status: 'complete',
      speaker_attribution_unavailable: false,
      turns: [
        {
          turn_id: 'turn-1',
          turn_index: 0,
          start_time: 0,
          end_time: 2,
          text: 'Thanks for holding.',
          text_sentiment: 'neutral',
          text_emotion: 'neutral',
          text_confidence: 0.7,
        },
      ],
    })
    vi.mocked(callsApi.getAcousticSummary).mockResolvedValue({
      call_id: 'call-1',
      status: 'complete',
      segment_count: 1,
      pitch_mean_hz: 142.3,
      energy_rms_mean: 0.041,
      speaking_rate_estimate: 2.7,
      pause_ratio: 0.18,
    })

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    expect(await screen.findByText('Thanks for holding.')).toBeInTheDocument()
    expect(screen.getByText('142 Hz')).toBeInTheDocument()
  })
})

describe('AnalysisDashboard — standing disclaimer bar (Story 2.6, Task 2)', () => {
  it('renders the exact fixed disclaimer copy for a completed Call with a result', async () => {
    mockAllSuccess()

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    expect(await screen.findByText(DISCLAIMER_TEXT)).toBeInTheDocument()
  })

  it('does not render the disclaimer for a no-speech-detected Call (nothing to disclaim)', async () => {
    vi.mocked(callsApi.getCallStatus).mockResolvedValue({
      call_id: 'call-1',
      status: 'complete',
      filename: 'silence.wav',
      duration_seconds: 5,
      completed_at: '2026-08-15T00:00:00.000Z',
      no_speech_detected: true,
    })
    vi.mocked(callsApi.getTimeline).mockResolvedValue(EMPTY_TIMELINE)
    vi.mocked(callsApi.getTranscript).mockResolvedValue(EMPTY_TRANSCRIPT)
    vi.mocked(callsApi.getAcousticSummary).mockResolvedValue(EMPTY_ACOUSTIC)

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    await screen.findByText(/no speech.*detected/i)
    expect(screen.queryByText(/Model output/)).not.toBeInTheDocument()
  })
})

describe('AnalysisDashboard — single-modality disclosure (Story 2.6, Task 3)', () => {
  it('renders the single-signal note when single_modality_flag is true', async () => {
    mockAllSuccess({ single_modality_flag: true })

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    expect(
      await screen.findByText(
        'Single-signal result — no transcript signal was available for this Call; based on the acoustic signal only.',
      ),
    ).toBeInTheDocument()
  })

  // Story 2.7 (Task 4; AC8 — deferred-work.md, Story 2.6 review): a
  // deliberate, app-wide role="status" convention for conditional Dashboard
  // notices (not the standing disclaimer, which is never conditional).
  it('the single-signal note has role="status"', async () => {
    mockAllSuccess({ single_modality_flag: true })

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    const note = await screen.findByText(
      'Single-signal result — no transcript signal was available for this Call; based on the acoustic signal only.',
    )
    expect(note).toHaveAttribute('role', 'status')
  })

  it('does not render the single-signal note when single_modality_flag is false', async () => {
    mockAllSuccess({ single_modality_flag: false })

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    await screen.findByText('case_4471.wav')
    expect(screen.queryByText(/Single-signal result/)).not.toBeInTheDocument()
  })

  it('does not render the single-signal note when single_modality_flag is undefined', async () => {
    vi.mocked(callsApi.getCallStatus).mockResolvedValue({
      ...COMPLETE_STATUS,
      single_modality_flag: undefined,
    })
    vi.mocked(callsApi.getTimeline).mockResolvedValue(EMPTY_TIMELINE)
    vi.mocked(callsApi.getTranscript).mockResolvedValue(EMPTY_TRANSCRIPT)
    vi.mocked(callsApi.getAcousticSummary).mockResolvedValue(EMPTY_ACOUSTIC)

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    await screen.findByText('case_4471.wav')
    expect(screen.queryByText(/Single-signal result/)).not.toBeInTheDocument()
  })
})

describe('AnalysisDashboard — whole-Call speaker-attribution-unavailable note (Story 3.4: real backend field, not the client-side heuristic)', () => {
  it('renders "Mono input — turns unattributed" when speaker_attribution_unavailable is true', async () => {
    vi.mocked(callsApi.getCallStatus).mockResolvedValue(COMPLETE_STATUS)
    vi.mocked(callsApi.getTimeline).mockResolvedValue(EMPTY_TIMELINE)
    vi.mocked(callsApi.getTranscript).mockResolvedValue({
      call_id: 'call-1',
      status: 'complete',
      speaker_attribution_unavailable: true,
      turns: [
        {
          turn_id: 'turn-1',
          turn_index: 0,
          start_time: 0,
          end_time: 2,
          text: 'Thanks for holding.',
          text_sentiment: 'neutral',
          text_emotion: 'neutral',
          text_confidence: 0.7,
        },
      ],
    })
    vi.mocked(callsApi.getAcousticSummary).mockResolvedValue(EMPTY_ACOUSTIC)

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    expect(await screen.findByText('Mono input — turns unattributed')).toBeInTheDocument()
  })

  // Story 2.7 (Task 4; AC8 — deferred-work.md, Story 2.6 review).
  it('the "Mono input — turns unattributed" note has role="status"', async () => {
    vi.mocked(callsApi.getCallStatus).mockResolvedValue(COMPLETE_STATUS)
    vi.mocked(callsApi.getTimeline).mockResolvedValue(EMPTY_TIMELINE)
    vi.mocked(callsApi.getTranscript).mockResolvedValue({
      call_id: 'call-1',
      status: 'complete',
      speaker_attribution_unavailable: true,
      turns: [
        {
          turn_id: 'turn-1',
          turn_index: 0,
          start_time: 0,
          end_time: 2,
          text: 'Thanks for holding.',
          text_sentiment: 'neutral',
          text_emotion: 'neutral',
          text_confidence: 0.7,
        },
      ],
    })
    vi.mocked(callsApi.getAcousticSummary).mockResolvedValue(EMPTY_ACOUSTIC)

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    const note = await screen.findByText('Mono input — turns unattributed')
    expect(note).toHaveAttribute('role', 'status')
  })

  it('does not render the note when speaker_attribution_unavailable is false, even with an unattributed turn', async () => {
    // Story 3.4: proves the note is now driven by the real backend field,
    // not a client-side "every turn lacks speaker_label" re-derivation —
    // a Call can have `speaker_attribution_unavailable: false` (e.g. a
    // stereo Call whose channel-based attribution simply hasn't populated
    // this one turn yet) without ever showing the note.
    vi.mocked(callsApi.getCallStatus).mockResolvedValue(COMPLETE_STATUS)
    vi.mocked(callsApi.getTimeline).mockResolvedValue(EMPTY_TIMELINE)
    vi.mocked(callsApi.getTranscript).mockResolvedValue({
      call_id: 'call-1',
      status: 'complete',
      speaker_attribution_unavailable: false,
      turns: [
        {
          turn_id: 'turn-1',
          turn_index: 0,
          start_time: 0,
          end_time: 2,
          text: 'Thanks for holding.',
          text_sentiment: 'neutral',
          text_emotion: 'neutral',
          text_confidence: 0.7,
        },
      ],
    })
    vi.mocked(callsApi.getAcousticSummary).mockResolvedValue(EMPTY_ACOUSTIC)

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    await screen.findByText('Thanks for holding.')
    expect(screen.queryByText('Mono input — turns unattributed')).not.toBeInTheDocument()
  })

  it('does not render the note when at least one turn carries a real speaker_label', async () => {
    vi.mocked(callsApi.getCallStatus).mockResolvedValue(COMPLETE_STATUS)
    vi.mocked(callsApi.getTimeline).mockResolvedValue(EMPTY_TIMELINE)
    vi.mocked(callsApi.getTranscript).mockResolvedValue({
      call_id: 'call-1',
      status: 'complete',
      speaker_attribution_unavailable: false,
      turns: [
        {
          turn_id: 'turn-1',
          turn_index: 0,
          start_time: 0,
          end_time: 2,
          text: 'Thanks for holding.',
          text_sentiment: 'neutral',
          text_emotion: 'neutral',
          text_confidence: 0.7,
          speaker_label: 'Agent',
        },
      ],
    })
    vi.mocked(callsApi.getAcousticSummary).mockResolvedValue(EMPTY_ACOUSTIC)

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    await screen.findByText('Thanks for holding.')
    expect(screen.queryByText('Mono input — turns unattributed')).not.toBeInTheDocument()
  })

  it('does not render the note when there are no transcript turns', async () => {
    mockAllSuccess()

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    await screen.findByText('case_4471.wav')
    expect(screen.queryByText('Mono input — turns unattributed')).not.toBeInTheDocument()
  })

  it('does not render the note when the transcript fetch failed', async () => {
    vi.mocked(callsApi.getCallStatus).mockResolvedValue(COMPLETE_STATUS)
    vi.mocked(callsApi.getTimeline).mockResolvedValue(EMPTY_TIMELINE)
    vi.mocked(callsApi.getTranscript).mockRejectedValue(new Error('network blip'))
    vi.mocked(callsApi.getAcousticSummary).mockResolvedValue(EMPTY_ACOUSTIC)

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    await screen.findByText('Transcript unavailable.')
    expect(screen.queryByText('Mono input — turns unattributed')).not.toBeInTheDocument()
  })
})

describe('AnalysisDashboard — terminology discipline regression (Story 2.6, Task 5)', () => {
  it('never swaps Overall Sentiment and Dominant Emotion values', async () => {
    mockAllSuccess({ overall_sentiment: 'negative', overall_emotion: 'frustration' })

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    const sentimentLabel = await screen.findByText('Overall Sentiment')
    const sentimentCell = sentimentLabel.closest('.analysis-dashboard__summary-cell') as HTMLElement
    expect(sentimentCell).toHaveTextContent('Negative')
    expect(sentimentCell).not.toHaveTextContent('Frustration')

    const emotionLabel = screen.getByText('Dominant Emotion')
    const emotionCell = emotionLabel.closest('.analysis-dashboard__summary-cell') as HTMLElement
    expect(emotionCell).toHaveTextContent('Frustration')
    expect(emotionCell).not.toHaveTextContent('Negative')
  })
})

// Code review (2026-08-16, Story 2.7): Task 4's own comment claimed a
// "deliberate, app-wide role=status convention for conditional Dashboard
// notices" but only applied it to 2 of ~6 equally-conditional notices in
// this file. Extending it to the rest makes that claim true.
describe('AnalysisDashboard — role="status" on every conditional notice (Story 2.7 code review patch)', () => {
  it('the getCallStatus error message has role="status"', async () => {
    vi.mocked(callsApi.getCallStatus).mockRejectedValue(
      new ApiError({
        error_code: 'CALL_NOT_FOUND',
        message: 'No Call found with id call-1.',
        next_step: 'Verify the Call id and try again.',
      }),
    )
    vi.mocked(callsApi.getTimeline).mockRejectedValue(new Error('irrelevant'))
    vi.mocked(callsApi.getTranscript).mockRejectedValue(new Error('irrelevant'))
    vi.mocked(callsApi.getAcousticSummary).mockRejectedValue(new Error('irrelevant'))

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    const message = await screen.findByText('No Call found with id call-1.')
    expect(message).toHaveAttribute('role', 'status')
  })

  it('the no-speech-detected message has role="status"', async () => {
    vi.mocked(callsApi.getCallStatus).mockResolvedValue({
      call_id: 'call-1',
      status: 'complete',
      filename: 'silence.wav',
      duration_seconds: 5,
      completed_at: '2026-08-15T00:00:00.000Z',
      no_speech_detected: true,
    })
    vi.mocked(callsApi.getTimeline).mockResolvedValue(EMPTY_TIMELINE)
    vi.mocked(callsApi.getTranscript).mockResolvedValue(EMPTY_TRANSCRIPT)
    vi.mocked(callsApi.getAcousticSummary).mockResolvedValue(EMPTY_ACOUSTIC)

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    const message = await screen.findByText(/no speech.*detected/i)
    expect(message).toHaveAttribute('role', 'status')
  })

  it('each of the three panel-unavailable messages has role="status"', async () => {
    vi.mocked(callsApi.getCallStatus).mockResolvedValue(COMPLETE_STATUS)
    vi.mocked(callsApi.getTimeline).mockRejectedValue(new Error('network blip'))
    vi.mocked(callsApi.getTranscript).mockRejectedValue(new Error('network blip'))
    vi.mocked(callsApi.getAcousticSummary).mockRejectedValue(new Error('network blip'))

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    expect(await screen.findByText('Emotional Timeline unavailable.')).toHaveAttribute('role', 'status')
    expect(screen.getByText('Transcript unavailable.')).toHaveAttribute('role', 'status')
    expect(screen.getByText('Acoustic insights unavailable.')).toHaveAttribute('role', 'status')
  })
})

describe('AnalysisDashboard — selection synchronization (Story 2.5, Task 6/8)', () => {
  it('selecting a Timeline segment updates the Acoustic panel to that segment’s own metrics', async () => {
    vi.mocked(callsApi.getCallStatus).mockResolvedValue(COMPLETE_STATUS)
    vi.mocked(callsApi.getTimeline).mockResolvedValue({
      call_id: 'call-1',
      status: 'complete',
      segments: [
        {
          segment_id: 'seg-1',
          start_time: 0,
          end_time: 2,
          fused_sentiment: 'negative',
          fused_emotion: 'angry',
          fused_confidence: 0.9,
          disagreement_flag: false,
          low_confidence_flag: false,
          flag_reason: null,
          acoustic_emotion: null,
          acoustic_confidence: null,
          pitch_mean_hz: 210.5,
          energy_rms_mean: 0.061,
          speaking_rate_estimate: 4.1,
          pause_ratio: 0.15,
        },
      ],
    })
    vi.mocked(callsApi.getTranscript).mockResolvedValue(EMPTY_TRANSCRIPT)
    vi.mocked(callsApi.getAcousticSummary).mockResolvedValue({
      call_id: 'call-1',
      status: 'complete',
      segment_count: 1,
      pitch_mean_hz: 142.3,
      energy_rms_mean: 0.041,
      speaking_rate_estimate: 2.7,
      pause_ratio: 0.18,
    })

    render(<AnalysisDashboard callId="call-1" onBreadcrumbReady={vi.fn()} onBack={vi.fn()} />)

    // Default: the call-level aggregate (Story 2.4's unchanged behavior).
    expect(await screen.findByText('142 Hz')).toBeInTheDocument()

    await userEvent.click(document.getElementById('segment-seg-1') as HTMLElement)

    expect(await screen.findByText('211 Hz')).toBeInTheDocument()
    expect(screen.queryByText('142 Hz')).not.toBeInTheDocument()
  })
})
