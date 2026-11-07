import type { GapEvent } from '../types'

// All display wording for forecast and gap codes in one place (neutral; forecast report). coverage_flag names may be
// renamed by the data model: change the keys here only.
export const COVERAGE_FLAG_LABEL: Record<GapEvent['coverage_flag'], string> = {
  deliberate_candidate: 'reception normal nearby',
  coverage_gap: 'coverage hole here',
  own_stall: 'our feed paused',
  unknown: 'no ships nearby to compare',
}

export const REASON_LABEL: Record<string, string> = {
  OPEN_GAP: 'No AIS now, reception normal nearby',
  RECENT_GAP: 'Silent gap in the last 24 h',
  SPOOF_CIRCLING: 'Circling while reporting at anchor',
  SANCTIONED: 'On EU sanctions list',
  DRAUGHT_JUMP: 'Draught up',
  FLAG_MISMATCH: 'Flag does not match MMSI country',
  BLANK_DESTINATION: 'No destination',
  LOITERING: 'Loitering',
}

export const OUTCOME_LABEL = { hit: 'Went silent', miss: 'Stayed heard', censored: 'Not scored' } as const

export const BASELINE_LABEL: Record<string, string> = {
  'baseline-prior-gap': 'Went silent before',
  'baseline-tankers': 'Tankers near Russian ports',
  'baseline-cell-rate': 'Cell-hour gap rate',
}

// The model is frozen and committed about 23:00Z Saturday and scored prospectively on Sunday (evaluation plan).
export const FREEZE_TS = Date.UTC(2026, 10, 7, 23)
export const HORIZON_MS = 6 * 3_600_000
export const RESOLVE_LAG_MS = 30 * 60_000          // outcomes exist only after made_at + 6 h 30 min

export const pct = (p: number) => `${Math.round(p * 100)} %`
