import { useEffect } from 'react'
import { Button, Kbd } from '../ui'
import { vessels } from '../store/vessels'
import { MAX_SHIPS, runBriefing } from '../briefing/store'
import { details, requestDetail } from '../windows/detail'
import { useNow, useVessel } from '../windows/hooks'
import { TYPE_LABEL, fmtMmsi, hms } from '../windows/format'
import type { VesselView } from '../types'

// Side-by-side view of the ships in the review list. Every value comes from the live VesselView or the `detail`
// reply; anything not known yet shows "—".
const WEEK = 7 * 24 * 3600 * 1000
const DASH = '—'

type Cell = (v: VesselView, now: number, d: ReturnType<typeof details.get>['byMmsi'][number] | undefined) => string
const ROWS: [string, Cell][] = [
  ['Type', (v) => TYPE_LABEL[v.type_group]],
  ['Flag', (v, _n, d) => d?.statics[0]?.flag_iso2 ?? v.flag ?? DASH],
  ['Speed', (v) => (v.sog_kn !== null ? `${v.sog_kn.toFixed(1)} kn` : DASH)],
  ['Course', (v) => (v.cog_deg !== null ? `${String(Math.round(v.cog_deg)).padStart(3, '0')}°` : DASH)],
  ['Status', (v) => (v.status === 'gap_open' || v.status === 'silent' ? 'No AIS' : 'AIS heard')],
  ['Since last AIS', (v, now) => hms(now - v.last_ts)],
  ['Ships nearby', (v) => { const g = v.open_gap_id ? vessels.gaps.get(v.open_gap_id) : undefined; return g ? `${g.neighbours_heard} within 20 km` : DASH }],
  ['Past silent gaps', (v, now, d) => (d ? `${d.gaps.filter((g) => g.start_ts > now - WEEK && g.id !== v.open_gap_id).length} in 7 days` : DASH)],
  ['Sanctions', (v) => (v.sanctioned ? 'List match' : 'No match')],
]

function Head({ mmsi, onOpen }: { mmsi: number; onOpen: () => void }) {
  const v = useVessel(mmsi)
  return (
    <th scope="col">
      <button type="button" className="rv-colhead" onClick={onOpen}>
        <b>{v?.name ?? `MMSI ${fmtMmsi(mmsi)}`}</b>
        <span>{v ? `MMSI ${fmtMmsi(mmsi)}` : 'not in view'}</span>
      </button>
    </th>
  )
}

function Value({ mmsi, cell }: { mmsi: number; cell: Cell }) {
  const v = useVessel(mmsi)
  const now = useNow()
  const d = details.use((s) => s.byMmsi[mmsi])
  return <td>{v ? cell(v, now, d) : DASH}</td>
}

export function Compare({ mmsis, onClose, onOpenShip }: { mmsis: number[]; onClose: () => void; onOpenShip: (m: number) => void }) {
  useEffect(() => { mmsis.forEach(requestDetail) }, [mmsis])
  // Capture phase: Esc closes only this view, not the review panel under it.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => { if (e.key === 'Escape') { e.preventDefault(); e.stopPropagation(); onClose() } }
    addEventListener('keydown', onKey, true)
    return () => removeEventListener('keydown', onKey, true)
  }, [onClose])
  const tooMany = mmsis.length > MAX_SHIPS
  return (
    <div className="panel rv-compare" role="dialog" aria-labelledby="rv-cmp-title">
      <div className="wl-titlerow rv-cmp-head">
        <h2 id="rv-cmp-title">Compare {mmsis.length} ships</h2>
        <Button className="btn-small" onClick={onClose}>Close <Kbd>Esc</Kbd></Button>
      </div>
      <div className="rv-cmp-scroll">
        <table className="rv-table">
          <thead>
            <tr><td />{mmsis.map((m) => <Head key={m} mmsi={m} onOpen={() => onOpenShip(m)} />)}</tr>
          </thead>
          <tbody>
            {ROWS.map(([label, cell]) => (
              <tr key={label}>
                <th scope="row">{label}</th>
                {mmsis.map((m) => <Value key={m} mmsi={m} cell={cell} />)}
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="wl-brief">
        <span>{tooMany ? `A briefing covers up to ${MAX_SHIPS} ships. Remove ${mmsis.length - MAX_SHIPS} to brief.` : 'Past gaps load when each ship reports its history.'}</span>
        <Button className="btn-small" variant="filled" disabled={tooMany} onClick={() => runBriefing(mmsis)}>Brief me on these</Button>
      </div>
    </div>
  )
}
