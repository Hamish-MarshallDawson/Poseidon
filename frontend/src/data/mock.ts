// MOCK, clearly labelled (ui.feed.isMock -> "Illustrative data"). Wraps the live adapter and adds what the backend lacks:
//  1. Session replay: records the live feed (ReplayLog) and answers {type:'replay'} exactly like backend PR 45:
//     every action answers `status`; seek answers a snapshot at t clamped to the stored range; play sends a delta every
//     wall second advancing `speed` s and pauses itself at the newest stored time; play/pause/speed while live first seek
//     to the newest stored time; live answers status (live) + the live snapshot. A client in replay gets no live deltas.
//     Replay messages are always forwarded to the server too; once the server answers status.mode 'replay' itself,
//     the mock steps aside for good.
//  2. Forecast: deterministic synthetic scores for ~40 Baltic ships (seeded by mmsi), risk_p/risk_rank on their views,
//     a watchlist, three open gaps (those ships freeze at their last fix), closed gaps, spoofs, a meeting, outcomes.
import type { ClientMsg, GapEvent, HistoryRange, Outcome, RiskScore, SpoofEvent, TimelineEvent, VesselView, Watchlist, WatchlistRow } from '../types'
import type { Frame } from '../store/vessels'
import { vessels as store } from '../store/vessels'
import type { DataAdapter, FeedHandlers, FeedStatus } from './adapter'
import { ReplayLog, type Sample } from './replayLog'
import { ghostRadius } from '../forecast/geo'
import { FREEZE_TS } from '../forecast/labels'
import { wilson } from '../forecast/stats'

const H = 3_600_000
const MIN = 60_000
const HORIZON_S = 21_600
const BALTIC = { w: 9, e: 31, s: 53, n: 66.5 }
export const OWN_STALL = { start: Date.UTC(2026, 10, 7, 19, 39, 44), end: Date.UTC(2026, 10, 7, 19, 50, 8) } // real, from the board
const REASONS = ['RECENT_GAP', 'BLANK_DESTINATION', 'LOITERING', 'FLAG_MISMATCH', 'DRAUGHT_JUMP', 'SPOOF_CIRCLING', 'SANCTIONED']
export const MOCK_MODEL = 'mock-illustrative'

// Deterministic hash of (a, b) to [0, 1).
export function h01(a: number, b = 0): number {
  let x = (a % 2147483647) ^ Math.imul(b | 0, 0x9e3779b1)
  x = Math.imul(x ^ (x >>> 16), 0x85ebca6b); x = Math.imul(x ^ (x >>> 13), 0xc2b2ae35)
  return ((x ^ (x >>> 16)) >>> 0) / 4294967296
}

interface Ranked { mmsi: number; name: string | null; p: number; rank: number; reasons: string[] }

// The synthetic forecast world, built once from the first live snapshot.
class Forecast {
  ranked = new Map<number, Ranked>()
  frozen = new Map<number, VesselView>()   // views of ships whose AIS "stopped" (open gaps)
  gaps: GapEvent[] = []
  spoofs: SpoofEvent[] = []
  meetings: Extract<TimelineEvent, { kind: 'meeting' }>[] = []

  constructor(snapshot: VesselView[], t0: number) {
    const baltic = snapshot.filter((v) => v.lon > BALTIC.w && v.lon < BALTIC.e && v.lat > BALTIC.s && v.lat < BALTIC.n)
      .sort((a, b) => h01(a.mmsi) - h01(b.mmsi)).slice(0, 40)
    const rows = baltic.map((v) => ({ v, p: 0.05 + 0.75 * h01(v.mmsi, 1) })).sort((a, b) => b.p - a.p)
    rows.forEach(({ v, p }, i) => this.ranked.set(v.mmsi, {
      mmsi: v.mmsi, name: v.name, p, rank: i + 1, reasons: REASONS.filter((_, k) => h01(v.mmsi, 10 + k) < 0.3).slice(0, 3),
    }))
    const at = (rank: number) => rows[rank - 1]?.v
    // Open gaps on ranks 3, 8, 16 (rank 3 echoes the design's AURORA BAY); one inside a coverage hole (grey ghost).
    ;([[3, 'deliberate_candidate'], [8, 'deliberate_candidate'], [16, 'coverage_gap']] as const).forEach(([rank, flag]) => {
      const v = at(rank); if (!v) return
      const start = t0 - Math.round((12 + 50 * h01(v.mmsi, 2)) * MIN)
      const g = this.gap(v, start, null, flag)
      this.gaps.push(g)
      this.frozen.set(v.mmsi, { ...v, status: 'gap_open', open_gap_id: g.id, sog_kn: v.sog_kn, last_ts: start })
    })
    ;[5, 11].forEach((rank, k) => {
      const v = at(rank); if (!v) return
      const start = t0 - (4 + k) * H + Math.round(h01(v.mmsi, 3) * 30 * MIN)
      this.gaps.push(this.gap(v, start, start + Math.round((25 + 40 * h01(v.mmsi, 4)) * MIN), 'deliberate_candidate'))
    })
    ;([[9, 'circling_at_anchor', 2], [20, 'jump', 5]] as const).forEach(([rank, type, hAgo]) => {
      const v = at(rank); if (!v) return
      const ts = t0 - hAgo * H
      this.spoofs.push({ id: `spoof-${type}-${v.mmsi}-${ts}`, mmsi: v.mmsi, ts, type, severity: 0.6, jamming_suspect: false, evidence: { mock: true } })
    })
    const a = at(1), b = at(6)
    if (a && b) this.meetings.push({ kind: 'meeting', id: `meet-${a.mmsi}-${b.mmsi}`, mmsi: a.mmsi, other_mmsi: b.mmsi, ts: t0 - 3 * H })
  }

  private gap(v: VesselView, start: number, end: number | null, flag: GapEvent['coverage_flag']): GapEvent {
    return {
      id: `gap-${v.mmsi}-${start}`, version: 1, mmsi: v.mmsi, state: end ? 'closed' : 'open', start_ts: start, end_ts: end,
      duration_s: end ? (end - start) / 1000 : 0, last_lat: v.lat, last_lon: v.lon, last_sog_kn: v.sog_kn ?? 8, last_cog_deg: v.cog_deg,
      next_lat: null, next_lon: null, neighbours_heard: flag === 'coverage_gap' ? 0 : 9 + Math.floor(8 * h01(v.mmsi, 5)),
      neighbours_baseline: 16, cell_id: 'mock', coverage_flag: flag,
    }
  }

  // Gaps as the server would hold them at time t (latest version per id).
  gapsAt(t: number): GapEvent[] {
    const out: GapEvent[] = []
    for (const g of this.gaps) {
      if (g.start_ts > t) continue
      if (g.end_ts !== null) { if (g.end_ts <= t) out.push({ ...g, radius_m: ghostRadius(g, g.end_ts) }); continue }
      const dur = Math.floor((t - g.start_ts) / 1000)
      out.push({ ...g, version: 1 + Math.floor(dur / 60), duration_s: dur, radius_m: ghostRadius(g, t) })
    }
    return out
  }

  isFrozenAt(mmsi: number, t: number): boolean {
    const v = this.frozen.get(mmsi)
    return !!v && v.last_ts <= t
  }

  decorate(v: VesselView, t: number): VesselView {
    const fz = this.frozen.get(v.mmsi)
    const base = fz && fz.last_ts <= t ? fz : v
    const r = this.ranked.get(v.mmsi)
    return r ? { ...base, risk_p: r.p, risk_rank: r.rank } : base
  }

  watchlist(t: number): Watchlist {
    const entries: WatchlistRow[] = [...this.ranked.values()].filter((r) => r.p >= 0.1).map((r) => ({
      rank: r.rank, mmsi: r.mmsi, name: r.name, p: r.p, decision: r.rank <= 5 ? 'inspect' : 'watch', prev_rank: r.rank,
      reason_codes: this.frozen.has(r.mmsi) && this.isFrozenAt(r.mmsi, t) ? ['OPEN_GAP', ...r.reasons] : r.reasons,
      evidence: [{ kind: 'score', id: `score-${r.mmsi}-dark_6h-${hourOf(t)}`, label: `${Math.round(r.p * 100)} % · illustrative` }],
    }))
    return { snapshot_ts: t, entries }
  }

  // Forecast made at hour `made_at`: p jitters per hour around the ship's base p; ranks recomputed.
  scoresAt(made_at: number): RiskScore[] {
    const rows = [...this.ranked.values()].map((r) => {
      const p = Math.min(0.85, Math.max(0.03, r.p + 0.12 * (h01(r.mmsi, made_at / H) - 0.5)))
      return { r, p }
    }).sort((a, b) => b.p - a.p)
    return rows.map(({ r, p }, i) => ({
      id: `score-${r.mmsi}-dark_6h-${made_at}`, mmsi: r.mmsi, made_at, as_of: made_at, horizon_s: HORIZON_S, target: 'dark_6h',
      p, rank: i + 1, mode: 'live', features: { gaps_24h: Math.floor(3 * h01(r.mmsi, 20)) }, contrib: {}, model_version: MOCK_MODEL,
    }))
  }

  outcomeFor(s: RiskScore): Outcome {
    const end = s.made_at + HORIZON_S * 1000
    const stalled = s.made_at < OWN_STALL.end && end > OWN_STALL.start && h01(s.mmsi, 30) < 0.3
    const censored = stalled ? 'own_stall' : h01(s.mmsi, s.made_at / H + 31) < 0.08 ? 'coverage_gap' : null
    const hit = h01(s.mmsi, s.made_at / H + 7) < s.p
    return {
      score_id: s.id, mmsi: s.mmsi, made_at: s.made_at, resolved_at: end + 30 * MIN, label: hit ? 'hit' : 'miss', censored,
      lead_s: hit ? Math.round(HORIZON_S * h01(s.mmsi, s.made_at / H + 8)) : null,
    }
  }
}

const hourOf = (t: number) => Math.floor(t / H) * H

// Illustrative baselines for the forecast check (the real ones come from the evaluation read, per model_version).
export function mockBaselines(madeAt: number, n: number): { model_version: string; hits: number; n: number; ci: [number, number] }[] {
  return ['baseline-prior-gap', 'baseline-tankers', 'baseline-cell-rate'].map((m, i) => {
    const hits = Math.floor(n * (0.15 + 0.3 * h01(madeAt / H, 40 + i)))
    return { model_version: m, hits, n, ci: wilson(hits, n) }
  })
}

export function createMockAdapter(live: DataAdapter): DataAdapter {
  const log = new ReplayLog()
  const latest = new Map<number, VesselView>()     // live state: statics for replay views and the snapshot on 'live'
  let fc: Forecast | null = null
  let h: FeedHandlers | null = null
  let liveStatus: FeedStatus | null = null
  let liveNow = Date.now()
  let serverReplay = false                          // the backend answered replay itself: step aside for good
  let serverMode: 'live' | 'replay' = 'live'
  // local replay state
  let mode: 'live' | 'replay' = 'live'
  let paused = false
  let speed = 60
  let clock = 0
  let timer: number | undefined

  const range = () => ({ from_ts: log.from_ts ?? liveNow, to_ts: log.to_ts ?? liveNow })

  function emitStatus() {
    if (!h || !liveStatus) return
    h.onStatus({ ...liveStatus, mode, speed: mode === 'live' ? 1 : speed, paused: mode === 'live' ? false : paused,
      now_ts: mode === 'live' ? liveNow : clock, replay: range() })
  }

  function view(s: Sample): VesselView | null {
    const v = latest.get(s.mmsi)
    if (!v) return null
    return { ...v, lat: s.lat, lon: s.lon, sog_kn: s.sog, cog_deg: s.cog, heading_deg: s.hdg, last_ts: s.t, status: 'active', open_gap_id: null }
  }

  function frame(type: 'snapshot' | 'delta', t: number, vs: VesselView[], removed: number[] = []): Frame {
    const out: VesselView[] = []
    for (const v of vs) {
      if (type === 'delta' && fc?.isFrozenAt(v.mmsi, t)) continue      // a silent ship sends nothing
      out.push(fc ? fc.decorate(v, t) : v)
    }
    if (type === 'snapshot' && fc) for (const [m, fz] of fc.frozen) if (fz.last_ts <= t && !vs.some((v) => v.mmsi === m)) out.push(fc.decorate(fz, t))
    const gaps = fc ? (type === 'snapshot' ? fc.gapsAt(t) : fc.gapsAt(t).filter((g) => g.state === 'open')) : []
    const spoofs = fc && type === 'snapshot' ? fc.spoofs.filter((s) => s.ts <= t) : []
    return { type, now_ts: t, vessels: out, removed, gaps, spoofs, watchlist: fc && type === 'snapshot' ? fc.watchlist(t) : null }
  }

  function seek(t: number) {
    const r = range()
    clock = Math.min(r.to_ts, Math.max(r.from_ts, t))
    mode = 'replay'
    const vs = log.snapshotAt(clock).map(view).filter((v): v is VesselView => !!v)
    h?.onFrame({ ...frame('snapshot', clock, vs), trails: {}, coverage: [] })
  }

  function stopTimer() { window.clearInterval(timer); timer = undefined }
  function tick() {
    const to = range().to_ts
    const t1 = Math.min(to, clock + speed * 1000)
    const vs = log.between(clock, t1).map(view).filter((v): v is VesselView => !!v)
    clock = t1
    h?.onFrame(frame('delta', clock, vs))
    if (clock >= to) { paused = true; stopTimer(); emitStatus() }
  }

  function replay(msg: Extract<ClientMsg, { type: 'replay' }>) {
    if (msg.action === 'live') {
      stopTimer(); mode = 'live'; paused = false
      emitStatus()
      h?.onFrame(frame('snapshot', liveNow, [...latest.values()]))
      return
    }
    if (msg.action === 'seek') { if (mode === 'live') paused = true; seek(msg.t ?? clock); emitStatus(); return }
    if (mode === 'live') { paused = true; seek(range().to_ts) }
    if (msg.action === 'speed') speed = Math.min(600, Math.max(1, msg.speed ?? 60))
    if (msg.action === 'pause') { paused = true; stopTimer() }
    if (msg.action === 'play') { paused = false; if (timer === undefined) timer = window.setInterval(tick, 1000) }
    emitStatus()
  }

  return {
    isMock: true,
    start(handlers) {
      h = handlers
      live.start({
        onDetail: (m) => handlers.onDetail(fc ? { ...m, vessel: fc.decorate(m.vessel, m.vessel.last_ts) } : m),
        onStatus(s) {
          serverMode = s.mode
          if (s.mode === 'replay') { serverReplay = true; stopTimer(); mode = 'live' }
          if (serverReplay) { handlers.onStatus(s); return }
          liveStatus = s
          emitStatus()
        },
        onFrame(f) {
          if (serverReplay && serverMode === 'replay') { handlers.onFrame(fc ? { ...f, ...frame(f.type, f.now_ts, f.vessels, f.removed), trails: f.trails, coverage: f.coverage } : f); return }
          liveNow = f.now_ts
          if (f.type === 'snapshot') latest.clear()
          for (const v of f.vessels) { latest.set(v.mmsi, v); log.record(f.now_ts, v) }
          for (const m of f.removed) latest.delete(m)
          if (!fc && f.type === 'snapshot') fc = new Forecast(f.vessels, f.now_ts)
          if (mode === 'replay' && !serverReplay) return                // a client in replay gets no live deltas
          const out = frame(f.type, f.now_ts, f.vessels, f.removed)
          handlers.onFrame({ ...out, trails: f.trails, coverage: f.coverage })
        },
      })
    },
    stop() { stopTimer(); live.stop(); h = null },
    send(msg) {
      live.send(msg)
      if (msg.type === 'replay' && !serverReplay) replay(msg)
    },
    async historyRange(): Promise<HistoryRange> { return range() },
    async scores(as_of?: number) { return fc ? fc.scoresAt(hourOf(as_of ?? liveNow)) : [] },
    async outcomes(from_ts, to_ts) {
      if (!fc) return []
      const out: Outcome[] = []
      const until = Math.min(to_ts, liveNow)
      for (let made = hourOf(from_ts - HORIZON_S * 1000 - 30 * MIN); made + HORIZON_S * 1000 + 30 * MIN <= until; made += H) {
        for (const s of fc.scoresAt(made).slice(0, 10)) {
          const o = fc.outcomeFor(s)
          if (o.resolved_at >= from_ts) out.push(o)
        }
      }
      return out
    },
    async timeline(from_ts, to_ts) {
      const ev: TimelineEvent[] = []
      const inWin = (a: number, b: number | null) => a <= to_ts && (b ?? liveNow) >= from_ts
      const gaps = new Map<string, GapEvent>()
      for (const g of fc?.gapsAt(liveNow) ?? []) gaps.set(g.id, g)
      for (const g of store.gaps.values()) if (!gaps.has(g.id)) gaps.set(g.id, g)
      for (const g of gaps.values()) if (inWin(g.start_ts, g.end_ts)) ev.push({ kind: 'gap', id: g.id, mmsi: g.mmsi, start_ts: g.start_ts, end_ts: g.end_ts })
      for (const s of [...(fc?.spoofs ?? []), ...store.spoofs]) if (inWin(s.ts, s.ts)) ev.push({ kind: 'spoof', id: s.id, mmsi: s.mmsi, ts: s.ts })
      for (const m of fc?.meetings ?? []) if (inWin(m.ts, m.ts)) ev.push(m)
      if (inWin(FREEZE_TS, FREEZE_TS)) ev.push({ kind: 'freeze', id: 'freeze', ts: FREEZE_TS })
      for (const o of await this.outcomes(from_ts, to_ts)) {
        ev.push({ kind: 'outcome', id: `out-${o.score_id}`, mmsi: o.mmsi, ts: o.resolved_at, label: o.censored ? 'censored' : o.label })
      }
      // Coverage: the server log (GET /history/range when it exists) with today's real own_stall; else this session.
      const r = await live.historyRange().then((x) => (x.from_ts ? x : range()), () => range())
      const spans: [number, number, 'data' | 'own_stall'][] = OWN_STALL.start > r.from_ts && OWN_STALL.end < r.to_ts
        ? [[r.from_ts, OWN_STALL.start, 'data'], [OWN_STALL.start, OWN_STALL.end, 'own_stall'], [OWN_STALL.end, r.to_ts, 'data']]
        : [[r.from_ts, r.to_ts, 'data']]
      spans.forEach(([a, b, state], i) => ev.push({ kind: 'coverage', id: `cov-${i}`, start_ts: a, end_ts: b, state }))
      return ev
    },
  }
}
