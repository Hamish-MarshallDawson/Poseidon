import { adapter } from '../data/index'
import { getTrack } from '../data/track'
import type { Observation } from '../types'

const DAY = 86_400_000
const KINDS = ['port_visit', 'loitering', 'encounter']
const BUFFER_DEG = 0.5
const TTL_MS = 5 * 60_000

export interface ShipHistory { rows: Observation[]; days: number; attribution: string }

// Newer backends take `mmsi` without a bbox and a long window; older ones answer 422. Remembered for the session.
let byMmsi = true
const cache = new Map<number, { at: number; p: Promise<ShipHistory | null> }>()

async function load(mmsi: number): Promise<ShipHistory | null> {
  if (!adapter?.observations) return null
  const end = Date.now()
  let days = 30
  let reply
  if (byMmsi) {
    try { reply = await adapter.observations({ kinds: KINDS, mmsi, start: end - 30 * DAY, end }) }
    catch (e) { if ((e as { status?: number }).status !== 422) throw e; byMmsi = false }
  }
  if (!reply) {
    // shortcut: without the mmsi parameter the route needs a bbox and allows 7 days; use the 24 h track's box and filter here.
    days = 7
    const t = await getTrack(mmsi, 24)
    if (!t.length) return null
    const lons = t.map((p) => p[1]), lats = t.map((p) => p[2])
    reply = await adapter.observations({ kinds: KINDS, start: end - 7 * DAY, end,
      bbox: [Math.min(...lons) - BUFFER_DEG, Math.min(...lats) - BUFFER_DEG, Math.max(...lons) + BUFFER_DEG, Math.max(...lats) + BUFFER_DEG] })
  }
  const rows = reply.observations.filter((o) => o.mmsi === mmsi && KINDS.includes(o.kind))
  const a = Object.values(reply.attribution ?? {}).find((v) => typeof v === 'string') as string | undefined
  return { rows, days, attribution: a ?? 'Global Fishing Watch, CC BY-NC 4.0' }
}

// One ship's recent port visits, loitering and encounters; cached per ship for a few minutes. Rejects or resolves null
// when the backend has none of this, so the caller shows nothing.
export function getHistory(mmsi: number): Promise<ShipHistory | null> {
  const hit = cache.get(mmsi)
  if (hit && Date.now() - hit.at < TTL_MS) return hit.p
  const p = load(mmsi)
  cache.set(mmsi, { at: Date.now(), p })
  p.catch(() => { if (cache.get(mmsi)?.p === p) cache.delete(mmsi) })
  return p
}
