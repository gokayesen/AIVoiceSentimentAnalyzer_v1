import './DualSignalPanel.css'
import { capitalize } from '../utils/capitalize'

interface DualSignalPanelProps {
  textSentiment: string | null
  textConfidence: number | null
  toneEmotion: string | null
  toneConfidence: number | null
}

function formatHalf(value: string | null, confidence: number | null): string {
  if (value === null || confidence === null) return 'Not available'
  return `${capitalize(value)} · ${confidence.toFixed(2)}`
}

// Story 2.5 (Task 5; AC6, FR-11, AD-10): the canonical rendering of a
// disagreement — two fixed-labeled halves, each with its own value +
// confidence, never collapsed into one blended number under any state.
export function DualSignalPanel({ textSentiment, textConfidence, toneEmotion, toneConfidence }: DualSignalPanelProps) {
  return (
    <div className="dual-signal-panel">
      <div className="dual-signal-panel__half">
        <div className="dual-signal-panel__label">Text signal</div>
        <div className="dual-signal-panel__value">{formatHalf(textSentiment, textConfidence)}</div>
      </div>
      <div className="dual-signal-panel__half">
        <div className="dual-signal-panel__label">Tone signal</div>
        <div className="dual-signal-panel__value">{formatHalf(toneEmotion, toneConfidence)}</div>
      </div>
    </div>
  )
}
