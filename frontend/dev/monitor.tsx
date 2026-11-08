// Dev-server only: the real <Monitor/> without the Auth0 login gate, for scripts/overlap.mjs and manual checks.
// Vite builds only index.html, so this page is never in dist/ and never deployed.
import { createRoot } from 'react-dom/client'
import '../src/index.css'
import '../src/theme/theme'
import { Monitor } from '../src/App'
import { ui } from '../src/store/ui'
import { vessels } from '../src/store/vessels'
import { openShipWindow, shipScreenPoint } from '../src/windows/open'
import { runBriefing } from '../src/briefing/store'
import { yachts } from '../src/yachts/store'
import { setShow } from '../src/show/state'
import { DelayedLayers } from '../src/panels/DelayedLayers'
import { startClock } from '../src/timeline/replay'

// The synthetic feed forces mode 'live' every second; while __hold is set, keep the replay mode a test chose.
const rawSet = ui.set.bind(ui) as (p: unknown) => void
;(ui as unknown as { set: (p: unknown) => void }).set = (p) => rawSet((st: ReturnType<typeof ui.get>) => {
  const patch = typeof p === 'function' ? (p as (s: unknown) => Record<string, unknown>)(st) : (p as Record<string, unknown>)
  const f = patch.feed as { mode?: string } | undefined
  if (f && dev.hold && st.feed.mode === 'replay' && f.mode === 'live') return { ...patch, feed: { ...f, mode: 'replay', paused: st.feed.paused, speed: st.feed.speed, now_ts: st.feed.now_ts } }
  return patch
})
const dev = {
  hold: false,
  ui,
  vessels,
  yachts,
  setShow,
  openShipWindow,
  shipScreenPoint,
  runBriefing,
  replay() { dev.hold = true; ui.set((s) => ({ feed: { ...s.feed, mode: 'replay', paused: true } })) },
}
;(window as unknown as { __dev: typeof dev }).__dev = dev
startClock()
createRoot(document.getElementById('root')!).render(<>
  <Monitor getToken={async () => undefined} onLogout={() => {}} />
  {/* Temporary test mount: the lead mounts <DelayedLayers /> in the Display panel. Dev page only, with ?delayed. */}
  {location.search.includes('delayed') && <div className="panel" style={{ position: 'fixed', left: 16, top: 70, width: 300, zIndex: 50 }}><DelayedLayers /></div>}
</>)
