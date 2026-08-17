// Shared by CallRow (Story 2.2) and AnalysisDashboard (Story 2.4) — both
// render raw sentiment/emotion label strings from the API and need the
// identical capitalization, lifted here rather than duplicated.
export function capitalize(value: string): string {
  return value.charAt(0).toUpperCase() + value.slice(1)
}
