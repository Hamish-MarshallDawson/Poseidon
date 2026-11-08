// Data shaping for the runs section: plain-words labels, primary skill, change against the parent, decision line.
// The record shapes follow the Model Lab contract (docs/handoffs/lab.md); only the fields used here are typed.
import { byHandLine, promotionWhy, verdict } from '../decision'

export interface SkillH { n: number; stat: number | null; baseline_stat: number | null; skill: number | null; skill_lo: number | null; skill_hi: number | null; win_rate?: number | null }
export interface CalCheck { name: string; horizon_s: number | null; value: number | null; nominal: number | null; tol?: number | null; ok?: boolean | null }
export interface DecisionH { n?: number; cand: number | null; ref: number | null; diff: number | null; lo: number | null; hi: number | null; win: boolean | null }
export interface Stratum { stratum: string; value: string; horizon_s: number; n: number; cand: number; ref: number }
export interface Decision {
  promote: boolean | null
  against: string | null
  by?: string | null
  alpha?: number | null
  n_comparisons?: number | null
  horizons?: Record<string, DecisionH> | null
  calibration?: CalCheck[] | null
  strata_worse?: Stratum[] | null
  reasons?: string[] | null
}
export interface RunMetrics {
  state?: string | null
  holdout?: { name?: string | null; start?: number | null; end?: number | null; n?: number | null; hash?: string | null } | null
  split?: { n_train?: number | null; n_test?: number | null; embargo_s?: number | null } | null
  statistic?: string | null
  loss_name?: string | null
  loss_unit?: string | null
  skill?: Record<string, SkillH> | null
  calibration?: CalCheck[] | null
  decision?: Decision | null
  seconds?: number | null
}
export type RunStatus = 'champion' | 'retired' | 'candidate' | 'rejected'
export interface RunRecord {
  run_id: string
  target: string
  model: string | null
  config: Record<string, unknown> | null
  data_hash?: string | null
  train_from: number | null
  train_to: number | null
  proposer: string | null
  parent_run: string | null
  status: RunStatus | string
  created_at: number
  source?: string | null
  metrics: RunMetrics | null
}
export interface RuleCheck { check: string; passed: boolean | null; detail?: string | null }
export interface RunDetail extends RunRecord {
  parent: RunRecord | null
  config_diff: { key: string; parent: unknown; value: unknown }[]
  rationale: string | null
  rule: RuleCheck[]
  confirm: { run_id: string; passed: boolean } | null
  decision_summary?: string | null
}
export type ProposalOutcome = 'champion' | 'candidate' | 'rejected' | 'invalid' | 'duplicate'
export interface Proposal {
  id: string
  target: string
  loop_id?: string | null
  round?: number | null
  proposer: string
  created_at: number
  proposal: Record<string, unknown> | null
  valid: boolean
  errors: string[]
  rationale: string | null
  source?: string | null
  run_id: string | null
  outcome: ProposalOutcome | string
}

const TARGET_LABEL: Record<string, string> = {
  route: 'Route',
  godark: 'Go-dark',
  godark_gfw: 'Go-dark (GFW gaps)',
  fishing: 'Fishing in protected areas',
}
export const targetLabel = (t: string) => TARGET_LABEL[t] ?? t

const PROPOSER_LABEL: Record<string, string> = { human: 'Human', default: 'Fixed list', gemini: 'Gemini' }
export const proposerLabel = (p: string | null | undefined) => (p ? PROPOSER_LABEL[p] ?? p : '—')

export const STATUS_LABEL: Record<string, string> = { champion: 'Champion', retired: 'Retired champion', candidate: 'Candidate', rejected: 'Rejected' }

const LOSS_LABEL: Record<string, string> = { log_loss: 'log loss', brier: 'Brier score', median_err_m: 'median error', err_m: 'error' }
export const lossLabel = (m: RunMetrics | null | undefined) => (m?.loss_name ? LOSS_LABEL[m.loss_name] ?? m.loss_name.replace(/_/g, ' ') : 'loss')

/** A horizon in seconds as plain words: "3 h", "7 d" (with a non-breaking space). */
export function horizonLabel(s: number | string | null | undefined): string {
  if (s == null || s === '') return 'all horizons'
  const v = Number(s)
  if (!Number.isFinite(v)) return String(s)
  if (v < 3600) return `${Math.round(v / 60)}\u00a0min`
  const h = v / 3600
  return h >= 48 && h % 24 === 0 ? `${h / 24}\u00a0d` : `${Math.round(h * 10) / 10}\u00a0h`
}

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const p2 = (n: number) => String(n).padStart(2, '0')
/** "8 Nov 07:19Z" (UTC, like the rest of the app). */
export function fmtWhen(t: number | null | undefined): string {
  if (t == null) return '—'
  const d = new Date(t)
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${p2(d.getUTCHours())}:${p2(d.getUTCMinutes())}Z`
}
/** "Dec 2021" */
export function fmtMonth(t: number | null | undefined): string {
  if (t == null) return '?'
  const d = new Date(t)
  return `${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`
}
export const fmtCount = (n: number | null | undefined) => (n == null ? '—' : n.toLocaleString('en-GB'))
/** Skill as a signed percentage: "+13 %", "−6 %". */
export const fmtPct = (x: number | null | undefined, digits = 0) =>
  x == null ? '—' : `${x >= 0 ? '+' : '−'}${Math.abs(x * 100).toFixed(digits)} %`
/** A loss value with sensible precision (metres become km). */
export function fmtStat(x: number | null | undefined, unit?: string | null): string {
  if (x == null) return '—'
  if (unit === 'm') return Math.abs(x) >= 1000 ? `${(x / 1000).toFixed(1)} km` : `${Math.round(x)} m`
  const a = Math.abs(x)
  return a >= 100 ? x.toFixed(0) : a >= 1 ? x.toFixed(2) : x.toFixed(4)
}

/** Horizons with skill numbers, shortest first. */
export function horizons(run: Pick<RunRecord, 'metrics'>): number[] {
  const keys = new Set([...Object.keys(run.metrics?.skill ?? {}), ...Object.keys(run.metrics?.decision?.horizons ?? {})])
  return [...keys].map(Number).filter(Number.isFinite).sort((a, b) => a - b)
}

/** The horizon a run is judged on: the caller's choice when the run has it, otherwise its shortest scored horizon. */
export function primaryHorizon(run: Pick<RunRecord, 'metrics'>, preferred?: number | null): number | null {
  const hs = horizons(run)
  if (preferred != null && hs.includes(preferred)) return preferred
  return hs[0] ?? null
}

export interface PrimarySkill { h: number; skill: number | null; lo: number | null; hi: number | null; n: number | null }
export function primarySkill(run: Pick<RunRecord, 'metrics'>, preferred?: number | null): PrimarySkill | null {
  const h = primaryHorizon(run, preferred)
  if (h == null) return null
  const s = run.metrics?.skill?.[String(h)]
  if (!s) return { h, skill: null, lo: null, hi: null, n: null }
  return { h, skill: s.skill, lo: s.skill_lo, hi: s.skill_hi, n: s.n }
}

const show = (v: unknown) => (v == null ? '—' : typeof v === 'object' ? JSON.stringify(v) : String(v))

/** Config keys that differ from the parent (keys in either one), in a stable order. Model first. */
export function configDiff(config: Record<string, unknown> | null, parent: Record<string, unknown> | null): { key: string; parent: unknown; value: unknown }[] {
  const a = parent ?? {}, b = config ?? {}
  const keys = [...new Set([...Object.keys(b), ...Object.keys(a)])]
  return keys
    .filter((k) => JSON.stringify(a[k]) !== JSON.stringify(b[k]))
    .sort((x, y) => (x === 'model' ? -1 : y === 'model' ? 1 : 0))
    .map((key) => ({ key, parent: a[key] ?? null, value: b[key] ?? null }))
}

/** One short line for the table: what this run changed against its parent. */
export function changeLine(run: RunRecord, byId: Map<string, RunRecord>): string {
  const parent = run.parent_run ? byId.get(run.parent_run) : undefined
  if (!run.parent_run) return run.model ? `first ${run.model} run` : 'first run'
  if (!parent) return `parent ${run.parent_run} not listed`
  const diff = configDiff(run.config, parent.config).filter((d) => d.key !== 'seed')
  if (!diff.length) return 'same config (new data or seed)'
  const model = diff.find((d) => d.key === 'model')
  if (model) return `${show(model.parent)} → ${show(model.value)}`
  const parts = diff.slice(0, 2).map((d) => `${d.key} ${show(d.parent)} → ${show(d.value)}`)
  return diff.length > 2 ? `${parts.join(', ')} +${diff.length - 2} more` : parts.join(', ')
}

/** "rejected: did not beat the champion at 168 h", "promoted by hand: <first reason>" and their kin, from the stored
 *  decision (read the same way as the Improve markers, see decision.ts). */
export function decisionLine(run: RunRecord): string {
  const d = run.metrics?.decision
  const state = run.metrics?.state
  if (state && state !== 'done') return `not scored (${state})`
  if (!d) return run.status === 'champion' ? 'champion (set by hand)' : STATUS_LABEL[run.status] ?? run.status
  const v = verdict(d)
  const word = run.status === 'candidate' ? 'not promoted' : 'rejected'
  if (v.hand) return byHandLine(d, run.status === 'candidate' ? 'kept as a candidate' : word)
  if (d.promote) return `promoted: ${promotionWhy(d, horizonLabel)}`
  const why: string[] = []
  if (v.lost.length) why.push(`did not beat ${v.against} at ${v.lost.map(horizonLabel).join(', ')}`)
  const badCal = (d.calibration ?? []).filter((c) => c.ok === false)
  if (badCal.length) why.push(`${badCal.map((c) => c.name).join(', ')} out of tolerance`)
  return why.length ? `${word}: ${why.join('; ')}` : `${word}`
}

/** The run the detail panel shows: the selected one while it is still listed, else the first shown. A refresh, or a
 *  fallback to the sample data, can drop the selected run from the list; that must never leave a dangling id. */
export function currentRun<R extends { run_id: string }>(selected: string | null, byId: Map<string, R>, shown: R[]): R | undefined {
  return (selected != null ? byId.get(selected) : undefined) ?? shown[0]
}

/** The run detail's decision lines: the backend's one-sentence decision_summary when present, with the stored
 *  decision read in words under it; else that reading alone. */
export function decisionHeadline(run: RunRecord, detail: Pick<RunDetail, 'decision_summary'> | null | undefined): { main: string; sub: string | null } {
  const line = decisionLine(run)
  const summary = detail?.decision_summary?.trim()
  return summary ? { main: summary, sub: line === summary ? null : line } : { main: line, sub: null }
}

export interface RunFilters { target: string; proposer: string; status: string }
export const ALL = 'all'
export function filterRuns(runs: RunRecord[], f: RunFilters): RunRecord[] {
  return runs
    .filter((r) => (f.target === ALL || r.target === f.target) && (f.proposer === ALL || r.proposer === f.proposer) && (f.status === ALL || r.status === f.status))
    .sort((a, b) => b.created_at - a.created_at)
}
/** Distinct values of a field, for the filter menus. */
export const distinct = <T,>(xs: T[], f: (x: T) => string | null | undefined) => [...new Set(xs.map(f).filter((v): v is string => !!v))].sort()

/** Strata where the candidate lost most against the reference: by total excess loss (difference × cases), so a big
 *  relative change on a near-zero loss in a small group doesn't top the list. */
export function weakestStrata(run: Pick<RunRecord, 'metrics'>, k = 5): (Stratum & { diff: number })[] {
  return (run.metrics?.decision?.strata_worse ?? [])
    .map((s) => ({ ...s, diff: s.cand - s.ref }))
    .sort((a, b) => b.diff * b.n - a.diff * a.n)
    .slice(0, k)
}

/** Rows of the per-horizon skill table: the run against the baseline, and the decision's comparison against the champion. */
export interface HorizonRow { h: number; skill: SkillH | null; vs: DecisionH | null }
export function horizonRows(run: Pick<RunRecord, 'metrics'>): HorizonRow[] {
  return horizons(run).map((h) => ({ h, skill: run.metrics?.skill?.[String(h)] ?? null, vs: run.metrics?.decision?.horizons?.[String(h)] ?? null }))
}

/** Calibration checks: the decision's (with ok) when present, else the run's own. */
export function calibrationChecks(run: Pick<RunRecord, 'metrics'>): CalCheck[] {
  const d = run.metrics?.decision?.calibration
  return d?.length ? d : run.metrics?.calibration ?? []
}
/** A coverage-style check (route circles: "80% radius coverage", cover80) is a share, written in percent. */
export const isCoverage = (name: string) => /coverage|cover\d|circle|%/i.test(name)
const sig = (x: number) => String(Number(x.toPrecision(3)))
const pc = (x: number) => `${sig(x * 100)}\u00a0%`
/** "80.5 % (target 80 % ± 5 %)" for coverage, "0.027 (target 0 ± 0.05)" for the rest. */
export function fmtCalCheck(c: CalCheck): string {
  const f = isCoverage(c.name) ? pc : sig
  const v = c.value == null ? '—' : f(c.value)
  const target = c.nominal == null ? '' : ` (target ${f(c.nominal)}${c.tol != null ? ` ± ${f(c.tol)}` : ''})`
  return v + target
}
export function calibrationOk(c: CalCheck): boolean | null {
  if (c.ok != null) return c.ok
  if (c.value == null || c.nominal == null || c.tol == null) return null
  return Math.abs(c.value - c.nominal) <= c.tol
}

/** Rows for the skill chart: per horizon, this run's skill over the baseline and, when given, the champion's on the same horizon. */
export interface SkillRow { key: string; h: number; who: 'run' | 'champion'; v: number; lo: number | null; hi: number | null; sameHoldout: boolean }
export function skillRows(run: Pick<RunRecord, 'metrics'>, champion?: Pick<RunRecord, 'metrics'> | null): SkillRow[] {
  const same = !!champion && champion.metrics?.holdout?.hash != null && champion.metrics.holdout.hash === run.metrics?.holdout?.hash
  return horizons(run).flatMap((h) => {
    const out: SkillRow[] = []
    const s = run.metrics?.skill?.[String(h)]
    if (s?.skill != null) out.push({ key: `${horizonLabel(h)} · this run`, h, who: 'run', v: s.skill, lo: s.skill_lo, hi: s.skill_hi, sameHoldout: true })
    const c = champion?.metrics?.skill?.[String(h)]
    if (c?.skill != null) out.push({ key: `${horizonLabel(h)} · champion`, h, who: 'champion', v: c.skill, lo: c.skill_lo, hi: c.skill_hi, sameHoldout: same })
    return out
  })
}
