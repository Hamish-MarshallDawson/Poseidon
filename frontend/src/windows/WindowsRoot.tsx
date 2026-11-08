import { useEffect } from 'react'
import { ui } from '../store/ui'
import { StatusLine } from '../panels/StatusLine'
import { MapControls } from '../panels/MapControls'
import { Watchlist } from '../panels/Watchlist'
import { Legend } from '../panels/Legend'
import { FocusBar } from '../panels/FocusBar'
import { WindowLayer } from './ShipWindow'
import { LeaderLines } from './Leader'
import { clampWindows, closeShipWindow } from './open'
import '../panels/panels.css'
import './windows.css'

// Everything the windows agent puts over the map, in one mount: <WindowsRoot onLogout={...} />.
// Esc closes the innermost thing: the window holding keyboard focus, then the layers pop-over, the watchlist,
// the legend, focus mode, and finally the front window.
function onKey(e: KeyboardEvent) {
  if (e.key !== 'Escape' || e.defaultPrevented) return
  const s = ui.get()
  const inWindow = (document.activeElement as HTMLElement | null)?.closest<HTMLElement>('.sw')
  if (inWindow) closeShipWindow(Number(inWindow.dataset.mmsi))
  else if (s.layersOpen) ui.set({ layersOpen: false })
  else if (s.watchlistOpen) ui.set({ watchlistOpen: false })
  else if (s.reviewOpen) ui.set({ reviewOpen: false })
  else if (s.legendOpen) ui.set({ legendOpen: false })
  else if (s.focusMmsi !== null) ui.set({ focusMmsi: null, focusRelated: [] })
  else if (s.frontMmsi !== null) closeShipWindow(s.frontMmsi)
  else return
  e.preventDefault()
}

export function WindowsRoot({ onLogout }: { onLogout?: () => void }) {
  useEffect(() => {
    let raf = 0
    const onResize = () => { cancelAnimationFrame(raf); raf = requestAnimationFrame(clampWindows) }
    addEventListener('keydown', onKey)
    addEventListener('resize', onResize)
    return () => {
      removeEventListener('keydown', onKey)
      removeEventListener('resize', onResize)
      cancelAnimationFrame(raf)
    }
  }, [])
  return (
    <div className="dvm-overlay">
      <LeaderLines />
      <StatusLine />
      <FocusBar />
      <MapControls onLogout={onLogout} />
      <Watchlist />
      <Legend />
      <WindowLayer />
    </div>
  )
}
