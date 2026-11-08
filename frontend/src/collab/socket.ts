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
  | { type: 'invite'; invite: unknown }                       // pushed when someone invites you (entry agent, PR 2)
  | { type: 'error'; code: 'forbidden' | 'bad_request' | 'unavailable'; for?: string; session_id?: string }

export interface PresenceOut {
  viewing: number | null; following: number[]; bbox: [number, number, number, number] | null; private: boolean
}

let joined: string | null = null

function send(msg: object) { adapter?.send(msg as never) }

export function joinSocket(sessionId: string) {
  joined = sessionId
  send({ type: 'session_join', session_id: sessionId, ...(devUser ? { dev_user: devUser } : {}) })
}
export function leaveSocket() { joined = null; send({ type: 'session_leave' }) }
/** The presence agent calls this (throttled ~2 s, heartbeat under 10 s). */
export function sendPresence(p: PresenceOut) { if (joined) send({ type: 'presence', ...p }) }

export function bindSocket(): () => void {
  collabLink.onOpen = () => { if (joined) joinSocket(joined) }    // after a reconnect, re-join (the server forgot us)
  collabLink.onMessage = (m) => collab.applyMessage(m as CollabMsg)
  return () => { collabLink.onOpen = null; collabLink.onMessage = null; joined = null }
}
