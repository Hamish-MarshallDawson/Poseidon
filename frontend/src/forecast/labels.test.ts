import { describe, expect, it } from 'vitest'
import { raisedBy } from './labels'

describe('raisedBy', () => {
  it('keeps positive contributions, largest first, in plain words, without repeats', () => {
    expect(raisedBy({ sog_kn: 0.4, hour_sin: 0.2, hour_cos: 0.3, age_s: -0.9, mystery_feature: 0.1 })).toEqual(['speed', 'time of day', 'mystery feature'])
  })
  it('is empty without contributions', () => {
    expect(raisedBy(undefined)).toEqual([])
    expect(raisedBy({ sog_kn: -1 })).toEqual([])
  })
})
