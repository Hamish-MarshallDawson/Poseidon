import { useEffect, useRef, useState } from 'react'
import { useAuth0 } from '@auth0/auth0-react'
import { Map as MapLibreMap, type GeoJSONSource } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import type { ServerMsg, VesselView } from './types'
import { applyMessage, toFeatureCollection } from './vessels'

const WS_URL = import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws'
const STYLE_URL = 'https://tiles.openfreemap.org/styles/dark'
const SOURCE_ID = 'ships'
const MIN_DELAY_MS = 1000
const MAX_DELAY_MS = 15000

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
  const getTokenRef = useRef(getToken) // the socket effect runs once; this keeps it off the deps list
  const mapRef = useRef<MapLibreMap | null>(null)
  const styleReady = useRef(false)
  const vessels = useRef(new Map<number, VesselView>())
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
    </>
  )
}
