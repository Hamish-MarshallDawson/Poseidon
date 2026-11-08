import { expect, test, vi } from 'vitest'
import { collab } from '../store'
import { entry, explain, rememberedSession, tokenFrom } from './state'
import type { OutgoingInvite } from '../client'

test('a pasted invite link or bare token gives the token; anything else gives nothing', () => {
  expect(tokenFrom(' https://site.example/?invite=abc123 ')).toBe('abc123')
  expect(tokenFrom('abc123')).toBe('abc123')
  expect(tokenFrom('https://site.example/?x=1')).toBeNull()
  expect(tokenFrom('   ')).toBeNull()
})

test('the session a tab is in is remembered for a reload, and leaving forgets it; being in one ends the pop-up', () => {
  const head = { id: 's9', title: 'T', created_by: 'u', created_at: 1, members: [] }
  const kept = new Map<string, string>()
  vi.stubGlobal('sessionStorage', { getItem: (k: string) => kept.get(k) ?? null, setItem: (k: string, v: string) => void kept.set(k, v), removeItem: (k: string) => void kept.delete(k) })
  collab.set({ me: { id: 'u', name: 'U', picture: null }, session: null })
  entry.set({ popupDone: false })
  collab.set({ session: head })
  expect(rememberedSession('u')).toBe('s9')
  expect(entry.get().popupDone).toBe(true)
  collab.set({ session: null })
  expect(rememberedSession('u')).toBeNull()
  collab.set({ me: null })
  vi.unstubAllGlobals()
})

test('a declined invite tells the owner once; first load and other changes say nothing', () => {
  const o: OutgoingInvite = { id: 'i', session_id: 's', session_title: 'Kattegat', to: { email: 'c@x.io' }, created_at: 1, expires_at: 2, status: 'pending' }
  entry.set({ notice: null })
  collab.set({ invites: { incoming: [], outgoing: [o] } })
  expect(entry.get().notice).toBeNull()
  collab.set({ invites: { incoming: [], outgoing: [{ ...o, status: 'declined' }] } })
  expect(entry.get().notice?.text).toBe('c@x.io declined your invite to Kattegat.')
  entry.set({ notice: null })
  collab.set({ invites: { incoming: [], outgoing: [{ ...o, status: 'declined' }] } })
  expect(entry.get().notice).toBeNull()
  collab.set({ invites: { incoming: [], outgoing: [] } })
})

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
