import { describe, expect, it } from 'vitest'
import type { GapEvent } from '../types'
import { ghostOf, ghostRadius } from './geo'

const gap = { id: 'g', last_lat: 55, last_lon: 10, last_sog_kn: 10, start_ts: 0 } as GapEvent
const T = 3_600_000

describe('ghostOf', () => {
  it('without prediction: dead reckoning at the last fix', () => {
    expect(ghostOf(gap, T)).toEqual({ lon: 10, lat: 55, r: ghostRadius(gap, T) })
  })
  it('with prediction: centre, r80, r95 ring, model', () => {
    const g = { ...gap, pred_lat: 55.2, pred_lon: 10.3, pred_r80_m: 3200, pred_r95_m: 6000, pred_model: 'm1' }
    expect(ghostOf(g, T)).toEqual({ lon: 10.3, lat: 55.2, r: 3200, r95: 6000, model: 'm1' })
  })
  it('partial fields fall back to dead reckoning; a missing r95 is just no ring', () => {
    expect(ghostOf({ ...gap, pred_lat: 55.2, pred_r80_m: 3200 }, T)).toEqual({ lon: 10, lat: 55, r: ghostRadius(gap, T) })
    expect(ghostOf({ ...gap, pred_lat: 55.2, pred_lon: 10.3, pred_r80_m: 3200 }, T).r95).toBeUndefined()
  })
})
