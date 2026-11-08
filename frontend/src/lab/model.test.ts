import { describe, expect, it } from 'vitest'
import { parseRoute, routeHash } from './hash'
import { godarkLive, levelFor, modelView, pipeline, routeLive } from './model'
import type { Metrics, ModelSummary, Run } from './types'

const metrics: Metrics = {
  bucket: 3600, truncated: false, reliability: [],
  route: [
    { t: 1, mode: 'live', model_version: 'route-a', horizon_s: 10800, n: 10, cov80: 0.4, cov95: 0.6, median_err_m: 20000, baseline_median_err_m: 40000, skill: 0.5 },
    { t: 2, mode: 'live', model_version: 'route-a', horizon_s: 10800, n: 30, cov80: 0.6, cov95: 0.8, median_err_m: 10000, baseline_median_err_m: 30000, skill: 0.6 },
    { t: 2, mode: 'live', model_version: 'baseline-dr', horizon_s: 10800, n: 30, cov80: 0.1, cov95: 0.2, median_err_m: 90000, baseline_median_err_m: 90000, skill: 0 },
  ],
  godark: [{ t: 1, mode: 'live', target: 'dark_6h', model_version: 'gd-a-cal1', n: 100, positives: 10, mean_p: 0.12, hit_rate: 0.1, brier: 0.08, brier_skill: 0.05 }],
  lift: [{ target: 'dark_6h', top_share: 0.1, top_hit_rate: 0.3, all_hit_rate: 0.1 }],
}
const summary = (target: string, version: string): ModelSummary => ({
  target, label: target, champion: { run_id: version, version, since: 1, proposer: 'human', source: 'server' },
  offline: { primary_h: 10800, skill: 0.6, skill_lo: 0.5, skill_hi: 0.7, holdout: null }, live: null, deployed: true, note: null,
})

describe('hash routes', () => {
  it('parses home, model and tab, and ignores unknown parts', () => {
    expect(parseRoute('#lab')).toEqual({ model: null, tab: 'overview' })
    expect(parseRoute('#lab/godark')).toEqual({ model: 'godark', tab: 'overview' })
    expect(parseRoute('#lab/route/champions')).toEqual({ model: 'route', tab: 'champions' })
    expect(parseRoute('#lab/route/nope')).toEqual({ model: 'route', tab: 'overview' })
    expect(parseRoute('#lab/ships/live')).toEqual({ model: null, tab: 'overview' })
    expect(routeHash({ model: 'fishing', tab: 'data' })).toBe('#lab/fishing/data')
    expect(routeHash({ model: 'route', tab: 'overview' })).toBe('#lab/route')
  })
})

describe('headline numbers', () => {
  it('route pools the champion rows only, n-weighted', () => {
    const r = routeLive(metrics, 'route-a')
    expect(r.n).toBe(40)
    expect(r.errM).toBeCloseTo(12500)
    expect(r.cov80).toBeCloseTo(0.55)
    const v = modelView('route', summary('route', 'route-a'), [], metrics)
    expect(v.headline.text).toBe('Finds a silent ship within 13 km after 3 hours')
    expect(v.status.level).toBe('bad')
  })
  it('go-dark lift and says/actual, matching a recalibrated champion name', () => {
    const g = godarkLive(metrics, 'gd-a-cal1')
    expect(g.lift).toBeCloseTo(3)
    expect(g.said).toBeCloseTo(0.12)
    expect(modelView('godark', summary('godark', 'gd-a-cal1'), [], metrics).status.level).toBe('ok')
  })
  it('prefers the server headline and status, and is honest with no data', () => {
    const m = { ...summary('route', 'route-a'), headline: { text: 'Server says', value: 1, unit: 'km' }, status: { level: 'warn' as const, text: 'Drifting' } }
    const v = modelView('route', m, [], metrics)
    expect(v.headline.text).toBe('Server says')
    expect(v.status).toEqual({ level: 'warn', text: 'Drifting' })
    expect(modelView('fishing', null, [], null).status.level).toBe('none')
    expect(modelView('route', summary('route', 'route-a'), [], null).status.level).toBe('none')
  })
  it('levels: on target, drifting, off target, none', () => {
    expect([levelFor(0.78, 0.8), levelFor(0.7, 0.8), levelFor(0.44, 0.8), levelFor(null, 0.8)]).toEqual(['ok', 'warn', 'bad', 'none'])
  })
})

describe('pipeline', () => {
  const run = (id: string, status: Run['status'], t: number, decided = true): Run => ({
    run_id: id, target: 'route', model: null, config: null, data_hash: null, train_from: null, train_to: t - 1, artifact: null, proposer: 'default',
    parent_run: null, status, created_at: t, loop_id: null, round: null, git_sha: null, source: null,
    metrics: decided ? ({ decision: { promote: status === 'champion' } } as Run['metrics']) : null,
  })
  it('derives counts from runs when the summary has no pipeline', () => {
    const st = Object.fromEntries(pipeline(null, [run('a', 'champion', 30), run('b', 'rejected', 20), run('c', 'candidate', 10, false)], [], [], 500).map((s) => [s.key, s]))
    expect(st.trained.n).toBe(3)
    expect(st.judged.n).toBe(2)
    expect(st.promoted.n).toBe(1)
    expect(st.rejected.n).toBe(1)
    expect(st.new_data).toEqual({ key: 'new_data', label: 'New data', n: 500, last: 29 })
  })
  it('takes summary.pipeline numbers and {n, last_ts} objects', () => {
    const m = { ...summary('route', 'a'), pipeline: { trained: 7, graded: { n: 900, last_ts: 99 }, last_ts: { trained: 55 } } }
    const st = Object.fromEntries(pipeline(m, [run('a', 'champion', 30)], [], [], null).map((s) => [s.key, s]))
    expect([st.trained.n, st.trained.last, st.graded.n, st.graded.last, st.promoted.n]).toEqual([7, 55, 900, 99, 1])
  })
})
