import { Popup, type GeoJSONSource, type Map as MapLibreMap, type MapMouseEvent } from 'maplibre-gl'
import { adapter } from '../data/index'
import { createStore } from '../store/store'
import { readToken } from '../theme/tokens'
import type { Observation } from '../types'

// Delayed-data layers (GFW and Sentinel-1 through GET /observations): radar detections, radar passes and GFW gap
// events. Each is off by default, remembered per viewer, and only on the map (source, layers, attribution, fetching)
// while switched on. Rows come for the current view, last 7 days, debounced on moveend, cached per view.

export type DelayedKey = 'detections' | 'passes' | 'gaps'
export const DELAYED: Record<DelayedKey, { label: string; kind: string; src: 'gfw' | 'sentinel1'; attribution: string }> = {
  detections: { label: 'Radar detections', kind: 'sar_detection', src: 'gfw', attribution: 'Global Fishing Watch, CC BY-NC 4.0' },
  passes: { label: 'Radar passes', kind: 'radar_scene', src: 'sentinel1', attribution: 'Contains modified Copernicus Sentinel data' },
  gaps: { label: 'GFW gap events', kind: 'gap', src: 'gfw', attribution: 'Global Fishing Watch, CC BY-NC 4.0' },
}
const KEYS = Object.keys(DELAYED) as DelayedKey[]
const LIMIT = 5000
const WEEK = 7 * 86_400_000
const STORE_KEY = 'poseidon.delayed'

interface DelayedState { on: Record<DelayedKey, boolean>; notes: Record<DelayedKey, string> }
const noNotes = { detections: '', passes: '', gaps: '' }

function saved(): Record<DelayedKey, boolean> {
  const off = { detections: false, passes: false, gaps: false }
  try {
    const raw = JSON.parse(localStorage.getItem(STORE_KEY) ?? '{}') ?? {}
    for (const k of KEYS) off[k] = raw[k] === true
  } catch { /* no storage or corrupt: all off */ }
  return off
}

export const delayed = createStore<DelayedState>({ on: saved(), notes: noNotes })

export function setDelayed(key: DelayedKey, on: boolean): void {
  const next = { ...delayed.get().on, [key]: on }
  try { localStorage.setItem(STORE_KEY, JSON.stringify(next)) } catch { /* private window: not remembered */ }
  delayed.set({ on: next })
}

const ID = (k: DelayedKey) => `dvm-dl-${k}`
const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const when = (ts: number) => { const d = new Date(ts); return `${d.getUTCDate()} ${MON[d.getUTCMonth()]} ${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}Z` }
const EMPTY: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] }
const num = (v: unknown): v is number => typeof v === 'number' && Number.isFinite(v)

function features(key: DelayedKey, rows: Observation[]): GeoJSON.Feature[] {
  const out: GeoJSON.Feature[] = []
  for (const o of rows) {
    if (key === 'passes') {
      if (o.geom) out.push({ type: 'Feature', properties: { tip: `Sentinel-1 radar pass · ${when(o.ts)}` }, geometry: o.geom })
      continue
    }
    if (o.lat == null || o.lon == null) continue
    const pt: GeoJSON.Point = { type: 'Point', coordinates: [o.lon, o.lat] }
    if (key === 'detections') {
      const matched = o.matched === true
      out.push({ type: 'Feature', properties: { matched, tip: matched ? `Radar detection matched to AIS · ${when(o.ts)}` : `Radar saw a hull with no AIS · ${when(o.ts)}` }, geometry: pt })
    } else {
      const hrs = o.value != null ? ` · off ${Math.round(o.value)} h` : ''
      out.push({ type: 'Feature', properties: { kind: 'off', tip: `AIS switched off offshore · ${when(o.ts)}${hrs}` }, geometry: pt })
      const a = o.attrs
      if (a && num(a.on_lat) && num(a.on_lon)) out.push({ type: 'Feature', properties: { kind: 'link' }, geometry: { type: 'LineString', coordinates: [[o.lon, o.lat], [a.on_lon, a.on_lat]] } })
    }
  }
  return out
}

function diamond(colour: string): { image: ImageData; ratio: number } {
  const c = document.createElement('canvas'); c.width = c.height = 28
  const g = c.getContext('2d')!
  g.strokeStyle = colour; g.lineWidth = 3; g.lineJoin = 'miter'
  g.beginPath(); g.moveTo(14, 3); g.lineTo(25, 14); g.lineTo(14, 25); g.lineTo(3, 14); g.closePath(); g.stroke()
  return { image: g.getImageData(0, 0, 28, 28), ratio: 2 }
}

export class DelayedMap {
  private map: MapLibreMap | null = null
  private unsub: (() => void) | null = null
  private timer: number | undefined
  private seq = 0
  private cache = new Map<string, Observation[]>()
  private popup = new Popup({ closeButton: false, closeOnClick: false, offset: 10, className: 'dvm-dl-tip' })

  attach(map: MapLibreMap): void {
    this.detach()
    this.map = map
    this.unsub = delayed.subscribe((s, p) => { if (s.on !== p.on) this.apply() })
    map.on('moveend', this.schedule)
    this.apply()
  }

  detach(): void {
    const map = this.map
    window.clearTimeout(this.timer); this.seq++
    this.unsub?.(); this.unsub = null
    if (map) {
      map.off('moveend', this.schedule)
      for (const k of KEYS) this.remove(map, k)
    }
    this.popup.remove()
    this.map = null
  }

  private apply(): void {
    const map = this.map
    if (!map) return
    const on = delayed.get().on
    for (const k of KEYS) { if (on[k]) this.ensure(map, k); else this.remove(map, k) }
    if (KEYS.some((k) => on[k])) this.schedule(); else { window.clearTimeout(this.timer); this.seq++ }
  }

  private ensure(map: MapLibreMap, k: DelayedKey): void {
    if (map.getSource(ID(k))) return
    map.addSource(ID(k), { type: 'geojson', data: EMPTY, attribution: DELAYED[k].attribution })
    const before = map.getLayer('dvm-chips') ? 'dvm-chips' : undefined   // under chips and ships
    const ink = readToken('text-secondary') || '#a5a99f', muted = readToken('text-muted') || '#a5a99f'
    const add = (layer: Parameters<MapLibreMap['addLayer']>[0]) => map.addLayer(layer, before)
    if (k === 'detections') {
      const d = diamond(readToken('ship-dark') || '#f26aa0')
      if (map.hasImage('dvm-dl-diamond')) map.removeImage('dvm-dl-diamond')
      map.addImage('dvm-dl-diamond', d.image, { pixelRatio: d.ratio })
      add({ id: `${ID(k)}-ok`, type: 'circle', source: ID(k), filter: ['==', ['get', 'matched'], true], paint: { 'circle-radius': 2, 'circle-color': muted, 'circle-opacity': 0.35 } })
      add({ id: `${ID(k)}-dark`, type: 'symbol', source: ID(k), filter: ['!=', ['get', 'matched'], true], layout: { 'icon-image': 'dvm-dl-diamond', 'icon-allow-overlap': true } })
    } else if (k === 'passes') {
      add({ id: `${ID(k)}-line`, type: 'line', source: ID(k), paint: { 'line-color': muted, 'line-width': 1, 'line-opacity': 0.4 } })
    } else {
      add({ id: `${ID(k)}-link`, type: 'line', source: ID(k), filter: ['==', ['get', 'kind'], 'link'], paint: { 'line-color': ink, 'line-width': 1, 'line-opacity': 0.4, 'line-dasharray': [2, 2] } })
      add({ id: `${ID(k)}-off`, type: 'circle', source: ID(k), filter: ['==', ['get', 'kind'], 'off'], paint: { 'circle-radius': 3.5, 'circle-color': ink, 'circle-stroke-color': readToken('bg-app') || '#000', 'circle-stroke-width': 1 } })
    }
    const hit = k === 'detections' ? `${ID(k)}-dark` : k === 'passes' ? `${ID(k)}-line` : `${ID(k)}-off`
    map.on('mousemove', hit, this.hover); map.on('mouseleave', hit, this.leave)
  }

  private remove(map: MapLibreMap, k: DelayedKey): void {
    if (!map.getSource(ID(k))) return
    for (const l of map.getStyle().layers.filter((l) => l.id.startsWith(`${ID(k)}-`))) {
      map.off('mousemove', l.id, this.hover); map.off('mouseleave', l.id, this.leave)
      map.removeLayer(l.id)
    }
    map.removeSource(ID(k))
    delayed.set((s) => ({ notes: { ...s.notes, [k]: '' } }))
  }

  private hover = (e: MapMouseEvent & { features?: GeoJSON.Feature[] }): void => {
    const tip = e.features?.[0]?.properties?.tip
    if (!tip || !this.map) return
    this.map.getCanvas().style.cursor = 'default'
    this.popup.setLngLat(e.lngLat).setText(String(tip)).addTo(this.map)
  }
  private leave = (): void => { this.popup.remove() }

  private schedule = (): void => {
    window.clearTimeout(this.timer)
    this.timer = window.setTimeout(() => void this.load(), 400)
  }

  private async load(): Promise<void> {
    const map = this.map
    if (!map || !adapter?.observations) return
    const seq = ++this.seq
    const b = map.getBounds()
    const bbox: [number, number, number, number] = [Math.max(-180, b.getWest()), Math.max(-85, b.getSouth()), Math.min(180, b.getEast()), Math.min(85, b.getNorth())]
    const end = Date.now(), hour = Math.floor(end / 3_600_000)
    for (const k of KEYS) {
      if (!delayed.get().on[k]) continue
      const key = `${k}|${bbox.map((v) => v.toFixed(1)).join(',')}|${hour}`
      let rows = this.cache.get(key)
      if (!rows) {
        try { rows = (await adapter.observations({ kinds: [DELAYED[k].kind], bbox, start: end - WEEK, end, limit: LIMIT })).observations }
        catch { rows = undefined }
        if (rows) { if (this.cache.size > 40) this.cache.clear(); this.cache.set(key, rows) }
      }
      if (seq !== this.seq || this.map !== map || !delayed.get().on[k]) return   // the view moved on or the layer went off
      if (!rows) continue
      ;(map.getSource(ID(k)) as GeoJSONSource | undefined)?.setData({ type: 'FeatureCollection', features: features(k, rows) })
      delayed.set((s) => ({ notes: { ...s.notes, [k]: rows.length >= LIMIT ? 'showing the latest 5,000' : '' } }))
    }
  }
}
