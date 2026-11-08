import { haversineM } from './geo.ts'

// Nearby ships mode: pure maths. Which ships came within 5 km of a ship's track in 6 h, when and how close, and whether
// two ships met at sea. Tracks are [ts, lon, lat][], oldest first (GET /track: at most one fix a minute).

export type Track = [number, number, number][]

export const RANGE_KM = 5
export const HOURS = 6
export const MAX_CANDIDATES = 30
const SOG_CAP_KN = 25
const MIN = 60_000
const GAP_MS = 15 * MIN             // fixes further apart than this are a hole: no position is invented across it
const MET_SPEED_KN = 2, MET_DIST_M = 500, MET_MIN_MS = 10 * MIN

export interface Approach { dM: number; ts: number; a: [number, number]; b: [number, number] }   // a, b = [lon, lat]
export interface Met { from: number; to: number }

/** Position on a track at time ts (linear between fixes), or null outside it or inside a hole. */
export function at(t: Track, ts: number): [number, number] | null {
  let lo = 0, hi = t.length - 1
  if (hi < 0 || ts < t[0][0] || ts > t[hi][0]) return null
  while (lo < hi) { const m = (lo + hi + 1) >> 1; if (t[m][0] <= ts) lo = m; else hi = m - 1 }
  const p = t[lo], q = t[Math.min(lo + 1, t.length - 1)]
  if (q[0] === p[0]) return [p[1], p[2]]
  if (q[0] - p[0] > GAP_MS) return null
  const f = (ts - p[0]) / (q[0] - p[0])
  return [p[1] + (q[1] - p[1]) * f, p[2] + (q[2] - p[2]) * f]
}

/** Both tracks resampled on whole minutes they share, with the distance between the two ships. */
function aligned(a: Track, b: Track): { ts: number; pa: [number, number]; pb: [number, number]; d: number }[] {
  const out: ReturnType<typeof aligned> = []
  if (!a.length || !b.length) return out
  const from = Math.ceil(Math.max(a[0][0], b[0][0]) / MIN) * MIN, to = Math.min(a[a.length - 1][0], b[b.length - 1][0])
  for (let ts = from; ts <= to; ts += MIN) {
    const pa = at(a, ts), pb = at(b, ts)
    if (pa && pb) out.push({ ts, pa, pb, d: haversineM(pa[1], pa[0], pb[1], pb[0]) })
  }
  return out
}

/** Smallest distance between the two ships at the same moment, with its time and both positions. */
export function closestApproach(a: Track, b: Track): Approach | null {
  let best: Approach | null = null
  for (const s of aligned(a, b)) if (!best || s.d < best.dM) best = { dM: s.d, ts: s.ts, a: s.pa, b: s.pb }
  return best
}

/** Both ships under 2 kn (speed from position change over 3 min) and within 500 m for at least 10 minutes in a row. */
export function metAtSea(a: Track, b: Track): Met | null {
  const speed = (t: Track, ts: number) => {
    const p = at(t, ts - 1.5 * MIN), q = at(t, ts + 1.5 * MIN)
    return p && q ? haversineM(p[1], p[0], q[1], q[0]) / (3 * 60) / 0.514444 : Infinity
  }
  let start = 0, prev = 0
  for (const s of aligned(a, b)) {
    const ok = s.d <= MET_DIST_M && speed(a, s.ts) < MET_SPEED_KN && speed(b, s.ts) < MET_SPEED_KN
    if (ok && (!start || s.ts - prev > MIN)) start = s.ts
    if (ok) { prev = s.ts; if (prev - start >= MET_MIN_MS) return { from: start, to: prev } }
    else start = 0
  }
  return null
}

const kmPerDegLon = (lat: number) => 111.32 * Math.cos((lat * Math.PI) / 180)

export interface Ship { mmsi: number; lon: number; lat: number; sog_kn: number | null }

/**
 * Ships that could have come within RANGE_KM of the track in the last 6 h, nearest to the track first, at most `max`.
 * A ship can only be a candidate if its position now is within 5 km + 6 h at its speed (at least 25 kn) of the track's
 * bounding box; the rest are rejected before any trigonometry.
 */
export function candidates(track: Track, ships: Iterable<Ship>, skip: number, max = MAX_CANDIDATES): number[] {
  if (!track.length) return []
  let w = Infinity, e = -Infinity, s = Infinity, n = -Infinity
  for (const p of track) { w = Math.min(w, p[1]); e = Math.max(e, p[1]); s = Math.min(s, p[2]); n = Math.max(n, p[2]) }
  const ranked: [number, number][] = []
  for (const v of ships) {
    if (v.mmsi === skip) continue
    const reachKm = RANGE_KM + HOURS * Math.max(v.sog_kn ?? 0, SOG_CAP_KN) * 1.852
    const dLat = reachKm / 111.32, dLon = reachKm / Math.max(1, kmPerDegLon(v.lat))
    if (v.lat < s - dLat || v.lat > n + dLat || v.lon < w - dLon || v.lon > e + dLon) continue
    let best = Infinity
    for (const p of track) best = Math.min(best, haversineM(v.lat, v.lon, p[2], p[1]))
    ranked.push([best, v.mmsi])
  }
  ranked.sort((x, y) => x[0] - y[0])
  return ranked.slice(0, max).map((r) => r[1])
}
