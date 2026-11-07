import { ui, nextWindowLetter, type ShipWindow } from '../store/ui'
import { vessels } from '../store/vessels'
import { mapStore } from '../map/context'
import { MAX_OPEN, WINDOW_W, clampToViewport, placeWindow, type Rect } from './place'
import { requestDetail } from './detail'

// The canonical way to open, close and arrange ship windows. The map (ship click), the watchlist (row click)
// and focus mode all call these; ui.windows stays the one source of truth that the map draws brackets from.

// Where each window grew from, so the open and close animations scale from and back to the ship.
export const openOrigins = new Map<number, Rect>()

// The ship's screen position now, in viewport px, or null when the map or the ship isn't there.
export function shipScreenPoint(mmsi: number): Rect | null {
  const map = mapStore.get().map
  const v = vessels.vessels.get(mmsi)
  if (!map || !v) return null
  const p = map.project([v.lon, v.lat])
  const r = map.getContainer().getBoundingClientRect()
  return { x: p.x + r.left, y: p.y + r.top }
}

function topZ(windows: ShipWindow[]): number {
  return windows.reduce((m, w) => Math.max(m, w.z), 0)
}

export function openShipWindow(mmsi: number, at?: { x: number; y: number }): void {
  const { windows } = ui.get()
  const existing = windows.find((w) => w.mmsi === mmsi)
  requestDetail(mmsi)
  if (existing) {
    // Already open: bring it forward and restore it, never open a second one.
    return void ui.set({
      windows: windows.map((w) => (w.mmsi === mmsi ? { ...w, minimised: false, z: topZ(windows) + 1 } : w)),
      frontMmsi: mmsi,
    })
  }
  const ship = at ?? shipScreenPoint(mmsi) ?? { x: innerWidth / 2 - WINDOW_W, y: innerHeight / 2 }
  const open = windows.filter((w) => !w.minimised)
  const pos = placeWindow(ship, open, innerWidth, innerHeight)
  openOrigins.set(mmsi, ship)
  let next = windows
  if (open.length >= MAX_OPEN) {
    // A 5th window minimises the one used least recently, so it moves to a pill instead of vanishing.
    const oldest = open.reduce((a, b) => (b.z < a.z ? b : a))
    next = windows.map((w) => (w === oldest ? { ...w, minimised: true } : w))
  }
  const win: ShipWindow = { mmsi, letter: nextWindowLetter(windows), minimised: false, ...pos, z: topZ(windows) + 1 }
  ui.set({ windows: [...next, win], frontMmsi: mmsi })
}

export function closeShipWindow(mmsi: number): void {
  const windows = ui.get().windows.filter((w) => w.mmsi !== mmsi)
  const open = windows.filter((w) => !w.minimised)
  const front = open.length ? open.reduce((a, b) => (b.z > a.z ? b : a)).mmsi : null
  ui.set((s) => ({ windows, frontMmsi: s.frontMmsi === mmsi ? front : s.frontMmsi, hoverMmsi: s.hoverMmsi === mmsi ? null : s.hoverMmsi }))
}

export function bringToFront(mmsi: number): void {
  const { windows, frontMmsi } = ui.get()
  const w = windows.find((x) => x.mmsi === mmsi)
  if (!w || (frontMmsi === mmsi && w.z === topZ(windows))) return
  ui.set({ windows: windows.map((x) => (x.mmsi === mmsi ? { ...x, z: topZ(windows) + 1 } : x)), frontMmsi: mmsi })
}

export function setMinimised(mmsi: number, minimised: boolean): void {
  if (!minimised) return openShipWindow(mmsi)   // restoring follows the same 4-open rule and comes to the front
  const windows = ui.get().windows.map((w) => (w.mmsi === mmsi ? { ...w, minimised } : w))
  const open = windows.filter((w) => !w.minimised)
  ui.set((s) => ({ windows, frontMmsi: s.frontMmsi === mmsi ? (open.length ? open.reduce((a, b) => (b.z > a.z ? b : a)).mmsi : null) : s.frontMmsi }))
}

export function moveShipWindow(mmsi: number, x: number, y: number): void {
  ui.set((s) => ({ windows: s.windows.map((w) => (w.mmsi === mmsi ? { ...w, x, y } : w)) }))
}

// Keep every window inside the viewport after a resize.
export function clampWindows(): void {
  ui.set((s) => ({
    windows: s.windows.map((w) => {
      const p = clampToViewport(w, innerWidth, innerHeight)
      return p.x === w.x && p.y === w.y ? w : { ...w, ...p }
    }),
  }))
}
