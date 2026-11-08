// The lab-fix-backend fields, wired on real /lab/* output (testdata/real-20261108.json, taken after that change):
// offline.statistic, live.statistic / horizon_s / offline, live null, decision_summary, counted_from, truncated and
// graded_outcomes_estimated.
import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import real from './testdata/real-20261108.json'
import { ModelCard, Overview } from './Overview'
import { Improve } from './improve/Improve'
import { DataCollected } from './live/DataCollected'
import { liveComparison, liveHorizon, liveStatistic, recordedOffline } from './skill'
import { decisionHeadline, type RunRecord } from './runs/shape'
import type { LabData, LabEvent, Metrics, ModelSummary, Run, RunDetail, Summary } from './types'

const summary = real.summary as unknown as Summary
const runs = real.runs as unknown as Run[]
const model = (t: string) => summary.models.find((m) => m.target === t)!
const html = (el: React.ReactElement) => renderToStaticMarkup(el)

describe('offline.statistic and the live comparison fields', () => {
  it('labels the recorded held-out number with offline.statistic', () => {
    expect(recordedOffline(model('route'), runs)?.name).toBe('median-error skill')
    expect(recordedOffline(model('godark'), runs)?.name).toBe('log-loss skill')
    expect(html(<ModelCard m={model('route')} runs={runs} />)).toContain('+62%</b> median-error skill over dead reckoning at 3 h')
  })

  it('pairs live with live.offline: same statistic, same horizon', () => {
    const gd = model('godark')
    expect([liveStatistic(gd, runs), liveHorizon(gd)]).toEqual(['Brier skill', 3600])
    const c = liveComparison(gd, runs)!
    expect(c.offline).toMatchObject({ name: 'Brier skill', h: 3600, skill: gd.live!.offline!.skill })
    expect(c.live).toMatchObject({ name: 'Brier skill', h: 3600, skill: gd.live!.primary.value })
  })

  it('live.offline null (or on another statistic) pairs nothing, and the strip says so', () => {
    const gd = model('godark')
    const none = { ...gd, live: { ...gd.live!, offline: null } }
    expect(liveComparison(none, runs)?.offline).toBeNull()
    const other = { ...gd, live: { ...gd.live!, offline: { ...gd.live!.offline!, statistic: 'log-loss skill' } } }
    expect(liveComparison(other, runs)?.offline).toBeNull()
    const out = html(<ModelCard m={none} runs={runs} />)
    expect(out).not.toContain('held-out test, 1 h')
    expect(out).toContain('No held-out Brier skill at 1 h recorded for this run, so nothing to compare against.')
  })

  it('live null on a deployed model: "No live grades for this version yet."', () => {
    const m: ModelSummary = { ...model('route'), champion: { ...model('route').champion, version: 'route-dma90-v2-cal1' }, live: null }
    expect(liveComparison(m, runs)).toBeNull()
    expect(html(<ModelCard m={m} runs={runs} />)).toContain('No live grades for this version yet.')
    const page = html(<Improve summary={{ ...summary, models: [m] }} runs={runs} events={real.events as unknown as LabEvent[]} metrics={real.metrics as unknown as Metrics} />)
    expect(page).toContain('No live grades for this version yet.')
    expect(html(<ModelCard m={model('fishing')} runs={runs} />)).toContain('Not graded live.')
  })

  it('the Improve note compares live with live.offline only', () => {
    const page = html(<Improve summary={summary} runs={runs} events={real.events as unknown as LabEvent[]} metrics={real.metrics as unknown as Metrics} />)
    expect(page).toContain('Live median-error skill at 3 h (+36%) is below the held-out median-error skill at the same horizon (+62%)')
  })
})

describe('decision_summary', () => {
  it('leads the run detail, with the stored decision in words under it', () => {
    const d = real.run_detail['route-dma90-v2'] as unknown as RunDetail
    const run = runs.find((r) => r.run_id === 'route-dma90-v2') as unknown as RunRecord
    expect(decisionHeadline(run, d)).toEqual({
      main: 'promoted by hand over route-dma14-v3; no paired test was run',
      sub: expect.stringMatching(/^promoted by hand: higher skill than route-dma14-v3/),
    })
    expect(decisionHeadline(run, { decision_summary: null }).main).toMatch(/^promoted by hand: /)
  })
})

describe('/lab/data counted_from and truncated, totals estimated', () => {
  const data = real.data as unknown as LabData

  it('says since counted_from on the cumulative chart', () => {
    expect(data.counted_from).toBe(1790931600000)
    const out = html(<DataCollected data={data} />)
    expect(out).toContain('since Fri 2 Oct 09:00Z') // 1790931600000 = 2026-10-02 09:00 UTC
    expect(out).toContain('cumulative since')
    expect(out).not.toContain('At least')
  })

  it('a truncated window gives the total as a lower bound', () => {
    expect(html(<DataCollected data={{ ...data, truncated: true }} />)).toContain('At least <b>')
  })

  it('an estimated total is marked with ~', () => {
    expect(html(<Overview summary={summary} runs={runs} />)).not.toContain('~')
    const est = { ...summary, totals: { ...summary.totals, graded_outcomes_estimated: true } }
    expect(html(<Overview summary={est} runs={runs} />)).toContain('~122,093')
  })
})
