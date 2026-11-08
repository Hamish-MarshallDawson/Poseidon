import { describe, expect, it } from 'vitest'
import { calValue, horizon, interval, signedPct, when } from './format'

describe('lab format', () => {
  it('times in UTC, year only when it differs', () => {
    const t = Date.UTC(2026, 10, 8, 8, 25)
    expect(when(t, t)).toBe('8 Nov 08:25 UTC')
    expect(when(t, Date.UTC(2027, 0, 1))).toBe('8 Nov 2026 08:25 UTC')
    expect(when(null)).toBe('unknown time')
  })
  it('horizons', () => {
    expect(horizon(10800)).toBe('3 h')
    expect(horizon('604800')).toBe('7 d')
    expect(horizon(1800)).toBe('30 min')
  })
  it('signed percents and intervals', () => {
    expect(signedPct(0.624)).toBe('+62%')
    expect(signedPct(-0.057)).toBe('−5.7%')
    expect(signedPct(null)).toBe('n/a')
    expect(interval(0.264, 0.313)).toBe('[+26%, +31%]')
    expect(interval(null, 0.3)).toBeNull()
  })
  it('calibration values', () => {
    expect(calValue('80% circle coverage', 0.6)).toBe('60%')
    expect(calValue('mean p vs hit rate, 6 h', 0.0952)).toBe('0.095')
  })
})
