import type { ClientMsg, HistoryRange, ObservationQuery, ObservationReply, Outcome, SourcesReply, RiskScore, ServerMsg, TimelineEvent } from '../types'
import type { AdapterOptions, DataAdapter, FeedHandlers, FeedStatus } from './adapter'

// The real backend: ws /ws (Auth0 token as the first message), GET /history/range. Self-contained on purpose
// (no imports from map/ or the stores): it only calls the handlers; data/index.ts wires them to the stores.
// Deltas carry whole VesselView objects, so a message is JSON.parse'd once and handed over as is.

// Collaboration (src/collab/socket.ts) shares this socket: messages this adapter does not know go to onMessage, and
// onOpen fires on every (re)connect after `hello` so the session can be re-joined.
export const collabLink: { onMessage: ((m: unknown) => void) | null; onOpen: (() => void) | null } = { onMessage: null, onOpen: null }

const AUTH_OFF = import.meta.env.DEV && import.meta.env.VITE_AUTH === 'off'   // local dev without Auth0

const MIN_DELAY_MS = 1000
const MAX_DELAY_MS = 15000

export function createLiveAdapter(opts: AdapterOptions): DataAdapter {
  let ws: WebSocket | null = null
  let timer: number | undefined
  let delay = MIN_DELAY_MS
  let disposed = true
  let subscribe: ClientMsg | null = null       // re-sent after a reconnect
  const status: FeedStatus = {
    connected: false, mode: 'live', speed: 1, paused: false, now_ts: Date.now(), replay: null,
    sources: [], stats: { tracked: 0, msgs_per_s: 0, queue_depth: 0 },
  }

  function start(h: FeedHandlers) {
    disposed = false
    const emit = (patch: Partial<FeedStatus>) => { Object.assign(status, patch); h.onStatus({ ...status }) }

    const connect = () => {
      const sock = new WebSocket(opts.wsUrl)
      ws = sock
      let lastSeq: number | null = null
      let stale = false
      // Browsers can't set headers on a WebSocket, so the access token is the first message.
      sock.onopen = () => {
        opts.getToken()
          .then((token) => (token ? sock.send(JSON.stringify({ type: 'auth', token })) : AUTH_OFF ? undefined : sock.close()))
          .catch(() => sock.close())
      }
      sock.onmessage = (ev) => {
        if (stale) return
        let msg: ServerMsg
        try { msg = JSON.parse(ev.data) } catch { return }
        if (lastSeq !== null && msg.seq !== lastSeq + 1) {
          stale = true                                // missed a delta: drop the socket, take a fresh snapshot
          sock.close()
          return
        }
        lastSeq = msg.seq
        delay = MIN_DELAY_MS
        switch (msg.type) {
          case 'hello':
            emit({ connected: true, mode: msg.mode, speed: msg.speed, now_ts: msg.now_ts, sources: msg.sources })
            if (subscribe) sock.send(JSON.stringify(subscribe))
            collabLink.onOpen?.()
            break
          case 'snapshot':
            h.onFrame({ type: 'snapshot', now_ts: msg.now_ts, vessels: msg.vessels, removed: [], gaps: msg.gaps ?? [],
              spoofs: msg.spoofs ?? [], watchlist: msg.watchlist ?? null, coverage: msg.coverage ?? [], trails: msg.trails ?? {} })
            emit({ connected: true, now_ts: msg.now_ts, stats: msg.stats })
            break
          case 'delta':
            h.onFrame({ type: 'delta', now_ts: msg.now_ts, vessels: msg.vessels, removed: msg.removed ?? [], gaps: msg.gaps ?? [],
              spoofs: msg.spoofs ?? [], watchlist: msg.watchlist ?? null })
            emit({ connected: true, now_ts: msg.now_ts, stats: msg.stats })
            break
          case 'watchlist': {
            const { snapshot_ts, entries } = msg
            h.onFrame({ type: 'delta', now_ts: status.now_ts, vessels: [], removed: [], gaps: [], spoofs: [], watchlist: { snapshot_ts, entries } })
            break
          }
          case 'status':
            emit({ connected: true, mode: msg.mode, speed: msg.speed, paused: msg.paused ?? false, now_ts: msg.now_ts,
              sources: msg.sources, replay: msg.replay ?? null })
            break
          case 'ping':
            emit({ connected: true, now_ts: msg.now_ts })
            break
          case 'detail':
            h.onDetail(msg)
            break
          default:
            collabLink.onMessage?.(msg)
        }
      }
      sock.onclose = () => {
        if (ws === sock) ws = null
        emit({ connected: false })
        if (disposed) return
        timer = window.setTimeout(connect, delay)
        delay = Math.min(delay * 2, MAX_DELAY_MS)
      }
    }
    connect()
  }

  // A route that answers 404 or 501 is remembered for the session: it throws at once, so the callers keep their
  // fallback without a request every frame.
  const missing = new Set<string>()
  let reportCheck: Promise<string | null> | undefined
  async function read<T>(path: string, params: Record<string, number>): Promise<T> {
    if (missing.has(path)) throw new Error(`GET ${path}: not available`)
    const token = await opts.getToken()
    const q = new URLSearchParams(Object.entries(params).map(([k, v]) => [k, String(v)])).toString()
    const res = await fetch(`${opts.httpBase}${path}${q ? `?${q}` : ''}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
    if (res.status === 404 || res.status === 501) missing.add(path)
    if (!res.ok) throw new Error(`GET ${path}: ${res.status}`)
    return res.json()
  }
  return {
    isMock: false,
    start,
    stop() {
      disposed = true
      window.clearTimeout(timer)
      ws?.close()
      ws = null
    },
    send(msg) {
      if (msg.type === 'subscribe') subscribe = msg
      if (ws?.readyState === WebSocket.OPEN) ws.send(JSON.stringify(msg))
    },
    async historyRange(): Promise<HistoryRange> {
      const token = await opts.getToken()
      const res = await fetch(`${opts.httpBase}/history/range`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      if (!res.ok) throw new Error(`GET /history/range: ${res.status}`)
      return res.json()
    },
    async track(mmsi, hours) {
      const token = await opts.getToken()
      const res = await fetch(`${opts.httpBase}/track?mmsi=${mmsi}&hours=${Math.min(24, Math.max(1, Math.round(hours)))}`,
        { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      if (!res.ok) throw new Error(`GET /track: ${res.status}`)
      return ((await res.json()) as { track?: [number, number, number][] }).track ?? []
    },
    timeline: (from, to) => read<TimelineEvent[]>('/timeline', { from_ts: from, to_ts: to }),
    scores: (as_of) => read<RiskScore[]>('/scores', as_of == null ? {} : { as_of }),
    outcomes: (from, to) => read<Outcome[]>('/outcomes', { from_ts: from, to_ts: to }),
    async observations(q: ObservationQuery): Promise<ObservationReply> {
      const token = await opts.getToken()
      const p = new URLSearchParams({ kinds: q.kinds.join(','), start: String(q.start), end: String(q.end) })
      if (q.mmsi != null) p.set('mmsi', String(q.mmsi))
      if (q.bbox) p.set('bbox', q.bbox.join(','))
      if (q.limit) p.set('limit', String(q.limit))
      const res = await fetch(`${opts.httpBase}/observations?${p}`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      if (!res.ok) throw Object.assign(new Error(`GET /observations: ${res.status}`), { status: res.status })
      return res.json()
    },
    async sources(): Promise<SourcesReply> {
      const token = await opts.getToken()
      const res = await fetch(`${opts.httpBase}/sources`, { headers: token ? { Authorization: `Bearer ${token}` } : {} })
      if (!res.ok) throw new Error(`GET /sources: ${res.status}`)
      return res.json()
    },
    modelReport() {
      reportCheck ??= (async () => {
        const token = await opts.getToken()
        const headers: HeadersInit = token ? { Authorization: `Bearer ${token}` } : {}
        try {
          let res = await fetch(`${opts.httpBase}/model/report`, { method: 'HEAD', headers })
          if (res.status === 405) res = await fetch(`${opts.httpBase}/model/report`, { headers })
          return res.ok ? `${opts.httpBase}/model/report` : null
        } catch { return null }
      })()
      return reportCheck
    },
  }
}
