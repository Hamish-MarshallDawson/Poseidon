import { createStore } from './store'
import type { SourceStatus, Stats } from '../types'

// Shared UI state. Who writes what is in frontend/ARCHITECTURE.md. Keep additions additive and small.

export interface ShipWindow {
  mmsi: number
  letter: string          // A, B, C… the badge shown on the window and beside the ship on the map
  minimised: boolean
  x: number; y: number    // top-left in CSS px of the viewport
  z: number               // stacking order; the highest is the front window
}

export interface FocusRelation { mmsi: number; reason: 'nearby' | 'rendezvous' | 'also_dark' | 'same_flag' }

export type TimeRange = '1h' | '6h' | '24h' | { from_ts: number; to_ts: number }

export interface UIState {
  // windows and selection (windows/ writes; map/ reads for brackets, badges and dimming)
  windows: ShipWindow[]
  frontMmsi: number | null      // the window clicked last: the only one with a leader line
  hoverMmsi: number | null
  // focus mode (windows/ sets focusMmsi; map/ computes related and dims the rest)
  focusMmsi: number | null
  focusRelated: FocusRelation[]
  // stack list (map/ writes when a chip of 9+ ships is clicked; windows/ may render it, map/ has a fallback popover)
  stack: { mmsis: number[]; x: number; y: number } | null   // mmsis in z-order; x/y = chip centre in CSS px
  // drop-ins
  legendOpen: boolean
  watchlistOpen: boolean
  reviewOpen: boolean
  layersOpen: boolean
  layers: { density: boolean; coverage: boolean; inland: boolean; labels: boolean; depth: boolean; forecast: boolean }
  // what the map is showing right now (map/ writes; the status line reads)
  view: { inView: number; shown: number; stacked: number; inCells: number; noCoverageCells: number; zoom: number }
  // feed state (data adapter writes; status line and scrub bar read)
  feed: {
    connected: boolean; mode: 'live' | 'replay'; speed: number; paused: boolean
    now_ts: number                      // the shown moment: wall clock in live, the replay clock in replay
    replay: { from_ts: number; to_ts: number } | null
    sources: SourceStatus[]; stats: Stats; isMock: boolean
  }
  // follow selected (map/follow.ts writes; replay only): only the open windows' ships and their tracks are shown
  follow: boolean
  // scrub bar (timeline/ writes)
  time: { range: TimeRange; dragging: boolean; dragT: number | null }
}

export const ui = createStore<UIState>({
  windows: [],
  frontMmsi: null,
  hoverMmsi: null,
  focusMmsi: null,
  focusRelated: [],
  stack: null,
  legendOpen: false,
  watchlistOpen: false,
  reviewOpen: false,
  layersOpen: false,
  layers: { density: true, coverage: true, inland: false, labels: true, depth: false, forecast: true },
  view: { inView: 0, shown: 0, stacked: 0, inCells: 0, noCoverageCells: 0, zoom: 0 },
  feed: {
    connected: false, mode: 'live', speed: 1, paused: false, now_ts: Date.now(), replay: null,
    sources: [], stats: { tracked: 0, msgs_per_s: 0, queue_depth: 0 }, isMock: false,
  },
  follow: false,
  time: { range: '6h', dragging: false, dragT: null },
})

// Letters for ship windows: A..Z then AA.. ; the lowest free letter is reused when a window closes.
export function nextWindowLetter(windows: ShipWindow[]): string {
  const used = new Set(windows.map((w) => w.letter))
  for (let i = 0; ; i++) {
    const letter = i < 26 ? String.fromCharCode(65 + i) : String.fromCharCode(65 + Math.floor(i / 26) - 1) + String.fromCharCode(65 + (i % 26))
    if (!used.has(letter)) return letter
  }
}
