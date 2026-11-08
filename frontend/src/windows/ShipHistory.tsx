import { useEffect, useState } from 'react'
import { getHistory, type ShipHistory as History } from '../ports/history'
import { loadPorts, nearestPort } from '../ports'
import type { PortIndex } from '../ports'
import type { Observation } from '../types'

const MON = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const LABEL: Record<string, string> = { port_visit: 'Port visit', loitering: 'Loitering', encounter: 'Encounter' }

const ago = (ms: number) => (ms < 48 * 3_600_000 ? `${Math.max(1, Math.round(ms / 3_600_000))} h ago` : `${Math.round(ms / 86_400_000)} d ago`)
const hours = (h: number | null) => (h == null ? '' : h < 1 ? '< 1 h' : h < 48 ? `${Math.round(h)} h` : `${Math.round(h / 24)} d`)
const when = (ts: number) => {
  const d = new Date(ts)
  return `${d.getUTCDate()} ${MON[d.getUTCMonth()]} ${String(d.getUTCHours()).padStart(2, '0')}:${String(d.getUTCMinutes()).padStart(2, '0')}Z`
}
const at = (o: Observation) => o.end_ts ?? o.ts

function place(o: Observation, ports: PortIndex | null): string {
  const p = o.lat != null && o.lon != null && ports ? nearestPort(ports, o.lat, o.lon) : null
  if (o.kind === 'encounter' && o.attrs?.other_vessel?.name) return `with ${o.attrs.other_vessel.name}`
  if (p) return o.kind === 'port_visit' ? p.name : `near ${p.name}`
  return o.lat != null && o.lon != null ? `${o.lat.toFixed(1)}°, ${o.lon.toFixed(1)}°` : 'at sea'
}

// One line under From → To: last port, loitering and encounters from GFW; click for the list. Nothing while loading,
// on an error, or when the ship has no such events.
export function ShipHistory({ mmsi, now }: { mmsi: number; now: number }) {
  const [res, setRes] = useState<{ mmsi: number; h: History | null; ports: PortIndex | null }>({ mmsi, h: null, ports: null })
  const [open, setOpen] = useState(false)
  useEffect(() => {
    let live = true
    Promise.all([getHistory(mmsi), loadPorts().catch(() => null)]).then(([h, ports]) => live && setRes({ mmsi, h, ports }), () => {})
    return () => { live = false }
  }, [mmsi])
  if (res.mmsi !== mmsi || !res.h || !res.h.rows.length) return null
  const { rows, days, attribution } = res.h, ports = res.ports
  const sorted = [...rows].sort((a, b) => at(b) - at(a))
  const last = sorted.find((o) => o.kind === 'port_visit')
  const loiter = rows.filter((o) => o.kind === 'loitering').length
  const meet = rows.filter((o) => o.kind === 'encounter').length
  const line = [
    last && `Last port ${place(last, ports)}, ${ago(now - at(last))}`,
    loiter > 0 && `${loiter} loitering in ${days} d`,
    meet > 0 && `${meet} encounter${meet > 1 ? 's' : ''}${last || loiter ? '' : ` in ${days} d`}`,
  ].filter(Boolean).join(' · ')
  return (
    <div className="sc-hist">
      <button type="button" className="sc-hist-line" aria-expanded={open} onClick={() => setOpen(!open)}>
        <span aria-hidden>{open ? '▾' : '▸'}</span> {line}
      </button>
      {open && (
        <>
          <ul className="sc-hist-list">
            {sorted.slice(0, 8).map((o) => (
              <li key={o.id}>{LABEL[o.kind]} · {place(o, ports)} · {when(o.ts)}{o.value != null && ` · ${hours(o.value)}`}</li>
            ))}
          </ul>
          <small className="sc-hist-src">{attribution}</small>
        </>
      )}
    </div>
  )
}
