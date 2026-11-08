// The Champions & challengers tab on real /lab/* output (testdata/real-20261108.json) plus a synthetic Gemini round.
import { describe, expect, it } from 'vitest'
import { renderToStaticMarkup } from 'react-dom/server'
import real from '../testdata/real-20261108.json'
import type { RunRecord } from '../runs/shape'
import type { Proposal, Run } from '../types'
import { ChampionsTab } from './ChampionsTab'
import { championLine, changePhrase, decisionSentence, latestDecided, measureFor, outcomePhrase, proposalRows, timelinePoints } from './shape'

const runs = real.runs as unknown as RunRecord[]
const byId = new Map(runs.map((r) => [r.run_id, r]))
const noDetail = async () => null
const M = (target: 'route' | 'godark' | 'fishing') => ({ target, name: target, question: '?', summary: null })
const BANNED = /skill|brier|log loss|dead reckoning|isotonic/i

const parent = runs.find((r) => r.run_id === 'godark-lgbm-20261108T051156')!
const gem: RunRecord = {
  ...parent, run_id: 'godark-gem-1', proposer: 'gemini', parent_run: parent.run_id, status: 'rejected', created_at: parent.created_at + 3_600_000,
  config: { ...(parent.config ?? {}), num_leaves: 15 },
  metrics: { ...parent.metrics!, decision: { promote: false, against: parent.run_id, by: 'rule', horizons: { '3600': { cand: 1, ref: 1, diff: 0, lo: -1, hi: 1, win: false } } } },
}
const gemParent: RunRecord = { ...parent, config: { ...(parent.config ?? {}), num_leaves: 31 } }
const gemIds = new Map([...byId, [parent.run_id, gemParent], [gem.run_id, gem]])
const prop = (o: Partial<Proposal>): Proposal => ({ id: 'p', target: 'godark', loop_id: null, round: 1, proposer: 'gemini', created_at: gem.created_at, proposal: { num_leaves: 15 }, valid: true, errors: [], rationale: 'Fewer leaves may generalise better.', source: null, run_id: gem.run_id, outcome: 'rejected', ...o })

describe('timeline', () => {
  it('route is drawn in km at 3 h, lower better; champions joined in time order to now', () => {
    const pts = timelinePoints(runs, 'route')
    expect(pts.map((p) => p.run.run_id)).toEqual(['route-dma14-v1', 'route-dma14-v2', 'route-dma14-v3', 'route-dma90-v2'])
    expect(pts.every((p) => p.y != null && p.y > 100)).toBe(true)
    expect(measureFor('route').lowerBetter).toBe(true)
    const line = championLine(pts, pts[3].x + 1000)
    expect(line).toHaveLength(4) // v1, v3, v2 (dma90), extended to now
    expect(line[3].y).toBe(line[2].y)
  })
  it('go-dark is drawn as improvement over a simple guess', () => {
    const pts = timelinePoints(runs, 'godark')
    expect(pts).toHaveLength(2)
    expect(measureFor('godark').fmt(0.12)).toBe('12%')
  })
})

describe('the latest decision in one plain sentence', () => {
  it('a Gemini rejection names the change and why', () => {
    const s = decisionSentence(gem, gemIds)
    expect(s).toMatch(/^Gemini proposed fewer leaves \(31 → 15\): rejected, not better than the champion at 1 h\.$/)
    expect(s).not.toMatch(BANNED)
  })
  it('real hand decisions never say dead reckoning', () => {
    for (const r of runs) expect(outcomePhrase(r)).not.toMatch(/dead reckoning/i)
    expect(latestDecided(runs, 'fishing')!.run_id).toBe('fishing-20261108T071925-e2db5c'.replace('e2db5c', 'be7ea1'))
    expect(changePhrase(runs.find((r) => !r.parent_run)!, byId)).toMatch(/^a first/)
  })
})

describe('proposals', () => {
  it('valid, invalid and duplicate each carry a reason', () => {
    const rows = proposalRows([
      prop({}),
      prop({ id: 'i', valid: false, outcome: 'invalid', errors: ['num_leaves must be ≥ 4'], run_id: null }),
      prop({ id: 'd', outcome: 'duplicate', run_id: null, created_at: 0 }),
    ], 'godark')
    expect(rows.map((r) => r.kind)).toEqual(['valid', 'invalid', 'duplicate'])
    expect(rows[1].reason).toBe('num_leaves must be ≥ 4')
    expect(rows[2].reason).toMatch(/already tried/)
  })
})

describe('ChampionsTab renders on real data', () => {
  it('shows the decision card, the timeline and an honest empty proposals list', () => {
    for (const t of ['route', 'godark', 'fishing']) {
      const html = renderToStaticMarkup(<ChampionsTab model={M(t as 'route')} runs={real.runs as unknown as Run[]} proposals={[]} events={[]} loadDetail={noDetail} now={real.summary.generated_at} />)
      expect(html).toContain('Latest decision')
      expect(html).toContain('No proposals yet')
      expect(html.replace(/<[^>]+>/g, ' ')).not.toMatch(/dead reckoning|log loss|brier/i)
    }
  })
  it('badges Gemini runs and proposals, and is honest when empty', () => {
    const html = renderToStaticMarkup(<ChampionsTab model={M('godark')} runs={[...real.runs, gem] as unknown as Run[]} proposals={[prop({})]} events={[]} loadDetail={noDetail} />)
    expect(html).toContain('lc-gemini')
    expect(html).toContain('Fewer leaves may generalise better.')
    expect(renderToStaticMarkup(<ChampionsTab model={M('route')} runs={[]} proposals={[]} events={[]} loadDetail={noDetail} />)).toContain('No training runs')
  })
})
