import { adapter } from '../data/index'
import { createStore } from '../store/store'
import { nextWindowLetter, ui } from '../store/ui'
import { vessels } from '../store/vessels'

// The replay controller owns the shown clock. In live it runs at wall speed from the last frame; in replay while playing
// it runs at `speed` between the server's 1 Hz deltas. Drift is absorbed by a soft rate correction (aim to meet the next
// frame) so the clock never jumps backwards between frames, and it never runs more than 1.5 frame periods past the data.
// rAF consumers (map interpolation, ghost growth) call shownNow(); ui.feed.now_ts gets the same clock at 10 Hz.

let anchorTs = Date.now()
let anchorPerf = performance.now()
let rate = 1                // shown ms per wall ms
let lastFrameTs = 0

function nominal(): number {
  const f = ui.get().feed
  return f.mode === 'live' ? 1 : f.paused ? 0 : f.speed
}

export function shownNow(): number {
  const t = anchorTs + (performance.now() - anchorPerf) * rate
  return lastFrameTs ? Math.min(t, Math.max(anchorTs, lastFrameTs + 1500 * Math.max(1, nominal()))) : t
}

function anchor(ts: number, r: number) { anchorTs = ts; anchorPerf = performance.now(); rate = r }

// Local UI state for the bar: a seek in flight shows "Loading…".
export const replayUi = createStore({ loading: false })

let inFlight = false
let queued: number | null = null
let inFlightTimer: number | undefined
function settle() {
  inFlight = false
  window.clearTimeout(inFlightTimer)
  if (queued !== null) { const t = queued; queued = null; sendSeek(t) }
  else { replayUi.set({ loading: false }); if (!ui.get().time.dragging) ui.set((s) => ({ time: { ...s.time, dragT: null } })) }
}
function sendSeek(t: number) {
  inFlight = true
  replayUi.set({ loading: true })
  adapter?.send({ type: 'replay', action: 'seek', t: Math.round(t) })
  inFlightTimer = window.setTimeout(settle, 10_000)       // a world seek takes ~5 s; don't wait forever
}

const send = (action: 'play' | 'pause' | 'live' | 'speed', speed?: number) => adapter?.send({ type: 'replay', action, speed })

export const replay = {
  // One request in flight; a newer target replaces the queued one.
  seek(t: number) {
    ui.set((s) => ({ time: { ...s.time, dragT: t } }))
    if (inFlight) queued = t
    else sendSeek(t)
  },
  play() { send('play') },
  pause() { if (ui.get().feed.mode === 'live') replayUi.set({ loading: true }); send('pause') },   // live: server seeks to newest, pauses
  toggle() { const f = ui.get().feed; if (f.mode === 'replay' && f.paused) replay.play(); else replay.pause() },
  speed(x: number) { send('speed', x) },
  live() { queued = null; ui.set((s) => ({ time: { ...s.time, dragT: null } })); send('live') },
}

// shortcut: opens a window by writing ui.windows directly; switch to windows/ openShipWindow(mmsi) when it lands.
export function openShip(mmsi: number) {
  ui.set((s) => s.windows.some((w) => w.mmsi === mmsi) ? { frontMmsi: mmsi } : {
    frontMmsi: mmsi,
    windows: [...s.windows, { mmsi, letter: nextWindowLetter(s.windows), minimised: false, x: 24 + 24 * s.windows.length, y: 80, z: s.windows.length + 1 }],
  })
}

let started = false
export function startClock(): () => void {
  if (started) return () => {}
  started = true
  const offFrames = vessels.subscribe((_c, _r, frame) => {
    const n = nominal()
    const now = shownNow()
    lastFrameTs = frame.now_ts
    if (frame.type === 'snapshot' || n === 0 || Math.abs(now - frame.now_ts) > 2000 * Math.max(1, n)) anchor(frame.now_ts, n)
    else anchor(now, Math.min(2 * n, Math.max(0, (frame.now_ts + n * 1000 - now) / 1000)))
    if (frame.type === 'snapshot') { if (inFlight) settle(); else replayUi.set({ loading: false }) }
  })
  const offUi = ui.subscribe((s, prev) => {
    const a = s.feed, b = prev.feed
    if (a.mode !== b.mode || a.paused !== b.paused || a.speed !== b.speed) {
      anchor(a.mode !== b.mode ? a.now_ts : shownNow(), nominal())
      if (a.mode === 'live' && b.mode === 'replay') { inFlight = false; queued = null; replayUi.set({ loading: false }) }
    }
  })
  let raf = 0
  let lastWrite = 0
  const loop = (perf: number) => {
    raf = requestAnimationFrame(loop)
    if (perf - lastWrite < 100) return
    lastWrite = perf
    const t = Math.floor(shownNow())
    ui.set((s) => (s.feed.now_ts === t ? {} : { feed: { ...s.feed, now_ts: t } }))
  }
  raf = requestAnimationFrame(loop)
  return () => { started = false; offFrames(); offUi(); cancelAnimationFrame(raf) }
}
