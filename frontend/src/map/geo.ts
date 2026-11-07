// Small geometry helpers shared by the ship layer, density pass and focus mode.
// The map never rotates or pitches (MapView disables both), so screen px = (mercator - centre) × worldSize.

export const EARTH_M = 40075016.686          // circumference at the equator, = 1 mercator unit
export const NMI_M = 1852
const MAX_LAT = 85.051129

export const mercX = (lon: number) => (lon + 180) / 360
export function mercY(lat: number): number {
  const s = Math.sin((Math.max(-MAX_LAT, Math.min(MAX_LAT, lat)) * Math.PI) / 180)
  return 0.5 - Math.log((1 + s) / (1 - s)) / (4 * Math.PI)
}
export const lonOf = (x: number) => x * 360 - 180
export const latOf = (y: number) => (Math.atan(Math.sinh(Math.PI * (1 - 2 * y))) * 180) / Math.PI

// Mercator units per metre at a latitude (same in x and y: mercator is conformal).
export const unitsPerMetre = (lat: number) => 1 / (EARTH_M * Math.cos((lat * Math.PI) / 180))

export function haversineM(lat1: number, lon1: number, lat2: number, lon2: number): number {
  const r = Math.PI / 180
  const a = Math.sin(((lat2 - lat1) * r) / 2) ** 2 + Math.cos(lat1 * r) * Math.cos(lat2 * r) * Math.sin(((lon2 - lon1) * r) / 2) ** 2
  return 2 * 6371008.8 * Math.asin(Math.min(1, Math.sqrt(a)))
}

// AIS "not available" values: heading 511, course 360.
export function headingOf(heading: number | null, cog: number | null): number | null {
  if (heading != null && heading >= 0 && heading < 360) return heading
  if (cog != null && cog >= 0 && cog < 360) return cog
  return null
}

// Zoom tiers from the ship iconography report (far 0–6, mid 7–10, near 11+).
export type SizeTier = 'far' | 'mid' | 'near'
export const sizeTier = (zoom: number): SizeTier => (zoom < 7 ? 'far' : zoom < 11 ? 'mid' : 'near')
