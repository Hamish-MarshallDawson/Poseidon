import { expect, test } from 'vitest'
import { collab } from '../store'
import { entry, explain } from './state'

test('invite and session failures read as plain words; other features stay silent', () => {
  expect(explain('POST /invites/abc/accept: 404')).toMatch(/expired, been used/)
  expect(explain('GET /sessions/abc: 404')).toMatch(/no longer available/)
  expect(explain('POST /sessions: offline')).toMatch(/Cannot reach/)
  expect(explain('POST /sessions/abc/list: 500')).toBeNull()
})

test('a failed call shows its reason once and clears the error', () => {
  collab.set({ error: 'POST /invites/abc/accept: 404' })
  expect(entry.get().notice?.bad).toBe(true)
  expect(collab.get().error).toBeNull()
})
