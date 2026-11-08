import { describe, expect, it } from 'vitest'
import {
  ALL, calibrationOk, changeLine, configDiff, decisionLine, filterRuns, fmtPct, horizonLabel, primarySkill, skillRows, weakestStrata, type RunRecord,
} from './shape'

const run = (over: Partial<RunRecord> & { run_id: string }): RunRecord => ({
  target: 'fishing', model: 'lgbm', config: { model: 'lgbm', seed: 7, num_leaves: 15 }, train_from: 0, train_to: 1,
  proposer: 'human', parent_run: null, status: 'candidate', created_at: 0, metrics: null, ...over,
})

const champ = run({ run_id: 'c', status: 'champion', created_at: 2 })

describe('horizonLabel', () => {
  it('writes hours, and whole days from 48 h', () => {
    expect(horizonLabel(10800)).toBe('3\u00a0h')
    expect(horizonLabel('604800')).toBe('7\u00a0d')
    expect(horizonLabel(1800)).toBe('30\u00a0min')
    expect(horizonLabel(129600)).toBe('36\u00a0h')
  })
})

describe('fmtPct', () => {
  it('signs the skill', () => {
    expect(fmtPct(0.134)).toBe('+13 %')
    expect(fmtPct(-0.057)).toBe('−6 %')
    expect(fmtPct(null)).toBe('—')
  })
})

describe('configDiff and changeLine', () => {
  it('lists changed keys, model first', () => {
    expect(configDiff({ seed: 7, model: 'persistence' }, { model: 'lgbm', seed: 7, num_leaves: 15 })).toEqual([
      { key: 'model', parent: 'lgbm', value: 'persistence' },
      { key: 'num_leaves', parent: 15, value: null },
    ])
  })
  it('says what changed against the parent in one line', () => {
    const byId = new Map([[champ.run_id, champ]])
    expect(changeLine(run({ run_id: 'a', parent_run: 'c', config: { model: 'persistence', seed: 7 } }), byId)).toBe('lgbm → persistence')
    expect(changeLine(run({ run_id: 'b', parent_run: 'c', config: { model: 'lgbm', seed: 8, num_leaves: 31 } }), byId)).toBe('num_leaves 15 → 31')
    expect(changeLine(run({ run_id: 'd', parent_run: 'c', config: { model: 'lgbm', seed: 9, num_leaves: 15 } }), byId)).toBe('same config (new data or seed)')
    expect(changeLine(run({ run_id: 'e' }), byId)).toBe('first lgbm run')
    expect(changeLine(run({ run_id: 'f', parent_run: 'zz' }), byId)).toBe('parent zz not listed')
  })
})

describe('decisionLine', () => {
  const metrics = (promote: boolean, win: boolean, ok = true) => ({
    state: 'done',
    decision: {
      promote, against: 'champion fishing-1',
      horizons: { '604800': { cand: 0.4, ref: 0.33, diff: 0.07, lo: 0.06, hi: 0.08, win } },
      calibration: [{ name: 'ece', horizon_s: 604800, value: 0.02, nominal: 0, tol: 0.05, ok }],
    },
  })
  it('names the horizon the candidate lost at', () => {
    expect(decisionLine(run({ run_id: 'r', status: 'rejected', metrics: metrics(false, false) }))).toBe('rejected: did not beat the champion at 7\u00a0d')
  })
  it('names failed calibration', () => {
    expect(decisionLine(run({ run_id: 'r', status: 'rejected', metrics: metrics(false, true, false) }))).toBe('rejected: ece out of tolerance')
  })
  it('names the win', () => {
    expect(decisionLine(run({ run_id: 'r', status: 'champion', metrics: { ...metrics(true, true), decision: { ...metrics(true, true).decision, against: 'baseline' } } })))
      .toBe('promoted: beat the baseline at 7\u00a0d')
  })
  it('handles runs without a decision', () => {
    expect(decisionLine(champ)).toBe('champion (set by hand)')
    expect(decisionLine(run({ run_id: 'x', metrics: { state: 'failed' } }))).toBe('not scored (failed)')
  })
})

describe('primarySkill', () => {
  const r = run({ run_id: 'g', metrics: { skill: {
    '2592000': { n: 10, stat: 1, baseline_stat: 1, skill: 0.1, skill_lo: 0, skill_hi: 0.2 },
    '1209600': { n: 10, stat: 1, baseline_stat: 1, skill: 0.3, skill_lo: 0.2, skill_hi: 0.4 },
  } } })
  it('uses the preferred horizon when present, else the shortest', () => {
    expect(primarySkill(r, 2592000)?.skill).toBe(0.1)
    expect(primarySkill(r)?.h).toBe(1209600)
    expect(primarySkill(r, 10800)?.h).toBe(1209600)
    expect(primarySkill(run({ run_id: 'n' }))).toBeNull()
  })
})

describe('filterRuns', () => {
  it('filters and sorts newest first', () => {
    const rs = [run({ run_id: 'a', created_at: 1, status: 'rejected' }), champ, run({ run_id: 'g', target: 'godark_gfw', created_at: 3 })]
    expect(filterRuns(rs, { target: ALL, proposer: ALL, status: ALL }).map((r) => r.run_id)).toEqual(['g', 'c', 'a'])
    expect(filterRuns(rs, { target: 'fishing', proposer: 'human', status: ALL }).map((r) => r.run_id)).toEqual(['c', 'a'])
    expect(filterRuns(rs, { target: ALL, proposer: 'gemini', status: ALL })).toEqual([])
  })
})

describe('weakestStrata and calibrationOk', () => {
  it('ranks strata by excess loss, difference times cases', () => {
    const r = run({ run_id: 's', metrics: { decision: { promote: false, against: 'x', strata_worse: [
      { stratum: 'region', value: 'tiny', horizon_s: 1, n: 100, cand: 0.006, ref: 0.002 },
      { stratum: 'region', value: 'big', horizon_s: 1, n: 3000, cand: 0.48, ref: 0.40 },
      { stratum: 'region', value: 'few', horizon_s: 1, n: 10, cand: 3, ref: 1 },
    ] } } })
    expect(weakestStrata(r).map((s) => s.value)).toEqual(['big', 'few', 'tiny'])
    expect(weakestStrata(r)[0].diff).toBeCloseTo(0.08)
  })
  it('derives ok from tolerance when not stored', () => {
    expect(calibrationOk({ name: 'ece', horizon_s: 1, value: 0.02, nominal: 0, tol: 0.05 })).toBe(true)
    expect(calibrationOk({ name: 'cov80', horizon_s: 1, value: 0.6, nominal: 0.8, tol: 0.05 })).toBe(false)
    expect(calibrationOk({ name: 'cov80', horizon_s: 1, value: 0.6, nominal: 0.8, tol: 0.05, ok: true })).toBe(true)
    expect(calibrationOk({ name: 'x', horizon_s: 1, value: null, nominal: 0.8 })).toBeNull()
  })
})

describe('skillRows', () => {
  const sk = (v: number) => ({ n: 1, stat: 1, baseline_stat: 1, skill: v, skill_lo: v - 0.1, skill_hi: v + 0.1 })
  it('pairs the run with the champion per horizon, flagging a different holdout', () => {
    const r = run({ run_id: 'r', metrics: { holdout: { hash: 'a' }, skill: { '604800': sk(0.1) } } })
    const c = run({ run_id: 'c', metrics: { holdout: { hash: 'b' }, skill: { '604800': sk(0.3) } } })
    expect(skillRows(r, c).map((x) => [x.key, x.v, x.sameHoldout])).toEqual([['7 d · this run', 0.1, true], ['7 d · champion', 0.3, false]])
    expect(skillRows(r).length).toBe(1)
  })
})
