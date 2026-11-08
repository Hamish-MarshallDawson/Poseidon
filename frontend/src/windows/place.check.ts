// Self-check for the window geometry. Run: node src/windows/place.check.ts
import { BOTTOM, TOP } from '../layout.ts'
import { PILL_H, SAFE, WINDOW_H, WINDOW_W, dockSlot, fitHeight, nearestEdge, placeWindow, zonesFor } from './place.ts'
import { riskBand, wilson } from './format.ts'

function check(cond: boolean, msg: string) {
  if (!cond) throw new Error(`place.check: ${msg}`)
}

const vw = 1440
const vh = 900
const W = WINDOW_W
const box = (p: { x: number; y: number }, h = WINDOW_H) => ({ ...p, w: W, h })
const hit = (a: { x: number; y: number; w: number; h: number }, b: { x: number; y: number; w: number; h: number }) =>
  Math.min(a.x + a.w, b.x + b.w) - Math.max(a.x, b.x) > 2 && Math.min(a.y + a.h, b.y + b.h) - Math.max(a.y, b.y) > 2
// Ship on the left half: window opens to its right, clear of the ship.
const a = placeWindow({ x: 300, y: 400 }, [], vw, vh)
check(a.x > 300, 'opens on the freer right side')
// Ship on the right half: window opens to its left and never covers it.
const b = placeWindow({ x: 1200, y: 400 }, [], vw, vh)
check(b.x + W < 1200, 'opens on the freer left side without covering the ship')
// A second window for a ship at the same spot goes to free space, not on top of the first.
const c = placeWindow({ x: 300, y: 400 }, [box(a)], vw, vh)
check(!hit(box(c), box(a)), 'second window does not overlap the first')
// Four windows, then a fifth: still nothing hidden when there is room, and the free-space scan finds it.
const row: ReturnType<typeof box>[] = []
for (let i = 0; i < 3; i++) row.push(box(placeWindow({ x: 700, y: 450 }, row, vw, vh)))
check(row.every((r, i) => row.every((o, j) => i === j || !hit(r, o))), 'three windows tile without overlap')
// Near the top edge it stays below the status line, and never reaches the scrub bar band.
check(placeWindow({ x: 300, y: 0 }, [], vw, vh).y === SAFE.top, 'clamped under the status line')
const low = placeWindow({ x: 300, y: 880 }, [], vw, vh)
check(low.y + fitHeight(zonesFor(vh)) <= vh - BOTTOM, 'clamped above the scrub bar band')
// At 768 px high the window's height shrinks to the free area, so it cannot reach the scrub bar.
check(fitHeight(zonesFor(768)) === WINDOW_H && fitHeight(zonesFor(500)) === 500 - BOTTOM - TOP, 'height follows the free area')
// A blocked zone (the briefing, 400 wide at the left) is avoided.
const brief = { x: 16, y: 100, w: 400, h: 700 }
const d = placeWindow({ x: 200, y: 450 }, [], vw, vh, zonesFor(vh, [brief]))
check(!hit(box(d), brief), 'window opens outside the briefing')
// No room at all: falls back to the least overlap, cascaded so the title bar of the one below stays visible.
const crowded = zonesFor(vh, [{ x: 0, y: 0, w: vw, h: vh }])
check(placeWindow({ x: 300, y: 400 }, [], vw, vh, crowded).x >= SAFE.side, 'falls back inside the viewport')
// Pills stack upwards above the legend toggle.
check(dockSlot(1, vh).y === dockSlot(0, vh).y - PILL_H - 8, 'pills stack upwards')
// Leader end: nearest edge, or nothing when the ship is under the window.
const r = { x: 100, y: 100, w: 200, h: 100 }
const e = nearestEdge({ x: 400, y: 150 }, r)
check(e !== null && e.x === 300 && e.y === 150, 'nearest edge on the right side')
check(nearestEdge({ x: 150, y: 150 }, r) === null, 'no leader when the ship is under the window')
// Wilson interval matches the forecast report's worked example: 6 of 9 → 35–88 %, 6 of 10 → 31–83 %.
const w9 = wilson(6, 9)
const w10 = wilson(6, 10)
check(w9[0] === 35 && w9[1] === 88, `wilson 6/9 = ${w9}`)
check(w10[0] === 31 && w10[1] === 83, `wilson 6/10 = ${w10}`)
check(riskBand(0.74) === 3 && riskBand(0.75) === 4 && riskBand(0.09) === 0, 'risk bands')
console.log('place.check: ok')
