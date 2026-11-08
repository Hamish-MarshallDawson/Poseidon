// The /lab/metrics and /lab/data shapes this section reads (the Lab contract, docs/handoffs/lab.md).
// Kept local so the section builds on its own; lab/types.ts is the shared source once lab-shell lands.

export type Mode = 'live' | 'backtest'

export interface RouteRow {
  t: number; mode?: string; model_version: string; horizon_s: number; n: number
  cov80: number | null; cov95: number | null; median_err_m: number | null; baseline_median_err_m: number | null; skill: number | null
}
export interface DarkRow {
  t: number; mode?: string; target: string; model_version: string; n: number; positives: number
  mean_p: number | null; hit_rate: number | null; brier: number | null; brier_skill: number | null
}
export interface ReliabilityBin { p_mean: number; hit_rate: number; n: number }
export interface Reliability { target: string; bins: ReliabilityBin[] }
export interface Lift { target: string; top_share: number; top_hit_rate: number; all_hit_rate: number }
export interface LabMetrics { bucket: number; route: RouteRow[]; godark: DarkRow[]; reliability: Reliability[]; lift: Lift[] }

export interface OutcomeRow { t: number; mode: string; n: number; cumulative: number }
export interface SourceRow { src: string; stream: string; label: string; oldest: number | null; newest: number | null; windows: number; rows: number }
export interface TrainingRow { target: string; run_id: string; created_at: number; n_train: number | null }
export interface HoldoutRow { target: string; name: string; n: number; start: number; end: number; hash: string }
export interface LabData { outcomes: OutcomeRow[]; sources: SourceRow[]; training: TrainingRow[]; holdouts: HoldoutRow[] }
