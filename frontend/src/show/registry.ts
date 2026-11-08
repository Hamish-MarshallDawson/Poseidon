import type { ComponentType } from 'react'
import type { VesselView } from '../types'
import { setYachtsLayer, yachts } from '../yachts/store'
import { YachtsList } from '../yachts/Yachts'

// The "Show" choice in the Layers panel: one set of ships at a time. One entry per filter.
//
// To add one, append an entry; nothing else changes (the panel, the map, the status chip and persistence read this list).
// Example, "Possible spoofing":
//   { id: 'spoofing', label: 'Possible spoofing', match: (v) => v.spoof_recent.length > 0,
//     chip: (n) => `Showing ${n} ships with a possible spoofed position` }
// A filter that needs data from the server adds `enter` / `leave` (start / stop loading) and an optional `List`.
export interface ShowFilter {
  id: string
  label: string
  match?: (v: VesselView) => boolean          // absent for 'all'
  chip: (n: number) => string
  List?: ComponentType                        // shown under the control while this filter is selected
  enter?(): void
  leave?(): void
}

export const SHOW_FILTERS: ShowFilter[] = [
  { id: 'all', label: 'All ships', chip: (n) => `Showing all ${n} ships` },
  {
    id: 'yachts', label: 'Sanctioned and notable yachts',
    match: (v) => yachts.get().byMmsi.has(v.mmsi),
    chip: (n) => `Showing ${n} sanctioned and notable ${n === 1 ? 'yacht' : 'yachts'}`,
    List: YachtsList,
    enter: () => setYachtsLayer(true),
    leave: () => setYachtsLayer(false),
  },
  {
    id: 'dark', label: 'Dark-ship candidates',
    match: (v) => v.status === 'gap_open',
    chip: (n) => `Showing ${n} dark-ship ${n === 1 ? 'candidate' : 'candidates'}`,
  },
]

export const showFilter = (id: string): ShowFilter => SHOW_FILTERS.find((f) => f.id === id) ?? SHOW_FILTERS[0]
