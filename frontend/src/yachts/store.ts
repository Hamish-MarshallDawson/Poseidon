import { createStore } from '../store/store'

// Sanctioned and notable yachts (#101): GET /yachts, matched by IMO on the server. Loaded on first need and every
// minute while the layer is on. Owners are only ever shown as "reported" with the source link.

export interface Yacht {
  imo: number
  name: string | null
  length_m: number | null
  owner_reported: string | null
  owner_source_url: string | null
  sanctioned: boolean
  programs: string[]
  sanctions_source: string | null
  mmsi: number | null
  last_seen_ts: number | null
  status: 'ais' | 'no_ais' | 'not_seen'
}

interface YachtsState {
  on: boolean                       // the Layers toggle; off by default
  list: Yacht[] | null
  byMmsi: Map<number, Yacht>
  error: string | null
}

export const yachts = createStore<YachtsState>({ on: false, list: null, byMmsi: new Map(), error: null })

let getToken: () => Promise<string | undefined> = async () => undefined
export function bindYachtsAuth(fn: (() => Promise<string | undefined>) | null) { getToken = fn ?? (async () => undefined) }

const base = () => import.meta.env.VITE_API_URL || 'http://localhost:8000'
const TTL_MS = 60_000
let loadedAt = 0
let inflight: Promise<void> | null = null
let timer: number | undefined

export function loadYachts(): Promise<void> {
  if (inflight) return inflight
  if (Date.now() - loadedAt < TTL_MS && yachts.get().list) return Promise.resolve()
  inflight = (async () => {
    try {
      const token = await getToken()
      const res = await fetch(`${base()}/yachts`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      if (!res.ok) throw new Error(res.status === 503 ? 'The yacht list is still loading on the server.' : `GET /yachts: ${res.status}`)
      const list = (await res.json()) as Yacht[]
      const byMmsi = new Map<number, Yacht>()
      for (const y of list) if (y.mmsi != null) byMmsi.set(y.mmsi, y)
      loadedAt = Date.now()
      yachts.set({ list, byMmsi, error: null })
    } catch (e) {
      yachts.set({ error: e instanceof Error ? e.message : 'The yacht list could not be loaded.' })
    } finally {
      inflight = null
    }
  })()
  return inflight
}

export function setYachtsLayer(on: boolean): void {
  yachts.set({ on })
  window.clearInterval(timer)
  if (on) {
    void loadYachts()
    timer = window.setInterval(() => void loadYachts(), TTL_MS)
  }
}

// The map badge for a ship while the layer is on: the sanctions-match badge, or the quieter notable badge.
export function yachtBadge(mmsi: number): 'sanctioned' | 'notable' | null {
  const s = yachts.get()
  if (!s.on) return null
  const y = s.byMmsi.get(mmsi)
  return y ? (y.sanctioned ? 'sanctioned' : 'notable') : null
}

// "3 d", "5 h", "12 min": how long a yacht has been silent.
export function ago(ms: number): string {
  const m = Math.max(0, Math.floor(ms / 60_000))
  if (m < 60) return `${m} min`
  if (m < 48 * 60) return `${Math.floor(m / 60)} h`
  return `${Math.floor(m / 1440)} d`
}

// Heard ships after silent ones; among silent ones, the longest silence first; not seen ones are left out.
export function listOrder(list: Yacht[]): Yacht[] {
  const rank = { no_ais: 0, ais: 1, not_seen: 2 } as const
  return list.filter((y) => y.status !== 'not_seen')
    .sort((a, b) => rank[a.status] - rank[b.status] || (a.last_seen_ts ?? 0) - (b.last_seen_ts ?? 0))
}
