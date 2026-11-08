// Data shaping for the Champions & challengers tab: the timeline points, the champion line, the latest decision as one
// plain sentence, and the proposals list. Plain words only (no "skill", "log loss", "dead reckoning").
import { byHandLine, verdict } from '../decision'
import { configDiff, horizonLabel, primaryHorizon, type RunRecord } from '../runs/shape'
import type { Proposal } from '../types'

/** The tab's subject: a target name, or anything carrying one (a /lab/summary model). */
export type ModelRef = string | { target: string }
export const targetOf = (m: ModelRef) => (typeof m === 'string' ? m : m.target)

/** Route is judged on 3 h when it has it (the headline horizon), the others on their shortest scored horizon. */
export const PREFERRED_H: Record<string, number> = { route: 10800 }

export interface Measure {
  /** Axis title in plain words. */
  label: string
  /** Lower is better (route km), else higher is better. */
  lowerBetter: boolean
  /** Format a y value for the axis and the tooltips. */
  fmt: (v: number) => string
  /** The run's value, or null when it has no held-out number. */
  value: (r: RunRecord) => number | null
}

const km = (m: number) => `${(m / 1000).toFixed(m >= 10000 ? 0 : 1)} km`
const pct = (x: number) => `${x >= 0 ? '' : '−'}${Math.abs(Math.round(x * 100))}%`

/** The number each run is drawn at: route's typical miss in km, the others' improvement over a simple guess. */
export function measureFor(target: string): Measure {
  const pref = PREFERRED_H[target]
  if (target === 'route') {
    return {
      label: `Typical miss after ${horizonLabel(pref)}`,
      lowerBetter: true,
      fmt: km,
      value: (r) => {
        const h = primaryHorizon(r, pref)
        const v = h == null ? null : r.metrics?.skill?.[String(h)]?.stat
        return v == null || !Number.isFinite(v) ? null : v
      },
    }
  }
  return {
    label: 'Better than a simple guess',
    lowerBetter: false,
    fmt: pct,
    value: (r) => {
      const h = primaryHorizon(r, pref)
      const v = h == null ? null : r.metrics?.skill?.[String(h)]?.skill
      return v == null || !Number.isFinite(v) ? null : v
    },
  }
}

/** Was this run ever the champion (now, or retired from it)? */
export const wasChampion = (r: RunRecord) => r.status === 'champion' || r.status === 'retired'

export type PointKind = 'champion' | 'retired' | 'candidate' | 'rejected'
export interface Point { run: RunRecord; x: number; y: number | null; kind: PointKind; gemini: boolean }

/** Every run of the model, oldest first, with its y value (null: no held-out number, drawn on the top rail). */
export function timelinePoints(runs: RunRecord[], target: string): Point[] {
  const m = measureFor(target)
  return runs
    .filter((r) => r.target === target)
    .sort((a, b) => a.created_at - b.created_at)
    .map((r) => ({
      run: r,
      x: r.created_at,
      y: m.value(r),
      kind: (['champion', 'retired', 'candidate'].includes(r.status) ? r.status : 'rejected') as PointKind,
      gemini: r.proposer === 'gemini',
    }))
}

/** The champion line: past and present champions in time order, extended flat to `now` from the current one. */
export function championLine(points: Point[], now: number): { x: number; y: number }[] {
  const line = points.filter((p) => wasChampion(p.run) && p.y != null).map((p) => ({ x: p.x, y: p.y as number }))
  const last = line[line.length - 1]
  if (last && now > last.x) line.push({ x: now, y: last.y })
  return line
}

/** Words levels 1 and 2 never show. */
export const JARGON = /skill|brier|log[ -]?loss|dead reckoning|isotonic|\bece\b|auc/i

const WHO: Record<string, string> = { gemini: 'Gemini proposed', human: 'A person tried', default: 'The fixed list tried' }

const words = (k: string) => k.replace(/_/g, ' ')
const val = (v: unknown) => (v == null ? 'none' : typeof v === 'object' ? JSON.stringify(v) : String(v))

/** What a run changed against its parent, in a few words: "fewer num leaves (63 → 31)", "a new model: lgbm". */
export function changePhrase(run: RunRecord, byId: Map<string, RunRecord>): string {
  if (!run.parent_run) return run.model ? `a first ${run.model} model` : 'a first model'
  const parent = byId.get(run.parent_run)
  if (!parent) return 'a change'
  const diff = configDiff(run.config, parent.config).filter((d) => d.key !== 'seed')
  if (!diff.length) return 'the same settings on newer data'
  const d = diff[0]
  let p: string
  if (d.key === 'model') p = `a different model (${val(d.parent)} → ${val(d.value)})`
  else if (typeof d.parent === 'number' && typeof d.value === 'number') {
    const count = /^(n_|num_)|leaves|trees|rounds|estimators|features|bins/i.test(d.key)
    const dir = d.value < d.parent ? (count ? 'fewer' : 'lower') : (count ? 'more' : 'higher')
    p = `${dir} ${words(d.key).replace(/^(n|num) /, '')} (${val(d.parent)} → ${val(d.value)})`
  } else if (d.parent == null) p = `${words(d.key)} set to ${val(d.value)}`
  else p = `${words(d.key)} ${val(d.parent)} → ${val(d.value)}`
  return diff.length > 1 ? `${p} and ${diff.length - 1} more change${diff.length > 2 ? 's' : ''}` : p
}

/** The outcome half of the sentence: "rejected, not better than the champion at 3 h". */
export function outcomePhrase(run: RunRecord): string {
  const d = run.metrics?.decision
  const state = run.metrics?.state
  if (state && state !== 'done') return `not scored yet (${state})`
  if (!d) return run.status === 'champion' ? 'made champion by hand' : run.status === 'candidate' ? 'kept as a candidate' : run.status === 'retired' ? 'was champion, now replaced' : 'rejected'
  const v = verdict(d)
  if (v.hand) {
    // A person decided: their stored reason is shown only when it is plain words (the run panel has it in full).
    const line = byHandLine(d, run.status === 'candidate' ? 'kept as a candidate' : 'rejected').replace(/dead reckoning/gi, 'a straight-line guess')
    return JARGON.test(line) ? line.split(':')[0] : line
  }
  if (d.promote) return v.won.length ? `promoted, better than ${v.against} at ${v.won.map(horizonLabel).join(', ')}` : `promoted, passed every check against ${v.against}`
  const why: string[] = []
  if (v.lost.length) why.push(`not better than ${v.against} at ${v.lost.map(horizonLabel).join(', ')}`)
  if ((d.calibration ?? []).some((c) => c.ok === false)) why.push('its stated chances were off')
  const word = run.status === 'candidate' ? 'not promoted' : 'rejected'
  return why.length ? `${word}, ${why.join(' and ')}` : word
}

/** "Gemini proposed fewer leaves: rejected, not better than the champion at 3 h." */
export function decisionSentence(run: RunRecord, byId: Map<string, RunRecord>): string {
  const who = WHO[run.proposer ?? ''] ?? 'A run tried'
  return `${who} ${changePhrase(run, byId)}: ${outcomePhrase(run)}.`
}

/** The newest run of the model that has been decided (not still training). */
export function latestDecided(runs: RunRecord[], target: string): RunRecord | undefined {
  return runs
    .filter((r) => r.target === target && (!r.metrics?.state || r.metrics.state === 'done'))
    .sort((a, b) => b.created_at - a.created_at)[0]
}

export type ProposalKind = 'valid' | 'invalid' | 'duplicate'
export interface ProposalRow { p: Proposal; kind: ProposalKind; change: string; reason: string; outcome: string }

const OUTCOME: Record<string, string> = { champion: 'became champion', candidate: 'kept as a candidate', rejected: 'trained, rejected', invalid: 'not run', duplicate: 'not run' }

/** The model's proposals, newest first, each with its kind and the reason in words. */
export function proposalRows(proposals: Proposal[], target: string): ProposalRow[] {
  return proposals
    .filter((p) => p.target === target)
    .sort((a, b) => b.created_at - a.created_at)
    .map((p) => {
      const kind: ProposalKind = p.outcome === 'duplicate' ? 'duplicate' : !p.valid || p.outcome === 'invalid' ? 'invalid' : 'valid'
      const change = p.proposal && Object.keys(p.proposal).length ? Object.entries(p.proposal).map(([k, v]) => `${words(k)} ${val(v)}`).join(', ') : 'no change given'
      const reason = kind === 'duplicate'
        ? (p.errors?.join('; ') || 'already tried with the same settings')
        : kind === 'invalid' ? (p.errors?.join('; ') || 'outside the allowed settings') : (p.rationale ?? '')
      return { p, kind, change, reason, outcome: OUTCOME[p.outcome] ?? p.outcome }
    })
}
