import type { VesselView } from '../../types'
import { headingOf, mercX, mercY, unitsPerMetre } from '../geo'

// Per-ship motion state in typed arrays indexed by a dense slot, updated O(changed) from vessels.subscribe.
// A moving ship dead-reckons along its course from the fix for at most EXTRAP_S (min of 10 min and the backend's
// 30 min stale threshold). The drawn position at arrival of a fix is blended onto that new path: an offset
// (p0 - p1) decays with smoothstep over GLIDE_S. The shader evaluates the same formula per frame; posAt() is the CPU
// copy (used to start the next blend from the drawn position, for hit-testing and for the slot pass).
// Slot fields: (x0,y0) drawn position at arrival, (x1,y1) the fix, t0 arrival time, t1 = t0 + blend length.

export const GLIDE_S = 3
export const EXTRAP_S = 600
const MIN_KN = 0.5
const JUMP = 0.001           // ~40 km in mercator units: farther than that is a jump, not a glide
const KN = 0.514444

export const clock = () => performance.now() / 1000

export class ShipState {
  private n = 0
  private cap: number
  readonly slotOf = new Map<number, number>()
  private free: number[] = []
  view: (VesselView | undefined)[] = []
  mmsi!: Int32Array
  x0!: Float64Array; y0!: Float64Array; x1!: Float64Array; y1!: Float64Array
  vx!: Float32Array; vy!: Float32Array
  t0!: Float64Array; t1!: Float64Array
  h0!: Float32Array; dh!: Float32Array
  hasHeading!: Uint8Array
  reducedMotion = false

  constructor(cap = 32768) { this.cap = cap; this.alloc(cap) }

  get highWater(): number { return this.n }

  private alloc(cap: number) {
    const grow = <T extends Float64Array | Float32Array | Int32Array | Uint8Array>(old: T | undefined, C: new (n: number) => T): T => {
      const a = new C(cap); if (old) a.set(old); return a
    }
    this.mmsi = grow(this.mmsi, Int32Array)
    this.x0 = grow(this.x0, Float64Array); this.y0 = grow(this.y0, Float64Array)
    this.x1 = grow(this.x1, Float64Array); this.y1 = grow(this.y1, Float64Array)
    this.vx = grow(this.vx, Float32Array); this.vy = grow(this.vy, Float32Array)
    this.t0 = grow(this.t0, Float64Array); this.t1 = grow(this.t1, Float64Array)
    this.h0 = grow(this.h0, Float32Array); this.dh = grow(this.dh, Float32Array)
    this.hasHeading = grow(this.hasHeading, Uint8Array)
    this.cap = cap
  }

  // Glide progress 0..1 (no allocation: posAt runs for every ship in the slot pass).
  private ease(s: number, now: number): number {
    const span = this.t1[s] - this.t0[s]
    return span > 0 ? Math.min(1, Math.max(0, (now - this.t0[s]) / span)) : 1
  }

  posAt(s: number, now: number, out: Float64Array | number[]): void {
    const e = this.ease(s, now), k = 1 - e * e * (3 - 2 * e)
    const dt = Math.min(EXTRAP_S, Math.max(0, now - this.t0[s]))
    out[0] = this.x1[s] + (this.x0[s] - this.x1[s]) * k + this.vx[s] * dt
    out[1] = this.y1[s] + (this.y0[s] - this.y1[s]) * k + this.vy[s] * dt
  }

  headingAt(s: number, now: number): number {
    const e = this.ease(s, now)
    return this.h0[s] + this.dh[s] * e * e * (3 - 2 * e)
  }

  // When the drawn motion of a slot ends (for the repaint loop).
  animEnd(s: number): number { return this.vx[s] || this.vy[s] ? this.t0[s] + EXTRAP_S : this.t1[s] }

  private tmp = new Float64Array(2)

  // Returns the slots whose fix moved (callers redraw only those).
  upsert(v: VesselView, now: number): number {
    let s = this.slotOf.get(v.mmsi)
    const x = mercX(v.lon), y = mercY(v.lat)
    const hdg = headingOf(v.heading_deg, v.cog_deg)
    const moving = v.status === 'active' && v.sog_kn != null && v.sog_kn >= MIN_KN && v.cog_deg != null && v.cog_deg < 360
    const upm = unitsPerMetre(v.lat)
    const vx = Math.fround(this.reducedMotion || !moving ? 0 : (v.sog_kn! * KN * Math.sin((v.cog_deg! * Math.PI) / 180)) * upm)
    const vy = Math.fround(this.reducedMotion || !moving ? 0 : -(v.sog_kn! * KN * Math.cos((v.cog_deg! * Math.PI) / 180)) * upm)
    if (s === undefined) {
      s = this.free.pop() ?? this.n++
      if (s >= this.cap) this.alloc(this.cap * 2)
      this.slotOf.set(v.mmsi, s)
      this.mmsi[s] = v.mmsi
      this.x0[s] = this.x1[s] = x; this.y0[s] = this.y1[s] = y
      this.t0[s] = this.t1[s] = now
      this.h0[s] = hdg ?? 0; this.dh[s] = 0
    } else if (x !== this.x1[s] || y !== this.y1[s]) {
      const p = this.tmp
      this.posAt(s, now, p)
      const h = this.headingAt(s, now)
      const jump = Math.abs(x - p[0]) > JUMP || Math.abs(y - p[1]) > JUMP
      this.x0[s] = jump ? x : p[0]; this.y0[s] = jump ? y : p[1]
      this.x1[s] = x; this.y1[s] = y
      this.t0[s] = now; this.t1[s] = now + (this.reducedMotion || jump ? 0 : GLIDE_S)
      this.h0[s] = ((h % 360) + 360) % 360
      this.dh[s] = hdg == null ? 0 : ((hdg - this.h0[s] + 540) % 360) - 180
      if (this.reducedMotion || jump) { this.h0[s] = hdg ?? this.h0[s]; this.dh[s] = 0 }
    } else if (vx !== this.vx[s] || vy !== this.vy[s]) {
      // same fix position but new speed or course: continue from where the ship is drawn
      const p = this.tmp
      this.posAt(s, now, p)
      this.x0[s] = this.x1[s] = p[0]; this.y0[s] = this.y1[s] = p[1]
      this.t0[s] = this.t1[s] = now
    } else if (hdg != null && !this.vx[s] && !this.vy[s] && now >= this.t1[s]) {
      // heading-only change at a standstill: turn on the spot
      const h = ((this.headingAt(s, now) % 360) + 360) % 360
      const d = ((hdg - h + 540) % 360) - 180
      if (Math.abs(d) > 0.5) {
        this.t0[s] = now; this.t1[s] = now + (this.reducedMotion ? 0 : GLIDE_S)
        this.x0[s] = this.x1[s]; this.y0[s] = this.y1[s]
        this.h0[s] = this.reducedMotion ? hdg : h; this.dh[s] = this.reducedMotion ? 0 : d
      }
    }
    this.vx[s] = vx; this.vy[s] = vy
    this.hasHeading[s] = hdg == null ? 0 : 1
    this.view[s] = v
    return s
  }

  clear(): void {
    this.n = 0; this.free.length = 0; this.slotOf.clear(); this.view.length = 0
  }

  remove(mmsi: number): void {
    const s = this.slotOf.get(mmsi)
    if (s === undefined) return
    this.slotOf.delete(mmsi)
    this.view[s] = undefined
    this.free.push(s)
  }
}
