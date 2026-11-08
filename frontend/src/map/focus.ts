import type { FocusRelation } from '../store/ui'
import type { GapEvent, VesselView } from '../types'
import { candidates, closestApproach, HOURS, metAtSea, RANGE_KM } from './nearby.ts'
import type { Track } from './nearby.ts'

// Focus mode is "Nearby ships": the ships that came within 5 km of the focused ship's track in the last 6 h.

const IN_FLIGHT = 4
const HOUR_MS = 3_600_000

export interface NearbyResult { relations: FocusRelation[]; features: GeoJSON.Feature[] }

/** "13:40Z" in UTC. */
export const utcTime = (ts: number) => `${new Date(ts).toISOString().slice(11, 16)}Z`
export const fmtKm = (m: number) => `${(m / 1000).toFixed(1)} km`

// Runs the search: the focal 6 h track, then candidate ships' tracks (4 requests at a time) and their closest approach.
// A ship whose track cannot be read is left out. `stale()` stops the work when focus has moved on.
export async function findNearby(
  focus: VesselView, vessels: Iterable<VesselView>, nowMs: number,
  getTrack: (mmsi: number, hours: number) => Promise<Track>, stale: () => boolean,
): Promise<NearbyResult | null> {
  const since = nowMs - HOURS * HOUR_MS
  const mine = (await getTrack(focus.mmsi, HOURS).catch(() => [] as Track)).filter((p) => p[0] >= since)
  if (stale()) return null
  const ids = candidates(mine, vessels, focus.mmsi)
  const found: { rel: FocusRelation; track: Track; a: [number, number]; b: [number, number] }[] = []
  let next = 0
  const worker = async () => {
    while (next < ids.length && !stale()) {
      const mmsi = ids[next++]
      const t = (await getTrack(mmsi, HOURS).catch(() => [] as Track)).filter((p) => p[0] >= since)
      const ca = closestApproach(mine, t)
      if (!ca || ca.dM > RANGE_KM * 1000) continue
      found.push({ rel: { mmsi, cpaM: ca.dM, cpaTs: ca.ts, met: metAtSea(mine, t) !== null }, track: t, a: ca.a, b: ca.b })
    }
  }
  await Promise.all(Array.from({ length: Math.min(IN_FLIGHT, ids.length) }, worker))
  if (stale()) return null
  found.sort((x, y) => x.rel.cpaM - y.rel.cpaM)
  const features: GeoJSON.Feature[] = []
  const line = (coords: number[][], props: object): GeoJSON.Feature => ({ type: 'Feature', properties: props, geometry: { type: 'LineString', coordinates: coords } })
  const point = (c: number[], props: object): GeoJSON.Feature => ({ type: 'Feature', properties: props, geometry: { type: 'Point', coordinates: c } })
  for (const f of found) {
    let seg: number[][] = []
    for (let i = 0; i < f.track.length; i++) {
      if (i && f.track[i][0] - f.track[i - 1][0] > 15 * 60_000) { if (seg.length > 1) features.push(line(seg, { kind: 'ntrack' })); seg = [] }
      seg.push([f.track[i][1], f.track[i][2]])
    }
    if (seg.length > 1) features.push(line(seg, { kind: 'ntrack' }))
    features.push(line([f.a, f.b], { kind: 'cpa-link' }), point(f.a, { kind: 'cpa' }), point(f.b, { kind: 'cpa' }))
    // The label sits on the other ship's marker, so the focal track stays clear of text.
    features.push(point(f.b, { kind: 'cpa-label', label: `${utcTime(f.rel.cpaTs)} · ${fmtKm(f.rel.cpaM)}` }))
  }
  return { relations: found.map((f) => f.rel), features }
}

export const openGap = (gaps: Iterable<GapEvent>, mmsi: number) => {
  for (const g of gaps) if (g.mmsi === mmsi && g.state === 'open') return g
  return undefined
}

// Map geometry for a focused ship that has gone dark: inferred segment (dashed), ghost circle and cross.
export function focusGeometry(gap: GapEvent | undefined, nowMs: number) {
  const line = (coords: number[][], kind: string): GeoJSON.Feature => ({ type: 'Feature', properties: { kind }, geometry: { type: 'LineString', coordinates: coords } })
  const features: GeoJSON.Feature[] = []
  if (gap) {
    const radius = gap.radius_m ?? 0
    // Inferred: dead reckoning from the last fix along the last course, at most to the ghost edge.
    if (gap.last_sog_kn != null && gap.last_cog_deg != null && gap.last_sog_kn > 0.3) {
      const dist = Math.min(gap.last_sog_kn * 0.514444 * (nowMs - gap.start_ts) / 1000, radius || Infinity)
      features.push(line([[gap.last_lon, gap.last_lat], offset(gap.last_lat, gap.last_lon, gap.last_cog_deg, dist)], 'inferred'))
    }
    if (radius > 0) {
      const ring = Array.from({ length: 65 }, (_, i) => offset(gap.last_lat, gap.last_lon, (i / 64) * 360, radius))
      features.push({ type: 'Feature', properties: { kind: 'ghost' }, geometry: { type: 'Polygon', coordinates: [ring] } })
    }
    features.push({ type: 'Feature', properties: { kind: 'cross' }, geometry: { type: 'Point', coordinates: [gap.last_lon, gap.last_lat] } })
  }
  return { type: 'FeatureCollection' as const, features }
}

function offset(lat: number, lon: number, bearingDeg: number, m: number): number[] {
  const b = (bearingDeg * Math.PI) / 180
  const dLat = (m * Math.cos(b)) / 111_320
  const dLon = (m * Math.sin(b)) / (111_320 * Math.cos((lat * Math.PI) / 180))
  return [lon + dLon, lat + dLat]
}

