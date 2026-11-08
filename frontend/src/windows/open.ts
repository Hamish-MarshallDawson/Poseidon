import { ui, nextWindowLetter, type ShipWindow } from '../store/ui'
import { vessels } from '../store/vessels'
import { mapStore } from '../map/context'
import { MAX_OPEN, WINDOW_W, clampToViewport, fitHeight, findSpot, placeWindow, zonesFor, type Box, type Rect } from './place'
import { requestDetail } from './detail'

// The canonical way to open, close and arrange ship windows. The map (ship click), the watchlist (row click)
// all call these; ui.windows stays the one source of truth that the map draws brackets from.

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

// The occupied zones right now: the boxes of every element tagged data-zone (src/layout.ts).
function blockedBoxes(): Box[] {
  return [...document.querySelectorAll<HTMLElement>('[data-zone]')].flatMap((el) => {
    const r = el.getBoundingClientRect()
    return r.width > 0 && r.height > 0 && getComputedStyle(el).visibility !== 'hidden' ? [{ x: r.left, y: r.top, w: r.width, h: r.height }] : []
  })
}
const boxOf = (w: ShipWindow): Box => ({ x: w.x, y: w.y, w: WINDOW_W, h: fitHeight(zonesFor(innerHeight)) })

function topZ(windows: ShipWindow[]): number {
  return windows.reduce((m, w) => Math.max(m, w.z), 0)
}

export function openShipWindow(mmsi: number, at?: { x: number; y: number }): void {
  const { windows } = ui.get()
  const existing = windows.find((w) => w.mmsi === mmsi)
  requestDetail(mmsi)
  const open = windows.filter((w) => !w.minimised && w.mmsi !== mmsi)
  // A 5th open window (new or restored) minimises the one used least recently, so it moves to a pill instead of vanishing.
  const oldest = open.length >= MAX_OPEN ? open.reduce((a, b) => (b.z < a.z ? b : a)) : null
  const next = oldest ? windows.map((w) => (w === oldest ? { ...w, minimised: true } : w)) : windows
  if (existing) {
    // Already open: bring it forward and restore it, never open a second one.
    return void ui.set({
      windows: next.map((w) => (w.mmsi === mmsi ? { ...w, minimised: false, z: topZ(windows) + 1 } : w)),
      frontMmsi: mmsi,
    })
  }
  const ship = at ?? shipScreenPoint(mmsi) ?? { x: innerWidth / 2 - WINDOW_W, y: innerHeight / 2 }
  const pos = placeWindow(ship, open.filter((w) => w !== oldest).map(boxOf), innerWidth, innerHeight, zonesFor(innerHeight, blockedBoxes()))
  openOrigins.set(mmsi, ship)
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

// When a zone appears (a panel, the legend, the briefing), windows under it move to the nearest free
// spot. Later drags are the user's choice and are left alone.
export function reflowWindows(): void {
  const z = zonesFor(innerHeight, blockedBoxes())
  const hit = (a: Box, b: Box) => Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x) > 2 && Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y) > 2
  const win = ui.get().windows.filter((w) => !w.minimised)
  const touching = new Set(win.filter((w) => z.blocked.some((o) => hit(boxOf(w), o))).map((w) => w.mmsi))
  if (!touching.size) return
  // Windows that must move leave the obstacle list until each is placed, so they don't block one another's new spots.
  // If that still leaves a clash (no room beside the windows that stayed), all open windows are laid out again.
  const run = (moving: Set<number>) => {
    const fixed: Box[] = win.filter((w) => !moving.has(w.mmsi)).map(boxOf)
    const next = new Map<number, Rect>()
    let clash = false
    for (const w of win) {
      if (!moving.has(w.mmsi)) continue
      const p = findSpot(w, null, fixed, innerWidth, innerHeight, z)
      const b = { ...boxOf(w), ...p }
      clash = clash || fixed.some((o) => hit(b, o)) || z.blocked.some((o) => hit(b, o))
      fixed.push(b)
      next.set(w.mmsi, p)
    }
    return { next, clash }
  }
  let r = run(touching)
  if (r.clash) r = run(new Set(win.map((w) => w.mmsi)))
  ui.set((s) => ({ windows: s.windows.map((w) => (r.next.has(w.mmsi) ? { ...w, ...r.next.get(w.mmsi)! } : w)) }))
}
