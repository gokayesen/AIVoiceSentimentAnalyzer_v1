import { afterEach, describe, expect, it, vi } from 'vitest'
import {
  ApiError,
  deleteCall,
  getAcousticSummary,
  getCallStatus,
  getTimeline,
  getTranscript,
  uploadCall,
} from './callsApi'

function mockFetchOnce(status: number, body: unknown) {
  vi.stubGlobal(
    'fetch',
    vi.fn().mockResolvedValue({
      ok: status >= 200 && status < 300,
      status,
      json: () => Promise.resolve(body),
    }),
  )
}

afterEach(() => {
  vi.unstubAllGlobals()
})

describe('uploadCall', () => {
  it('POSTs the file as multipart form data to /calls and resolves the call_id/status', async () => {
    mockFetchOnce(201, { call_id: 'abc-123', status: 'queued' })
    const file = new File(['audio bytes'], 'call.wav', { type: 'audio/wav' })

    const result = await uploadCall(file)

    expect(result).toEqual({ call_id: 'abc-123', status: 'queued' })
    const [url, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toMatch(/\/calls$/)
    expect(init.method).toBe('POST')
    expect(init.body).toBeInstanceOf(FormData)
    expect((init.body as FormData).get('file')).toBe(file)
  })

  it('throws an ApiError with error_code/message/next_step on a validation rejection', async () => {
    mockFetchOnce(422, {
      error_code: 'UNSUPPORTED_FORMAT',
      message: 'Unsupported audio format: .ogg. Accepted formats are WAV, MP3, and M4A.',
      next_step: 'Re-export the recording as WAV, MP3, or M4A and upload again.',
    })
    const file = new File(['x'], 'call.ogg', { type: 'audio/ogg' })

    await expect(uploadCall(file)).rejects.toThrow(ApiError)
    try {
      await uploadCall(file)
      expect.unreachable()
    } catch (err) {
      const apiErr = err as ApiError
      expect(apiErr.error_code).toBe('UNSUPPORTED_FORMAT')
      expect(apiErr.next_step).toBe('Re-export the recording as WAV, MP3, or M4A and upload again.')
      expect(apiErr.message).toContain('Unsupported audio format')
    }
  })
})

describe('getCallStatus', () => {
  it('returns the full result fields when the call is complete', async () => {
    mockFetchOnce(200, {
      call_id: 'abc-123',
      status: 'complete',
      filename: 'call.wav',
      duration_seconds: 402,
      overall_sentiment: 'negative',
      overall_emotion: 'frustration',
      overall_confidence: 0.84,
    })

    const result = await getCallStatus('abc-123')

    expect(result.status).toBe('complete')
    expect(result.overall_sentiment).toBe('negative')
    expect(result.overall_emotion).toBe('frustration')
    expect(result.overall_confidence).toBe(0.84)
    const [url] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toMatch(/\/calls\/abc-123$/)
  })

  it('omits result fields for a non-complete status', async () => {
    mockFetchOnce(200, {
      call_id: 'abc-123',
      status: 'processing',
      filename: 'call.wav',
      duration_seconds: 402,
    })

    const result = await getCallStatus('abc-123')

    expect(result.status).toBe('processing')
    expect(result.overall_sentiment).toBeUndefined()
  })

  it('throws an ApiError on a 404', async () => {
    mockFetchOnce(404, {
      error_code: 'CALL_NOT_FOUND',
      message: 'No Call found with id abc-123.',
      next_step: 'Verify the Call id and try again.',
    })

    await expect(getCallStatus('abc-123')).rejects.toThrow(ApiError)
  })
})

describe('deleteCall', () => {
  it('DELETEs /calls/{call_id} and resolves without reading a body on a 204', async () => {
    vi.stubGlobal(
      'fetch',
      vi.fn().mockResolvedValue({
        ok: true,
        status: 204,
        json: () => Promise.reject(new Error('deleteCall must not call .json() on a 204 success')),
      }),
    )

    await expect(deleteCall('abc-123')).resolves.toBeUndefined()
    const [url, init] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toMatch(/\/calls\/abc-123$/)
    expect(init.method).toBe('DELETE')
  })

  it('throws an ApiError with error_code/message/next_step on a failed delete', async () => {
    mockFetchOnce(409, {
      error_code: 'CALL_DELETION_IN_PROGRESS',
      message: "Call abc-123 is still being processed and could not be safely deleted within the wait window.",
      next_step: 'Retry the delete request shortly, once processing has finished.',
    })

    await expect(deleteCall('abc-123')).rejects.toThrow(ApiError)
    try {
      await deleteCall('abc-123')
      expect.unreachable()
    } catch (err) {
      const apiErr = err as ApiError
      expect(apiErr.error_code).toBe('CALL_DELETION_IN_PROGRESS')
      expect(apiErr.next_step).toBe('Retry the delete request shortly, once processing has finished.')
    }
  })
})

describe('getTimeline', () => {
  it('returns the parsed segments on success', async () => {
    mockFetchOnce(200, {
      call_id: 'abc-123',
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
          acoustic_emotion: 'frustration',
          acoustic_confidence: 0.71,
          pitch_mean_hz: 210.5,
          energy_rms_mean: 0.061,
          speaking_rate_estimate: 4.1,
          pause_ratio: 0.15,
        },
      ],
    })

    const result = await getTimeline('abc-123')

    expect(result.segments).toHaveLength(1)
    expect(result.segments[0].fused_sentiment).toBe('negative')
    // Story 2.5 (Task 7): the per-segment acoustic + tone-signal fields
    // Task 1 added to the backend response parse through unchanged.
    expect(result.segments[0].acoustic_emotion).toBe('frustration')
    expect(result.segments[0].acoustic_confidence).toBe(0.71)
    expect(result.segments[0].pitch_mean_hz).toBe(210.5)
    expect(result.segments[0].energy_rms_mean).toBe(0.061)
    expect(result.segments[0].speaking_rate_estimate).toBe(4.1)
    expect(result.segments[0].pause_ratio).toBe(0.15)
    const [url] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toMatch(/\/calls\/abc-123\/timeline$/)
  })

  it('throws an ApiError on a 409', async () => {
    mockFetchOnce(409, {
      error_code: 'CALL_NOT_COMPLETE',
      message: "Call abc-123 is currently 'processing'.",
      next_step: 'Poll the Call status and retry once complete.',
    })

    await expect(getTimeline('abc-123')).rejects.toThrow(ApiError)
  })
})

describe('getTranscript', () => {
  it('returns the parsed turns on success', async () => {
    mockFetchOnce(200, {
      call_id: 'abc-123',
      status: 'complete',
      turns: [
        {
          turn_id: 'turn-1',
          turn_index: 0,
          start_time: 0,
          end_time: 2,
          text: 'hello there',
          text_sentiment: 'neutral',
          text_emotion: 'neutral',
          text_confidence: 0.7,
        },
      ],
    })

    const result = await getTranscript('abc-123')

    expect(result.turns).toHaveLength(1)
    expect(result.turns[0].text).toBe('hello there')
    const [url] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toMatch(/\/calls\/abc-123\/transcript$/)
  })

  it('throws an ApiError on a 404', async () => {
    mockFetchOnce(404, {
      error_code: 'CALL_NOT_FOUND',
      message: 'No Call found with id abc-123.',
      next_step: 'Verify the Call id and try again.',
    })

    await expect(getTranscript('abc-123')).rejects.toThrow(ApiError)
  })
})

describe('getAcousticSummary', () => {
  it('returns the parsed summary on success', async () => {
    mockFetchOnce(200, {
      call_id: 'abc-123',
      status: 'complete',
      segment_count: 2,
      pitch_mean_hz: 130.0,
      energy_rms_mean: 0.05,
      speaking_rate_estimate: 2.5,
      pause_ratio: 0.2,
    })

    const result = await getAcousticSummary('abc-123')

    expect(result.segment_count).toBe(2)
    expect(result.pitch_mean_hz).toBe(130.0)
    const [url] = (fetch as ReturnType<typeof vi.fn>).mock.calls[0]
    expect(url).toMatch(/\/calls\/abc-123\/acoustic-summary$/)
  })

  it('throws an ApiError on a 404', async () => {
    mockFetchOnce(404, {
      error_code: 'CALL_NOT_FOUND',
      message: 'No Call found with id abc-123.',
      next_step: 'Verify the Call id and try again.',
    })

    await expect(getAcousticSummary('abc-123')).rejects.toThrow(ApiError)
  })
})
