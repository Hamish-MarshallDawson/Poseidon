// Data shaping for "How it improved": the champion's offline skill as a step series, the live skill under it, the
// event markers with their tooltip text, and the recalibration log. Pure functions over the /lab/* contract (lab.md),
// typed structurally so they accept lab-shell's full types.

export type ModelKey = 'route' | 'godark' | 'fishing'

export interface SkillAt { n?: number | null; skill: number | null; skill_lo?: number | null; skill_hi?: number | null }
export interface Decision { promote?: boolean | null; against?: string | null; reasons?: string[] | null; horizons?: Record<string, { win?: boolean | null }> | null }
export interface RunLike {
  run_id: string
  target: string
  model?: string | null
  status?: string | null
  proposer?: string | null
  parent_run?: string | null
  created_at: number
  config?: Record<string, unknown> | null
  metrics?: { skill?: Record<string, SkillAt> | null; decision?: Decision | null } | null
}
export interface EventLike { ts: number; target: string; kind: string; run_id?: string | null; version?: string | null; label?: string | null; detail?: Record<string, unknown> | null }
export interface ProposalLike { id: string; target: string; created_at: number; proposer?: string | null; rationale?: string | null; run_id?: string | null; outcome?: string | null; valid?: boolean | null; errors?: string[] | null; proposal?: unknown }
export interface ModelSummaryLike {
  target: string
  label?: string
  champion: { run_id?: string | null; version: string; since?: number | null; proposer?: string | null }
  offline: { primary_h: number; skill: number | null; skill_lo?: number | null; skill_hi?: number | null; holdout?: string | null }
  live?: { hours?: number; n?: number; primary?: { name: string; value: number | null; ref_label?: string } | null } | null
}
export interface RouteRowLike { t: number; mode?: string | null; model_version: string; horizon_s: number; n: number; skill: number | null }
export interface GodarkRowLike { t: number; mode?: string | null; target: string; model_version: string; n: number; brier_skill: number | null }
export interface MetricsLike { route?: RouteRowLike[] | null; godark?: GodarkRowLike[] | null }

/** Registry targets that belong to one of the three Lab models (godark_gfw is a go-dark candidate trained on GFW gaps). */
export const modelKey = (target: string): ModelKey | null =>
  target === 'route' || target.startsWith('route') ? 'route'
    : target.startsWith('godark') ? 'godark'
      : target.startsWith('fishing') ? 'fishing' : null

export const BASELINE: Record<ModelKey, string> = { route: 'dead reckoning', godark: 'the base rate', fishing: 'the baseline' }

export const hoursLabel = (s: number) => (s >= 86400 && s % 86400 === 0 ? `${s / 86400} d` : `${Math.round(s / 3600)} h`)
export const pct = (x: number | null | undefined) => (x == null || !Number.isFinite(x) ? '–' : `${x < 0 ? '−' : ''}${Math.abs(Math.round(x * 100))}%`)

const skillAt = (run: RunLike | undefined, h: number): SkillAt | null => run?.metrics?.skill?.[String(h)] ?? null

// ---------------------------------------------------------------- champion steps

export type StepHow = 'promoted' | 'deployed' | 'recalibrated' | 'current'
export interface Step { t: number; value: number | null; lo: number | null; hi: number | null; version: string; run_id: string | null; how: StepHow }

const base = (v: string) => v.replace(/-cal\d+$/, '')

/** The champion's offline primary skill over time: one step per promotion or deployment (a recalibration keeps the
 *  offline skill but changes the version), ending with the current champion. Values come from the run record, then
 *  the event's `skill_<h>h` detail, then the summary (for the current champion and its earlier, uncalibrated self). */
export function championSteps(model: ModelSummaryLike, runs: RunLike[], events: EventLike[]): Step[] {
  const key = modelKey(model.target)
  const h = model.offline.primary_h
  const byId = new Map(runs.map((r) => [r.run_id, r]))
  const cur = model.champion
  const fromSummary = (version: string) =>
    base(version) === base(cur.version) || (cur.run_id != null && version === cur.run_id)
      ? { value: model.offline.skill, lo: model.offline.skill_lo ?? null, hi: model.offline.skill_hi ?? null } : null
  const value = (e: { run_id?: string | null; version: string; detail?: Record<string, unknown> | null }) => {
    const run = byId.get(e.run_id ?? '') ?? byId.get(e.version)
    const s = skillAt(run, h)
    if (s && s.skill != null) return { value: s.skill, lo: s.skill_lo ?? null, hi: s.skill_hi ?? null }
    const d = e.detail?.[`skill_${Math.round(h / 3600)}h`]
    if (typeof d === 'number') return { value: d, lo: null, hi: null }
    return fromSummary(e.version) ?? { value: null, lo: null, hi: null }
  }

  const evs = events
    .filter((e) => modelKey(e.target) === key && (e.kind === 'promoted' || e.kind === 'deployed' || e.kind === 'recalibrated'))
    // only events about the served model family (godark_gfw promotions are candidates, not the live champion)
    .filter((e) => e.target === model.target)
    .sort((a, b) => a.ts - b.ts)

  const steps: Step[] = []
  for (const e of evs) {
    const version = e.version ?? e.run_id ?? '?'
    const prev = steps[steps.length - 1]
    if (prev && prev.version === version) continue           // deployed, then promoted, the same version: one step
    if (e.kind === 'recalibrated') {
      const v = prev && base(prev.version) === base(version) ? prev : { ...value({ ...e, version }) }
      steps.push({ t: e.ts, value: v.value, lo: v.lo, hi: v.hi, version, run_id: e.run_id ?? null, how: 'recalibrated' })
    } else {
      steps.push({ t: e.ts, ...value({ ...e, version }), version, run_id: e.run_id ?? null, how: e.kind as StepHow })
    }
  }
  if (!steps.some((s) => s.version === cur.version)) {
    const t = cur.since ?? steps[steps.length - 1]?.t ?? 0
    steps.push({ t, ...(fromSummary(cur.version) ?? { value: null, lo: null, hi: null }), version: cur.version, run_id: cur.run_id ?? null, how: 'current' })
    steps.sort((a, b) => a.t - b.t)
  }
  return steps
}

// ---------------------------------------------------------------- live skill

export interface LivePoint { t: number; value: number; n: number }
export interface LiveSeries { live: LivePoint[]; backtest: LivePoint[]; name: string }

/** The champion's skill per bucket on our own feed at the primary horizon (baseline rows dropped, n-weighted over
 *  model versions), split into live grading and backtest replays. Route: median-error skill over dead reckoning;
 *  go-dark: Brier skill over the base rate. Fishing is not graded live yet. */
export function liveSkill(model: ModelSummaryLike, metrics: MetricsLike | null | undefined): LiveSeries {
  const key = modelKey(model.target)
  const h = model.offline.primary_h
  type Row = { t: number; mode?: string | null; model_version: string; n: number; v: number | null }
  let rows: Row[] = []
  let name = ''
  if (key === 'route') {
    rows = (metrics?.route ?? []).filter((r) => r.horizon_s === h).map((r) => ({ ...r, v: r.skill }))
    name = `skill over dead reckoning at ${hoursLabel(h)}`
  } else if (key === 'godark') {
    const target = `dark_${Math.round(h / 3600)}h`
    rows = (metrics?.godark ?? []).filter((r) => r.target === target).map((r) => ({ ...r, v: r.brier_skill }))
    name = `Brier skill over the base rate at ${hoursLabel(h)}`
  }
  const fold = (mode: 'live' | 'backtest') => {
    const acc = new Map<number, { s: number; n: number }>()
    for (const r of rows) {
      if ((r.mode ?? 'live') !== mode || r.model_version.startsWith('baseline') || r.v == null || !(r.n > 0)) continue
      const a = acc.get(r.t) ?? { s: 0, n: 0 }
      a.s += r.v * r.n
      a.n += r.n
      acc.set(r.t, a)
    }
    return [...acc].sort((a, b) => a[0] - b[0]).map(([t, a]) => ({ t, value: a.s / a.n, n: a.n }))
  }
  return { live: fold('live'), backtest: fold('backtest'), name }
}

// ---------------------------------------------------------------- markers

export type MarkerKind = 'promoted' | 'rejected' | 'recalibrated' | 'deployed' | 'proposal'
export interface Marker { t: number; kind: MarkerKind; title: string; changed: string | null; why: string | null; run_id: string | null; target: string }

export const MARKER_LABEL: Record<MarkerKind, string> = {
  promoted: 'Promoted', rejected: 'Rejected', recalibrated: 'Recalibrated', deployed: 'Deployed', proposal: 'Gemini proposal',
}

const fmtVal = (v: unknown) => (v == null ? 'none' : typeof v === 'object' ? JSON.stringify(v) : String(v))

/** Config keys that differ between a run and its parent, as "key: old → new". */
export function configDiff(run: RunLike | undefined, parent: RunLike | undefined): string[] {
  if (!run?.config) return []
  const a = parent?.config ?? {}
  const b = run.config
  const keys = [...new Set([...Object.keys(a), ...Object.keys(b)])].sort()
  return keys.filter((k) => JSON.stringify(a[k]) !== JSON.stringify(b[k])).map((k) => `${k}: ${fmtVal(a[k])} → ${fmtVal(b[k])}`)
}

const describeRun = (run: RunLike | undefined, byId: Map<string, RunLike>) => {
  if (!run) return null
  const parent = run.parent_run ? byId.get(run.parent_run) : undefined
  const diff = configDiff(run, parent)
  if (diff.length) return diff.slice(0, 3).join('; ') + (diff.length > 3 ? ` (+${diff.length - 3} more)` : '')
  return run.model ? `model ${run.model}` : null
}

/** Plain-words reason for a promote/reject from the rule's decision, e.g. "did not beat the champion at 7 d". */
export function decisionWhy(run: RunLike | undefined): string | null {
  const d = run?.metrics?.decision
  if (!d) return null
  const hs = Object.entries(d.horizons ?? {})
  const lost = hs.filter(([, v]) => v?.win === false).map(([h]) => hoursLabel(Number(h)))
  const against = d.against && /baseline/i.test(d.against) && !/^champion/i.test(d.against) ? 'the baseline' : 'the champion'
  if (d.promote) return `beat ${against} at every primary horizon`
  if (lost.length) return `did not beat ${against} at ${lost.join(', ')}`
  return d.reasons?.[0] ?? 'failed the promotion rule'
}

/** Markers for one model: promoted, rejected, recalibrated and deployed events (rejected runs without an event are
 *  added from their status) and Gemini proposals, each with what changed and why. */
export function markers(model: ModelSummaryLike, runs: RunLike[], events: EventLike[], proposals: ProposalLike[] = []): Marker[] {
  const key = modelKey(model.target)
  const byId = new Map(runs.map((r) => [r.run_id, r]))
  const out: Marker[] = []
  const seen = new Set<string>()
  for (const e of events) {
    if (modelKey(e.target) !== key) continue
    if (!['promoted', 'rejected', 'recalibrated', 'deployed', 'proposal'].includes(e.kind)) continue
    const run = byId.get(e.run_id ?? '')
    const kind = e.kind as MarkerKind
    seen.add(`${kind}:${e.run_id ?? e.version}`)
    out.push({
      t: e.ts, kind, target: e.target, run_id: e.run_id ?? null,
      title: `${MARKER_LABEL[kind]} · ${e.version ?? e.run_id ?? e.target}`,
      changed: kind === 'recalibrated' ? e.label ?? null : describeRun(run, byId),
      why: kind === 'promoted' || kind === 'rejected' ? decisionWhy(run) ?? e.label ?? null : kind === 'recalibrated' ? null : e.label ?? null,
    })
  }
  for (const r of runs) {
    if (modelKey(r.target) !== key || r.status !== 'rejected' || seen.has(`rejected:${r.run_id}`)) continue
    out.push({ t: r.created_at, kind: 'rejected', target: r.target, run_id: r.run_id, title: `Rejected · ${r.run_id}`, changed: describeRun(r, byId), why: decisionWhy(r) })
  }
  for (const p of proposals) {
    if (modelKey(p.target) !== key || p.proposer !== 'gemini' || seen.has(`proposal:${p.run_id ?? p.id}`)) continue
    const outcome = p.valid === false ? `invalid: ${(p.errors ?? []).join('; ') || 'rejected by the schema'}` : p.outcome ? `outcome: ${p.outcome}` : null
    out.push({ t: p.created_at, kind: 'proposal', target: p.target, run_id: p.run_id ?? null, title: `Gemini proposal${p.run_id ? ` · ${p.run_id}` : ''}`, changed: p.rationale ?? null, why: outcome })
  }
  return out.sort((a, b) => a.t - b.t)
}

// ---------------------------------------------------------------- recalibration log

export interface RecalFactor { name: string; value: string; kept: boolean; why: string | null }
export interface RecalEntry { t: number; target: string; version: string; label: string; factors: RecalFactor[]; before: string | null; after: string | null; kept: boolean | null }

const num = (v: unknown) => (typeof v === 'number' && Number.isFinite(v) ? v : null)

/** Every `calN` recalibration (all models, newest first): its factors per horizon or target, the coverage before and
 *  after, and whether each part was kept or rejected and why. Tolerates the detail shapes the history import emits. */
export function recalLog(events: EventLike[]): RecalEntry[] {
  return events.filter((e) => e.kind === 'recalibrated').map((e) => {
    const d = e.detail ?? {}
    const factors: RecalFactor[] = []
    const keptFlag = typeof d.kept === 'boolean' ? d.kept : null
    for (const ring of ['80', '95']) {
      const k = d[`k${ring}`]
      if (k && typeof k === 'object') {
        for (const [h, v] of Object.entries(k as Record<string, unknown>)) {
          const f = num(v)
          if (f != null) factors.push({ name: `${ring}% circle at ${hoursLabel(Number(h))}`, value: `×${f.toFixed(2)}`, kept: keptFlag ?? true, why: null })
        }
      }
    }
    if (d.kept && typeof d.kept === 'object') {
      for (const [name, v] of Object.entries(d.kept as Record<string, unknown>)) {
        const f = num(v)
        factors.push({ name, value: f == null ? fmtVal(v) : `shift ${f > 0 ? '+' : '−'}${Math.abs(f).toFixed(2)}`, kept: true, why: null })
      }
    }
    if (d.rejected && typeof d.rejected === 'object') {
      for (const [name, v] of Object.entries(d.rejected as Record<string, unknown>)) {
        factors.push({ name, value: 'not applied', kept: false, why: typeof v === 'string' ? v : fmtVal(v) })
      }
    }
    const cov = (when: 'before' | 'after') => {
      const parts = ['80', '95'].flatMap((ring) => {
        const v = num(d[`cov${ring}_${when}`])
        return v == null ? [] : [`${ring}% circle held ${pct(v)} (target ${ring}%)`]
      })
      return parts.length ? parts.join(', ') : null
    }
    const anyKept = keptFlag ?? (factors.length ? factors.some((f) => f.kept) : null)
    return { t: e.ts, target: e.target, version: e.version ?? '', label: e.label ?? '', factors, before: cov('before'), after: cov('after'), kept: anyKept }
  }).sort((a, b) => b.t - a.t)
}
