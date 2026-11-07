import { lazy, Suspense, useEffect, useRef, useState } from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import { Map as MapLibreMap, Popup, setWorkerUrl, type GeoJSONSource } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
// MapLibre 6 finds its worker at ./maplibre-gl-worker.mjs next to its own module. Once Vite pre-bundles it into
// node_modules/.vite/deps that file isn't there ("Worker failed to load", a black map), so point at it explicitly.
// The worker is self-contained, so the ?url asset works in dev and in production builds.
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'

setWorkerUrl(maplibreWorkerUrl)
import type { ServerMsg, VesselView } from './types'
import { applyMessage, toFeatureCollection } from './vessels'
import { popupContent, type StaticDetail } from './popup'
import ThemeMenu from './theme/ThemeMenu'
import { Button, Panel } from './ui'

const TokensDemo = lazy(() => import('./tokens/TokensDemo'))

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'
const STYLE_URL = 'https://tiles.openfreemap.org/styles/dark'
const SOURCE_ID = 'ships'
const MIN_DELAY_MS = 1000
const MAX_DELAY_MS = 15000

// Auth0 login gates the map; the backend checks the same access token on the WebSocket.
export default function App() {
  const { isLoading, isAuthenticated, error, loginWithRedirect, logout, getAccessTokenSilently } = useAuth0()
  if (new URLSearchParams(location.search).get('demo') === 'tokens') return <Suspense><TokensDemo /></Suspense>
  if (isLoading) return <div className="gate"><p className="gate__foot">Loading…</p></div>
  if (!isAuthenticated) {
    return (
      <div className="gate">
        <Panel className="gate__card">
          <h1>Dark Vessel Monitor</h1>
          <p className="gate__lede">Ships that go quiet on AIS while reception nearby is normal, ranked for review. Never an accusation.</p>
          <Button variant="filled" onClick={() => loginWithRedirect()}>Log in to view the map</Button>
          {error && <p className="error" role="alert">{error.message}</p>}
          <p className="gate__foot">HackTheBurgh · team Hedged Bets</p>
        </Panel>
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
  const getTokenRef = useRef(getToken) // the socket effect runs once; this keeps it off the deps list
  const mapRef = useRef<MapLibreMap | null>(null)
  const styleReady = useRef(false)
  const vessels = useRef(new Map<number, VesselView>())
  const wsRef = useRef<WebSocket | null>(null)
  const popupRef = useRef<{ popup: Popup; mmsi: number } | null>(null)
  const [connected, setConnected] = useState(false)
  const [shipCount, setShipCount] = useState(0)
  const [msgsPerS, setMsgsPerS] = useState(0)

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
      map.addSource(SOURCE_ID, { type: 'geojson', data: toFeatureCollection(vessels.current) })
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
        const v = vessels.current.get(Number(e.features?.[0]?.properties?.mmsi))
        if (!v) return
        popupRef.current?.popup.remove()
        const popup = new Popup({ maxWidth: '300px' }).setLngLat([v.lon, v.lat]).setDOMContent(popupContent(v, undefined)).addTo(map)
        popupRef.current = { popup, mmsi: v.mmsi }
        popup.on('close', () => {
          if (popupRef.current?.popup === popup) popupRef.current = null
        })
        if (wsRef.current?.readyState === WebSocket.OPEN) wsRef.current.send(JSON.stringify({ type: 'detail', mmsi: v.mmsi }))
      })
      map.on('mouseenter', 'ships', () => (map.getCanvas().style.cursor = 'pointer'))
      map.on('mouseleave', 'ships', () => (map.getCanvas().style.cursor = ''))
      styleReady.current = true
    })
    return () => {
      styleReady.current = false
      map.remove()
      mapRef.current = null
    }
  }, [])

  // WebSocket feed with seq-gap reconnect and backoff.
  useEffect(() => {
    let ws: WebSocket | null = null
    let timer: number | undefined
    let delay = MIN_DELAY_MS
    let disposed = false

    const connect = () => {
      const sock = new WebSocket(WS_URL)
      ws = sock
      wsRef.current = sock
      let lastSeq: number | null = null
      let stale = false

      // The first message must be the access token: browsers can't set headers on a WebSocket.
      sock.onopen = () => {
        getTokenRef.current()
          .then((token) => (token ? sock.send(JSON.stringify({ type: 'auth', token })) : sock.close()))
          .catch(() => sock.close())
      }

      sock.onmessage = (ev) => {
        if (stale) return
        setConnected(true) // the server only talks after the token checks out
        let msg: ServerMsg
        try {
          msg = JSON.parse(ev.data)
        } catch {
          return
        }
        if (lastSeq !== null && msg.seq !== lastSeq + 1) {
          // A gap means we missed a delta: drop the socket and take a fresh snapshot.
          stale = true
          sock.close()
          return
        }
        lastSeq = msg.seq
        delay = MIN_DELAY_MS

        if (applyMessage(vessels.current, msg)) {
          // One setData per snapshot or delta, not per vessel.
          const src = styleReady.current ? mapRef.current?.getSource<GeoJSONSource>(SOURCE_ID) : undefined
          src?.setData(toFeatureCollection(vessels.current))
          setShipCount(vessels.current.size)
        }
        if (msg.type === 'snapshot' || msg.type === 'delta') setMsgsPerS(msg.stats.msgs_per_s)
        const open = popupRef.current
        const v = open && msg.type === 'detail' && msg.mmsi === open.mmsi ? vessels.current.get(open.mmsi) : undefined
        if (open && v && msg.type === 'detail') open.popup.setDOMContent(popupContent(v, msg.statics[0] as StaticDetail))
      }

      sock.onclose = () => {
        setConnected(false)
        if (disposed) return
        timer = window.setTimeout(connect, delay)
        delay = Math.min(delay * 2, MAX_DELAY_MS)
      }
    }

    connect()
    return () => {
      disposed = true
      window.clearTimeout(timer)
      ws?.close()
    }
  }, [])

  return (
    <>
      <div ref={containerRef} className="map" />
      <div className="status">
        <span className={connected ? 'dot on' : 'dot off'} />
        {connected ? 'connected' : 'disconnected'} · ships {shipCount} · {Math.round(msgsPerS)} msg/s ·{' '}
        <button className="link" onClick={onLogout}>log out</button>
      </div>
      <ThemeMenu />
    </>
  )
}
