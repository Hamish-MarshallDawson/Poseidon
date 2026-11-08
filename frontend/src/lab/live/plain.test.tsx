import { renderToStaticMarkup } from 'react-dom/server'
import { describe, expect, it } from 'vitest'
import real from '../testdata/real-20261108.json'
import type { LabData, Metrics, Summary } from '../types'
import { DataTab } from '../data'
import { dataCounters, depthLabel } from '../data/shape'
import { LiveTab } from './LiveTab'
import { LiveTrackRecord } from './LiveTrackRecord'

const text = (el: React.ReactElement) => renderToStaticMarkup(el).replace(/<[^>]+>/g, ' ')
import { coverageLevel, livePlain, ratioLevel } from './plain'

const metrics = real.metrics as unknown as Metrics
const data = real.data as unknown as LabData
const summary = real.summary as unknown as Summary
const JARGON = /skill|brier|log loss|dead reckoning|isotonic/i

describe('status levels', () => {
  it('grades coverage and said-vs-actual', () => {
    expect(coverageLevel(0.78, 0.8)).toBe('ok')
    expect(coverageLevel(0.7, 0.8)).toBe('warn')
    expect(coverageLevel(0.44, 0.8)).toBe('bad')
    expect(coverageLevel(null, 0.8)).toBe('none')
    expect(ratioLevel(0.02, 0.025)).toBe('ok')
    expect(ratioLevel(0.04, 0.01)).toBe('bad')
    expect(ratioLevel(null, 0.01)).toBe('none')
  })
})

describe('Live tab on real /lab/metrics', () => {
  it('route: miss distance and circle coverage at 3 h, in plain words', () => {
    const p = livePlain(metrics, 'route')
    expect(p.mode).not.toBeNull()
    expect(p.tiles[0].title).toMatch(/after 3 h/)
    expect(p.tiles[0].value).toMatch(/^within [\d.]+ km$/)
    expect(p.tiles[1].value).toMatch(/^\d+%$/)
    expect(p.tiles[1].caption).toBe('of the time · target 80%')
    expect(p.trend.points.length).toBeGreaterThan(0)
    for (const t of p.tiles) expect(`${t.title} ${t.value} ${t.caption}`).not.toMatch(JARGON)
  })
  it('godark: lift and said vs actual', () => {
    const p = livePlain(metrics, summary.models.find((m) => m.target === 'godark')!)
    expect(p.tiles[0].value).toMatch(/× more often$/)
    expect(p.tiles[1].value).toMatch(/%.*→.*%/)
    for (const t of p.tiles) expect(`${t.title} ${t.value} ${t.caption}`).not.toMatch(JARGON)
  })
  it('fishing: honest grey state', () => {
    const p = livePlain(metrics, 'fishing')
    expect(p.tiles.every((t) => t.level === 'none')).toBe(true)
  })
  it('renders without jargon and opens details', () => {
    const t = text(<LiveTab model="route" metrics={metrics} />)
    expect(t).not.toMatch(JARGON)
    expect(t).toContain('Show details')
    const d = text(<LiveTrackRecord metrics={metrics} only="route" />)
    expect(d).toContain('straight-line guess')
    expect(d).not.toMatch(/dead reckoning|Who went dark/i)
  })
  it('shows loading while metrics are null', () => {
    expect(text(<LiveTab model="godark" metrics={null} />)).toContain('Loading…')
  })
})

describe('Data tab on real /lab/data', () => {
  it('counts graded, training and history depth', () => {
    const c = dataCounters(data, 'fishing', Date.UTC(2026, 10, 8))
    expect(c.graded).toBeGreaterThan(0)
    expect(c.training).toBeGreaterThan(0)
    expect(c.depth).toMatch(/years|days/)
    expect(depthLabel(3 * 86_400_000)).toBe('3 days')
    expect(depthLabel(800 * 86_400_000)).toBe('2.2 years')
  })
  it('renders counters and sources without jargon', () => {
    const t = text(<DataTab model="route" data={data} />)
    expect(t).toContain('Graded predictions')
    expect(t).toContain('Sources')
    expect(t).not.toMatch(JARGON)
  })
})

describe('nav tab contract (TabModel)', () => {
  it('reads the champion from model.summary', () => {
    const s = summary.models.find((m) => m.target === 'route')!
    const p = livePlain(metrics, { target: 'route', name: 'Route', question: 'Where is a silent ship now?', summary: s } as never)
    expect(p.version).not.toBeNull()
    expect(text(<DataTab model={{ target: 'fishing', name: 'Fishing', question: '', summary: null }} data={data} />)).toContain('In the latest training run')
  })
})
