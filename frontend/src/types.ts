// frontend/src/types.ts (copied from CONTEXT.md section 6.2, path only changed)
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
}

export interface GapEvent {
  id: string; version: number; mmsi: number; state: "open" | "closed";
  start_ts: number; end_ts: number | null; duration_s: number;
  last_lat: number; last_lon: number; last_sog_kn: number | null; last_cog_deg: number | null;
  next_lat: number | null; next_lon: number | null;
  neighbours_heard: number; neighbours_baseline: number; cell_id: string;
  coverage_flag: "deliberate_candidate" | "coverage_gap" | "own_stall" | "unknown";
  radius_m?: number;               // server-derived, for the ghost circle
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
  | (Base & { type: "status"; now_ts: number; mode: "live" | "replay"; speed: number;
              sources: SourceStatus[]; replay?: { from_ts: number; to_ts: number } })
  | (Base & { type: "detail"; mmsi: number; vessel: unknown; statics: unknown[]; gaps: GapEvent[];
              spoofs: SpoofEvent[]; sanction: unknown | null; score: unknown | null });

export type ClientMsg =
  | { type: "subscribe"; bbox: [[number, number], [number, number]]; min_status?: Status }
  | { type: "replay"; action: "play" | "pause" | "seek" | "speed"; t?: number; speed?: number }
  | { type: "detail"; mmsi: number };
