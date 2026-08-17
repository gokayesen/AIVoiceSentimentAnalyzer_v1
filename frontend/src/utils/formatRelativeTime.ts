// Story 2.4: formats a Call's `completed_at` (ISO-8601) as "N ago" copy for
// the Analysis Dashboard's Case strip ("analyzed N ago"). `now` defaults to
// the real clock and exists only so tests can inject a fixed reference time.
export function formatRelativeTime(isoString: string, now: Date = new Date()): string {
  const elapsedSeconds = Math.floor((now.getTime() - new Date(isoString).getTime()) / 1000)

  if (elapsedSeconds < 60) {
    return 'just now'
  }
  const elapsedMinutes = Math.floor(elapsedSeconds / 60)
  if (elapsedMinutes < 60) {
    return `${elapsedMinutes} min ago`
  }
  const elapsedHours = Math.floor(elapsedMinutes / 60)
  if (elapsedHours < 24) {
    return `${elapsedHours} hr ago`
  }
  const elapsedDays = Math.floor(elapsedHours / 24)
  return elapsedDays === 1 ? '1 day ago' : `${elapsedDays} days ago`
}
