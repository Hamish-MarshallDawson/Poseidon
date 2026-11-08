import type { ExpressionSpecification, GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import { getTrack } from '../data/track'
import { ui } from '../store/ui'
import { TRAIL_MS, vessels } from '../store/vessels'
import { shownNow } from '../timeline/replay'
import { onTokensChange, readToken } from '../theme/tokens'

// Past track of every selected ship (an open ship window, or the focused ship): one GeoJSON source, drawn as a solid
// accent line with a thin bg/app casing that fades with age, a dot at each fix, a start ring and an oldest-time label.
// Data: the store's trail (live detail trail + deltas), prepended with GET /track (24 h) once per ship.

type Trail = [number, number, number][]   // [ts, lon, lat]

export const TRACK_BREAK_MS = 15 * 60000   // fixes further apart than this are separate segments, not a straight jump
const PASS_MS = 1000                       // the geometry changes with 1 Hz data

const ID = { src: 'dvm-track', casing: 'dvm-track-casing', line: 'dvm-track-line', fix: 'dvm-track-fix', start: 'dvm-track-start', label: 'dvm-track-label' }
const FONT = ['Barlow Semi Condensed Medium']   // the map font has no U+2212, so the label uses an ASCII hyphen

/** "-58 min" / "-6 h 20 min" / "-24 h": how far back a track reaches. */
export function trackAgeLabel(ms: number): string {
  const min = Math.round(ms / 60000)
  if (min < 60) return `-${Math.max(1, min)} min`
  const h = Math.floor(min / 60), m = min % 60
  return m && h < 10 ? `-${h} h ${m} min` : `-${Math.round(min / 60)} h`
}

/** Features for one ship's trail ending at its latest fix. */
export function trackFeatures(trail: Trail, last: [number, number, number], nowMs: number): GeoJSON.Feature[] {
  const pts = trail.filter((p) => p[0] >= nowMs - TRAIL_MS)
  if (last[0] > (pts[pts.length - 1]?.[0] ?? -Infinity)) pts.push(last)
  if (pts.length < 2) return []
  const out: GeoJSON.Feature[] = []
  const t0 = pts[0][0], span = Math.max(1, pts[pts.length - 1][0] - t0)
  for (let i = 1; i < pts.length; i++) {
    if (pts[i][0] - pts[i - 1][0] > TRACK_BREAK_MS) continue
    out.push({ type: 'Feature', properties: { kind: 'line', age: (pts[i][0] - t0) / span }, geometry: { type: 'LineString', coordinates: [[pts[i - 1][1], pts[i - 1][2]], [pts[i][1], pts[i][2]]] } })
  }
  for (const p of pts.slice(1)) out.push({ type: 'Feature', properties: { kind: 'fix' }, geometry: { type: 'Point', coordinates: [p[1], p[2]] } })
  out.push({ type: 'Feature', properties: { kind: 'start', label: trackAgeLabel(span) }, geometry: { type: 'Point', coordinates: [pts[0][1], pts[0][2]] } })
  return out
}

/** Follow mode: one ship's track in the replay range, solid up to the head and faint (age 0, lines only) after it. */
export function followFeatures(track: Trail, head: number, range: { from_ts: number; to_ts: number } | null): GeoJSON.Feature[] {
  const pts = range ? track.filter((p) => p[0] >= range.from_ts && p[0] <= range.to_ts) : track
  const i = pts.findIndex((p) => p[0] > head)
  const past = i < 0 ? pts : pts.slice(0, i)
  const out = past.length > 1 ? trackFeatures(past, past[past.length - 1], past[0][0] + TRAIL_MS) : []
  const future = i < 0 ? [] : pts.slice(Math.max(0, i - 1))
  for (let k = 1; k < future.length; k++) {
    if (future[k][0] - future[k - 1][0] > TRACK_BREAK_MS) continue
    out.push({ type: 'Feature', properties: { kind: 'line', age: 0 }, geometry: { type: 'LineString', coordinates: [[future[k - 1][1], future[k - 1][2]], [future[k][1], future[k][2]]] } })
  }
  return out
}

export class TrackRenderer {
  private map: MapLibreMap | null = null
  private last = 0
  private timer: number | undefined
  private asked = new Set<number>()
  private followTracks = new Map<number, Trail>()   // the 24 h read per followed ship, for the replay head
  private headTimer: number | undefined
  private unTokens = onTokensChange(() => this.recolour())

  attach(map: MapLibreMap): void {
    this.map = map
    if (!map.getSource(ID.src)) map.addSource(ID.src, { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
    const kind = (k: string) => ['==', ['get', 'kind'], k] as ['==', ['get', string], string]
    const fade = (hi: number) => ['interpolate', ['linear'], ['get', 'age'], 0, hi * 0.25, 1, hi] as ExpressionSpecification
    const round = { 'line-cap': 'round' as const, 'line-join': 'round' as const }
    map.addLayer({ id: ID.casing, type: 'line', source: ID.src, filter: kind('line'), layout: round, paint: { 'line-width': 5.5, 'line-opacity': fade(0.7) } })
    map.addLayer({ id: ID.line, type: 'line', source: ID.src, filter: kind('line'), layout: round, paint: { 'line-width': 3, 'line-opacity': fade(1) } })
    map.addLayer({ id: ID.fix, type: 'circle', source: ID.src, filter: kind('fix'), paint: { 'circle-radius': 2.5, 'circle-stroke-width': 1 } })
    map.addLayer({ id: ID.start, type: 'circle', source: ID.src, filter: kind('start'), paint: { 'circle-radius': 6, 'circle-stroke-width': 2.5 } })
    map.addLayer({
      id: ID.label, type: 'symbol', source: ID.src, filter: kind('start'),
      layout: { 'text-field': ['get', 'label'], 'text-font': FONT, 'text-size': 12, 'text-anchor': 'top', 'text-offset': [0, 1.2], 'text-allow-overlap': true },
      paint: { 'text-halo-width': 1.5 },
    })
    this.recolour()
    this.touch(true)
  }

  remove(map: MapLibreMap): void {
    for (const id of [ID.label, ID.start, ID.fix, ID.line, ID.casing]) if (map.getLayer(id)) map.removeLayer(id)
    if (map.getSource(ID.src)) map.removeSource(ID.src)
  }

  dispose(): void { window.clearTimeout(this.timer); window.clearInterval(this.headTimer); this.unTokens(); this.map = null }

  private recolour(): void {
    const map = this.map
    if (!map?.getLayer(ID.line)) return
    const accent = readToken('accent-default') || '#86c9e8', casing = readToken('bg-app') || '#15232d', ink = readToken('text-primary') || '#eee9dc'
    map.setPaintProperty(ID.casing, 'line-color', casing)
    map.setPaintProperty(ID.line, 'line-color', accent)
    map.setPaintProperty(ID.fix, 'circle-color', accent); map.setPaintProperty(ID.fix, 'circle-stroke-color', casing)
    map.setPaintProperty(ID.start, 'circle-color', casing); map.setPaintProperty(ID.start, 'circle-stroke-color', accent)
    map.setPaintProperty(ID.label, 'text-color', ink); map.setPaintProperty(ID.label, 'text-halo-color', casing)
  }

  /** Data or selection changed: redraw at most once a second (now = selection changed, so redraw straight away). */
  touch(now = false): void {
    if (!this.map) return
    if (now) { window.clearTimeout(this.timer); this.timer = undefined; this.draw(); return }
    if (this.timer !== undefined) return
    this.timer = window.setTimeout(() => { this.timer = undefined; this.draw() }, Math.max(0, PASS_MS - (performance.now() - this.last)))
  }

  private draw(): void {
    const src = this.map?.getSource(ID.src) as GeoJSONSource | undefined
    if (!src) return
    this.last = performance.now()
    const s = ui.get()
    window.clearInterval(this.headTimer)
    if (s.follow) {
      // The head moves with the replay clock: re-split at 4 Hz, not per frame.
      this.headTimer = window.setInterval(() => this.draw(), 250)
      const head = s.time.dragT ?? shownNow()
      const features: GeoJSON.Feature[] = []
      for (const w of s.windows) {
        const t = this.followTracks.get(w.mmsi)
        if (t) features.push(...followFeatures(t, head, s.feed.replay))
        else this.askFollow(w.mmsi)
      }
      src.setData({ type: 'FeatureCollection', features })
      return
    }
    const sel = new Set<number>(s.windows.map((w) => w.mmsi))
    if (s.focusMmsi != null) sel.add(s.focusMmsi)
    const features: GeoJSON.Feature[] = []
    const nowMs = vessels.now_ts || Date.now()
    for (const mmsi of sel) {
      const v = vessels.vessels.get(mmsi)
      if (!v) continue
      this.ask(mmsi)
      features.push(...trackFeatures(vessels.trails.get(mmsi) ?? [], [v.last_ts, v.lon, v.lat], nowMs))
    }
    src.setData({ type: 'FeatureCollection', features })
  }

  private askFollow(mmsi: number): void {
    if (this.followTracks.has(mmsi) || this.asked.has(-mmsi)) return
    this.asked.add(-mmsi)
    getTrack(mmsi, 24).then((t) => { this.followTracks.set(mmsi, t); this.touch(true) }, () => { this.asked.delete(-mmsi) })
  }

  // The 24 h read, once per ship per session (getTrack caches it for a minute); failures keep the live trail.
  private ask(mmsi: number): void {
    if (this.asked.has(mmsi)) return
    this.asked.add(mmsi)
    getTrack(mmsi, 24).then((track) => {
      const live = vessels.trails.get(mmsi) ?? []
      const from = live[0]?.[0] ?? Infinity
      const older = track.filter((p) => p[0] < from)
      if (older.length) { vessels.setTrail(mmsi, [...older, ...live]); this.touch(true) }
    }, () => { /* no /track on this backend or no feed: the live trail stays */ })
  }
}
