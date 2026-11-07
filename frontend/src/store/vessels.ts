import type { GapEvent, SpoofEvent, VesselView, Watchlist, CoverageCellView } from '../types'

// One frame from the feed: a whole snapshot or a delta of whole VesselView objects (06 section 4.3).
export interface Frame {
  type: 'snapshot' | 'delta'
  now_ts: number
  vessels: VesselView[]
  removed: number[]
  gaps: GapEvent[]
  spoofs: SpoofEvent[]
  watchlist: Watchlist | null
  coverage?: CoverageCellView[]
  trails?: Record<string, [number, number, number][]>
}

export type VesselListener = (changed: number[], removed: number[], frame: Frame) => void

// The current state of every ship, outside React. Applying a frame is O(changed), never O(all ships).
// Interpolation state (previous position, eased heading) is the map layer's business (map/), keyed by mmsi.
export class VesselStore {
  readonly vessels = new Map<number, VesselView>()
  readonly gaps = new Map<string, GapEvent>()          // latest version per gap id
  readonly spoofs: SpoofEvent[] = []                   // most recent first, capped
  readonly coverage = new Map<string, CoverageCellView>()
  readonly trails = new Map<number, [number, number, number][]>()
  watchlist: Watchlist | null = null
  version = 0                                          // bumps once per frame
  now_ts = 0
  private listeners = new Set<VesselListener>()

  applyFrame(frame: Frame): void {
    const changed: number[] = []
    if (frame.type === 'snapshot') {
      this.vessels.clear(); this.gaps.clear(); this.coverage.clear(); this.trails.clear(); this.spoofs.length = 0
      for (const [k, t] of Object.entries(frame.trails ?? {})) this.trails.set(Number(k), t)
      for (const c of frame.coverage ?? []) this.coverage.set(c.cell_id, c)
    }
    for (const mmsi of frame.removed) if (this.vessels.delete(mmsi)) this.trails.delete(mmsi)
    for (const v of frame.vessels) { this.vessels.set(v.mmsi, v); changed.push(v.mmsi) }
    for (const g of frame.gaps) {
      const cur = this.gaps.get(g.id)
      if (!cur || g.version >= cur.version) this.gaps.set(g.id, g)
    }
    if (frame.spoofs.length) {
      this.spoofs.unshift(...frame.spoofs)
      if (this.spoofs.length > 500) this.spoofs.length = 500
    }
    if (frame.watchlist) this.watchlist = frame.watchlist
    this.now_ts = frame.now_ts
    this.version++
    for (const l of this.listeners) l(changed, frame.removed, frame)
  }

  subscribe(listener: VesselListener): () => void {
    this.listeners.add(listener)
    return () => void this.listeners.delete(listener)
  }
}

export const vessels = new VesselStore()
