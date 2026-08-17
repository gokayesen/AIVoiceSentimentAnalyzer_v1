import { describe, expect, it, vi } from 'vitest'
import { fireEvent, render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { ConfirmDialog } from './ConfirmDialog'

describe('ConfirmDialog', () => {
  it('renders the filename and the confirm-dialog copy', () => {
    render(<ConfirmDialog filename="case_4511.wav" onCancel={vi.fn()} onConfirm={vi.fn()} />)

    expect(screen.getByRole('alertdialog')).toBeInTheDocument()
    expect(screen.getByText('case_4511.wav')).toBeInTheDocument()
    expect(
      screen.getByText(/this removes the call and its analysis result from this session/i),
    ).toBeInTheDocument()
    expect(
      screen.getByText(/immediate and unrecoverable/i),
    ).toBeInTheDocument()
  })

  it('Cancel is default-focused', () => {
    render(<ConfirmDialog filename="case_4511.wav" onCancel={vi.fn()} onConfirm={vi.fn()} />)

    expect(screen.getByRole('button', { name: /cancel/i })).toHaveFocus()
  })

  it('clicking Cancel calls onCancel', async () => {
    const onCancel = vi.fn()
    render(<ConfirmDialog filename="case_4511.wav" onCancel={onCancel} onConfirm={vi.fn()} />)

    await userEvent.click(screen.getByRole('button', { name: /cancel/i }))
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('clicking Delete calls onConfirm', async () => {
    const onConfirm = vi.fn()
    render(<ConfirmDialog filename="case_4511.wav" onCancel={vi.fn()} onConfirm={onConfirm} />)

    await userEvent.click(screen.getByRole('button', { name: /^delete$/i }))
    expect(onConfirm).toHaveBeenCalledTimes(1)
  })

  it('clicking the overlay calls onCancel', async () => {
    const onCancel = vi.fn()
    const { container } = render(
      <ConfirmDialog filename="case_4511.wav" onCancel={onCancel} onConfirm={vi.fn()} />,
    )

    const overlay = container.firstElementChild as HTMLElement
    await userEvent.click(overlay)
    expect(onCancel).toHaveBeenCalledTimes(1)
  })

  it('clicking inside the dialog does not call onCancel', async () => {
    const onCancel = vi.fn()
    render(<ConfirmDialog filename="case_4511.wav" onCancel={onCancel} onConfirm={vi.fn()} />)

    await userEvent.click(screen.getByRole('alertdialog'))
    expect(onCancel).not.toHaveBeenCalled()
  })

  it('pressing Escape calls onCancel', () => {
    const onCancel = vi.fn()
    render(<ConfirmDialog filename="case_4511.wav" onCancel={onCancel} onConfirm={vi.fn()} />)

    fireEvent.keyDown(document, { key: 'Escape' })
    expect(onCancel).toHaveBeenCalledTimes(1)
  })
})

// Story 2.7 (Task 3; AC8 — deferred-work.md, Story 2.3 review): aria-labelledby/
// aria-describedby association and a Tab-key focus trap between the dialog's
// only two focusable elements.
describe('ConfirmDialog — focus trap and ARIA association (Story 2.7, Task 3)', () => {
  it('aria-labelledby/aria-describedby resolve to elements containing the title/body/warning text', () => {
    render(<ConfirmDialog filename="case_4511.wav" onCancel={vi.fn()} onConfirm={vi.fn()} />)

    const dialog = screen.getByRole('alertdialog')
    const labelledbyId = dialog.getAttribute('aria-labelledby')
    const describedbyIds = dialog.getAttribute('aria-describedby')?.split(' ') ?? []

    expect(labelledbyId).toBeTruthy()
    expect(document.getElementById(labelledbyId!)?.textContent).toContain('case_4511.wav')

    expect(describedbyIds.length).toBe(2)
    const describedText = describedbyIds.map((id) => document.getElementById(id)?.textContent).join(' ')
    expect(describedText).toMatch(/this removes the call and its analysis result from this session/i)
    expect(describedText).toMatch(/immediate and unrecoverable/i)
  })

  it('Tab while Delete has focus wraps focus to Cancel', () => {
    render(<ConfirmDialog filename="case_4511.wav" onCancel={vi.fn()} onConfirm={vi.fn()} />)

    screen.getByRole('button', { name: /^delete$/i }).focus()
    fireEvent.keyDown(document.activeElement!, { key: 'Tab', shiftKey: false })

    expect(screen.getByRole('button', { name: /cancel/i })).toHaveFocus()
  })

  it('Shift+Tab while Cancel has focus wraps focus to Delete', () => {
    render(<ConfirmDialog filename="case_4511.wav" onCancel={vi.fn()} onConfirm={vi.fn()} />)

    screen.getByRole('button', { name: /cancel/i }).focus()
    fireEvent.keyDown(document.activeElement!, { key: 'Tab', shiftKey: true })

    expect(screen.getByRole('button', { name: /^delete$/i })).toHaveFocus()
  })

  // Code review (2026-08-16): the original trap only engaged when
  // activeElement was exactly Cancel or Delete — if focus ever landed
  // somewhere else while the dialog was open (e.g. a browser where a mouse
  // click doesn't move focus, or focus is briefly on the dialog root
  // itself), Tab would fall through uncaught and could escape the modal.
  // The trap now always intercepts Tab/Shift+Tab and resolves to one of
  // the two buttons regardless of current focus state.
  it('Tab pressed while focus is on neither button still keeps focus trapped inside the dialog', () => {
    const { container } = render(
      <ConfirmDialog filename="case_4511.wav" onCancel={vi.fn()} onConfirm={vi.fn()} />,
    )

    // Simulate focus having landed somewhere other than Cancel/Delete (the
    // real-world trigger: a mouse click that doesn't move focus, e.g.
    // macOS Safari's default button behavior).
    ;(document.activeElement as HTMLElement | null)?.blur()
    expect(document.activeElement).not.toBe(screen.getByRole('button', { name: /cancel/i }))

    const dialog = container.querySelector('.confirm-dialog') as HTMLElement
    fireEvent.keyDown(dialog, { key: 'Tab', shiftKey: false })

    const focused = document.activeElement
    expect(
      focused === screen.getByRole('button', { name: /cancel/i }) ||
        focused === screen.getByRole('button', { name: /^delete$/i }),
    ).toBe(true)
  })
})
