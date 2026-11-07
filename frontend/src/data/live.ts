// STAND-IN for the map agent's data/live.ts (branch 40-map-ships), so the timeline branch builds and runs on its own.
// On merge, take the map agent's file. Contract it relies on: createLiveAdapter(opts) only calls the handlers
// passed to start(); it never writes vessels or ui itself (data/index.ts does that wiring).
import type { ClientMsg, HistoryRange, ServerMsg } from '../types'
import type { AdapterOptions, DataAdapter, FeedHandlers, FeedStatus } from './adapter'

const notYet = () => Promise.reject(new Error('not implemented by backend'))

export function createLiveAdapter(opts: AdapterOptions): DataAdapter {
  let ws: WebSocket | null = null
  let timer: number | undefined
  let delay = 1000
  let disposed = false
  let status: FeedStatus = {
    connected: false, mode: 'live', speed: 1, paused: false, now_ts: Date.now(), replay: null, sources: [],
    stats: { tracked: 0, msgs_per_s: 0, queue_depth: 0 },
  }

  function connect(h: FeedHandlers) {
    const sock = new WebSocket(opts.wsUrl)
    ws = sock
    let lastSeq: number | null = null
    let stale = false
    const setStatus = (patch: Partial<FeedStatus>) => { status = { ...status, ...patch }; h.onStatus(status) }
    sock.onopen = () => {
      opts.getToken().then((t) => (t ? sock.send(JSON.stringify({ type: 'auth', token: t })) : sock.close()))
        .catch(() => sock.close())
    }
    sock.onmessage = (ev) => {
      if (stale) return
      const msg = JSON.parse(ev.data) as ServerMsg
      if (lastSeq !== null && msg.seq !== lastSeq + 1) { stale = true; sock.close(); return }   // missed a delta: resnapshot
      lastSeq = msg.seq
      delay = 1000
      switch (msg.type) {
        case 'hello': setStatus({ connected: true, mode: msg.mode, speed: msg.speed, now_ts: msg.now_ts, sources: msg.sources }); break
        case 'status': setStatus({ connected: true, mode: msg.mode, speed: msg.speed, paused: !!msg.paused, now_ts: msg.now_ts,
          sources: msg.sources, replay: msg.replay ?? null }); break
        case 'snapshot': case 'delta':
          h.onFrame({ type: msg.type, now_ts: msg.now_ts, vessels: msg.vessels, removed: msg.type === 'delta' ? msg.removed : [],
            gaps: msg.gaps, spoofs: msg.spoofs, watchlist: msg.watchlist,
            coverage: msg.type === 'snapshot' ? msg.coverage : undefined, trails: msg.type === 'snapshot' ? msg.trails : undefined })
          if (msg.stats) setStatus({ stats: msg.stats })
          break
        case 'detail': h.onDetail(msg); break
      }
    }
    sock.onclose = () => {
      setStatus({ connected: false })
      if (disposed) return
      timer = window.setTimeout(() => connect(h), delay)
      delay = Math.min(delay * 2, 15000)
    }
  }

  return {
    isMock: false,
    start(h) { disposed = false; connect(h) },
    stop() { disposed = true; window.clearTimeout(timer); ws?.close() },
    send(msg: ClientMsg) { if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg)) },
    async historyRange(): Promise<HistoryRange> {
      const token = await opts.getToken()
      const r = await fetch(`${opts.httpBase}/history/range`, { headers: { Authorization: `Bearer ${token}` } })
      if (!r.ok) throw new Error(`history/range ${r.status}`)
      return r.json()
    },
    timeline: notYet, scores: notYet, outcomes: notYet,
  }
}
