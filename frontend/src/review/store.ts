import { createStore } from '../store/store'

// The viewer's review list: MMSIs in the order they were added, kept in localStorage (per browser, never sent anywhere).
// Storage can throw (private window, blocked site data), so every access is wrapped and the list then lives in memory only.
const KEY = 'poseidon.review'

function load(): number[] {
  try {
    const a: unknown = JSON.parse(localStorage.getItem(KEY) ?? '[]')
    return Array.isArray(a) ? [...new Set(a.filter((m): m is number => Number.isInteger(m) && m > 0))] : []
  } catch { return [] }
}

export const review = createStore<{ list: number[] }>({ list: load() })
review.subscribe((s) => { try { localStorage.setItem(KEY, JSON.stringify(s.list)) } catch { /* memory only */ } })

export const toggleReview = (mmsi: number) =>
  review.set((s) => ({ list: s.list.includes(mmsi) ? s.list.filter((m) => m !== mmsi) : [...s.list, mmsi] }))
export const removeReview = (mmsi: number) => review.set((s) => ({ list: s.list.filter((m) => m !== mmsi) }))
export const clearReview = () => review.set({ list: [] })
export const useInReview = (mmsi: number) => review.use((s) => s.list.includes(mmsi))
