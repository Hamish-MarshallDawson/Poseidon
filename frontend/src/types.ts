// Frontend contract types. Mirrors 06-unified-data-model.md section 4.3 (WebSocket) and sections 2.x (records).
// Field names are frozen by the data model; add types here, never rename fields.
export type Status = "active" | "silent" | "gap_open" | "stale";
export type TypeGroup = "tanker" | "cargo" | "passenger" | "fishing" | "tug_special"
  | "military" | "pleasure" | "other" | "unknown";

export interface VesselView {
  mmsi: number; name: string | null; imo: number | null; flag: string | null;
  type_group: TypeGroup; length_m: number | null;
  lat: number; lon: number;
  sog_kn: number | null; cog_deg: number | null; heading_deg: number | null;
  last_ts: number;                 // epoch ms UTC
  status: Status; open_gap_id: string | null;
  risk_p: number | null; risk_rank: number | null;
  sanctioned: boolean; spoof_recent: string[];
  cls?: 'A' | 'B' | null;          // AIS class; missing or null = unknown, drawn as before
}

export interface GapEvent {
  id: string; version: number; mmsi: number; state: "open" | "closed";
  start_ts: number; end_ts: number | null; duration_s: number;
  last_lat: number; last_lon: number; last_sog_kn: number | null; last_cog_deg: number | null;
  next_lat: number | null; next_lon: number | null;
  neighbours_heard: number; neighbours_baseline: number; cell_id: string;
  coverage_flag: "deliberate_candidate" | "coverage_gap" | "own_stall" | "unknown";
  radius_m?: number;               // server-derived, for the ghost circle
  // Route prediction (backend model, optional): centre and 80 % / 95 % radii of where the ship is expected to be.
  pred_lat?: number; pred_lon?: number; pred_r80_m?: number; pred_r95_m?: number;
  pred_horizon_s?: number; pred_made_at?: number; pred_model?: string;
}

// The detail reply's optional route prediction: same fields as the gap, unprefixed (exact shape not final).
export interface RoutePrediction {
  lat?: number; lon?: number; r80_m?: number; r95_m?: number; horizon_s?: number; made_at?: number; model?: string;
}

export interface SpoofEvent {
  id: string; mmsi: number; ts: number;
  type: "jump" | "on_land" | "circling_at_anchor" | "duplicate_mmsi" | "mmsi_change" | "imo_change" | "flag_mismatch";
  severity: number; jamming_suspect: boolean; evidence: Record<string, unknown>;
}

export interface Evidence { kind: "gap" | "spoof" | "sanction" | "score"; id: string; label: string; url?: string }
export interface WatchlistRow {
  rank: number; mmsi: number; name: string | null; p: number;
  decision: "inspect" | "watch" | "none"; prev_rank: number | null;
  reason_codes: string[]; evidence: Evidence[];
}
export interface Watchlist { snapshot_ts: number; entries: WatchlistRow[] }
export interface CoverageCellView { cell_id: string; state: "ok" | "degraded" | "dead"; coverage_score: number }
export interface SourceStatus { src: string; state: "up" | "silent" | "down" | "stall"; msgs_per_s: number }
export interface Stats { tracked: number; msgs_per_s: number; queue_depth: number }

// 06 section 2.7: one forecast row. Append-only on the server, so a frozen forecast stays checkable.
export interface RiskScore {
  id: string; mmsi: number; made_at: number; as_of: number; horizon_s: number;   // 21600 = 6 h
  target: "dark_6h" | "dark_1h" | "dark_24h"; p: number; rank: number | null; mode: "live" | "replay" | "backtest";
  features: Record<string, number>; contrib: Record<string, number>; model_version: string;
}
// 06 section 2.10: what happened after a forecast.
export interface Outcome {
  score_id: string; mmsi: number; made_at: number; resolved_at: number;
  label: "hit" | "miss"; censored: "coverage_gap" | "own_stall" | "data_end" | "already_dark" | null;
  lead_s: number | null;
}
// Markers for the scrub bar track (R2 timeline design). Built from gaps, spoofs, outcomes and feed stalls.
export type TimelineEvent =
  | { kind: "gap"; id: string; mmsi: number; start_ts: number; end_ts: number | null }
  | { kind: "spoof"; id: string; mmsi: number; ts: number }
  | { kind: "meeting"; id: string; mmsi: number; other_mmsi: number; ts: number }
  | { kind: "freeze"; id: string; ts: number }                       // forecast frozen and committed
  | { kind: "outcome"; id: string; mmsi: number; ts: number; label: "hit" | "miss" | "censored" }
  | { kind: "coverage"; id: string; start_ts: number; end_ts: number; state: "data" | "degraded" | "own_stall" | "none" };
export interface HistoryRange { from_ts: number; to_ts: number }

// Statics merged by the server for `detail` (backend live.detail: fields never seen are absent, not null).
export interface StaticDetail {
  mmsi: number; imo?: number; name?: string; callsign?: string; ship_type?: number; type_group?: TypeGroup;
  length_m?: number; beam_m?: number; draught_m?: number; destination?: string; eta_utc?: string; flag_iso2?: string;
}

type Base = { seq: number };
export type ServerMsg =
  | (Base & { type: "hello"; schema: 1; mode: "live" | "replay"; speed: number; now_ts: number;
              sources: SourceStatus[]; bbox: [[number, number], [number, number]] })
  | (Base & { type: "snapshot"; now_ts: number; vessels: VesselView[];
              trails: Record<string, [number, number, number][]>;   // [ts, lon, lat]
              gaps: GapEvent[]; spoofs: SpoofEvent[]; watchlist: Watchlist;
              coverage: CoverageCellView[]; stats: Stats })
  | (Base & { type: "delta"; now_ts: number; vessels: VesselView[]; removed: number[];
              gaps: GapEvent[]; spoofs: SpoofEvent[]; watchlist: Watchlist | null; stats: Stats })
  | (Base & { type: "watchlist" } & Watchlist)
  | (Base & { type: "status"; now_ts: number; mode: "live" | "replay"; speed: number; paused?: boolean;
              sources: SourceStatus[]; replay?: { from_ts: number; to_ts: number } })
  | (Base & { type: "ping"; now_ts: number })
  | (Base & { type: "detail"; mmsi: number; vessel: VesselView; statics: StaticDetail[]; gaps: GapEvent[];
              spoofs: SpoofEvent[]; sanction: unknown | null; score: RiskScore | null; route_prediction?: RoutePrediction | null;
              trail?: [number, number, number][] });   // last 60 min [ts, lon, lat], oldest first

export type ClientMsg =
  | { type: "subscribe"; bbox: [[number, number], [number, number]]; min_status?: Status }
  | { type: "replay"; action: "play" | "pause" | "seek" | "speed" | "live"; t?: number; speed?: number }
  | { type: "detail"; mmsi: number }
  | { type: "session_join"; session_id: string; dev_user?: string }   // collaboration (src/collab/socket.ts)
  | { type: "session_leave" }
  | { type: "auth"; dev_user: string }                                  // local dev only (VITE_AUTH=off)
  | { type: "presence"; viewing: number | null; following: number[]; bbox: [number, number, number, number] | null; private: boolean };
