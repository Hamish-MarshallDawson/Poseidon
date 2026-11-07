import { useSyncExternalStore } from 'react'
import { vessels } from '../store/vessels'
import { ui } from '../store/ui'
import type { GapEvent, VesselView, Watchlist } from '../types'

// One ship from the VesselStore. Re-renders only when that ship's VesselView object is replaced.
export function useVessel(mmsi: number): VesselView | undefined {
  return useSyncExternalStore(
    (cb) => vessels.subscribe((changed, removed) => { if (changed.includes(mmsi) || removed.includes(mmsi)) cb() }),
    () => vessels.vessels.get(mmsi),
  )
}

export function useGap(id: string | null | undefined): GapEvent | undefined {
  return useSyncExternalStore((cb) => vessels.subscribe(cb), () => (id ? vessels.gaps.get(id) : undefined))
}

export function useWatchlist(): Watchlist | null {
  return useSyncExternalStore((cb) => vessels.subscribe(cb), () => vessels.watchlist)
}

// The shown moment: the replay clock in replay, the wall clock (from the feed, about 1 Hz) in live.
export function useNow(): number {
  return ui.use((s) => s.feed.now_ts)
}
