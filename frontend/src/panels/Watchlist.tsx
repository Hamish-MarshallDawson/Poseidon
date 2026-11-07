import { memo, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { ui } from '../store/ui'
import { onTokensChange } from '../theme/tokens'
import { Button, Kbd } from '../ui'
import { vessels } from '../store/vessels'
import { mapStore } from '../map/context'
import { reducedMotion, usePresence } from '../motion'
import { openShipWindow } from '../windows/open'
import { useNow, useWatchlist } from '../windows/hooks'
import { EvidenceStrip } from '../windows/ShipCard'
import { DECISION_LABEL, TYPE_LABEL, fmtInt, minutes, pct, reasonText, riskBand, utcTime, wilson } from '../windows/format'
import type { WatchlistRow } from '../types'

// Watchlist summon chip (Figma 66:21907) and the 360-wide drop-in panel (R2/Forecast/Watchlist panel 56:4359).
// Rows are virtualised: two fixed row heights (normal and "No AIS now"), measured once from the first rendered row.

export function WatchlistChip() {
  const open = ui.use((s) => s.watchlistOpen)
  const n = useWatchlist()?.entries.length ?? 0
  return (
    <button type="button" className={`chip ${open ? 'on' : ''}`} aria-expanded={open} aria-controls="watchlist-panel"
      onClick={() => ui.set((s) => ({ watchlistOpen: !s.watchlistOpen, layersOpen: false }))}>
      <span className="lamp" aria-hidden />
      Ranked for review · next 6 h
      <span className="chip-count">{n}</span>
    </button>
  )
}

const PANEL_W = 360

function select(mmsi: number) {
  const map = mapStore.get().map
  const v = vessels.vessels.get(mmsi)
  if (map && v) {
    // The ship ends at the centre of the map left of the panel, so its window can open beside it straight away.
    const padding = { top: 0, bottom: 0, left: 0, right: PANEL_W + 16 }
    const r = map.getContainer().getBoundingClientRect()
    map.flyTo({ center: [v.lon, v.lat], zoom: Math.max(map.getZoom(), 7), padding, duration: reducedMotion() ? 0 : 900, essential: true })
    openShipWindow(mmsi, { x: r.left + (r.width - padding.right) / 2, y: r.top + r.height / 2 })
  } else openShipWindow(mmsi)
}

const isNoAis = (e: WatchlistRow) => e.reason_codes.includes('OPEN_GAP')

const Row = memo(function Row({ e, now, y, measure }: { e: WatchlistRow; now: number; y: number; measure?: (el: HTMLElement | null) => void }) {
  const v = vessels.vessels.get(e.mmsi)
  const gap = v?.open_gap_id ? vessels.gaps.get(v.open_gap_id) : undefined
  const noAis = isNoAis(e)
  const move = e.prev_rank === null ? 'new' : e.prev_rank > e.rank ? `↑${e.prev_rank - e.rank}` : e.prev_rank < e.rank ? `↓${e.rank - e.prev_rank}` : '–'
  const band = riskBand(e.p)
  return (
    <button type="button" ref={measure} className={`wl-row ${noAis ? 'is-noais' : ''}`} style={{ transform: `translateY(${y}px)` }}
      onClick={() => select(e.mmsi)}
      onPointerEnter={() => ui.set({ hoverMmsi: e.mmsi })}
      onPointerLeave={() => ui.set((s) => ({ hoverMmsi: s.hoverMmsi === e.mmsi ? null : s.hoverMmsi }))}
      onFocus={() => ui.set({ hoverMmsi: e.mmsi })}
      onBlur={() => ui.set((s) => ({ hoverMmsi: s.hoverMmsi === e.mmsi ? null : s.hoverMmsi }))}>
      <span className="wl-rank">
        <b>{String(e.rank).padStart(2, '0')}</b>
        <span aria-label={e.prev_rank === null ? 'new' : `was ${e.prev_rank}`}>{move}</span>
      </span>
      <span className="wl-body">
        <span className="wl-head">
          <span className="wl-name"><b>{e.name ?? v?.name ?? e.mmsi}</b>{v && <span>{TYPE_LABEL[v.type_group]}</span>}</span>
          {e.decision !== 'none' && <span className={`wl-decision ${e.decision}`}>{DECISION_LABEL[e.decision]}</span>}
        </span>
        <span className="wl-p">
          <span className="wl-bar"><i className={noAis ? '' : `risk-${band}`} style={{ transform: `scaleX(${e.p})` }} /></span>
          <b>{pct(e.p)}</b>
        </span>
        {noAis && (
          <span className="wl-note">
            No AIS{gap ? ` ${minutes(now - gap.start_ts)}` : ''} · {pct(e.p)} was the forecast before the silence
          </span>
        )}
        <span className="wl-reasons">{reasonText(e.reason_codes)}</span>
        <span className="wl-ev">{v && <EvidenceStrip ts={v.last_ts} now={now} />}</span>
      </span>
    </button>
  )
})

// The honest footer (R2/Forecast/Test summary 56:4358): Running until outcomes exist, then Scored compact.
export interface TestResult { freezeTs: number; hits: number; n: number; censored: number; baselinesOverlap: boolean }
export function TestSummary({ result }: { result?: TestResult }) {
  if (!result) {
    return (
      <div className="wl-test">
        <b>Prospective test running</b>
        <span className="wl-test-note">Forecast frozen 23:00Z Sat · scored at 11:00Z Sun. No results until then.</span>
      </div>
    )
  }
  const [lo, hi] = wilson(result.hits, result.n)
  return (
    <div className="wl-test">
      <b>Prospective test · top 10 at the {utcTime(result.freezeTs, false)} freeze</b>
      <span className="wl-test-head">{result.hits} of {result.n} went silent · 95 % range {lo}–{hi} %</span>
      <span className="wl-test-note">
        {result.baselinesOverlap ? 'Ranges overlap all three baselines' : 'Ranges clear of the baselines'}
        {result.censored ? ` · ${result.censored} not scored` : ''}.
      </span>
    </div>
  )
}

function WatchlistPanel() {
  const wl = useWatchlist()
  const now = useNow()
  const entries = useMemo(() => wl?.entries ?? [], [wl])
  const listRef = useRef<HTMLDivElement>(null)
  const [scroll, setScroll] = useState({ top: 0, height: 432 })
  const [heights, setHeights] = useState({ row: 150, noais: 170 })

  const offsets = useMemo(() => {
    const o = [0]
    for (const e of entries) o.push(o[o.length - 1] + (isNoAis(e) ? heights.noais : heights.row))
    return o
  }, [entries, heights])
  // First and last visible row, by binary search over the offsets, plus 2 rows either side.
  let first = 0
  for (let lo = 0, hi = entries.length - 1; lo <= hi;) {
    const mid = (lo + hi) >> 1
    if (offsets[mid + 1] <= scroll.top) lo = first = mid + 1
    else hi = mid - 1
  }
  first = Math.max(0, first - 2)
  let last = first
  while (last < entries.length && offsets[last] < scroll.top + scroll.height) last++
  last = Math.min(entries.length, last + 2)

  // Each kind's height is measured once from its first rendered row (text size modes change it).
  const [measured, setMeasured] = useState({ row: false, noais: false })
  useEffect(() => onTokensChange(() => setMeasured({ row: false, noais: false })), [])
  const measure = (kind: 'row' | 'noais') => (el: HTMLElement | null) => {
    if (!el) return
    const h = el.offsetHeight
    setMeasured((m) => ({ ...m, [kind]: true }))
    if (h) setHeights((s) => (s[kind] === h ? s : { ...s, [kind]: h }))
  }

  useLayoutEffect(() => {
    const el = listRef.current!
    let pending = 0
    const onScroll = () => {
      if (pending) return
      pending = requestAnimationFrame(() => { pending = 0; setScroll({ top: el.scrollTop, height: el.clientHeight }) })
    }
    setScroll({ top: el.scrollTop, height: el.clientHeight })
    el.addEventListener('scroll', onScroll, { passive: true })
    return () => { el.removeEventListener('scroll', onScroll); cancelAnimationFrame(pending) }
  }, [])

  return (
    <div className="panel watchlist" id="watchlist-panel" role="region" aria-labelledby="wl-title">
      <div className="wl-header">
        <div className="wl-titlerow">
          <h2 id="wl-title">Ranked for review · next 6 h</h2>
          <Button className="btn-small" onClick={() => ui.set({ watchlistOpen: false })}>Close <Kbd>Esc</Kbd></Button>
        </div>
        <p className="wl-explain">Chance a ship goes silent with reception normal nearby, within 6 h. Behaviour only: list matches show as reasons, never as inputs.</p>
        <p className="wl-meta">{wl ? `Forecast ${utcTime(wl.snapshot_ts, false)} · ${fmtInt(entries.length)} ships ranked` : 'No forecast received yet'}</p>
      </div>
      <div className="wl-list" ref={listRef} role="list">
        <div className="wl-spacer" style={{ height: offsets[entries.length] }}>
          {entries.slice(first, last).map((e, i) => {
            const kind = isNoAis(e) ? 'noais' : 'row'
            return (
              <div role="listitem" key={e.mmsi}>
                <Row e={e} now={now} y={offsets[first + i]} measure={measured[kind] ? undefined : measure(kind)} />
              </div>
            )
          })}
        </div>
      </div>
      <TestSummary />
    </div>
  )
}

export function Watchlist() {
  const open = ui.use((s) => s.watchlistOpen)
  const { mounted, attach } = usePresence(open, { y: -12, opacity: 0 })
  return mounted ? <div className="watchlist-wrap" ref={attach}><WatchlistPanel /></div> : null
}
