// Story 2.2: formats a Call's duration_seconds as mm:ss (mock reference:
// "06:42"). Durations an hour or longer render as total minutes:seconds
// rather than switching to hh:mm:ss — AD-20 caps every Call at 30 minutes,
// so a triple-digit minute count is already an out-of-range value this
// helper doesn't need to special-case further.
export function formatDuration(seconds: number): string {
  const totalSeconds = Math.floor(seconds)
  const minutes = Math.floor(totalSeconds / 60)
  const remainingSeconds = totalSeconds % 60
  return `${String(minutes).padStart(2, '0')}:${String(remainingSeconds).padStart(2, '0')}`
}
