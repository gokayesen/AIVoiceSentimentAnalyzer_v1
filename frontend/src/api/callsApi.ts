// Story 2.2 (AD-7): the single module that owns web-api's base URL and every
// fetch call — no other component may construct a URL or call fetch directly.
//
// Base URL rationale: the browser executing this code always runs on the
// host machine (dev server or the Docker Compose stack), never inside a
// container's network namespace, so `web-api` is reachable at the host's
// localhost:8000 in every scenario this project supports. See the story's
// Dev Notes "Frontend↔backend base URL" for the full reasoning.
const API_BASE_URL = import.meta.env.VITE_API_BASE_URL ?? 'http://localhost:8000'

export interface ApiErrorBody {
  error_code: string
  message: string
  next_step: string
}

// web-api's UploadValidationError handler (errors.py) always returns this
// exact three-field JSON shape on a non-2xx response — this is a direct
// pass-through, not a guess.
export class ApiError extends Error {
  error_code: string
  next_step: string

  constructor(body: ApiErrorBody) {
    super(body.message)
    this.name = 'ApiError'
    this.error_code = body.error_code
    this.next_step = body.next_step
  }
}

export interface UploadCallResponse {
  call_id: string
  status: string
}

export interface CallStatusResponse {
  call_id: string
  status: string
  filename: string
  duration_seconds: number
  completed_at?: string | null
  no_speech_detected?: boolean
  overall_sentiment?: string
  overall_emotion?: string
  overall_confidence?: number
  single_modality_flag?: boolean
  secondary_signal_emotion?: string | null
  secondary_signal_confidence?: number | null
  // Story 3.4 (AC4): present once `status === 'complete'`, same whole-Call
  // fact TranscriptResponse's own field below carries — the Session Call
  // List only ever polls this endpoint, never `/transcript`.
  speaker_attribution_unavailable?: boolean
}

export interface TimelineSegmentResponse {
  segment_id: string
  start_time: number
  end_time: number
  fused_sentiment: string
  fused_emotion: string
  fused_confidence: number
  disagreement_flag: boolean
  low_confidence_flag: boolean
  flag_reason: string | null
  // Story 2.5 (Task 7): the Dual-signal panel's "Tone signal" half.
  acoustic_emotion: string | null
  acoustic_confidence: number | null
  // Story 2.5 (Task 7): per-segment acoustic evidence for the Acoustic
  // panel's selection-driven highlight mode (AC7) — same four fields
  // AcousticSummaryResponse already exposes as a call-level average, here
  // scoped to one segment.
  pitch_mean_hz: number | null
  energy_rms_mean: number | null
  speaking_rate_estimate: number | null
  pause_ratio: number | null
}

export interface TimelineResponse {
  call_id: string
  status: string
  segments: TimelineSegmentResponse[]
}

export interface TranscriptTurnResponse {
  turn_id: string
  turn_index: number
  start_time: number
  end_time: number
  text: string
  text_sentiment: string | null
  text_emotion: string | null
  text_confidence: number | null
  // Story 2.5 (Task 7; AC8): frontend-only, forward-compatible fields — no
  // backend column exists yet (Epic 3, still `backlog`, owns populating
  // these). Optional so nothing existing has to supply them; see the
  // story's Dev Notes "Speaker-attribution data gap."
  speaker_label?: string | null
  speaker_uncertain?: boolean
}

export interface TranscriptResponse {
  call_id: string
  status: string
  // Story 3.3/3.4: the whole-Call "attribution unavailable" fact — always
  // present on a `complete` Call's transcript response, never optional.
  speaker_attribution_unavailable: boolean
  turns: TranscriptTurnResponse[]
}

export interface AcousticSummaryResponse {
  call_id: string
  status: string
  segment_count: number
  pitch_mean_hz: number | null
  energy_rms_mean: number | null
  speaking_rate_estimate: number | null
  pause_ratio: number | null
}

async function throwApiError(response: Response): Promise<never> {
  const body = (await response.json()) as ApiErrorBody
  throw new ApiError(body)
}

export async function uploadCall(file: File): Promise<UploadCallResponse> {
  const formData = new FormData()
  formData.append('file', file)

  const response = await fetch(`${API_BASE_URL}/calls`, {
    method: 'POST',
    body: formData,
  })

  if (!response.ok) {
    await throwApiError(response)
  }

  return (await response.json()) as UploadCallResponse
}

export async function getCallStatus(callId: string): Promise<CallStatusResponse> {
  const response = await fetch(`${API_BASE_URL}/calls/${callId}`)

  if (!response.ok) {
    await throwApiError(response)
  }

  return (await response.json()) as CallStatusResponse
}

// Story 2.4 (Task 5): the Emotional Timeline, full transcript, and
// call-level acoustic summary the Analysis Dashboard needs. `getTimeline`
// consumes Story 1.7/1.9's already-built `/timeline` endpoint (this is its
// first frontend consumer); `getTranscript`/`getAcousticSummary` consume
// the two new endpoints Story 2.4 added to web-api.
export async function getTimeline(callId: string): Promise<TimelineResponse> {
  const response = await fetch(`${API_BASE_URL}/calls/${callId}/timeline`)

  if (!response.ok) {
    await throwApiError(response)
  }

  return (await response.json()) as TimelineResponse
}

export async function getTranscript(callId: string): Promise<TranscriptResponse> {
  const response = await fetch(`${API_BASE_URL}/calls/${callId}/transcript`)

  if (!response.ok) {
    await throwApiError(response)
  }

  return (await response.json()) as TranscriptResponse
}

export async function getAcousticSummary(callId: string): Promise<AcousticSummaryResponse> {
  const response = await fetch(`${API_BASE_URL}/calls/${callId}/acoustic-summary`)

  if (!response.ok) {
    await throwApiError(response)
  }

  return (await response.json()) as AcousticSummaryResponse
}

// web-api's DELETE /calls/{call_id} (Story 1.10) returns 204 with an empty
// body on success — never call .json() on that response, only on the error
// path (whose handler shares the same {error_code, message, next_step} shape
// every other endpoint uses).
export async function deleteCall(callId: string): Promise<void> {
  const response = await fetch(`${API_BASE_URL}/calls/${callId}`, { method: 'DELETE' })

  if (!response.ok) {
    await throwApiError(response)
  }
}
