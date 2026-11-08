import type { ClientMsg, HistoryRange, ObservationQuery, ObservationReply, Outcome, RiskScore, ServerMsg, SourceStatus, Stats, TimelineEvent } from '../types'
import type { Frame } from '../store/vessels'

// The one data interface the UI talks to. Two implementations:
//   data/live.ts  (map/ agent): the real backend: ws://localhost:8000/ws + Auth0 token, GET /history/range, GET /coverage.
//   data/mock.ts  (timeline/ agent): a clearly labelled mock for what the backend lacks yet (replay, scores, outcomes).
// Swapping to real data later is one change: data/index.ts picks the adapter.

export interface FeedStatus {
  connected: boolean
  mode: 'live' | 'replay'
  speed: number
  paused: boolean
  now_ts: number                                  // the shown moment (replay clock in replay)
  replay: { from_ts: number; to_ts: number } | null
  sources: SourceStatus[]
  stats: Stats
}

export interface FeedHandlers {
  onFrame(frame: Frame): void
  onStatus(status: FeedStatus): void
  onDetail(msg: Extract<ServerMsg, { type: 'detail' }>): void
}

export interface DataAdapter {
  readonly isMock: boolean                        // true when any part of the data is synthetic; the UI labels it
  start(handlers: FeedHandlers): void
  stop(): void
  send(msg: ClientMsg): void                      // detail, replay (play|pause|seek|speed|live), subscribe
  // Reads for the scrub bar and the forecast overlay. Reject with an Error when the backend has no such read yet.
  historyRange(): Promise<HistoryRange>
  timeline(from_ts: number, to_ts: number): Promise<TimelineEvent[]>
  scores(as_of?: number): Promise<RiskScore[]>
  outcomes(from_ts: number, to_ts: number): Promise<Outcome[]>
  // GET /track: one ship's past positions [ts, lon, lat], oldest first, at most one per minute, hours 1..24.
  track(mmsi: number, hours: number): Promise<[number, number, number][]>
  // URL of the backend's model report page when it answers (checked once); null otherwise. Absent on the mock.
  modelReport?(): Promise<string | null>
  // GET /observations. Rejects with an Error whose `status` is the HTTP code (422 = the route needs a bbox).
  observations?(q: ObservationQuery): Promise<ObservationReply>
}

export interface AdapterOptions {
  wsUrl: string
  httpBase: string                                // e.g. http://localhost:8000
  getToken: () => Promise<string | undefined>     // Auth0 access token; sent as the first WS message and as Bearer
}
