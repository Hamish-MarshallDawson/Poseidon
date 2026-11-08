import { describe, expect, it } from 'vitest'
import { band, extent, linear, niceTicks, numLabel, pad, timeLabel, timeTicks } from './scale'
import { pathOf, placeTip } from './geom'

const H = 3_600_000
const D = 24 * H

describe('scales', () => {
  it('linear maps and inverts, and a flat domain maps to the middle', () => {
    const s = linear([0, 10], [100, 200])
    expect(s(5)).toBe(150)
    expect(s.invert(150)).toBe(5)
    expect(linear([3, 3], [0, 100])(3)).toBe(50)
  })
  it('band spreads categories with padding', () => {
    const b = band(['a', 'b'], [0, 100], 0.2)
    expect(b('a')).toBe(5)
    expect(b('b')).toBe(55)
    expect(b.bandwidth).toBe(40)
  })
  it('extent skips nulls and NaN; pad widens', () => {
    expect(extent([3, null, NaN, -1, undefined, 7])).toEqual([-1, 7])
    expect(extent([], [0, 5])).toEqual([0, 5])
    expect(pad([0, 10], 0.1)).toEqual([-1, 11])
    expect(pad([0, 0])).toEqual([-1, 1])
  })
})

describe('ticks', () => {
  it('nice numeric ticks', () => {
    expect(niceTicks([0, 1], 5)).toEqual([0, 0.2, 0.4, 0.6, 0.8, 1])
    expect(niceTicks([-0.13, 0.62], 4)).toEqual([0, 0.2, 0.4, 0.6])
  })
  it('hourly ticks over a day, aligned to UTC hours', () => {
    const t0 = Date.UTC(2026, 10, 7, 8, 25)
    const t = timeTicks([t0, t0 + D], 5)
    expect(t.length).toBeGreaterThanOrEqual(4)
    expect(t.every((v) => v % (3 * H) === 0)).toBe(true)
    expect(timeLabel(t[0], 6 * H)).toMatch(/^\d\d:00$/)
  })
  it('month and year ticks over long spans', () => {
    const m = timeTicks([Date.UTC(2026, 0, 15), Date.UTC(2026, 10, 8)], 5)
    expect(m.map((t) => new Date(t).getUTCDate())).toEqual(m.map(() => 1))
    const y = timeTicks([Date.UTC(2017, 0, 1), Date.UTC(2026, 10, 8)], 5)
    expect(y.map((t) => new Date(t).getUTCFullYear())).toEqual([2018, 2020, 2022, 2024, 2026])
    expect(timeLabel(y[0], 730 * D)).toBe('2018')
    expect(timeLabel(Date.UTC(2026, 10, 8), 3 * D)).toBe('8 Nov')
  })
  it('number labels', () => {
    expect(numLabel(0.8, true)).toBe('80%')
    expect(numLabel(117900)).toBe('118k')
    expect(numLabel(1500)).toBe('1.5k')
    expect(numLabel(0.046)).toBe('0.046')
  })
})

describe('pathOf', () => {
  it('breaks at nulls and draws step-after', () => {
    expect(pathOf([{ px: 0, py: 1 }, { px: 1, py: 2 }, { px: 2, py: null }, { px: 3, py: 4 }])).toBe('M0,1L1,2M3,4')
    expect(pathOf([{ px: 0, py: 1 }, { px: 5, py: 2 }], true)).toBe('M0,1H5V2')
  })
})

describe('placeTip', () => {
  const size = { w: 260, h: 40 }
  it('centres above the point when there is room', () => {
    expect(placeTip({ x: 500, y: 100 }, size, { left: 0, top: 200 }, { w: 1440 })).toEqual({ left: 370, top: 50 })
  })
  it('stays inside a 390 px viewport at both edges, measured from the chart origin', () => {
    expect(placeTip({ x: 10, y: 100 }, size, { left: 16, top: 200 }, { w: 390 }).left).toBe(4 - 16)
    expect(placeTip({ x: 350, y: 100 }, size, { left: 16, top: 200 }, { w: 390 }).left).toBe(390 - 4 - 260 - 16)
  })
  it('drops below the point near the top of the viewport', () => {
    expect(placeTip({ x: 200, y: 20 }, size, { left: 0, top: 10 }, { w: 1440 }).top).toBe(30)
  })
})
