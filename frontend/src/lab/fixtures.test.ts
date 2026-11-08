import { describe, expect, it } from 'vitest'
import raw from './fixtures.json'
import type { Fixtures } from './types'

// The fixtures must keep the contract's shape: they're what the Lab shows on mock data or when an endpoint fails.
const fx = raw as unknown as Fixtures

describe('fixtures', () => {
  it('have every endpoint', () => {
    for (const k of ['summary', 'runs', 'run_detail', 'proposals', 'events', 'metrics', 'data']) expect(fx).toHaveProperty(k)
    expect(fx.summary.models.length).toBeGreaterThan(0)
  })
  it('have a detail for every run, newest run first', () => {
    for (const r of fx.runs) expect(fx.run_detail[r.run_id]?.run_id).toBe(r.run_id)
    const ts = fx.runs.map((r) => r.created_at)
    expect([...ts].sort((a, b) => b - a)).toEqual(ts)
  })
  it('have events oldest first', () => {
    const ts = fx.events.map((e) => e.ts)
    expect([...ts].sort((a, b) => a - b)).toEqual(ts)
  })
})
