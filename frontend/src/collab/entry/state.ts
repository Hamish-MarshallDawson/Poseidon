import { createStore } from '../../store/store'
import { ui } from '../../store/ui'
import type { OutgoingInvite, Session } from '../client'
import { collab } from '../store'

// Entry UI state: which menu or panel is open, the one-shot joined toast, and the invite links this browser created
// (the server keeps only a link's hash, so "Copy link" works for links made here).

export const entry = createStore<{
  panel: boolean; menu: 'switch' | 'profile' | null; toast: string[] | null; notice: { text: string; bad: boolean } | null; popupDone: boolean
}>({ panel: false, menu: null, toast: null, notice: null, popupDone: false })

// An invite link survives the Auth0 login redirect (which drops the query string): stash it at load, take it once logged in.
const PENDING = 'dvm.pending-invite'
try {
  const u = new URL(location.href), t = u.searchParams.get('invite')
  if (t) { sessionStorage.setItem(PENDING, t); u.searchParams.delete('invite'); history.replaceState(null, '', u) }
} catch { /* no storage: the link only works when already logged in */ }
export function takeInvite(): string | null {
  try { const t = sessionStorage.getItem(PENDING); sessionStorage.removeItem(PENDING); return t } catch { return null }
}

// The right column holds one panel: opening Layers, Review or the watchlist closes this one.
ui.subscribe((s, p) => {
  if ((s.layersOpen && !p.layersOpen) || (s.reviewOpen && !p.reviewOpen) || (s.watchlistOpen && !p.watchlistOpen)) entry.set({ panel: false })
})
export function openPanel(open: boolean) {
  entry.set({ panel: open, menu: null })
  if (open) ui.set({ layersOpen: false, reviewOpen: false, watchlistOpen: false })
}

let toastTimer: number | undefined
/** "You have joined <title> with A, B and C": once, in the centre, gone after about 3 s. */
export function showJoined(sess: Session) {
  const me = collab.get().me?.id
  const others = sess.members.filter((m) => m.id !== me).map((m) => m.name ?? 'someone')
  window.clearTimeout(toastTimer)
  entry.set({ notice: null, toast: [sess.title, others.length > 1 ? `${others.slice(0, -1).join(', ')} and ${others[others.length - 1]}` : others[0] ?? ''] })
  toastTimer = window.setTimeout(() => entry.set({ toast: null }), 3000)
}

let noticeTimer: ReturnType<typeof setTimeout> | undefined
/** One plain line in the centre, for a result or an error: gone after 3 s (5 s for an error). */
export function say(text: string, bad = false) {
  clearTimeout(noticeTimer)
  entry.set({ notice: { text, bad } })
  noticeTimer = setTimeout(() => entry.set({ notice: null }), bad ? 5000 : 3000)
}

/** The reason an invite or session call failed, in plain words; null for errors that belong to other features. */
export function explain(raw: string): string | null {
  if (/^Could not join/.test(raw)) return 'Could not join that session.'
  const m = /^(\w+) (\/\S*?): (\d+|offline)$/.exec(raw)
  if (!m) return null
  const [, method, path, code] = m
  const mine = /^\/invites/.test(path) || (method === 'POST' && path === '/sessions') || (method === 'GET' && /^\/sessions\/[^/]+$/.test(path))
  if (!mine) return null
  if (code === 'offline') return 'Cannot reach the server. Try again.'
  if (/accept$/.test(path) && code === '404') return 'That invite has expired, been used or been withdrawn.'
  if (code === '404' && method === 'GET') return 'That session is no longer available.'
  return /^\/invites/.test(path) ? 'That invite did not go through. Try again.' : 'Could not start the session. Try again.'
}
// Every failed invite or session call shows its reason once, so nothing fails silently.
collab.subscribe((s, p) => {
  if (!s.error || s.error === p.error) return
  const m = explain(s.error)
  if (m) { collab.set({ error: null }); say(m, true) }
})

/** Who an invite went to, in words. */
export const inviteeName = (o: OutgoingInvite) => (o.to === null ? 'Invite link' : 'email' in o.to ? o.to.email : o.to.name ?? 'Someone')
// A decline must reach the owner even with the panel shut (an accept shows up as a new face).
collab.subscribe((s, p) => {
  if (s.invites === p.invites) return
  for (const o of s.invites.outgoing) {
    if (o.status === 'declined' && p.invites.outgoing.some((x) => x.id === o.id && x.status === 'pending')) say(`${inviteeName(o)} declined your invite to ${o.session_title}.`)
  }
})

// A reload puts you back in the session this tab was in. sessionStorage: per tab, and leaving clears it. Per user, for a shared browser.
const sessionKey = (me: string) => `dvm.session.${me}`
export function rememberedSession(me: string): string | null {
  try { return sessionStorage.getItem(sessionKey(me)) } catch { return null }
}
export function forgetSession(me: string) {
  try { sessionStorage.removeItem(sessionKey(me)) } catch { /* no storage: nothing was remembered */ }
}
collab.subscribe((s, p) => {
  if (s.session?.id === p.session?.id) return
  if (s.session) entry.set({ popupDone: true })          // once you have been in a session this load, leaving must not offer it straight back
  if (!s.me) return
  if (!s.session) forgetSession(s.me.id)
  else try { sessionStorage.setItem(sessionKey(s.me.id), s.session.id) } catch { /* no storage: a reload goes through the pop-up */ }
})

/** A pasted invite link, or a bare token, to the token. */
export function tokenFrom(text: string): string | null {
  const t = text.trim()
  try { return new URL(t).searchParams.get('invite') } catch { return t || null }
}

const KEY = 'dvm.invite-links'
export function savedLinks(): Record<string, string> {
  try { return JSON.parse(localStorage.getItem(KEY) || '{}') } catch { return {} }
}
export function saveLink(id: string, token: string) {
  try { localStorage.setItem(KEY, JSON.stringify({ ...savedLinks(), [id]: token })) } catch { /* private window: no copy later */ }
}
export const linkFor = (token: string) => `${location.origin}/?invite=${token}`
