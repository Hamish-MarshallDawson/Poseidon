import type { ServerMsg, VesselView } from './types'

// Applies a snapshot or delta to the vessel map. Returns true if the map changed.
// Other message types (watchlist, status, detail, ping, hello) are ignored for milestone 1.
export function applyMessage(vessels: Map<number, VesselView>, msg: ServerMsg): boolean {
  if (msg.type === 'snapshot') {
    vessels.clear()
    for (const v of msg.vessels) vessels.set(v.mmsi, v)
    return true
  }
  if (msg.type === 'delta') {
    for (const mmsi of msg.removed) vessels.delete(mmsi)
    for (const v of msg.vessels) vessels.set(v.mmsi, v)
    return true
  }
  return false
}

// One GeoJSON feature per vessel, coordinates in [lon, lat] order.
export function toFeatureCollection(vessels: Map<number, VesselView>) {
  return {
    type: 'FeatureCollection' as const,
    features: Array.from(vessels.values(), (v) => ({
      type: 'Feature' as const,
      properties: { mmsi: v.mmsi },
      geometry: { type: 'Point' as const, coordinates: [v.lon, v.lat] },
    })),
  }
}
