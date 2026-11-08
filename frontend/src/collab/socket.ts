import { collabLink } from '../data/live'
import { adapter } from '../data/index'
import { devUser } from './client'
import type { Doc, Entry, Member, Session } from './client'
import { collab } from './store'

// Collaboration messages over the one existing /ws (data/live.ts hands them over; there is no second socket).

export interface PresenceUser {
  id: string; name: string | null; picture: string | null
  viewing: number | null; following: number[]; bbox: [number, number, number, number] | null; ts: number
}

export type CollabMsg =
  | { type: 'session_joined'; session_id: string; role: 'owner' | 'member'; user_id: string; session: Session }
  | { type: 'presence'; session_id: string; users: PresenceUser[] }
  | { type: 'list_delta'; session_id: string; op: 'put'; entry: Entry }
  | { type: 'list_delta'; session_id: string; op: 'remove'; entry: { mmsi: number; updated_by: string; updated_at: number } }
  | { type: 'document'; session_id: string; document: Doc }
  | { type: 'member_joined'; session_id: string; member: Member }
  | { type: 'invite'; invite_id: string; session_id: string }   // someone invited you: re-read GET /invites
  | { type: 'invites_changed' }                                  // one of your invites changed: re-read GET /invites
  | { type: 'error'; code: 'forbidden' | 'bad_request' | 'unavailable'; for?: string; session_id?: string }

export interface PresenceOut {
  viewing: number | null; following: number[]; bbox: [number, number, number, number] | null; private: boolean
}

let joined: string | null = null

function send(msg: object) { adapter?.send(msg as never) }

/** Local dev only: tell the server who this socket is, so invite pushes reach it before any session is joined. */
export function identifyDev() { if (devUser) send({ type: 'auth', dev_user: devUser }) }

export function joinSocket(sessionId: string) {
  joined = sessionId
  send({ type: 'session_join', session_id: sessionId, ...(devUser ? { dev_user: devUser } : {}) })
}
export function leaveSocket() { joined = null; send({ type: 'session_leave' }) }
let lastOut: PresenceOut | null = null
/** The presence agent calls this (throttled ~2 s, heartbeat under 10 s). */
export function sendPresence(p: PresenceOut) { lastOut = p; if (joined) send({ type: 'presence', ...p }) }
/** The server only lists a socket after its first presence, so a (re)join says it at once instead of on the next heartbeat. */
export function resendPresence() { if (lastOut) sendPresence(lastOut) }
/** The server's collaboration store is not ready yet (a restart): ask again rather than drop the session. */
export function rejoinSoon() { setTimeout(() => { if (joined) joinSocket(joined) }, 2000) }

export function bindSocket(): () => void {
  collabLink.onOpen = () => { identifyDev(); void collab.refreshInvites(); if (joined) joinSocket(joined) }    // after a reconnect, re-join (the server forgot us)
  collabLink.onMessage = (m) => collab.applyMessage(m as CollabMsg)
  return () => { collabLink.onOpen = null; collabLink.onMessage = null; joined = null }
}
