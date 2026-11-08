import { useState } from 'react'
import { ui } from '../store/ui'
import { vessels } from '../store/vessels'
import { Button, Kbd } from '../ui'
import { mapStore } from '../map/context'
import { reducedMotion, usePresence } from '../motion'
import { openShipWindow } from '../windows/open'
import { useNow, useVessel } from '../windows/hooks'
import { TYPE_LABEL, fmtMmsi, hms } from '../windows/format'
import { review, removeReview, clearReview } from './store'
import { Compare } from './Compare'
import './review.css'

// The review list: a summon chip beside "Ranked for review" and a panel in the Watchlist's style.
// Rows subscribe to their own ship (and the 1 Hz clock), so nothing renders while the panel is closed.

const PANEL_W = 360

export function ReviewChip() {
  const open = ui.use((s) => s.reviewOpen)
  const n = review.use((s) => s.list.length)
  return (
    <button type="button" className={`chip ${open ? 'on' : ''}`} aria-expanded={open} aria-controls="review-panel"
      onClick={() => ui.set((s) => ({ reviewOpen: !s.reviewOpen, watchlistOpen: false, layersOpen: false }))}>
      <span className="lamp" aria-hidden />
      Review list
      <span className="chip-count">{n}</span>
    </button>
  )
}

function focusOnMap(mmsi: number) {
  const map = mapStore.get().map
  const v = vessels.vessels.get(mmsi)
  if (map && v) {
    const padding = { top: 0, bottom: 0, left: 0, right: PANEL_W + 16 }
    const r = map.getContainer().getBoundingClientRect()
    map.flyTo({ center: [v.lon, v.lat], zoom: Math.max(map.getZoom(), 7), padding, duration: reducedMotion() ? 0 : 900, essential: true })
    openShipWindow(mmsi, { x: r.left + (r.width - padding.right) / 2, y: r.top + r.height / 2 })
  } else openShipWindow(mmsi)
}

function Row({ mmsi }: { mmsi: number }) {
  const v = useVessel(mmsi)
  const now = useNow()
  const noAis = !!v && (v.status === 'gap_open' || v.status === 'silent')
  const name = v?.name ?? `MMSI ${fmtMmsi(mmsi)}`
  return (
    <li className={`rv-item ${noAis ? 'is-noais' : ''}`}>
      <div className="wl-body">
        <span className="wl-head">
          <span className="wl-name"><b>{name}</b>{v && <span>{TYPE_LABEL[v.type_group]}</span>}</span>
        </span>
        <span className="wl-note">
          MMSI {fmtMmsi(mmsi)} · {v ? <>{noAis ? 'No AIS' : 'AIS heard'} · <span className="rv-timer">{hms(now - v.last_ts)}</span> since last AIS</> : 'not in view / no data'}
        </span>
        <span className="rv-actions">
          <Button className="btn-small" onClick={() => focusOnMap(mmsi)}>Focus on map</Button>
          <Button className="btn-small" aria-label={`Remove ${name} from review`} onClick={() => removeReview(mmsi)}>Remove</Button>
        </span>
      </div>
    </li>
  )
}

function ReviewPanel({ onCompare }: { onCompare: () => void }) {
  const list = review.use((s) => s.list)
  return (
      <div className="panel watchlist" id="review-panel" role="region" aria-labelledby="rv-title">
        <div className="wl-header">
          <div className="wl-titlerow">
            <h2 id="rv-title">Review list</h2>
            <Button className="btn-small" onClick={() => ui.set({ reviewOpen: false })}>Close <Kbd>Esc</Kbd></Button>
          </div>
          <p className="wl-explain">Ships you added from their windows. Kept in this browser only.</p>
          <p className="wl-meta">{list.length} {list.length === 1 ? 'ship' : 'ships'} in review</p>
        </div>
        {list.length === 0 ? (
          <p className="rv-empty">Nothing yet. Open a ship and choose Add to review.</p>
        ) : (
          <ul className="wl-list rv-list">{list.map((m) => <Row key={m} mmsi={m} />)}</ul>
        )}
        {list.length > 0 && (
          <div className="wl-brief">
            <span>{list.length} in review</span>
            <span className="wl-brief-actions">
              <Button className="btn-small" onClick={clearReview}>Clear</Button>
              <Button className="btn-small" variant="filled" disabled={list.length < 2} onClick={onCompare}>Compare {list.length} ships</Button>
            </span>
          </div>
        )}
      </div>
  )
}

export function Review() {
  const open = ui.use((s) => s.reviewOpen)
  const list = review.use((s) => s.list)
  const [comparing, setComparing] = useState(false)
  const { mounted, attach } = usePresence(open, { y: -12, opacity: 0 })
  return (
    <>
      {mounted && <div className="watchlist-wrap" data-zone ref={attach}><ReviewPanel onCompare={() => setComparing(true)} /></div>}
      {/* Outside the wrap: its presence transform would make a fixed child position against the wrap. */}
      {comparing && list.length >= 2 && <Compare mmsis={list} onClose={() => setComparing(false)} onOpenShip={openShipWindow} />}
    </>
  )
}
