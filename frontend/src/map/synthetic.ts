import type { CoverageCellView, GapEvent, TypeGroup, VesselView, Watchlist } from '../types'
import { ui } from '../store/ui'
import { vessels } from '../store/vessels'

// SYNTHETIC SHIPS, dev switch `?synthetic=25000`: labelled (ui.feed.isMock = true) and never mixed into real data
// unless asked. It exists so the 60 fps measurement uses an honest ship count without a backend. Ships sail inside
// open-water boxes (a third of the Baltic), and every second a third of them report a new fix as a whole VesselView,
// which is about the delta rate of the real feed. A few are No AIS, sanctioned, spoofed or on the watchlist so every
// state is on screen.

// [west, south, east, north, weight]: boxes chosen to be (almost) all water.
const BOXES: [number, number, number, number, number][] = [
  [17, 55, 20, 58.3, 9], [19.6, 57.6, 22.6, 59.4, 5], [14, 54.6, 16.8, 55.5, 4], [10.6, 54.25, 13.6, 54.9, 3],
  [23, 59.5, 29, 60.1, 5], [18.6, 60.6, 21, 62.9, 3], [20.8, 63.6, 23.6, 65.2, 2], [22.6, 57.4, 23.9, 58.4, 1],
  [2, 53.6, 7.5, 57.5, 8], [-1, 57.2, 4, 60.5, 3], [-4.5, 49.7, 1, 50.3, 4], [6, 57.8, 10, 58.6, 2],
  [4, 37.6, 8, 42.6, 3], [11, 34, 18, 37, 3], [18, 33, 28, 35.4, 3], [-0.5, 36.2, 4, 38, 2],
  [-40, 30, -15, 50, 4], [-70, 30, -52, 40, 2], [-95, 25.2, -85, 28.4, 3], [110, 8, 118, 18, 5],
  [103.6, 1.12, 104.4, 1.22, 2], [123, 26, 128, 31.5, 4], [140, 30, 150, 34, 2], [120.5, 33.5, 124, 36.5, 3],
  [60, 5, 75, 15, 3], [50, 25.3, 55, 26.8, 2], [36.5, 20, 38.8, 23, 1], [-160, 20, -130, 40, 2],
]
// Anchorages: tight clusters of moored ships (they make the stacks and "+N" chips worth testing).
const ANCHORAGES: [number, number][] = [[18.95, 57.2], [24.6, 59.75], [11.2, 54.5], [21.0, 56.9], [3.6, 51.9 + 2], [17.9, 59.55]]
const TYPES: TypeGroup[] = ['cargo', 'cargo', 'cargo', 'tanker', 'tanker', 'fishing', 'passenger', 'tug_special', 'pleasure', 'other']
const FLAGS = ['FI', 'SE', 'EE', 'DE', 'DK', 'PL', 'LV', 'LT', 'NO', 'PA', 'LR', 'MT', 'GB', 'NL']
const KN = 0.514444

function rng(seed: number) {
  let x = seed >>> 0
  return () => { x = (x + 0x6d2b79f5) >>> 0; let t = x; t = Math.imul(t ^ (t >>> 15), t | 1); t ^= t + Math.imul(t ^ (t >>> 7), t | 61); return ((t ^ (t >>> 14)) >>> 0) / 4294967296 }
}

export function startSynthetic(n: number): () => void {
  const r = rng(40)
  const total = BOXES.reduce((a, b) => a + b[4], 0)
  const box = new Uint8Array(n)
  const views: VesselView[] = []
  const gaps: GapEvent[] = []
  const trails: Record<string, [number, number, number][]> = {}
  let now = Date.now()
  for (let i = 0; i < n; i++) {
    let pick = r() * total, b = 0
    while (pick > BOXES[b][4]) { pick -= BOXES[b][4]; b++ }
    box[i] = b
    const [w, s, e, nn] = BOXES[b]
    const type = TYPES[Math.floor(r() * TYPES.length)]
    const anchor = b < 9 && r() < 0.03 ? ANCHORAGES[Math.floor(r() * ANCHORAGES.length)] : null
    const moored = !!anchor || r() < 0.18
    const sog = moored ? 0 : type === 'fishing' ? 3 + r() * 6 : 8 + r() * 12
    const cog = r() * 360
    const noHeading = r() < 0.03
    const v: VesselView = {
      mmsi: 200000000 + i, name: `SYN ${i}`, imo: null, flag: FLAGS[Math.floor(r() * FLAGS.length)], type_group: type,
      length_m: type === 'pleasure' ? 12 : 40 + Math.round(r() * 260),
      lat: anchor ? anchor[1] + (r() - 0.5) * 0.03 : s + r() * (nn - s), lon: anchor ? anchor[0] + (r() - 0.5) * 0.05 : w + r() * (e - w),
      sog_kn: sog, cog_deg: noHeading ? null : cog, heading_deg: noHeading ? null : (cog + (r() - 0.5) * 6 + 360) % 360,
      last_ts: now - Math.floor(r() * 60000), status: 'active', open_gap_id: null, risk_p: null, risk_rank: null,
      sanctioned: r() < 0.001, spoof_recent: r() < 0.001 ? ['jump'] : [], cls: r() < 0.7 ? 'A' : 'B',
    }
    if (r() < 0.001) {
      const start = now - Math.floor((10 + r() * 80) * 60000)
      const g: GapEvent = {
        id: `syn-gap-${v.mmsi}`, version: 1, mmsi: v.mmsi, state: 'open', start_ts: start, end_ts: null, duration_s: (now - start) / 1000,
        last_lat: v.lat, last_lon: v.lon, last_sog_kn: sog, last_cog_deg: cog, next_lat: null, next_lon: null,
        neighbours_heard: 12, neighbours_baseline: 15, cell_id: 'syn', coverage_flag: 'deliberate_candidate',
        radius_m: Math.max(500, sog * KN * (now - start) / 1000),
      }
      gaps.push(g)
      Object.assign(v, { status: 'gap_open', open_gap_id: g.id, last_ts: start })
    }
    if (b < 8 && i % 40 === 0) {
      // 6 h heard track behind Baltic ships, every 10 min, along the reverse course.
      const t: [number, number, number][] = []
      for (let k = 36; k >= 1; k--) {
        const dm = sog * KN * k * 600
        t.push([now - k * 600_000, v.lon - (Math.sin((cog * Math.PI) / 180) * dm) / (111_320 * Math.cos((v.lat * Math.PI) / 180)), v.lat - (Math.cos((cog * Math.PI) / 180) * dm) / 111_320])
      }
      trails[v.mmsi] = t
    }
    views.push(v)
  }
  // Watchlist: 40 Baltic ships, ranks 1–5 inspect, the rest watch.
  const baltic = views.filter((_, i) => box[i] < 8 && i % 97 === 3).slice(0, 40)
  const watchlist: Watchlist = {
    snapshot_ts: now,
    entries: baltic.map((v, k) => ({ rank: k + 1, mmsi: v.mmsi, name: v.name, p: 0.8 - k * 0.015, decision: k < 5 ? 'inspect' : 'watch', prev_rank: k + 1, reason_codes: ['SYNTHETIC'], evidence: [] })),
  }
  for (const e of watchlist.entries) { const v = views[e.mmsi - 200000000]; v.risk_rank = e.rank; v.risk_p = e.p }
  // A receiver hole in the Gulf of Bothnia: dead 0.1° cells.
  const coverage: CoverageCellView[] = []
  for (let a = 628; a < 634; a++) for (let o = 196; o < 204; o++) coverage.push({ cell_id: `${a}_${o}`, state: 'dead', coverage_score: 0 })

  const stats = () => ({ tracked: n, msgs_per_s: Math.round(n / 3), queue_depth: 0 })
  const feed = () => ui.set((s) => ({ feed: { ...s.feed, connected: true, mode: 'live', now_ts: now, stats: stats(), isMock: true } }))
  vessels.applyFrame({ type: 'snapshot', now_ts: now, vessels: views, removed: [], gaps, spoofs: [], watchlist, coverage, trails })
  feed()

  let tick = 0
  const timer = window.setInterval(() => {
    now = Date.now()
    const t0 = performance.now()
    tick++
    const out: VesselView[] = []
    for (let i = tick % 3; i < n; i += 3) {
      const v = views[i]
      if (v.status !== 'active' || !v.sog_kn) continue          // moored ships report rarely; keep them put
      const dt = (now - v.last_ts) / 1000
      let cog = v.cog_deg ?? 0
      if (r() < 0.02) cog = (cog + (r() - 0.5) * 40 + 360) % 360
      const dm = (v.sog_kn ?? 0) * KN * dt
      let lat = v.lat + (Math.cos((cog * Math.PI) / 180) * dm) / 111_320
      let lon = v.lon + (Math.sin((cog * Math.PI) / 180) * dm) / (111_320 * Math.cos((v.lat * Math.PI) / 180))
      const [w, s, e, nn] = BOXES[box[i]]
      if (lon < w || lon > e) { cog = (360 - cog) % 360; lon = Math.min(e, Math.max(w, lon)) }
      if (lat < s || lat > nn) { cog = (540 - cog) % 360; lat = Math.min(nn, Math.max(s, lat)) }
      const nv: VesselView = { ...v, lat, lon, last_ts: now, cog_deg: v.cog_deg == null ? null : cog, heading_deg: v.heading_deg == null ? null : (cog + (r() - 0.5) * 4 + 360) % 360 }
      views[i] = nv
      out.push(nv)
    }
    const t1 = performance.now()
    vessels.applyFrame({ type: 'delta', now_ts: now, vessels: out, removed: [], gaps: [], spoofs: [], watchlist: null })
    feed()
    performance.measure('dvm:synthetic-gen', { start: t0, end: t1 })
    performance.measure('dvm:apply-frame', { start: t1 })
  }, 1000)
  return () => window.clearInterval(timer)
}
