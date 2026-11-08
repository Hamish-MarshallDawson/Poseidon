import type { GeoJSONSource, Map as MapLibreMap, MapMouseEvent } from 'maplibre-gl'
import { TrackRenderer } from '../track'
import type { VesselView } from '../../types'
import { ui, type UIState } from '../../store/ui'
import { vessels, type Frame } from '../../store/vessels'
import { readToken } from '../../theme/tokens'
import { themeStore } from '../../theme/theme'
import { rgba } from '../colour'
import { computeSlots, deadCells, bandOf, HEAT_FADE, type Chip, type View } from '../density'
import { inferredSegment, openGap } from '../focus'
import { headingOf, lonOf, latOf, mercX, mercY, sizeTier, type SizeTier } from '../geo'
import { isFull, OPACITY, ringOffsets, sortKey, zTier, FAN_RADIUS, type Rank } from '../stacking'
import { openShipWindow } from '../actions'
import { BASEMAP_FIRST_LABEL_LAYER } from '../../basemap'
import { Colour, createShipLayer, InstanceBuffer, N_COLOURS, writeMotion, type ShipLayerHooks } from './layer'
import { buildAtlas, hullKey, TIERS, TYPES, type HullType, type Sprite } from './sprites'
import { CourseLine } from './course'
import { shownNow } from '../../timeline/replay'
import { DelayedMap } from '../delayed'
import { ghostOf } from '../../forecast/geo'
import { clock, setShownClock, ShipState } from './state'
import { yachts, yachtBadge } from '../../yachts/store'
import { showFilter } from '../../show/registry'

setShownClock(shownNow)

// Owns everything ship-shaped on the map: per-ship motion state (typed arrays), the slot pass (caps, priority,
// separation, hysteresis), the GPU layer, heat map, stack chips, fan-out and hit-testing.
// Nothing here runs per ship per frame on the CPU: the vertex shader animates; the CPU rebuilds the (capped) instance
// list only when a fix arrives for a drawn ship, a slot changes, or the selection changes.

const HULL_LEN: Record<SizeTier, number> = { far: 16, mid: 32, near: 64 }
const OVERLAY_BOX: Record<SizeTier, number> = { far: 25, mid: 43, near: 80 }   // drawn bracket box incl. stroke (Figma export)
const BADGE: Record<SizeTier, number> = { far: 5, mid: 7, near: 10 }
const SPOOF_OFFSET: Record<SizeTier, number> = { far: 5, mid: 7, near: 10 }
const CLASS_B_SCALE = 0.75              // Class B hull size: the non-colour cue next to the violet colour
const SLOT_FADE_S = 0.15, DIM_FADE_S = 0.2
const DATA_PASS_MS = 2000               // slot pass for new data at most this often while the map is still
const PAD = 0.15                        // fraction of the viewport added on each side for culling

const L = {
  heat: 'dvm-heat', dead: 'dvm-dead', deadEdge: 'dvm-dead-edge',
  inferred: 'dvm-inferred', chips: 'dvm-chips', fan: 'dvm-fan', ships: 'dvm-ships',
}
const HEAT_OPACITY = 0.7
const S = { heat: 'dvm-heat', dead: 'dvm-dead', inferred: 'dvm-inferred', chips: 'dvm-chips', fan: 'dvm-fan' }
const EMPTY: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] }
const FONT = ['Barlow Semi Condensed Medium']   // served from public/basemap/fonts (scripts/basemap/glyphs.py)

const hullType = (t: VesselView['type_group']): HullType =>
  t === 'tanker' || t === 'cargo' || t === 'fishing' || t === 'passenger' ? t : 'other'

// Same sprite, colour and overlays (only position, course or heading changed).
const sameLook = (a: VesselView, b: VesselView) =>
  a.status === b.status && a.sanctioned === b.sanctioned && a.spoof_recent.length === b.spoof_recent.length &&
  a.type_group === b.type_group && a.length_m === b.length_m && a.risk_rank === b.risk_rank &&
  (headingOf(a.heading_deg, a.cog_deg) == null) === (headingOf(b.heading_deg, b.cog_deg) == null)

interface Fade { from: number; to: number; t: number; dur: number; leaving: boolean }
interface Hit { mmsi: number; slot: number; offX: number; offY: number; r: number }
interface Fan { mmsis: number[]; offsets: Map<number, [number, number]>; lon: number; lat: number }

export interface ControllerOptions { capOverride?: number }

export class ShipController {
  readonly state = new ShipState()
  private atlas = buildAtlas()
  private buf = new InstanceBuffer(this.atlas, this.state)
  private gpu: ReturnType<typeof createShipLayer>
  private map: MapLibreMap | null = null
  private drawn: number[] = []                       // mmsis that hold a slot
  private drawnSet = new Set<number>()
  private chips: Chip[] = []
  private held = new Map<number, number>()
  private fades = new Map<number, Fade>()
  private hits: Hit[] = []
  private ranks = new Map<number, Rank>()
  private fan: Fan | null = null
  private lastPass = 0
  private passTimer: number | undefined
  private fadeTimer: number | undefined
  private colourCache = { list: new Float32Array(N_COLOURS * 4), key: new Float32Array(3), dim: 0.45 }
  private unsubs: (() => void)[] = []
  private tmp = new Float64Array(2)
  private course = new CourseLine(this.state)
  private delayed = new DelayedMap()
  private instHead = new Int32Array(0)               // slot → first instance (linked through instNext), -1 = none
  private instNext = new Int32Array(0)
  private pending = new Set<number>()
  private selectionChanged = true                // slots whose motion changed since the last fill/patch
  /** performance.now() of the first frame that drew ships (for the first-ship-frame measurement). */
  firstShipFrame = 0
  private opts: ControllerOptions
  private track = new TrackRenderer()

  // Hull sprites by (type, tier, hollow, heading), so the rebuild never builds a string per ship.
  private hullSprites: (Sprite | undefined)[] = []
  private hullSprite(type: HullType, tier: SizeTier, hollow: boolean, heading: boolean): Sprite | undefined {
    return this.hullSprites[((TYPES.indexOf(type) * 3 + TIERS.indexOf(tier)) * 2 + (hollow ? 1 : 0)) * 2 + (heading ? 1 : 0)]
  }

  constructor(opts: ControllerOptions = {}) {
    this.opts = opts
    for (const type of TYPES) for (const tier of TIERS) for (const hollow of [false, true]) for (const heading of [false, true]) {
      this.hullSprites[((TYPES.indexOf(type) * 3 + TIERS.indexOf(tier)) * 2 + (hollow ? 1 : 0)) * 2 + (heading ? 1 : 0)] = this.atlas.sprites.get(hullKey(type, tier, hollow, heading))
    }
    const hooks: ShipLayerHooks = { rebuild: (b) => this.rebuild(b), patch: (b) => this.patch(b), colours: () => this.colourCache }
    this.gpu = createShipLayer(L.ships, this.atlas, this.buf, hooks)
    this.readColours()
    this.state.reducedMotion = themeStore.get().reducedMotion
    // Ships already in the store (the feed may have started before the map).
    for (const v of vessels.vessels.values()) this.state.upsert(v, clock())
    this.updateRanks()
    this.unsubs.push(
      vessels.subscribe((changed, removed, frame) => this.onFrame(changed, removed, frame)),
      ui.subscribe((s, p) => this.onUi(s, p)),
      yachts.subscribe(() => { this.gpu.invalidate(); if (ui.get().show !== 'all') this.slotPass() }),   // yacht badges (#101); the yachts filter matches on this list
      themeStore.subscribe((s, p) => { this.state.reducedMotion = s.reducedMotion; if (s.classColour !== p.classColour) this.gpu.invalidate() }),
    )
  }

  // ---- map lifecycle -------------------------------------------------------------------------------------------

  /** Add sources and layers. Called after every style load (theme swaps rebuild the style). */
  attach(map: MapLibreMap): void {
    const first = this.map !== map
    this.map = map
    this.readColours()
    this.addImages(map)
    const add = (id: string, data = EMPTY) => { if (!map.getSource(id)) map.addSource(id, { type: 'geojson', data }) }
    add(S.heat); add(S.dead, deadCells(vessels.coverage.values())); add(S.inferred); add(S.chips); add(S.fan)
    const ink = readToken('text-primary') || '#eee9dc'
    // Density and no-receiver fills go under the basemap's land, so cells never tint land (dashboard map, layer 2 of 4).
    const underLand = map.getLayer('coast-land') ? 'coast-land' : undefined
    // Heat map (zoomed out): ship counts on a screen grid, ramp from the heat/0..4 tokens, faded out across HEAT_FADE as the
    // ships fade in. Under the place labels so names stay readable; the no-receiver hatch is a different thing (grey pattern, dashed edge).
    const heat = (i: number, fb: string) => readToken(`heat-${i}`) || fb
    // Traditional ramp (blue, cyan, green, yellow, orange, red; viridis for colour-blind): low alpha and radius, so no bloom.
    const stops = [0, 0.1, 0.25, 0.4, 0.55, 0.75, 1]
    const fallback = ['#2f5fd000', '#2f5fd040', '#1fb5d861', '#3cb86775', '#e6d02a85', '#f08a1c91', '#d62a1f99']
    map.addLayer({
      id: L.heat, type: 'heatmap', source: S.heat,
      paint: {
        'heatmap-weight': ['interpolate', ['linear'], ['get', 'n'], 1, 0.35, 6, 0.75, 40, 1],
        'heatmap-intensity': ['interpolate', ['linear'], ['zoom'], 0, 0.6, 4, 0.8, 7, 0.9],
        'heatmap-radius': ['interpolate', ['linear'], ['zoom'], 0, 12, 4, 16, 7, 22],
        'heatmap-color': ['interpolate', ['linear'], ['heatmap-density'], ...stops.flatMap((d, i) => [d, heat(i, fallback[i])])],
        'heatmap-opacity': ['interpolate', ['linear'], ['zoom'], HEAT_FADE[0], HEAT_OPACITY, HEAT_FADE[1], 0],
      },
    }, map.getLayer(BASEMAP_FIRST_LABEL_LAYER) ? BASEMAP_FIRST_LABEL_LAYER : underLand)
    map.addLayer({ id: L.dead, type: 'fill', source: S.dead, paint: { 'fill-pattern': 'dvm-hatch', 'fill-antialias': false } }, underLand)
    map.addLayer({
      id: L.deadEdge, type: 'line', source: S.dead,
      paint: { 'line-color': readToken('coverage-dead') || '#888', 'line-width': 1, 'line-dasharray': [3, 2] },
    })
    this.track.attach(map)
    map.addLayer({ id: L.inferred, type: 'line', source: S.inferred, paint: { 'line-color': readToken('accent-default') || '#86c9e8', 'line-width': 1.5, 'line-dasharray': [3, 3] } })
    map.addLayer({
      id: L.chips, type: 'symbol', source: S.chips,
      layout: {
        'icon-image': 'dvm-chip', 'icon-allow-overlap': true, 'icon-ignore-placement': true,
        'icon-size': ['step', ['length', ['get', 'label']], 0.8, 2, 1, 3, 1.25],   // the disc grows with the digits
        'text-field': ['get', 'label'], 'text-font': FONT, 'text-size': 10, 'text-allow-overlap': true, 'text-ignore-placement': true,
        'text-offset': [0, 1.05],   // this font's glyphs sit above the anchor; centres the count on the disc
      },
      paint: { 'text-color': ink, 'icon-opacity': 0.85 },
    })
    map.addLayer({ id: L.fan, type: 'line', source: S.fan, paint: { 'line-color': ink, 'line-width': 1, 'line-opacity': 0.5 } })
    this.gpu = createShipLayer(L.ships, this.atlas, this.buf, { rebuild: (b) => this.rebuild(b), patch: (b) => this.patch(b), colours: () => this.colourCache })
    map.addLayer(this.gpu.layer)
    this.course.attach(map)
    this.delayed.attach(map)
    this.applyLayerVisibility(ui.get().layers)
    if (first) {
      map.on('moveend', this.onMoveEnd)
      map.on('zoom', this.onZoom)
      map.on('movestart', this.onMoveStart)
      map.on('click', this.onClick)
      map.on('mousemove', this.onMouseMove)
      map.on('mouseout', this.onMouseOut)
    }
    this.slotPass()
    this.drawInferred()
  }

  detach(): void {
    const map = this.map
    if (map) {
      map.off('moveend', this.onMoveEnd); map.off('zoom', this.onZoom); map.off('movestart', this.onMoveStart); map.off('click', this.onClick)
      map.off('mousemove', this.onMouseMove); map.off('mouseout', this.onMouseOut)
    }
    this.course.detach()
    this.delayed.detach()
    this.map = null
    for (const u of this.unsubs) u()
    this.unsubs = []
    this.track.dispose()
    window.clearTimeout(this.passTimer); window.clearTimeout(this.fadeTimer)
  }

  /** Signal set or text size changed on the same basemap: re-add our layers with the new token colours. */
  repaint(): void {
    const map = this.map
    if (!map) return
    this.track.remove(map)
    for (const id of Object.values(L).reverse()) if (map.getLayer(id)) map.removeLayer(id)
    for (const id of Object.values(S)) if (map.getSource(id)) map.removeSource(id)
    this.attach(map)
  }

  // ---- data -------------------------------------------------------------------------------------------------------

  private onFrame(changed: number[], removed: number[], frame: Frame): void {
    const now = clock()
    let touched = false
    if (frame.type === 'snapshot') {
      for (const mmsi of [...this.state.slotOf.keys()]) if (!vessels.vessels.has(mmsi)) this.state.remove(mmsi)
      if (this.map) (this.map.getSource(S.dead) as GeoJSONSource | undefined)?.setData(deadCells(vessels.coverage.values()))
      touched = true
    }
    for (const mmsi of removed) { if (this.drawnSet.has(mmsi) || this.fades.has(mmsi)) touched = true; this.state.remove(mmsi) }
    let moved = false
    for (const mmsi of changed) {
      const v = vessels.vessels.get(mmsi)
      if (!v) continue
      const drawn = this.drawnSet.has(mmsi) || this.fades.has(mmsi)
      const before = drawn ? this.state.view[this.state.slotOf.get(mmsi) ?? -1] : undefined
      const slot = this.state.upsert(v, now)
      if (!drawn || touched) continue
      // Only a new fix: patch this ship's instances. Anything that changes how it looks: rebuild the list.
      if (before && sameLook(before, v)) { this.pending.add(slot); moved = true } else touched = true
    }
    if (frame.watchlist || frame.type === 'snapshot') { this.updateRanks(); touched = true }   // tiers and opacity may change
    if (touched) this.gpu.invalidate()
    else if (moved) this.gpu.patch()
    this.schedulePass()
    this.drawInferred()
    this.track.touch()
  }

  private updateRanks(): void {
    this.ranks.clear()
    for (const e of vessels.watchlist?.entries ?? []) if (e.decision !== 'none') this.ranks.set(e.mmsi, { decision: e.decision, rank: e.rank })
    for (const v of vessels.vessels.values()) {
      // risk_rank on the view without a watchlist row counts as watch (a ranked ship the server didn't list).
      if (v.risk_rank != null && !this.ranks.has(v.mmsi)) this.ranks.set(v.mmsi, { decision: 'watch', rank: v.risk_rank })
    }
  }

  private schedulePass(): void {
    if (this.passTimer !== undefined) return
    const wait = Math.max(0, DATA_PASS_MS - (performance.now() - this.lastPass))
    this.passTimer = window.setTimeout(() => {
      this.passTimer = undefined
      if (this.map?.isMoving()) return             // moveend runs it
      this.slotPass()
    }, wait)
  }

  // ---- ui ---------------------------------------------------------------------------------------------------------

  private onUi(s: UIState, p: UIState): void {
    if (s.windows !== p.windows) this.drawInferred()
    if (s.layers.density !== p.layers.density) this.slotPass()
    if (s.show !== p.show) { this.applyLayerVisibility(s.layers); this.selectionChanged = true; this.slotPass() }
    if (s.follow !== p.follow) { this.applyLayerVisibility(s.layers); this.selectionChanged = true; this.gpu.invalidate() }
    if (s.windows !== p.windows || s.follow !== p.follow) this.track.touch(true)
    if (s.windows !== p.windows) { this.selectionChanged = true; this.slotPass() }
    else if (s.hoverMmsi !== p.hoverMmsi) this.gpu.invalidate()
    if (s.layers !== p.layers) this.applyLayerVisibility(s.layers)
  }

  private applyLayerVisibility(layers: UIState['layers']): void {
    const map = this.map
    if (!map) return
    const vis = (ids: string[], on: boolean) => { for (const id of ids) if (map.getLayer(id)) map.setLayoutProperty(id, 'visibility', on ? 'visible' : 'none') }
    const following = ui.get().follow, filtering = ui.get().show !== 'all'   // a Show filter hides the heat map and chips like Follow selected
    vis([L.heat], layers.density && !following && !filtering)
    vis([L.chips], !following && !filtering)
    vis([L.dead, L.deadEdge], layers.coverage)
  }

  // ---- slot pass --------------------------------------------------------------------------------------------------

  private view(): View | null {
    const map = this.map
    if (!map) return null
    const canvas = map.getCanvas(), zoom = map.getZoom()
    // Not getCenter(): flyTo({ padding }) leaves padding on the camera, which moves the centre off the canvas midpoint.
    const c = map.unproject([canvas.clientWidth / 2, canvas.clientHeight / 2])
    const tier = sizeTier(zoom)
    return { cx: mercX(c.lng), cy: mercY(c.lat), worldSize: 512 * 2 ** zoom, width: canvas.clientWidth, height: canvas.clientHeight, zoom, hullPx: HULL_LEN[tier] }
  }

  private slotPass(): void {
    const view = this.view()
    if (!view) return
    this.lastPass = performance.now()
    const t0 = this.lastPass
    const s = ui.get()
    const pinned = new Set<number>(s.windows.map((w) => w.mmsi))
    const res = computeSlots({
      state: this.state, view, nowMs: vessels.now_ts || Date.now(), now: clock(), pinned,
      ranks: this.ranks, held: this.held, capOverride: this.opts.capOverride, pad: PAD, allow: showFilter(s.show).match,
    })
    const drawn = res.drawn.map((slot) => this.state.mmsi[slot])
    const same = drawn.length === this.drawn.length && drawn.every((m) => this.drawnSet.has(m))
    this.drawn = drawn
    if (!same) this.drawnSet = new Set(drawn)
    const map = this.map!
    this.avoidGhosts(res, map, view)
    this.chips = res.chips
    ;(map.getSource(S.heat) as GeoJSONSource | undefined)?.setData(res.heat)
    ;(map.getSource(S.chips) as GeoJSONSource | undefined)?.setData(this.chipFeatures())
    const b = map.getBounds()
    let dead = 0
    for (const c of vessels.coverage.values()) {
      if (c.state !== 'dead') continue
      const [a, o] = c.cell_id.split('_').map(Number)
      if (a / 10 <= b.getNorth() && a / 10 + 0.1 >= b.getSouth() && o / 10 <= b.getEast() && o / 10 + 0.1 >= b.getWest()) dead++
    }
    ui.set({ view: { ...res.counts, noCoverageCells: dead, zoom: Math.round(view.zoom * 10) / 10 } })
    if (!same || this.selectionChanged) this.gpu.invalidate()     // the same ships: positions are patched as fixes arrive
    this.selectionChanged = false
    performance.measure('dvm:slot-pass', { start: t0 })
  }

  // Ghost circles (open could-be-within regions as ForecastOverlay draws them, plus every open gap ship, at least 14 px) in
  // screen px. A stack chip over a gap's last fix moves off it (max 40 px). Runs per slot
  // pass (moveend / 1 Hz data), never per frame.
  private avoidGhosts(res: ReturnType<typeof computeSlots>, map: MapLibreMap, view: View): void {
    const s = ui.get(), t = shownNow()
    const picked = new Set<number>(s.windows.map((w) => w.mmsi))
    const zones: { x: number; y: number; r: number }[] = []
    for (const g of vessels.gaps.values()) {
      if (g.state !== 'open' || g.start_ts > t || g.coverage_flag === 'own_stall') continue
      const dark = g.coverage_flag === 'deliberate_candidate'
      if (!dark && !picked.has(g.mmsi)) continue
      const o = ghostOf(g, t)
      const mpp = (40_075_016 * Math.cos((o.lat * Math.PI) / 180)) / view.worldSize
      const p = map.project([o.lon, o.lat])
      zones.push({ x: p.x, y: p.y, r: Math.max(14, (o.r95 ?? o.r) / mpp) })
    }
    if (!zones.length) return
    // Chips stay near their ships: only the gap's last fix (24 px disc) is protected, and a chip moves at most 40 px.
    const disc = (x: number, y: number) => zones.find((z) => Math.hypot(Math.max(Math.abs(x - z.x) - 22, 0), Math.max(Math.abs(y - z.y) - 10, 0)) < 24)
    for (const c of res.chips) {
      const p = map.project([c.lon, c.lat]), z = disc(p.x, p.y)
      if (!z) continue
      const d = Math.hypot(p.x - z.x, p.y - z.y), ux = d < 1 ? 0 : (p.x - z.x) / d, uy = d < 1 ? -1 : (p.y - z.y) / d
      const move = Math.min(40, 48 - d)       // 48: far enough for the chip box to clear the disc along the line
      const a = map.unproject([p.x + ux * move, p.y + uy * move]); c.lon = a.lng; c.lat = a.lat
    }
  }

  private chipFeatures(): GeoJSON.FeatureCollection {
    return {
      type: 'FeatureCollection',
      features: this.chips.map((c, i) => ({
        type: 'Feature', id: i, properties: { i, label: c.plus ? `+${c.mmsis.length}` : String(c.mmsis.length) },
        geometry: { type: 'Point', coordinates: [c.lon, c.lat] },
      })),
    }
  }

  // ---- instance list (runs inside the layer's render when invalidated) --------------------------------------------

  private readColours(): void {
    const names = ['ship-normal', 'ship-selected', 'ship-dark', 'ship-spoof', 'ship-sanctioned', 'text-muted', 'ship-class-a', 'ship-class-b']
    const fallback = ['#eee9dc', '#86c9e8', '#f26aa0', '#f2b33d', '#ff7650', '#a5a99f', '#eee9dc', '#9a8fe8']
    names.forEach((n, i) => this.colourCache.list.set(rgba(readToken(n) || fallback[i]), i * 4))
    this.colourCache.key.set(rgba(readToken('ship-keyline') || readToken('bg-app') || '#15232d').slice(0, 3))
    const dim = parseFloat(readToken('focus-dim-opacity'))
    this.colourCache.dim = Number.isFinite(dim) ? dim : 0.45
  }

  private opacityAt(f: Fade, now: number): number {
    const e = f.dur > 0 ? Math.min(1, Math.max(0, (now - f.t) / f.dur)) : 1
    return f.from + (f.to - f.from) * e
  }

  private rebuild(buf: InstanceBuffer): number {
    const t0 = performance.now()
    const end = this.fill(buf)
    performance.measure('dvm:rebuild', { start: t0 })
    return end
  }

  private fill(buf: InstanceBuffer): number {
    const now = clock()
    const st = this.state
    const s = ui.get()
    const view = this.view()
    const tier = view ? sizeTier(view.zoom) : 'far'
    const reduce = st.reducedMotion
    const windows = new Map(s.windows.map((w) => [w.mmsi, w]))
    const following = s.follow
    const nowMs = vessels.now_ts || Date.now()
    const fanned = this.fan ? new Set(this.fan.mmsis) : null

    // Who is drawn: slot holders, plus the hovered ship (it may come from the stack list) and fanned ships.
    const want = new Set(this.drawn)
    if (s.hoverMmsi != null && st.slotOf.has(s.hoverMmsi)) want.add(s.hoverMmsi)
    if (fanned) for (const m of fanned) want.add(m)
    for (const m of this.fades.keys()) want.add(m)        // leaving ships keep drawing until their fade ends

    interface Item { mmsi: number; slot: number; v: VesselView; key: number; op: Fade; top: boolean }
    const items: Item[] = []
    let end = 0
    for (const mmsi of want) {
      const slot = st.slotOf.get(mmsi)
      const v = slot === undefined ? undefined : st.view[slot]
      if (slot === undefined || !v) { this.fades.delete(mmsi); continue }
      const holds = this.drawnSet.has(mmsi) || mmsi === s.hoverMmsi || !!fanned?.has(mmsi)
      const top = windows.has(mmsi) || mmsi === s.hoverMmsi
      const rank = this.ranks.get(mmsi)
      const zt = zTier(v, rank)
      let target: number
      if (!holds || (following && !windows.has(mmsi))) target = 0
      else if (top) target = 1
      else target = isFull(zt) ? OPACITY.full : OPACITY.routine
      let f = this.fades.get(mmsi)
      if (!f) { f = { from: 0, to: target, t: now, dur: reduce ? 0 : SLOT_FADE_S, leaving: false }; this.fades.set(mmsi, f) }
      else if (f.to !== target) {
        const cur = this.opacityAt(f, now)
        f = { from: cur, to: target, t: now, dur: reduce ? 0 : target === 0 ? SLOT_FADE_S : DIM_FADE_S, leaving: target === 0 }
        this.fades.set(mmsi, f)
      }
      if (f.leaving && now >= f.t + f.dur) { this.fades.delete(mmsi); continue }
      end = Math.max(end, f.t + f.dur, st.animEnd(slot))
      items.push({ mmsi, slot, v, key: top ? 9_000_000 + (mmsi === s.hoverMmsi ? 1 : 0) : sortKey(v, zt, rank, nowMs), op: f, top })
    }
    // Packed sort (key < 2^24, index < 2^24): native Float64Array sort, no comparator over thousands of objects.
    const order = new Float64Array(items.length)
    for (let i = 0; i < items.length; i++) order[i] = items[i].key * 16_777_216 + i
    order.sort()
    const sorted: Item[] = new Array(items.length)
    for (let i = 0; i < order.length; i++) sorted[i] = items[order[i] % 16_777_216]

    // Hulls, bottom to top. Class B is drawn at CLASS_B_SCALE as the non-colour cue; unknown class looks like today.
    const byClass = themeStore.get().classColour
    const hits: Hit[] = []
    const len = HULL_LEN[tier]
    for (const it of sorted) {
      const v = it.v
      const near = tier === 'near'
      const scale = (near ? Math.min(1.4, Math.max(0.7, (v.length_m ?? 150) / 150)) : 1) * (byClass && v.cls === 'B' ? CLASS_B_SCALE : 1)
      const hasHeading = st.hasHeading[it.slot] === 1
      const hollow = v.status === 'gap_open' || v.status === 'silent'
      const colour = v.status === 'gap_open' ? Colour.Dark : v.spoof_recent.length ? Colour.Spoof : v.status === 'silent' ? 5 : byClass && v.cls ? (v.cls === 'B' ? Colour.ClassB : Colour.ClassA) : Colour.Normal
      const type = hullType(v.type_group)
      const sprite = this.hullSprite(type, tier, hollow, hasHeading)
      const off = fanned?.has(it.mmsi) ? this.fan!.offsets.get(it.mmsi) : undefined
      const { from, to, t, dur } = it.op
      if (off) {
        // Fan-out: the true position stays visible at Trace; the ring copy is the one you can click.
        buf.push(it.slot, sprite, colour as Colour, hasHeading, 0, 0, scale, OPACITY.trace, OPACITY.trace, 0, 0)
        buf.push(it.slot, sprite, colour as Colour, hasHeading, off[0], off[1], scale, 1, 1, 0, 0)
      } else {
        buf.push(it.slot, sprite, colour as Colour, hasHeading, 0, 0, scale, from, to, t, dur)
        if (v.spoof_recent.length && !hollow) {
          const o = SPOOF_OFFSET[tier]
          buf.push(it.slot, this.hullSprite(type, tier, true, hasHeading), Colour.Spoof, hasHeading, o, -o, scale, from, to, t, dur)
        }
      }
      if (to > 0) hits.push({ mmsi: it.mmsi, slot: it.slot, offX: off?.[0] ?? 0, offY: off?.[1] ?? 0, r: Math.max(8, (len * scale) / 2) })
    }

    // Upright overlays above every hull: brackets for windows (and hover), sanctioned badges.
    const box = OVERLAY_BOX[tier]
    for (const it of sorted) {
      const yacht = yachtBadge(it.mmsi)
      if (!it.top && !it.v.sanctioned && !yacht) continue
      const { from, to, t, dur } = it.op
      const off = fanned?.has(it.mmsi) ? this.fan!.offsets.get(it.mmsi) : undefined
      const ox = off?.[0] ?? 0, oy = off?.[1] ?? 0
      if (it.v.sanctioned || yacht) {   // a notable (not sanctioned) yacht gets the same badge in the muted colour
        const b = BADGE[tier], d = box / 2 - b / 2
        const c = it.v.sanctioned || yacht === 'sanctioned' ? Colour.Sanctioned : Colour.Keyline
        buf.push(it.slot, `ovl:sanctioned:${tier}`, c, false, ox + d, oy - d, 1, from, to, t, dur)
      }
      const w = windows.get(it.mmsi)
      if (w || it.mmsi === s.hoverMmsi) {
        const hoverOnly = !w
        buf.push(it.slot, `ovl:selected:${tier}`, Colour.Selected, false, ox, oy, 1, hoverOnly ? 0.55 : 1, hoverOnly ? 0.55 : 1, 0, 0)
      }
    }
    this.hits = hits
    if (this.instHead.length < st.highWater) this.instHead = new Int32Array(st.highWater * 2)
    this.instHead.fill(-1)
    if (this.instNext.length < buf.count) this.instNext = new Int32Array(buf.count * 2)
    for (let i = 0; i < buf.count; i++) {
      const sl = buf.instSlot[i]
      if (sl >= 0) { this.instNext[i] = this.instHead[sl]; this.instHead[sl] = i }
    }
    this.pending.clear()
    if (buf.count && !this.firstShipFrame) { this.firstShipFrame = performance.now(); performance.mark('dvm:first-ship-frame') }
    // Leaving fades finish: drop them with one more rebuild.
    window.clearTimeout(this.fadeTimer)
    let leaveEnd = 0
    for (const f of this.fades.values()) if (f.leaving) leaveEnd = Math.max(leaveEnd, f.t + f.dur)
    if (leaveEnd > now) this.fadeTimer = window.setTimeout(() => this.gpu.invalidate(), (leaveEnd - now) * 1000 + 20)
    return end
  }

  private patch(buf: InstanceBuffer): { lo: number; hi: number; end: number } | null {
    let lo = Infinity, hi = -1, end = 0
    for (const slot of this.pending) {
      if (slot >= this.instHead.length) continue
      for (let i = this.instHead[slot]; i >= 0; i = this.instNext[i]) {
        writeMotion(buf, this.state, i, slot)
        if (i < lo) lo = i
        if (i + 1 > hi) hi = i + 1
      }
      end = Math.max(end, this.state.animEnd(slot))
    }
    this.pending.clear()
    return hi > lo ? { lo, hi, end } : null
  }

  // ---- input ------------------------------------------------------------------------------------------------------

  /** Topmost ship under a screen point (CSS px), using the drawn (interpolated) positions. */
  pick(x: number, y: number): { mmsi: number; x: number; y: number } | null {
    const view = this.view()
    if (!view) return null
    const now = clock(), p = this.tmp
    for (let i = this.hits.length - 1; i >= 0; i--) {
      const h = this.hits[i]
      if (this.state.slotOf.get(h.mmsi) !== h.slot) continue
      this.state.posAt(h.slot, now, p)
      let dx = p[0] - view.cx
      dx -= Math.round(dx)
      const sx = view.width / 2 + dx * view.worldSize + h.offX, sy = view.height / 2 + (p[1] - view.cy) * view.worldSize + h.offY
      if (Math.hypot(sx - x, sy - y) <= h.r) return { mmsi: h.mmsi, x: sx, y: sy }
    }
    return null
  }

  private onClick = (e: MapMouseEvent): void => {
    const hit = this.pick(e.point.x, e.point.y)
    if (hit) {
      this.closeFan()
      openShipWindow(hit.mmsi, hit)
      return
    }
    const chip = this.map?.queryRenderedFeatures(e.point, { layers: [L.chips] })[0]
    if (chip) { this.openChip(this.chips[Number(chip.properties?.i)], e.point); return }
    this.closeFan()                                // a click on water closes a fan or list
  }

  private hoverTip: string | null = null
  /** Chip and forecast-tag hover callback for the tooltip (MapView renders it). */
  onChipHover: ((info: { x: number; y: number; text: string } | null) => void) | null = null

  private onMouseMove = (e: MapMouseEvent): void => {
    const map = this.map
    if (!map) return
    const hit = this.pick(e.point.x, e.point.y)
    const hover = hit?.mmsi ?? null
    if (ui.get().hoverMmsi !== hover) ui.set({ hoverMmsi: hover })
    let chipIdx: number | null = null
    if (!hit && this.chips.length) {
      const f = map.queryRenderedFeatures(e.point, { layers: [L.chips] })[0]
      if (f) chipIdx = Number(f.properties?.i)
    }
    map.getCanvas().style.cursor = hit || chipIdx != null ? 'pointer' : ''
    const c = chipIdx != null ? this.chips[chipIdx] : undefined
    let text = c ? this.chipText(c) : null
    if (!hit && !c && map.getLayer('fc-tags')) {
      const tag = map.queryRenderedFeatures(e.point, { layers: ['fc-tags'] })[0]?.properties
      if (tag) text = `Rank ${tag.rank} on the watchlist · ${tag.p} model estimate of going dark in 6 h, for ranking only`
    }
    if (text !== this.hoverTip) {
      this.hoverTip = text
      this.onChipHover?.(text ? { x: e.point.x, y: e.point.y, text } : null)
    }
  }

  private onMouseOut = (): void => {
    if (ui.get().hoverMmsi != null) ui.set({ hoverMmsi: null })
    if (this.hoverTip != null) { this.hoverTip = null; this.onChipHover?.(null) }
  }

  private chipText(c: Chip): string {
    const counts = new Map<string, number>()
    for (const m of c.mmsis) {
      const t = hullType(vessels.vessels.get(m)?.type_group ?? 'other')
      counts.set(t, (counts.get(t) ?? 0) + 1)
    }
    const parts = [...counts].sort((a, b) => b[1] - a[1]).map(([t, n]) => `${n} ${t}`)
    return `${c.mmsis.length} ships · ${parts.join(', ')}`
  }

  private zOrdered(mmsis: number[]): number[] {
    const nowMs = vessels.now_ts || Date.now()
    const key = (m: number) => {
      const v = vessels.vessels.get(m)
      if (!v) return -1
      const r = this.ranks.get(m)
      return sortKey(v, zTier(v, r), r, nowMs)
    }
    return [...mmsis].sort((a, b) => key(b) - key(a) || a - b)
  }

  private openChip(c: Chip | undefined, at: { x: number; y: number }): void {
    if (!c || !this.map) return
    this.closeFan()
    const order = this.zOrdered(c.mmsis)
    const chipPx = this.map.project([c.lon, c.lat])
    if (order.length > 8) { ui.set({ stack: { mmsis: order, x: chipPx.x, y: chipPx.y } }); return }
    void at
    const view = this.view()!
    const tier = sizeTier(view.zoom)
    const ring = ringOffsets(order.length, FAN_RADIUS[tier])
    const offsets = new Map<number, [number, number]>()
    const lines: GeoJSON.Feature[] = []
    const now = clock(), p = this.tmp
    order.forEach((m, i) => {
      const slot = this.state.slotOf.get(m)
      if (slot === undefined) return
      this.state.posAt(slot, now, p)
      let dx = p[0] - view.cx
      dx -= Math.round(dx)
      const sx = view.width / 2 + dx * view.worldSize, sy = view.height / 2 + (p[1] - view.cy) * view.worldSize
      const tx = chipPx.x + ring[i][0], ty = chipPx.y + ring[i][1]
      offsets.set(m, [tx - sx, ty - sy])
      const a = this.map!.unproject([tx, ty])
      lines.push({ type: 'Feature', properties: {}, geometry: { type: 'LineString', coordinates: [[a.lng, a.lat], [lonOf(p[0]), latOf(p[1])]] } })
    })
    this.fan = { mmsis: order, offsets, lon: c.lon, lat: c.lat }
    ;(this.map.getSource(S.fan) as GeoJSONSource | undefined)?.setData({ type: 'FeatureCollection', features: lines })
    this.gpu.invalidate()
  }

  closeFan(): void {
    if (ui.get().stack) ui.set({ stack: null })
    if (!this.fan) return
    this.fan = null
    ;(this.map?.getSource(S.fan) as GeoJSONSource | undefined)?.setData(EMPTY)
    this.gpu.invalidate()
  }

  /** Esc: close a fan or list. Returns true when it did something. */
  escape(): boolean {
    if (this.fan || ui.get().stack) { this.closeFan(); return true }
    return false
  }

  private onMoveStart = (): void => { this.closeFan() }
  // Zooming through the heat-map handover: re-run the slot pass about 4 times a second so ships spawn in while the
  // heat map fades (its opacity is a paint property and needs no pass). Outside the band, moveend is enough.
  private lastZoomPass = 0
  private onZoom = (): void => {
    const z = this.map!.getZoom()
    if (z < HEAT_FADE[0] - 0.5 || z > HEAT_FADE[1] + 0.5 || performance.now() - this.lastZoomPass < 250) return
    this.lastZoomPass = performance.now()
    this.slotPass()
  }
  private onMoveEnd = (): void => { this.slotPass() }

  // Dashed dead-reckoning segment for each open window whose ship has gone dark (the ghost is ForecastOverlay's).
  private drawInferred(): void {
    const src = this.map?.getSource(S.inferred) as GeoJSONSource | undefined
    if (!src) return
    const now = vessels.now_ts || Date.now()
    const features: GeoJSON.Feature[] = []
    for (const w of ui.get().windows) {
      const gap = vessels.vessels.get(w.mmsi)?.status === 'gap_open' ? openGap(vessels.gaps.values(), w.mmsi) : undefined
      const f = gap && inferredSegment(gap, now)
      if (f) features.push(f)
    }
    src.setData({ type: 'FeatureCollection', features })
  }

  // ---- images for MapLibre layers (built per theme) ---------------------------------------------------------------

  private addImages(map: MapLibreMap): void {
    const ratio = 2
    const make = (w: number, h: number, draw: (g: CanvasRenderingContext2D) => void) => {
      const c = document.createElement('canvas')
      c.width = w * ratio; c.height = h * ratio
      const g = c.getContext('2d')!
      g.scale(ratio, ratio)
      draw(g)
      return g.getImageData(0, 0, c.width, c.height)
    }
    const put = (id: string, img: ImageData, opts: Parameters<MapLibreMap['addImage']>[2] = {}) => {
      if (map.hasImage(id)) map.removeImage(id)
      map.addImage(id, img, { pixelRatio: ratio, ...opts })
    }
    const dead = readToken('coverage-dead') || 'rgba(141,150,154,0.24)'
    put('dvm-hatch', make(8, 8, (g) => {
      g.strokeStyle = dead; g.lineWidth = 1.5
      g.beginPath(); g.moveTo(-2, 10); g.lineTo(10, -2); g.moveTo(-2, 2); g.lineTo(2, -2); g.moveTo(6, 10); g.lineTo(10, 6); g.stroke()
    }))
    const panel = readToken('bg-panel') || '#1c2d38', edge = readToken('border-default') || '#4a6474'
    const keyline = readToken('ship-keyline') || readToken('bg-app') || '#15232d'
    // Stack marker: a quiet round disc behind the count (the map scales it with the digits).
    put('dvm-chip', make(26, 26, (g) => {
      g.beginPath(); g.arc(13, 13, 12.5, 0, Math.PI * 2); g.fillStyle = keyline; g.fill()
      g.beginPath(); g.arc(13, 13, 11.5, 0, Math.PI * 2); g.fillStyle = panel; g.fill()
      g.strokeStyle = edge; g.lineWidth = 1; g.stroke()
    }))
  }

  /** Ships in the store (for status and tests). */
  get count(): number { return this.state.slotOf.size }
  get band(): string { const v = this.view(); return v ? bandOf(v.zoom).name : '' }
}
