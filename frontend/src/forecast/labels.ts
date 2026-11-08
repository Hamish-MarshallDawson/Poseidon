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

// Go-dark model features (backend/dvm/predict/features.py) in plain words, for the reasons behind a score.
const FEATURE_LABEL: Record<string, string> = {
  sog_kn: 'speed', sog_mean: 'average speed', sog_std: 'speed changes', sog_trend: 'slowing or speeding up',
  turn_abs_deg_per_h: 'turning', heading_cog_diff_deg: 'heading off course', straightness: 'straight course',
  hour_sin: 'time of day', hour_cos: 'time of day', age_s: 'time since last report', rate_per_min: 'report rate',
  nav_status: 'navigation status', anchored: 'at anchor', draught_m: 'draught', length_m: 'size', ship_type: 'ship type',
  is_class_a: 'AIS class', lat: 'area', lon: 'area', disp_kn: 'distance made good',
}
const featureLabel = (k: string) => FEATURE_LABEL[k] ?? k.replace(/_/g, ' ')

/** The features that raised this ship's score most (top SHAP contributions above zero), as up to `n` plain words. */
export function raisedBy(contrib: Record<string, number> | undefined, n = 3): string[] {
  const out: string[] = []
  for (const [k] of Object.entries(contrib ?? {}).filter(([, v]) => v > 0).sort((a, b) => b[1] - a[1])) {
    const l = featureLabel(k)
    if (!out.includes(l)) out.push(l)
    if (out.length === n) break
  }
  return out
}
