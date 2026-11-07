import type { GapEvent } from '../types'

export const GHOST_CAP_M = 60_000      // placeholder cap from the forecast report until the detector sets the real one

// "Could be anywhere in here": last speed x time since the last fix, capped; the server's radius_m when speed is unknown.
export function ghostRadius(g: GapEvent, at: number): number {
  if (g.last_sog_kn == null) return g.radius_m ?? 500
  return Math.min(GHOST_CAP_M, Math.max(500, g.last_sog_kn * 0.514444 * Math.max(0, at - g.start_ts) / 1000))
}

// Closed ring of n vertices round (lon, lat), radius r metres (equirectangular; fine below the 60 km cap).
export function circle(lon: number, lat: number, r: number, n = 64): [number, number][] {
  const dLat = r / 111_320
  const dLon = r / (111_320 * Math.cos((lat * Math.PI) / 180))
  const ring: [number, number][] = []
  for (let i = 0; i <= n; i++) {
    const a = (i / n) * 2 * Math.PI
    ring.push([lon + dLon * Math.sin(a), lat + dLat * Math.cos(a)])
  }
  return ring
}
