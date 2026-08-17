import './SpeakerLabel.css'

interface SpeakerLabelProps {
  label: string
  uncertain?: boolean
}

// Story 2.5 (Task 9; AC8): the `default`/`uncertain` Speaker label
// component. Wired into TranscriptPanel but — per the story's Dev Notes
// "Speaker-attribution data gap" — unreachable with real data from any
// current fetch in this codebase (no such DB column exists yet, Epic 3
// still `backlog`); this component's own test is what exercises it.
export function SpeakerLabel({ label, uncertain }: SpeakerLabelProps) {
  return (
    <span className={`speaker-label${uncertain ? ' speaker-label--uncertain' : ''}`}>{label}</span>
  )
}
