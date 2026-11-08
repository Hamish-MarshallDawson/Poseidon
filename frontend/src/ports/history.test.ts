import { describe, expect, it, vi } from 'vitest'

const obs = vi.fn()
vi.mock('../data/index', () => ({ adapter: { observations: (q: unknown) => obs(q) } }))
vi.mock('../data/track', () => ({ getTrack: async () => [[0, 10, 55], [1, 11, 56]] }))

const row = (mmsi: number) => ({ id: `r${mmsi}`, src: 'gfw', kind: 'port_visit', ts: 1, end_ts: 2, mmsi, lat: 55, lon: 10, value: 3 })

describe('getHistory', () => {
  it('falls back to the track bbox and 7 days on a 422, filtering by mmsi', async () => {
    const { getHistory } = await import('./history')
    obs.mockRejectedValueOnce(Object.assign(new Error('422'), { status: 422 }))
    obs.mockResolvedValueOnce({ observations: [row(7), row(8)] })
    const h = await getHistory(7)
    expect(h?.days).toBe(7)
    expect(h?.rows.map((r) => r.mmsi)).toEqual([7])
    expect(obs.mock.calls[1][0].bbox).toEqual([9.5, 54.5, 11.5, 56.5])
    // remembered: the next ship goes straight to the bbox query
    obs.mockResolvedValueOnce({ observations: [] })
    await getHistory(9)
    expect(obs.mock.calls[2][0].mmsi).toBeUndefined()
  })
})
