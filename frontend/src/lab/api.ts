import { ui } from '../store/ui'
import raw from './fixtures.json'
import type { Fixtures, LabData, LabEvent, Metrics, Proposal, Run, RunDetail, Summary } from './types'

// GET /lab/* with the app's Bearer token (the yachts/briefing pattern). Each endpoint falls back to fixtures.json on
// any error, and always when the app runs on mock data (VITE_DATA=offline, or the feed is illustrative), so the Lab
// works offline. Every result says whether it is the sample (`sample: true`), and the Lab labels it.

export const fixtures = raw as unknown as Fixtures

export type Loaded<T> = { value: T; sample: boolean; error?: string }

let getToken: () => Promise<string | undefined> = async () => undefined
export function bindLabAuth(fn: (() => Promise<string | undefined>) | null) { getToken = fn ?? (async () => undefined) }

const base = () => import.meta.env.VITE_API_URL || 'http://localhost:8000'

/** True when the Lab should not call the server at all. */
export function offline(): boolean {
  return import.meta.env.VITE_DATA === 'offline' || ui.get().feed.isMock
}

export async function get<T>(path: string, sample: () => T): Promise<Loaded<T>> {
  if (offline()) return { value: sample(), sample: true }
  try {
    const token = await getToken()
    const res = await fetch(`${base()}${path}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    if (!res.ok) throw new Error(`GET ${path}: ${res.status}`)
    return { value: (await res.json()) as T, sample: false }
  } catch (e) {
    return { value: sample(), sample: true, error: e instanceof Error ? e.message : String(e) }
  }
}

const q = (params: Record<string, string | number | undefined>) => {
  const s = new URLSearchParams()
  for (const [k, v] of Object.entries(params)) if (v != null && v !== '') s.set(k, String(v))
  const t = s.toString()
  return t ? `?${t}` : ''
}

/** Fixture rows filtered the way the server filters them. */
const byTarget = <T extends { target: string }>(rows: T[], target?: string) => (target ? rows.filter((r) => r.target === target) : rows)
const sinceHours = <T,>(rows: T[], ts: (r: T) => number, hours?: number, now = fixtures.summary.generated_at) =>
  hours == null ? rows : rows.filter((r) => ts(r) >= now - hours * 3_600_000)

export const lab = {
  summary: () => get<Summary>('/lab/summary', () => fixtures.summary),
  runs: (target?: string) => get<Run[]>(`/lab/runs${q({ target })}`, () => byTarget(fixtures.runs, target)),
  run: (id: string) => get<RunDetail | null>(`/lab/runs/${encodeURIComponent(id)}`, () => fixtures.run_detail[id] ?? null),
  proposals: (target?: string) => get<Proposal[]>(`/lab/proposals${q({ target })}`, () => byTarget(fixtures.proposals, target)),
  events: (hours?: number) => get<LabEvent[]>(`/lab/events${q({ hours })}`, () => sinceHours(fixtures.events, (e) => e.ts, hours)),
  metrics: (hours = 24, bucket = 3600) => get<Metrics>(`/lab/metrics${q({ hours, bucket })}`, () => fixtures.metrics),
  data: () => get<LabData>('/lab/data', () => fixtures.data),
}
export type LabApi = typeof lab
