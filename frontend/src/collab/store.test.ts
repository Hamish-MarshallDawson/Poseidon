import { expect, test } from 'vitest'
import { collab } from './store'
import type { Entry, Session } from './client'

const entry = (mmsi: number, status: Entry['status'], at: number): Entry => ({ mmsi, status, added_by: 'u1', added_at: at, updated_by: 'u1', updated_at: at })
const member = { id: 'u1', name: 'A', picture: null, role: 'owner' as const, joined_at: 1, last_active_at: 1 }
const session: Session = { id: 's1', title: 'T', created_by: 'u1', created_at: 1, members: [member], list: [entry(111111111, 'open', 1)], documents: [] }

test('a late session_joined for a session already left is ignored', () => {
  collab.set({ session: null })
  collab.applyMessage({ type: 'session_joined', session_id: 's1', role: 'owner', user_id: 'u1', session })
  expect(collab.get().session).toBeNull()
})

test('a join the server refuses leaves the session cleanly; a server still starting does not', () => {
  const { list: _l, documents: _d, ...head } = session
  collab.set({ session: head, role: 'owner', list: session.list })
  collab.applyMessage({ type: 'error', code: 'unavailable', for: 'session_join' })
  expect(collab.get().session?.id).toBe('s1')
  collab.applyMessage({ type: 'error', code: 'forbidden', for: 'session_join', session_id: 'other' })
  expect(collab.get().session?.id).toBe('s1')
  collab.applyMessage({ type: 'error', code: 'forbidden', for: 'session_join', session_id: 's1' })
  expect(collab.get()).toMatchObject({ session: null, role: null, list: [], error: 'Could not join the session' })
  collab.set({ error: null })
})

test('session_joined adopts the session; deltas and documents apply idempotently', () => {
  const { list: _l, documents: _d, ...head } = session
  collab.set({ session: head })
  collab.applyMessage({ type: 'session_joined', session_id: 's1', role: 'owner', user_id: 'u1', session })
  expect(collab.get().list).toHaveLength(1)
  const put = { type: 'list_delta', session_id: 's1', op: 'put', entry: entry(111111111, 'reviewed', 2) } as const
  collab.applyMessage(put); collab.applyMessage(put)
  expect(collab.get().list.map((e) => e.status)).toEqual(['reviewed'])
  const doc = { type: 'document', session_id: 's1', document: { id: 5, mmsi: null, author_id: 'u1', body: 'x', created_at: 3, kind: 'note', mmsis: [] as number[] } } as const
  collab.applyMessage(doc); collab.applyMessage(doc)
  expect(collab.get().documents).toHaveLength(1)
  collab.applyMessage({ type: 'list_delta', session_id: 's1', op: 'remove', entry: { mmsi: 111111111, updated_by: 'u1', updated_at: 4 } })
  expect(collab.get().list).toHaveLength(0)
})

test('messages for another session are ignored', () => {
  collab.applyMessage({ type: 'presence', session_id: 'other', users: [{ id: 'x', name: null, picture: null, viewing: null, following: [], bbox: null, ts: 1 }] })
  expect(collab.get().presence).toHaveLength(0)
})
