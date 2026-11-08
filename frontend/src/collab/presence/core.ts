import { api } from '../client'
import type { Entry, Status } from '../client'
import { collab, refreshActivity, type CollabState } from '../store'
import { sendPresence } from '../socket'

// The presence UI's one door to the collab core (client.ts, store.ts, socket.ts). Selectors keep the shapes stable.
export { collab, refreshActivity, sendPresence }
export type { Entry, Member } from '../client'
export type { Status }

const NO_MEMBERS: never[] = []
export const selMeId = (s: CollabState) => s.me?.id ?? null
export const selMembers = (s: CollabState) => s.session?.members ?? NO_MEMBERS
export const inSession = () => collab.get().session != null
export const useInSession = () => collab.use((s) => s.session != null)

const sid = () => collab.get().session?.id
async function run(f: (id: string) => Promise<unknown>) {
  const id = sid()
  if (!id) return
  try { await f(id) } catch (e) { collab.set({ error: e instanceof Error ? e.message : String(e) }) }
}
// The list changes arrive back as list_delta over the socket (applied idempotently by the store), so nothing to set here.
export const listAdd = (mmsi: number) => run((id) => api.listAdd(id, mmsi))
export const listSetStatus = (mmsi: number, status: Status) => run((id) => api.listSet(id, mmsi, status))
// Applied here as well as by the echo: with the socket down the row would otherwise stay on the list.
export const listRemove = (mmsi: number) => run(async (id) => {
  await api.listRemove(id, mmsi)
  collab.set((s) => ({ list: s.list.filter((e) => e.mmsi !== mmsi) }))
})
export type { Entry as ListEntry }
