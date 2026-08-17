import './AcousticPanel.css'
import type { AcousticSummaryResponse, TimelineSegmentResponse } from '../api/callsApi'
import { formatDuration } from '../utils/formatDuration'

interface AcousticPanelProps {
  summary: AcousticSummaryResponse
  selectedSegment?: TimelineSegmentResponse | null
}

interface AcousticMetrics {
  pitch_mean_hz: number | null
  energy_rms_mean: number | null
  speaking_rate_estimate: number | null
  pause_ratio: number | null
}

// Story 2.4 (Task 13): plain call-level aggregates only — no narrative/
// anomaly-highlighting/timestamp-anchoring text (Story 2.5's evidence
// drill-down, FR-13). speaking_rate_estimate is labeled "onsets/sec", the
// documented approximation it actually is (ml-service/app/pipeline/
// acoustic/features.py), not a precise words-per-minute figure.
//
// Story 2.5 (Task 8): when selectedSegment is present, its own four metrics
// (Task 1's per-segment fields) replace the call-level aggregate, anchored
// by the segment's own time range (AC7 — "anchored to a specific transcript
// timestamp"). When absent, the aggregate renders exactly as Story 2.4
// built it — see the story's Dev Notes "Acoustic panel: aggregate by
// default, per-segment on selection."
export function AcousticPanel({ summary, selectedSegment }: AcousticPanelProps) {
  const metrics: AcousticMetrics = selectedSegment ?? summary
  const anchor = selectedSegment
    ? `at ${formatDuration(selectedSegment.start_time)}–${formatDuration(selectedSegment.end_time)}`
    : null

  return (
    <div className="acoustic-panel">
      <div className="acoustic-panel__metric">
        <span className="acoustic-panel__label">Pitch (F0)</span>
        <span className="acoustic-panel__value">
          {metrics.pitch_mean_hz === null
            ? 'No voiced audio detected'
            : `${metrics.pitch_mean_hz.toFixed(0)} Hz`}
        </span>
      </div>
      <div className="acoustic-panel__metric">
        <span className="acoustic-panel__label">Energy</span>
        <span className="acoustic-panel__value">
          {metrics.energy_rms_mean === null ? '—' : metrics.energy_rms_mean.toFixed(3)}
        </span>
      </div>
      <div className="acoustic-panel__metric">
        <span className="acoustic-panel__label">Speaking rate</span>
        <span className="acoustic-panel__value">
          {metrics.speaking_rate_estimate === null
            ? '—'
            : `${metrics.speaking_rate_estimate.toFixed(2)} onsets/sec`}
        </span>
      </div>
      <div className="acoustic-panel__metric">
        <span className="acoustic-panel__label">Pauses</span>
        <span className="acoustic-panel__value">
          {metrics.pause_ratio === null ? '—' : `${(metrics.pause_ratio * 100).toFixed(0)}% of call`}
        </span>
      </div>
      {anchor && <p className="acoustic-panel__anchor">{anchor}</p>}
    </div>
  )
}
