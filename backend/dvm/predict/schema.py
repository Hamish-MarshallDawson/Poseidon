"""Prediction ledger tables (#121): additive, append-only like `scores` (the dvm_append_only trigger from store.py).

- `route_predictions`: one row per ship, as_of, horizon and model version. `as_of` is the newest fix the model saw;
  the predicted point is for `as_of + horizon_s`. `base_lat, base_lon` is the dead-reckoning baseline for the same
  time, so every graded row also grades the baseline. `gap_id` is set when the ship was in an open gap.
  `mpa_ids, mpa_share_80, foreign_eez, foreign_share_80` (#157): protected areas the 80% circle touches and the
  share of it inside them; EEZs other than the ship's own (at its last fix) and the share inside those.
- `model_runs`: the training registry mirrored for the backend and the leaderboard. A run gets one row per status
  it reaches (candidate, champion, rejected); the newest row of a run is its status now.
- `outcomes` (store.py) gains nullable columns for route grades: error_m, baseline_error_m, truth_*, in_r80, in_r95,
  truth_source, model_version. Go-dark grades use the existing label/censored columns.
"""
from __future__ import annotations

import asyncpg

SCHEMA = """
CREATE TABLE IF NOT EXISTS route_predictions (
  time timestamptz NOT NULL, id text NOT NULL, mmsi integer NOT NULL, made_at bigint NOT NULL, as_of bigint NOT NULL,
  model_version text NOT NULL, horizon_s integer NOT NULL, lat double precision NOT NULL, lon double precision NOT NULL,
  radius_m_80 real NOT NULL, radius_m_95 real NOT NULL, base_lat double precision NOT NULL,
  base_lon double precision NOT NULL, gap_id text, feature_version text NOT NULL, mode text NOT NULL
);
SELECT create_hypertable('route_predictions', by_range('time', INTERVAL '6 hours'), if_not_exists => TRUE);
CREATE UNIQUE INDEX IF NOT EXISTS route_predictions_id_time ON route_predictions (id, time);
CREATE INDEX IF NOT EXISTS route_predictions_mmsi_time ON route_predictions (mmsi, time DESC);
CREATE INDEX IF NOT EXISTS route_predictions_gap ON route_predictions (gap_id) WHERE gap_id IS NOT NULL;

CREATE TABLE IF NOT EXISTS model_runs (
  run_id text NOT NULL, target text NOT NULL, model text NOT NULL, config jsonb NOT NULL DEFAULT '{}',
  data_hash text, train_from bigint, train_to bigint, metrics jsonb NOT NULL DEFAULT '{}', artifact text,
  proposer text, parent_run text, status text NOT NULL, created_at bigint NOT NULL, recorded_at bigint NOT NULL,
  PRIMARY KEY (run_id, status)
);

-- zone incursion of the 80% circle (#157, dvm/zones/incursion.py); null when the zones were not loaded
ALTER TABLE route_predictions ADD COLUMN IF NOT EXISTS mpa_ids bigint[];
ALTER TABLE route_predictions ADD COLUMN IF NOT EXISTS mpa_share_80 real;
ALTER TABLE route_predictions ADD COLUMN IF NOT EXISTS foreign_eez integer[];
ALTER TABLE route_predictions ADD COLUMN IF NOT EXISTS foreign_share_80 real;

ALTER TABLE outcomes ADD COLUMN IF NOT EXISTS model_version text;
ALTER TABLE outcomes ADD COLUMN IF NOT EXISTS truth_source text;
ALTER TABLE outcomes ADD COLUMN IF NOT EXISTS truth_ts bigint;
ALTER TABLE outcomes ADD COLUMN IF NOT EXISTS truth_lat double precision;
ALTER TABLE outcomes ADD COLUMN IF NOT EXISTS truth_lon double precision;
ALTER TABLE outcomes ADD COLUMN IF NOT EXISTS error_m double precision;
ALTER TABLE outcomes ADD COLUMN IF NOT EXISTS baseline_error_m double precision;
ALTER TABLE outcomes ADD COLUMN IF NOT EXISTS in_r80 boolean;
ALTER TABLE outcomes ADD COLUMN IF NOT EXISTS in_r95 boolean;
CREATE INDEX IF NOT EXISTS outcomes_target_made_at ON outcomes (target, made_at);

CREATE OR REPLACE TRIGGER route_predictions_append_only BEFORE UPDATE OR DELETE ON route_predictions
  FOR EACH ROW EXECUTE FUNCTION dvm_append_only();
CREATE OR REPLACE TRIGGER model_runs_append_only BEFORE UPDATE OR DELETE ON model_runs
  FOR EACH ROW EXECUTE FUNCTION dvm_append_only();
"""

ROUTE_COLS = ["id", "mmsi", "made_at", "as_of", "model_version", "horizon_s", "lat", "lon", "radius_m_80",
              "radius_m_95", "base_lat", "base_lon", "gap_id", "feature_version", "mode", "mpa_ids", "mpa_share_80",
              "foreign_eez", "foreign_share_80"]
RUN_COLS = ["run_id", "target", "model", "config", "data_hash", "train_from", "train_to", "metrics", "artifact",
            "proposer", "parent_run", "status", "created_at", "recorded_at"]
OUTCOME_COLS = ["score_id", "mmsi", "target", "made_at", "horizon_s", "resolved_at", "label", "censored", "event_id",
                "lead_s", "model_version", "truth_source", "truth_ts", "truth_lat", "truth_lon", "error_m",
                "baseline_error_m", "in_r80", "in_r95"]

ROUTE_INSERT = (f"INSERT INTO route_predictions (time, {', '.join(ROUTE_COLS)}) "
                f"VALUES (to_timestamp($3::bigint / 1000.0), {', '.join(f'${i}' for i in range(1, len(ROUTE_COLS) + 1))}) "
                "ON CONFLICT (id, time) DO NOTHING")
RUN_INSERT = (f"INSERT INTO model_runs ({', '.join(RUN_COLS)}) "
              f"VALUES ({', '.join(f'${i}' for i in range(1, len(RUN_COLS) + 1))}) ON CONFLICT DO NOTHING")
OUTCOME_INSERT = (f"INSERT INTO outcomes ({', '.join(OUTCOME_COLS)}) "
                  f"VALUES ({', '.join(f'${i}' for i in range(1, len(OUTCOME_COLS) + 1))}) "
                  "ON CONFLICT (score_id) DO NOTHING")
SCORE_INSERT = ("INSERT INTO scores (time, id, mmsi, target, made_at, horizon_s, p, model_version, feature_version, "
                "features, contrib, mode) VALUES (to_timestamp($4::bigint / 1000.0), $1, $2, $3, $4, $5, $6, $7, $8, $9, "
                "$10, $11) ON CONFLICT (id, time) DO NOTHING")
SCORE_COLS = ["id", "mmsi", "target", "made_at", "horizon_s", "p", "model_version", "feature_version", "features",
              "contrib", "mode"]


async def setup(con: asyncpg.Connection) -> None:
    """Create the ledger tables and columns. Idempotent; needs store.setup to have run (outcomes, the trigger)."""
    await con.execute(SCHEMA)
