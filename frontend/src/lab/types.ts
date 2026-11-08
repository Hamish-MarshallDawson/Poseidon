// The Model Lab contract (docs/handoffs/lab.md): GET /lab/* responses. Times are epoch ms; horizons are seconds,
// used as string keys ("10800") in the per-horizon maps. Fields older runs lack are null.

export type Target = 'route' | 'godark' | 'fishing' | 'godark_gfw' | (string & {})
export type Proposer = 'human' | 'default' | 'gemini'
export type RunStatus = 'champion' | 'retired' | 'candidate' | 'rejected'
export type Source = 'pc-aiden' | 'desktop-hamish' | 'server' | (string & {})

export interface Holdout {
  target: string
  name: string
  start: number | null
  end: number | null
  hash: string | null
  n: number | null
  [k: string]: unknown
}

export interface HorizonSkill {
  n: number
  stat: number | null
  baseline_stat: number | null
  skill: number | null
  skill_lo: number | null
  skill_hi: number | null
  win_rate: number | null
}

export interface CalibrationCheck {
  name: string
  horizon_s: number | null
  value: number | null
  nominal: number | null
  tol?: number | null
  ok?: boolean | null
}

export interface HorizonDecision {
  n?: number
  cand: number | null
  ref: number | null
  diff: number | null
  lo: number | null
  hi: number | null
  win: boolean | null
}

export interface Decision {
  promote: boolean | null
  against: string | null
  alpha: number | null
  n_comparisons: number | null
  horizons: Record<string, HorizonDecision> | null
  calibration: CalibrationCheck[] | null
  reasons: string[] | null
  /** 'human' for a promotion (or hold) made by hand, 'rule' when the promotion rule decided. */
  by?: string | null
  strata_worse?: { stratum: string; value: string; horizon_s: number; n: number; cand: number; ref: number }[] | null
}

export interface RunMetrics {
  state: string | null
  holdout: Holdout | null
  split: { n_train: number | null; n_test: number | null; embargo_s: number | null; [k: string]: unknown } | null
  statistic: string | null
  loss_name: string | null
  loss_unit: string | null
  summary: Record<string, Record<string, unknown>> | null
  skill: Record<string, HorizonSkill> | null
  calibration: CalibrationCheck[] | null
  strata?: unknown
  strata_baseline?: unknown
  cv: unknown
  decision: Decision | null
  seconds: number | null
  [k: string]: unknown
}

export interface Run {
  run_id: string
  target: Target
  model: string | null
  config: Record<string, unknown> | null
  data_hash: string | null
  train_from: number | null
  train_to: number | null
  artifact: string | null
  proposer: Proposer | null
  parent_run: string | null
  status: RunStatus
  created_at: number
  loop_id: string | null
  round: number | null
  git_sha: string | null
  source: Source | null
  metrics: RunMetrics | null
}

export interface RuleCheck { check: string; passed: boolean | null; detail: string | null }

export interface RunDetail extends Run {
  parent: Run | null
  config_diff: { key: string; parent: unknown; value: unknown }[]
  rationale: string | null
  rule: RuleCheck[]
  confirm: { run_id: string; passed: boolean } | null
  /** One plain sentence for the decision, e.g. "promoted by hand over route-dma14-v3; no paired test was run". */
  decision_summary?: string | null
}

export type ProposalOutcome = 'champion' | 'candidate' | 'rejected' | 'invalid' | 'duplicate'

export interface Proposal {
  id: string
  target: Target
  loop_id: string | null
  round: number | null
  proposer: Proposer
  created_at: number
  proposal: Record<string, unknown> | null
  valid: boolean
  errors: string[]
  rationale: string | null
  source: Source | null
  run_id: string | null
  outcome: ProposalOutcome
}

export type EventKind = 'trained' | 'promoted' | 'rejected' | 'recalibrated' | 'deployed' | 'proposal'

export interface LabEvent {
  ts: number
  target: Target
  kind: EventKind
  run_id: string | null
  version: string | null
  label: string
  detail: Record<string, unknown>
}

export interface LiveOffline { statistic: string; horizon_s: number; skill: number | null; skill_lo: number | null; skill_hi: number | null }

export interface ModelSummary {
  target: Target
  label: string
  champion: { run_id: string | null; version: string; since: number | null; proposer: Proposer | null; source: Source | null }
  /** `statistic` names the held-out number ('log-loss skill', 'median-error skill'). */
  offline: { primary_h: number; statistic?: string | null; skill: number | null; skill_lo: number | null; skill_hi: number | null; holdout: string | null }
  live: {
    hours: number
    n: number
    /** The version graded live, and for go-dark the target graded ("dark_1h"). */
    model_version?: string
    target?: string
    /** What the live number is ('Brier skill', 'median-error skill') and at which horizon (s). */
    statistic?: string
    horizon_s?: number
    /** The held-out number on the same statistic at the same horizon; null when the run has none (then no comparison). */
    offline?: LiveOffline | null
    primary: { name: string; value: number | null; ref_label: string }
    calibration: { name: string; value: number | null; nominal: number | null; ok: boolean | null }
  } | null
  deployed: boolean
  note: string | null
}

export interface Summary {
  generated_at: number
  models: ModelSummary[]
  cycle: { state: 'manual' | 'scheduled'; last: number | null; next: number | null }
  /** `graded_outcomes_estimated`: the total is the planner's estimate past the exact-count limit (show it with ~). */
  totals: { runs: number; proposals: number; graded_outcomes: number; graded_outcomes_estimated?: boolean; graded_last_hour: number }
}

export type Mode = 'live' | 'backtest' | 'all' | (string & {})

export interface RouteMetricRow {
  t: number
  mode?: Mode
  model_version: string
  horizon_s: number
  n: number
  cov80: number | null
  cov95: number | null
  median_err_m: number | null
  baseline_median_err_m: number | null
  skill: number | null
}

export interface DarkMetricRow {
  t: number
  mode?: Mode
  target: string
  model_version: string
  n: number
  positives: number
  mean_p: number | null
  hit_rate: number | null
  brier: number | null
  brier_skill: number | null
}

export interface Metrics {
  bucket: number
  route: RouteMetricRow[]
  godark: DarkMetricRow[]
  reliability: { target: string; bins: { p_mean: number; hit_rate: number; n: number }[] }[]
  lift: { target: string; top_share: number; top_hit_rate: number; all_hit_rate: number }[]
  /** True when the row limit dropped the oldest buckets. */
  truncated?: boolean
}

export interface LabData {
  outcomes: { t: number; mode: Mode; n: number; cumulative: number }[]
  sources: { src: string; stream: string; label: string; oldest: number | null; newest: number | null; windows: number; rows: number }[]
  training: { target: Target; run_id: string; created_at: number; n_train: number | null }[]
  holdouts: { target: Target; name: string; n: number | null; start: number | null; end: number | null; hash: string | null }[]
  /** Epoch ms the running total of graded outcomes is counted from. */
  counted_from?: number | null
  /** True when the row limit dropped the oldest hourly buckets. */
  truncated?: boolean
}

/** The fixtures file: every endpoint's response, same shapes. */
export interface Fixtures {
  summary: Summary
  runs: Run[]
  run_detail: Record<string, RunDetail>
  proposals: Proposal[]
  events: LabEvent[]
  metrics: Metrics
  data: LabData
}
