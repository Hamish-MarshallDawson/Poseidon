import { Fragment, useEffect, useRef } from 'react'
import { SessionBar, InvitePanelSlot } from '../collab/entry/SessionBar'
import { LabChip } from '../lab/LabEntry'
import { collab } from '../collab/store'
import { ui, type UIState } from '../store/ui'
import { Switch } from '../ui'
import { useMapInstance } from '../map/context'
import { reducedMotion, usePresence } from '../motion'
import { popular } from '../data/popular'
import { ThemeSettings } from '../theme/ThemeMenu'
import { ReviewChip } from '../review/ReviewPanel'
import { DelayedLayers } from './DelayedLayers'
import { ChannelChip } from '../collab/docs/Channel'
import { SHOW_FILTERS, showFilter } from '../show/registry'
import { setShow, startShow } from '../show/state'

// Top-right buttons (Review, Display, log out), zoom on the right edge and the scale bar bottom-right
// (Figma 66:21908). The Display panel holds Show, Layers and Settings.

type LayerKey = keyof UIState['layers']
const LAYERS: { key: LayerKey; label: string }[] = [
  { key: 'density', label: 'Heat map' },
  { key: 'coverage', label: 'Coverage gaps' },
  { key: 'forecast', label: 'Forecast' },
  { key: 'inland', label: 'Inland vessels' },
  { key: 'labels', label: 'Labels' },
  { key: 'depth', label: 'Depth contours' },
]

// Single choice: which set of ships the map shows. Native radios give the arrow-key behaviour for free.
function ShowChoice() {
  const show = ui.use((s) => s.show)
  const List = showFilter(show).List
  return (
    <div className="show-choice">
      <span className="kicker ly-head" id="show-head">Show</span>
      <div role="radiogroup" aria-labelledby="show-head" className="show-group">
        {SHOW_FILTERS.map((f) => (
          <label key={f.id} className={`show-opt ${show === f.id ? 'on' : ''}`}>
            <input type="radio" name="show" value={f.id} checked={show === f.id} onChange={() => setShow(f.id)} />
            <span>{f.label}</span>
          </label>
        ))}
      </div>
      {List && <div className="show-list"><List /></div>}
    </div>
  )
}

// Live traffic, or where ships go most over time. The note is the data's own label (range, or illustrative).
function HeatChoice() {
  const heat = ui.use((s) => s.heat)
  const label = popular.use((s) => s.label)
  const loading = popular.use((s) => s.loading)
  return (
    <div className="heat-choice">
      <div role="radiogroup" aria-label="Heat map data" className="show-group heat-group">
        {([['live', 'Live'], ['popular', 'Popular places']] as const).map(([id, text]) => (
          <label key={id} className={`show-opt ${heat === id ? 'on' : ''}`}>
            <input type="radio" name="heat" value={id} checked={heat === id} onChange={() => ui.set({ heat: id })} />
            <span>{text}</span>
          </label>
        ))}
      </div>
      {heat === 'popular' && <span className="ly-note heat-note">{loading ? 'Loading…' : label?.replace('Popular places · ', '')}</span>}
    </div>
  )
}

// One panel for everything about how the map looks: Show, Layers, Settings.
function DisplayPanel() {
  const layers = ui.use((s) => s.layers)
  return (
    <div className="panel layers" id="layers-panel" role="region" aria-label="Display">
      <ShowChoice />
      <span className="kicker ly-head">Layers</span>
      {LAYERS.map(({ key, label }) => (
        <Fragment key={key}>
          <Switch checked={layers[key]} label={label}
            onChange={(on) => ui.set((s) => ({ layers: { ...s.layers, [key]: on } }))} />
          {key === 'density' && layers.density && <HeatChoice />}
        </Fragment>
      ))}
      <DelayedLayers />
      <span className="kicker ly-head">Settings</span>
      <ThemeSettings />
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
  // After the app has bound the yachts login (its effect runs after this one), so a restored yachts filter loads with a token.
  useEffect(() => void queueMicrotask(startShow), [])
  const layersOpen = ui.use((s) => s.layersOpen)
  const me = collab.use((s) => s.me)   // the profile menu has Log out once the collaboration identity is loaded
  const { mounted, attach } = usePresence(layersOpen, { y: -8, opacity: 0 })
  const zoom = (by: number) => map?.easeTo({ zoom: map.getZoom() + by, duration: reducedMotion() ? 0 : 250 })
  return (
    <>
      <div className="top-right" data-zone>
        <SessionBar onLogout={onLogout} />
        <ReviewChip />
        <ChannelChip />
        <LabChip />
        <button type="button" className={`chip ${layersOpen ? 'on' : ''}`} aria-expanded={layersOpen} aria-controls="layers-panel"
          onClick={() => ui.set((s) => ({ layersOpen: !s.layersOpen, reviewOpen: false }))}>
          <span className="chip-square" aria-hidden />Display
        </button>
        {onLogout && !me && <button type="button" className="chip chip-quiet" onClick={onLogout}>Log out</button>}
      </div>
      <InvitePanelSlot />
      {mounted && <div className="layers-wrap" data-zone ref={attach}><DisplayPanel /></div>}
      <div className="zoom" data-zone role="group" aria-label="Zoom">
        <button type="button" aria-label="Zoom in" onClick={() => zoom(1)}>+</button>
        <button type="button" aria-label="Zoom out" onClick={() => zoom(-1)}>−</button>
      </div>
      <ScaleBar />
    </>
  )
}
