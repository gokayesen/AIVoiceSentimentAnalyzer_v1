import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { DISCLAIMER_TEXT, DisclaimerBar } from './DisclaimerBar'

describe('DisclaimerBar (Story 2.6, Task 1)', () => {
  it('renders the exact fixed disclaimer copy', () => {
    render(<DisclaimerBar />)
    expect(screen.getByText(DISCLAIMER_TEXT)).toBeInTheDocument()
  })
})
