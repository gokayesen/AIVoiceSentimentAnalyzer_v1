import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DualSignalPanel } from './DualSignalPanel'

describe('DualSignalPanel (Story 2.5, Task 5 — canonical FR-11 rendering)', () => {
  it('always renders both fixed-labeled halves, never collapsed to one value', () => {
    render(
      <DualSignalPanel textSentiment="neutral" textConfidence={0.66} toneEmotion="frustration" toneConfidence={0.71} />,
    )

    expect(screen.getByText('Text signal')).toBeInTheDocument()
    expect(screen.getByText('Tone signal')).toBeInTheDocument()
    expect(screen.getByText('Neutral · 0.66')).toBeInTheDocument()
    expect(screen.getByText('Frustration · 0.71')).toBeInTheDocument()
  })

  it('renders "Not available" for a null value instead of crashing', () => {
    render(<DualSignalPanel textSentiment={null} textConfidence={null} toneEmotion="frustration" toneConfidence={0.71} />)

    expect(screen.getByText('Text signal')).toBeInTheDocument()
    expect(screen.getByText('Not available')).toBeInTheDocument()
    expect(screen.getByText('Tone signal')).toBeInTheDocument()
    expect(screen.getByText('Frustration · 0.71')).toBeInTheDocument()
  })
})
