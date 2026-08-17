import { describe, expect, it } from 'vitest'
import { findOverlappingSegment, overlaps } from './timeOverlap'

describe('overlaps', () => {
  it('returns false when intervals do not overlap at all', () => {
    expect(overlaps({ start_time: 0, end_time: 1 }, { start_time: 2, end_time: 3 })).toBe(false)
    expect(overlaps({ start_time: 2, end_time: 3 }, { start_time: 0, end_time: 1 })).toBe(false)
  })

  it('returns true for a partial overlap in either direction', () => {
    expect(overlaps({ start_time: 0, end_time: 2 }, { start_time: 1, end_time: 3 })).toBe(true)
    expect(overlaps({ start_time: 1, end_time: 3 }, { start_time: 0, end_time: 2 })).toBe(true)
  })

  it('returns true when one interval fully contains another', () => {
    expect(overlaps({ start_time: 0, end_time: 10 }, { start_time: 2, end_time: 4 })).toBe(true)
    expect(overlaps({ start_time: 2, end_time: 4 }, { start_time: 0, end_time: 10 })).toBe(true)
  })

  it('returns false when intervals only touch at a boundary (half-open, no double-count)', () => {
    expect(overlaps({ start_time: 0, end_time: 2 }, { start_time: 2, end_time: 4 })).toBe(false)
    expect(overlaps({ start_time: 2, end_time: 4 }, { start_time: 0, end_time: 2 })).toBe(false)
  })
})

interface TestSegment {
  segment_id: string
  start_time: number
  end_time: number
  disagreement_flag: boolean
  low_confidence_flag: boolean
}

function seg(overrides: Partial<TestSegment> = {}): TestSegment {
  return {
    segment_id: 'seg',
    start_time: 0,
    end_time: 2,
    disagreement_flag: false,
    low_confidence_flag: false,
    ...overrides,
  }
}

describe('findOverlappingSegment', () => {
  const turn = { start_time: 0, end_time: 2 }

  it('returns undefined when there are no candidate segments', () => {
    expect(findOverlappingSegment(turn, [])).toBeUndefined()
  })

  it('returns undefined when no segment overlaps the turn', () => {
    expect(findOverlappingSegment(turn, [seg({ start_time: 5, end_time: 6 })])).toBeUndefined()
  })

  it('returns the single overlapping segment when only one exists', () => {
    const only = seg({ segment_id: 'only', start_time: 0, end_time: 2 })
    expect(findOverlappingSegment(turn, [only])).toBe(only)
  })

  it('prioritizes a flagged (disagreement) overlapping segment over an unflagged one', () => {
    const clean = seg({ segment_id: 'clean', start_time: 0, end_time: 1 })
    const disagreement = seg({ segment_id: 'disagreement', start_time: 1, end_time: 2, disagreement_flag: true })
    expect(findOverlappingSegment(turn, [clean, disagreement])).toBe(disagreement)
  })

  it('prioritizes a flagged (low-confidence) overlapping segment over an unflagged one', () => {
    const clean = seg({ segment_id: 'clean', start_time: 0, end_time: 1 })
    const lowConf = seg({ segment_id: 'lowconf', start_time: 1, end_time: 2, low_confidence_flag: true })
    expect(findOverlappingSegment(turn, [clean, lowConf])).toBe(lowConf)
  })

  it('falls back to the first overlapping segment when none are flagged', () => {
    const first = seg({ segment_id: 'first', start_time: 0, end_time: 1 })
    const second = seg({ segment_id: 'second', start_time: 1, end_time: 2 })
    expect(findOverlappingSegment(turn, [first, second])).toBe(first)
  })
})
