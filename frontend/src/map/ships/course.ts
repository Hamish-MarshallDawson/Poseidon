import type { GeoJSONSource, Map as MapLibreMap } from 'maplibre-gl'
import { ui } from '../../store/ui'
import { vessels } from '../../store/vessels'
import { readToken } from '../../theme/tokens'
import { latOf, lonOf, unitsPerMetre } from '../geo'
import { clock, type ShipState } from './state'

// Predicted course: a dashed line ahead of the front-window or focused ship along its COG, as far as it sails in
// 10 min at its SOG, fading to the tip with a "+10 min" label. The start follows the drawn (animated) position, read
// from ShipState.posAt at ~8 Hz; setData is skipped while nothing moved. MapLibre cannot combine line-gradient with
// dashes, so the dashes are separate features whose line-opacity falls from 1 to 0.1.
// Shown from the view's own SOG/COG, so reduced motion still draws it (statically).

const SRC = 'dvm-course', L_LINE = 'dvm-course-line', L_LABEL = 'dvm-course-label'
const HORIZON_S = 600, DASHES = 12, MIN_KN = 0.5, KN = 0.514444, HZ_MS = 125
const FONT = ['Barlow Semi Condensed Medium']
const EMPTY: GeoJSON.FeatureCollection = { type: 'FeatureCollection', features: [] }

export class CourseLine {
  private map: MapLibreMap | null = null
  private timer: number | undefined
  private key = ''
  private p = new Float64Array(2)
  private state: ShipState
  constructor(state: ShipState) { this.state = state }

  attach(map: MapLibreMap): void {
    this.map = map
    for (const id of [L_LABEL, L_LINE]) if (map.getLayer(id)) map.removeLayer(id)
    if (map.getSource(SRC)) map.removeSource(SRC)
    map.addSource(SRC, { type: 'geojson', data: EMPTY })
    const ink = readToken('ship-dark') || '#f26aa0'
    map.addLayer({
      id: L_LINE, type: 'line', source: SRC, filter: ['==', ['get', 'k'], 'dash'],
      layout: { 'line-cap': 'butt' }, paint: { 'line-color': ink, 'line-width': 2, 'line-opacity': ['get', 'op'] },
    })
    map.addLayer({
      id: L_LABEL, type: 'symbol', source: SRC, filter: ['==', ['get', 'k'], 'tip'],
      layout: { 'text-field': '+10 min', 'text-font': FONT, 'text-size': 11, 'text-anchor': 'top-left', 'text-offset': [0.5, 0.3], 'text-allow-overlap': true },
      paint: { 'text-color': ink, 'text-halo-color': readToken('bg-app') || '#000', 'text-halo-width': 1.2 },
    })
    this.key = ''
    window.clearInterval(this.timer)
    this.timer = window.setInterval(() => this.update(), HZ_MS)
    this.update()
  }

  detach(): void {
    window.clearInterval(this.timer)
    this.timer = undefined
    this.map = null
  }

  private update(): void {
    const src = this.map?.getSource(SRC) as GeoJSONSource | undefined
    if (!src) return
    const s = ui.get(), mmsi = s.frontMmsi ?? s.focusMmsi
    const v = mmsi != null ? vessels.vessels.get(mmsi) : undefined
    const slot = mmsi != null ? this.state.slotOf.get(mmsi) : undefined
    let key = ''
    let data = EMPTY
    if (v && slot !== undefined && v.status === 'active' && v.sog_kn != null && v.sog_kn >= MIN_KN && v.cog_deg != null && v.cog_deg < 360) {
      const p = this.p
      this.state.posAt(slot, clock(), p)
      key = `${mmsi}|${p[0].toFixed(8)}|${p[1].toFixed(8)}|${v.sog_kn}|${v.cog_deg}`
      if (key === this.key) return
      const upm = unitsPerMetre(latOf(p[1]))
      const len = v.sog_kn * KN * HORIZON_S * upm, a = (v.cog_deg * Math.PI) / 180
      const dx = Math.sin(a) * len, dy = -Math.cos(a) * len
      const pt = (f: number): [number, number] => [lonOf(p[0] + dx * f), latOf(p[1] + dy * f)]
      const features: GeoJSON.Feature[] = []
      for (let i = 0; i < DASHES; i++) {
        features.push({
          type: 'Feature', properties: { k: 'dash', op: 1 - (0.9 * i) / (DASHES - 1) },
          geometry: { type: 'LineString', coordinates: [pt((i + 0.1) / DASHES), pt((i + 0.6) / DASHES)] },
        })
      }
      features.push({ type: 'Feature', properties: { k: 'tip' }, geometry: { type: 'Point', coordinates: pt(1) } })
      data = { type: 'FeatureCollection', features }
    }
    if (key === this.key) return
    this.key = key
    src.setData(data)
  }
}
