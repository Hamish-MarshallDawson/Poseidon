import type { VesselView } from '../types'

// Z-order, sort key and opacity steps from R2-AGENT1-STACKING.md.

export const OPACITY = { full: 1, routine: 0.8, trace: 0.2 }   // Context = --dvm-focus-dim-opacity (per theme)

export interface Rank { decision: 'inspect' | 'watch' | 'none'; rank: number }

// Z tier 1..8 (tier 0, the selected/focused/hovered ship, is drawn after everything and never sorted).
export function zTier(v: VesselView, rank: Rank | undefined): number {
  if (rank?.decision === 'inspect') return 2
  if (v.status === 'gap_open') return 3
  if (rank?.decision === 'watch') return 4
  if (v.sanctioned || v.spoof_recent.length) return 5
  // 6 = followed (pinned this session): no pinning in the UI yet
  if ((v.length_m ?? 0) >= 200 || (v.sog_kn ?? 0) >= 18) return 7
  return 8
}

// sort_key = (8 − tier) × 1 000 000 + order_in_tier × 1 000 + recency; a higher key draws on top.
export function sortKey(v: VesselView, tier: number, rank: Rank | undefined, nowMs: number): number {
  let order = 0
  if (tier === 2 || tier === 4) order = 999 - Math.min(rank?.rank ?? 999, 999)
  else if (tier === 3) order = Math.min(Math.floor((nowMs - v.last_ts) / 60000), 999)
  else if (tier === 7) order = Math.min(v.length_m ?? 0, 999)
  const recency = 999 - Math.min(Math.max(0, Math.floor((nowMs - v.last_ts) / 60000)), 999)
  return (8 - tier) * 1_000_000 + order * 1000 + recency
}

// Ships at Full strength (tiers 0–5) are never folded into a stack and never dimmed to Routine.
export const isFull = (tier: number) => tier <= 5

// Fan-out: 2–8 ships on a ring, highest z-order at 12 o'clock, then clockwise. Offsets in CSS px.
export const FAN_RADIUS = { far: 52, mid: 78, near: 110 }
export function ringOffsets(n: number, radius: number): [number, number][] {
  return Array.from({ length: n }, (_, i) => {
    const a = (i / n) * 2 * Math.PI
    return [Math.sin(a) * radius, -Math.cos(a) * radius]
  })
}
