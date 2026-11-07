// ?demo=basemap: a plain map on the DVM basemap at the Helsinki skerries, for review. Follows the Display menu theme.
import { useEffect, useRef, useState } from 'react'
import { Map as MapLibreMap, NavigationControl, setWorkerUrl } from 'maplibre-gl'
import 'maplibre-gl/dist/maplibre-gl.css'
import maplibreWorkerUrl from 'maplibre-gl/dist/maplibre-gl-worker.mjs?url'
import { onTokensChange } from '../theme/tokens'
import ThemeMenu from '../theme/ThemeMenu'
import { basemapStyle, registerBasemap, setBasemapTheme } from './index'
import './demo.css'

setWorkerUrl(maplibreWorkerUrl)
const VIEWS = {
  skerries: { bounds: [[24.55, 59.98], [25.45, 60.26]] as [[number, number], [number, number]], label: 'Helsinki skerries' },
  baltic: { bounds: [[9, 53.5], [31, 66]] as [[number, number], [number, number]], label: 'Baltic' },
  world: { bounds: [[-170, -60], [170, 75]] as [[number, number], [number, number]], label: 'World' },
}

export default function BasemapDemo() {
  const ref = useRef<HTMLDivElement>(null)
  const [map, setMap] = useState<MapLibreMap | null>(null)
  const [zoom, setZoom] = useState(0)
  useEffect(() => {
    registerBasemap()
    let m: MapLibreMap | null = null
    let dead = false
    const view = (new URLSearchParams(location.search).get('view') ?? 'skerries') as keyof typeof VIEWS
    basemapStyle().then((style) => {
      if (dead) return
      m = new MapLibreMap({ container: ref.current!, style, bounds: (VIEWS[view] ?? VIEWS.skerries).bounds, hash: true, attributionControl: { compact: true } })
      m.addControl(new NavigationControl({ showCompass: false }), 'bottom-right')
      m.on('style.load', () => m!.setProjection({ type: 'mercator' }))
      m.on('zoom', () => setZoom(m!.getZoom()))
      m.once('load', () => setZoom(m!.getZoom()))
      ;(window as unknown as { __map: MapLibreMap }).__map = m
      setMap(m)
    })
    return () => { dead = true; m?.remove() }
  }, [])
  useEffect(() => (map ? onTokensChange(() => setBasemapTheme(map)) : undefined), [map])
  return (
    <>
      <div ref={ref} className="bm-demo" />
      <div className="bm-demo__bar" role="toolbar" aria-label="Basemap views">
        {Object.entries(VIEWS).map(([k, v]) => <button key={k} onClick={() => map?.fitBounds(v.bounds, { duration: 0 })}>{v.label}</button>)}
        <span className="t-data">z{zoom.toFixed(2)}</span>
      </div>
      <ThemeMenu />
    </>
  )
}
