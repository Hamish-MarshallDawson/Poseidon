import { createStore } from '../../store/store'
import { ui } from '../../store/ui'
import type { Session } from '../client'
import { collab } from '../store'

// Entry UI state: which menu or panel is open, the one-shot joined toast, and the invite links this browser created
// (the server keeps only a link's hash, so "Copy link" works for links made here).

export const entry = createStore<{ panel: boolean; menu: 'switch' | 'profile' | null; toast: string[] | null; popupDone: boolean }>({
  panel: false, menu: null, toast: null, popupDone: false,
})

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
  entry.set({ toast: [sess.title, others.length > 1 ? `${others.slice(0, -1).join(', ')} and ${others[others.length - 1]}` : others[0] ?? ''] })
  toastTimer = window.setTimeout(() => entry.set({ toast: null }), 3000)
}

const KEY = 'dvm.invite-links'
export function savedLinks(): Record<string, string> {
  try { return JSON.parse(localStorage.getItem(KEY) || '{}') } catch { return {} }
}
export function saveLink(id: string, token: string) {
  try { localStorage.setItem(KEY, JSON.stringify({ ...savedLinks(), [id]: token })) } catch { /* private window: no copy later */ }
}
export const linkFor = (token: string) => `${location.origin}/?invite=${token}`
