// Self-check for the pure timeline logic: node src/timeline/selfcheck.ts (Node 22.6+ strips the types).
import { ReplayLog } from '../data/replayLog.ts'
import { wilson } from '../forecast/stats.ts'
import type { VesselView } from '../types.ts'

// No node:assert: the app's tsconfig has no Node types, and this file sits in src/.
const assert = {
  ok(c: unknown, m = 'assertion failed') { if (!c) throw new Error(m) },
  equal(a: unknown, b: unknown) { if (a !== b) throw new Error(`${String(a)} !== ${String(b)}`) },
  deepEqual(a: unknown, b: unknown) { if (JSON.stringify(a) !== JSON.stringify(b)) throw new Error(`${JSON.stringify(a)} != ${JSON.stringify(b)}`) },
}

const v = (mmsi: number, lat: number): VesselView => ({ mmsi, lat, lon: 20, name: null, imo: null, flag: null, type_group: 'cargo', length_m: null,
  sog_kn: 10, cog_deg: null, heading_deg: 90, last_ts: 0, status: 'active', open_gap_id: null, risk_p: null, risk_rank: null, sanctioned: false, spoof_recent: [] })

const log = new ReplayLog(60 * 60_000, 10_000)
for (let s = 0; s <= 3600; s++) { log.record(s * 1000, v(1, s)); if (s % 2 === 0) log.record(s * 1000, v(2, -s)) }
assert.equal(log.from_ts, 0); assert.equal(log.to_ts, 3600_000)
assert.equal(log.size, 2 * 361)                                   // compacted to one sample per ship per 10 s
const snap = log.snapshotAt(1234_000)
assert.deepEqual(snap.map((x) => [x.mmsi, x.lat]).sort(), [[1, 1230], [2, -1230]])  // last sample at or before t
assert.equal(snap.find((x) => x.mmsi === 1)!.cog, null)           // NaN round-trips as null
assert.deepEqual(log.between(1230_000, 1250_000).map((x) => x.lat), [1250, -1250]) // last per ship
assert.equal(log.snapshotAt(-1).length, 0)
// ring: blocks older than the keep window are dropped, and lookups still work across block boundaries
const big = new ReplayLog(60_000, 0)
for (let i = 0; i < 200_000; i++) big.record(i, v(i % 1000, i))
assert.ok(big.size < 200_000 && big.size >= 60_000, `kept ${big.size}`)
assert.equal(big.snapshotAt(199_999).length, 1000)
assert.equal(big.snapshotAt(199_999).find((x) => x.mmsi === 999)!.lat, 199_999)

const [a, b] = wilson(6, 10)
assert.equal(Math.round(a * 100), 31); assert.equal(Math.round(b * 100), 83)
const [c, d] = wilson(6, 9)
assert.equal(Math.round(c * 100), 35); assert.equal(Math.round(d * 100), 88)
console.log('timeline selfcheck OK')
