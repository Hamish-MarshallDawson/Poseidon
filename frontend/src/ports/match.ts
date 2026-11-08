// Pure port logic: matching AIS destination text and inferring a departure port from a past track. No browser APIs,
// so ports.check.ts runs under plain node.

export type PortRow = [name: string, iso2: string, locode: string, lat: number, lon: number]
export interface Port { name: string; cc: string; locode: string; lat: number; lon: number }
export type Track = [number, number, number][]   // [ts, lon, lat], oldest first

export interface PortIndex { all: Port[]; byLocode: Map<string, Port>; byName: Map<string, Port[]> }

const plain = (s: string) => s.normalize('NFD').replace(/\p{M}/gu, '').toUpperCase()

export function buildIndex(rows: PortRow[]): PortIndex {
  const all = rows.map(([name, cc, locode, lat, lon]): Port => ({ name, cc, locode, lat, lon }))
  const byLocode = new Map<string, Port>()
  const byName = new Map<string, Port[]>()
  for (const p of all) {
    if (p.locode) byLocode.set(p.locode, p)
    const k = plain(p.name)
    byName.set(k, [...(byName.get(k) ?? []), p])
  }
  return { all, byLocode, byName }
}

const NOISE = /\b(PORT OF|PORT|PORTS|ANCHORAGE|ROADS|ROADSTEAD|OPL|OPA|ANCH|FOR ORDERS?|ORDERS?|ETA|TBA|TBN|TBC)\b/g
const km = (a: Port, lat: number, lon: number) =>
  Math.hypot((a.lat - lat) * 111.2, (a.lon - lon) * 111.2 * Math.cos((lat * Math.PI) / 180))

// `near` (the ship's [lat, lon]) breaks ties between same-name ports in different countries; without it an
// ambiguous bare name stays unmatched rather than guessing.
export function matchDestination(raw: string, idx: PortIndex, near?: [number, number]): { port: Port; how: 'locode' | 'name' } | null {
  const last = plain(raw).split(/>|<|=|\bTO\b/).map((s) => s.trim()).filter(Boolean).pop()
  if (!last) return null
  const code = last.replace(/[\s\-_.]/g, '')
  const byCode = /^[A-Z]{2}[A-Z2-9]{3}$/.test(code) ? idx.byLocode.get(code) : undefined
  if (byCode) return { port: byCode, how: 'locode' }

  let name = last.replace(NOISE, ' ').replace(/[^A-Z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim()
  let cc = ''
  const m = /^(.*\S) ([A-Z]{2})$/.exec(name)   // "GDANSK PL"
  if (m && !idx.byName.has(name)) { name = m[1]; cc = m[2] }
  const hits = (idx.byName.get(name) ?? []).filter((p) => !cc || p.cc === cc)
  if (hits.length === 1) return { port: hits[0], how: 'name' }
  if (hits.length > 1 && near) return { port: hits.reduce((a, b) => (km(a, ...near) <= km(b, ...near) ? a : b)), how: 'name' }
  return null
}

const STOP_M = 150
const STOP_MS = 20 * 60e3
const PORT_KM = 5

// The most recent stop (>= 20 min within 150 m of where it began) that sits within 5 km of a port, and when the ship
// left it. A stop still going at the end of the track has no departure yet and is skipped, as is one at sea.
export function inferDeparture(track: Track, idx: PortIndex): { port: Port; leftTs: number } | null {
  const stops: { j: number; lat: number; lon: number }[] = []
  for (let i = 0; i < track.length; ) {
    let j = i
    while (j + 1 < track.length && km({ lat: track[i][2], lon: track[i][1] } as Port, track[j + 1][2], track[j + 1][1]) * 1000 <= STOP_M) j++
    if (j > i && track[j][0] - track[i][0] >= STOP_MS) { stops.push({ j, lat: track[i][2], lon: track[i][1] }); i = j + 1 } else i++
  }
  for (const s of stops.reverse()) {
    if (s.j >= track.length - 1) continue
    let best: Port | null = null, bd = PORT_KM
    for (const p of idx.all) { const d = km(p, s.lat, s.lon); if (d <= bd) { best = p; bd = d } }
    if (best) return { port: best, leftTs: track[s.j + 1][0] }
  }
  return null
}

// "20261108T1400" / ISO -> "8 Nov 14:00Z"; null when it doesn't parse.
export function fmtEta(eta: string): string | null {
  const t = Date.parse(eta)
  if (Number.isNaN(t)) return null
  const d = new Date(t)
  const p = (n: number) => String(n).padStart(2, '0')
  return `${d.getUTCDate()} ${d.toLocaleString('en-GB', { month: 'short', timeZone: 'UTC' })} ${p(d.getUTCHours())}:${p(d.getUTCMinutes())}Z`
}
