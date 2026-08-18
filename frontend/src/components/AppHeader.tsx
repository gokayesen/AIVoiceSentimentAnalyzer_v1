import './AppHeader.css'

interface AppHeaderProps {
  /** Monospace queue/case path shown center. Defaults to the session root — a
   * Call-scoped Dashboard (Story 2.4) will pass its own case path here. */
  breadcrumbLabel?: string
  /** Per EXPERIENCE.md Interaction Primitives: returns the Analyst to the
   * Session Call List from anywhere in the Dashboard. No Dashboard exists
   * yet in this story, so the default is a no-op. */
  onBreadcrumbClick?: () => void
}

/**
 * The near-black chrome bar shared by every surface (DESIGN.md `app-header`
 * component). Wordmark left, breadcrumb center, analyst identity right — no
 * login/account UI (PRD §2.3, MVP has no auth).
 */
export function AppHeader({
  breadcrumbLabel,
  onBreadcrumbClick,
}: AppHeaderProps) {
  // A default parameter only covers `undefined` — guard here too, since an
  // empty/whitespace string passed explicitly (e.g. a future caller with no
  // case path yet) would otherwise render an empty, inaccessible button.
  const crumbText = breadcrumbLabel?.trim() ? breadcrumbLabel : 'queue/session'

  return (
    <header className="app-header">
      <div className="app-header__brand">VOICE SENTIMENT · CONSOLE</div>
      <button type="button" className="app-header__crumb" onClick={onBreadcrumbClick}>
        {crumbText}
      </button>
      <div className="app-header__user">
        <span className="app-header__avatar" aria-hidden="true">
          GE
        </span>
        Gokay E. · CX Analyst
      </div>
    </header>
  )
}
