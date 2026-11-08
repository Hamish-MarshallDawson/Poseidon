// MOCK ship feed for machines without the backend (only Hamish's desktop runs it). The mock adapter switches to this
// when the backend does not answer within a few seconds (VITE_DATA=mock) or at once (VITE_DATA=offline). It behaves
// like data/live.ts: hello/status, one snapshot, then a delta every second with the ships that reported (each ship
// reports every 10 s moving, 60 s at anchor, like AIS). Positions are a pure function of time, so backfill() can hand
// the replay log the last minutes before the session started. Everything it makes is labelled "Illustrative data".
import type { ClientMsg, HistoryRange, StaticDetail, TypeGroup, VesselView } from '../types'
import type { DataAdapter, FeedHandlers, FeedStatus } from './adapter'

// Mostly-water boxes [w, s, e, n, weight]; the Baltic boxes are heavy so the mock forecast finds its 40 ships there.
const SEAS: [number, number, number, number, number][] = [
  [16, 54.6, 20.5, 58.2, 9], [22.5, 59.4, 28.5, 60.2, 4], [18, 60.8, 21, 63.2, 3], [10.8, 54.3, 12.6, 55.6, 2], // Baltic
  [1.5, 52.5, 6.5, 57.5, 8], [-5, 49.3, 1, 50.4, 5], [-11, 36, -6, 50, 6],                                      // N Sea, Channel, Biscay
  [3, 36.5, 15, 41, 6], [17, 31.5, 28, 35.5, 5], [28, 40.3, 29.5, 41.3, 1],                                     // Med, Bosporus
  [-40, 20, -15, 45, 5], [-75, 30, -55, 40, 4], [32.3, 12, 43, 27, 4], [55, 22, 66, 26, 4],                    // Atlantic, Red Sea, Arabian Sea
  [72, 5, 90, 15, 4], [104, 1, 105.5, 1.5, 3], [108, 5, 118, 20, 8], [119, 25, 125, 32, 7],                     // Indian Ocean, Singapore, SCS, E China Sea
  [130, 30, 150, 40, 4], [-160, 20, -125, 45, 4], [-80, -40, -74, -5, 2], [-48, -35, -38, -23, 3],              // Japan, N Pacific, S America
  [140, -40, 155, -30, 2], [-95, 19, -84, 28, 4],                                                               // Tasman, Gulf of Mexico
]
const TYPES: TypeGroup[] = ['cargo', 'cargo', 'cargo', 'tanker', 'tanker', 'passenger', 'fishing', 'fishing', 'tug_special', 'pleasure', 'other', 'unknown']
const FLAGS = ['PA', 'LR', 'MT', 'MH', 'BS', 'CY', 'GR', 'NO', 'DK', 'FI', 'SE', 'DE', 'NL', 'GB', 'SG', 'CN', 'JP', 'RU', 'EE', 'LV']
const W1 = ['AURORA', 'NORDIC', 'BALTIC', 'SEA', 'POLAR', 'GOLDEN', 'SILVER', 'NORTHERN', 'OCEAN', 'STAR', 'BLUE', 'EAST']
const W2 = ['BAY', 'SPIRIT', 'TRADER', 'WIND', 'GRACE', 'PEARL', 'PRIDE', 'HAWK', 'QUEEN', 'RIVER', 'LIGHT', 'VOYAGER']
const LEG_MS = 2 * 3_600_000          // ships sail out and back along their course over this period
const SEC = 1000

function h01(a: number, b: number): number {
  let x = (a % 2147483647) ^ Math.imul(b | 0, 0x9e3779b1)
  x = Math.imul(x ^ (x >>> 16), 0x85ebca6b); x = Math.imul(x ^ (x >>> 13), 0xc2b2ae35)
  return ((x ^ (x >>> 16)) >>> 0) / 4294967296
}

interface Ship { mmsi: number; lat0: number; lon0: number; sog: number; cog: number; phase: number; every: number; base: VesselView }

function makeShips(n: number): Ship[] {
  const total = SEAS.reduce((s, b) => s + b[4], 0)
  const ships: Ship[] = []
  for (let i = 0; i < n; i++) {
    const mmsi = 200_000_000 + Math.floor(h01(i, 1) * 575_000_000)
    let pick = h01(i, 2) * total, box = SEAS[0]
    for (const b of SEAS) { pick -= b[4]; if (pick <= 0) { box = b; break } }
    const lat0 = box[1] + (box[3] - box[1]) * h01(i, 3), lon0 = box[0] + (box[2] - box[0]) * h01(i, 4)
    const anchored = h01(i, 5) < 0.15
    const sog = anchored ? 0 : 6 + 12 * h01(i, 6)
    const type_group = TYPES[Math.floor(h01(i, 7) * TYPES.length)]
    const base: VesselView = {
      mmsi, name: `${W1[Math.floor(h01(i, 8) * W1.length)]} ${W2[Math.floor(h01(i, 9) * W2.length)]}`, imo: null,
      flag: FLAGS[Math.floor(h01(i, 10) * FLAGS.length)], type_group, length_m: Math.round(20 + 280 * h01(i, 11) ** 2),
      lat: lat0, lon: lon0, sog_kn: null, cog_deg: null, heading_deg: null, last_ts: 0, status: 'active', open_gap_id: null,
      risk_p: null, risk_rank: null, sanctioned: h01(i, 12) < 0.004, spoof_recent: [], cls: h01(i, 15) < 0.7 ? 'A' : 'B',
    }
    ships.push({ mmsi, lat0, lon0, sog, cog: 360 * h01(i, 13), phase: LEG_MS * h01(i, 14), every: anchored ? 60 : 10, base })
  }
  return ships
}

// Position at t: dead reckoning along cog, out and back (triangle wave) so ships stay in their sea.
function at(s: Ship, t: number): VesselView {
  const u = ((t + s.phase) % LEG_MS) / LEG_MS
  const out = u < 0.5
  const dist = s.sog * 0.514444 * (LEG_MS / SEC) * (out ? u : 1 - u)          // metres from the start
  const rad = (s.cog * Math.PI) / 180
  const lat = s.lat0 + (dist * Math.cos(rad)) / 111_320
  const lon = s.lon0 + (dist * Math.sin(rad)) / (111_320 * Math.cos((s.lat0 * Math.PI) / 180))
  const cog = s.sog ? (out ? s.cog : (s.cog + 180) % 360) : null
  return { ...s.base, lat, lon, sog_kn: Math.round(s.sog * 10) / 10, cog_deg: cog, heading_deg: cog ?? Math.round(s.cog), last_ts: t }
}

const reports = (s: Ship, sec: number) => (sec + (s.mmsi % s.every)) % s.every === 0

export interface SyntheticFeed extends DataAdapter {
  // The positions each ship reported in [from, to), oldest first, for the replay log (call before start()).
  backfill(from: number, to: number, record: (t: number, v: VesselView) => void): void
}

export function createSyntheticFeed(count = 25_000): SyntheticFeed {
  const ships = makeShips(count)
  const byMmsi = new Map(ships.map((s) => [s.mmsi, s]))
  let timer: number | undefined
  let h: FeedHandlers | null = null
  const status = (now: number, msgs: number): FeedStatus => ({
    connected: true, mode: 'live', speed: 1, paused: false, now_ts: now, replay: null,
    sources: [{ src: 'mock', state: 'up', msgs_per_s: msgs }], stats: { tracked: ships.length, msgs_per_s: msgs, queue_depth: 0 },
  })

  return {
    isMock: true,
    backfill(from, to, record) {
      for (let t = Math.ceil(from / SEC) * SEC; t < to; t += SEC) {
        const sec = Math.floor(t / SEC)
        for (const s of ships) if (reports(s, sec)) record(t, at(s, t))
      }
    },
    start(handlers) {
      h = handlers
      const now = Math.floor(Date.now() / SEC) * SEC
      h.onStatus(status(now, 0))
      h.onFrame({ type: 'snapshot', now_ts: now, vessels: ships.map((s) => at(s, now)), removed: [], gaps: [], spoofs: [], watchlist: null, trails: {}, coverage: [] })
      const tick = () => {
        const t = Math.floor(Date.now() / SEC) * SEC
        const sec = t / SEC
        const vs = ships.filter((s) => reports(s, sec)).map((s) => at(s, t))
        h?.onFrame({ type: 'delta', now_ts: t, vessels: vs, removed: [], gaps: [], spoofs: [], watchlist: null })
        h?.onStatus(status(t, vs.length))
      }
      timer = window.setInterval(tick, SEC)
    },
    stop() { window.clearInterval(timer); timer = undefined; h = null },
    send(msg: ClientMsg) {
      if (msg.type !== 'detail' || !h) return
      const s = byMmsi.get(msg.mmsi)
      if (!s) return
      const v = at(s, Date.now())
      const statics: StaticDetail = { mmsi: v.mmsi, name: v.name ?? undefined, type_group: v.type_group, length_m: v.length_m ?? undefined,
        flag_iso2: v.flag ?? undefined, destination: 'ILLUSTRATIVE' }
      const handlers = h
      window.setTimeout(() => handlers.onDetail({ type: 'detail', seq: 0, mmsi: v.mmsi, vessel: v, statics: [statics], gaps: [], spoofs: [], sanction: null, score: null }), 80)
    },
    // No server log: the mock falls back to its own replay log's range (which includes the backfill).
    historyRange: (): Promise<HistoryRange> => Promise.reject(new Error('synthetic feed has no history log')),
    timeline: () => Promise.reject(new Error('synthetic feed has no timeline')),
    track: () => Promise.reject(new Error('synthetic feed has no track')),
    scores: () => Promise.reject(new Error('synthetic feed has no scores')),
    outcomes: () => Promise.reject(new Error('synthetic feed has no outcomes')),
  }
}
