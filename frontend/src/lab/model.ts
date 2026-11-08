import type { LabModel } from './hash'
import type { LabEvent, Metrics, ModelSummary, Proposal, Run, Summary } from './types'

// Plain-words reading of each model for the home cards and the model page: the headline number, the status (one
// colour scale everywhere), the pipeline counts. Prefers what /lab/summary says (lab2-plain adds headline, status,
// pipeline); otherwise derives the same from the existing fields. Pure; tested in model.test.ts.

export type Level = 'ok' | 'warn' | 'bad' | 'none'
export interface Headline { text: string; value: number | null; unit: string | null }
export interface Status { level: Level; text: string }

export const MODEL_INFO: Record<LabModel, { name: string; question: string }> = {
  route: { name: 'Route', question: 'Where is a silent ship now?' },
  godark: { name: 'Go-dark', question: 'Will this ship go dark?' },
  fishing: { name: 'Fishing', question: 'Will it fish in a protected area?' },
}

/** Optional fields lab2-plain adds to each /lab/summary model. */
export type PipelineStage = 'new_data' | 'proposed' | 'trained' | 'judged' | 'promoted' | 'rejected' | 'graded'
type StageValue = number | { n?: number | null; count?: number | null; last_ts?: number | null } | null
export interface SummaryExtras {
  headline?: Headline | null
  status?: Status | null
  pipeline?: Partial<Record<PipelineStage | 'last_ts', StageValue | Record<string, number | null>>> | null
  runs_total?: number | null
  runs_gemini?: number | null
}
export type RichSummary = ModelSummary & SummaryExtras

export const modelSummary = (s: Summary | null, t: LabModel): RichSummary | null =>
  (s?.models.find((m) => m.target === t) as RichSummary | undefined) ?? null

export const runsOf = (runs: Run[] | null, t: LabModel) => (runs ?? []).filter((r) => r.target === t).sort((a, b) => b.created_at - a.created_at)
export const proposalsOf = (ps: Proposal[] | null, t: LabModel) => (ps ?? []).filter((p) => p.target === t)
export const eventsOf = (es: LabEvent[] | null, t: LabModel) => (es ?? []).filter((e) => e.target === t)

const sameModel = (c: string, v: string) => c === v || c.replace(/-cal\d+$/, '') === v || v.replace(/-cal\d+$/, '') === c
function wmean<T>(rows: T[], n: (r: T) => number, v: (r: T) => number | null | undefined): number | null {
  let w = 0, s = 0
  for (const r of rows) { const x = v(r); if (x == null || !Number.isFinite(x)) continue; w += n(r); s += n(r) * x }
  return w > 0 ? s / w : null
}
const km = (m: number) => (m >= 10_000 ? Math.round(m / 1000) : Math.round(m / 100) / 10)
const pct0 = (x: number) => Math.round(x * 100)

/** Route at 3 h: live median error (km) and how often the 80% circle held the ship, for the champion. */
export function routeLive(metrics: Metrics | null, champion: string | null, h = 10800) {
  const rows = (metrics?.route ?? []).filter((r) => r.horizon_s === h && (r.mode ?? 'live') === 'live' && r.n > 0
    && (champion ? sameModel(champion, r.model_version) : !r.model_version.startsWith('baseline')))
  const n = rows.reduce((a, r) => a + r.n, 0)
  return { n, errM: wmean(rows, (r) => r.n, (r) => r.median_err_m), cov80: wmean(rows, (r) => r.n, (r) => r.cov80) }
}

/** Go-dark: lift of the top-flagged ships, and the mean prediction against the actual rate, for dark_6h when graded. */
export function godarkLive(metrics: Metrics | null, champion: string | null) {
  const lifts = metrics?.lift ?? []
  const lift = lifts.find((l) => l.target === 'dark_6h') ?? lifts.find((l) => l.target.startsWith('dark')) ?? null
  const all = (metrics?.godark ?? []).filter((r) => (r.mode ?? 'live') === 'live' && r.n > 0 && (!champion || sameModel(champion, r.model_version)))
  const target = all.some((r) => r.target === 'dark_6h') ? 'dark_6h' : all[0]?.target ?? null
  const rows = all.filter((r) => r.target === target)
  return {
    target,
    n: rows.reduce((a, r) => a + r.n, 0),
    lift: lift && lift.all_hit_rate > 0 ? lift.top_hit_rate / lift.all_hit_rate : null,
    liftTarget: lift?.target ?? null,
    said: wmean(rows, (r) => r.n, (r) => r.mean_p),
    actual: wmean(rows, (r) => r.n, (r) => r.hit_rate),
  }
}

/** The champion run's held-out numbers at its primary horizon (recall at the operating threshold if stored, AUC-PR). */
export function heldOut(run: Run | null | undefined, h: number | null | undefined) {
  const sum = run?.metrics?.summary ?? null
  const key = h != null && sum?.[String(h)] ? String(h) : sum ? Object.keys(sum)[0] : null
  const s = (key && sum?.[key]) || {}
  const num = (k: string) => (typeof s[k] === 'number' && Number.isFinite(s[k] as number) ? (s[k] as number) : null)
  const recall = num('recall_at_threshold') ?? num('recall') ?? num('recall_at_op')
  return { recall, aucPr: num('auc_pr'), baseRate: num('base_rate'), n: num('n') }
}

export function championRun(m: ModelSummary | null, runs: Run[]): Run | null {
  if (!m) return null
  return runs.find((r) => r.run_id === m.champion.run_id) ?? runs.find((r) => r.status === 'champion') ?? null
}

/** Within 5 points of the target: on target; within 15: drifting; else off target. */
export function levelFor(value: number | null, target: number, warn = 0.05, bad = 0.15): Level {
  if (value == null || !Number.isFinite(value)) return 'none'
  const d = Math.abs(value - target)
  return d <= warn ? 'ok' : d <= bad ? 'warn' : 'bad'
}

export interface ModelView { headline: Headline; sub: string | null; status: Status }

export function modelView(t: LabModel, m: RichSummary | null, runs: Run[], metrics: Metrics | null): ModelView {
  const derived = derive(t, m, runs, metrics)
  return {
    headline: m?.headline?.text ? m.headline : derived.headline,
    sub: derived.sub,
    status: m?.status?.text ? m.status : derived.status,
  }
}

function derive(t: LabModel, m: ModelSummary | null, runs: Run[], metrics: Metrics | null): ModelView {
  const none = (text: string): Status => ({ level: 'none', text })
  if (!m) return { headline: { text: 'No model trained yet', value: null, unit: null }, sub: null, status: none('No data yet') }
  const champ = m.champion.version
  if (t === 'route') {
    const r = routeLive(metrics, champ)
    const head: Headline = r.errM == null
      ? { text: 'No live grades in the last 24 h yet', value: null, unit: null }
      : { text: `Finds a silent ship within ${km(r.errM)} km after 3 hours`, value: km(r.errM), unit: 'km' }
    const sub = r.cov80 == null ? null : `Circle held the ship ${pct0(r.cov80)}% of the time · target 80%`
    const level = levelFor(r.cov80, 0.8)
    return { headline: head, sub, status: level === 'none' ? none('Not graded live yet') : { level, text: level === 'ok' ? 'Circles on target' : level === 'warn' ? 'Circles drifting from 80%' : 'Circles too small: off target' } }
  }
  if (t === 'godark') {
    const g = godarkLive(metrics, champ)
    const head: Headline = g.lift == null
      ? { text: 'No live grades in the last 24 h yet', value: null, unit: null }
      : { text: `Flagged ships go dark ${g.lift.toFixed(1)}× more often`, value: Math.round(g.lift * 10) / 10, unit: '×' }
    const sub = g.said == null || g.actual == null ? null : `Says ${pctTxt(g.said)}, actual ${pctTxt(g.actual)}${g.target ? ` · ${g.target.replace('dark_', 'dark within ')}` : ''}`
    let level: Level = 'none'
    if (g.said != null && g.actual != null) {
      const ratio = g.actual > 0 ? g.said / g.actual : g.said > 0.02 ? 99 : 1
      level = ratio >= 0.75 && ratio <= 1.33 ? 'ok' : ratio >= 0.5 && ratio <= 2 ? 'warn' : 'bad'
    }
    return { headline: head, sub, status: level === 'none' ? none('Not graded live yet') : { level, text: level === 'ok' ? 'Odds on target' : level === 'warn' ? 'Odds drifting' : 'Odds off target' } }
  }
  const ho = heldOut(championRun(m, runs), m.offline.primary_h)
  const head: Headline = ho.recall != null
    ? { text: `Spots ${Math.round(ho.recall * 10)} in 10 protected-area fishing weeks`, value: Math.round(ho.recall * 10), unit: 'in 10' }
    : ho.aucPr != null
      ? { text: `Ranks ${Math.round(ho.aucPr * 10)} in 10 protected-area fishing weeks correctly`, value: Math.round(ho.aucPr * 10), unit: 'in 10' }
      : { text: 'No held-out score recorded yet', value: null, unit: null }
  const sub = ho.baseRate != null ? `On held-out weeks · ${pctTxt(ho.baseRate)} of weeks had such fishing` : null
  return { headline: head, sub, status: m.live && m.live.n > 0 ? { level: 'ok', text: `Graded live: ${m.live.n} predictions` } : none(m.deployed ? 'No live grades yet' : 'Not served live yet') }
}

const pctTxt = (x: number) => (x < 0.1 && x > 0 ? `${(x * 100).toFixed(1)}%` : `${Math.round(x * 100)}%`)

/** The champion's primary held-out number over time, for sparklines: one point per champion (promotion) run. */
export function championSeries(runs: Run[], h: number | null | undefined): { t: number; v: number }[] {
  return runs
    .filter((r) => r.status === 'champion' || r.status === 'retired')
    .map((r) => ({ t: r.created_at, v: skillAt(r, h) }))
    .filter((p): p is { t: number; v: number } => p.v != null)
    .sort((a, b) => a.t - b.t)
}

export function skillAt(r: Run, h: number | null | undefined): number | null {
  const sk = r.metrics?.skill
  if (!sk) return null
  const v = (h != null ? sk[String(h)] : undefined) ?? Object.values(sk)[0]
  return v?.skill ?? null
}

export interface Stage { key: PipelineStage; label: string; n: number | null; last: number | null }

const STAGES: [PipelineStage, string][] = [
  ['new_data', 'New data'], ['proposed', 'Gemini proposes'], ['trained', 'Train'], ['judged', 'Judge on frozen test'],
  ['promoted', 'Promote'], ['rejected', 'Reject'], ['graded', 'Live grading'],
]

/** Pipeline counts from summary.pipeline when present, else from runs, proposals, events and live. */
export function pipeline(m: RichSummary | null, runs: Run[], proposals: Proposal[], events: LabEvent[], trainingN: number | null): Stage[] {
  const p = m?.pipeline ?? null
  const lastTs = (p?.last_ts && typeof p.last_ts === 'object' ? p.last_ts : {}) as Record<string, number | null>
  const latest = (xs: (number | null | undefined)[]) => xs.reduce<number | null>((a, x) => (x != null && (a == null || x > a) ? x : a), null)
  const judged = runs.filter((r) => r.metrics?.decision != null)
  const ev = (k: string) => events.filter((e) => e.kind === k)
  const derived: Record<PipelineStage, { n: number | null; last: number | null }> = {
    new_data: { n: trainingN, last: latest(runs.map((r) => r.train_to)) },
    proposed: { n: proposals.length, last: latest(proposals.map((x) => x.created_at)) },
    trained: { n: runs.length, last: latest(runs.map((r) => r.created_at)) },
    judged: { n: judged.length, last: latest(judged.map((r) => r.created_at)) },
    promoted: { n: runs.filter((r) => r.status === 'champion' || r.status === 'retired').length, last: latest([...ev('promoted').map((e) => e.ts), ...runs.filter((r) => r.status === 'champion').map((r) => r.created_at)]) },
    rejected: { n: runs.filter((r) => r.status === 'rejected').length, last: latest([...ev('rejected').map((e) => e.ts), ...runs.filter((r) => r.status === 'rejected').map((r) => r.created_at)]) },
    graded: { n: m?.live?.n ?? null, last: null },
  }
  return STAGES.map(([key, label]) => {
    const raw = p?.[key] as StageValue | undefined
    const n = typeof raw === 'number' ? raw : raw && typeof raw === 'object' ? raw.n ?? raw.count ?? null : undefined
    const last = raw && typeof raw === 'object' ? raw.last_ts ?? null : lastTs[key] ?? undefined
    return { key, label, n: n === undefined ? derived[key].n : n, last: last === undefined ? derived[key].last : last }
  })
}
