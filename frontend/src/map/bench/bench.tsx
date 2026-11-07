import { createRoot } from 'react-dom/client'
import { Map as MapLibreMap, type GeoJSONSource } from 'maplibre-gl'
import '../../index.css'
import '../../theme/theme'
import ThemeMenu from '../../theme/ThemeMenu'
import MapView from '../MapView'
import { vessels } from '../../store/vessels'
import { ShipState, clock } from '../ships/state'
import { headingOf, latOf, lonOf } from '../geo'

// Dev-only bench page, served by `npm run dev` at /src/map/bench/bench.html (not part of the build). No login, no
// backend: MapView with ?synthetic=N labelled synthetic ships. ?renderer=symbol swaps in the alternative we measured
// against: one MapLibre symbol layer for every ship, interpolated by setData on every frame.
const params = new URLSearchParams(location.search)
const root = createRoot(document.getElementById('root')!)

if (params.get('renderer') === 'symbol') {
  const el = document.createElement('div')
  el.className = 'dvm-map'
  document.body.append(el)
  const map = new MapLibreMap({ container: el, style: 'https://tiles.openfreemap.org/styles/dark', bounds: [[4, 54.4], [36, 64.5]], maxPitch: 0 })
  ;(window as unknown as { __dvm: unknown }).__dvm = { map }
  map.on('load', async () => {
    map.setProjection({ type: 'mercator' })
    const c = document.createElement('canvas'); c.width = 16; c.height = 32
    const g = c.getContext('2d')!; g.fillStyle = '#eee9dc'; g.beginPath(); g.moveTo(8, 0); g.lineTo(15, 10); g.lineTo(15, 31); g.lineTo(1, 31); g.lineTo(1, 10); g.fill()
    map.addImage('hull', g.getImageData(0, 0, 16, 32), { pixelRatio: 2 })
    map.addSource('ships', { type: 'geojson', data: { type: 'FeatureCollection', features: [] } })
    map.addLayer({ id: 'ships', type: 'symbol', source: 'ships', layout: {
      'icon-image': 'hull', 'icon-rotate': ['get', 'h'], 'icon-rotation-alignment': 'map', 'icon-allow-overlap': true,
      'icon-ignore-placement': true, 'symbol-sort-key': ['get', 'k'] } })
    const st = new ShipState()
    vessels.subscribe((changed) => { const now = clock(); for (const m of changed) st.upsert(vessels.vessels.get(m)!, now) })
    const { startSynthetic } = await import('../synthetic')
    startSynthetic(Number(params.get('synthetic')) || 25000)
    const src = map.getSource('ships') as GeoJSONSource
    const p = [0, 0]
    const frame = () => {
      const now = clock()
      const features: GeoJSON.Feature[] = []
      for (let s = 0; s < st.highWater; s++) {
        const v = st.view[s]; if (!v) continue
        st.posAt(s, now, p)
        features.push({ type: 'Feature', properties: { h: headingOf(v.heading_deg, v.cog_deg) ?? 0, k: s }, geometry: { type: 'Point', coordinates: [lonOf(p[0]), latOf(p[1])] } })
      }
      src.setData({ type: 'FeatureCollection', features })
      requestAnimationFrame(frame)
    }
    requestAnimationFrame(frame)
  })
} else {
  root.render(<><MapView /><ThemeMenu /></>)
}
