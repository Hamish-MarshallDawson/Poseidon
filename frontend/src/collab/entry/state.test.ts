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

test('when /me fails the bar keeps a quiet reconnecting state and retries', async () => {
  const { vi } = await import('vitest')
  const { loadMe } = await import('../store')
  vi.useFakeTimers()
  let up = false
  vi.stubGlobal('fetch', vi.fn(async (u: string) => {
    if (!up) throw new TypeError('down')
    const body = u.endsWith('/me') ? { user: { id: 'u', name: 'U', picture: null }, last_session: null } : u.endsWith('/sessions') ? { sessions: [] } : { incoming: [], outgoing: [] }
    return new Response(JSON.stringify(body), { status: 200 })
  }))
  collab.set({ me: null, reconnecting: false })
  await loadMe()
  expect(collab.get().reconnecting).toBe(true)
  up = true
  await vi.advanceTimersByTimeAsync(2100)
  expect(collab.get().me?.id).toBe('u')
  expect(collab.get().reconnecting).toBe(false)
  vi.useRealTimers(); vi.unstubAllGlobals()
})
