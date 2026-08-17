// Story 2.5 (Task 2): client-side reimplementation of AD-11's time-range
// overlap relationship between TranscriptTurn and TimelineSegment — the real
// overlap-matching logic lives only in ml-service's fusion/overlap.py, never
// exposed via any API (confirmed, Story 2.4's own Dev Notes), so this story
// owns computing it here from data /timeline and /transcript already return.
export function overlaps(
  a: { start_time: number; end_time: number },
  b: { start_time: number; end_time: number },
): boolean {
  return a.start_time < b.end_time && a.end_time > b.start_time
}

interface FlaggableSegment {
  start_time: number
  end_time: number
  disagreement_flag: boolean
  low_confidence_flag: boolean
}

// A turn can overlap more than one segment (AD-11's many-to-many
// relationship). This priority rule — the first flagged overlapping
// segment, else the first overlapping segment at all — is a deliberate,
// documented interpretation this story owns making (mirrors Story 2.4's own
// Segments Flagged link-target decision), not an oversight: no design
// pattern exists for rendering two simultaneous flagged states on one turn.
export function findOverlappingSegment<T extends FlaggableSegment>(
  turn: { start_time: number; end_time: number },
  segments: T[],
): T | undefined {
  const overlapping = segments.filter((segment) => overlaps(turn, segment))
  const flagged = overlapping.find((segment) => segment.disagreement_flag || segment.low_confidence_flag)
  return flagged ?? overlapping[0]
}
