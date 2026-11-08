import { createStore } from '../store/store'
import { api } from './client'
import type { ActivityRow, Doc, Entry, IncomingInvite, LastSession, Member, OutgoingInvite, Session, SessionRow, User } from './client'
import { joinSocket, leaveSocket } from './socket'
import type { CollabMsg, PresenceUser } from './socket'

// Collaboration state: me, the current session (members, list, documents), presence, activity. UI state only; ship
// positions never come through here. Server messages are applied idempotently (by mmsi and by document id).

export interface CollabState {
  me: User | null
  lastSession: LastSession | null
  sessions: SessionRow[]
  session: Omit<Session, 'list' | 'documents'> | null   // null = just the map
  role: 'owner' | 'member' | null
  list: Entry[]
  documents: Doc[]
  presence: PresenceUser[]
  activity: ActivityRow[]
  invites: { incoming: IncomingInvite[]; outgoing: OutgoingInvite[] }
  private: boolean                                      // hide me from the others (the profile menu)
  error: string | null
  reconnecting: boolean                                  // /me failed: the session bar shows a quiet "Reconnecting…" and retries
}

export const collab = {
  ...createStore<CollabState>({
    me: null, lastSession: null, sessions: [], session: null, role: null, list: [], documents: [], presence: [],
    activity: [], invites: { incoming: [], outgoing: [] }, private: false, error: null, reconnecting: false,
  }),
  applyMessage,
  refreshInvites,
}

const s = () => collab.get()
const fail = (e: unknown) => collab.set({ error: e instanceof Error ? e.message : String(e) })

function adopt(sess: Session, role: 'owner' | 'member' | null = null) {
  const { list, documents, ...head } = sess
  const me = s().me?.id
  collab.set({ session: head, list, documents, role: role ?? head.members.find((m) => m.id === me)?.role ?? 'member', presence: [], activity: [] })
}

let retry: ReturnType<typeof setTimeout> | undefined
/** After login: send the Auth0 profile, then read me and the last session. A failure retries with backoff (2 s up to 30 s). */
export async function loadMe(profile?: { name?: string | null; picture?: string | null; email?: string | null }, wait = 2000): Promise<void> {
  clearTimeout(retry)
  try {
    if (profile && (profile.name || profile.picture)) {
      await api.setMe({ name: profile.name?.slice(0, 80) ?? undefined, picture: profile.picture?.startsWith('https://') ? profile.picture : undefined, email: profile.email ?? undefined })
    }
    const { user, last_session } = await api.me()
    collab.set({ me: user, lastSession: last_session, error: null, reconnecting: false })
    await Promise.all([refreshSessions(), refreshInvites()])
  } catch (e) {
    if (!s().me) { collab.set({ reconnecting: true }); retry = setTimeout(() => void loadMe(profile, Math.min(wait * 2, 30000)), wait) }
    else fail(e)
  }
}

export async function refreshSessions(): Promise<void> {
  try { collab.set({ sessions: (await api.sessions()).sessions }) } catch (e) { fail(e) }
}

/** Enter a session: fetch it, tell the socket. Resolves to the session or null if it can't be opened. */
export async function openSession(id: string): Promise<Session | null> {
  try {
    const sess = await api.session(id)
    adopt(sess)
    joinSocket(id)
    void refreshActivity()
    return sess
  } catch (e) { fail(e); return null }
}

export async function createSession(title: string): Promise<Session | null> {
  try {
    const sess = await api.createSession(title.trim())
    adopt(sess, 'owner')
    joinSocket(sess.id)
    void refreshSessions()
    return sess
  } catch (e) { fail(e); return null }
}

/** Accept a link invite and enter the session. */
export async function acceptInviteToken(token: string): Promise<Session | null> {
  try {
    const sess = await api.acceptInvite(token)
    adopt(sess)
    joinSocket(sess.id)
    void refreshSessions()
    return sess
  } catch (e) { fail(e); return null }
}

export async function refreshInvites(): Promise<void> {
  try { collab.set({ invites: await api.invites() }) } catch { /* keep the last list; the badge just stays as it was */ }
}

/** Accept an invite addressed to me and enter the session. */
export async function acceptInviteId(id: string): Promise<Session | null> {
  try {
    const sess = await api.acceptInviteId(id)
    adopt(sess)
    joinSocket(sess.id)
    void refreshSessions(); void refreshInvites()
    return sess
  } catch (e) { fail(e); void refreshInvites(); return null }
}
export async function declineInvite(id: string) { try { await api.declineInvite(id) } catch (e) { fail(e) } await refreshInvites() }
export async function revokeInvite(id: string) { try { await api.revokeInvite(id) } catch (e) { fail(e) } await refreshInvites() }

export function leaveSession() {
  leaveSocket()
  collab.set({ session: null, role: null, list: [], documents: [], presence: [], activity: [] })
}

export async function refreshActivity() {
  const id = s().session?.id
  if (!id) return
  try { collab.set({ activity: (await api.activity(id)).activity }) } catch (e) { fail(e) }
}

/** Re-read the session (an unknown author or adder means a new member). */
async function refetch(id: string) {
  try {
    const sess = await api.session(id)
    if (s().session?.id === id) collab.set({ session: { id: sess.id, title: sess.title, created_by: sess.created_by, created_at: sess.created_at, members: sess.members } })
  } catch (e) { fail(e) }
}

const known = (id: string) => s().session?.members.some((m) => m.id === id)

function applyMessage(m: CollabMsg) {
  if (m.type === 'error') { if (m.for === 'session_join') collab.set({ error: 'Could not join the session', session: null }); return }
  if (m.type === 'session_joined') { adopt(m.session, m.role); return }
  if (m.type === 'invite' || m.type === 'invites_changed') { void refreshInvites(); return }
  if (m.session_id !== s().session?.id) return           // late message from a session we left
  switch (m.type) {
    case 'presence': collab.set({ presence: m.users }); break
    case 'list_delta':
      if (m.op === 'put') {
        collab.set((p) => ({ list: [...p.list.filter((e) => e.mmsi !== m.entry.mmsi), m.entry].sort((a, b) => a.added_at - b.added_at) }))
        if (!known(m.entry.added_by)) void refetch(m.session_id)
      } else collab.set((p) => ({ list: p.list.filter((e) => e.mmsi !== m.entry.mmsi) }))
      break
    case 'document':
      collab.set((p) => ({ documents: p.documents.some((d) => d.id === m.document.id) ? p.documents : [...p.documents, m.document].sort((a, b) => a.id - b.id) }))
      if (!known(m.document.author_id)) void refetch(m.session_id)
      break
    case 'member_joined':
      collab.set((p) => p.session ? { session: { ...p.session, members: [...p.session.members.filter((x: Member) => x.id !== m.member.id), m.member] } } : {})
      break
  }
}
