import { useEffect, useRef, useState } from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import { Map as MapLibreMap, Popup, setWorkerUrl, type GeoJSONSource } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
// MapLibre 6 finds its worker at ./maplibre-gl-worker.mjs next to its own module. Once Vite pre-bundles it into
// node_modules/.vite/deps that file isn't there ("Worker failed to load", a black map), so point at it explicitly.
// The worker is self-contained, so the ?url asset works in dev and in production builds.
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'

setWorkerUrl(maplibreWorkerUrl)
import { toFeatureCollection } from './vessels'
import { adapter, onDetail, useFeed } from './data/index'
import { mapStore } from './map/context'
import { ui } from './store/ui'
import { vessels } from './store/vessels'
import { ScrubBar } from './timeline/ScrubBar'
import { ReplayChrome } from './timeline/ReplayChrome'
import { ForecastOverlay } from './forecast/ForecastOverlay'
import { popupContent, type StaticDetail } from './popup'

const STYLE_URL = 'https://tiles.openfreemap.org/styles/dark'
const SOURCE_ID = 'ships'

// Auth0 login gates the map; the backend checks the same access token on the WebSocket.
export default function App() {
  const { isLoading, isAuthenticated, error, loginWithRedirect, logout, getAccessTokenSilently } = useAuth0()
  if (isLoading) return <div className="gate">Loading…</div>
  if (!isAuthenticated) {
    return (
      <div className="gate">
        <h1>Dark Vessel Monitor</h1>
        <button onClick={() => loginWithRedirect()}>Log in to view the map</button>
        {error && <p className="error">{error.message}</p>}
      </div>
    )
  }
  return (
    <LiveMap
      getToken={() => getAccessTokenSilently()}
      onLogout={() => logout({ logoutParams: { returnTo: window.location.origin } })}
    />
  )
}

function LiveMap({ getToken, onLogout }: { getToken: () => Promise<string | undefined>; onLogout: () => void }) {
  const containerRef = useRef<HTMLDivElement>(null)
  const mapRef = useRef<MapLibreMap | null>(null)
  const styleReady = useRef(false)
  const popupRef = useRef<{ popup: Popup; mmsi: number } | null>(null)
  const [shipCount, setShipCount] = useState(0)

  // Flat map. MapLibre v5+ defaults to globe, so mercator is forced once the style loads.
  useEffect(() => {
    const map = new MapLibreMap({
      container: containerRef.current!,
      style: STYLE_URL,
      center: [0, 20],
      zoom: 1.2,
    })
    mapRef.current = map
    map.on('style.load', () => {
      map.setProjection({ type: 'mercator' })
      map.addSource(SOURCE_ID, { type: 'geojson', data: toFeatureCollection(vessels.vessels) })
      map.addLayer({
        id: 'ships',
        type: 'circle',
        source: SOURCE_ID,
        paint: {
          'circle-color': '#22d3ee',
          'circle-radius': ['interpolate', ['linear'], ['zoom'], 0, 2, 8, 3, 14, 4],
        },
      })
      // Click a ship: open its popup at once, then ask the server for `detail` (destination, numeric ship type).
      map.on('click', 'ships', (e) => {
        const v = vessels.vessels.get(Number(e.features?.[0]?.properties?.mmsi))
        if (!v) return
        popupRef.current?.popup.remove()
        const popup = new Popup({ maxWidth: '300px' }).setLngLat([v.lon, v.lat]).setDOMContent(popupContent(v, undefined)).addTo(map)
        popupRef.current = { popup, mmsi: v.mmsi }
        popup.on('close', () => {
          if (popupRef.current?.popup === popup) popupRef.current = null
        })
        adapter?.send({ type: 'detail', mmsi: v.mmsi })
      })
      map.on('mouseenter', 'ships', () => (map.getCanvas().style.cursor = 'pointer'))
      map.on('mouseleave', 'ships', () => (map.getCanvas().style.cursor = ''))
      styleReady.current = true
      mapStore.set((m) => ({ map, styleVersion: m.styleVersion + 1 }))
    })
    return () => {
      styleReady.current = false
      mapStore.set({ map: null })
      map.remove()
      mapRef.current = null
    }
  }, [])

  // Feed through the data adapter (timeline branch: data/index.ts); the old cyan dots draw from the vessel store.
  useFeed(getToken)
  const connected = ui.use((st) => st.feed.connected)
  const isMock = ui.use((st) => st.feed.isMock)
  const msgsPerS = ui.use((st) => st.feed.stats.msgs_per_s)
  useEffect(() => vessels.subscribe(() => {
    const src = styleReady.current ? mapRef.current?.getSource<GeoJSONSource>(SOURCE_ID) : undefined
    src?.setData(toFeatureCollection(vessels.vessels))
    setShipCount(vessels.vessels.size)
  }), [])
  useEffect(() => onDetail((msg) => {
    const open = popupRef.current
    const v = open && msg.mmsi === open.mmsi ? vessels.vessels.get(open.mmsi) : undefined
    if (open && v) open.popup.setDOMContent(popupContent(v, msg.statics[0] as StaticDetail))
  }), [])

  return (
    <>
      <div ref={containerRef} className="map" />
      <div className="status">
        <span className={connected ? 'dot on' : 'dot off'} />
        {connected ? 'connected' : 'disconnected'} · ships {shipCount} · {Math.round(msgsPerS)} msg/s ·{' '}
        {isMock && <>Illustrative data · </>}<button className="link" onClick={onLogout}>log out</button>
      </div>
      <ForecastOverlay />
      <ReplayChrome />
      <ScrubBar />
    </>
  )
}
