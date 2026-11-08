import { useEffect, useRef, useState } from 'react'
import { ui } from '../../store/ui'
import { vessels } from '../../store/vessels'
import { Button, Kbd } from '../../ui'
import { mapStore } from '../../map/context'
import { reducedMotion, usePresence } from '../../motion'
import { openShipWindow } from '../../windows/open'
import { useVessel } from '../../windows/hooks'
import { fmtMmsi, utcTime } from '../../windows/format'
import { collab } from '../store'
import type { Doc, Member } from '../client'
import { NOTE_MAX, initials, pinnedSummary, tokenize } from './logic'
import { channel, closeChannel, openChannel, sendNote, summariseSession } from './store'
import './channel.css'

// The session channel (right column): notes on the whole session or one ship, saved briefings, and the pinned summary.
// Everything is rendered as text. Documents are append-only: there is no edit or delete.

const PANEL_W = 360

function focusShip(mmsi: number) {
  const map = mapStore.get().map
  const v = vessels.vessels.get(mmsi)
  if (map && v) {
    const r = map.getContainer().getBoundingClientRect()
    const padding = { top: 0, bottom: 0, left: 0, right: PANEL_W + 16 }
    map.flyTo({ center: [v.lon, v.lat], zoom: Math.max(map.getZoom(), 7), padding, duration: reducedMotion() ? 0 : 900, essential: true })
    openShipWindow(mmsi, { x: r.left + (r.width - padding.right) / 2, y: r.top + r.height / 2 })
  } else openShipWindow(mmsi)
}

function ShipName({ mmsi }: { mmsi: number }) {
  const v = useVessel(mmsi)
  return <>{v?.name ?? `MMSI ${fmtMmsi(mmsi)}`}</>
}

function ShipRef({ mmsi }: { mmsi: number }) {
  return <button type="button" className="ch-ref" onClick={() => focusShip(mmsi)}><ShipName mmsi={mmsi} /></button>
}

export function Avatar({ m }: { m: Pick<Member, 'name' | 'picture'> | undefined }) {
  const [bad, setBad] = useState(false)
  return m?.picture && !bad
    ? <img className="ch-avatar" src={m.picture} alt="" width={24} height={24} referrerPolicy="no-referrer" onError={() => setBad(true)} />
    : <span className="ch-avatar ch-avatar-i" aria-hidden>{initials(m?.name ?? null)}</span>
}

function Body({ text, docIds }: { text: string; docIds: Set<number> }) {
  return (
    <p className="ch-text">
      {tokenize(text).map((p, i) =>
        'text' in p ? p.text
        : 'ship' in p ? <ShipRef key={i} mmsi={p.ship} />
        : docIds.has(p.doc) ? <button key={i} type="button" className="ch-ref" onClick={() => channel.set({ openDoc: p.doc })}>doc#{p.doc}</button>
        : `doc#${p.doc}`)}
    </p>
  )
}

function Item({ d, members, docIds, onQuote }: { d: Doc; members: Member[]; docIds: Set<number>; onQuote: (ref: string) => void }) {
  const who = members.find((m) => m.id === d.author_id)
  const hit = channel.use((s) => s.openDoc === d.id)
  const ref = useRef<HTMLLIElement>(null)
  useEffect(() => { if (hit) ref.current?.scrollIntoView({ block: 'nearest' }) }, [hit])
  const [open, setOpen] = useState(false)
  const ships = d.mmsis.length ? d.mmsis : d.mmsi ? [d.mmsi] : []
  const isNote = d.kind === 'note'
  return (
    <li ref={ref} className={`ch-item ch-${d.kind} ${hit ? 'is-hit' : ''}`} id={`ch-doc-${d.id}`}>
      <Avatar m={who} />
      <div className="ch-main">
        <span className="ch-meta">
          <b>{who?.name ?? 'A member'}</b>
          <span>{utcTime(d.created_at, false)}</span>
          <button type="button" className="ch-id" title="Quote this item in a note" onClick={() => onQuote(`doc#${d.id}`)}>doc#{d.id}</button>
        </span>
        {isNote ? (
          <>
            {d.mmsi && <span className="ch-about">About <ShipRef mmsi={d.mmsi} /></span>}
            <Body text={d.body} docIds={docIds} />
          </>
        ) : (
          <>
            <span className="ch-kind">{d.kind === 'summary' ? 'Session summary' : `Briefing · ${ships.length} ${ships.length === 1 ? 'ship' : 'ships'}`}</span>
            {d.kind === 'briefing' && <span className="ch-ships">{ships.map((m) => <ShipRef key={m} mmsi={m} />)}</span>}
            {open || hit || d.kind === 'summary'
              ? <p className="ch-text ch-doc">{d.body}</p>
              : <Button className="btn-small" aria-expanded={false} onClick={() => setOpen(true)}>Open briefing</Button>}
          </>
        )}
      </div>
    </li>
  )
}

function Composer() {
  const [text, setText] = useState('')
  const [about, setAbout] = useState(false)
  const [err, setErr] = useState<string | null>(null)
  const front = ui.use((s) => s.frontMmsi)
  const send = async () => {
    if (!text.trim()) return
    try { await sendNote(text, about ? front : null); setText(''); setErr(null) } catch { setErr('The note could not be sent. Try again.') }
  }
  useEffect(() => {
    const onQuote = (e: Event) => setText((t) => `${t}${t && !t.endsWith(' ') ? ' ' : ''}${(e as CustomEvent<string>).detail} `)
    addEventListener('ch-quote', onQuote)
    return () => removeEventListener('ch-quote', onQuote)
  }, [])
  return (
    <form className="ch-compose" onSubmit={(e) => { e.preventDefault(); void send() }}>
      <p className="ch-banner">A flag is a prompt to review, not an accusation.</p>
      {front !== null && (
        <label className="ch-about-pick">
          <input type="checkbox" checked={about} onChange={(e) => setAbout(e.target.checked)} /> About <ShipName mmsi={front} />
        </label>
      )}
      <textarea
        aria-label="Note" placeholder="Say what you see (plain text)" rows={2} maxLength={NOTE_MAX} value={text}
        onChange={(e) => setText(e.target.value)}
        onKeyDown={(e) => { if (e.key === 'Enter' && !e.shiftKey) { e.preventDefault(); void send() } }}
      />
      <div className="ch-compose-row">
        <span className="ch-count">{text.length > NOTE_MAX * 0.8 ? `${text.length}/${NOTE_MAX}` : 'Enter sends, Shift+Enter adds a line'}</span>
        <Button type="submit" variant="filled" className="btn-small" disabled={!text.trim()}>Send</Button>
      </div>
      {err && <p className="ch-err" role="alert">{err}</p>}
    </form>
  )
}

function ChannelPanel() {
  const session = collab.use((s) => s.session)
  const docs = collab.use((s) => s.documents)
  const { summary, summaryError, offer } = channel.use((s) => s)
  const feed = useRef<HTMLUListElement>(null)
  const pinned = pinnedSummary(docs)
  const rest = docs.filter((d) => d !== pinned)
  const docIds = new Set(docs.map((d) => d.id))
  const members = session?.members ?? []
  useEffect(() => { feed.current?.scrollTo({ top: feed.current.scrollHeight }) }, [docs.length])
  const quote = (ref: string) => dispatchEvent(new CustomEvent('ch-quote', { detail: ref }))
  return (
    <div className="panel watchlist ch-panel" id="channel-panel" role="region" aria-labelledby="ch-title">
      <div className="wl-header">
        <div className="wl-titlerow">
          <h2 id="ch-title">Channel</h2>
          <Button className="btn-small" onClick={closeChannel}>Close <Kbd>Esc</Kbd></Button>
        </div>
        <p className="wl-meta">{docs.length} {docs.length === 1 ? 'item' : 'items'}</p>
        <span className="ch-summarise">
          <Button className="btn-small" disabled={summary === 'busy'} onClick={() => void summariseSession()}>
            {summary === 'busy' ? 'Summarising…' : 'Summarise session'}
          </Button>
          {summary === 'error' && <span className="ch-err" role="alert">{summaryError}</span>}
        </span>
      </div>
      {offer && (
        <div className="ch-offer" role="status">
          <span>Everyone else has left. Summarise this session?</span>
          <Button className="btn-small" variant="filled" onClick={() => void summariseSession()}>Summarise</Button>
          <Button className="btn-small" onClick={() => channel.set({ offer: false })}>Not now</Button>
        </div>
      )}
      {pinned && <ul className="ch-pinned"><Item d={pinned} members={members} docIds={docIds} onQuote={quote} /></ul>}
      {rest.length === 0 && !pinned
        ? <p className="rv-empty">Nothing yet. Notes and saved briefings appear here.</p>
        : <ul className="ch-feed" ref={feed} aria-live="polite">{rest.map((d) => <Item key={d.id} d={d} members={members} docIds={docIds} onQuote={quote} />)}</ul>}
      <Composer />
    </div>
  )
}

export function ChannelChip() {
  const inSession = collab.use((s) => s.session !== null)
  const open = channel.use((s) => s.open)
  const n = collab.use((s) => s.documents.length)
  if (!inSession) return null
  return (
    <button type="button" className={`chip ${open ? 'on' : ''}`} aria-expanded={open} aria-controls="channel-panel"
      onClick={() => (open ? closeChannel() : openChannel())}>
      <span className="lamp" aria-hidden />
      Channel
      <span className="chip-count">{n}</span>
    </button>
  )
}

export function Channel() {
  const open = channel.use((s) => s.open)
  const { mounted, attach } = usePresence(open, { y: -12, opacity: 0 })
  useEffect(() => {
    if (!open) return
    const esc = (e: KeyboardEvent) => { if (e.key === 'Escape' && !(e.target instanceof HTMLTextAreaElement)) closeChannel() }
    addEventListener('keydown', esc)
    return () => removeEventListener('keydown', esc)
  }, [open])
  return mounted ? <div className="watchlist-wrap" data-zone ref={attach}><ChannelPanel /></div> : null
}
