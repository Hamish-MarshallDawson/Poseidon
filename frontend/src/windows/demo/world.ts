import type { FeatureCollection } from 'geojson'
import type { Frame } from '../../store/vessels'
import type { DetailMsg } from '../detail'
import type { GapEvent, TypeGroup, VesselView, Watchlist } from '../../types'

// ILLUSTRATIVE DATA for the ?demo=windows harness only: seeded Baltic ships that move along their course, a few
// open gaps ("No AIS received; reception normal nearby"), a ranked watchlist and canned `detail` replies.

const NAMES = ['AURORA BAY', 'NORDIC HAVEN', 'KESTREL', 'BALTIC TERN', 'SVEA STAR', 'MERIDIAN', 'POLAR WIND', 'GOTLAND SPIRIT',
  'IRON GULL', 'ODIN TRADER', 'RIGA DAWN', 'FINN CARRIER', 'AMBER COAST', 'SEA LARK', 'HELMSMAN', 'NORTHERN LIGHT']
const TYPES: TypeGroup[] = ['tanker', 'cargo', 'cargo', 'cargo', 'passenger', 'fishing', 'tug_special', 'pleasure', 'other']
const REASONS = ['RECENT_GAP', 'BLANK_DESTINATION', 'LOITERING', 'FLAG_MISMATCH', 'DRAUGHT_JUMP', 'SANCTIONED']
const FLAGS = ['PA', 'LR', 'MT', 'FI', 'SE', 'EE', 'RU', 'CM', 'GA']

// Rough open-water boxes [lon0, lon1, lat0, lat1]: central Baltic, Bothnian Sea, Gulf of Finland, Gulf of Riga, Kattegat.
const WATER = [[15.5, 20.5, 55, 58], [18.6, 21.2, 60.6, 63.2], [23.5, 28.5, 59.6, 60.1], [21.9, 23.8, 57.4, 58.3], [11.2, 12.2, 56.4, 57.4]]
function inWater(r: () => number) {
  const b = WATER[Math.min(WATER.length - 1, Math.floor(r() * r() * WATER.length * 1.6))]
  return { lon: b[0] + r() * (b[1] - b[0]), lat: b[2] + r() * (b[3] - b[2]) }
}

function rng(seed: number) {
  let s = seed >>> 0
  return () => {
    s = (s + 0x6d2b79f5) >>> 0
    let t = s
    t = Math.imul(t ^ (t >>> 15), t | 1)
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61)
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296
  }
}

export function createDemoWorld(count: number) {
  const r = rng(40)
  let now = Date.now()
  const ships: VesselView[] = []
  const gaps = new Map<string, GapEvent>()
  for (let i = 0; i < count; i++) {
    const mmsi = 230000000 + Math.floor(r() * 49999999)
    const type_group = TYPES[Math.floor(r() * TYPES.length)]
    ships.push({
      mmsi, name: i < NAMES.length ? NAMES[i] : r() < 0.85 ? `VESSEL ${i}` : null, imo: 9000000 + i, flag: FLAGS[i % FLAGS.length],
      type_group, length_m: Math.round(20 + r() * 260),
      ...inWater(r), sog_kn: Math.round(r() * 160) / 10, cog_deg: Math.round(r() * 360),
      heading_deg: r() < 0.9 ? Math.round(r() * 360) : null, last_ts: now - Math.round(r() * 20e3),
      status: 'active', open_gap_id: null, risk_p: null, risk_rank: null, sanctioned: r() < 0.01, spoof_recent: [],
    })
  }
  // The first 40 ships are ranked; ranks 1, 3 and 8 are silent with an open gap.
  const ranked = ships.slice(0, 40).map((v) => ({ v, p: 0.08 + 0.8 * r() })).sort((a, b) => b.p - a.p)
  ranked.forEach(({ v, p }, i) => { v.risk_p = p; v.risk_rank = i + 1 })
  const reasons = new Map(ranked.map(({ v }) => [v.mmsi, REASONS.filter(() => r() < 0.3).slice(0, 2)]))
  for (const rank of [1, 3, 8]) {
    const v = ranked[rank - 1]?.v
    if (!v) continue
    const start = now - Math.round((12 + r() * 50) * 60e3)
    const g: GapEvent = {
      id: `gap-${v.mmsi}`, version: 1, mmsi: v.mmsi, state: 'open', start_ts: start, end_ts: null, duration_s: 0,
      last_lat: v.lat, last_lon: v.lon, last_sog_kn: v.sog_kn, last_cog_deg: v.cog_deg, next_lat: null, next_lon: null,
      neighbours_heard: 9 + Math.floor(r() * 8), neighbours_baseline: 16, cell_id: 'demo', coverage_flag: 'deliberate_candidate',
    }
    gaps.set(g.id, g)
    Object.assign(v, { status: 'gap_open', open_gap_id: g.id, last_ts: start })
  }
  const byMmsi = new Map(ships.map((v) => [v.mmsi, v]))

  const watchlist = (): Watchlist => ({
    snapshot_ts: now,
    entries: ranked.map(({ v, p }, i) => ({
      rank: i + 1, mmsi: v.mmsi, name: v.name, p, decision: i < 5 ? 'inspect' : 'watch', prev_rank: i === 4 ? null : i + 1 + (i % 7 === 2 ? 1 : 0),
      reason_codes: v.open_gap_id ? ['OPEN_GAP', ...reasons.get(v.mmsi)!] : reasons.get(v.mmsi)!,
      evidence: [{ kind: 'score', id: `score-${v.mmsi}`, label: `${Math.round(p * 100)} % · illustrative` }],
    })),
  })
  const gapsNow = () => [...gaps.values()].map((g) => {
    const s = (now - g.start_ts) / 1000
    return { ...g, version: 1 + Math.floor(s / 60), duration_s: Math.floor(s), radius_m: Math.round(500 + (g.last_sog_kn ?? 8) * 0.514 * s * 0.6) }
  })

  return {
    get now() { return now },
    get size() { return ships.length },
    snapshot(): Frame {
      return { type: 'snapshot', now_ts: now, vessels: ships.map((v) => ({ ...v })), removed: [], gaps: gapsNow(), spoofs: [], watchlist: watchlist() }
    },
    // Every heard ship moves one second along its course; silent ships stay at their last fix.
    delta(): Frame {
      now = Date.now()
      const changed: VesselView[] = []
      for (const v of ships) {
        if (v.status !== 'active' || !v.sog_kn) continue
        const d = (v.sog_kn * 0.514) / 111_320
        const c = ((v.cog_deg ?? 0) * Math.PI) / 180
        v.lat += d * Math.cos(c)
        v.lon += (d * Math.sin(c)) / Math.cos((v.lat * Math.PI) / 180)
        v.last_ts = now
        const copy = { ...v }
        byMmsi.set(v.mmsi, copy)
        changed.push(copy)
      }
      return { type: 'delta', now_ts: now, vessels: changed, removed: [], gaps: gapsNow(), spoofs: [], watchlist: watchlist() }
    },
    geojson(): FeatureCollection {
      return { type: 'FeatureCollection', features: ships.map((v) => ({ type: 'Feature', properties: { mmsi: v.mmsi, dark: v.status !== 'active' },
        geometry: { type: 'Point', coordinates: [v.lon, v.lat] } })) }
    },
    detail(mmsi: number): DetailMsg {
      const v = byMmsi.get(mmsi)!
      const past: GapEvent[] = Array.from({ length: mmsi % 4 }, (_, k) => ({
        ...[...gaps.values()][0], id: `past-${mmsi}-${k}`, mmsi, state: 'closed', start_ts: now - (k + 1) * 36 * 3600e3,
        end_ts: now - (k + 1) * 36 * 3600e3 + 40 * 60e3, duration_s: 2400,
      }))
      return { type: 'detail', seq: 0, mmsi, vessel: v, gaps: past, spoofs: [], sanction: null,
        statics: [{ mmsi, name: v.name ?? undefined, flag_iso2: v.flag ?? undefined, length_m: v.length_m ?? undefined, destination: 'PRIMORSK' }],
        score: v.risk_p === null ? null : { id: `score-${mmsi}`, mmsi, made_at: now - 25 * 60e3, as_of: now - 25 * 60e3, horizon_s: 21600,
          target: 'dark_6h', p: v.risk_p, rank: v.risk_rank, mode: 'live', features: {}, contrib: {}, model_version: 'demo-illustrative' } }
    },
  }
}
