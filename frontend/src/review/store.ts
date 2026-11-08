import { createStore } from '../store/store'
import { collab, inSession, listAdd, listRemove } from '../collab/presence/core'

// The viewer's review list: MMSIs in the order they were added, kept in localStorage (per browser, never sent anywhere).
// Storage can throw (private window, blocked site data), so every access is wrapped and the list then lives in memory only.
const KEY = 'poseidon.review'
const DISMISSED = 'poseidon.review.dismissed'   // System entries this viewer dismissed (per browser)

function load(key = KEY): number[] {
  try {
    const a: unknown = JSON.parse(localStorage.getItem(key) ?? '[]')
    return Array.isArray(a) ? [...new Set(a.filter((m): m is number => Number.isInteger(m) && m > 0))] : []
  } catch { return [] }
}

export const review = createStore<{ list: number[]; dismissed: number[] }>({ list: load(), dismissed: load(DISMISSED) })
review.subscribe((s) => {
  try { localStorage.setItem(KEY, JSON.stringify(s.list)); localStorage.setItem(DISMISSED, JSON.stringify(s.dismissed)) } catch { /* memory only */ }
})

// In a session the review list is the session's shared list (collab/presence); otherwise it is this browser's own.
export const toggleReview = (mmsi: number) => inSession()
  ? void (collab.get().list.some((e) => e.mmsi === mmsi) ? removeReview(mmsi) : listAdd(mmsi))
  : review.get().list.includes(mmsi) ? removeReview(mmsi) : review.set((s) => ({ list: [...s.list, mmsi] }))
// Also dismissed: a removed ship the forecast flags would otherwise come straight back as a System entry.
export function removeReview(mmsi: number) {
  dismissSystem(mmsi)
  if (inSession()) void listRemove(mmsi)
  else review.set((s) => ({ list: s.list.filter((m) => m !== mmsi) }))
}
export const clearReview = () => review.set((s) => ({ list: [], dismissed: [...new Set([...s.dismissed, ...s.list])] }))
export const useInReview = (mmsi: number) => {
  const mine = review.use((s) => s.list.includes(mmsi))
  const shared = collab.use((s) => s.session != null && s.list.some((e) => e.mmsi === mmsi))
  return collab.use((s) => s.session != null) ? shared : mine
}
export const dismissSystem = (mmsi: number) => review.set((s) => ({ dismissed: s.dismissed.includes(mmsi) ? s.dismissed : [...s.dismissed, mmsi] }))
export const restoreSystem = () => review.set({ dismissed: [] })
