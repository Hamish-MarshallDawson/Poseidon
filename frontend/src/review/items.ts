import { useMemo } from 'react'
import { collab, useInSession, type Entry } from '../collab/presence/core'
import { REASON_LABEL, pct } from '../forecast/labels'
import { useWatchlist } from '../windows/hooks'
import type { WatchlistRow } from '../types'
import { review } from './store'

// One Review list: the viewer's own ships (or the session's shared list), then the forecast's flagged ships as
// System entries. System entries are derived from the live watchlist (Inspect / Watch with p >= 0.10, as the map tags)
// and never written to the server; a ship already on the list is not repeated.
export type Item =
  | { kind: 'you'; mmsi: number }
  | { kind: 'shared'; mmsi: number; entry: Entry }
  | { kind: 'system'; mmsi: number; row: WatchlistRow }

// The leading reason only, with a count of the rest, so the line stays one line.
export const systemReason = (r: WatchlistRow) =>
  `System · ${pct(r.p)} next 6 h · ${REASON_LABEL[r.reason_codes[0]] ?? r.reason_codes[0] ?? 'Forecast'}${r.reason_codes.length > 1 ? ` +${r.reason_codes.length - 1}` : ''}`

export function useReviewItems(): { items: Item[]; dismissed: number } {
  const wl = useWatchlist()
  const inSession = useInSession()
  const mine = review.use((s) => s.list)
  const shared = collab.use((s) => s.list)
  const dismissed = review.use((s) => s.dismissed)
  return useMemo(() => {
    const own: Item[] = inSession ? shared.map((entry) => ({ kind: 'shared', mmsi: entry.mmsi, entry })) : mine.map((mmsi) => ({ kind: 'you', mmsi }))
    const have = new Set(own.map((i) => i.mmsi))
    const flagged = (wl?.entries ?? []).filter((e) => e.decision !== 'none' && e.p >= 0.1)
    const sys: Item[] = flagged.filter((e) => !have.has(e.mmsi)).sort((a, b) => a.rank - b.rank)
      .map((row) => ({ kind: 'system', mmsi: row.mmsi, row }))
    return { items: [...own, ...sys.filter((i) => !dismissed.includes(i.mmsi))], dismissed: sys.length - sys.filter((i) => !dismissed.includes(i.mmsi)).length }
  }, [wl, inSession, mine, shared, dismissed])
}
