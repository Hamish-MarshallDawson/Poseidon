import { describe, expect, it } from 'vitest'
import { darkSeries, headline, horizonsIn, km, modesIn, outcomeSeries, pooledBrierSkill, routeView, sourceSpans, uniqueHoldouts, versionsIn } from './shape'
import type { DarkMetricRow as DarkRow, RouteMetricRow as RouteRow } from '../types'

const r = (o: Partial<RouteRow>): RouteRow => ({ t: 0, mode: 'live', model_version: 'm', horizon_s: 3600, n: 1, cov80: null, cov95: null, median_err_m: null, baseline_median_err_m: null, skill: null, ...o })

describe('route shaping', () => {
  const rows = [
    r({ t: 2, model_version: 'dma', n: 30, cov80: 0.9, cov95: 1, median_err_m: 1000, baseline_median_err_m: 2000 }),
    r({ t: 1, model_version: 'dma', n: 10, cov80: 0.5, cov95: 0.8, median_err_m: 2000, baseline_median_err_m: 2000 }),
    r({ t: 1, model_version: 'baseline-dr-v1', n: 10, cov80: 0.7 }),
    r({ t: 1, model_version: 'dma', horizon_s: 21600, n: 5 }),
    r({ t: 1, model_version: 'dma', mode: 'backtest', n: 99, cov80: 0 }),
    r({ t: 3, model_version: 'dma', n: 0, cov80: 0 }),
  ]
  it('lists modes live first, horizons ascending, baselines last', () => {
    expect(modesIn([{ mode: 'backtest' }, { mode: 'live' }, {}])).toEqual(['live', 'backtest'])
    expect(horizonsIn(rows)).toEqual([3600, 21600])
    expect(versionsIn([{ model_version: 'baseline-dr-v1' }, { model_version: 'z' }, { model_version: 'a' }])).toEqual(['a', 'z', 'baseline-dr-v1'])
  })
  it('keeps one horizon and mode, sorts by time, drops empty buckets and pools by n', () => {
    const v = routeView(rows, 3600, 'live')
    expect(v.versions).toEqual(['dma', 'baseline-dr-v1'])
    expect(v.series[0].points.map((p) => p.t)).toEqual([1, 2])
    const dma = v.pooled[0]
    expect(dma.n).toBe(40)
    expect(dma.cov80).toBeCloseTo((0.5 * 10 + 0.9 * 30) / 40)
    expect(dma.err).toBeCloseTo(1250)
    expect(dma.skill).toBeCloseTo(1 - 1250 / 2000)
    expect(v.pooled[1].err).toBeNull()
    expect(v.pooled[1].skill).toBeNull()
  })
  it('speaks for the running champion, else the model with most graded predictions, never a baseline', () => {
    const p = (version: string, n: number) => ({ version, n, cov80: null, cov95: null, err: null, base: null, skill: null })
    const pooled = [p('a', 5), p('b', 50), p('baseline-dr-v1', 500), p('c', 0)]
    expect(headline(pooled, ['c', 'a'])?.version).toBe('a')
    expect(headline(pooled, [])?.version).toBe('b')
    expect(headline([p('baseline-dr-v1', 9)], [])).toBeUndefined()
  })
})

describe('go-dark shaping', () => {
  const d = (o: Partial<DarkRow>): DarkRow => ({ t: 0, mode: 'live', target: 'dark_1h', model_version: 'lgbm', n: 10, positives: 1, mean_p: 0.1, hit_rate: 0.1, brier: 0.1, brier_skill: 0.1, ...o })
  it('drops baselines and null skill, groups by target and version, pools by n', () => {
    const s = darkSeries([d({ t: 2, brier_skill: 0.3, n: 30 }), d({ t: 1, brier_skill: -0.1 }), d({ model_version: 'baseline-rate-v1' }), d({ brier_skill: null }), d({ mode: 'backtest' })], 'live')
    expect(s).toHaveLength(1)
    expect(s[0].points.map((p) => p.t)).toEqual([1, 2])
    expect(pooledBrierSkill(s[0])).toBeCloseTo((0.3 * 30 - 0.1 * 10) / 40)
  })
})

describe('data shaping', () => {
  it('recomputes cumulative outcomes per mode in time order', () => {
    const s = outcomeSeries([{ t: 2, mode: 'live', n: 5, cumulative: 0 }, { t: 1, mode: 'live', n: 3, cumulative: 0 }, { t: 1, mode: 'backtest', n: 7, cumulative: 7 }])
    expect(s.map((x) => x.mode)).toEqual(['backtest', 'live'])
    expect(s[1].points.map((p) => p.cumulative)).toEqual([3, 8])
  })
  it('keeps sources with bounds, deepest first, and dedupes held-out sets', () => {
    const src = (oldest: number | null, label: string) => ({ src: 's', stream: 'x', label, oldest, newest: 9, windows: 1, rows: 1 })
    expect(sourceSpans([src(5, 'b'), src(null, 'none'), src(1, 'a')]).map((s) => s.label)).toEqual(['a', 'b'])
    const h = { target: 'fishing', name: 'v1', n: 1, start: 0, end: 1, hash: 'x' }
    expect(uniqueHoldouts([h, { ...h }, { ...h, hash: 'y' }])).toHaveLength(2)
  })
  it('formats distances in plain km', () => {
    expect(km(4244)).toBe('4.2 km')
    expect(km(26732)).toBe('27 km')
    expect(km(null)).toBe('–')
  })
})
