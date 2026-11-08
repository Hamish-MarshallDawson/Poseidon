import { createStore } from '../../store/store'
import type { PresenceOut, PresenceUser, Status } from './logic'

// TEMPORARY STUB of the entry agent's core (collab/store.ts, client.ts, socket.ts). This file is the only place the
// presence UI touches the core; when that PR merges, replace the body with re-exports and delete the stub state.

export interface Member { id: string; name: string | null; picture: string | null; role: 'owner' | 'member' }
export interface Entry { mmsi: number; status: Status; added_by: string; added_at: number; updated_by: string; updated_at: number }
export interface Activity { id: number; actor_id: string; kind: string; mmsi: number | null; at: number }

export interface CollabState {
  meId: string | null
  sessionId: string | null
  members: Member[]
  presence: PresenceUser[]
  list: Entry[]
  activity: Activity[]
}

export const collab = createStore<CollabState>({ meId: null, sessionId: null, members: [], presence: [], list: [], activity: [] })

export const inSession = () => collab.get().sessionId != null
export const useInSession = () => collab.use((s) => s.sessionId != null)

export function sendPresence(_p: PresenceOut): void { /* stub */ }
export async function listAdd(_mmsi: number): Promise<void> { /* stub */ }
export async function listSetStatus(_mmsi: number, _status: Status): Promise<void> { /* stub */ }
export async function listRemove(_mmsi: number): Promise<void> { /* stub */ }
