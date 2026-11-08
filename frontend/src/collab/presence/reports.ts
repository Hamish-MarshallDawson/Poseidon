// Whether the session holds a saved briefing that covers this ship. The docs agent (session documents) replaces this
// body with a lookup in its documents store; until then no ship shows "report generated".
export const useHasReport = (_mmsi: number): boolean => false
