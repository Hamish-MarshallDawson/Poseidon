import { createStore } from '../store/store'
import { vessels } from '../store/vessels'

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
  sample: boolean                   // the list is the offline illustrative sample, not server data
}

export const yachts = createStore<YachtsState>({ on: false, list: null, byMmsi: new Map(), error: null, sample: false })

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
      if (import.meta.env.VITE_DATA === 'offline') { if (!applySample()) window.setTimeout(() => void loadYachts(), 1500); return }
      const token = await getToken()
      const res = await fetch(`${base()}/yachts`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      if (!res.ok) throw new Error(res.status === 503 ? 'The yacht list is still loading on the server.' : `GET /yachts: ${res.status}`)
      const list = (await res.json()) as Yacht[]
      const byMmsi = new Map<number, Yacht>()
      for (const y of list) if (y.mmsi != null) byMmsi.set(y.mmsi, y)
      loadedAt = Date.now()
      yachts.set({ list, byMmsi, error: null, sample: false })
    } catch (e) {
      if (import.meta.env.VITE_DATA !== 'live' && applySample()) return
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

// Offline sample (no backend): about 12 made-up yachts. Heard and quiet ones borrow real synthetic MMSIs so the list can
// be clicked through; until ships arrive it returns false and the next load tries again.
function applySample(): boolean {
  const all = [...vessels.vessels.values()]
  const moving = all.filter((v) => v.status === 'active' && (v.sog_kn ?? 0) > 3)
  const gaps = all.filter((v) => v.status === 'gap_open')
  const quiet = [...gaps, ...all.filter((v) => v.status !== 'active' && v.status !== 'gap_open')]
  if (moving.length < 5 || quiet.length < 1) return false
  const now = Date.now()
  const mk = (i: number, name: string, status: Yacht['status'], mmsi: number | null, sanctioned: boolean, silentH = 0): Yacht => ({
    imo: 9900000 + i, name, length_m: 60 + i * 9, sanctioned, mmsi, status,
    owner_reported: i % 2 ? `Sample Holdings ${i} Ltd` : null,
    owner_source_url: i % 2 ? 'https://en.wikipedia.org/wiki/Superyacht' : null,
    programs: sanctioned ? ['EU-UKR (sample)'] : [],
    sanctions_source: sanctioned ? 'https://www.opensanctions.org/' : null,
    last_seen_ts: status === 'ais' ? now : status === 'no_ais' ? now - silentH * 3600_000 : null,
  })
  const list = [
    ...moving.slice(0, 5).map((v, i) => mk(i, `Sample Heard ${i + 1}`, 'ais', v.mmsi, i < 2)),
    ...[0, 1, 2].map((i) => mk(5 + i, `Sample Quiet ${i + 1}`, 'no_ais', quiet[i % quiet.length].mmsi, i === 0, 5 + i * 20)),
    ...[0, 1, 2, 3].map((i) => mk(8 + i, `Sample Unseen ${i + 1}`, 'not_seen', null, i < 2)),
  ]
  const byMmsi = new Map<number, Yacht>()
  for (const y of list) if (y.mmsi != null) byMmsi.set(y.mmsi, y)
  yachts.set({ list, byMmsi, error: null, sample: true })
  return true
}
