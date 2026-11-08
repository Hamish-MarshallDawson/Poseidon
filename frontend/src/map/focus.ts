import type { GapEvent } from '../types'
import { ghostOf } from '../forecast/geo'

export const openGap = (gaps: Iterable<GapEvent>, mmsi: number) => {
  for (const g of gaps) if (g.mmsi === mmsi && g.state === 'open') return g
  return undefined
}

// Dashed dead-reckoning segment from a gap's last fix along its last course, at most to the ghost edge.
// With the model's prediction it runs from the last fix to the predicted centre instead.
export function inferredSegment(gap: GapEvent, nowMs: number): GeoJSON.Feature | null {
  const g = ghostOf(gap, nowMs)
  if (g.model) return { type: 'Feature', properties: { kind: 'inferred' }, geometry: { type: 'LineString', coordinates: [[gap.last_lon, gap.last_lat], [g.lon, g.lat]] } }
  if (gap.last_sog_kn == null || gap.last_cog_deg == null || gap.last_sog_kn <= 0.3) return null
  const dist = Math.min(gap.last_sog_kn * 0.514444 * (nowMs - gap.start_ts) / 1000, gap.radius_m || Infinity)
  const b = (gap.last_cog_deg * Math.PI) / 180
  const to = [gap.last_lon + (dist * Math.sin(b)) / (111_320 * Math.cos((gap.last_lat * Math.PI) / 180)), gap.last_lat + (dist * Math.cos(b)) / 111_320]
  return { type: 'Feature', properties: { kind: 'inferred' }, geometry: { type: 'LineString', coordinates: [[gap.last_lon, gap.last_lat], to] } }
}
