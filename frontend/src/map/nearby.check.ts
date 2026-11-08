// Self-check for Nearby ships maths. Run: node --experimental-strip-types src/map/nearby.check.ts
import { candidates, closestApproach, metAtSea } from './nearby.ts'
import type { Track } from './nearby.ts'

function check(cond: boolean, msg: string) { if (!cond) throw new Error(`nearby.check: ${msg}`) }
const T0 = Date.UTC(2026, 10, 8, 6, 0)
const M = 60_000
// A sails east along lat 59 at the equator-ish 0.01 deg lon per minute; B sails north across A's line at lon 20.20.
const A: Track = Array.from({ length: 361 }, (_, i) => [T0 + i * M, 20 + i * 0.001, 59])
const B: Track = Array.from({ length: 361 }, (_, i) => [T0 + i * M, 20.2, 58.9 + i * 0.0005])
const ca = closestApproach(A, B)!
check(ca != null && ca.dM < 200, `crossing is close, got ${ca?.dM}`)
check(Math.abs(ca.ts - (T0 + 200 * M)) <= 2 * M, 'crossing time near minute 200')
const far: Track = A.map(([t, x, y]) => [t, x, y + 0.2])   // about 22 km north the whole time
check(closestApproach(A, far)!.dM > 20_000, 'parallel far ship stays far')
check(closestApproach(A, [[T0 + 400 * M, 20, 59]]) === null, 'no overlap in time')
const hole: Track = [[T0, 20, 59], [T0 + 60 * M, 20, 59]]       // 60 min between fixes: a hole, not a position
const h = closestApproach(A, hole)!
check(h.ts === T0 || h.ts === T0 + 60 * M, 'nothing invented inside the hole, only its two fixes')

// Met at sea: both nearly still, 100 m apart, for 20 min; then a run of 5 min is not enough.
const still = (lat: number, mins: number): Track => Array.from({ length: mins + 1 }, (_, i) => [T0 + i * M, 20, lat])
check(metAtSea(still(59, 20), still(59.0009, 20)) != null, 'two still ships 100 m apart met')
check(metAtSea(still(59, 20), still(59.01, 20)) === null, '1.1 km apart did not meet')
check(metAtSea(still(59, 5), still(59.0009, 5)) === null, '5 min is too short')
const fast: Track = A.map(([t, , y], i) => [t, 20 + i * 0.01, y])   // about 19 kn
check(metAtSea(fast, fast) === null, 'moving ships did not meet')

const ships = [
  { mmsi: 1, lon: 20.3, lat: 59.1, sog_kn: 0 },       // inside the buffer
  { mmsi: 2, lon: 20.3, lat: 70, sog_kn: 10 },        // far beyond 5 km + 6 h at 25 kn (~280 km)
  { mmsi: 3, lon: 20.15, lat: 59.02, sog_kn: 5 },
  { mmsi: 9, lon: 20, lat: 59, sog_kn: 5 },           // the focal ship itself
]
const c = candidates(A, ships, 9)
check(c.join() === '3,1', `candidates sorted by distance, got ${c}`)
check(candidates(A, ships, 9, 1).length === 1, 'cap')
console.log('nearby.check: ok')
