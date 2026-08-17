import { describe, expect, it } from 'vitest'
import { formatRelativeTime } from './formatRelativeTime'

const NOW = new Date('2026-08-15T00:10:00.000Z')

function isoSecondsAgo(seconds: number): string {
  return new Date(NOW.getTime() - seconds * 1000).toISOString()
}

describe('formatRelativeTime', () => {
  it('renders "just now" under 60 seconds', () => {
    expect(formatRelativeTime(isoSecondsAgo(0), NOW)).toBe('just now')
    expect(formatRelativeTime(isoSecondsAgo(59), NOW)).toBe('just now')
  })

  it('renders minutes at the 60s boundary and beyond', () => {
    expect(formatRelativeTime(isoSecondsAgo(60), NOW)).toBe('1 min ago')
    expect(formatRelativeTime(isoSecondsAgo(120), NOW)).toBe('2 min ago')
    expect(formatRelativeTime(isoSecondsAgo(59 * 60), NOW)).toBe('59 min ago')
  })

  it('renders hours at the 60min boundary and beyond', () => {
    expect(formatRelativeTime(isoSecondsAgo(60 * 60), NOW)).toBe('1 hr ago')
    expect(formatRelativeTime(isoSecondsAgo(3 * 60 * 60), NOW)).toBe('3 hr ago')
    expect(formatRelativeTime(isoSecondsAgo(23 * 60 * 60), NOW)).toBe('23 hr ago')
  })

  it('renders days at the 24hr boundary and beyond, with a singular form for exactly 1 day', () => {
    expect(formatRelativeTime(isoSecondsAgo(24 * 60 * 60), NOW)).toBe('1 day ago')
    expect(formatRelativeTime(isoSecondsAgo(3 * 24 * 60 * 60), NOW)).toBe('3 days ago')
  })
})
