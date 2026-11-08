import { createStore } from '../store/store'
import { ui } from '../store/ui'
import { vessels } from '../store/vessels'
import { collab } from '../collab/store'
import { review } from '../review/store'
import { mockBriefing } from './mock'

// AI briefing: POST /briefing (Gemini summary of 1 to 10 live ships) and POST /briefing/speech (ElevenLabs MP3).
// Contract: backend/dvm/briefing/routes.py. Keys live on the server only; the browser sends the Auth0 Bearer token.

export const MAX_SHIPS = 10

/** Why a ship is in the briefing, so the summary can say who suggested it: the prediction model, a user, or just opened. */
export type Origin = { kind: 'system'; reasons: string[]; risk_p: number | null } | { kind: 'user'; added_by: string } | { kind: 'selected' }

export function originOf(mmsi: number): Origin {
  const c = collab.get()
  const shared = c.session ? c.list.find((e) => e.mmsi === mmsi) : undefined
  if (shared) return { kind: 'user', added_by: shared.added_by === c.me?.id ? 'you' : c.session?.members.find((m) => m.id === shared.added_by)?.name ?? 'a teammate' }
  if (!c.session && review.get().list.includes(mmsi)) return { kind: 'user', added_by: 'you' }
  const row = vessels.watchlist?.entries.find((e) => e.mmsi === mmsi && e.decision !== 'none')
  return row ? { kind: 'system', reasons: row.reason_codes, risk_p: row.p } : { kind: 'selected' }
}

export interface VesselBrief { mmsi: number; name: string | null; risk: string; findings: string[]; caveats: string[] }
export interface Correlation { found: boolean; strength: 'none' | 'weak' | 'moderate' | 'strong'; links: string[]; explanation: string }
export interface Briefing {
  generated_at: number
  model: string
  mmsis: number[]
  summary: { headline: string; overview: string; per_vessel: VesselBrief[]; correlation: Correlation; speech_script: string }
  voice_available: boolean
  mock?: boolean
}

export interface BriefingState {
  selected: number[]                                   // Watchlist multi-select
  open: boolean
  status: 'idle' | 'loading' | 'done' | 'error'
  requested: number[]
  result: Briefing | null
  error: string | null
  voice: 'idle' | 'loading' | 'playing' | 'error'
  voiceError: string | null
}

export const briefing = createStore<BriefingState>({
  selected: [], open: false, status: 'idle', requested: [], result: null, error: null, voice: 'idle', voiceError: null,
})

let getToken: () => Promise<string | undefined> = async () => undefined
export function bindBriefingAuth(fn: (() => Promise<string | undefined>) | null) { getToken = fn ?? (async () => undefined) }

const base = () => import.meta.env.VITE_API_URL || 'http://localhost:8000'

async function post(path: string, body: unknown): Promise<Response> {
  const token = await getToken()
  return fetch(`${base()}${path}`, {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', ...(token ? { Authorization: `Bearer ${token}` } : {}) },
    body: JSON.stringify(body),
  })
}

function explain(status: number): string {
  if (status === 404) return 'One of these ships is not in the live picture any more. Pick them again from the map.'
  if (status === 422) return `Pick between 1 and ${MAX_SHIPS} ships.`
  if (status === 401 || status === 403) return 'Your login has expired. Reload the page and log in again.'
  if (status === 503) return 'The AI summary is not set up on the server yet (no Gemini key).'
  return 'The AI summary failed. Try again in a moment.'
}

export function toggleSelected(mmsi: number) {
  briefing.set((s) => {
    if (s.selected.includes(mmsi)) return { selected: s.selected.filter((m) => m !== mmsi) }
    return s.selected.length >= MAX_SHIPS ? {} : { selected: [...s.selected, mmsi] }
  })
}
export const clearSelected = () => briefing.set({ selected: [] })

let inFlight = 0
export async function runBriefing(mmsis: number[]): Promise<void> {
  if (briefing.get().status === 'loading' || mmsis.length === 0) return
  const ids = mmsis.slice(0, MAX_SHIPS)
  stopVoice()
  briefing.set({ open: true, status: 'loading', requested: ids, result: null, error: null, voice: 'idle', voiceError: null })
  const run = ++inFlight
  try {
    const res = await post('/briefing', { mmsis: ids, origins: Object.fromEntries(ids.map((m) => [m, originOf(m)])) })
    if (run !== inFlight) return
    if (!res.ok) throw Object.assign(new Error(explain(res.status)), { status: res.status })
    briefing.set({ status: 'done', result: (await res.json()) as Briefing })
  } catch (e) {
    if (run !== inFlight) return
    const status = (e as { status?: number }).status
    // Mock data mode: the ships are not in a backend's live picture (or there is no backend), so show a labelled sample.
    if (ui.get().feed.isMock && (status === undefined || status === 404 || status === 503)) {
      await new Promise((r) => setTimeout(r, 900))
      if (run !== inFlight) return
      briefing.set({ status: 'done', result: mockBriefing(ids, (m) => vessels.vessels.get(m)?.name ?? null) })
      return
    }
    briefing.set({ status: 'error', error: e instanceof Error && status ? e.message : 'Could not reach the server. Check the connection and try again.' })
  }
}

export function closeBriefing() {
  inFlight++
  stopVoice()
  briefing.set({ open: false, status: 'idle', result: null, error: null })
}

// Voiceover: one Audio element, one blob URL at a time, revoked when it stops.
let audio: HTMLAudioElement | null = null
let audioUrl: string | null = null
function stopVoice() {
  if (audio) { audio.pause(); audio.onended = null; audio = null }
  if (audioUrl) { URL.revokeObjectURL(audioUrl); audioUrl = null }
  if (briefing.get().voice !== 'idle') briefing.set({ voice: 'idle' })
}
export { stopVoice }

export async function playVoice(): Promise<void> {
  const r = briefing.get().result
  if (!r || briefing.get().voice === 'loading') return
  if (briefing.get().voice === 'playing') return stopVoice()
  if (r.mock) { briefing.set({ voice: 'error', voiceError: 'Voiceover is not available for the sample briefing.' }); return }
  briefing.set({ voice: 'loading', voiceError: null })
  try {
    const res = await post('/briefing/speech', { text: r.summary.speech_script })
    if (!res.ok) throw new Error(res.status === 503 ? 'Voiceover is not set up on the server yet (no ElevenLabs key).' : 'Voiceover failed. Try again.')
    audioUrl = URL.createObjectURL(await res.blob())
    audio = new Audio(audioUrl)
    audio.onended = stopVoice
    await audio.play()
    briefing.set({ voice: 'playing' })
  } catch (e) {
    stopVoice()
    briefing.set({ voice: 'error', voiceError: e instanceof Error && e.message.startsWith('Voice') ? e.message : 'Voiceover could not play. Try again.' })
  }
}
