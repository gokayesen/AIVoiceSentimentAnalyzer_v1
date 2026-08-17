import { describe, expect, it } from 'vitest'
import { formatDuration } from './formatDuration'

describe('formatDuration', () => {
  it('formats whole seconds under a minute as 00:ss', () => {
    expect(formatDuration(0)).toBe('00:00')
    expect(formatDuration(42)).toBe('00:42')
  })

  it('formats minutes and seconds as mm:ss', () => {
    expect(formatDuration(402)).toBe('06:42')
  })

  it('zero-pads both minutes and seconds', () => {
    expect(formatDuration(65)).toBe('01:05')
  })

  it('truncates fractional seconds down to the whole second', () => {
    expect(formatDuration(402.9)).toBe('06:42')
  })

  it('formats durations an hour or longer as total minutes, not hh:mm:ss', () => {
    expect(formatDuration(3661)).toBe('61:01')
  })
})
