import { useMemo } from 'react'
import { createStore } from '../../store/store'
import { ui } from '../../store/ui'
import { api, CollabError } from '../client'
import type { Doc } from '../client'
import { collab } from '../store'
import type { Briefing } from '../../briefing/store'
import { briefingText, reportedShips } from './logic'

// The session channel: open state, summary progress, and the calls that add a note, save a briefing or summarise.
// The documents themselves live in collab.get().documents (the shared core store).

export const channel = createStore({
  open: false,
  summary: 'idle' as 'idle' | 'busy' | 'error',
  summaryError: null as string | null,
  offer: false,            // everyone else has left: offer the summary
  openDoc: null as number | null,   // a document opened from a reference in the channel
})

const sid = () => collab.get().session?.id ?? null

export function openChannel() {
  ui.set({ reviewOpen: false, watchlistOpen: false, layersOpen: false })   // one panel at a time in the right column
  channel.set({ open: true })
}
export const closeChannel = () => channel.set({ open: false })
ui.subscribe((s, p) => {
  if ((s.reviewOpen && !p.reviewOpen) || (s.watchlistOpen && !p.watchlistOpen) || (s.layersOpen && !p.layersOpen)) closeChannel()
})
// Leaving or switching session closes the channel.
collab.subscribe((s, p) => { if (s.session?.id !== p.session?.id) channel.set({ open: false, offer: false, summary: 'idle', summaryError: null }) })

// A server reply is applied at once; the same document arriving over /ws is then ignored (applied by id).
const apply = (document: Doc, session_id: string) => collab.applyMessage({ type: 'document', session_id, document })

export async function sendNote(body: string, mmsi: number | null): Promise<void> {
  const id = sid()
  const text = body.trim()
  if (!id || !text) return
  apply((await api.addDocument(id, text, mmsi)).document, id)
}

export async function saveBriefing(b: Briefing): Promise<void> {
  const id = sid()
  if (!id) throw new Error('Not in a session')
  const one = b.mmsis.length === 1 ? b.mmsis[0] : null
  apply((await api.addDocument(id, briefingText(b), one, { kind: 'briefing', mmsis: b.mmsis.slice(0, 10) })).document, id)
}

const SUMMARY_ERRORS: Record<number, string> = {
  409: 'Nothing to summarise yet. Add a note, a ship or a briefing first.',
  503: 'The summary is not set up on the server yet (no Gemini key).',
  502: 'The AI summary failed. Try again in a moment.',
}
export async function summariseSession(): Promise<void> {
  const id = sid()
  if (!id || channel.get().summary === 'busy') return
  channel.set({ summary: 'busy', summaryError: null, offer: false })
  try {
    apply((await api.summarise(id)).document, id)
    channel.set({ summary: 'idle', open: true })
  } catch (e) {
    const status = e instanceof CollabError ? e.status : 0
    channel.set({ summary: 'error', summaryError: SUMMARY_ERRORS[status] ?? 'Could not reach the server. Try again.' })
  }
}

/** Ships with a saved briefing in this session (the tracking list shows "report generated" for these). */
export function useReported(): Set<number> {
  const docs = collab.use((s) => s.documents)
  return useMemo(() => reportedShips(docs), [docs])
}

// Offer the summary when the others have left: presence falls to just me after it showed two or more.
let peak = 0
collab.subscribe((s, p) => {
  if (s.presence === p.presence) return
  const n = s.presence.length
  if (!s.session) { peak = 0; return }
  if (n >= 2) peak = n
  else if (peak >= 2 && n <= 1 && s.documents.length > 0 && !s.documents.some((d) => d.kind === 'summary')) {
    peak = 0
    channel.set({ offer: true })
    openChannel()
  }
})
