import { describe, expect, it } from 'vitest'
import { championSteps, configDiff, decisionWhy, liveSkill, markers, modelKey, recalLog, type EventLike, type ModelSummaryLike, type RunLike } from './shape'

const H = 3_600_000
const route: ModelSummaryLike = {
  target: 'route',
  champion: { run_id: null, version: 'route-dma90-v2-cal1', since: 100 * H },
  offline: { primary_h: 10800, skill: 0.624, skill_lo: null, skill_hi: null },
}
const fishing: ModelSummaryLike = {
  target: 'fishing',
  champion: { run_id: 'f1', version: 'f1', since: 10 * H },
  offline: { primary_h: 604800, skill: 0.289, skill_lo: 0.264, skill_hi: 0.313 },
}
const skill = (s: number, lo: number, hi: number) => ({ '604800': { n: 4683, skill: s, skill_lo: lo, skill_hi: hi } })
const runs: RunLike[] = [
  { run_id: 'f1', target: 'fishing', model: 'lgbm', status: 'champion', created_at: 10 * H, config: { model: 'lgbm', seed: 7, leaves: 31 },
    metrics: { skill: skill(0.289, 0.264, 0.313), decision: { promote: true, against: 'baseline', horizons: { '604800': { win: true } } } } },
  { run_id: 'f2', target: 'fishing', model: 'persistence', status: 'rejected', parent_run: 'f1', created_at: 11 * H, config: { model: 'persistence', seed: 7 },
    metrics: { skill: skill(0.134, 0.111, 0.158), decision: { promote: false, against: 'champion f1', horizons: { '604800': { win: false } } } } },
  { run_id: 'g1', target: 'godark_gfw', status: 'rejected', created_at: 5 * H, config: { model: 'lgbm' }, metrics: null },
]
const events: EventLike[] = [
  { ts: 90 * H, target: 'route', kind: 'deployed', run_id: null, version: 'route-dma90-v2', label: 'route champion live', detail: { skill_1h: 0.365 } },
  { ts: 100 * H, target: 'route', kind: 'recalibrated', run_id: null, version: 'route-dma90-v2-cal1', label: 'circles x1.6',
    detail: { k80: { '3600': 1.642, '10800': 1.609 }, cov80_before: 0.6, cov80_after: 0.8, kept: true } },
  { ts: 10 * H, target: 'fishing', kind: 'trained', run_id: 'f1', version: 'f1', label: 'trained', detail: {} },
  { ts: 10 * H + 1, target: 'fishing', kind: 'promoted', run_id: 'f1', version: 'f1', label: 'promoted over the baseline', detail: {} },
  { ts: 100 * H, target: 'godark', kind: 'recalibrated', run_id: null, version: 'gd-cal1', label: 'dark_6h kept',
    detail: { kept: { dark_6h: -0.792 }, rejected: { dark_1h: 'newer-half log loss 0.081 -> 0.085' } } },
]

describe('modelKey', () => {
  it('folds registry targets into the three models', () => {
    expect(['route', 'godark', 'godark_gfw', 'fishing', 'other'].map(modelKey)).toEqual(['route', 'godark', 'godark', 'fishing', null])
  })
})

describe('championSteps', () => {
  it('route: the deployed champion takes its skill from the summary; recalibration keeps the value', () => {
    const s = championSteps(route, runs, events)
    expect(s.map((x) => [x.t, x.how, x.version, x.value])).toEqual([
      [90 * H, 'deployed', 'route-dma90-v2', 0.624],
      [100 * H, 'recalibrated', 'route-dma90-v2-cal1', 0.624],
    ])
  })
  it('fishing: promotion takes skill and interval from the run record', () => {
    expect(championSteps(fishing, runs, events)).toEqual([{ t: 10 * H + 1, value: 0.289, lo: 0.264, hi: 0.313, version: 'f1', run_id: 'f1', how: 'promoted' }])
  })
  it('adds the current champion when no event names it', () => {
    const s = championSteps(route, [], [])
    expect(s).toEqual([{ t: 100 * H, value: 0.624, lo: null, hi: null, version: 'route-dma90-v2-cal1', run_id: null, how: 'current' }])
  })
  it('uses the event skill_<h>h detail for an older champion', () => {
    const old = { ts: 50 * H, target: 'route', kind: 'deployed', run_id: null, version: 'route-dma14-v1', detail: { skill_3h: 0.41 } }
    expect(championSteps(route, [], [old, ...events])[0]).toMatchObject({ version: 'route-dma14-v1', value: 0.41 })
  })
})

describe('liveSkill', () => {
  it("keeps only the champion's own version (and its -calN base), drops baselines, splits live and backtest", () => {
    const m = { route: [
      // the -cal1 champion predicts under its base version's name
      { t: 1, mode: 'live', model_version: 'route-dma90-v2', horizon_s: 10800, n: 10, skill: 0.2 },
      { t: 1, mode: 'live', model_version: 'dma14-v2', horizon_s: 10800, n: 30, skill: 0.1 },
      { t: 1, mode: 'live', model_version: 'baseline-dr-v1', horizon_s: 10800, n: 99, skill: 0 },
      { t: 1, mode: 'live', model_version: 'route-dma90-v2', horizon_s: 3600, n: 99, skill: 0.9 },
      { t: 2, mode: 'backtest', model_version: 'route-dma90-v2', horizon_s: 10800, n: 5, skill: -0.2 },
    ] }
    const s = liveSkill(route, m)
    expect(s.live).toEqual([{ t: 1, value: 0.2, n: 10 }])
    expect(s.backtest).toEqual([{ t: 2, value: -0.2, n: 5 }])
    expect(s.name).toBe('skill over dead reckoning at 3 h')
  })
  it('godark reads brier_skill for dark_<h>h; fishing has none', () => {
    const gd = { ...route, target: 'godark', champion: { run_id: 'g', version: 'g' }, offline: { ...route.offline, primary_h: 21600 } }
    const m = { godark: [{ t: 3, mode: 'live', target: 'dark_6h', model_version: 'g', n: 4, brier_skill: -0.05 }, { t: 3, mode: 'live', target: 'dark_1h', model_version: 'g', n: 4, brier_skill: 0.5 }] }
    expect(liveSkill(gd, m).live).toEqual([{ t: 3, value: -0.05, n: 4 }])
    expect(liveSkill(fishing, m)).toMatchObject({ live: [], backtest: [] })
  })
})

describe('markers', () => {
  it('promoted with why, rejected from run status with the config change and the failed horizon', () => {
    const m = markers(fishing, runs, events)
    expect(m.map((x) => x.kind)).toEqual(['promoted', 'rejected'])
    expect(m[0].why).toBe('beat the baseline at 7 d')
    expect(m[1]).toMatchObject({ run_id: 'f2', changed: 'leaves: 31 → none; model: lgbm → persistence', why: 'did not beat the champion at 7 d' })
  })
  it('godark includes godark_gfw runs and Gemini proposals', () => {
    const gd = { ...route, target: 'godark' }
    const m = markers(gd, runs, events, [{ id: 'p1', target: 'godark', created_at: 1, proposer: 'gemini', rationale: 'more trees', valid: false, errors: ['bad key'] }])
    expect(m.map((x) => [x.kind, x.target])).toEqual([['proposal', 'godark'], ['rejected', 'godark_gfw'], ['recalibrated', 'godark']])
    expect(m[0]).toMatchObject({ changed: 'more trees', why: 'invalid: bad key' })
  })
})

describe('configDiff / decisionWhy', () => {
  it('lists every differing key, parent first', () => {
    expect(configDiff(runs[1], runs[0])).toEqual(['leaves: 31 → none', 'model: lgbm → persistence'])
    expect(configDiff(runs[0], undefined)).toEqual(['leaves: none → 31', 'model: none → lgbm', 'seed: none → 7'])
  })
  it('falls back to the first reason', () => {
    expect(decisionWhy({ ...runs[1], metrics: { decision: { promote: false, reasons: ['seed 2 failed'] } } })).toBe('seed 2 failed')
    expect(decisionWhy(runs[2])).toBeNull()
  })
})

describe('recalLog', () => {
  it('route: circle factors per horizon with coverage before and after', () => {
    const [, r] = recalLog(events).sort((a, b) => a.target.localeCompare(b.target))
    expect(r.target).toBe('route')
    expect(r.factors).toEqual([
      { name: '80% circle at 1 h', value: '×1.64', kept: true, why: null },
      { name: '80% circle at 3 h', value: '×1.61', kept: true, why: null },
    ])
    expect([r.before, r.after, r.kept]).toEqual(['80% circle held 60% (target 80%)', '80% circle held 80% (target 80%)', true])
  })
  it('godark: kept shifts and rejected targets with the reason', () => {
    const g = recalLog(events).find((x) => x.target === 'godark')!
    expect(g.factors).toEqual([
      { name: 'dark_6h', value: 'shift −0.79', kept: true, why: null },
      { name: 'dark_1h', value: 'not applied', kept: false, why: 'newer-half log loss 0.081 -> 0.085' },
    ])
    expect(g.kept).toBe(true)
  })
})

describe('on the shared fixtures', async () => {
  const fx = (await import('../fixtures.json')).default as unknown as {
    summary: { models: ModelSummaryLike[] }; runs: RunLike[]; events: EventLike[]; metrics: Parameters<typeof liveSkill>[1]; proposals: Parameters<typeof markers>[3]
  }
  it('every model has a current champion step and markers sorted in time', () => {
    for (const m of fx.summary.models) {
      const s = championSteps(m, fx.runs, fx.events)
      expect(s[s.length - 1].version).toBe(m.champion.version)
      const mk = markers(m, fx.runs, fx.events, fx.proposals)
      expect(mk.map((x) => x.t)).toEqual([...mk.map((x) => x.t)].sort((a, b) => a - b))
    }
  })
  it('route has a live series at 3 h and the recalibration is kept', () => {
    const route = fx.summary.models.find((m) => m.target === 'route')!
    expect(liveSkill(route, fx.metrics).live.length).toBeGreaterThan(0)
    expect(recalLog(fx.events).find((r) => r.target === 'route')?.kept).toBe(true)
  })
})
