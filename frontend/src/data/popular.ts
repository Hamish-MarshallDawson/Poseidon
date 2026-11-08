import { createStore } from '../store/store'
import { vessels } from '../store/vessels'

// Popular places: where ships spend the most hours, from GFW `ais_presence` cells (0.01° per day, value = hours).
// 1. Server summary GET /observations/heat (one request, months of history). It may 404 until the backend has it.
// 2. Fallback: the raw route, current view only, last 7 days, one request per day, summed on a coarse grid client-side.
// 3. Offline or mock data: an illustrative sample made from the synthetic ships.
export type Cell = [lon: number, lat: number, hours: number]
export type Bbox = [w: number, s: number, e: number, n: number]
export interface Popular { cells: Cell[]; label: string; attribution: string | null; source: 'summary' | 'raw' | 'sample'; rows: number; ms: number }

export const ATTRIBUTION = 'Global Fishing Watch, CC BY-NC 4.0'
const DAY = 86_400_000
const ROW_CAP = 50_000            // stop fetching after this many raw rows
const SUMMARY_DAYS = 90           // how far back the summary is asked for (the route's maximum)
const base = () => import.meta.env.VITE_API_URL || 'http://localhost:8000'

/** What the map shows now (the controller writes it, the Display panel reads it). */
export const popular = createStore<{ loading: boolean; label: string | null }>({ loading: false, label: null })

let getToken: () => Promise<string | undefined> = async () => undefined
export function bindPopularAuth(fn: (() => Promise<string | undefined>) | null) { getToken = fn ?? (async () => undefined) }

/** Grid size in degrees for a zoom (about 12 px per cell at the screen). */
export function resFor(zoom: number): number {
  return zoom < 3 ? 2 : zoom < 5 ? 1 : zoom < 7 ? 0.25 : zoom < 9 ? 0.05 : 0.02
}

const cache = new Map<string, Popular>()
let summaryMissing = 0   // when the summary last answered 404; retried after 10 minutes

export async function popularCells(bbox: Bbox, zoom: number, signal?: AbortSignal): Promise<Popular> {
  const res = resFor(zoom)
  const key = `${res}|${bbox.map((v) => Math.round(v / (res * 4))).join(',')}`
  const hit = cache.get(key)
  if (hit) return hit
  const t0 = performance.now()
  let out: Popular
  if (import.meta.env.VITE_DATA === 'offline') out = sample(res)
  else {
    try {
      out = (await summary(bbox, res, signal)) ?? (await raw(bbox, res, signal))
    } catch (e) {
      if (signal?.aborted || import.meta.env.VITE_DATA === 'live') throw e
      out = sample(res)   // mock mode with no backend answering
    }
  }
  out.ms = Math.round(performance.now() - t0)
  cache.set(key, out)
  if (cache.size > 40) cache.delete(cache.keys().next().value!)
  return out
}

async function get(path: string, signal?: AbortSignal): Promise<Response> {
  const token = await getToken()
  return fetch(`${base()}${path}`, { signal, headers: token ? { Authorization: `Bearer ${token}` } : {} })
}

async function summary(bbox: Bbox, res: number, signal?: AbortSignal): Promise<Popular | null> {
  if (Date.now() - summaryMissing < 600_000) return null
  const start = Date.now() - SUMMARY_DAYS * DAY
  const cellDeg = Math.min(1, Math.max(0.05, res))   // the route takes cell_deg 0.05 to 1
  const r = await get(`/observations/heat?kinds=ais_presence&bbox=${bbox.join(',')}&start=${start}&end=${Date.now()}&cell_deg=${cellDeg}`, signal)
  if (r.status === 404) { summaryMissing = Date.now(); return null }
  if (!r.ok) throw new Error(`GET /observations/heat: ${r.status}`)
  // Aiden's #143 shape: { cells: [{ lat, lon, value, n }], cell_deg, kinds, attribution }
  const j = (await r.json()) as { cells: { lat: number; lon: number; value: number }[]; attribution?: unknown }
  const cells: Cell[] = j.cells.map((c) => [c.lon, c.lat, c.value])
  const since = new Date(start).toLocaleString('en-GB', { month: 'long', year: 'numeric', timeZone: 'UTC' })
  return { cells, label: `Popular places · since ${since}`, attribution: typeof j.attribution === 'string' ? j.attribution : ATTRIBUTION, source: 'summary', rows: cells.length, ms: 0 }
}

// Raw rows: the route returns at most 5,000 per call, newest first, so ask one day at a time to cover the week.
async function raw(bbox: Bbox, res: number, signal?: AbortSignal): Promise<Popular> {
  const grid = new Map<string, Cell>()
  const end = Date.now()
  let rows = 0
  for (let d = 0; d < 7 && rows < ROW_CAP; d++) {
    const hi = end - d * DAY
    const r = await get(`/observations?kinds=ais_presence&bbox=${bbox.join(',')}&start=${hi - DAY}&end=${hi}&limit=5000`, signal)
    if (!r.ok) throw new Error(`GET /observations: ${r.status}`)
    const j = (await r.json()) as { observations: { lon: number; lat: number; value: number | null; cell_deg: number | null }[] }
    for (const o of j.observations) {
      if (!o.cell_deg || o.value == null) continue   // region rows (one per vessel) are not cells
      add(grid, res, o.lon, o.lat, o.value)
      rows++
    }
  }
  return { cells: [...grid.values()], label: 'Popular places · last 7 days', attribution: ATTRIBUTION, source: 'raw', rows, ms: 0 }
}

function add(grid: Map<string, Cell>, res: number, lon: number, lat: number, hours: number) {
  const x = Math.floor(lon / res), y = Math.floor(lat / res), k = `${x},${y}`
  const c = grid.get(k)
  if (c) c[2] += hours
  else grid.set(k, [(x + 0.5) * res, (y + 0.5) * res, hours])
}

// Illustrative sample: every synthetic ship counts one hour in its cell, so busy places come out busy.
function sample(res: number): Popular {
  const grid = new Map<string, Cell>()
  for (const v of vessels.vessels.values()) if (v.lat != null && v.lon != null) add(grid, res, v.lon, v.lat, 1)
  return { cells: [...grid.values()], label: 'Popular places · illustrative sample', attribution: null, source: 'sample', rows: vessels.vessels.size, ms: 0 }
}

/** Heat points with `n` rescaled to 1..40 on a log scale, which the layer's weight stops expect. */
export function popularFeatures(cells: Cell[]): GeoJSON.FeatureCollection {
  const max = Math.log1p(Math.max(1, ...cells.map((c) => c[2])))
  return {
    type: 'FeatureCollection',
    features: cells.map(([lon, lat, h]) => ({
      type: 'Feature', properties: { n: 1 + (39 * Math.log1p(h)) / max }, geometry: { type: 'Point', coordinates: [lon, lat] },
    })),
  }
}
