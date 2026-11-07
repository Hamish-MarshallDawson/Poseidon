import type { VesselView } from '../types'
import type { Rank } from './stacking'
import { latOf, lonOf } from './geo'
import type { ShipState } from './ships/state'

// Density caps, slot priority, separation and hysteresis from R1-AGENT3-DENSITY.md, plus the stack fold from
// R2-AGENT1-STACKING.md. Runs on moveend (and every few seconds for new data), never per frame.

export interface Band { name: 'world' | 'region' | 'sea' | 'harbour'; cap: number; cellDeg: number; breaks: number[] }
export function bandOf(zoom: number): Band {
  if (zoom < 4) return { name: 'world', cap: 100, cellDeg: 2, breaks: [1, 50, 250, 1000] }
  if (zoom < 7) return { name: 'region', cap: 100, cellDeg: 0.5, breaks: [1, 20, 80, 300] }
  if (zoom < 10) return { name: 'sea', cap: 40, cellDeg: 0.1, breaks: [1, 3, 10, 30] }
  return { name: 'harbour', cap: 20, cellDeg: 0, breaks: [] }
}
export const CELL_TINT = [0.05, 0.09, 0.14, 0.22]   // ink at these opacities, lightest to busiest
export const HOLD_S = 20

export interface View { cx: number; cy: number; worldSize: number; width: number; height: number; zoom: number; hullPx: number }
export interface SlotInput {
  state: ShipState
  view: View
  nowMs: number                    // feed clock (epoch ms), for recency
  now: number                      // page clock (s), for hysteresis
  pinned: Set<number>              // tier 0: windows, focus, hover; always drawn, never counted against the cap
  related: Set<number>             // focus relations: drawn like tier 0 but counted
  ranks: Map<number, Rank>
  held: Map<number, number>        // mmsi → held until (page clock s); updated in place
  capOverride?: number             // dev switch: ?cap=0 draws every ship in view (stress test)
}
export interface Chip { lon: number; lat: number; mmsis: number[]; plus: boolean }
export interface SlotResult {
  drawn: number[]                  // slots
  chips: Chip[]
  cells: GeoJSON.FeatureCollection
  counts: { inView: number; shown: number; stacked: number; inCells: number }
}

// Slot priority 0..7; 9 = may not take a slot (silent or stale without a flag).
function slotTier(v: VesselView, pinned: boolean, related: boolean, rank: Rank | undefined): number {
  if (pinned || related) return 0
  if (rank?.decision === 'inspect') return 1
  if (v.status === 'gap_open') return 2
  if (rank?.decision === 'watch') return 3
  if (v.sanctioned || v.spoof_recent.length) return 4
  if (v.status !== 'active') return 9
  if ((v.length_m ?? 0) >= 200 || (v.sog_kn ?? 0) >= 18) return 6
  return 7
}

export function computeSlots(inp: SlotInput): SlotResult {
  const { state, view, nowMs, now, pinned, related, ranks, held } = inp
  const band = bandOf(view.zoom)
  const cap = inp.capOverride === 0 ? Infinity : (inp.capOverride ?? band.cap)
  const pad = 0.05
  const halfW = (view.width * (0.5 + pad)) / view.worldSize, halfH = (view.height * (0.5 + pad)) / view.worldSize
  const n = state.highWater
  const idx: number[] = []
  const key = new Float64Array(n)
  const px = new Float32Array(n), py = new Float32Array(n), tier = new Uint8Array(n)
  const p = [0, 0]
  for (let s = 0; s < n; s++) {
    const v = state.view[s]
    if (!v) continue
    state.posAt(s, now, p)
    let dx = p[0] - view.cx
    dx -= Math.round(dx)                                          // nearest world copy
    const dy = p[1] - view.cy
    if (Math.abs(dx) > halfW || Math.abs(dy) > halfH) continue
    px[s] = view.width / 2 + dx * view.worldSize
    py[s] = view.height / 2 + dy * view.worldSize
    const r = ranks.get(v.mmsi)
    const t = slotTier(v, pinned.has(v.mmsi), related.has(v.mmsi), r)
    tier[s] = t
    let sec: number
    if (t === 1 || t === 3) sec = r!.rank
    else if (t === 2) sec = 1e9 - Math.max(0, (nowMs - v.last_ts) / 1000)
    else if (t === 6) sec = 1e5 - (v.length_m ?? 0)
    else sec = Math.min(1e9, Math.max(0, (nowMs - v.last_ts) / 1000))
    const dist = Math.min(999, Math.hypot(px[s] - view.width / 2, py[s] - view.height / 2) / 4)
    const hold = (held.get(v.mmsi) ?? 0) > now ? -2e12 : 0     // hysteresis: holders win ties inside their tier
    key[s] = t * 1e13 + hold + sec * 1e3 + dist
    idx.push(s)
  }
  idx.sort((a, b) => key[a] - key[b])

  // Greedy pass: caps, 1.5 × icon length separation (routine tiers only), fold the rest.
  const sep = view.hullPx * 1.5
  const grid = new Map<number, number[]>()
  const gk = (gx: number, gy: number) => gx * 65536 + gy
  const crowded = (x: number, y: number) => {
    const gx = Math.floor(x / sep), gy = Math.floor(y / sep)
    for (let i = -1; i <= 1; i++) for (let j = -1; j <= 1; j++) {
      for (const o of grid.get(gk(gx + i, gy + j)) ?? []) if (Math.hypot(px[o] - x, py[o] - y) < sep) return true
    }
    return false
  }
  const place = (s: number) => {
    const k = gk(Math.floor(px[s] / sep), Math.floor(py[s] / sep))
    const c = grid.get(k); if (c) c.push(s); else grid.set(k, [s])
  }
  const drawn: number[] = [], folded: number[] = [], overflow: number[] = []
  let shown = 0
  for (const s of idx) {
    const t = tier[s]
    if (t === 0) { drawn.push(s); place(s); if (!pinned.has(state.mmsi[s])) shown++; continue }
    if (t === 9 || shown >= cap) { overflow.push(s); continue }
    if (t > 4 && crowded(px[s], py[s])) { folded.push(s); continue }
    drawn.push(s); place(s); shown++
  }
  for (const s of drawn) held.set(state.mmsi[s], now + HOLD_S)
  if (held.size > 4 * cap + 1000) for (const [m, until] of held) if (until <= now) held.delete(m)

  // Folded ships: groups of 4+ within one hull length become a stack chip; at harbour zoom every leftover is a
  // "+N" chip (no cells there); otherwise the rest go to cells.
  const chips: Chip[] = []
  const toCells: number[] = band.name === 'harbour' ? [] : [...overflow]
  const harbour = band.name === 'harbour'
  const groupPx = harbour ? 64 : view.hullPx
  const groups = new Map<number, number[]>()
  for (const s of harbour ? folded.concat(overflow) : folded) {
    const k = gk(Math.floor(px[s] / groupPx), Math.floor(py[s] / groupPx))
    const g = groups.get(k); if (g) g.push(s); else groups.set(k, [s])
  }
  let stacked = 0
  for (const g of groups.values()) {
    if (!harbour && g.length < 4) { toCells.push(...g); continue }
    let sx = 0, sy = 0
    for (const s of g) { sx += px[s]; sy += py[s] }
    const cxp = sx / g.length, cyp = sy / g.length
    const mx = view.cx + (cxp - view.width / 2) / view.worldSize, my = view.cy + (cyp - view.height / 2) / view.worldSize
    chips.push({ lon: lonOf(mx), lat: latOf(my), mmsis: g.map((s) => state.mmsi[s]), plus: harbour })
    stacked += g.length
  }

  return { drawn, chips, cells: cellsOf(state, toCells, band), counts: { inView: idx.length, shown: drawn.length, stacked, inCells: toCells.length } }
}

// Aggregate cells: count per cell, 4 ink tints by the band's breaks, the count printed on the 6 busiest.
function cellsOf(state: ShipState, slots: number[], band: Band): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = []
  if (!band.cellDeg) return { type: 'FeatureCollection', features }
  const d = band.cellDeg
  const counts = new Map<string, number>()
  for (const s of slots) {
    const v = state.view[s]!
    const k = `${Math.floor(v.lat / d)}_${Math.floor(v.lon / d)}`
    counts.set(k, (counts.get(k) ?? 0) + 1)
  }
  const busiest = new Set([...counts].sort((a, b) => b[1] - a[1]).slice(0, 6).map(([k]) => k))
  for (const [k, n] of counts) {
    const [a, b] = k.split('_').map(Number)
    const lat = a * d, lon = b * d
    let cls = 0
    while (cls < 3 && n >= band.breaks[cls + 1]) cls++
    features.push({
      type: 'Feature',
      properties: { n, tint: CELL_TINT[cls], label: busiest.has(k) ? n.toLocaleString('en-GB') : '' },
      geometry: { type: 'Polygon', coordinates: [[[lon, lat], [lon + d, lat], [lon + d, lat + d], [lon, lat + d], [lon, lat]]] },
    })
  }
  return { type: 'FeatureCollection', features }
}

// "No receiver" cells: 0.1° coverage cells in state `dead` (cell_id = "<floor(lat×10)>_<floor(lon×10)>").
export function deadCells(coverage: Iterable<{ cell_id: string; state: string }>): GeoJSON.FeatureCollection {
  const features: GeoJSON.Feature[] = []
  for (const c of coverage) {
    if (c.state !== 'dead') continue
    const [a, b] = c.cell_id.split('_').map(Number)
    if (!Number.isFinite(a) || !Number.isFinite(b)) continue
    const lat = a / 10, lon = b / 10
    features.push({ type: 'Feature', properties: {}, geometry: { type: 'Polygon', coordinates: [[[lon, lat], [lon + 0.1, lat], [lon + 0.1, lat + 0.1], [lon, lat + 0.1], [lon, lat]]] } })
  }
  return { type: 'FeatureCollection', features }
}
