import type { KeyboardEvent as ReactKeyboardEvent } from 'react'
import { useEffect } from 'react'
import './ConfirmDialog.css'

interface ConfirmDialogProps {
  filename: string
  onCancel: () => void
  onConfirm: () => void
}

// Story 2.3: the delete-Call confirmation — the one elevated/modal surface in
// the product (DESIGN.md "Elevation & Depth"). Standalone and takes no
// dependency on where it's mounted from — Story 2.4's Analysis Dashboard can
// import and render it from anywhere (AC2's known spec gap — see the story's
// Dev Notes). Note (code review, 2026-08-15): the copy itself (title/body/
// warning/button label) is still hardcoded for the delete use case, not
// parameterized — reusing this for a *different* confirmation would need
// `title`/`body`/`confirmLabel` props added first, not just a different
// mount point.
export function ConfirmDialog({ filename, onCancel, onConfirm }: ConfirmDialogProps) {
  useEffect(() => {
    function handleKeyDown(event: KeyboardEvent) {
      if (event.key === 'Escape') {
        onCancel()
      }
    }
    document.addEventListener('keydown', handleKeyDown)
    return () => document.removeEventListener('keydown', handleKeyDown)
  }, [onCancel])

  // Story 2.7 (Task 3; AC8 — deferred-work.md, Story 2.3 review): a Tab-key
  // focus trap between the dialog's only two focusable elements (Cancel,
  // Delete) — `aria-modal="true"` alone doesn't stop the browser's native
  // tab order from escaping onto background content.
  // Code review (2026-08-16): always intercept Tab/Shift+Tab rather than
  // only reacting when activeElement is exactly Cancel or Delete — with
  // only two focusable elements, forward and backward traversal both
  // reduce to "focus the other one," so this also correctly recovers
  // focus if it ever lands somewhere else while the dialog is open (e.g. a
  // mouse click that doesn't move focus, per-browser default).
  function handleTabTrap(event: ReactKeyboardEvent<HTMLDivElement>) {
    if (event.key !== 'Tab') return
    event.preventDefault()
    const cancelButton = event.currentTarget.querySelector('.confirm-dialog__cancel') as HTMLElement | null
    const deleteButton = event.currentTarget.querySelector('.confirm-dialog__delete') as HTMLElement | null
    if (document.activeElement === cancelButton) {
      deleteButton?.focus()
    } else {
      cancelButton?.focus()
    }
  }

  return (
    <div className="confirm-dialog-overlay" onClick={onCancel}>
      <div
        className="confirm-dialog"
        role="alertdialog"
        aria-modal="true"
        aria-labelledby="confirm-dialog-title"
        aria-describedby="confirm-dialog-body confirm-dialog-warning"
        onClick={(event) => event.stopPropagation()}
        onKeyDown={handleTabTrap}
      >
        <h3 className="confirm-dialog__title" id="confirm-dialog-title">
          Delete <span className="confirm-dialog__filename">{filename}</span>?
        </h3>
        <p className="confirm-dialog__body" id="confirm-dialog-body">
          This removes the Call and its Analysis Result from this session.
        </p>
        <p className="confirm-dialog__warning" id="confirm-dialog-warning">
          This action is immediate and unrecoverable — nothing is retained beyond the current
          session.
        </p>
        <div className="confirm-dialog__actions">
          {/* eslint-disable-next-line jsx-a11y/no-autofocus -- AC3: Cancel is default-focused */}
          <button type="button" className="confirm-dialog__cancel" onClick={onCancel} autoFocus>
            Cancel
          </button>
          <button type="button" className="confirm-dialog__delete" onClick={onConfirm}>
            Delete
          </button>
        </div>
      </div>
    </div>
  )
}
