import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { SpeakerLabel } from './SpeakerLabel'

describe('SpeakerLabel (Story 2.5, Task 9)', () => {
  it('renders the default variant without the uncertain styling', () => {
    render(<SpeakerLabel label="Agent" />)
    const el = screen.getByText('Agent')
    expect(el).not.toHaveClass('speaker-label--uncertain')
  })

  it('renders the uncertain variant with a dotted underline, distinct from the transcript-turn dashed border', () => {
    render(<SpeakerLabel label="Agent" uncertain />)
    const el = screen.getByText('Agent')
    expect(el).toHaveClass('speaker-label--uncertain')
  })
})
