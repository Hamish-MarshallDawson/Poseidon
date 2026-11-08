import type { FocusRelation } from '../store/ui'
import type { GapEvent, VesselView } from '../types'
import { haversineM, NMI_M } from './geo'

// Focus mode relation rules from R1-AGENT3-DENSITY.md (same owner needs a data source: not built).
const NEARBY_M = 10 * NMI_M, NEARBY_MOORED_M = 2 * NMI_M
const RDV_M = 0.5 * NMI_M, RDV_MIN_MS = 30 * 60000, RDV_SOG = 3
const DARK_M = 30 * NMI_M, DARK_WINDOW_MS = 60 * 60000
const MAX = { nearby: 8, rendezvous: 3, also_dark: 3, same_flag: 5 }

type Trail = [number, number, number][]   // [ts, lon, lat]

export interface FocusInput {
  focus: VesselView
  vessels: Iterable<VesselView>
  gaps: Iterable<GapEvent>
  trails: Map<number, Trail>
  inView: (lon: number, lat: number) => boolean
}

const openGap = (gaps: Iterable<GapEvent>, mmsi: number) => {
  for (const g of gaps) if (g.mmsi === mmsi && g.state === 'open') return g
  return undefined
}

// Both ships slow and within 0.5 nmi at matching times for at least 30 min, walking back from the latest fix.
function rendezvous(a: Trail | undefined, b: Trail | undefined): boolean {
  if (!a?.length || !b?.length) return false
  let j = b.length - 1, end = 0, start = 0
  for (let i = a.length - 1; i >= 0; i--) {
    const [ts, lon, lat] = a[i]
    while (j > 0 && b[j][0] > ts + 90_000) j--
    const p = b[j]
    if (Math.abs(p[0] - ts) > 180_000 || haversineM(lat, lon, p[2], p[1]) > RDV_M) break
    if (!end) end = ts
    start = ts
  }
  return end - start >= RDV_MIN_MS
}

export function computeRelations(inp: FocusInput): FocusRelation[] {
  const f = inp.focus
  const used = new Set<number>([f.mmsi])
  const out: FocusRelation[] = []
  const near: [number, VesselView][] = [], flag: [number, VesselView][] = []
  const nearR = (f.sog_kn ?? 0) < 0.5 ? NEARBY_MOORED_M : NEARBY_M
  const dLat = DARK_M / 111_000
  const rdv: VesselView[] = []
  for (const v of inp.vessels) {
    if (v.mmsi === f.mmsi) continue
    const sameFlag = f.flag != null && v.flag === f.flag
    if (!sameFlag && Math.abs(v.lat - f.lat) > dLat) continue        // cheap reject before the trig
    const d = haversineM(f.lat, f.lon, v.lat, v.lon)
    if (d <= nearR) near.push([d, v])
    if (d <= RDV_M && (v.sog_kn ?? 0) < RDV_SOG && (f.sog_kn ?? 0) < RDV_SOG) rdv.push(v)
    if (sameFlag && inp.inView(v.lon, v.lat)) flag.push([d, v])
  }
  const add = (mmsi: number, reason: FocusRelation['reason']) => { used.add(mmsi); out.push({ mmsi, reason }) }

  let n = 0
  for (const v of rdv) if (n < MAX.rendezvous && rendezvous(inp.trails.get(f.mmsi), inp.trails.get(v.mmsi))) { add(v.mmsi, 'rendezvous'); n++ }

  const g = openGap(inp.gaps, f.mmsi)
  if (g) {
    const dark: [number, number][] = []
    for (const o of inp.gaps) {
      if (o.state !== 'open' || used.has(o.mmsi) || Math.abs(o.start_ts - g.start_ts) > DARK_WINDOW_MS) continue
      const d = haversineM(g.last_lat, g.last_lon, o.last_lat, o.last_lon)
      if (d <= DARK_M) dark.push([d, o.mmsi])
    }
    dark.sort((a, b) => a[0] - b[0])
    for (const [, m] of dark.slice(0, MAX.also_dark)) add(m, 'also_dark')
  }
  near.sort((a, b) => a[0] - b[0])
  n = 0
  for (const [, v] of near) if (n < MAX.nearby && !used.has(v.mmsi)) { add(v.mmsi, 'nearby'); n++ }
  flag.sort((a, b) => a[0] - b[0])
  n = 0
  for (const [, v] of flag) if (n < MAX.same_flag && !used.has(v.mmsi)) { add(v.mmsi, 'same_flag'); n++ }
  return out
}

export const sameRelations = (a: FocusRelation[], b: FocusRelation[]) =>
  a.length === b.length && a.every((r, i) => r.mmsi === b[i].mmsi && r.reason === b[i].reason)

// Map geometry for focus mode: inferred segment (dashed), ghost circle and leaders.
export function focusGeometry(f: VesselView, related: VesselView[], gap: GapEvent | undefined, nowMs: number) {
  const line = (coords: number[][], kind: string): GeoJSON.Feature => ({ type: 'Feature', properties: { kind }, geometry: { type: 'LineString', coordinates: coords } })
  const features: GeoJSON.Feature[] = []
  for (const r of related) features.push(line([[r.lon, r.lat], [f.lon, f.lat]], 'leader'))
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

export { openGap }
