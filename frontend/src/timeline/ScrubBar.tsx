import { memo, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { adapter } from '../data/index'
import { ui, type TimeRange } from '../store/ui'
import { vessels } from '../store/vessels'
import type { TimelineEvent } from '../types'
import { forecastUi } from '../forecast/state'
import { fmtBehind, fmtDay, fmtSpan, fmtTime } from './format'
import { openShip, replay, replayUi, shownNow, startClock } from './replay'
import './scrubbar.css'

const MIN = 60_000
const H = 60 * MIN
const PRESETS: Record<'1h' | '6h' | '24h', number> = { '1h': H, '6h': 6 * H, '24h': 24 * H }
const SPEEDS = [1, 10, 60, 300]
const ZOOM_MIN = 15 * MIN
const ZOOM_MAX = 7 * 24 * H
const MERGE_PX = 6

interface View { from: number; to: number }
const viewOf = (r: TimeRange, now: number): View => typeof r === 'string' ? { from: now - PRESETS[r], to: now } : { from: r.from_ts, to: r.to_ts }
const spanOf = (v: View) => v.to - v.from

// Arrow / Shift+arrow steps and ticks per range (timeline report); anything else picks the nearest.
function stepsFor(span: number): [number, number] {
  if (span <= H) return [MIN, 10 * MIN]
  if (span <= 6 * H) return [5 * MIN, 30 * MIN]
  return [15 * MIN, 2 * H]
}
function ticksFor(span: number): [number, number] {
  const table: [number, number, number][] = [[H, 10 * MIN, 5 * MIN], [6 * H, H, 15 * MIN], [24 * H, 3 * H, H], [Infinity, 24 * H, 6 * H]]
  const [, major, minor] = table.find(([max]) => span <= max * 1.01) ?? table[3]
  return [major, minor]
}

export function ScrubBar() {
  const mode = ui.use((s) => s.feed.mode)
  const paused = ui.use((s) => s.feed.paused)
  const speed = ui.use((s) => s.feed.speed)
  const range = ui.use((s) => s.time.range)
  const follow = ui.use((s) => s.follow)
  const nWin = ui.use((s) => s.windows.length)
  const loading = replayUi.use((s) => s.loading)
  const [wall, setWall] = useState(() => Date.now())
  const [width, setWidth] = useState(0)
  const [menu, setMenu] = useState<null | 'speed' | 'range' | 'custom'>(null)
  const lastPreset = useRef<'1h' | '6h' | '24h'>(typeof range === 'string' ? range : '6h')
  const trackRef = useRef<HTMLDivElement>(null)
  const headRef = useRef<HTMLDivElement>(null)
  const tipRef = useRef<HTMLDivElement>(null)
  const live = mode === 'live'
  const view = useMemo(() => viewOf(range, wall), [range, wall])
  const viewRef = useRef(view)
  useLayoutEffect(() => { viewRef.current = view }, [view])

  useEffect(() => startClock(), [])
  useEffect(() => { const id = window.setInterval(() => setWall(Date.now()), 1000); return () => window.clearInterval(id) }, [])
  useLayoutEffect(() => {
    const el = trackRef.current!
    const ro = new ResizeObserver(() => setWidth(el.clientWidth))
    ro.observe(el)
    return () => ro.disconnect()
  }, [])

  const setRange = (r: TimeRange) => {
    if (typeof r === 'string') lastPreset.current = r
    ui.set((s) => ({ time: { ...s.time, range: r } }))
  }
  const xToT = (clientX: number) => {
    const r = trackRef.current!.getBoundingClientRect()
    const v = viewRef.current
    return v.from + Math.min(1, Math.max(0, (clientX - r.left) / r.width)) * spanOf(v)
  }

  // Playhead from rAF: transform only, no React render per frame.
  useEffect(() => {
    let raf = 0
    const loop = () => {
      raf = requestAnimationFrame(loop)
      const el = headRef.current, tr = trackRef.current
      if (!el || !tr) return
      const s = ui.get()
      const v = viewRef.current
      const t = s.time.dragT ?? (s.feed.mode === 'live' ? v.to : shownNow())
      const f = (t - v.from) / spanOf(v)
      el.style.transform = `translateX(${Math.min(1, Math.max(0, f)) * tr.clientWidth}px)`
      el.style.opacity = f < 0 || f > 1 ? '0.35' : '1'
    }
    raf = requestAnimationFrame(loop)
    return () => cancelAnimationFrame(raf)
  }, [])

  // Pointer: click seeks; drag scrubs locally with a trailing seek after 150 ms rest and a final seek on release.
  // Gap spans cover long stretches of the line (an open gap runs to now), so a drag may start on one: moving scrubs,
  // a press without movement is a click on that gap. Point markers are small and keep their own click.
  const drag = useRef<{ id: number; rest?: number; x0: number; moved: boolean; gap: HTMLElement | null } | null>(null)
  const onPointerDown = (e: React.PointerEvent) => {
    const hit = (e.target as HTMLElement).closest<HTMLElement>('.tl-marker')
    if (e.button !== 0 || (hit && !hit.classList.contains('tl-gap'))) return
    if (hit) e.preventDefault()                               // no focus ring jump; the click is replayed on release
    trackRef.current!.setPointerCapture(e.pointerId)
    drag.current = { id: e.pointerId, x0: e.clientX, moved: !hit, gap: hit }
    if (!hit) ui.set((s) => ({ time: { ...s.time, dragging: true, dragT: xToT(e.clientX) } }))
  }
  const onPointerMove = (e: React.PointerEvent) => {
    const t = xToT(e.clientX)
    const tip = tipRef.current
    if (tip) {
      tip.textContent = fmtTime(t)
      tip.style.transform = `translateX(${e.clientX - trackRef.current!.getBoundingClientRect().left}px) translateX(-50%)`
    }
    const d = drag.current
    if (!d || d.id !== e.pointerId) return
    if (!d.moved) {
      if (Math.abs(e.clientX - d.x0) < 3) return
      d.moved = true
      ui.set((s) => ({ time: { ...s.time, dragging: true } }))
    }
    ui.set((s) => ({ time: { ...s.time, dragT: t } }))
    window.clearTimeout(d.rest)
    d.rest = window.setTimeout(() => replay.seek(t), 150)
  }
  const endDrag = (e: React.PointerEvent, commit: boolean) => {
    const d = drag.current
    if (!d || d.id !== e.pointerId) return
    window.clearTimeout(d.rest)
    drag.current = null
    if (!d.moved) { if (commit) d.gap?.click(); return }      // a press on a gap span: that gap's own action
    const t = xToT(e.clientX)
    ui.set((s) => ({ time: { ...s.time, dragging: false } }))
    if (commit) replay.seek(t)
    else ui.set((s) => ({ time: { ...s.time, dragT: null } }))
  }

  // Wheel zooms around the cursor (15 min to 7 d); Shift+wheel pans. Non-passive so the page doesn't scroll.
  useEffect(() => {
    const el = trackRef.current!
    const onWheel = (e: WheelEvent) => {
      e.preventDefault()
      const v = viewRef.current
      const span = spanOf(v)
      const delta = e.deltaY || e.deltaX
      if (e.shiftKey) {
        const dt = (delta / 500) * span
        const to = Math.min(Date.now(), v.to + dt)
        setRange({ from_ts: to - span, to_ts: to })
        return
      }
      const r = el.getBoundingClientRect()
      const f = Math.min(1, Math.max(0, (e.clientX - r.left) / r.width))
      const at = v.from + f * span
      const next = Math.min(ZOOM_MAX, Math.max(ZOOM_MIN, span * Math.exp(delta / 400)))
      const to = Math.min(Date.now(), at + (1 - f) * next)
      setRange({ from_ts: to - next, to_ts: to })
    }
    el.addEventListener('wheel', onWheel, { passive: false })
    return () => el.removeEventListener('wheel', onWheel)
  }, [])

  // Keys: Space play/pause, arrows step, Shift+arrows big step, L live, Home oldest, End live.
  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const t = e.target as HTMLElement
      const onSlider = t.getAttribute?.('role') === 'slider' && t.closest('.tl-bar')
      if (!onSlider && t.closest?.('input, textarea, select, button, [contenteditable], [role=dialog], [role=menu]')) return
      if (e.ctrlKey || e.metaKey || e.altKey) return
      const s = ui.get()
      const [small, big] = stepsFor(spanOf(viewRef.current))
      const shown = s.time.dragT ?? (s.feed.mode === 'live' ? Date.now() : shownNow())
      // Steps belong to the focused slider; elsewhere arrows pan the map and Home/End scroll lists.
      if (!onSlider && ['ArrowLeft', 'ArrowRight', 'Home', 'End'].includes(e.key)) return
      switch (e.key) {
        case ' ': replay.toggle(); break
        case 'l': case 'L': replay.live(); break
        case 'ArrowLeft': replay.seek(shown - (e.shiftKey ? big : small)); break
        case 'ArrowRight': if (s.feed.mode === 'replay') replay.seek(shown + (e.shiftKey ? big : small)); break
        case 'Home': replay.seek(s.feed.replay?.from_ts ?? viewRef.current.from); break
        case 'End': replay.live(); break
        default: return
      }
      e.preventDefault()
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [])

  const aria = useAriaClock(live, wall)
  return (
    <div className={`tl-bar ${live ? 'is-live' : 'is-replay'}`} role="group" aria-label="Timeline">
      <button className="tl-btn tl-play" onClick={() => replay.toggle()}
        aria-label={live || !paused ? 'Pause (Space)' : 'Play (Space)'} title={live || !paused ? 'Pause (Space)' : 'Play (Space)'}>
        {live || !paused ? <PauseIcon /> : <PlayIcon />}
      </button>
      <Readout live={live} loading={loading} wall={wall} />
      <div ref={trackRef} className="tl-track" role="slider" tabIndex={0} aria-label="Shown time"
        aria-valuemin={Math.round(view.from)} aria-valuemax={Math.round(view.to)} aria-valuenow={aria.now} aria-valuetext={aria.text}
        onPointerDown={onPointerDown} onPointerMove={onPointerMove} onPointerUp={(e) => endDrag(e, true)}
        onPointerCancel={(e) => endDrag(e, false)} onDoubleClick={() => setRange(lastPreset.current)}>
        <Ticks view={view} width={width} />
        <div className="tl-line" />
        <Markers view={view} width={width} />
        <div ref={headRef} className="tl-head" aria-hidden><i /></div>
        <div ref={tipRef} className="tl-tip" aria-hidden />
      </div>
      <div className="tl-menu-wrap">
        <button className="tl-btn tl-text" disabled={live} aria-haspopup="menu" aria-expanded={menu === 'speed'}
          aria-label={`Playback speed ${live ? 1 : speed}×`} onClick={() => setMenu(menu === 'speed' ? null : 'speed')}>{live ? 1 : speed}×</button>
        {menu === 'speed' && (
          <Menu label="Playback speed" onClose={() => setMenu(null)}
            items={SPEEDS.map((x) => ({ key: String(x), label: `${x}×`, checked: x === speed, run: () => replay.speed(x) }))} />
        )}
      </div>
      <div className="tl-menu-wrap">
        <button className="tl-btn tl-text" aria-haspopup="menu" aria-expanded={menu === 'range' || menu === 'custom'}
          aria-label={`Range ${fmtSpan(spanOf(view))}`} onClick={() => setMenu(menu ? null : 'range')}>
          {typeof range === 'string' ? range.replace('h', ' h') : fmtSpan(spanOf(view))}
        </button>
        {menu === 'range' && (
          <Menu label="Range" onClose={() => setMenu(null)} items={[
            ...(['1h', '6h', '24h'] as const).map((r) => ({ key: r, label: r.replace('h', ' h'), checked: range === r, run: () => setRange(r) })),
            { key: 'custom', label: 'Custom…', checked: typeof range !== 'string', run: () => setMenu('custom'), keepOpen: true },
          ]} />
        )}
        {menu === 'custom' && <CustomRange view={view} onApply={(v) => { setRange(v); setMenu(null) }} onClose={() => setMenu(null)} />}
      </div>
      {!live && nWin > 0 && (
        <button className="tl-btn tl-text tl-follow" aria-pressed={follow} onClick={() => ui.set({ follow: !follow })}
          title={follow ? 'Show every ship again' : 'Show only the selected ships and their tracks'}>
          {follow ? `Following ${nWin} ${nWin === 1 ? 'ship' : 'ships'} · Show all` : `Follow selected (${nWin})`}
        </button>
      )}
      {!live && <button className="tl-btn tl-live" onClick={() => replay.live()} title="Back to live (L)">Back to live</button>}
    </div>
  )
}

function useAriaClock(live: boolean, wall: number) {
  const now = ui.use((s) => Math.floor((s.time.dragT ?? s.feed.now_ts) / 1000) * 1000)
  return { now, text: live ? `Live, ${fmtTime(now)}` : `${fmtDay(now)} ${fmtTime(now)}, ${fmtBehind(wall - now).slice(1)} behind live` }
}

function Readout({ live, loading, wall }: { live: boolean; loading: boolean; wall: number }) {
  const t = ui.use((s) => Math.floor((s.time.dragT ?? s.feed.now_ts) / 1000) * 1000)
  return (
    <span className="tl-readout" aria-live="off">
      <span className="tl-time">{fmtTime(t)}</span>
      {!live && <span className="tl-behind">{fmtBehind(wall - t)}</span>}
      {loading && <span className="tl-loading">Loading…</span>}
    </span>
  )
}

const Ticks = memo(function Ticks({ view, width }: { view: View; width: number }) {
  if (!width) return null
  const [major, minor] = ticksFor(spanOf(view))
  const out = []
  for (let t = Math.ceil(view.from / minor) * minor; t <= view.to; t += minor) {
    const x = ((t - view.from) / spanOf(view)) * width
    out.push(<i key={t} className={t % major === 0 ? 'tl-tick major' : 'tl-tick'} style={{ transform: `translateX(${x}px)` }} />)
  }
  return <div className="tl-ticks" aria-hidden>{out}</div>
})

// Event markers and the coverage strip for the visible window. Only watchlisted and selected ships, plus freeze/coverage.
function Markers({ view, width }: { view: View; width: number }) {
  const [events, setEvents] = useState<TimelineEvent[]>([])
  const windows = ui.use((s) => s.windows)
  const rangeKey = `${Math.round(view.from / 30_000)}:${Math.round(spanOf(view) / 30_000)}`
  const vRef = useRef(view)
  useEffect(() => { vRef.current = view }, [view])
  useEffect(() => {
    let dead = false
    const load = () => {
      const v = vRef.current
      adapter?.timeline(v.from - spanOf(v) * 0.1, v.to).then((e) => { if (!dead) setEvents(e) }, () => {})
    }
    const t0 = window.setTimeout(load, 300)
    const id = window.setInterval(load, 15_000)
    // A snapshot (first data, a seek, back to live) can bring new events: reload soon after it, coalesced.
    let soon: number | undefined
    const off = vessels.subscribe((_c, _r, f) => { if (f.type === 'snapshot') { window.clearTimeout(soon); soon = window.setTimeout(load, 300) } })
    return () => { dead = true; off(); window.clearTimeout(t0); window.clearTimeout(soon); window.clearInterval(id) }
  }, [rangeKey])

  if (!width) return null
  const span = spanOf(view)
  const x = (t: number) => ((t - view.from) / span) * width
  const shown = new Set<number>([...(vessels.watchlist?.entries.map((e) => e.mmsi) ?? []), ...windows.map((w) => w.mmsi)])
  const visible = (e: TimelineEvent) => !('mmsi' in e) || shown.has(e.mmsi)
  const seekOpen = (t: number, mmsi?: number) => { replay.seek(t); if (mmsi) openShip(mmsi) }

  // Gaps: spans in two lanes.
  const laneEnd = [-Infinity, -Infinity]
  const gaps = events.filter((e): e is Extract<TimelineEvent, { kind: 'gap' }> => e.kind === 'gap' && visible(e))
    .sort((a, b) => a.start_ts - b.start_ts).map((g) => {
      const end = g.end_ts ?? view.to
      const lane = laneEnd[0] <= g.start_ts ? 0 : 1
      laneEnd[lane] = Math.max(laneEnd[lane], end)
      return { g, lane, x0: x(g.start_ts), x1: x(end) }
    }).filter((s) => s.x1 >= 0 && s.x0 <= width)

  // Point markers, merged into a count when closer than 6 px.
  type Pt = Exclude<TimelineEvent, { kind: 'gap' | 'coverage' }>
  const pts = events.filter((e): e is Pt => e.kind !== 'gap' && e.kind !== 'coverage' && visible(e))
    .map((e) => ({ e, px: x(e.ts) })).filter((p) => p.px >= 0 && p.px <= width).sort((a, b) => a.px - b.px)
  const groups: { px: number; items: Pt[] }[] = []
  for (const p of pts) {
    const last = groups[groups.length - 1]
    if (last && p.px - last.px < MERGE_PX && p.e.kind !== 'freeze' && last.items[0].kind !== 'freeze') last.items.push(p.e)
    else groups.push({ px: p.px, items: [p.e] })
  }
  const cov = events.filter((e): e is Extract<TimelineEvent, { kind: 'coverage' }> => e.kind === 'coverage')

  return (
    <>
      <div className="tl-cov" aria-hidden>
        {cov.map((c) => {
          const a = Math.max(0, x(c.start_ts)), b = Math.min(width, x(c.end_ts))
          return b > a ? <i key={c.id} className={`tl-cov-${c.state}`} style={{ left: a, width: b - a }} /> : null
        })}
      </div>
      {gaps.map(({ g, lane, x0, x1 }) => (
        <button key={g.id} className={`tl-marker tl-gap lane${lane}${g.end_ts ? '' : ' open'}`}
          style={{ left: Math.max(0, x0), width: Math.max(4, Math.min(width, x1) - Math.max(0, x0)) }}
          aria-label={`No AIS received from ${fmtTime(g.start_ts)}${g.end_ts ? ` to ${fmtTime(g.end_ts)}` : ', still silent'}, MMSI ${g.mmsi}`}
          onClick={() => seekOpen(g.start_ts, g.mmsi)} />
      ))}
      {groups.map(({ px, items }) => {
        const e = items[0]
        if (items.length > 1) {
          return <button key={`${e.id}+${items.length}`} className="tl-marker tl-count" style={{ left: px }}
            aria-label={`${items.length} events near ${fmtTime(e.ts)}`} onClick={() => seekOpen(e.ts)}>{items.length}</button>
        }
        const label = e.kind === 'spoof' ? 'Possible spoofing' : e.kind === 'meeting' ? 'Meeting, two ships alongside'
          : e.kind === 'freeze' ? 'Forecast frozen and committed' : `Forecast outcome: ${e.label === 'hit' ? 'went silent' : e.label === 'miss' ? 'stayed heard' : 'not scored'}`
        const cls = e.kind === 'outcome' ? `tl-outcome ${e.label}` : `tl-${e.kind}`
        const run = e.kind === 'freeze' ? () => forecastUi.set({ checkOpen: true }) : () => seekOpen(e.ts, 'mmsi' in e ? e.mmsi : undefined)
        return <button key={e.id} className={`tl-marker ${cls}`} style={{ left: px }} aria-label={`${label}, ${fmtTime(e.ts)}`} title={`${label} · ${fmtTime(e.ts)}`} onClick={run} />
      })}
    </>
  )
}

interface Item { key: string; label: string; checked: boolean; run: () => void; keepOpen?: boolean }
function Menu({ label, items, onClose }: { label: string; items: Item[]; onClose: () => void }) {
  const ref = useRef<HTMLDivElement>(null)
  useEffect(() => {
    ref.current?.querySelector<HTMLButtonElement>('[aria-checked=true], button')?.focus()
    const away = (e: PointerEvent) => { if (!ref.current?.parentElement?.contains(e.target as Node)) onClose() }
    window.addEventListener('pointerdown', away)
    return () => window.removeEventListener('pointerdown', away)
  }, [onClose])
  const onKey = (e: React.KeyboardEvent) => {
    const btns = [...ref.current!.querySelectorAll<HTMLButtonElement>('button')]
    const i = btns.indexOf(document.activeElement as HTMLButtonElement)
    if (e.key === 'Escape') { onClose(); (ref.current?.previousElementSibling as HTMLElement | null)?.focus() }
    else if (e.key === 'ArrowDown' || e.key === 'ArrowUp') btns[(i + (e.key === 'ArrowDown' ? 1 : btns.length - 1)) % btns.length]?.focus()
    else return
    e.preventDefault()
  }
  return (
    <div ref={ref} className="tl-pop" role="menu" aria-label={label} onKeyDown={onKey}>
      {items.map((it) => (
        <button key={it.key} role="menuitemradio" aria-checked={it.checked} onClick={() => { it.run(); if (!it.keepOpen) onClose() }}>{it.label}</button>
      ))}
    </div>
  )
}

// UTC from/to fields, clamped to what the log holds (status.replay) when known.
function CustomRange({ view, onApply, onClose }: { view: View; onApply: (r: TimeRange) => void; onClose: () => void }) {
  const log = ui.use((s) => s.feed.replay)
  const iso = (t: number) => new Date(t).toISOString().slice(0, 16)
  const [from, setFrom] = useState(iso(view.from))
  const [to, setTo] = useState(iso(view.to))
  const apply = (e: React.FormEvent) => {
    e.preventDefault()
    let a = Date.parse(from + 'Z'), b = Date.parse(to + 'Z')
    if (log) { a = Math.max(a, log.from_ts); b = Math.min(b, Math.max(log.to_ts, Date.now())) }
    if (!(b - a >= ZOOM_MIN)) return
    onApply({ from_ts: a, to_ts: Math.min(b, a + ZOOM_MAX) })
  }
  return (
    <form className="tl-pop tl-custom" role="dialog" aria-label="Custom range (UTC)" onSubmit={apply} onKeyDown={(e) => e.key === 'Escape' && onClose()}>
      <label>From (UTC)<input type="datetime-local" value={from} onChange={(e) => setFrom(e.target.value)} autoFocus /></label>
      <label>To (UTC)<input type="datetime-local" value={to} onChange={(e) => setTo(e.target.value)} /></label>
      <div><button type="button" className="tl-btn tl-text" onClick={onClose}>Cancel</button><button className="tl-btn tl-text">Apply</button></div>
    </form>
  )
}

const PlayIcon = () => <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden><path d="M2 1l9 5-9 5z" fill="currentColor" /></svg>
const PauseIcon = () => <svg width="12" height="12" viewBox="0 0 12 12" aria-hidden><path d="M2 1h3v10H2zM7 1h3v10H7z" fill="currentColor" /></svg>
