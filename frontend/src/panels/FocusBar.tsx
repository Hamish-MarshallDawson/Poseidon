import { useState } from 'react'
import { ui, type FocusRelation } from '../store/ui'
import { useVessel } from '../windows/hooks'
import { TYPE_LABEL, fmtMmsi } from '../windows/format'

// Focus bar (density report, focus mode 39:1366): "FOCUS · name · type · MMSI", reason chips for the related
// ships, a breadcrumb when focus moved from one ship to another, and "Leave focus [Esc]".

const REASON_LABEL: Record<FocusRelation['reason'], string> = {
  nearby: 'Nearby', rendezvous: 'Possible rendezvous', also_dark: 'Also no AIS', same_flag: 'Same flag',
}

function Crumb({ mmsi, onClick }: { mmsi: number; onClick: () => void }) {
  const v = useVessel(mmsi)
  return <button type="button" className="fb-crumb" onClick={onClick}>{v?.name ?? fmtMmsi(mmsi)}</button>
}

export function FocusBar() {
  const focus = ui.use((s) => s.focusMmsi)
  const related = ui.use((s) => s.focusRelated)
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

  const counts = new Map<FocusRelation['reason'], number>()
  for (const r of related) counts.set(r.reason, (counts.get(r.reason) ?? 0) + 1)

  return (
    <div className="panel focus-bar" role="region" aria-label="Focus">
      <span className="kicker">Focus</span>
      {trail.path.map((m) => (
        <span key={m} className="fb-step"><Crumb mmsi={m} onClick={() => ui.set({ focusMmsi: m })} /><span aria-hidden>›</span></span>
      ))}
      <span className="fb-name">
        <b>{v?.name ?? fmtMmsi(focus)}</b>
        {v && ` · ${TYPE_LABEL[v.type_group]} · MMSI ${fmtMmsi(focus)}`}
      </span>
      <span className="fb-reasons">
        {related.length === 0 && <span className="fb-none">No related ships shown</span>}
        {[...counts].map(([reason, n]) => <span key={reason} className="reason-chip">{REASON_LABEL[reason]} {n}</span>)}
      </span>
      <button type="button" className="btn btn-small" onClick={() => ui.set({ focusMmsi: null, focusRelated: [] })}>
        Leave focus <kbd>Esc</kbd>
      </button>
    </div>
  )
}
