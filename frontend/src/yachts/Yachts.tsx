import { useEffect } from 'react'
import { Switch } from '../ui'
import { vessels } from '../store/vessels'
import { openShipWindow } from '../windows/open'
import { useNow } from '../windows/hooks'
import { ago, listOrder, loadYachts, setYachtsLayer, yachts } from './store'
import './yachts.css'

const OS = 'OpenSanctions (CC BY-NC 4.0)'
const WP = 'Wikipedia (CC BY-SA 4.0)'

// The Layers panel part: the toggle and, when on, the matched yachts with silent ones first.
export function YachtsLayer() {
  const { on, list, error } = yachts.use((s) => s)
  const now = useNow()
  const rows = list ? listOrder(list) : []
  const notSeen = list ? list.length - rows.length : 0
  return (
    <>
      <Switch checked={on} label="Sanctioned and notable yachts" hint="matched by IMO · OpenSanctions, Wikipedia"
        onChange={setYachtsLayer} />
      {on && (
        <div className="yl">
          {error && <p className="yl-note">{error}</p>}
          {!list && !error && <p className="yl-note">Loading…</p>}
          {rows.length > 0 && (
            <ul className="yl-list">
              {rows.map((y) => {
                const live = y.mmsi != null && vessels.vessels.has(y.mmsi)
                const state = y.status === 'ais' ? 'AIS heard' : `No AIS ${ago(now - (y.last_seen_ts ?? now))}`
                const text = (
                  <>
                    <span className={`yl-mark ${y.sanctioned ? 'is-sanctioned' : ''}`} aria-hidden />
                    <span className="yl-name">{y.name ?? `IMO ${y.imo}`}</span>
                    <span className={`yl-state ${y.status === 'no_ais' ? 'is-noais' : ''}`}>· {state}</span>
                    {y.sanctioned && <span className="yl-sr">, sanctioned</span>}
                  </>
                )
                return (
                  <li key={y.imo}>
                    {live
                      ? <button type="button" className="yl-row" onClick={() => openShipWindow(y.mmsi!)}>{text}</button>
                      : <span className="yl-row is-off" title="Not on the map now">{text}</span>}
                  </li>
                )
              })}
            </ul>
          )}
          {list && <p className="yl-note">{notSeen > 0 && `${notSeen} more not seen in our data. `}Sources: {OS}, {WP}.</p>}
        </div>
      )}
    </>
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
