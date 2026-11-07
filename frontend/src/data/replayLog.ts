import type { VesselView } from '../types'

// Session replay buffer for the mock: every live position, compacted to one sample per ship per 10 s, kept for 60 min.
// Columnar Float64 blocks so 25,000 ships x 360 samples stay around 60 MB and never allocate per sample.
// Samples are appended in frame order, so the time column is sorted and range lookups are binary searches.
const BLOCK = 1 << 16
const COLS = 7 // t (frame now_ts), mmsi, lat, lon, sog, cog, hdg   (NaN = null)
export const LOOKBACK_MS = 30 * 60_000   // a snapshot shows each ship's last position in the 30 min before t (as the server)

export interface Sample { mmsi: number; t: number; lat: number; lon: number; sog: number | null; cog: number | null; hdg: number | null }

export class ReplayLog {
  private blocks: Float64Array[] = []
  private base = 0        // global index of blocks[0][0]
  private end = 0         // global index one past the last sample
  private lastRec = new Map<number, number>()
  readonly keepMs: number
  readonly minStepMs: number
  constructor(keepMs = 60 * 60_000, minStepMs = 10_000) { this.keepMs = keepMs; this.minStepMs = minStepMs }

  get size() { return this.end - this.base }
  get from_ts() { return this.size ? this.col(this.base, 0) : null }
  get to_ts() { return this.size ? this.col(this.end - 1, 0) : null }

  record(t: number, v: VesselView): void {
    const prev = this.lastRec.get(v.mmsi)
    if (prev !== undefined && t - prev < this.minStepMs) return
    this.lastRec.set(v.mmsi, t)
    const off = (this.end - this.base) % BLOCK
    if (this.end - this.base === this.blocks.length * BLOCK) this.blocks.push(new Float64Array(BLOCK * COLS))
    const b = this.blocks[Math.floor((this.end - this.base) / BLOCK)]
    const i = off * COLS
    b[i] = t; b[i + 1] = v.mmsi; b[i + 2] = v.lat; b[i + 3] = v.lon
    b[i + 4] = v.sog_kn ?? NaN; b[i + 5] = v.cog_deg ?? NaN; b[i + 6] = v.heading_deg ?? NaN
    this.end++
    // drop whole blocks that ended before the keep window
    while (this.blocks.length > 1 && this.col(this.base + BLOCK - 1, 0) < t - this.keepMs) { this.blocks.shift(); this.base += BLOCK }
  }

  // Last sample per ship with t in (t0, t1], in time order of their last sample.
  between(t0: number, t1: number): Sample[] {
    const last = new Map<number, number>()
    for (let g = this.firstAfter(t0); g < this.end && this.col(g, 0) <= t1; g++) last.set(this.col(g, 1), g)
    return [...last.values()].map((g) => this.sample(g))
  }

  // What the server sends on seek: the last position per ship in the LOOKBACK before t.
  snapshotAt(t: number): Sample[] { return this.between(t - LOOKBACK_MS, t) }

  private firstAfter(t: number): number {
    let lo = this.base, hi = this.end
    while (lo < hi) { const mid = (lo + hi) >> 1; if (this.col(mid, 0) <= t) lo = mid + 1; else hi = mid }
    return lo
  }
  private col(g: number, c: number): number {
    const k = g - this.base
    return this.blocks[Math.floor(k / BLOCK)][(k % BLOCK) * COLS + c]
  }
  private sample(g: number): Sample {
    const n = (c: number) => { const x = this.col(g, c); return Number.isNaN(x) ? null : x }
    return { t: this.col(g, 0), mmsi: this.col(g, 1), lat: this.col(g, 2), lon: this.col(g, 3), sog: n(4), cog: n(5), hdg: n(6) }
  }
}
