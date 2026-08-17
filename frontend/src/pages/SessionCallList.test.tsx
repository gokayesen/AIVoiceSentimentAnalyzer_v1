import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { SessionCallList } from './SessionCallList'
import * as callsApi from '../api/callsApi'

vi.mock('../api/callsApi', async () => {
  const actual = await vi.importActual<typeof import('../api/callsApi')>('../api/callsApi')
  return {
    ...actual,
    uploadCall: vi.fn(),
    getCallStatus: vi.fn(),
    deleteCall: vi.fn(),
  }
})

function makeFile(name = 'case_4471.wav') {
  return new File(['audio bytes'], name, { type: 'audio/wav' })
}

function getHiddenFileInput(container: HTMLElement) {
  return container.querySelector('input[type="file"]') as HTMLInputElement
}

// `userEvent.upload` doesn't reliably re-fire `change` on a second call to
// the same <input> once the component has reset `event.target.value = ''`
// itself (a jsdom/user-event same-input-tracking quirk, not a real-browser
// limitation) — a manual `files` assignment + `fireEvent.change` sidesteps
// it and is what every multi-upload test below uses.
function selectFile(input: HTMLInputElement, file: File) {
  Object.defineProperty(input, 'files', { value: [file], configurable: true })
  fireEvent.change(input)
}

describe('SessionCallList', () => {
  it('renders the session title and an "+ Add call" control', () => {
    render(<SessionCallList />)
    expect(screen.getByRole('heading', { name: /this session/i })).toBeInTheDocument()
    expect(screen.getByRole('button', { name: /\+\s*add call/i })).toBeInTheDocument()
  })

  it('shows a plain upload prompt when there are zero Calls (AC4)', () => {
    render(<SessionCallList />)
    expect(screen.getByText(/no calls yet/i)).toBeInTheDocument()
  })

  it('renders no illustration/mascot graphic in the empty state (AC4)', () => {
    const { container } = render(<SessionCallList />)
    expect(container.querySelectorAll('img')).toHaveLength(0)
    expect(container.querySelectorAll('svg')).toHaveLength(0)
  })

  it('never uses exclamation-point hype copy (EXPERIENCE.md Voice and Tone)', () => {
    const { container } = render(<SessionCallList />)
    expect(container.textContent).not.toMatch(/!/)
  })
})

describe('SessionCallList — upload flow (AC1, AC2, AC3)', () => {
  beforeEach(() => {
    vi.mocked(callsApi.uploadCall).mockReset()
    vi.mocked(callsApi.getCallStatus).mockReset()
  })

  it('shows a validating row immediately on file-picker selection, before the upload resolves', async () => {
    let resolveUpload!: (value: { call_id: string; status: string }) => void
    vi.mocked(callsApi.uploadCall).mockReturnValue(
      new Promise((resolve) => {
        resolveUpload = resolve
      }),
    )
    const { container } = render(<SessionCallList />)

    const input = getHiddenFileInput(container)
    selectFile(input, makeFile())

    expect(screen.getByText('case_4471.wav')).toBeInTheDocument()
    expect(screen.getByText(/validating/i)).toBeInTheDocument()

    resolveUpload({ call_id: 'call-1', status: 'queued' })
    await waitFor(() => expect(screen.getByText(/queued/i)).toBeInTheDocument())
  })

  it('drag-and-drop triggers the identical upload flow (AC2)', async () => {
    vi.mocked(callsApi.uploadCall).mockResolvedValue({ call_id: 'call-1', status: 'queued' })
    const { container } = render(<SessionCallList />)

    const dropZone = container.querySelector('.session-call-list__content') as HTMLElement
    const file = makeFile('dropped.wav')
    const dataTransfer = { files: [file] }

    dropZone.dispatchEvent(
      Object.assign(new Event('drop', { bubbles: true, cancelable: true }), { dataTransfer }),
    )

    await waitFor(() => expect(callsApi.uploadCall).toHaveBeenCalledWith(file))
    expect(await screen.findByText('dropped.wav')).toBeInTheDocument()
  })

  it('a validation failure renders the error + Retry without removing other existing rows', async () => {
    vi.mocked(callsApi.uploadCall)
      .mockResolvedValueOnce({ call_id: 'call-good', status: 'queued' })
      .mockRejectedValueOnce(
        new callsApi.ApiError({
          error_code: 'UNSUPPORTED_FORMAT',
          message: 'Unsupported audio format: .ogg. Accepted formats are WAV, MP3, and M4A.',
          next_step: 'Re-export the recording as WAV, MP3, or M4A and upload again.',
        }),
      )
    const { container } = render(<SessionCallList />)
    const input = getHiddenFileInput(container)

    selectFile(input, makeFile('good.wav'))
    await waitFor(() => expect(screen.getByText('good.wav')).toBeInTheDocument())

    selectFile(input, makeFile('bad.ogg'))

    await waitFor(() => expect(screen.getByText(/unsupported audio format/i)).toBeInTheDocument())
    expect(screen.getByText('good.wav')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('a non-ApiError rejection (network failure) shows a friendly fallback, never a raw error string', async () => {
    vi.mocked(callsApi.uploadCall).mockRejectedValueOnce(new TypeError('Failed to fetch'))
    const { container } = render(<SessionCallList />)
    const input = getHiddenFileInput(container)

    selectFile(input, makeFile('network-fail.wav'))

    await waitFor(() => expect(screen.getByText(/could not reach the server/i)).toBeInTheDocument())
    expect(screen.getByText(/check your connection/i)).toBeInTheDocument()
    expect(screen.queryByText(/failed to fetch/i)).not.toBeInTheDocument()
  })

  it('Retry re-submits the same file and clears the failed row', async () => {
    vi.mocked(callsApi.uploadCall)
      .mockRejectedValueOnce(
        new callsApi.ApiError({
          error_code: 'UNSUPPORTED_FORMAT',
          message: 'Unsupported audio format.',
          next_step: 'Re-export and try again.',
        }),
      )
      .mockResolvedValueOnce({ call_id: 'call-2', status: 'queued' })
    const { container } = render(<SessionCallList />)
    const input = getHiddenFileInput(container)

    selectFile(input, makeFile('retry-me.wav'))
    await waitFor(() => expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: 'Retry' }))

    await waitFor(() => expect(screen.getByText(/queued/i)).toBeInTheDocument())
    expect(screen.queryByRole('button', { name: 'Retry' })).not.toBeInTheDocument()
    expect(callsApi.uploadCall).toHaveBeenCalledTimes(2)
  })
})

describe('SessionCallList — status polling (AC5, AC6, AC7, AC8)', () => {
  beforeEach(() => {
    vi.mocked(callsApi.uploadCall).mockReset()
    vi.mocked(callsApi.getCallStatus).mockReset()
    vi.mocked(callsApi.deleteCall).mockReset()
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('polls a queued Call and transitions the row to complete with Sentiment/Emotion/Confidence/duration', async () => {
    vi.mocked(callsApi.uploadCall).mockResolvedValue({ call_id: 'call-1', status: 'queued' })
    vi.mocked(callsApi.getCallStatus).mockResolvedValue({
      call_id: 'call-1',
      status: 'complete',
      filename: 'case_4471.wav',
      duration_seconds: 402,
      overall_sentiment: 'negative',
      overall_emotion: 'frustration',
      overall_confidence: 0.84,
    })
    const { container } = render(<SessionCallList />)
    const input = getHiddenFileInput(container)

    selectFile(input, makeFile())
    await vi.waitFor(() => expect(screen.getByText(/queued/i)).toBeInTheDocument())

    await vi.advanceTimersByTimeAsync(2000)

    await vi.waitFor(() => expect(screen.getByText('0.84')).toBeInTheDocument())
    expect(screen.getByText('06:42')).toBeInTheDocument()
  })

  it('polls a queued Call that completes with no_speech_detected and shows a distinct state, not a blank sentiment badge (Story 2.4 code review)', async () => {
    vi.mocked(callsApi.uploadCall).mockResolvedValue({ call_id: 'call-1', status: 'queued' })
    vi.mocked(callsApi.getCallStatus).mockResolvedValue({
      call_id: 'call-1',
      status: 'complete',
      filename: 'silence.wav',
      duration_seconds: 5,
      no_speech_detected: true,
    })
    const { container } = render(<SessionCallList />)
    const input = getHiddenFileInput(container)

    selectFile(input, makeFile())
    await vi.waitFor(() => expect(screen.getByText(/queued/i)).toBeInTheDocument())

    await vi.advanceTimersByTimeAsync(2000)

    await vi.waitFor(() => expect(screen.getByText('No speech detected')).toBeInTheDocument())
    expect(screen.queryByText('Undefined')).not.toBeInTheDocument()
  })

  it('polls a processing Call that fails and shows a non-blaming message with Retry', async () => {
    vi.mocked(callsApi.uploadCall).mockResolvedValue({ call_id: 'call-1', status: 'processing' })
    vi.mocked(callsApi.getCallStatus).mockResolvedValue({
      call_id: 'call-1',
      status: 'failed',
      filename: 'case_4471.wav',
      duration_seconds: 402,
    })
    const { container } = render(<SessionCallList />)
    const input = getHiddenFileInput(container)

    selectFile(input, makeFile())
    await vi.waitFor(() => expect(screen.getByText(/processing/i)).toBeInTheDocument())

    await vi.advanceTimersByTimeAsync(2000)

    await vi.waitFor(() =>
      expect(screen.getByText(/could not be analyzed/i)).toBeInTheDocument(),
    )
    expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument()
  })

  it('polls a Call that completes with speaker_attribution_unavailable and shows the row warning (Story 3.4, AC4)', async () => {
    vi.mocked(callsApi.uploadCall).mockResolvedValue({ call_id: 'call-1', status: 'queued' })
    vi.mocked(callsApi.getCallStatus).mockResolvedValue({
      call_id: 'call-1',
      status: 'complete',
      filename: 'case_4471.wav',
      duration_seconds: 402,
      overall_sentiment: 'negative',
      overall_emotion: 'frustration',
      overall_confidence: 0.84,
      speaker_attribution_unavailable: true,
    })
    const { container } = render(<SessionCallList />)
    const input = getHiddenFileInput(container)

    selectFile(input, makeFile())
    await vi.waitFor(() => expect(screen.getByText(/queued/i)).toBeInTheDocument())

    await vi.advanceTimersByTimeAsync(2000)

    await vi.waitFor(() =>
      expect(screen.getByText('Mono input — turns unattributed')).toBeInTheDocument(),
    )
  })

  it('excludes a deleting row from polling (Story 2.3 Task 6)', async () => {
    vi.mocked(callsApi.uploadCall).mockResolvedValue({ call_id: 'call-1', status: 'queued' })
    vi.mocked(callsApi.getCallStatus).mockResolvedValue({
      call_id: 'call-1',
      status: 'queued',
      filename: 'case_4471.wav',
      duration_seconds: 402,
    })
    vi.mocked(callsApi.deleteCall).mockReturnValue(new Promise(() => {})) // never resolves in this test
    const { container } = render(<SessionCallList />)
    const input = getHiddenFileInput(container)

    selectFile(input, makeFile())
    await vi.waitFor(() => expect(screen.getByText(/queued/i)).toBeInTheDocument())

    fireEvent.click(screen.getByRole('button', { name: /delete case_4471.wav/i }))
    fireEvent.click(screen.getByRole('button', { name: /^delete$/i }))
    await vi.waitFor(() => expect(screen.getByText(/deleting/i)).toBeInTheDocument())

    vi.mocked(callsApi.getCallStatus).mockClear()
    await vi.advanceTimersByTimeAsync(2000)

    expect(callsApi.getCallStatus).not.toHaveBeenCalled()
  })
})

describe('SessionCallList — onSelectCall passthrough (Story 2.4, Task 7)', () => {
  beforeEach(() => {
    vi.mocked(callsApi.uploadCall).mockReset()
    vi.mocked(callsApi.getCallStatus).mockReset()
    vi.useFakeTimers({ shouldAdvanceTime: true })
  })

  afterEach(() => {
    vi.useRealTimers()
  })

  it('calls onSelectCall with the call id when a complete row is clicked', async () => {
    vi.mocked(callsApi.uploadCall).mockResolvedValue({ call_id: 'call-1', status: 'queued' })
    vi.mocked(callsApi.getCallStatus).mockResolvedValue({
      call_id: 'call-1',
      status: 'complete',
      filename: 'case_4471.wav',
      duration_seconds: 402,
      overall_sentiment: 'negative',
      overall_emotion: 'frustration',
      overall_confidence: 0.84,
    })
    const onSelectCall = vi.fn()
    const { container } = render(<SessionCallList onSelectCall={onSelectCall} />)
    const input = getHiddenFileInput(container)

    selectFile(input, makeFile())
    await vi.waitFor(() => expect(screen.getByText(/queued/i)).toBeInTheDocument())
    await vi.advanceTimersByTimeAsync(2000)
    await vi.waitFor(() => expect(screen.getByText('0.84')).toBeInTheDocument())

    fireEvent.click(screen.getByText('case_4471.wav'))

    expect(onSelectCall).toHaveBeenCalledWith('call-1')
  })
})

describe('SessionCallList — delete flow (AC1, AC3, AC4, AC5, AC6, AC7, AC8, AC9)', () => {
  beforeEach(() => {
    vi.mocked(callsApi.uploadCall).mockReset()
    vi.mocked(callsApi.getCallStatus).mockReset()
    vi.mocked(callsApi.deleteCall).mockReset()
  })

  async function uploadOneCall(container: HTMLElement, filename = 'case_4471.wav') {
    vi.mocked(callsApi.uploadCall).mockResolvedValueOnce({ call_id: 'call-1', status: 'complete' })
    const input = getHiddenFileInput(container)
    selectFile(input, makeFile(filename))
    await waitFor(() => expect(screen.getByText(filename)).toBeInTheDocument())
  }

  it('clicking the delete icon-button opens the confirm dialog with the row\'s filename', async () => {
    const { container } = render(<SessionCallList />)
    await uploadOneCall(container)

    await userEvent.click(screen.getByRole('button', { name: /delete case_4471.wav/i }))

    const dialog = screen.getByRole('alertdialog')
    expect(within(dialog).getByText('case_4471.wav')).toBeInTheDocument()
  })

  it('Cancel closes the dialog and changes nothing', async () => {
    const { container } = render(<SessionCallList />)
    await uploadOneCall(container)

    await userEvent.click(screen.getByRole('button', { name: /delete case_4471.wav/i }))
    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(screen.getByText('case_4471.wav')).toBeInTheDocument()
    expect(callsApi.deleteCall).not.toHaveBeenCalled()
  })

  it('Escape closes the dialog with no state change', async () => {
    const { container } = render(<SessionCallList />)
    await uploadOneCall(container)

    await userEvent.click(screen.getByRole('button', { name: /delete case_4471.wav/i }))
    fireEvent.keyDown(document, { key: 'Escape' })

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(callsApi.deleteCall).not.toHaveBeenCalled()
  })

  it('confirming Delete shows a deleting state, then removes the row on success, leaving other rows untouched', async () => {
    let resolveDelete!: () => void
    vi.mocked(callsApi.deleteCall).mockReturnValue(
      new Promise((resolve) => {
        resolveDelete = () => resolve(undefined)
      }),
    )
    const { container } = render(<SessionCallList />)
    await uploadOneCall(container, 'case_4471.wav')
    vi.mocked(callsApi.uploadCall).mockResolvedValueOnce({ call_id: 'call-2', status: 'complete' })
    const input = getHiddenFileInput(container)
    selectFile(input, makeFile('case_4498.wav'))
    await waitFor(() => expect(screen.getByText('case_4498.wav')).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: /delete case_4471.wav/i }))
    await userEvent.click(screen.getByRole('button', { name: /^delete$/i }))

    expect(screen.queryByRole('alertdialog')).not.toBeInTheDocument()
    expect(callsApi.deleteCall).toHaveBeenCalledWith('call-1')
    await waitFor(() => expect(screen.getByText(/deleting/i)).toBeInTheDocument())
    // The other row is untouched throughout — never enters a deleting state.
    expect(screen.getByText('case_4498.wav')).toBeInTheDocument()

    resolveDelete()
    await waitFor(() => expect(screen.queryByText('case_4471.wav')).not.toBeInTheDocument())
    expect(screen.getByText('case_4498.wav')).toBeInTheDocument()
  })

  it('deleting a still-validating row removes it locally without calling the backend', async () => {
    let resolveUpload!: (value: { call_id: string; status: string }) => void
    vi.mocked(callsApi.uploadCall).mockReturnValue(
      new Promise((resolve) => {
        resolveUpload = resolve
      }),
    )
    const { container } = render(<SessionCallList />)
    const input = getHiddenFileInput(container)
    selectFile(input, makeFile())
    await waitFor(() => expect(screen.getByText(/validating/i)).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: /delete case_4471.wav/i }))
    await userEvent.click(screen.getByRole('button', { name: /^delete$/i }))

    expect(screen.queryByText('case_4471.wav')).not.toBeInTheDocument()
    expect(callsApi.deleteCall).not.toHaveBeenCalled()

    // The in-flight upload resolving afterward must not resurrect the row.
    resolveUpload({ call_id: 'call-1', status: 'queued' })
    await new Promise((resolve) => setTimeout(resolve, 0))
    expect(screen.queryByText('case_4471.wav')).not.toBeInTheDocument()
  })

  it('a failed delete (ApiError) leaves the row in place, showing the error, and clears the deleting state', async () => {
    vi.mocked(callsApi.deleteCall).mockRejectedValueOnce(
      new callsApi.ApiError({
        error_code: 'CALL_DELETION_IN_PROGRESS',
        message: 'Call call-1 is still being processed and could not be safely deleted.',
        next_step: 'Retry the delete request shortly, once processing has finished.',
      }),
    )
    const { container } = render(<SessionCallList />)
    await uploadOneCall(container)

    await userEvent.click(screen.getByRole('button', { name: /delete case_4471.wav/i }))
    await userEvent.click(screen.getByRole('button', { name: /^delete$/i }))

    await waitFor(() =>
      expect(screen.getByText(/could not be safely deleted/i)).toBeInTheDocument(),
    )
    expect(screen.getByText('case_4471.wav')).toBeInTheDocument()
    expect(screen.queryByText(/deleting/i)).not.toBeInTheDocument()
  })

  it('a non-ApiError delete rejection shows a friendly fallback, never a raw error string', async () => {
    vi.mocked(callsApi.deleteCall).mockRejectedValueOnce(new TypeError('Failed to fetch'))
    const { container } = render(<SessionCallList />)
    await uploadOneCall(container)

    await userEvent.click(screen.getByRole('button', { name: /delete case_4471.wav/i }))
    await userEvent.click(screen.getByRole('button', { name: /^delete$/i }))

    await waitFor(() => expect(screen.getByText(/could not reach the server/i)).toBeInTheDocument())
    expect(screen.queryByText(/failed to fetch/i)).not.toBeInTheDocument()
  })

  it('a non-complete (queued) row can be deleted too', async () => {
    vi.mocked(callsApi.uploadCall).mockResolvedValueOnce({ call_id: 'call-1', status: 'queued' })
    vi.mocked(callsApi.deleteCall).mockResolvedValueOnce(undefined)
    const { container } = render(<SessionCallList />)
    const input = getHiddenFileInput(container)
    selectFile(input, makeFile())
    await waitFor(() => expect(screen.getByText(/queued/i)).toBeInTheDocument())

    await userEvent.click(screen.getByRole('button', { name: /delete case_4471.wav/i }))
    await userEvent.click(screen.getByRole('button', { name: /^delete$/i }))

    await waitFor(() => expect(screen.queryByText('case_4471.wav')).not.toBeInTheDocument())
    expect(callsApi.deleteCall).toHaveBeenCalledWith('call-1')
  })
})
