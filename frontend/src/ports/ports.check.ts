// Self-check for port matching and departure inference. Run: node --experimental-strip-types src/ports/ports.check.ts
import { buildIndex, fmtEta, inferDeparture, matchDestination } from './match.ts'
import type { PortRow, Track } from './match.ts'

function check(cond: boolean, msg: string) {
  if (!cond) throw new Error(`ports.check: ${msg}`)
}

const rows: PortRow[] = [
  ['Stockholm', 'SE', 'SESTO', 59.33, 18.05], ['Helsinki', 'FI', 'FIHEL', 60.17, 24.93],
  ['Göteborg', 'SE', 'SEGOT', 57.72, 11.97], ['Gdansk', 'PL', 'PLGDN', 54.4, 18.67],
  ['Rotterdam', 'NL', 'NLRTM', 51.92, 4.5], ['Rotterdam', 'US', 'USRAJ', 42.78, -73.97],
]
const idx = buildIndex(rows)
const m = (s: string, near?: [number, number]) => matchDestination(s, idx, near)

for (const s of ['SE STO', 'SESTO', 'SE-STO', 'se sto ']) check(m(s)?.port.name === 'Stockholm' && m(s)?.how === 'locode', `locode ${s}`)
check(m('FIHEL')?.port.name === 'Helsinki', 'FIHEL')
check(m('SEGOT>FIHEL')?.port.name === 'Helsinki', 'last of a > chain')
check(m('GDANSK')?.how === 'name', 'plain name')
check(m('GDANSK PL')?.port.name === 'Gdansk', 'name with country')
check(m('GOTEBORG')?.port.name === 'Göteborg', 'diacritics folded')
check(m('PORT OF STOCKHOLM')?.port.name === 'Stockholm', 'noise word')
check(m('FOR ORDERS') === null && m('') === null && m('???') === null, 'no match')
check(m('ROTTERDAM') === null, 'ambiguous name without a position stays unmatched')
check(m('ROTTERDAM', [52, 4])?.port.cc === 'NL', 'ambiguous name resolved by position')

// A ship parked 40 min at Gdansk, then sailing east at ~0.1 deg per minute-ish; one point a minute.
const T0 = Date.UTC(2026, 10, 8, 10, 0)
const track: Track = []
for (let i = 0; i < 40; i++) track.push([T0 + i * 60e3, 18.67, 54.4])
for (let i = 40; i < 80; i++) track.push([T0 + i * 60e3, 18.67 + (i - 39) * 0.01, 54.4])
const d = inferDeparture(track, idx)
check(d?.port.name === 'Gdansk' && d.leftTs === T0 + 40 * 60e3, 'departure from the last stop')
check(inferDeparture(track.slice(40), idx) === null, 'no stop in a moving track')
check(inferDeparture(track.slice(0, 40), idx) === null, 'still moored: no departure yet')
check(inferDeparture(track.slice(0, 15), idx) === null, 'stop shorter than 20 min')
const sea: Track = track.map(([t, lo, la]) => [t, lo - 2, la + 1])   // same shape, no port within 5 km
check(inferDeparture(sea, idx) === null, 'stop away from any port')

check(fmtEta('2026-11-08T14:00:00Z') === '8 Nov 14:00Z', 'eta format')
check(fmtEta('soon') === null, 'bad eta')
console.log('ports.check: ok')
