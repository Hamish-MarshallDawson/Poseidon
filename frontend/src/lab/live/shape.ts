// Data shaping for "Live track record" and "Data collected" (pure; tested in shape.test.ts).
import type { DarkRow, HoldoutRow, Mode, OutcomeRow, RouteRow, SourceRow } from './types'

export const BASELINE_PREFIX = 'baseline'
export const isBaseline = (v: string) => v.startsWith(BASELINE_PREFIX)
const modeOf = (r: { mode?: string }): Mode => (r.mode === 'backtest' ? 'backtest' : 'live')

/** Modes present, live first. */
export function modesIn(rows: { mode?: string }[]): Mode[] {
  const s = new Set(rows.map(modeOf))
  return (['live', 'backtest'] as Mode[]).filter((m) => s.has(m))
}

/** Horizons present, ascending. */
export const horizonsIn = (rows: RouteRow[]) => [...new Set(rows.map((r) => r.horizon_s))].sort((a, b) => a - b)

/** Model versions, models first (alphabetical), baselines last. */
export function versionsIn(rows: { model_version: string }[]): string[] {
  return [...new Set(rows.map((r) => r.model_version))].sort((a, b) => Number(isBaseline(a)) - Number(isBaseline(b)) || a.localeCompare(b))
}

export interface RoutePoint { t: number; n: number; cov80: number | null; cov95: number | null; err: number | null; base: number | null }
export interface RoutePooled { version: string; n: number; cov80: number | null; cov95: number | null; err: number | null; base: number | null; skill: number | null }
export interface RouteView { versions: string[]; series: { version: string; points: RoutePoint[] }[]; pooled: RoutePooled[] }

/** n-weighted mean of a field over rows where it is present. */
function wmean<T>(rows: T[], n: (r: T) => number, v: (r: T) => number | null): number | null {
  let w = 0, s = 0
  for (const r of rows) { const x = v(r); if (x == null || !Number.isFinite(x)) continue; w += n(r); s += n(r) * x }
  return w > 0 ? s / w : null
}

/** Route rows for one horizon and mode: an hourly series per model version, and the window pooled (n-weighted). */
export function routeView(rows: RouteRow[], horizon: number, mode: Mode): RouteView {
  const sel = rows.filter((r) => r.horizon_s === horizon && modeOf(r) === mode && r.n > 0)
  const versions = versionsIn(sel)
  const series = versions.map((version) => ({
    version,
    points: sel.filter((r) => r.model_version === version).sort((a, b) => a.t - b.t)
      .map((r) => ({ t: r.t, n: r.n, cov80: r.cov80, cov95: r.cov95, err: r.median_err_m, base: r.baseline_median_err_m })),
  }))
  const pooled = series.map(({ version, points }) => {
    const err = wmean(points, (p) => p.n, (p) => p.err)
    const base = wmean(points, (p) => p.n, (p) => p.base)
    return {
      version, n: points.reduce((a, p) => a + p.n, 0),
      cov80: wmean(points, (p) => p.n, (p) => p.cov80), cov95: wmean(points, (p) => p.n, (p) => p.cov95),
      err, base, skill: err != null && base ? 1 - err / base : null,
    }
  })
  return { versions, series, pooled }
}

/** The version the headline sentence speaks for: the first running champion with data, else the model with most graded predictions. */
export function headline(pooled: RoutePooled[], champions: string[]): RoutePooled | undefined {
  const models = pooled.filter((p) => !isBaseline(p.version) && p.n > 0)
  return champions.map((c) => models.find((p) => p.version === c)).find(Boolean) ?? [...models].sort((a, b) => b.n - a.n)[0]
}

export interface DarkSeries { key: string; target: string; version: string; points: { t: number; n: number; positives: number; brier_skill: number }[] }

/** Brier skill over time per (target, model version) for one mode; baselines are dropped (their skill is 0 by construction). */
export function darkSeries(rows: DarkRow[], mode: Mode): DarkSeries[] {
  const sel = rows.filter((r) => modeOf(r) === mode && !isBaseline(r.model_version) && r.brier_skill != null && r.n > 0)
  const keys = [...new Set(sel.map((r) => `${r.target} · ${r.model_version}`))].sort()
  return keys.map((key) => {
    const pts = sel.filter((r) => `${r.target} · ${r.model_version}` === key).sort((a, b) => a.t - b.t)
    return { key, target: pts[0].target, version: pts[0].model_version, points: pts.map((r) => ({ t: r.t, n: r.n, positives: r.positives, brier_skill: r.brier_skill as number })) }
  })
}

/** Pooled Brier skill (n-weighted) per series. */
export const pooledBrierSkill = (s: DarkSeries) => wmean(s.points, (p) => p.n, (p) => p.brier_skill)

/** Cumulative graded outcomes per mode, recomputed from the hourly counts (the API's own cumulative is per row). */
export function outcomeSeries(rows: OutcomeRow[]): { mode: string; points: { t: number; n: number; cumulative: number }[] }[] {
  const modes = [...new Set(rows.map((r) => r.mode))].sort()
  return modes.map((mode) => {
    let c = 0
    const points = rows.filter((r) => r.mode === mode).sort((a, b) => a.t - b.t).map((r) => ({ t: r.t, n: r.n, cumulative: (c += r.n) }))
    return { mode, points }
  })
}

/** Sources with known history bounds, deepest history first. */
export const sourceSpans = (rows: SourceRow[]) =>
  rows.filter((r): r is SourceRow & { oldest: number; newest: number } => r.oldest != null && r.newest != null)
    .sort((a, b) => a.oldest - b.oldest)

/** Held-out sets, one per (target, name, hash). */
export function uniqueHoldouts(rows: HoldoutRow[]): HoldoutRow[] {
  const seen = new Set<string>()
  return rows.filter((h) => { const k = `${h.target}|${h.name}|${h.hash}`; return !seen.has(k) && !!seen.add(k) })
}

// Plain-words formatting.
export const pct = (x: number | null | undefined, d = 0) => (x == null ? '–' : `${(x * 100).toFixed(d)}%`)
export const km = (m: number | null | undefined) => (m == null ? '–' : m >= 10_000 ? `${Math.round(m / 1000)} km` : `${(m / 1000).toFixed(1)} km`)
export const hLabel = (s: number) => (s % 3600 === 0 ? `${s / 3600} h` : `${Math.round(s / 60)} min`)
export const count = (n: number) => (n >= 1e6 ? `${(n / 1e6).toFixed(1)} M` : n >= 1e4 ? `${Math.round(n / 1000)} k` : n.toLocaleString('en-GB'))
export const signedPct = (x: number | null | undefined) => (x == null ? '–' : `${x >= 0 ? '+' : '−'}${Math.abs(x * 100).toFixed(1)}%`)

/** SVG path through screen points. */
export const path = (pts: [number, number][]) => pts.map(([a, b], i) => `${i ? 'L' : 'M'}${a.toFixed(1)},${b.toFixed(1)}`).join('')
