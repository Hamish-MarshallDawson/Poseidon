import { expect, test } from 'vitest'
import { collab } from '../collab/store'
import { review } from '../review/store'
import { vessels } from '../store/vessels'
import { originOf } from './store'

test('origin: shared entry is by its adder, own list is you, watchlist is system, else selected', () => {
  collab.set({ me: { id: 'u1', name: 'Me', picture: null }, session: { id: 's', title: 'T', created_by: 'u1', created_at: 1,
    members: [{ id: 'u2', name: 'Aiden', picture: null, role: 'member', joined_at: 1, last_active_at: 1 }] },
    list: [{ mmsi: 1, status: 'open', added_by: 'u2', added_at: 1, updated_by: 'u2', updated_at: 1 }, { mmsi: 2, status: 'open', added_by: 'u1', added_at: 1, updated_by: 'u1', updated_at: 1 }] })
  expect(originOf(1)).toEqual({ kind: 'user', added_by: 'Aiden' })
  expect(originOf(2)).toEqual({ kind: 'user', added_by: 'you' })
  vessels.watchlist = { snapshot_ts: 1, entries: [{ rank: 1, mmsi: 3, name: null, p: 0.4, decision: 'watch', prev_rank: null, reason_codes: ['gap'], evidence: [] }] }
  expect(originOf(3)).toEqual({ kind: 'system', reasons: ['gap'], risk_p: 0.4 })
  expect(originOf(4)).toEqual({ kind: 'selected' })
  collab.set({ session: null, list: [] }); review.set({ list: [5] })
  expect(originOf(5)).toEqual({ kind: 'user', added_by: 'you' })
})
