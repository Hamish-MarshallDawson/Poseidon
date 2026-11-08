import { useState } from 'react'
import { Button, Kbd } from '../ui'
import { ui } from '../store/ui'
import { useVessel } from '../windows/hooks'
import { setFocus } from '../map/actions'
import { fmtMmsi } from '../windows/format'
import { openShipWindow } from '../windows/open'
import { fmtKm, utcTime } from '../map/focus'

// Focus bar ("Nearby ships"): the focused ship, how many ships came within 5 km of its track in 6 h, a list of them with
// their closest approach (a row opens that ship's window), a breadcrumb when focus moved from one ship to another, and
// "Leave [Esc]".

function Row({ r }: { r: { mmsi: number; cpaM: number; cpaTs: number; met: boolean } }) {
  const v = useVessel(r.mmsi)
  return (
    <li>
      <button type="button" className="fb-row" onClick={() => openShipWindow(r.mmsi)}>
        <b>{v?.name ?? fmtMmsi(r.mmsi)}</b>
        <span>{utcTime(r.cpaTs)} · {fmtKm(r.cpaM)}</span>
        {r.met && <span className="reason-chip">Both slow, within 500 m</span>}
      </button>
    </li>
  )
}

function Crumb({ mmsi, onClick }: { mmsi: number; onClick: () => void }) {
  const v = useVessel(mmsi)
  return <button type="button" className="fb-crumb" onClick={onClick}>{v?.name ?? fmtMmsi(mmsi)}</button>
}

export function FocusBar() {
  const focus = ui.use((s) => s.focusMmsi)
  const related = ui.use((s) => s.focusRelated)
  const loading = ui.use((s) => s.focusLoading)
  const v = useVessel(focus ?? -1)
  // Breadcrumb trail: derived during render from focus changes, cleared when focus is left.
  const [trail, setTrail] = useState<{ last: number | null; path: number[] }>({ last: focus, path: [] })
  if (trail.last !== focus) {
    const back = trail.path.indexOf(focus ?? -1)
    setTrail({
      last: focus,
      path: focus === null ? [] : back >= 0 ? trail.path.slice(0, back) : trail.last !== null ? [...trail.path, trail.last] : [],
    })
  }
  if (focus === null) return null

  const name = v?.name ?? fmtMmsi(focus)
  const n = related.length

  return (
    <div className="panel focus-bar" data-zone role="region" aria-label="Nearby ships">
      <div className="fb-head">
        {trail.path.map((m) => (
          <span key={m} className="fb-step"><Crumb mmsi={m} onClick={() => ui.set({ focusMmsi: m })} /><span aria-hidden>›</span></span>
        ))}
        <span className="fb-name">
          Nearby ships · <b>{name}</b> · {loading ? 'Finding ships near the track…' : n ? `${n} within 5 km in 6 h` : 'none within 5 km in 6 h'}
        </span>
        <Button className="btn-small" onClick={() => setFocus(null)}>
          Leave <Kbd>Esc</Kbd>
        </Button>
      </div>
      {n > 0 && !loading && <ul className="fb-list">{related.map((r) => <Row key={r.mmsi} r={r} />)}</ul>}
    </div>
  )
}
