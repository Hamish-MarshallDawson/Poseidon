import type { TypeGroup } from '../types'

// Wording and number formats shared by the ship card, watchlist and status line. Neutral wording only.

export const TYPE_LABEL: Record<TypeGroup, string> = {
  tanker: 'Tanker', cargo: 'Cargo', passenger: 'Passenger', fishing: 'Fishing', tug_special: 'Tug or service',
  military: 'Military', pleasure: 'Pleasure craft', other: 'Other', unknown: 'Type not known',
}

// Reason codes in plain words (R2 forecast report). Unknown codes fall back to the code itself.
const REASON: Record<string, string> = {
  OPEN_GAP: 'No AIS now, reception normal nearby',
  RECENT_GAP: 'Silent gap in the last 24 h',
  SPOOF_JUMP: 'Position jumped',
  SPOOF_CIRCLING: 'Circling while reporting at anchor',
  ID_CHANGE: 'Identity changed',
  FLAG_MISMATCH: 'Flag does not match MMSI country',
  SANCTIONED: 'On a sanctions list',
  SHADOW_TAGGED: 'Tagged in shadow-fleet lists',
  DRAUGHT_JUMP: 'Draught changed',
  LOITERING: 'Loitering',
  NEAR_TRANSFER_AREA: 'Near a ship-to-ship transfer area',
  BLANK_DESTINATION: 'No destination',
  HIGH_FORECAST: 'High forecast',
}
export function reasonText(codes: string[]): string {
  return codes.map((c, i) => {
    const t = REASON[c] ?? c
    return i === 0 ? t : t.charAt(0).toLowerCase() + t.slice(1)
  }).join(' · ')
}

// The decision label stays in one map, so a renamed backend value is a one-line change.
export const DECISION_LABEL = { inspect: 'Inspect', watch: 'Watch', none: '' } as const

export const fmtInt = (n: number) => n.toLocaleString('en-GB')
export const fmtMmsi = (m: number) => String(m).replace(/(\d{3})(?=\d)/g, '$1 ')
export const pct = (p: number) => `${Math.round(p * 100)} %`

const pad = (n: number) => String(n).padStart(2, '0')
export function utcTime(ts: number, seconds = true): string {
  const d = new Date(ts)
  return `${pad(d.getUTCHours())}:${pad(d.getUTCMinutes())}${seconds ? `:${pad(d.getUTCSeconds())}` : ''}Z`
}
export function hms(ms: number): string {
  const s = Math.max(0, Math.floor(ms / 1000))
  return `${pad(Math.floor(s / 3600))}:${pad(Math.floor(s / 60) % 60)}:${pad(s % 60)}`
}
export function minutes(ms: number): string {
  const m = Math.max(0, Math.floor(ms / 60000))
  return m < 60 ? `${m} min` : `${Math.floor(m / 60)} h ${pad(m % 60)} min`
}

// Wilson 95 % interval for k of n, as whole percents: every rate on screen carries one (forecast report).
export function wilson(k: number, n: number): [number, number] {
  if (n === 0) return [0, 100]
  const z = 1.96
  const p = k / n
  const d = 1 + (z * z) / n
  const c = (p + (z * z) / (2 * n)) / d
  const h = (z * Math.sqrt((p * (1 - p)) / n + (z * z) / (4 * n * n))) / d
  return [Math.round(Math.max(0, c - h) * 100), Math.round(Math.min(1, c + h) * 100)]
}

// Risk band of p (R2 forecast report): risk/1 10–24 %, risk/2 25–49 %, risk/3 50–74 %, risk/4 75 % and up.
export function riskBand(p: number): 1 | 2 | 3 | 4 | 0 {
  return p >= 0.75 ? 4 : p >= 0.5 ? 3 : p >= 0.25 ? 2 : p >= 0.1 ? 1 : 0
}
