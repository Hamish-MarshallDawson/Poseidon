import { useEffect } from 'react'
import { Button } from '../../ui'
import { useNow } from '../../windows/hooks'
import { fmtMmsi } from '../../windows/format'
import { collab, refreshActivity, listSetStatus, selMeId, selMembers, type Entry, type Member } from './core'
import { Avatar } from './Avatar'
import { followUser, presenceUi } from './state'
import { STATUS_LABEL, STATUS_ORDER, activityText, ago, trackedText, viewerText, type Status } from './logic'
import { useHasReport } from './reports'

// Session parts of the one Review list (review/ReviewPanel.tsx): who added each ship, who is viewing it, its status
// (open / reviewed / no action, plus "report generated" once a saved briefing exists), who is online, the activity log.

const who = (members: Member[], id: string) => members.find((m) => m.id === id)

/** Pieces of a Review row that only exist in a session; review/ReviewPanel.tsx lays them out. */
export function ReportTag({ mmsi }: { mmsi: number }) {
  return useHasReport(mmsi) ? <span className="pr-report">{STATUS_LABEL.report}</span> : null
}

export function AddedBy({ e }: { e: Entry }) {
  const by = who(collab.use(selMembers), e.added_by)
  const now = useNow()
  return (
    <span className="pr-added">
      {by && <Avatar id={by.id} name={by.name} picture={by.picture} size={18} />}
      <span>Added {by?.name ? `by ${by.name.split(/\s+/)[0]} ` : ''}{ago(e.added_at, now)}</span>
    </span>
  )
}

export function Viewing({ mmsi }: { mmsi: number }) {
  const presence = collab.use((s) => s.presence)
  const meId = collab.use(selMeId)
  const viewers = presence.filter((u) => u.id !== meId && u.viewing === mmsi)
  return viewers.length > 0 ? <span className="pr-added"><span className="pr-dot" aria-hidden />{viewerText(viewers)}</span> : null
}

export function StatusSelect({ e, name }: { e: Entry; name: string }) {
  return (
    <select className="pr-status" aria-label={`Status of ${name}`} value={e.status} data-status={e.status}
      onChange={(ev) => void listSetStatus(e.mmsi, ev.target.value as Status)}>
      {STATUS_ORDER.map((s) => <option key={s} value={s}>{STATUS_LABEL[s]}</option>)}
    </select>
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

/** Who is online, above the list. */
export const SessionOnline = Online
/** The session's activity log, below the list. */
export const SessionActivity = Activity

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
