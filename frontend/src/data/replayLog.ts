import type { VesselView } from '../types'

// Session replay buffer for the mock: every live position, compacted to one sample per ship per 10 s, kept for 60 min.
// Columnar typed blocks, 32 bytes a sample (t Float64, mmsi Uint32, lat/lon/sog/cog/hdg Float32, ~2 m precision), never
// allocating per sample: a 25,000-ship feed over the 60 min window is about 9 M samples, ~290 MB at worst.
// Samples are appended in frame order, so the time column is sorted and range lookups are binary searches.
const BLOCK = 1 << 16
const F = 5 // lat, lon, sog, cog, hdg   (NaN = null)
interface Block { t: Float64Array; m: Uint32Array; f: Float32Array }
export const LOOKBACK_MS = 30 * 60_000   // a snapshot shows each ship's last position in the 30 min before t (as the server)

export interface Sample { mmsi: number; t: number; lat: number; lon: number; sog: number | null; cog: number | null; hdg: number | null }

export class ReplayLog {
  private blocks: Block[] = []
  private base = 0        // global index of blocks[0][0]
  private end = 0         // global index one past the last sample
  private lastRec = new Map<number, number>()
  readonly keepMs: number
  readonly minStepMs: number
  constructor(keepMs = 60 * 60_000, minStepMs = 10_000) { this.keepMs = keepMs; this.minStepMs = minStepMs }

  get size() { return this.end - this.base }
  get from_ts() { return this.size ? this.ts(this.base) : null }
  get to_ts() { return this.size ? this.ts(this.end - 1) : null }

  record(t: number, v: VesselView): void {
    const prev = this.lastRec.get(v.mmsi)
    if (prev !== undefined && t - prev < this.minStepMs) return
    this.lastRec.set(v.mmsi, t)
    const off = (this.end - this.base) % BLOCK
    if (this.end - this.base === this.blocks.length * BLOCK) {
      this.blocks.push({ t: new Float64Array(BLOCK), m: new Uint32Array(BLOCK), f: new Float32Array(BLOCK * F) })
    }
    const b = this.blocks[Math.floor((this.end - this.base) / BLOCK)]
    const i = off * F
    b.t[off] = t; b.m[off] = v.mmsi
    b.f[i] = v.lat; b.f[i + 1] = v.lon; b.f[i + 2] = v.sog_kn ?? NaN; b.f[i + 3] = v.cog_deg ?? NaN; b.f[i + 4] = v.heading_deg ?? NaN
    this.end++
    // drop whole blocks that ended before the keep window
    while (this.blocks.length > 1 && this.ts(this.base + BLOCK - 1) < t - this.keepMs) { this.blocks.shift(); this.base += BLOCK }
  }

  // Last sample per ship with t in (t0, t1], in time order of their last sample.
  between(t0: number, t1: number): Sample[] {
    const last = new Map<number, number>()
    for (let g = this.firstAfter(t0); g < this.end && this.ts(g) <= t1; g++) last.set(this.at(g).m[(g - this.base) % BLOCK], g)
    return [...last.values()].map((g) => this.sample(g))
  }

  // What the server sends on seek: the last position per ship in the LOOKBACK before t.
  snapshotAt(t: number): Sample[] { return this.between(t - LOOKBACK_MS, t) }

  private firstAfter(t: number): number {
    let lo = this.base, hi = this.end
    while (lo < hi) { const mid = (lo + hi) >> 1; if (this.ts(mid) <= t) lo = mid + 1; else hi = mid }
    return lo
  }
  private at(g: number): Block { return this.blocks[Math.floor((g - this.base) / BLOCK)] }
  private ts(g: number): number { return this.at(g).t[(g - this.base) % BLOCK] }
  private sample(g: number): Sample {
    const b = this.at(g), k = (g - this.base) % BLOCK, i = k * F
    const n = (x: number) => (Number.isNaN(x) ? null : x)
    return { t: b.t[k], mmsi: b.m[k], lat: b.f[i], lon: b.f[i + 1], sog: n(b.f[i + 2]), cog: n(b.f[i + 3]), hdg: n(b.f[i + 4]) }
  }
}
