// The PR 179 defect review's fixes (docs/handoffs/lab-review-frontend.md), checked on real /lab/* output from the
// local API (testdata/real-20261108.json: /lab/summary, /lab/runs, /lab/metrics, /lab/events, two /lab/runs/<id>).
import { describe, expect, it, vi } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import real from './testdata/real-20261108.json'
import { againstBaseline, byHandLine } from './decision'
import { decisionLine, currentRun, fmtCalCheck, calibrationChecks, type RunRecord } from './runs/shape'
import { championSteps, decisionWhy, liveSkill, markers, type EventLike, type MetricsLike, type ModelSummaryLike, type RunLike } from './improve/shape'
import { liveHorizon, offlineSkill, recordedOffline } from './skill'
import { ModelCard } from './Overview'
import { LabBoundary } from './LabEntry'
import { fixtures } from './api'
import type { ModelSummary } from './types'

const runs = real.runs as unknown as RunRecord[]
const likes = real.runs as unknown as RunLike[]
const events = real.events as unknown as EventLike[]
const metrics = real.metrics as unknown as MetricsLike
const model = (t: string) => real.summary.models.find((m) => m.target === t) as unknown as ModelSummary & ModelSummaryLike
const run = (id: string) => runs.find((r) => r.run_id === id)!
const H3 = 10800

describe('1 and 2: one reading of the decision for the runs table and the Improve markers', () => {
  it('recognises baselines by name and anything else as a champion', () => {
    expect(['baseline (no champion yet)', 'global base rate', 'dead reckoning (no champion yet)', 'no champion'].map(againstBaseline)).toEqual([true, true, true, true])
    expect(['route-dma14-v3', 'route-dma14-v1', 'champion fishing-20261108T071922-e2db5c', null].map(againstBaseline)).toEqual([false, false, false, false])
  })

  it('hand promotions say "promoted by hand" with the first reason, never "beat the baseline"', () => {
    for (const id of ['route-dma90-v2', 'route-dma14-v3', 'route-dma14-v1', 'godark-lgbm-20261108T051156']) {
      const line = decisionLine(run(id))
      expect(line).toMatch(/^promoted by hand/)
      expect(line).not.toMatch(/beat the baseline/)
      expect(decisionWhy(run(id))).toBe(line)
    }
    expect(decisionLine(run('godark-lgbm-20261108T051156'))).toBe('promoted by hand to give the live predictor a go-dark model')
    expect(decisionLine(run('route-dma90-v2'))).toBe('promoted by hand: higher skill than route-dma14-v3 at every horizon (+0.03 at 1 h, +0.04 at 3 h, +0.01 at 24 h)')
    expect(decisionLine(run('route-dma14-v2'))).toBe('kept as a candidate by hand: retrained with east/north heads for the live loader, no frozen held-out set')
  })

  it('rule decisions name what they were compared with, and only the horizons actually won', () => {
    expect(decisionLine(run('fishing-20261108T071922-e2db5c'))).toBe('promoted: beat the baseline at 7 d')
    expect(decisionLine(run('fishing-20261108T071925-be7ea1'))).toBe('rejected: did not beat the champion at 7 d')
    expect(decisionWhy(run('fishing-20261108T071922-e2db5c'))).toBe('beat the baseline at 7 d')
    expect(decisionWhy(run('godark_gfw-20261108T064631-5c078d'))).toBe('did not beat the baseline at 14 d, 30 d')
  })

  it('Improve markers never claim a champion or horizon win for a hand promotion', () => {
    const why = (t: string) => markers(model(t), likes, events).filter((m) => m.kind === 'promoted').map((m) => m.why)
    expect(why('godark')).toEqual(['promoted by hand to give the live predictor a go-dark model'])
    for (const w of why('route')) {
      expect(w).toMatch(/^promoted by hand/)
      expect(w).not.toMatch(/every primary horizon/)
    }
    // route-dma14-v1's event carries a version that is not a run id; the event's own decision detail is read the same way
    expect(why('route')[0]).toBe('promoted by hand: first route model: beat dead reckoning at every horizon on 3-5 Nov')
  })

  it('byHandLine keeps a reason that already says so as it is', () => {
    expect(byHandLine({ promote: true, by: 'human', reasons: ['promoted by hand because x'] })).toBe('promoted by hand because x')
    expect(byHandLine({ promote: true, by: 'human', reasons: [] })).toBe('promoted by hand')
  })
})

describe('3: go-dark never mixes log-loss and Brier skill, or horizons', () => {
  const gd = model('godark')

  it('the comparable held-out figure is Brier skill from metrics.summary, at the asked horizon', () => {
    expect(gd.offline.skill).toBeCloseTo(0.0265, 4) // the summary's log-loss skill at 6 h
    expect(offlineSkill(gd, likes)).toMatchObject({ name: 'Brier skill', h: 21600, skill: expect.closeTo(0.01217, 5), lo: expect.closeTo(-0.01755, 5), hi: expect.closeTo(0.03894, 5) })
    expect(liveHorizon(gd)).toBe(3600)
    // without live.target (the bundled sample), the horizon comes from the figure's name
    expect(liveHorizon({ ...gd, live: { ...gd.live!, target: undefined } })).toBe(3600)
    expect(liveHorizon(model('route'))).toBe(H3)
    expect(offlineSkill(gd, likes, 3600)).toMatchObject({ name: 'Brier skill', h: 3600, skill: expect.closeTo(0.000144, 6) })
    expect(recordedOffline(gd, likes)).toMatchObject({ name: 'log-loss skill', h: 21600 })
    // a go-dark run without a stored Brier skill has no comparable figure (not the log-loss one)
    const bare = likes.map((r) => (r.run_id === gd.champion.run_id ? { ...r, metrics: { ...r.metrics, summary: null } } : r))
    expect(offlineSkill(gd, bare)).toBeNull()
  })

  it('the Improve step line is Brier skill at 6 h, the statistic and horizon of its live line', () => {
    const steps = championSteps(gd, likes, events)
    expect(steps.map((s) => s.value)).toEqual([expect.closeTo(0.01217, 5)])
    expect(liveSkill(gd, metrics).name).toBe('Brier skill over the base rate at 6 h')
  })

  it('route keeps its own skill, which live grading shares', () => {
    expect(offlineSkill(model('route'), likes)).toMatchObject({ name: 'median-error skill', h: H3, skill: expect.closeTo(0.6241, 4) })
  })

  it('the card labels the recorded held-out number with its statistic and puts 1 h live next to 1 h held-out only', () => {
    const html = renderToStaticMarkup(<ModelCard m={gd} runs={likes} />)
    expect(html).toContain('+2.6%</b> log-loss skill over the base rate at 6 h')
    expect(html).toContain('held-out test, 1 h')
    expect(html).toContain('Brier skill over the base rate at 1 h; left of 0 is worse')
  })

  it('the bundled sample data (the fallback) also pairs 1 h live with 1 h held-out', () => {
    const m = fixtures.summary.models.find((x) => x.target === 'godark')!
    const html = renderToStaticMarkup(<ModelCard m={m} runs={fixtures.runs} />)
    expect(html).not.toContain('held-out test, 6 h')
    expect(html).toMatch(/at 1 h; left of 0 is worse/)
  })
})

describe('4: the champion live line uses only the champion model_version', () => {
  it('the 3 h bucket at 1794121200000 is route-dma90-v2 alone (27.8 %), not pooled with dma14-v2 (21.9 %)', () => {
    const s = liveSkill(model('route'), metrics)
    const p = s.live.find((x) => x.t === 1794121200000)!
    expect(p.n).toBe(43)
    expect(p.value).toBeCloseTo(0.2779, 4)
    const versions = new Set((real.metrics.route as { model_version: string; horizon_s: number; mode: string; t: number; n: number }[])
      .filter((r) => r.horizon_s === H3 && r.mode === 'backtest').map((r) => r.model_version))
    expect(versions.has('dma14-v2')).toBe(true)
    const own = real.metrics.route.filter((r) => r.horizon_s === H3 && r.mode === 'backtest' && r.model_version === 'route-dma90-v2')
    expect(s.backtest.map((x) => x.n)).toEqual(own.sort((a, b) => a.t - b.t).map((r) => r.n))
  })

  it('a -calN champion is matched to rows under its base version', () => {
    const cal = { ...model('route'), champion: { ...model('route').champion, run_id: null, version: 'route-dma90-v2-cal1' }, live: null }
    expect(liveSkill(cal, metrics).live.find((x) => x.t === 1794121200000)?.value).toBeCloseTo(0.2779, 4)
  })
})

describe('5: the run selection can never crash', () => {
  it('falls back to the first shown run when the selected one left the list', () => {
    const byId = new Map(runs.map((r) => [r.run_id, r]))
    expect(currentRun('route-loop-r9-not-in-fixtures', byId, runs)).toBe(runs[0])
    expect(currentRun('route-dma14-v2', byId, runs)?.run_id).toBe('route-dma14-v2')
    expect(currentRun(null, byId, runs)).toBe(runs[0])
    expect(currentRun('x', new Map(), [])).toBeUndefined()
  })

  it('a Lab error renders the boundary fallback, with a way back to the map', () => {
    expect(LabBoundary.getDerivedStateFromError(new Error('boom'))).toEqual({ error: expect.any(Error) })
    const onClose = vi.fn()
    const b = new LabBoundary({ onClose, children: null })
    b.state = { error: new Error('boom') }
    const html = renderToStaticMarkup(b.render() as React.ReactElement)
    expect(html).toContain('The Model Lab hit an error')
    expect(html).toContain('Close the Model Lab and return to the map')
    b.state = { error: null }
    expect(b.render()).toBeNull()
  })
})

describe('polish: calibration rows', () => {
  it('route coverage in percent, ECE as a number', () => {
    const route = calibrationChecks(run('route-dma90-v2'))
    expect(fmtCalCheck(route[0])).toBe('80.5 % (target 80 % ± 5 %)')
    const gd = calibrationChecks(run('godark-lgbm-20261108T051156'))
    expect(fmtCalCheck(gd[0])).toBe('0.027 (target 0 ± 0.05)')
  })
})
