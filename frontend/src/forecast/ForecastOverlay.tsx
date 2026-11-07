import { useEffect, useState } from 'react'
import { Marker, type GeoJSONSource, type Map as MapLibreMap } from 'maplibre-gl'
import { adapter } from '../data/index'
import { useMapLayer } from '../map/context'
import { ui } from '../store/ui'
import { vessels } from '../store/vessels'
import { onTokensChange, readToken } from '../theme/tokens'
import { shownNow } from '../timeline/replay'
import { fmtDuration } from '../timeline/format'
import type { GapEvent, Outcome } from '../types'
import { ForecastCheck } from './ForecastCheck'
import { circle, ghostRadius } from './geo'
import { COVERAGE_FLAG_LABEL, HORIZON_MS, REASON_LABEL, RESOLVE_LAG_MS, pct } from './labels'
import { forecastUi } from './state'
import './forecast.css'

// Forecast overlay on the map: probability tags on ranked ships, growing ghost regions for open gaps with their labels,
// and outcome marks once a forecast's horizon has passed. Nothing after the shown time is drawn: everything reads the
// vessel store (which holds the state as of the shown time) and the shared clock shownNow().
export function ForecastOverlay() {
  const on = ui.use((s) => s.layers.forecast)
  const checkOpen = forecastUi.use((s) => s.checkOpen)
  // Colours are baked into paint and canvas images, so a theme, signals or text-size change rebuilds the layers.
  const [modes, setModes] = useState(0)
  useEffect(() => onTokensChange(() => setModes((n) => n + 1)), [])
  useMapLayer((map) => (on ? setup(map) : undefined), [on, modes])
  return checkOpen ? <ForecastCheck /> : null
}

const H = 3_600_000
const EMPTY = { type: 'FeatureCollection' as const, features: [] }
const tok = (name: string) => readToken(name) || '#888'
const IMAGES = ['fc-hatch-dark', 'fc-hatch-grey', 'fc-cross-dark', 'fc-cross-grey', 'fc-out-hit', 'fc-out-miss', 'fc-out-censored']

// Small canvas images (2x) for the map: hatch patterns, crosses, outcome squares, tag chips with a risk stripe.
function image(w: number, h: number, draw: (c: CanvasRenderingContext2D) => void): ImageData {
  const cv = document.createElement('canvas')
  cv.width = w * 2; cv.height = h * 2
  const c = cv.getContext('2d')!
  c.scale(2, 2)
  draw(c)
  return c.getImageData(0, 0, cv.width, cv.height)
}

function addImages(map: MapLibreMap) {
  const add = (id: string, data: ImageData, extra: object = {}) => { if (!map.hasImage(id)) map.addImage(id, data, { pixelRatio: 2, ...extra }) }
  const dark = tok('ship-dark'), muted = tok('text-muted'), ink = tok('text-primary'), panel = tok('bg-panel')
  for (const [k, col] of [['dark', dark], ['grey', muted]] as const) {
    add(`fc-hatch-${k}`, image(8, 8, (c) => {
      c.strokeStyle = col; c.globalAlpha = 0.55; c.lineWidth = 1
      c.beginPath(); c.moveTo(0, 8); c.lineTo(8, 0); c.moveTo(-2, 2); c.lineTo(2, -2); c.moveTo(6, 10); c.lineTo(10, 6); c.stroke()
    }))
    add(`fc-cross-${k}`, image(11, 11, (c) => {
      c.strokeStyle = col; c.lineWidth = 2; c.beginPath(); c.moveTo(2, 2); c.lineTo(9, 9); c.moveTo(9, 2); c.lineTo(2, 9); c.stroke()
    }))
  }
  add('fc-out-hit', image(9, 9, (c) => { c.fillStyle = ink; c.fillRect(1, 1, 7, 7) }))
  add('fc-out-miss', image(9, 9, (c) => { c.fillStyle = panel; c.fillRect(1, 1, 7, 7); c.strokeStyle = ink; c.lineWidth = 1; c.strokeRect(1.5, 1.5, 6, 6) }))
  add('fc-out-censored', image(9, 9, (c) => { c.fillStyle = panel; c.fillRect(1, 1, 7, 7); c.strokeStyle = muted; c.setLineDash([2, 1]); c.strokeRect(1.5, 1.5, 6, 6) }))
}

// Probability tag (56:56) drawn whole on a canvas, text included, so map glyph metrics can't push the text out of the
// chip. 1 px text/muted edge, 3 px risk stripe, rank in mono SemiBold, chance in mono, then a separator and the reason.
// The image carries a 10 px leader below-left of the chip; its bottom-left corner sits on the ship.
const LEAD = 10
function tagImage(band: number, rank: string, chance: string, reason: string): ImageData {
  const size = parseFloat(readToken('size-data')) || 12, h = (parseFloat(readToken('line-data')) || 16) + 2
  const mono = readToken('font-data'), sans = readToken('font-ui')
  const fonts = [`600 ${size}px ${mono}`, `400 ${size}px ${mono}`, `400 ${size}px ${sans}`]
  const m = document.createElement('canvas').getContext('2d')!
  const width = (text: string, i: number) => { m.font = fonts[i]; return Math.ceil(m.measureText(text).width) }
  const parts: [string, number, string][] = [[rank, 0, 'text-primary']]
  if (chance) parts.push([chance, 1, 'text-secondary'])
  if (reason) parts.push(['|', -1, 'border-subtle'], [reason, 2, 'text-secondary'])
  const w = 4 + parts.reduce((x, [t, f]) => x + 5 + (f < 0 ? 1 : width(t, f)), 0) + 5 + 1
  return image(w + LEAD, h + LEAD, (c) => {
    c.strokeStyle = tok('text-muted'); c.lineWidth = 1
    c.beginPath(); c.moveTo(1, h + LEAD - 1); c.lineTo(LEAD, h); c.stroke()
    c.fillStyle = tok('bg-panel'); c.fillRect(LEAD, 0, w, h)
    c.strokeRect(LEAD + 0.5, 0.5, w - 1, h - 1)
    c.fillStyle = tok(`risk-${band}`); c.fillRect(LEAD + 1, 1, 3, h - 2)
    c.textBaseline = 'middle'
    let x = LEAD + 4
    for (const [t, f, col] of parts) {
      x += 5
      c.fillStyle = tok(col)
      if (f < 0) { c.fillRect(x, (h - 12) / 2, 1, 12); x += 1; continue }
      c.font = fonts[f]; c.fillText(t, x, h / 2 + 0.5); x += width(t, f)
    }
  })
}

const band = (p: number) => (p >= 0.75 ? 4 : p >= 0.5 ? 3 : p >= 0.25 ? 2 : 1)
const zoomTier = (z: number) => (z < 7 ? 0 : z < 11 ? 1 : 2)          // far / mid / near (forecast report)
const CAP = [5, 10, 20]

function setup(map: MapLibreMap): () => void {
  addImages(map)
  const dark = tok('ship-dark'), muted = tok('text-muted')
  const before = map.getStyle().layers.find((l) => l.type === 'symbol')?.id   // ghosts sit under labels and ships
  for (const id of ['fc-ghost', 'fc-ghost-pt', 'fc-tags', 'fc-out']) map.addSource(id, { type: 'geojson', data: EMPTY })
  map.addLayer({ id: 'fc-ghost-fill', type: 'fill', source: 'fc-ghost',
    paint: { 'fill-color': ['match', ['get', 'kind'], 'dark', tok('ship-ghost-fill'), tok('coverage-dead')] } }, before)
  map.addLayer({ id: 'fc-ghost-hatch', type: 'fill', source: 'fc-ghost',
    paint: { 'fill-pattern': ['match', ['get', 'kind'], 'dark', 'fc-hatch-dark', 'fc-hatch-grey'] } }, before)
  // The edge uses full ship/dark: ship/ghost-edge (75 %) fails 3:1 on water in Dark (forecast report).
  map.addLayer({ id: 'fc-ghost-edge', type: 'line', source: 'fc-ghost',
    paint: { 'line-color': ['match', ['get', 'kind'], 'dark', dark, muted], 'line-width': 1.5, 'line-dasharray': [3, 2] } }, before)
  map.addLayer({ id: 'fc-ghost-cross', type: 'symbol', source: 'fc-ghost-pt',
    layout: { 'icon-image': ['match', ['get', 'kind'], 'dark', 'fc-cross-dark', 'fc-cross-grey'], 'icon-allow-overlap': true, 'icon-ignore-placement': true } })
  map.addLayer({ id: 'fc-out', type: 'symbol', source: 'fc-out',
    layout: { 'icon-image': ['concat', 'fc-out-', ['get', 'label']], 'icon-offset': [-11, 11], 'icon-allow-overlap': true } })
  map.addLayer({ id: 'fc-tags', type: 'symbol', source: 'fc-tags',
    layout: { 'icon-image': ['get', 'img'], 'icon-anchor': 'bottom-left', 'icon-allow-overlap': true, 'symbol-sort-key': ['get', 'rank'] } })

  // ---- probability tags: watchlist Inspect/Watch with p >= 0.10, capped per zoom tier; no tag on an open gap or open window
  let tier = zoomTier(map.getZoom())
  const tagImages = new Set<string>()      // shortcut: tag images are never evicted while the layer lives; fine for ~40 ranked ships
  const drawTags = () => {
    const open = new Set(ui.get().windows.map((w) => w.mmsi))
    const rows = vessels.watchlist?.entries.filter((e) => e.decision !== 'none' && e.p >= 0.1).map((e) => ({ mmsi: e.mmsi, p: e.p, rank: e.rank, codes: e.reason_codes }))
      ?? [...vessels.vessels.values()].filter((v) => v.risk_rank != null && (v.risk_p ?? 0) >= 0.1).map((v) => ({ mmsi: v.mmsi, p: v.risk_p!, rank: v.risk_rank!, codes: [] as string[] }))
    const features = rows.sort((a, b) => a.rank - b.rank).flatMap((r) => {
      const v = vessels.vessels.get(r.mmsi)
      if (!v || v.status === 'gap_open' || open.has(r.mmsi)) return []
      const rank = String(r.rank).padStart(2, '0')
      const chance = tier > 0 ? pct(r.p) : ''
      const reason = tier > 1 ? REASON_LABEL[r.codes.find((c) => c !== 'OPEN_GAP') ?? ''] ?? '' : ''
      const img = `fc-tag-${band(r.p)}-${rank}-${chance}-${reason}`
      return [{ type: 'Feature' as const, geometry: { type: 'Point' as const, coordinates: [v.lon, v.lat] }, properties: { img, band: band(r.p), rank: r.rank, chance, reason, label: rank } }]
    }).slice(0, CAP[tier])
    for (const { properties: f } of features) {
      if (map.hasImage(f.img)) continue
      map.addImage(f.img, tagImage(f.band, f.label, f.chance, f.reason), { pixelRatio: 2 })
      tagImages.add(f.img)
    }
    map.getSource<GeoJSONSource>('fc-tags')?.setData({ type: 'FeatureCollection', features })
  }

  // ---- ghosts: open gaps (not own_stall) as of the shown time; radius grows every animation frame while one is on screen
  let gaps: GapEvent[] = []
  const labels = new Map<string, { m: Marker; el: HTMLDivElement }>()
  let hoverGap: string | null = null
  const syncGaps = () => {
    const t = shownNow()
    gaps = [...vessels.gaps.values()].filter((g) => g.state === 'open' && g.start_ts <= t && g.coverage_flag !== 'own_stall')
    map.getSource<GeoJSONSource>('fc-ghost-pt')?.setData({ type: 'FeatureCollection', features: gaps.map((g) => ({
      type: 'Feature', geometry: { type: 'Point', coordinates: [g.last_lon, g.last_lat] }, properties: { kind: kindOf(g) } })) })
    syncLabels(t)
  }
  const syncLabels = (t: number) => {
    const open = new Set(ui.get().windows.map((w) => w.mmsi))
    const far = map.getZoom() < 7
    for (const [id, l] of labels) if (!gaps.some((g) => g.id === id)) { l.m.remove(); labels.delete(id) }
    for (const g of gaps) {
      let l = labels.get(g.id)
      if (!l) {
        // MapLibre owns the marker element's inline opacity, so the label (and its hidden state) is a child of it.
        const wrap = document.createElement('div')
        const el = wrap.appendChild(document.createElement('div'))
        el.className = `fc-gap-label ${kindOf(g)}`
        l = { m: new Marker({ element: wrap, anchor: 'left', offset: [14, 0] }).setLngLat([g.last_lon, g.last_lat]).addTo(map), el }
        labels.set(g.id, l)
      }
      const r = ghostRadius(g, t)
      const dur = fmtDuration(t - g.start_ts)
      const head = g.coverage_flag === 'deliberate_candidate' ? `No AIS ${dur} · within ${(r / 1000).toFixed(1)} km` : `No AIS ${dur} · ${COVERAGE_FLAG_LABEL[g.coverage_flag]}`
      const sub = g.coverage_flag === 'deliberate_candidate'
        ? `Reception normal nearby (${g.neighbours_heard} ships heard within 20 km)${g.last_sog_kn != null ? ` · last ${g.last_sog_kn.toFixed(1)} kn` : ''}${g.last_cog_deg != null ? `, ${String(Math.round(g.last_cog_deg)).padStart(3, '0')}°` : ''}`
        : `${g.neighbours_heard} ships heard within 20 km. Not counted as a silence.`
      if (l.el.dataset.head !== head) { l.el.dataset.head = head; l.el.innerHTML = `<b></b><span></span>`; l.el.firstChild!.textContent = head; l.el.lastChild!.textContent = sub }
      l.el.classList.toggle('hidden', open.has(g.mmsi) || (far && hoverGap !== g.id))
    }
  }
  const kindOf = (g: GapEvent) => (g.coverage_flag === 'deliberate_candidate' ? 'dark' : 'grey')
  // Each rAF, but setData (a worker re-tile) only when a visible ghost grew by half a pixel or the visible set changed:
  // at 1x a 10 kn ghost grows a pixel a minute at z8, so sub-pixel updates are invisible and cost ~10 fps at 25k ships.
  let raf = 0
  let drawn = new Map<string, number>()
  const tick = () => {
    raf = requestAnimationFrame(tick)
    if (document.hidden) return
    if (!gaps.length) { if (drawn.size) { drawn = new Map(); map.getSource<GeoJSONSource>('fc-ghost')?.setData(EMPTY) } return }
    const t = shownNow()
    const b = map.getBounds()
    const vis = gaps.map((g) => ({ g, r: ghostRadius(g, t) }))
      .filter(({ g, r }) => { const d = r / 111_320 * 2; return g.last_lat + d > b.getSouth() && g.last_lat - d < b.getNorth() && g.last_lon + d * 2 > b.getWest() && g.last_lon - d * 2 < b.getEast() })
    const mpp = (40_075_016 * Math.cos((map.getCenter().lat * Math.PI) / 180)) / (512 * 2 ** map.getZoom())   // metres per CSS px
    const same = vis.length === drawn.size && vis.every(({ g, r }) => { const r0 = drawn.get(g.id); return r0 !== undefined && Math.abs(r - r0) < mpp / 2 })
    if (same) return
    drawn = new Map(vis.map(({ g, r }) => [g.id, r]))
    const features = vis.map(({ g, r }) => ({ type: 'Feature' as const, properties: { kind: kindOf(g), id: g.id }, geometry: { type: 'Polygon' as const, coordinates: [circle(g.last_lon, g.last_lat, r)] } }))
    map.getSource<GeoJSONSource>('fc-ghost')?.setData({ type: 'FeatureCollection', features })
  }
  raf = requestAnimationFrame(tick)
  const onEnter = (e: { features?: { properties: Record<string, unknown> }[] }) => { hoverGap = String(e.features?.[0]?.properties.id ?? ''); syncLabels(shownNow()) }
  const onLeave = () => { hoverGap = null; syncLabels(shownNow()) }
  map.on('mousemove', 'fc-ghost-fill', onEnter)
  map.on('mouseleave', 'fc-ghost-fill', onLeave)

  // ---- outcome marks: the newest forecast whose horizon has passed at the shown time (top 10), at each ship
  let outKey = -1
  let outcomes: Outcome[] = []
  const drawOutcomes = () => {
    const features = outcomes.flatMap((o) => {
      const v = vessels.vessels.get(o.mmsi)
      return v ? [{ type: 'Feature' as const, geometry: { type: 'Point' as const, coordinates: [v.lon, v.lat] }, properties: { label: o.censored ? 'censored' : o.label } }] : []
    })
    map.getSource<GeoJSONSource>('fc-out')?.setData({ type: 'FeatureCollection', features })
  }
  const syncOutcomes = () => {
    const made = Math.floor((shownNow() - HORIZON_MS - RESOLVE_LAG_MS) / H) * H
    if (made === outKey || !adapter) return drawOutcomes()
    outKey = made
    const resolved = made + HORIZON_MS + RESOLVE_LAG_MS
    adapter.outcomes(resolved, resolved).then((os) => { if (outKey === made) { outcomes = os.filter((o) => o.made_at === made); drawOutcomes() } }, () => { outcomes = [] })
  }

  const all = () => { drawTags(); syncGaps(); syncOutcomes() }
  let live = true
  // Tags drawn before the web fonts finished loading used a fallback face: redraw them once they are ready.
  document.fonts.ready.then(() => {
    if (!live || !map.style) return
    for (const id of tagImages) if (map.hasImage(id)) map.removeImage(id)
    tagImages.clear(); drawTags()
  })
  all()
  const offV = vessels.subscribe(all)
  const offUi = ui.subscribe((s, p) => { if (s.windows !== p.windows) { drawTags(); syncLabels(shownNow()) } })
  const onZoom = () => { const z = zoomTier(map.getZoom()); if (z !== tier) { tier = z; drawTags() } syncLabels(shownNow()) }
  map.on('zoomend', onZoom)
  const labelTimer = window.setInterval(() => gaps.length && syncLabels(shownNow()), 1000)

  return () => {
    live = false; cancelAnimationFrame(raf); window.clearInterval(labelTimer); offV(); offUi()
    map.off('zoomend', onZoom); map.off('mousemove', 'fc-ghost-fill', onEnter); map.off('mouseleave', 'fc-ghost-fill', onLeave)
    for (const l of labels.values()) l.m.remove()
    if (!map.style) return                                   // style already torn down by a swap
    for (const id of ['fc-tags', 'fc-out', 'fc-ghost-cross', 'fc-ghost-edge', 'fc-ghost-hatch', 'fc-ghost-fill']) if (map.getLayer(id)) map.removeLayer(id)
    for (const id of ['fc-ghost', 'fc-ghost-pt', 'fc-tags', 'fc-out']) if (map.getSource(id)) map.removeSource(id)
    for (const id of [...IMAGES, ...tagImages]) if (map.hasImage(id)) map.removeImage(id)
  }
}
