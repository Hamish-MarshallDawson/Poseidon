// Pure geometry for ship windows, kept free of imports so `node src/windows/place.check.ts` can test it.

export const WINDOW_W = 322   // the card is 320 plus a 1 px border each side
export const WINDOW_H = 495
export const PILL_W = 173
export const PILL_H = 38
export const MAX_OPEN = 4
export const CASCADE = 24      // offset from the window before it, so title bars never hide each other

// Map chrome the windows keep clear of: the status line on top, the scrub bar and legend toggle below.
export const SAFE = { top: 56, bottom: 100, side: 16 }
const GAP = 40                 // from the ship to the near edge of its window

export interface Rect { x: number; y: number }

export function clampToViewport(p: Rect, vw: number, vh: number, w = WINDOW_W, h = WINDOW_H): Rect {
  const maxX = Math.max(SAFE.side, vw - SAFE.side - w)
  const maxY = Math.max(SAFE.top, vh - SAFE.bottom - h)
  return { x: Math.min(maxX, Math.max(SAFE.side, p.x)), y: Math.min(maxY, Math.max(SAFE.top, p.y)) }
}

// A new window goes on the side of the ship with more free map, never over the ship, vertically centred on it,
// and 24 px down and outwards from any open window already at that spot.
export function placeWindow(ship: Rect, others: Rect[], vw: number, vh: number): Rect {
  const right = vw - ship.x >= ship.x
  let p = clampToViewport({ x: right ? ship.x + GAP : ship.x - GAP - WINDOW_W, y: ship.y - WINDOW_H / 2 }, vw, vh)
  for (let i = 0; i < 8 && others.some((o) => Math.abs(o.x - p.x) < CASCADE && Math.abs(o.y - p.y) < CASCADE); i++) {
    p = clampToViewport({ x: p.x + (right ? CASCADE : -CASCADE), y: p.y + CASCADE }, vw, vh)
  }
  return p
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
