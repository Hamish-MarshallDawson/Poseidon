// Plain-words numbers for the Live tab (pure; tested in plain.test.ts). One mode is shown: live when there is any,
// else the backtest replay (said so on screen).
import type { DarkMetricRow, Metrics, ModelSummary, Target } from '../types'
import { headline, isBaseline, modesIn, routeView, sameModel, type Mode } from './shape'

/** Status: green on target, amber drifting, red off target, grey no data. */
export type Level = 'ok' | 'warn' | 'bad' | 'none'
export const LEVEL_NAME: Record<Level, string> = { ok: 'On target', warn: 'Drifting', bad: 'Off target', none: 'No data yet' }

/** The model a tab is for: its target name, or its /lab/summary entry. */
export type ModelRef = Target | Pick<ModelSummary, 'target'> & Partial<Pick<ModelSummary, 'champion'>>
export const targetOf = (m: ModelRef): Target => (typeof m === 'string' ? m : m.target)
export const championOf = (m: ModelRef): string[] => (typeof m === 'string' || !m.champion?.version ? [] : [m.champion.version])

/** Circle coverage against its target: within 5 points ok, within 15 drifting, else off. */
export function coverageLevel(value: number | null | undefined, target: number): Level {
  if (value == null) return 'none'
  const d = Math.abs(value - target)
  return d <= 0.05 ? 'ok' : d <= 0.15 ? 'warn' : 'bad'
}

/** Said against actual (go-dark): within a factor 1.5 ok, 2.5 drifting, else off. */
export function ratioLevel(said: number | null, actual: number | null): Level {
  if (said == null || actual == null) return 'none'
  if (said <= 0 || actual <= 0) return said === actual ? 'ok' : 'bad'
  const r = Math.max(said / actual, actual / said)
  return r <= 1.5 ? 'ok' : r <= 2.5 ? 'warn' : 'bad'
}

export interface Tile { title: string; value: string; caption: string; level: Level; gauge?: { value: number; target: number; max: number } }
export interface TrendPoint { t: number; y: number | null; ref: number | null; n: number }
export interface LivePlain {
  mode: Mode | null
  version: string | null
  n: number
  tiles: [Tile, Tile]
  /** One line per hour: route median miss (km) against the straight-line guess; go-dark actual against said (0..1). */
  trend: { kind: 'km' | 'share'; label: string; refLabel: string; points: TrendPoint[] }
}

const pct = (x: number | null | undefined) => (x == null ? '–' : `${Math.round(x * 100)}%`)
const pct1 = (x: number | null | undefined) => (x == null ? '–' : x < 0.1 ? `${(x * 100).toFixed(1)}%` : `${Math.round(x * 100)}%`)
const km = (m: number | null | undefined) => (m == null ? '–' : m >= 10_000 ? `${Math.round(m / 1000)} km` : `${(m / 1000).toFixed(1)} km`)
const hours = (s: number) => (s % 3600 === 0 ? `${s / 3600} h` : `${Math.round(s / 60)} min`)
const pickMode = (rows: { mode?: string }[]): Mode | null => modesIn(rows)[0] ?? null
const modeOf = (r: { mode?: string }): Mode => (r.mode === 'backtest' ? 'backtest' : 'live')
const NONE = (title: string, caption = 'No graded predictions yet'): Tile => ({ title, value: '–', caption, level: 'none' })

export function livePlain(metrics: Metrics, model: ModelRef): LivePlain {
  const t = targetOf(model)
  if (t === 'route') return routePlain(metrics, championOf(model))
  if (t === 'godark') return darkPlain(metrics, championOf(model))
  return {
    mode: null, version: null, n: 0,
    tiles: [NONE('Protected-area fishing spotted', 'No graded live weeks yet'), NONE('Says vs actual', 'Graded once a scored week has passed')],
    trend: { kind: 'share', label: '', refLabel: '', points: [] },
  }
}

function routePlain(metrics: Metrics, champions: string[]): LivePlain {
  const mode = pickMode(metrics.route)
  const hs = [...new Set(metrics.route.filter((r) => modeOf(r) === mode).map((r) => r.horizon_s))].sort((a, b) => a - b)
  const h = hs.includes(10800) ? 10800 : hs[0]
  const empty: LivePlain = {
    mode, version: null, n: 0,
    tiles: [NONE('Where the ship is'), NONE('Circle held the ship')],
    trend: { kind: 'km', label: 'median miss', refLabel: 'straight-line guess', points: [] },
  }
  if (!mode || h == null) return empty
  const v = routeView(metrics.route, h, mode)
  const head = headline(v.pooled, champions)
  if (!head) return empty
  const better = head.err != null && head.base != null ? head.err < head.base : null
  const points = (v.series.find((s) => s.version === head.version)?.points ?? []).map((p) => ({ t: p.t, y: p.err == null ? null : p.err / 1000, ref: p.base == null ? null : p.base / 1000, n: p.n }))
  return {
    mode, version: head.version, n: head.n,
    tiles: [
      {
        title: `Where the ship is after ${hours(h)}`, value: `within ${km(head.err)}`,
        caption: head.base == null ? 'Half of the misses are shorter than this' : `Half the misses are shorter · a straight-line guess: ${km(head.base)}`,
        level: better == null ? 'none' : better ? 'ok' : head.err != null && head.err <= head.base! * 1.1 ? 'warn' : 'bad',
      },
      {
        title: 'Circle held the ship', value: pct(head.cov80), caption: 'of the time · target 80%',
        level: coverageLevel(head.cov80, 0.8), gauge: head.cov80 == null ? undefined : { value: head.cov80, target: 0.8, max: 1 },
      },
    ],
    trend: { kind: 'km', label: `median miss at ${hours(h)}`, refLabel: 'straight-line guess', points },
  }
}

function darkPlain(metrics: Metrics, champions: string[]): LivePlain {
  const mode = pickMode(metrics.godark)
  const models = metrics.godark.filter((r) => modeOf(r) === mode && !isBaseline(r.model_version) && r.n > 0)
  const versions = [...new Set(models.map((r) => r.model_version))]
  const version = champions.map((c) => versions.find((v) => sameModel(c, v))).find(Boolean) ?? versions[0] ?? null
  const targets = [...new Set(models.filter((r) => r.model_version === version).map((r) => r.target))]
  const target = targets.includes('dark_6h') ? 'dark_6h' : targets[0]
  const rows = models.filter((r) => r.model_version === version && r.target === target).sort((a, b) => a.t - b.t)
  const n = rows.reduce((a, r) => a + r.n, 0)
  const said = wmean(rows, (r) => r.mean_p)
  const actual = n ? rows.reduce((a, r) => a + r.positives, 0) / n : null
  const lift = metrics.lift.find((l) => l.target === target) ?? metrics.lift[0]
  const x = lift && lift.all_hit_rate > 0 ? lift.top_hit_rate / lift.all_hit_rate : null
  const within = target ? `within ${target.replace(/^dark_(\d+)h$/, '$1 h')}` : ''
  return {
    mode, version, n,
    tiles: [
      {
        title: 'Flagged ships go dark', value: x == null ? '–' : `${x.toFixed(1)}× more often`,
        caption: lift ? `Top ${pct(lift.top_share)} by risk: ${pct1(lift.top_hit_rate)} went dark · all ships: ${pct1(lift.all_hit_rate)}` : 'No graded predictions yet',
        level: x == null ? 'none' : x >= 2 ? 'ok' : x > 1.2 ? 'warn' : 'bad',
      },
      {
        title: `Says vs actual, dark ${within}`, value: `${pct1(said)} → ${pct1(actual)}`, caption: 'average risk it gave · share that went dark',
        level: ratioLevel(said, actual), gauge: said == null || actual == null ? undefined : { value: actual, target: said, max: Math.min(1, Math.max(said, actual) * 1.5) },
      },
    ],
    trend: { kind: 'share', label: 'went dark', refLabel: 'risk it gave', points: rows.map((r) => ({ t: r.t, y: r.n ? r.positives / r.n : null, ref: r.mean_p, n: r.n })) },
  }
}

function wmean(rows: DarkMetricRow[], v: (r: DarkMetricRow) => number | null): number | null {
  let w = 0, s = 0
  for (const r of rows) { const x = v(r); if (x == null || !Number.isFinite(x)) continue; w += r.n; s += r.n * x }
  return w > 0 ? s / w : null
}
