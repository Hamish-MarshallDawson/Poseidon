// Pure scale and tick helpers for the Lab charts (no DOM). Times are epoch ms, shown in UTC.

export type Domain = [number, number]

export interface Scale {
  (v: number): number
  domain: Domain
  range: Domain
  invert(px: number): number
}

/** Linear map from domain to range; a zero-width domain maps everything to the middle of the range. */
export function linear(domain: Domain, range: Domain): Scale {
  const [d0, d1] = domain
  const [r0, r1] = range
  const span = d1 - d0
  const f = ((v: number) => (span === 0 ? (r0 + r1) / 2 : r0 + ((v - d0) / span) * (r1 - r0))) as Scale
  f.domain = domain
  f.range = range
  f.invert = (px) => (r1 === r0 ? d0 : d0 + ((px - r0) / (r1 - r0)) * span)
  return f
}

export interface BandScale {
  (key: string): number          // start of the band
  bandwidth: number
  domain: string[]
  range: Domain
}

/** Categories spread evenly over the range, `pad` (0..1) of each step left empty. */
export function band(domain: string[], range: Domain, pad = 0.25): BandScale {
  const n = Math.max(domain.length, 1)
  const step = (range[1] - range[0]) / n
  const idx = new Map(domain.map((k, i) => [k, i]))
  const f = ((k: string) => range[0] + (idx.get(k) ?? 0) * step + (step * pad) / 2) as BandScale
  f.bandwidth = step * (1 - pad)
  f.domain = domain
  f.range = range
  return f
}

/** Min and max of the finite values, or `fallback` when there are none. */
export function extent(values: Iterable<number | null | undefined>, fallback: Domain = [0, 1]): Domain {
  let lo = Infinity
  let hi = -Infinity
  for (const v of values) {
    if (v == null || !Number.isFinite(v)) continue
    if (v < lo) lo = v
    if (v > hi) hi = v
  }
  return lo === Infinity ? fallback : [lo, hi]
}

/** Widen a domain by `frac` of its span on each side (a flat domain gets ±frac, or ±1 at zero). */
export function pad(d: Domain, frac = 0.08): Domain {
  const span = d[1] - d[0]
  const p = span === 0 ? Math.abs(d[0]) * frac || 1 : span * frac
  return [d[0] - p, d[1] + p]
}

/** About `count` round ticks (1, 2, 2.5, 5 × 10^k) inside the domain. */
export function niceTicks(d: Domain, count = 5): number[] {
  const [lo, hi] = d[0] <= d[1] ? d : [d[1], d[0]]
  if (hi === lo) return [lo]
  const raw = (hi - lo) / Math.max(count, 1)
  const mag = 10 ** Math.floor(Math.log10(raw))
  const step = [1, 2, 2.5, 5, 10].map((m) => m * mag).find((s) => s >= raw) ?? 10 * mag
  const out: number[] = []
  for (let v = Math.ceil(lo / step) * step; v <= hi + step * 1e-9; v += step) out.push(Math.abs(v) < step * 1e-9 ? 0 : +v.toPrecision(12))
  return out
}

const MIN = 60_000
const HOUR = 60 * MIN
const DAY = 24 * HOUR
const TIME_STEPS = [5 * MIN, 15 * MIN, 30 * MIN, HOUR, 3 * HOUR, 6 * HOUR, 12 * HOUR, DAY, 2 * DAY, 7 * DAY, 14 * DAY]
const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']

/** About `count` UTC-aligned time ticks: minutes to weeks, then whole months, then whole years. */
export function timeTicks(d: Domain, count = 5): number[] {
  const [lo, hi] = d[0] <= d[1] ? d : [d[1], d[0]]
  if (hi === lo) return [lo]
  const raw = (hi - lo) / Math.max(count, 1)
  const step = TIME_STEPS.find((s) => s >= raw)
  if (step) {
    const out: number[] = []
    for (let t = Math.ceil(lo / step) * step; t <= hi; t += step) out.push(t)
    return out
  }
  const out: number[] = []
  const months = [1, 2, 3, 6].find((m) => m * 30 * DAY >= raw)
  const start = new Date(lo)
  if (months) {
    for (let i = start.getUTCFullYear() * 12 + start.getUTCMonth(); ; i++) {
      const t = Date.UTC(Math.floor(i / 12), i % 12, 1)
      if (t > hi) break
      if (t >= lo && (i % 12) % months === 0) out.push(t)
    }
    return out
  }
  const years = [1, 2, 5, 10, 20, 50].find((y) => y * 365 * DAY >= raw) ?? 100
  for (let y = start.getUTCFullYear(); ; y++) {
    const t = Date.UTC(y, 0, 1)
    if (t > hi) break
    if (t >= lo && y % years === 0) out.push(t)
  }
  return out
}

const p2 = (n: number) => String(n).padStart(2, '0')

/** A tick label that fits the tick spacing: "08:00", "8 Nov", "Nov 2026" or "2026" (UTC). */
export function timeLabel(t: number, spacing: number): string {
  const d = new Date(t)
  if (spacing < DAY) return `${p2(d.getUTCHours())}:${p2(d.getUTCMinutes())}`
  if (spacing < 28 * DAY) return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}`
  if (spacing < 360 * DAY) return `${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`
  return String(d.getUTCFullYear())
}

/** "8 Nov 08:25 UTC" style full timestamp for tooltips. */
export function timeFull(t: number): string {
  const d = new Date(t)
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()} ${p2(d.getUTCHours())}:${p2(d.getUTCMinutes())} UTC`
}

/** Default number label: percent for share-like values when `percent`, else compact. */
export function numLabel(v: number, percent = false): string {
  if (percent) return `${Math.round(v * 100)}%`
  const a = Math.abs(v)
  if (a >= 1e6) return `${+(v / 1e6).toFixed(1)}M`
  if (a >= 1e4) return `${+(v / 1e3).toFixed(0)}k`
  if (a >= 1e3) return `${+(v / 1e3).toFixed(1)}k`
  if (a === 0 || a >= 1) return `${+v.toFixed(2)}`
  return `${+v.toPrecision(2)}`
}
