import type { Proposer, Source } from './types'

// Plain-words formatting for the Lab. Times in UTC (the team's notes and the server's logs are in UTC).

const MONTHS = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec']
const p2 = (n: number) => String(n).padStart(2, '0')

/** "8 Nov 08:25 UTC"; the year only when it isn't this year. */
export function when(t: number | null | undefined, now = Date.now()): string {
  if (t == null) return 'unknown time'
  const d = new Date(t)
  const y = d.getUTCFullYear() !== new Date(now).getUTCFullYear() ? ` ${d.getUTCFullYear()}` : ''
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]}${y} ${p2(d.getUTCHours())}:${p2(d.getUTCMinutes())} UTC`
}

/** "8 Nov 2026" */
export function day(t: number | null | undefined): string {
  if (t == null) return 'unknown'
  const d = new Date(t)
  return `${d.getUTCDate()} ${MONTHS[d.getUTCMonth()]} ${d.getUTCFullYear()}`
}

/** A horizon in seconds as "30 min", "3 h", "7 d". */
export function horizon(s: number | string): string {
  const n = Number(s)
  if (n % 86400 === 0 && n >= 86400) return `${n / 86400} d`
  if (n % 3600 === 0 && n >= 3600) return `${n / 3600} h`
  return `${Math.round(n / 60)} min`
}

/** Signed percent: 0.624 -> "+62%", -0.057 -> "−5.7%" (one decimal under 10%). */
export function signedPct(x: number | null | undefined): string {
  if (x == null || !Number.isFinite(x)) return 'n/a'
  const v = Math.abs(x * 100)
  const s = v < 10 && v !== 0 ? v.toFixed(1) : v.toFixed(0)
  return `${x < 0 ? '−' : '+'}${s}%`
}

export function pct(x: number | null | undefined, digits = 0): string {
  if (x == null || !Number.isFinite(x)) return 'n/a'
  return `${(x * 100).toFixed(digits)}%`
}

export function count(n: number | null | undefined): string {
  return n == null ? 'n/a' : n.toLocaleString('en-GB')
}

/** "[+26%, +31%]" or null when the run recorded no interval. */
export function interval(lo: number | null | undefined, hi: number | null | undefined): string | null {
  return lo == null || hi == null ? null : `[${signedPct(lo)}, ${signedPct(hi)}]`
}

export const PROPOSER: Record<Proposer, string> = { human: 'set by hand', default: 'default search', gemini: 'proposed by Gemini' }
export const SOURCE: Record<string, string> = { 'pc-aiden': "Aiden's PC", 'desktop-hamish': "Hamish's desktop", server: 'the server' }
export const proposerLabel = (p: Proposer | null | undefined) => (p ? PROPOSER[p] ?? p : 'unknown')
export const sourceLabel = (s: Source | null | undefined) => (s ? SOURCE[s] ?? s : 'unknown')

/** What each model's skill is measured against. Fishing's baseline is the historical rate per gear type and flag,
 * shrunk towards the overall rate where a group is small. */
export const BASELINE: Record<string, string> = { route: 'dead reckoning', godark: 'the base rate', godark_gfw: 'the base rate', fishing: 'the rate by gear type and flag' }
export const baselineOf = (target: string) => BASELINE[target] ?? 'the baseline'

/** A calibration value: a percent for coverage-style checks, else three decimals. */
export function calValue(name: string, v: number | null | undefined): string {
  if (v == null || !Number.isFinite(v)) return 'n/a'
  return /coverage|circle|%/.test(name) ? pct(v) : v.toFixed(3)
}
