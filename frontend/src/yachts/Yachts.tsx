import { useEffect, useState } from 'react'
import { Switch } from '../ui'
import { ui } from '../store/ui'
import { vessels } from '../store/vessels'
import { mapStore } from '../map/context'
import { reducedMotion } from '../motion'
import { adapter } from '../data'
import { openShipWindow } from '../windows/open'
import { useNow } from '../windows/hooks'
import { ago, loadYachts, yachts, type Yacht } from './store'
import './yachts.css'

const OS = 'OpenSanctions (CC BY-NC 4.0)'
const WP = 'Wikipedia (CC BY-SA 4.0)'
const SAT_START = Date.UTC(2026, 10, 7, 16, 51)   // recording start, used when the adapter has no history range
const fmtStart = (ms: number) =>
  new Date(ms).toLocaleString('en-GB', { timeZone: 'UTC', weekday: 'short', hour: '2-digit', minute: '2-digit', hour12: false })

function useRecordingStart(sample: boolean): number {
  const [t, setT] = useState(SAT_START)
  useEffect(() => {
    if (sample) return   // the mock range is made up
    adapter?.historyRange().then((r) => { if (r.from_ts) setT(r.from_ts < 1e12 ? r.from_ts * 1000 : r.from_ts) }, () => {})
  }, [sample])
  return t
}

// Fly to the yacht (live position, else its last fix) and open its window; same pattern as the Review list.
function focusYacht(mmsi: number) {
  const map = mapStore.get().map
  const v = vessels.vessels.get(mmsi)
  if (map && v) {
    const r = map.getContainer().getBoundingClientRect()
    // The list lives in the Layers panel (340 px, right column): centre the yacht in the map area left of it. On a
    // phone the panel spans the width, so close it instead.
    const narrow = r.width <= 720
    if (narrow) ui.set({ layersOpen: false })
    const right = narrow ? 0 : 340 + 32
    map.flyTo({ center: [v.lon, v.lat], zoom: Math.max(map.getZoom(), 7), padding: { top: 0, bottom: 0, left: 0, right }, duration: reducedMotion() ? 0 : 900, essential: true })
    openShipWindow(mmsi, { x: r.left + (r.width - right) / 2, y: r.top + r.height / 2 })
  } else openShipWindow(mmsi)
}

function Row({ y, now }: { y: Yacht; now: number }) {
  const [open, setOpen] = useState(false)
  const unseen = y.status === 'not_seen' || y.mmsi == null
  const state = y.status === 'ais' ? 'AIS heard' : y.status === 'no_ais' ? `No AIS ${ago(now - (y.last_seen_ts ?? now))}` : 'Not seen'
  return (
    <li>
      <button type="button" className="yl-row" aria-expanded={unseen ? open : undefined}
        onClick={() => (unseen ? setOpen(!open) : focusYacht(y.mmsi!))}>
        <span className={`yl-mark ${y.sanctioned ? 'is-sanctioned' : ''}`} aria-hidden />
        <span className="yl-name">{y.name ?? `IMO ${y.imo}`}</span>
        {y.sanctioned && <span className="yl-badge">Sanctioned</span>}
        <span className={`yl-state ${y.status === 'no_ais' ? 'is-noais' : ''}`}>· {state}</span>
      </button>
      {unseen && open && <YachtCard y={y} />}
    </li>
  )
}

function YachtCard({ y }: { y: Yacht }) {
  return (
    <div className="yl-card">
      <span>Length: {y.length_m != null ? `${Math.round(y.length_m)} m` : 'Not known'}</span>
      {y.owner_reported && (
        <span>
          Owner (reported): {y.owner_reported}
          {y.owner_source_url && <> · <a href={y.owner_source_url} target="_blank" rel="noreferrer">source</a></>}
        </span>
      )}
      {y.sanctioned && (
        <span>
          Sanctions: {y.programs.join(', ') || 'listed'} (
          {y.sanctions_source ? <a href={y.sanctions_source} target="_blank" rel="noreferrer">OpenSanctions</a> : 'OpenSanctions'})
        </span>
      )}
      <span>No AIS from this yacht since we started recording (Sat 7 Nov 16:51 UTC). Our receivers are mostly European.</span>
    </div>
  )
}

// The yachts list without the toggle: three sections and a "Sanctioned only" quick toggle. Rendered under the Show choice.
export function YachtsList() {
  const { list, error, sample } = yachts.use((s) => s)
  const now = useNow()
  const start = useRecordingStart(sample)
  const [onlySanctioned, setOnly] = useState(false)
  const [showUnseen, setShowUnseen] = useState(false)
  useEffect(() => void loadYachts(), [])
  const rows = (list ?? []).filter((y) => !onlySanctioned || y.sanctioned)
  const age = (y: Yacht) => now - (y.last_seen_ts ?? now)
  const heard = rows.filter((y) => y.status === 'ais')
  const quiet = rows.filter((y) => y.status === 'no_ais').sort((a, b) => age(b) - age(a))
  const unseen = rows.filter((y) => y.status === 'not_seen')
  const section = (title: string, items: Yacht[]) => items.length > 0 && (
    <section aria-label={title}>
      <h3 className="yl-head">{title} ({items.length})</h3>
      <ul className="yl-list">{items.map((y) => <Row key={y.imo} y={y} now={now} />)}</ul>
    </section>
  )
  return (
    <div className="yl">
      {sample && <p className="yl-note">Illustrative sample: made-up yachts, no backend.</p>}
      {error && <p className="yl-note">{error}</p>}
      {!list && !error && <p className="yl-note">Loading…</p>}
      {list && (
        <>
          <Switch checked={onlySanctioned} label="Sanctioned only" onChange={setOnly} />
          {section('Heard now', heard)}
          {section('Quiet: no AIS', quiet)}
          {unseen.length > 0 && (
            <section aria-label="Not seen">
              <h3 className="yl-head">
                <button type="button" className="yl-disc" aria-expanded={showUnseen} onClick={() => setShowUnseen(!showUnseen)}>
                  Not seen since recording began {fmtStart(start)} ({unseen.length})
                </button>
              </h3>
              {showUnseen && <ul className="yl-list">{unseen.map((y) => <Row key={y.imo} y={y} now={now} />)}</ul>}
            </section>
          )}
          <p className="yl-note">Sources: {OS}, {WP}.</p>
        </>
      )}
    </div>
  )
}

// The ship window's Yacht section: only for a ship that is on one of the lists.
export function YachtSection({ mmsi }: { mmsi: number }) {
  const y = yachts.use((s) => s.byMmsi.get(mmsi))
  useEffect(() => void loadYachts(), [])
  if (!y) return null
  return (
    <div className="sc-forecast yc">
      <b>Yacht</b>
      <span>Length: {y.length_m != null ? `${Math.round(y.length_m)} m` : 'Not known'}</span>
      {y.owner_reported && (
        <span>
          Owner (reported): {y.owner_reported}
          {y.owner_source_url && <> · <a href={y.owner_source_url} target="_blank" rel="noreferrer">{WP}</a></>}
        </span>
      )}
      {y.sanctioned && (
        <span>
          Sanctioned: {y.programs.join(', ') || 'listed'} (
          {y.sanctions_source ? <a href={y.sanctions_source} target="_blank" rel="noreferrer">OpenSanctions</a> : 'OpenSanctions'})
        </span>
      )}
    </div>
  )
}
