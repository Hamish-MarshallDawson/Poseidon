import { useState } from 'react'
import { ui } from '../store/ui'
import { vessels } from '../store/vessels'
import { Button, Kbd } from '../ui'
import { mapStore } from '../map/context'
import { reducedMotion, usePresence } from '../motion'
import { openShipWindow } from '../windows/open'
import { useNow, useVessel } from '../windows/hooks'
import { TYPE_LABEL, hms } from '../windows/format'
import { MAX_SHIPS, briefing, clearSelected, runBriefing, toggleSelected } from '../briefing/store'
import { forecastUi } from '../forecast/state'
import { collab, listAdd, listRemove, useInSession } from '../collab/presence/core'
import { AddedBy, ReportTag, SessionActivity, SessionOnline, StatusSelect, Viewing } from '../collab/presence/SharedList'
import { review, removeReview, clearReview, dismissSystem, restoreSystem, toggleReview } from './store'
import { systemReason, useReviewItems, type Item } from './items'
import { Compare } from './Compare'
import './review.css'

// The one Review list (a chip and a panel in the Watchlist panel style): the viewer's own ships, or the session's shared
// list, then the System entries from the forecast. Rows subscribe to their own ship and the 1 Hz clock, so nothing
// renders while the panel is closed. Tick boxes pick ships for Compare and Brief (the briefing store's selection).

const PANEL_W = 360

export function ReviewChip() {
  const open = ui.use((s) => s.reviewOpen)
  const { items } = useReviewItems()
  return (
    <button type="button" className={`chip ${open ? 'on' : ''}`} aria-expanded={open} aria-controls="review-panel"
      onClick={() => ui.set((s) => ({ reviewOpen: !s.reviewOpen, layersOpen: false }))}>
      <span className="lamp" aria-hidden />
      Review
      <span className="chip-count">{items.length}</span>
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

const hover = (mmsi: number | null) => ui.set({ hoverMmsi: mmsi })

function Row({ item, picked, full }: { item: Item; picked: boolean; full: boolean }) {
  const { mmsi } = item
  const v = useVessel(mmsi)
  const now = useNow()
  const noAis = !!v && (v.status === 'gap_open' || v.status === 'silent')
  const name = v?.name ?? `MMSI ${mmsi}`
  const drop = () => { if (picked) toggleSelected(mmsi) }
  // A System entry the viewer adds becomes theirs: in a session it joins the shared list, otherwise their own.
  const add = () => (collab.get().session ? void listAdd(mmsi) : toggleReview(mmsi))
  return (
    <li className={`wl-item rv-item ${noAis ? 'is-noais' : ''}`} data-mmsi={mmsi} data-kind={item.kind}
      onPointerEnter={() => hover(mmsi)} onPointerLeave={() => hover(null)}>
      <input type="checkbox" className="wl-pick" aria-label={`Select ${name} to compare or brief`}
        checked={picked} disabled={!picked && full} onChange={() => toggleSelected(mmsi)} />
      <div className="wl-body">
        <span className="wl-head">
          <span className="wl-name"><b>{name}</b>{v && <span>{TYPE_LABEL[v.type_group]}</span>}</span>
          {v && <span className="rv-timer" title="Since last AIS">{noAis ? 'No AIS' : 'AIS'} {hms(now - v.last_ts)}</span>}
          {item.kind === 'shared' && <ReportTag mmsi={mmsi} />}
        </span>
        <span className="wl-note">
          {item.kind === 'system' && systemReason(item.row)}
          {item.kind === 'you' && 'You'}
          {item.kind === 'shared' && <AddedBy e={item.entry} />}
        </span>
        {item.kind === 'shared' && <Viewing mmsi={mmsi} />}
        <span className="rv-actions">
          {item.kind === 'shared' && <StatusSelect e={item.entry} name={name} />}
          {item.kind === 'system' && <Button className="btn-small" aria-label={`Add ${name} to the list`} onClick={add}>Add</Button>}
          <Button className="btn-small" onClick={() => focusOnMap(mmsi)}>Focus on map</Button>
          {item.kind === 'system'
            ? <Button className="btn-small" aria-label={`Dismiss ${name}`} onClick={() => { drop(); dismissSystem(mmsi) }}>Dismiss</Button>
            : <Button className="btn-small" aria-label={`Remove ${name} from the list`}
                onClick={() => { drop(); void (item.kind === 'shared' ? listRemove(mmsi) : removeReview(mmsi)) }}>Remove</Button>}
        </span>
      </div>
    </li>
  )
}

function ReviewPanel({ onCompare }: { onCompare: () => void }) {
  const { items, dismissed } = useReviewItems()
  const inSession = useInSession()
  const picked = briefing.use((b) => b.selected)
  const mine = review.use((s) => s.list.length)
  return (
    <div className="panel watchlist" id="review-panel" role="region" aria-labelledby="rv-title">
      <div className="wl-header">
        <div className="wl-titlerow">
          <h2 id="rv-title">Review</h2>
          <Button className="btn-small" onClick={() => ui.set({ reviewOpen: false })}>Close <Kbd>Esc</Kbd></Button>
        </div>
      </div>
      {inSession && <SessionOnline />}
      {items.length === 0 ? (
        <p className="rv-empty">Nothing yet. Open a ship and choose Add to review{inSession ? ': everyone in the session sees it' : ''}.</p>
      ) : (
        <ul className="wl-list rv-list">
          {items.map((i) => <Row key={i.mmsi} item={i} picked={picked.includes(i.mmsi)} full={picked.length >= MAX_SHIPS} />)}
        </ul>
      )}
      {inSession && <SessionActivity />}
      {items.length > 0 && (
        <div className="wl-brief">
          <span>{picked.length > 0 ? `${picked.length} selected${picked.length >= MAX_SHIPS ? ' (most)' : ''}` : 'Tick ships to compare or brief'}</span>
          <span className="wl-brief-actions">
            {picked.length > 0 && <Button className="btn-small" onClick={clearSelected}>Clear</Button>}
            <Button className="btn-small" disabled={picked.length < 2} onClick={onCompare}>Compare</Button>
            <Button className="btn-small" variant="filled" disabled={picked.length === 0} onClick={() => runBriefing(picked)}>
              Brief {picked.length || ''} {picked.length === 1 ? 'ship' : 'ships'}
            </Button>
          </span>
        </div>
      )}
      <div className="rv-foot">
        <button type="button" className="rv-link" onClick={() => forecastUi.set({ checkOpen: true })}>Prospective test running…</button>
        {mine > 0 && !inSession && <button type="button" className="rv-link" onClick={clearReview}>Clear mine</button>}
        {dismissed > 0 && <button type="button" className="rv-link" onClick={restoreSystem}>Restore {dismissed} dismissed</button>}
      </div>
    </div>
  )
}

export function Review() {
  const open = ui.use((s) => s.reviewOpen)
  const picked = briefing.use((b) => b.selected)
  const [comparing, setComparing] = useState(false)
  const { mounted, attach } = usePresence(open, { y: -12, opacity: 0 })
  return (
    <>
      {mounted && <div className="watchlist-wrap" data-zone ref={attach}><ReviewPanel onCompare={() => setComparing(true)} /></div>}
      {/* Outside the wrap: its presence transform would make a fixed child position against the wrap. */}
      {comparing && picked.length >= 2 && <Compare mmsis={picked} onClose={() => setComparing(false)} onOpenShip={openShipWindow} />}
    </>
  )
}
