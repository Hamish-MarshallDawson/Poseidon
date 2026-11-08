import { useEffect, useRef } from 'react'
import { ui, type UIState } from '../store/ui'
import { Switch } from '../ui'
import { useMapInstance } from '../map/context'
import { reducedMotion, usePresence } from '../motion'
import { fmtInt } from '../windows/format'
import { WatchlistChip } from './Watchlist'
import { ReviewChip } from '../review/ReviewPanel'

// Top-right buttons (watchlist chip, Layers, log out), zoom on the right edge and the scale bar bottom-right
// (Figma 66:21908). The Layers pop-over follows the density report's layers panel (41:432).

type LayerKey = keyof UIState['layers']
const LAYERS: { key: LayerKey; label: string; note: string }[] = [
  { key: 'density', label: 'Density view', note: 'ships heard per cell; hidden when zoomed in' },
  { key: 'coverage', label: 'Coverage gaps', note: 'hatch where no receiver heard anything in 10 min' },
  { key: 'forecast', label: 'Forecast', note: 'rank tags and could-be-in-here regions' },
  { key: 'inland', label: 'Inland vessels', note: 'Rhine, Danube and other inland waterways' },
  { key: 'labels', label: 'Labels', note: 'place and water names' },
  { key: 'depth', label: 'Depth', note: 'contours only · off by default' },
]

function LayersPanel() {
  const layers = ui.use((s) => s.layers)
  const view = ui.use((s) => s.view)
  const hidden = Math.max(0, view.inView - view.shown)
  return (
    <div className="panel layers" id="layers-panel" role="region" aria-label="Layers">
      <div className="ly-cap">
        <span className="kicker">Ships</span>
        <span className="ly-showing">Showing {fmtInt(view.shown)} of {fmtInt(view.inView)} ships in view</span>
        <span className="ly-bar"><i style={{ transform: `scaleX(${view.inView ? view.shown / view.inView : 0})` }} /></span>
        <span className="ly-note">{fmtInt(hidden)} more counted in density cells and stacks</span>
      </div>
      <span className="kicker ly-head">Map</span>
      {LAYERS.map(({ key, label, note }) => (
        <Switch key={key} checked={layers[key]} label={label} hint={note}
          onChange={(on) => ui.set((s) => ({ layers: { ...s.layers, [key]: on } }))} />
      ))}
    </div>
  )
}

function ScaleBar() {
  const map = useMapInstance()
  const barRef = useRef<HTMLSpanElement>(null)
  const labelRef = useRef<HTMLSpanElement>(null)
  useEffect(() => {
    if (!map) return
    const MAX = 110
    let label = ''
    const update = () => {
      const { lat } = map.getCenter()
      const mpp = (40075016.686 * Math.cos((lat * Math.PI) / 180)) / (512 * 2 ** map.getZoom())
      const max = mpp * MAX
      const pow = 10 ** Math.floor(Math.log10(max))
      const nice = [5, 2, 1].map((n) => n * pow).find((d) => d <= max) ?? pow
      barRef.current!.style.transform = `scaleX(${nice / max})`
      const next = nice >= 1000 ? `${nice / 1000} km` : `${nice} m`
      if (next !== label) labelRef.current!.textContent = label = next
    }
    update()
    map.on('render', update)
    return () => void map.off('render', update)
  }, [map])
  return (
    <div className="scale" aria-hidden>
      <span className="scale-bar" ref={barRef} />
      <span className="scale-label" ref={labelRef} />
    </div>
  )
}

export function MapControls({ onLogout }: { onLogout?: () => void }) {
  const map = useMapInstance()
  const layersOpen = ui.use((s) => s.layersOpen)
  const { mounted, attach } = usePresence(layersOpen, { y: -8, opacity: 0 })
  const zoom = (by: number) => map?.easeTo({ zoom: map.getZoom() + by, duration: reducedMotion() ? 0 : 250 })
  return (
    <>
      <div className="top-right" data-zone>
        <WatchlistChip />
        <ReviewChip />
        <button type="button" className={`chip ${layersOpen ? 'on' : ''}`} aria-expanded={layersOpen} aria-controls="layers-panel"
          onClick={() => ui.set((s) => ({ layersOpen: !s.layersOpen, watchlistOpen: false, reviewOpen: false }))}>
          <span className="chip-square" aria-hidden />Layers
        </button>
        {onLogout && <button type="button" className="chip chip-quiet" onClick={onLogout}>Log out</button>}
      </div>
      {mounted && <div className="layers-wrap" data-zone ref={attach}><LayersPanel /></div>}
      <div className="zoom" data-zone role="group" aria-label="Zoom">
        <button type="button" aria-label="Zoom in" onClick={() => zoom(1)}>+</button>
        <button type="button" aria-label="Zoom out" onClick={() => zoom(-1)}>−</button>
      </div>
      <ScaleBar />
    </>
  )
}
