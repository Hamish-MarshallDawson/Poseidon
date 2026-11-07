import { useEffect, useRef } from 'react'
import { Map as MapLibreMap, Marker, setWorkerUrl, type GeoJSONSource, type MapLayerMouseEvent } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { mapStore } from '../../map/context'
import { ui } from '../../store/ui'
import { vessels } from '../../store/vessels'
import { themeStore } from '../../theme/theme'
import { readToken } from '../../theme/tokens'
import ThemeMenu from '../../theme/ThemeMenu'
import { WindowsRoot } from '../WindowsRoot'
import { bindDetailSender, receiveDetail } from '../detail'
import { openShipWindow } from '../open'
import { createDemoWorld } from './world'
import './demo.css'

setWorkerUrl(maplibreWorkerUrl)

// Development harness for the windows folder: ?demo=windows. ILLUSTRATIVE DATA, no login, no backend.
// It stands in for what the map agent (ships, brackets, letter badges) and the data adapter provide, so windows,
// leader lines, legend, watchlist, status line and focus can be exercised and measured on a real MapLibre map.
// Query: &ships=N (default 2000), &replay=1 (replay mode, AS OF chip), &blank=1 (no basemap tiles).

const STYLE: Record<string, string> = { light: 'positron', 'light-hc': 'bright', dark: 'dark', 'dark-hc': 'dark' }

export default function WindowsDemo() {
  const box = useRef<HTMLDivElement>(null)

  useEffect(() => {
    const q = new URLSearchParams(location.search)
    const world = createDemoWorld(Number(q.get('ships')) || 2000)
    const replay = q.get('replay') === '1'
    const blank = q.get('blank') === '1'
    const water = readToken('--dvm-map-water') || '#1f3b4b'
    const map = new MapLibreMap({
      container: box.current!,
      style: blank
        ? { version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': water } }] }
        : `https://tiles.openfreemap.org/styles/${STYLE[themeStore.get().theme]}`,
      center: [20, 59.4],
      zoom: 5,
      attributionControl: false,
    })
    ;(window as unknown as { __map: MapLibreMap }).__map = map

    // Feed: one frame a second, like the backend. The detail request is answered after a short delay.
    vessels.applyFrame(world.snapshot())
    bindDetailSender((m) => { if (m.type === 'detail') setTimeout(() => receiveDetail(world.detail(m.mmsi)), 120) })
    const tick = () => {
      vessels.applyFrame(world.delta())
      ui.set((s) => ({ feed: { ...s.feed, connected: true, mode: replay ? 'replay' : 'live', now_ts: world.now,
        replay: replay ? { from_ts: world.now - 6 * 3600e3, to_ts: world.now + 62 * 60e3 } : null,
        stats: { tracked: world.size, msgs_per_s: 340, queue_depth: 0 }, isMock: true } }))
    }
    tick()
    const timer = setInterval(tick, 1000)

    // Ships as one circle layer, plus the window marks the map agent will draw (a ring and the letter badge).
    const markers = new Map<number, Marker>()
    const drawMarks = () => {
      const { windows } = ui.get()
      for (const [mmsi, m] of markers) if (!windows.some((w) => w.mmsi === mmsi)) { m.remove(); markers.delete(mmsi) }
      for (const w of windows) {
        const v = vessels.vessels.get(w.mmsi)
        if (!v) continue
        let m = markers.get(w.mmsi)
        if (!m) {
          const el = document.createElement('div')
          el.className = 'wd-mark'
          el.innerHTML = `<i></i><b>${w.letter}</b>`
          m = new Marker({ element: el }).setLngLat([v.lon, v.lat]).addTo(map)
          markers.set(w.mmsi, m)
        } else m.setLngLat([v.lon, v.lat])
      }
    }
    const unsubMarks = ui.subscribe((s, p) => { if (s.windows !== p.windows) drawMarks() })
    const unsubVessels = vessels.subscribe(() => {
      drawMarks()
      map.getSource<GeoJSONSource>('ships')?.setData(world.geojson())
    })

    const countView = () => {
      const b = map.getBounds()
      let n = 0
      for (const v of vessels.vessels.values()) if (b.contains([v.lon, v.lat])) n++
      const shown = Math.min(n, 100)
      ui.set({ view: { inView: n, shown, stacked: Math.round((n - shown) * 0.18), inCells: n - shown - Math.round((n - shown) * 0.18),
        noCoverageCells: 3, zoom: map.getZoom() } })
    }
    const addShips = () => {
      if (map.getSource('ships')) return
      map.addSource('ships', { type: 'geojson', data: world.geojson() })
      map.addLayer({ id: 'ships', type: 'circle', source: 'ships', paint: {
        'circle-radius': ['interpolate', ['linear'], ['zoom'], 3, 2.5, 8, 4.5],
        'circle-color': ['case', ['get', 'dark'], 'rgba(0,0,0,0)', readToken('--dvm-ship-normal') || '#eee9dc'],
        'circle-stroke-width': ['case', ['get', 'dark'], 1.5, 0],
        'circle-stroke-color': readToken('--dvm-ship-dark') || '#f26aa0',
      } })
      mapStore.set({ map })
      countView()
    }
    map.on('load', addShips)
    map.on('error', () => { if (!blank && !map.isStyleLoaded()) map.setStyle({ version: 8, sources: {}, layers: [{ id: 'bg', type: 'background', paint: { 'background-color': water } }] }) })
    map.on('style.load', addShips)
    map.on('moveend', countView)
    map.on('click', 'ships', (e: MapLayerMouseEvent) => {
      const mmsi = Number(e.features?.[0]?.properties?.mmsi)
      if (mmsi) openShipWindow(mmsi)
    })
    map.on('mouseenter', 'ships', () => (map.getCanvas().style.cursor = 'pointer'))
    map.on('mouseleave', 'ships', () => (map.getCanvas().style.cursor = ''))

    return () => {
      clearInterval(timer)
      unsubMarks(); unsubVessels(); bindDetailSender(null)
      for (const m of markers.values()) m.remove()
      mapStore.set({ map: null })
      map.remove()
    }
  }, [])

  return (
    <div className="wd-root">
      <div ref={box} className="wd-map" />
      <WindowsRoot onLogout={() => location.assign(location.pathname)} />
      <ThemeMenu />
    </div>
  )
}
