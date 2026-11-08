import { useEffect, useRef, useState } from 'react'
import { ui } from '../../store/ui'
import { Avatar } from '../Avatar'
import { api } from '../client'
import type { IncomingInvite, OutgoingInvite } from '../client'
import { acceptInviteId, collab, createSession, declineInvite, leaveSession, openSession, refreshInvites, revokeInvite } from '../store'
import { entry, linkFor, openPanel, saveLink, savedLinks, showJoined } from './state'
import './entry.css'

// The session bar sits in the toolbar: the session title with members' faces (a switcher), Invite / Join with a red
// pulsing badge when invites wait for you, and your own avatar (profile menu: private mode, log out).
// Everything here renders only after login, because the app mounts it inside the logged-in Monitor.

/** Close a menu on Escape or a click outside it. */
function useDismiss(open: boolean, close: () => void) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    if (!open) return
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') close() }
    const down = (e: PointerEvent) => { if (!ref.current?.contains(e.target as Node)) close() }
    window.addEventListener('keydown', key); window.addEventListener('pointerdown', down)
    return () => { window.removeEventListener('keydown', key); window.removeEventListener('pointerdown', down) }
  }, [open, close])
  return ref
}

export function SessionBar({ onLogout }: { onLogout?: () => void }) {
  const me = collab.use((s) => s.me)
  const incoming = collab.use((s) => s.invites.incoming.length)
  const panel = entry.use((s) => s.panel)
  if (!me) return null
  return (
    <div className="session-bar">
      <SessionSwitcher />
      <button type="button" className={`chip invite-btn ${panel ? 'on' : ''}`} aria-expanded={panel} aria-controls="invite-panel"
        aria-label={incoming ? `Invite / Join, ${incoming} waiting` : 'Invite / Join'} onClick={() => { openPanel(!panel); void refreshInvites() }}>
        Invite / Join
        {incoming > 0 && <span className="invite-badge" aria-hidden>{incoming}</span>}
      </button>
      <ProfileMenu onLogout={onLogout} />
    </div>
  )
}

function SessionSwitcher() {
  const session = collab.use((s) => s.session)
  const sessions = collab.use((s) => s.sessions)
  const me = collab.use((s) => s.me)
  const open = entry.use((s) => s.menu === 'switch')
  const [title, setTitle] = useState('')
  const close = () => entry.set({ menu: null })
  const ref = useDismiss(open, close)
  const online = collab.use((s) => s.presence)
  const faces = session ? session.members.slice(0, 4) : []
  const go = async (id: string) => { close(); const s = await openSession(id); if (s) showJoined(s) }
  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return
    close(); setTitle('')
    await createSession(title)
  }
  return (
    <div className="session-bar__wrap" ref={ref}>
      <button type="button" className={`chip session-bar__title ${open ? 'on' : ''}`} aria-haspopup="menu" aria-expanded={open}
        onClick={() => entry.set({ menu: open ? null : 'switch' })}>
        {session ? (
          <>
            <span className="session-bar__faces">{faces.map((m) => <Avatar key={m.id} user={m} size={18} online={online.some((u) => u.id === m.id)} />)}</span>
            <span>{session.title}</span>
          </>
        ) : <span>{sessions.length === 0 ? 'Start a session' : 'Resume session'}</span>}
      </button>
      {open && (
        <div className="entry-menu" role="menu">
          {sessions.map((s) => (
            <button key={s.id} type="button" role="menuitem" onClick={() => go(s.id)} aria-current={s.id === session?.id}>
              <span className="invite-row__text">{s.title}</span><span className="muted">{s.members}</span>
            </button>
          ))}
          {session && <button type="button" role="menuitem" onClick={() => { close(); leaveSession() }}>Just the map</button>}
          {(sessions.length > 0 || session) && <hr />}
          <form onSubmit={create}>
            <input type="text" value={title} maxLength={120} placeholder="New session title" aria-label="New session title" onChange={(e) => setTitle(e.target.value)} />
            <button type="submit" className="chip" disabled={!title.trim() || !me}>Create</button>
          </form>
        </div>
      )}
    </div>
  )
}

function ProfileMenu({ onLogout }: { onLogout?: () => void }) {
  const me = collab.use((s) => s.me)
  const priv = collab.use((s) => s.private)
  const open = entry.use((s) => s.menu === 'profile')
  const ref = useDismiss(open, () => entry.set({ menu: null }))
  if (!me) return null
  return (
    <div className="session-bar__wrap" ref={ref}>
      <button type="button" className={`chip ${open ? 'on' : ''}`} aria-haspopup="menu" aria-expanded={open} aria-label="Your profile"
        onClick={() => entry.set({ menu: open ? null : 'profile' })}>
        <Avatar user={me} size={18} />
      </button>
      {open && (
        <div className="entry-menu" role="menu">
          <p className="muted" style={{ margin: '4px 8px' }}>{me.name ?? 'You'}</p>
          <label>
            <input type="checkbox" checked={priv} onChange={(e) => collab.set({ private: e.target.checked })} />
            Private mode: hide what I view from others
          </label>
          {onLogout && <button type="button" role="menuitem" onClick={onLogout}>Log out</button>}
        </div>
      )}
    </div>
  )
}

/** The right-column panel: invites waiting for you, invites you sent, and Create invite. Mounted by CollabPanel. */
export function InvitePanel() {
  const session = collab.use((s) => s.session)
  const role = collab.use((s) => s.role)
  const { incoming, outgoing } = collab.use((s) => s.invites)
  const [to, setTo] = useState('')
  const [links, setLinks] = useState(savedLinks)
  const [note, setNote] = useState<string | null>(null)
  const [copied, setCopied] = useState<string | null>(null)

  const accept = async (i: IncomingInvite) => { const s = await acceptInviteId(i.id); if (s) { openPanel(false); showJoined(s) } }
  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!session) return
    try {
      const inv = await api.createInvite(session.id, to.trim() || undefined)
      saveLink(inv.id, inv.token); setLinks(savedLinks()); setTo('')
      setNote(to.trim() ? `Invite sent to ${to.trim()}` : 'Link created. Copy it below.')
      await refreshInvites()
    } catch { setNote('Could not create the invite.') }
  }
  const copy = async (id: string) => {
    try { await navigator.clipboard.writeText(linkFor(links[id])); setCopied(id); window.setTimeout(() => setCopied(null), 1500) } catch { setNote('Copy failed; select the link yourself.') }
  }
  const who = (o: OutgoingInvite) => (o.to === null ? 'Link' : 'email' in o.to ? o.to.email : o.to.name ?? 'Someone')
  const mine = outgoing.filter((o) => !session || o.session_id === session.id)

  return (
    <div className="panel invite-panel" id="invite-panel" role="dialog" aria-label="Invite / Join">
      {incoming.length > 0 && <section aria-label="Incoming invites">
        <h2>Invites for you</h2>
        {incoming.map((i) => (
          <div className="invite-row" key={i.id}>
            <Avatar user={i.from} size={20} />
            <span className="invite-row__text"><b>{i.from.name ?? 'Someone'}</b> invited you to <em>{i.session_title}</em></span>
            <button type="button" className="chip on" onClick={() => accept(i)}>Accept</button>
            <button type="button" className="chip" onClick={() => declineInvite(i.id)}>Decline</button>
          </div>
        ))}
      </section>}
      <section aria-label="Invites you sent">
        {session && <h2>Invite</h2>}   {/* the session's name is in the bar */}
        {session && role === 'owner' && (
          <form className="invite-create" onSubmit={create}>
            <input type="text" value={to} maxLength={254} placeholder="Email, or blank for a link" aria-label="Email to invite" onChange={(e) => setTo(e.target.value)} />
            <button type="submit" className="chip on">Create invite</button>
          </form>
        )}
        {session && role !== 'owner' && <p className="muted">Only the session owner can invite.</p>}
        {!session && <p className="muted">Open or create a session to invite people.</p>}
        {note && <p className="muted" role="status">{note}</p>}
        {mine.map((o) => (
          <div className="invite-row" key={o.id}>
            <span className="invite-row__text">{who(o)} · {o.status}</span>
            {links[o.id] && <button type="button" className="chip" onClick={() => copy(o.id)}>{copied === o.id ? 'Copied' : 'Copy link'}</button>}
            <button type="button" className="chip" onClick={() => revokeInvite(o.id)}>Revoke</button>
          </div>
        ))}
      </section>
    </div>
  )
}

/** Mounted next to the Layers panel wrapper so it takes the same right-column slot. */
export function InvitePanelSlot() {
  const open = entry.use((s) => s.panel)
  const layers = ui.use((s) => s.layersOpen)
  useEffect(() => {
    if (!open) return
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') openPanel(false) }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [open])
  if (!open || layers) return null
  return <div className="layers-wrap" data-zone><InvitePanel /></div>
}
