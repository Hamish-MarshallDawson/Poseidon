import { useEffect, useRef, useState } from 'react'
import { Map as MapLibreMap, setWorkerUrl } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
// MapLibre 6 finds its worker at ./maplibre-gl-worker.mjs next to its own module. Once Vite pre-bundles it into
// node_modules/.vite/deps that file isn't there ("Worker failed to load", a black map), so point at it explicitly.
// The worker is self-contained, so the ?url asset works in dev and in production builds.
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { ui } from '../store/ui'
import { vessels } from '../store/vessels'
import { onTokensChange } from '../theme/tokens'
import { createLiveAdapter } from '../data/live'
import { mapStore } from './context'
import { currentTheme, getStyle, recolourBasemap } from './style'
import { ShipController } from './ships/controller'
import { StackList } from './StackList'
import './map.css'

setWorkerUrl(maplibreWorkerUrl)

// Default frame: the Baltic, as on the dashboard (lon 4–36, lat 54.4–64.5 at 1440 × 900).
const BALTIC: [[number, number], [number, number]] = [[4, 54.4], [36, 64.5]]

export interface MapViewProps {
  // Dev wiring until the lead composes App with data/index.ts `useFeed`: when given, MapView runs the live adapter
  // itself. Leave it out when something else feeds the vessel store.
  getToken?: () => Promise<string | undefined>
}

// The full-bleed map. Ships never pass through React: the controller draws them from typed arrays on the GPU.
// Dev switches: ?synthetic=25000 adds that many labelled synthetic ships (no backend needed); ?cap=0 lifts the
// density caps so every ship in view is drawn (stress test); ?cap=N sets a fixed cap.
export default function MapView({ getToken }: MapViewProps) {
  const ref = useRef<HTMLDivElement>(null)
  const tokenRef = useRef(getToken)
  const [tip, setTip] = useState<{ x: number; y: number; text: string } | null>(null)

  useEffect(() => {
    const params = new URLSearchParams(location.search)
    const capParam = params.get('cap')
    const synthetic = Math.min(200_000, Math.max(0, Number(params.get('synthetic')) || 0))
    const ctl = new ShipController({ capOverride: capParam != null && capParam !== '' ? Number(capParam) : undefined })
    ctl.onChipHover = setTip
    let map: MapLibreMap | null = null
    let disposed = false
    let theme = currentTheme()
    const stops: (() => void)[] = []

    void getStyle().then((style) => {
      if (disposed) return
      const m = new MapLibreMap({
        container: ref.current!, style, bounds: BALTIC, maxZoom: 15, maxPitch: 0,
        dragRotate: false, pitchWithRotate: false, touchPitch: false, attributionControl: { compact: true },
      })
      map = m
      m.touchZoomRotate.disableRotation()
      m.keyboard.disableRotation()
      m.once('load', () => performance.mark('dvm:map-load'))
      // Every style load (first, and after each theme swap): mercator, token recolour, our layers, then tell others.
      m.on('style.load', () => {
        m.setProjection({ type: 'mercator' })
        recolourBasemap(m)
        ctl.attach(m)
        mapStore.set((s) => ({ map: m, styleVersion: s.styleVersion + 1 }))
      })
      if (import.meta.env.DEV) (window as unknown as { __dvm: unknown }).__dvm = { map: m, ctl, ui, vessels, mapStore }
    })

    // Theme swap: new basemap style (our layers re-attach on style.load). Signals or text size: repaint our layers.
    stops.push(onTokensChange(() => {
      const next = currentTheme()
      if (next === theme) { ctl.repaint(); return }
      theme = next
      void getStyle().then((style) => { if (!disposed) map?.setStyle(style, { diff: false }) })
    }))

    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape' && ctl.escape()) e.preventDefault() }
    document.addEventListener('keydown', onKey)
    stops.push(() => document.removeEventListener('keydown', onKey))

    if (synthetic > 0) {
      void import('./synthetic').then(({ startSynthetic }) => { if (!disposed) stops.push(startSynthetic(synthetic)) })
    } else if (tokenRef.current) {
      const a = createLiveAdapter({
        wsUrl: import.meta.env.VITE_WS_URL || 'ws://localhost:8000/ws',
        httpBase: import.meta.env.VITE_API_URL || 'http://localhost:8000',
        getToken: () => tokenRef.current!(),
      })
      a.start({
        onFrame: (f) => vessels.applyFrame(f),
        onStatus: (s) => ui.set({ feed: { ...s, isMock: a.isMock } }),
        onDetail: () => {},
      })
      stops.push(() => a.stop())
    }

    return () => {
      disposed = true
      for (const s of stops) s()
      ctl.detach()
      mapStore.set({ map: null })
      map?.remove()
    }
  }, [])

  return (
    <>
      <div ref={ref} className="dvm-map" role="application" aria-label="Ship map" />
      {tip && <div className="dvm-chip-tip" style={{ transform: `translate(${tip.x + 12}px, ${tip.y + 12}px)` }}>{tip.text}</div>}
      <StackList />
    </>
  )
}
