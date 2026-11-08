import { useEffect, useRef, useState } from 'react'
import { ui } from '../../store/ui'
import { Avatar } from '../Avatar'
import { api, CollabError } from '../client'
import type { IncomingInvite } from '../client'
import { acceptInviteId, acceptInviteToken, collab, createSession, declineInvite, leaveSession, openSession, refreshInvites, refreshSessions, revokeInvite } from '../store'
import { entry, inviteeName, linkFor, openPanel, saveLink, savedLinks, say, showJoined, tokenFrom } from './state'
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
  const reconnecting = collab.use((s) => s.reconnecting)
  const inSession = collab.use((s) => s.session !== null)
  const connected = ui.use((s) => s.feed.connected)
  const dropped = inSession && !connected
  if (!me) return reconnecting ? <span className="chip chip-quiet" role="status">Reconnecting…</span> : null
  return (
    <div className="session-bar">
      {dropped && <span className="chip chip-quiet session-bar__offline" role="status">Reconnecting…</span>}
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

const DEFAULT_TITLE = 'Baltic dark ships'
const MAX_FACES = 4

function SessionSwitcher() {
  const session = collab.use((s) => s.session)
  const sessions = collab.use((s) => s.sessions)
  const me = collab.use((s) => s.me)
  const open = entry.use((s) => s.menu === 'switch')
  const [title, setTitle] = useState(DEFAULT_TITLE)
  const close = () => entry.set({ menu: null })
  const ref = useDismiss(open, close)
  const online = collab.use((s) => s.presence)
  const here = (id: string) => online.some((u) => u.id === id)
  const members = session ? [...session.members].sort((a, b) => Number(here(b.id)) - Number(here(a.id))) : []   // who is here first
  const faces = members.slice(0, MAX_FACES)
  // Keyboard: the menu opens on its first row, or with no sessions yet on the title field (selected).
  useEffect(() => {
    if (!open) return
    void refreshSessions()                             // counts and who is in them change while the menu is shut
    const first = ref.current?.querySelector<HTMLElement>('[role=menuitem], input')
    first?.focus(); if (first instanceof HTMLInputElement) first.select()
  }, [open, ref])
  const go = async (id: string) => { close(); if (id === session?.id) return; const s = await openSession(id); if (s) showJoined(s) }
  const leave = () => { const t = session?.title; close(); leaveSession(); if (t) say(`Left ${t}. Resume it from the session menu.`) }
  const create = async (e: React.FormEvent) => {
    e.preventDefault()
    if (!title.trim()) return
    close(); setTitle(DEFAULT_TITLE)
    if (await createSession(title)) openPanel(true)       // the next step is inviting someone
  }
  const label = session ? session.title : sessions.length ? 'Resume session' : 'Start a session'
  return (
    <div className="session-bar__wrap" ref={ref}>
      <button type="button" className={`chip session-bar__title ${open ? 'on' : ''}`} aria-haspopup="menu" aria-expanded={open}
        onClick={() => entry.set({ menu: open ? null : 'switch' })}>
        {session && (
          <span className="session-bar__faces">
            {faces.map((m) => <Avatar key={m.id} user={m} size={18} online={here(m.id)} />)}
            {members.length > MAX_FACES && <span className="session-bar__more" title={`${members.length} people in this session`}>+{members.length - MAX_FACES}</span>}
          </span>
        )}
        <span>{label}</span>
      </button>
      {open && (
        <div className="entry-menu" role="menu">
          {sessions.map((s) => (
            <button key={s.id} type="button" role="menuitem" onClick={() => go(s.id)} aria-current={s.id === session?.id}>
              <span className="invite-row__text">{s.title}</span>
              {s.online.length > 0 && <span className="session-bar__faces">{s.online.slice(0, 3).map((u) => <Avatar key={u.id} user={u} size={16} online />)}</span>}
              <span className="muted">{s.id === session?.id ? 'open' : s.members > 1 ? `${s.members} people` : 'just you'}</span>
            </button>
          ))}
          {session && <button type="button" role="menuitem" onClick={leave}>Leave session</button>}
          {(sessions.length > 0 || session) && <hr />}
          <form onSubmit={create}>
            <input type="text" value={title} maxLength={120} placeholder="Session title" aria-label="Session title" onChange={(e) => setTitle(e.target.value)} />
            <button type="submit" className="chip on" disabled={!title.trim() || !me}>{sessions.length || session ? 'New' : 'Start'}</button>
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

/** Copy text that is only known after a server call, inside the click's permission (Safari needs the promise form). */
async function copyLater(text: Promise<string>) {
  if (typeof ClipboardItem !== 'undefined' && navigator.clipboard?.write) {
    await navigator.clipboard.write([new ClipboardItem({ 'text/plain': text.then((t) => new Blob([t], { type: 'text/plain' })) })])
  } else await navigator.clipboard.writeText(await text)
}

/** Why an invite call failed, in words. */
function whyNot(e: unknown, to = ''): string {
  const c = e instanceof CollabError ? e.status : -1
  if (c === 403) return 'Only the session owner can invite.'
  if (c === 409) return `${to || 'They'} ${to ? 'is' : 'are'} already in this session.`
  if (c === 422) return 'That is not a valid email address.'
  return c === 0 ? 'Cannot reach the server. Try again.' : 'Could not create the invite. Try again.'
}

/** The right-column panel: invites waiting for you, then (in a session you own) one-click link and email invites. */
export function InvitePanel() {
  const session = collab.use((s) => s.session)
  const role = collab.use((s) => s.role)
  const { incoming, outgoing } = collab.use((s) => s.invites)
  const meId = collab.use((s) => s.me?.id)
  const online = collab.use((s) => s.presence)
  const [to, setTo] = useState('')
  const [paste, setPaste] = useState('')
  const [links, setLinks] = useState(savedLinks)
  const [note, setNote] = useState<{ text: string; bad: boolean } | null>(null)
  const [copied, setCopied] = useState<string | null>(null)
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => { ref.current?.querySelector<HTMLElement>('[data-first]')?.focus() }, [])   // the keyboard lands on the first action

  const flash = (id: string) => { setCopied(id); window.setTimeout(() => setCopied(null), 1500) }
  const accept = async (i: IncomingInvite) => { const s = await acceptInviteId(i.id); if (s) { openPanel(false); showJoined(s) } }
  const make = async (email?: string) => {
    const inv = await api.createInvite(session!.id, email)
    saveLink(inv.id, inv.token); setLinks(savedLinks()); void refreshInvites()
    return inv
  }
  const copyNew = async () => {
    setNote(null)
    try { await copyLater(make().then((i) => linkFor(i.token))); flash('new') } catch (e) { setNote({ text: whyNot(e), bad: true }) }
  }
  const send = async (e: React.FormEvent) => {
    e.preventDefault()
    const addr = to.trim()
    if (!addr) return
    try {
      await make(addr); setTo(''); setNote({ text: `Invited ${addr}. They see it on their Invite / Join badge.`, bad: false })
      window.setTimeout(() => setNote(null), 4000)
    } catch (err) { setNote({ text: whyNot(err, addr), bad: true }) }
  }
  const joinPasted = async (e: React.FormEvent) => {
    e.preventDefault()
    const token = tokenFrom(paste)
    if (!token) { setNote({ text: 'That is not an invite link.', bad: true }); return }
    const s = await acceptInviteToken(token)
    if (s) { setPaste(''); openPanel(false); showJoined(s) }
  }
  const copy = async (id: string) => {
    try { await navigator.clipboard.writeText(linkFor(links[id])); flash(id) } catch { setNote({ text: 'Copy failed. Allow clipboard access.', bad: true }) }
  }
  const owner = session?.members.find((m) => m.role === 'owner')
  // Accepted invites are the member faces already; pending and declined ones need an action.
  const mine = session ? outgoing.filter((o) => o.session_id === session.id && o.status !== 'accepted') : []

  return (
    <div className="panel invite-panel" id="invite-panel" role="dialog" aria-label="Invite / Join" ref={ref}>
      {incoming.length > 0 && (
        <section aria-label="Invites for you">
          <h2>Invites for you</h2>
          {incoming.map((i, n) => (
            <div className="invite-row" key={i.id}>
              <Avatar user={i.from} size={20} />
              <span className="invite-row__text"><b>{i.from.name ?? 'Someone'}</b> invited you to <em>{i.session_title}</em></span>
              <button type="button" className="chip on" onClick={() => accept(i)} data-first={n === 0 ? '' : undefined}>Accept</button>
              <button type="button" className="chip" onClick={() => declineInvite(i.id)}>Decline</button>
            </div>
          ))}
        </section>
      )}
      <section aria-label="Invite people">
        {session && role === 'owner' && (
          <>
            <h2>Invite to <em>{session.title}</em></h2>
            <button type="button" className="chip on invite-copy" onClick={copyNew} data-first={incoming.length ? undefined : ''}>
              {copied === 'new' ? 'Link copied' : 'Copy invite link'}
            </button>
            <p className="muted">Each link works for one person and lasts 7 days.</p>
            <form className="invite-create" onSubmit={send}>
              <input type="email" value={to} maxLength={254} placeholder="or invite by email" aria-label="Invite by email" onChange={(e) => { setTo(e.target.value); setNote(null) }} />
              <button type="submit" className="chip" disabled={!to.trim()}>Send</button>
            </form>
          </>
        )}
        {!session && (
          <>
            {incoming.length === 0 && <p className="muted">Start a session from the session menu to invite people, or join with a link.</p>}
            <form className="invite-create" onSubmit={joinPasted}>
              <input type="text" value={paste} placeholder="Paste an invite link" aria-label="Paste an invite link" data-first={incoming.length ? undefined : ''} onChange={(e) => { setPaste(e.target.value); setNote(null) }} />
              <button type="submit" className="chip" disabled={!paste.trim()}>Join</button>
            </form>
          </>
        )}
        {note && <p className={`muted ${note.bad ? 'bad' : ''}`} role={note.bad ? 'alert' : 'status'}>{note.text}</p>}
        {mine.map((o) => (
          <div className="invite-row" key={o.id}>
            <span className="invite-row__text">{inviteeName(o)} · {o.status === 'declined' ? 'declined' : 'waiting'}</span>
            {o.status === 'pending' && links[o.id] && <button type="button" className="chip" onClick={() => copy(o.id)}>{copied === o.id ? 'Copied' : 'Copy'}</button>}
            <button type="button" className="chip" onClick={() => revokeInvite(o.id)}>{o.status === 'declined' ? 'Remove' : 'Revoke'}</button>
          </div>
        ))}
      </section>
      {session && (
        <section aria-label="In this session">
          <h2>In this session · {session.members.length}</h2>
          {session.members.map((m) => {
            const here = online.some((u) => u.id === m.id)
            return (
              <div className="invite-row member-row" key={m.id}>
                <Avatar user={m} size={20} online={here} />
                <span className="invite-row__text">{m.name ?? 'Someone'}</span>
                <span className="muted">{[m.role === 'owner' && 'Owner', m.id === meId ? 'You' : here ? 'Online' : 'Away'].filter(Boolean).join(' · ')}</span>
              </div>
            )
          })}
          {role !== 'owner' && <p className="muted">{owner?.name ?? 'The session owner'} can invite more people.</p>}
        </section>
      )}
    </div>
  )
}

/** Mounted next to the Layers panel wrapper so it takes the same right-column slot. */
export function InvitePanelSlot() {
  const open = entry.use((s) => s.panel)
  const layers = ui.use((s) => s.layersOpen)
  useEffect(() => {
    if (!open) return
    const key = (e: KeyboardEvent) => { if (e.key === 'Escape') { openPanel(false); document.querySelector<HTMLElement>('.invite-btn')?.focus() } }
    window.addEventListener('keydown', key)
    return () => window.removeEventListener('keydown', key)
  }, [open])
  if (!open || layers) return null
  return <div className="layers-wrap" data-zone><InvitePanel /></div>
}
