import { useEffect, useMemo } from 'react'
import { ui } from '../../store/ui'
import { Button, Kbd } from '../../ui'
import { useNow, useVessel } from '../../windows/hooks'
import { TYPE_LABEL, fmtMmsi, hms } from '../../windows/format'
import { collab, refreshActivity, listRemove, listSetStatus, selMeId, selMembers, type Entry, type Member } from './core'
import { Avatar } from './Avatar'
import { followUser, presenceUi } from './state'
import { STATUS_LABEL, STATUS_ORDER, activityText, ago, trackedText, viewerText, type PresenceUser, type Status } from './logic'
import { useHasReport } from './reports'

// The shared tracking list: replaces the personal Review list while in a session (review/ReviewPanel.tsx switches).
// Reuses the Watchlist panel and row classes. Every row shows who added the ship and when, who is viewing it, and
// its status: open / reviewed / no action, plus "report generated" once a saved briefing exists (docs agent).

const who = (members: Member[], id: string) => members.find((m) => m.id === id)

function Row({ e, members, viewers, onFocus }: { e: Entry; members: Member[]; viewers: PresenceUser[]; onFocus: (mmsi: number) => void }) {
  const v = useVessel(e.mmsi)
  const now = useNow()
  const report = useHasReport(e.mmsi)
  const noAis = !!v && (v.status === 'gap_open' || v.status === 'silent')
  const name = v?.name ?? `MMSI ${fmtMmsi(e.mmsi)}`
  const by = who(members, e.added_by)
  return (
    <li className={`rv-item ${noAis ? 'is-noais' : ''}`} data-mmsi={e.mmsi}>
      <div className="wl-body">
        <span className="wl-head">
          <span className="wl-name"><b>{name}</b>{v && <span>{TYPE_LABEL[v.type_group]}</span>}</span>
          {report && <span className="pr-report">{STATUS_LABEL.report}</span>}
        </span>
        <span className="wl-note">
          MMSI {fmtMmsi(e.mmsi)} · {v ? <>{noAis ? 'No AIS' : 'AIS heard'} · <span className="rv-timer">{hms(now - v.last_ts)}</span> since last AIS</> : 'not in view / no data'}
        </span>
        <span className="pr-added">
          {by && <Avatar id={by.id} name={by.name} picture={by.picture} size={18} />}
          <span>Added {by?.name ? `by ${by.name.split(/\s+/)[0]} ` : ''}{ago(e.added_at, now)}</span>
        </span>
        {viewers.length > 0 && <span className="pr-added"><span className="pr-dot" aria-hidden />{viewerText(viewers)}</span>}
        <span className="rv-actions">
          <select className="pr-status" aria-label={`Status of ${name}`} value={e.status} data-status={e.status}
            onChange={(ev) => void listSetStatus(e.mmsi, ev.target.value as Status)}>
            {STATUS_ORDER.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
          </select>
          <Button className="btn-small" onClick={() => onFocus(e.mmsi)}>Focus on map</Button>
          <Button className="btn-small" aria-label={`Remove ${name} from the shared list`} onClick={() => void listRemove(e.mmsi)}>Remove</Button>
        </span>
      </div>
    </li>
  )
}

function Activity() {
  const activity = collab.use((s) => s.activity)
  const changes = collab.use((s) => s.list)
  // The socket carries no activity rows, so re-read when the panel opens and whenever the list changes.
  useEffect(() => { void refreshActivity() }, [changes])
  const members = collab.use(selMembers)
  const now = useNow()
  if (activity.length === 0) return null
  return (
    <details className="pr-activity">
      <summary>Activity</summary>
      <ul>
        {activity.slice(0, 8).map((a) => {
          const m = who(members, a.actor_id)
          return (
            <li key={a.id}>
              {m && <Avatar id={m.id} name={m.name} picture={m.picture} size={16} ring={false} />}
              <span>{activityText(a.kind, m?.name?.split(/\s+/)[0] ?? 'Someone')}{a.mmsi ? ` (${fmtMmsi(a.mmsi)})` : ''}</span>
              <time>{ago(a.at, now)}</time>
            </li>
          )
        })}
      </ul>
    </details>
  )
}

function Online() {
  const presence = collab.use((s) => s.presence)
  const meId = collab.use(selMeId)
  const target = presenceUi.use((s) => s.followUser)
  const others = presence.filter((p) => p.id !== meId)
  if (others.length === 0) return <p className="wl-meta">Nobody else is online.</p>
  return (
    <ul className="pr-online">
      {others.map((u) => (
        <li key={u.id}>
          <Avatar id={u.id} name={u.name} picture={u.picture} size={20} />
          <span>{u.name?.split(/\s+/)[0] ?? 'Member'}</span>
          <Button className="btn-small" aria-pressed={target === u.id} onClick={() => followUser(target === u.id ? null : u.id)}>
            {target === u.id ? 'Following' : 'Follow view'}
          </Button>
        </li>
      ))}
    </ul>
  )
}

export function SharedPanel({ onCompare, onFocus }: { onCompare: () => void; onFocus: (mmsi: number) => void }) {
  const list = collab.use((s) => s.list)
  const members = collab.use(selMembers)
  const presence = collab.use((s) => s.presence)
  const meId = collab.use(selMeId)
  const byShip = useMemo(() => {
    const m = new Map<number, PresenceUser[]>()
    for (const u of presence) if (u.id !== meId && u.viewing != null) m.set(u.viewing, [...(m.get(u.viewing) ?? []), u])
    return m
  }, [presence, meId])
  return (
    <div className="panel watchlist" id="review-panel" role="region" aria-labelledby="rv-title">
      <div className="wl-header">
        <div className="wl-titlerow">
          <h2 id="rv-title">Shared list</h2>
          <Button className="btn-small" onClick={() => ui.set({ reviewOpen: false })}>Close <Kbd>Esc</Kbd></Button>
        </div>
        <p className="wl-explain">Ships the session is tracking. A flag is a prompt to review, not an accusation.</p>
        <p className="wl-meta">{list.length} {list.length === 1 ? 'ship' : 'ships'} tracked</p>
      </div>
      <Online />
      {list.length === 0 ? (
        <p className="rv-empty">Nothing yet. Open a ship and choose Add to review: everyone in the session sees it.</p>
      ) : (
        <ul className="wl-list rv-list">
          {list.map((e) => <Row key={e.mmsi} e={e} members={members} viewers={byShip.get(e.mmsi) ?? []} onFocus={onFocus} />)}
        </ul>
      )}
      <Activity />
      {list.length > 1 && (
        <div className="wl-brief">
          <span>{list.length} tracked</span>
          <span className="wl-brief-actions">
            <Button className="btn-small" variant="filled" onClick={onCompare}>Compare {list.length} ships</Button>
          </span>
        </div>
      )}
    </div>
  )
}

/** "Aiden and Jake are viewing" and "Tracked by Mano" for a ship window. Nothing when nobody is. */
export function ShipPresence({ mmsi }: { mmsi: number }) {
  const presence = collab.use((s) => s.presence)
  const meId = collab.use(selMeId)
  const entry = collab.use((s) => s.list.find((e) => e.mmsi === mmsi) ?? null)
  const members = collab.use(selMembers)
  const viewers = presence.filter((u) => u.id !== meId && u.viewing === mmsi)
  // Tracking = following it in Follow selected, or having added it to the shared list.
  const trackerIds = new Set(presence.filter((u) => u.id !== meId && u.following.includes(mmsi)).map((u) => u.id))
  if (entry && entry.added_by !== meId) trackerIds.add(entry.added_by)
  const names = [...trackerIds].map((id) => who(members, id)?.name ?? presence.find((u) => u.id === id)?.name ?? null)
  if (viewers.length === 0 && names.length === 0) return null
  return (
    <p className="pr-ship" data-testid="ship-presence">
      {viewers.length > 0 && <span>{viewers.map((u) => <Avatar key={u.id} id={u.id} name={u.name} picture={u.picture} size={16} />)} {viewerText(viewers)}</span>}
      {names.length > 0 && <span>{trackedText(names)}</span>}
    </p>
  )
}
