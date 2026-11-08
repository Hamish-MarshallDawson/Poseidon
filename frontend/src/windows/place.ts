// Pure geometry for ship windows, kept free of runtime imports so `node src/windows/place.check.ts` can test it.
import { BOTTOM, INSET, TOP } from '../layout.ts'

export const WINDOW_W = 322   // the card is 320 plus a 1 px border each side
export const WINDOW_H = 575   // the tallest card seen (replay adds rows); the CSS max-height clamps it to the free area
export const MIN_H = 240
export const PILL_W = 173
export const PILL_H = 38
export const MAX_OPEN = 4
export const CASCADE = 24      // fallback offset from a window it must overlap, so title bars never hide each other

export const SAFE = { top: TOP, bottom: BOTTOM, side: INSET }
const GAP = 40                 // from the ship to the near edge of its window
const STEP = 32                // grid step when scanning for a free spot

export interface Rect { x: number; y: number }
export interface Box extends Rect { w: number; h: number }
// The free area is the viewport between TOP and `bottom`; `blocked` are the occupied zones inside it.
export interface Zones { bottom: number; blocked: Box[] }

export const zonesFor = (vh: number, blocked: Box[] = []): Zones => ({ bottom: vh - BOTTOM, blocked })

// Height a window may have: its natural height, or the free area's height when that is smaller.
export const fitHeight = (z: Zones) => Math.max(MIN_H, Math.min(WINDOW_H, z.bottom - TOP))

export function clampToViewport(p: Rect, vw: number, vh: number, w = WINDOW_W, h = WINDOW_H): Rect {
  const maxX = Math.max(SAFE.side, vw - SAFE.side - w)
  const maxY = Math.max(SAFE.top, vh - SAFE.bottom - h)
  return { x: Math.min(maxX, Math.max(SAFE.side, p.x)), y: Math.min(maxY, Math.max(SAFE.top, p.y)) }
}

const overlap = (a: Box, b: Box) => {
  const dx = Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x)
  const dy = Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y)
  return dx > 2 && dy > 2 ? dx * dy : 0
}
const covers = (b: Box, p: Rect) => p.x >= b.x && p.x <= b.x + b.w && p.y >= b.y && p.y <= b.y + b.h

// The first spot that touches nothing: `pref` itself, then `alt`, then a grid scan nearest to `pref`. When nothing is
// free, the spot with the least overlap (cascade offsets from `pref` are candidates, so title bars stay visible).
export function findSpot(pref: Rect, alt: Rect | null, others: Box[], vw: number, vh: number, z: Zones, ship: Rect | null = null): Rect {
  const h = fitHeight(z)
  const all = [...z.blocked, ...others]
  const box = (p: Rect): Box => ({ ...p, w: WINDOW_W, h })
  const score = (p: Rect) => all.reduce((s, o) => s + overlap(box(p), o), 0) + (ship && covers(box(p), ship) ? 1e9 : 0)
  const clamp = (p: Rect) => clampToViewport(p, vw, vh, WINDOW_W, h)
  const first = [pref, ...(alt ? [alt] : [])].map(clamp)
  const grid: Rect[] = []
  for (let y = TOP; y <= z.bottom - h; y += STEP) for (let x = SAFE.side; x <= vw - SAFE.side - WINDOW_W; x += STEP) grid.push({ x, y })
  const near = (p: Rect) => Math.hypot(p.x - pref.x, p.y - pref.y)
  grid.sort((a, b) => near(a) - near(b))
  const free = [...first, ...grid].find((p) => score(p) === 0)
  if (free) return free
  const dir = ship && ship.x > vw / 2 ? -1 : 1
  const cascade = Array.from({ length: 8 }, (_, i) => clamp({ x: pref.x + dir * (i + 1) * CASCADE, y: pref.y + (i + 1) * CASCADE }))
  return [...first, ...cascade, ...grid].reduce((best, p) => (score(p) < score(best) ? p : best))
}

// A new window goes on the side of the ship with more free map, vertically centred on it, clear of the zones and of
// the other windows, and never over the ship.
export function placeWindow(ship: Rect, others: Box[], vw: number, vh: number, z: Zones = zonesFor(vh)): Rect {
  const h = fitHeight(z)
  const right = vw - ship.x >= ship.x
  const at = (r: boolean): Rect => ({ x: r ? ship.x + GAP : ship.x - GAP - WINDOW_W, y: ship.y - h / 2 })
  return findSpot(at(right), at(!right), others, vw, vh, z, ship)
}

// Minimised pills dock along the bottom-left edge, stacking upwards above the legend toggle.
export function dockSlot(i: number, vh: number): Rect {
  const toggleTop = vh - 22 - 36   // the legend toggle sits 22 px up, centred on the scrub bar's row
  return { x: SAFE.side, y: toggleTop - 8 - PILL_H - i * (PILL_H + 8) }
}

// The point on a rectangle's edge nearest to p, or null when p is inside it.
export function nearestEdge(p: Rect, r: Rect & { w: number; h: number }): Rect | null {
  const x = Math.min(r.x + r.w, Math.max(r.x, p.x))
  const y = Math.min(r.y + r.h, Math.max(r.y, p.y))
  return x === p.x && y === p.y ? null : { x, y }
}
