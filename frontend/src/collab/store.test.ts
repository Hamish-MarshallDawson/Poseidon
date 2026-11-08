import { expect, test } from 'vitest'
import { collab } from './store'
import type { Entry, Session } from './client'

const entry = (mmsi: number, status: Entry['status'], at: number): Entry => ({ mmsi, status, added_by: 'u1', added_at: at, updated_by: 'u1', updated_at: at })
const member = { id: 'u1', name: 'A', picture: null, role: 'owner' as const, joined_at: 1, last_active_at: 1 }
const session: Session = { id: 's1', title: 'T', created_by: 'u1', created_at: 1, members: [member], list: [entry(111111111, 'open', 1)], documents: [] }

test('session_joined adopts the session; deltas and documents apply idempotently', () => {
  collab.applyMessage({ type: 'session_joined', session_id: 's1', role: 'owner', user_id: 'u1', session })
  expect(collab.get().list).toHaveLength(1)
  const put = { type: 'list_delta', session_id: 's1', op: 'put', entry: entry(111111111, 'reviewed', 2) } as const
  collab.applyMessage(put); collab.applyMessage(put)
  expect(collab.get().list.map((e) => e.status)).toEqual(['reviewed'])
  const doc = { type: 'document', session_id: 's1', document: { id: 5, mmsi: null, author_id: 'u1', body: 'x', created_at: 3 } } as const
  collab.applyMessage(doc); collab.applyMessage(doc)
  expect(collab.get().documents).toHaveLength(1)
  collab.applyMessage({ type: 'list_delta', session_id: 's1', op: 'remove', entry: { mmsi: 111111111, updated_by: 'u1', updated_at: 4 } })
  expect(collab.get().list).toHaveLength(0)
})

test('messages for another session are ignored', () => {
  collab.applyMessage({ type: 'presence', session_id: 'other', users: [{ id: 'x', name: null, picture: null, viewing: null, following: [], bbox: null, ts: 1 }] })
  expect(collab.get().presence).toHaveLength(0)
})
