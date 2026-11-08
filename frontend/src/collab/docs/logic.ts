import type { Doc } from '../client'
import type { Briefing } from '../../briefing/store'

// Pure helpers for the session channel: no React, no stores, so vitest can cover them.

export const NOTE_MAX = 1000          // a note's length cap in the UI (the API allows 4000)
export const BODY_MAX = 4000          // the API's cap on a document body

export type Piece = { text: string } | { ship: number } | { doc: number }

// A note can point at a ship (any 9-digit MMSI) or a document (doc#12). Everything else stays plain text.
const REF = /\b(\d{9})\b|\bdoc#(\d{1,9})\b/g
export function tokenize(body: string): Piece[] {
  const out: Piece[] = []
  let at = 0
  for (const m of body.matchAll(REF)) {
    if (m.index > at) out.push({ text: body.slice(at, m.index) })
    out.push(m[1] ? { ship: Number(m[1]) } : { doc: Number(m[2]) })
    at = m.index + m[0].length
  }
  if (at < body.length) out.push({ text: body.slice(at) })
  return out
}

/** The plain-text body saved for a Brief me result: headline, overview, one block per ship, then the link between them. */
export function briefingText(b: Briefing): string {
  const s = b.summary
  const lines = [s.headline, '', s.overview]
  for (const v of s.per_vessel) {
    lines.push('', `${v.name ?? `MMSI ${v.mmsi}`} (${v.mmsi}) · ${v.risk}`, ...v.findings.map((f) => `- ${f}`), ...v.caveats.map((c) => `Caveat: ${c}`))
  }
  if (s.correlation.found) lines.push('', `Link between ships (${s.correlation.strength}): ${s.correlation.explanation}`)
  lines.push('', 'Behaviour only, never an accusation.')
  const text = lines.join('\n')
  return text.length <= BODY_MAX ? text : `${text.slice(0, BODY_MAX - 1)}…`
}

/** Ships with a saved briefing: the tracking list shows these as "report generated". */
export function reportedShips(docs: Doc[]): Set<number> {
  const out = new Set<number>()
  for (const d of docs) if (d.kind === 'briefing') for (const m of d.mmsis) out.add(m)
  return out
}

/** The newest summary, pinned at the top of the channel. */
export const pinnedSummary = (docs: Doc[]): Doc | undefined => docs.findLast((d) => d.kind === 'summary')

// A summary needs something to summarise: a note, a saved briefing or a tracked ship. An earlier summary doesn't count.
export const canSummarise = (docs: Doc[], trackedShips: number): boolean =>
  trackedShips > 0 || docs.some((d) => d.kind !== 'summary')

export const initials = (name: string | null): string =>
  (name ?? '').trim().split(/\s+/).slice(0, 2).map((w) => w[0]?.toUpperCase() ?? '').join('') || '?'
