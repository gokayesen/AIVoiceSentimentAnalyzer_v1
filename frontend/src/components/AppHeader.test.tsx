import { describe, expect, it } from 'vitest'
import { render, screen } from '@testing-library/react'
import { AppHeader } from './AppHeader'

describe('AppHeader', () => {
  it('renders the product wordmark', () => {
    render(<AppHeader />)
    expect(screen.getByText(/VOICE SENTIMENT/i)).toBeInTheDocument()
  })

  it('renders a focusable breadcrumb button with a queue/case path', () => {
    render(<AppHeader />)
    const crumb = screen.getByRole('button', { name: /queue\/session/i })
    expect(crumb).toBeInTheDocument()
    expect(crumb.tagName).toBe('BUTTON')
    expect(crumb).not.toBeDisabled()
  })

  it('renders the analyst identity (name + role), no login UI', () => {
    render(<AppHeader />)
    expect(screen.getByText(/Gokay E\. · CX Analyst/)).toBeInTheDocument()
  })

  it('never renders any login/account UI (AC1 — MVP has no auth)', () => {
    render(<AppHeader />)
    expect(screen.queryByText(/log ?in|sign ?in|sign ?up|log ?out/i)).not.toBeInTheDocument()
  })

  it('falls back to the default breadcrumb when passed an empty/whitespace label', () => {
    render(<AppHeader breadcrumbLabel="   " />)
    const crumb = screen.getByRole('button', { name: /queue\/session/i })
    expect(crumb).toBeInTheDocument()
    expect(crumb.textContent).not.toBe('')
  })
})
