// Self-check for the window geometry. Run: node src/windows/place.check.ts
import { CASCADE, PILL_H, SAFE, WINDOW_W, dockSlot, nearestEdge, placeWindow } from './place.ts'
import { riskBand, wilson } from './format.ts'

function check(cond: boolean, msg: string) {
  if (!cond) throw new Error(`place.check: ${msg}`)
}

const vw = 1440
const vh = 900
// Ship on the left half: window opens to its right, clear of the ship.
const a = placeWindow({ x: 300, y: 400 }, [], vw, vh)
check(a.x > 300, 'opens on the freer right side')
// Ship on the right half: window opens to its left and never covers it.
const b = placeWindow({ x: 1200, y: 400 }, [], vw, vh)
check(b.x + WINDOW_W < 1200, 'opens on the freer left side without covering the ship')
// A second window at the same spot cascades by 24 px.
const c = placeWindow({ x: 300, y: 400 }, [a], vw, vh)
check(c.x === a.x + CASCADE && c.y === a.y + CASCADE, 'cascades 24 px from the window before it')
// Near the top edge it stays below the status line.
check(placeWindow({ x: 300, y: 0 }, [], vw, vh).y === SAFE.top, 'clamped under the status line')
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
