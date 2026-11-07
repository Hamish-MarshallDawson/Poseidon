"""Tiger Data (Tiger Cloud, TimescaleDB): positions and statics hypertables, written in batches with COPY.

Off the hot path: records are buffered and copied once a second. If the database is down the
buffer is capped and the raw JSONL log stays the source of truth for a later backfill.
"""
from __future__ import annotations

import asyncio
import json
import logging
from datetime import datetime, timezone

import asyncpg

from dvm.models import PositionReport, Record, VesselStatic

log = logging.getLogger(__name__)

# `time` (timestamptz, = ts) is the partition column, as Tiger's docs recommend; ts and recv_ts stay epoch ms per 06.
# Chunk size is PROVISIONAL (Hamish, 7 Nov): 15 minutes so compression shows on live data within the hackathon.
# Jake may change it once he settles the data model; existing tables move with `python -m dvm.rechunk`.
CHUNK_INTERVAL = "15 minutes"

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS positions (
  time timestamptz NOT NULL, mmsi integer NOT NULL, ts bigint NOT NULL, recv_ts bigint NOT NULL,
  lat double precision NOT NULL, lon double precision NOT NULL,
  sog_kn real, cog_deg real, heading_deg smallint, nav_status smallint,
  cls text NOT NULL, msg_type smallint NOT NULL, ts_quality text NOT NULL, src text NOT NULL,
  q text[] NOT NULL DEFAULT '{{}}'
);
SELECT create_hypertable('positions', by_range('time', INTERVAL '{CHUNK_INTERVAL}'), if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS positions_mmsi_time ON positions (mmsi, time DESC);

CREATE TABLE IF NOT EXISTS statics (
  time timestamptz NOT NULL, mmsi integer NOT NULL, ts bigint NOT NULL, recv_ts bigint NOT NULL,
  imo integer, name text, callsign text, ship_type smallint, type_group text NOT NULL,
  dim_a_m smallint, dim_b_m smallint, dim_c_m smallint, dim_d_m smallint, length_m smallint, beam_m smallint,
  draught_m real, destination text, eta_utc bigint, mid smallint NOT NULL, flag_iso2 text,
  src text NOT NULL, q text[] NOT NULL DEFAULT '{{}}'
);
SELECT create_hypertable('statics', by_range('time', INTERVAL '{CHUNK_INTERVAL}'), if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS statics_mmsi_time ON statics (mmsi, time DESC);

-- Detector, forecast and evaluation tables (06 sections 2.4, 2.7, 2.10). All append-only: a gap update is a new
-- version row, and a score is never changed after it is written, so the forecast frozen at a time stays checkable.
-- mmsi is the only vessel ID (Jake, 7 Nov): no identity table, names come from the latest statics row for the mmsi.
CREATE TABLE IF NOT EXISTS gaps (
  id text NOT NULL, version integer NOT NULL, mmsi integer NOT NULL, state text NOT NULL,
  start_ts bigint NOT NULL, end_ts bigint, detected_at bigint NOT NULL, duration_s integer NOT NULL,
  expected_interval_s real, last_lat double precision NOT NULL, last_lon double precision NOT NULL,
  last_sog_kn real, last_cog_deg real, last_nav_status smallint, next_lat double precision, next_lon double precision,
  implied_speed_kn real, draught_before_m real, draught_after_m real,
  neighbours_heard integer NOT NULL, neighbours_baseline integer NOT NULL, cell_id text NOT NULL,
  coverage_flag text NOT NULL, src text NOT NULL, gfw_intentional boolean, q text[] NOT NULL DEFAULT '{{}}',
  PRIMARY KEY (id, version)
);
CREATE INDEX IF NOT EXISTS gaps_mmsi_start ON gaps (mmsi, start_ts);
CREATE INDEX IF NOT EXISTS gaps_detected_at ON gaps (detected_at);

-- `time` (= made_at) partitions it; a unique index on a hypertable must include the partition column.
CREATE TABLE IF NOT EXISTS scores (
  time timestamptz NOT NULL, id text NOT NULL, mmsi integer NOT NULL, target text NOT NULL, made_at bigint NOT NULL,
  horizon_s integer NOT NULL, p double precision NOT NULL, model_version text NOT NULL, feature_version text NOT NULL,
  features jsonb NOT NULL, contrib jsonb, mode text NOT NULL
);
SELECT create_hypertable('scores', by_range('time', INTERVAL '1 hour'), if_not_exists => TRUE);
CREATE UNIQUE INDEX IF NOT EXISTS scores_id_time ON scores (id, time);
CREATE INDEX IF NOT EXISTS scores_mmsi_time ON scores (mmsi, time DESC);
CREATE INDEX IF NOT EXISTS scores_time_p ON scores (time, p DESC);

CREATE TABLE IF NOT EXISTS outcomes (
  score_id text PRIMARY KEY, mmsi integer NOT NULL, target text NOT NULL, made_at bigint NOT NULL,
  horizon_s integer NOT NULL, resolved_at bigint NOT NULL, label boolean, censored text, event_id text, lead_s integer
);
CREATE INDEX IF NOT EXISTS outcomes_made_at ON outcomes (made_at);

CREATE OR REPLACE FUNCTION dvm_append_only() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN RAISE EXCEPTION '% is append-only: write a new row instead of %', TG_TABLE_NAME, TG_OP; END $$;
CREATE OR REPLACE TRIGGER gaps_append_only BEFORE UPDATE OR DELETE ON gaps
  FOR EACH ROW EXECUTE FUNCTION dvm_append_only();
CREATE OR REPLACE TRIGGER scores_append_only BEFORE UPDATE OR DELETE ON scores
  FOR EACH ROW EXECUTE FUNCTION dvm_append_only();
CREATE OR REPLACE TRIGGER outcomes_append_only BEFORE UPDATE OR DELETE ON outcomes
  FOR EACH ROW EXECUTE FUNCTION dvm_append_only();
"""

# Run after SCHEMA on every start-up, one statement per execute(): asyncpg sends a multi-statement string as one
# transaction block, and a continuous aggregate can't be created inside one. Each statement is idempotent.
# set_chunk_time_interval keeps an existing database on CHUNK_INTERVAL (it only affects chunks created later).
SETUP = [
    f"SELECT set_chunk_time_interval('positions', interval '{CHUNK_INTERVAL}')",
    f"SELECT set_chunk_time_interval('statics', interval '{CHUNK_INTERVAL}')",
    # Not segmented by mmsi: at ~3,000 rows a minute over ~7,000 ships a 1-hour chunk holds about a dozen rows per
    # ship, and segmenting by mmsi made the compressed chunk BIGGER (0.6x). Ordering by mmsi, time gives 4.3x.
    # Only while columnstore is off: changing it once chunks are compressed is refused, and a restart must not trip.
    "DO $$ BEGIN IF NOT (SELECT compression_enabled FROM timescaledb_information.hypertables "
    "WHERE hypertable_name = 'positions') THEN ALTER TABLE positions SET (timescaledb.enable_columnstore = true, "
    "timescaledb.segmentby = '', timescaledb.orderby = 'mmsi, time'); END IF; END $$",
    # Only while columnstore is off: changing it once chunks are compressed is refused, and a restart must not trip.
    "DO $$ BEGIN IF NOT (SELECT compression_enabled FROM timescaledb_information.hypertables "
    "WHERE hypertable_name = 'statics') THEN ALTER TABLE statics SET (timescaledb.enable_columnstore = true, "
    "timescaledb.segmentby = '', timescaledb.orderby = 'mmsi, time'); END IF; END $$",
    "CALL add_columnstore_policy('positions', after => interval '1 hour', if_not_exists => true)",
    "CALL add_columnstore_policy('statics', after => interval '1 hour', if_not_exists => true)",
    # The first coverage_1m had no cls column. Drop that version so the next statement rebuilds it from positions.
    "DO $$ BEGIN IF EXISTS (SELECT FROM timescaledb_information.continuous_aggregates WHERE view_name = 'coverage_1m') "
    "AND NOT EXISTS (SELECT FROM information_schema.columns WHERE table_name = 'coverage_1m' AND column_name = 'cls') "
    "THEN DROP MATERIALIZED VIEW coverage_1m; END IF; END $$",
    # Per-cell coverage baseline (06 section 2.9): separates dark ships from coverage holes. Real-time aggregation on.
    # Split by cls: gaps and the forecast are Class A only, and short-range Class B makes a cell look healthier.
    # WITH DATA fills the history once, at creation; the policy keeps the last 2 h fresh.
    """CREATE MATERIALIZED VIEW IF NOT EXISTS coverage_1m
       WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
       SELECT time_bucket('1 minute', time) AS bucket, floor(lat * 10)::int AS lat_bin, floor(lon * 10)::int AS lon_bin,
              cls, count(DISTINCT mmsi)::int AS ships, count(*)::int AS msgs
       FROM positions GROUP BY 1, 2, 3, 4 WITH DATA""",
    "SELECT add_continuous_aggregate_policy('coverage_1m', start_offset => interval '2 hours', "
    "end_offset => interval '1 minute', schedule_interval => interval '1 minute', if_not_exists => true)",
    # Hourly cells for the hour-of-day expected_vessels baseline (06 section 2.9); kept for the whole run.
    # Built on positions, not on coverage_1m: distinct ships per hour can't be summed from per-minute distinct counts.
    """CREATE MATERIALIZED VIEW IF NOT EXISTS coverage_1h
       WITH (timescaledb.continuous, timescaledb.materialized_only = false) AS
       SELECT time_bucket('1 hour', time) AS bucket, floor(lat * 10)::int AS lat_bin, floor(lon * 10)::int AS lon_bin,
              cls, count(DISTINCT mmsi)::int AS ships, count(*)::int AS msgs
       FROM positions GROUP BY 1, 2, 3, 4 WITH DATA""",
    "SELECT add_continuous_aggregate_policy('coverage_1h', start_offset => interval '3 hours', "
    "end_offset => interval '1 hour', schedule_interval => interval '15 minutes', if_not_exists => true)",
]

# Rebuilding an aggregate WITH DATA over hours of positions can take minutes; the pool's 60 s default is too short.
SETUP_TIMEOUT_S = 900


async def setup(con: asyncpg.Connection) -> None:
    """Create the tables and Tiger Data objects. Safe to run again.

    The tables must exist; the extras (columnstore, policies, aggregate) are best-effort, so a problem with one is
    logged and never stops positions being written.
    """
    await con.execute(SCHEMA)
    for sql in SETUP:
        try:
            await con.execute(sql, timeout=SETUP_TIMEOUT_S)
        except asyncpg.PostgresError as e:
            log.warning("Tiger Data setup step failed, continuing without it: %s (%s)", e, sql.split("(")[0][:60])

POS_COLS = ["mmsi", "ts", "recv_ts", "lat", "lon", "sog_kn", "cog_deg", "heading_deg", "nav_status",
            "cls", "msg_type", "ts_quality", "src", "q"]
STATIC_COLS = ["mmsi", "ts", "recv_ts", "imo", "name", "callsign", "ship_type", "type_group",
               "dim_a_m", "dim_b_m", "dim_c_m", "dim_d_m", "length_m", "beam_m", "draught_m",
               "destination", "eta_utc", "mid", "flag_iso2", "src", "q"]
MAX_BUFFER = 200_000

# Columns the detector, scorer and evaluator write, in 06 field names. scores also gets `time` from made_at.
APPEND_COLS = {
    "gaps": ["id", "version", "mmsi", "state", "start_ts", "end_ts", "detected_at", "duration_s",
             "expected_interval_s", "last_lat", "last_lon", "last_sog_kn", "last_cog_deg", "last_nav_status",
             "next_lat", "next_lon", "implied_speed_kn", "draught_before_m", "draught_after_m",
             "neighbours_heard", "neighbours_baseline", "cell_id", "coverage_flag", "src", "gfw_intentional", "q"],
    "scores": ["id", "mmsi", "target", "made_at", "horizon_s", "p", "model_version", "feature_version",
               "features", "contrib", "mode"],
    "outcomes": ["score_id", "mmsi", "target", "made_at", "horizon_s", "resolved_at", "label", "censored",
                 "event_id", "lead_s"],
}
JSON_COLS = {"features", "contrib"}


def append_sql(table: str) -> str:
    cols = (["time"] if table == "scores" else []) + APPEND_COLS[table]
    return f"INSERT INTO {table} ({', '.join(cols)}) VALUES ({', '.join(f'${i}' for i in range(1, len(cols) + 1))})"


def append_args(table: str, row: dict) -> tuple:
    """One row's INSERT arguments. Missing optional fields become NULL; a missing required one fails in the database."""
    vals = [json.dumps(row[c]) if c in JSON_COLS and row.get(c) is not None else row.get(c)
            for c in APPEND_COLS[table]]
    if table == "gaps" and vals[-1] is None:
        vals[-1] = []
    if table == "scores":
        vals.insert(0, datetime.fromtimestamp(row["made_at"] / 1000, timezone.utc))
    return tuple(vals)


async def append(con: asyncpg.Connection, table: str, rows: list[dict]) -> None:
    """Insert rows into gaps, scores or outcomes, all or none. These tables refuse UPDATE and DELETE."""
    if rows:
        await con.executemany(append_sql(table), [append_args(table, r) for r in rows])


def _row(rec: Record, cols: list[str]) -> tuple:
    return (datetime.fromtimestamp(rec.ts / 1000, timezone.utc), *(getattr(rec, c) for c in cols))


class Store:
    def __init__(self, url: str):
        self.url = url
        self.pool: asyncpg.Pool | None = None
        self.buf: dict[str, list[tuple]] = {"positions": [], "statics": []}
        self.rows_written = 0
        self.dropped = 0
        self.last_error: str | None = None

    def add(self, rec: Record) -> None:
        table, cols = ("positions", POS_COLS) if isinstance(rec, PositionReport) else ("statics", STATIC_COLS)
        buf = self.buf[table]
        buf.append(_row(rec, cols))
        if len(buf) > MAX_BUFFER:   # database down for a long time: keep the newest, the JSONL log has the rest
            self.dropped += len(buf) - MAX_BUFFER
            del buf[: len(buf) - MAX_BUFFER]

    async def _connect(self) -> None:
        pool = await asyncpg.create_pool(self.url, min_size=1, max_size=2, command_timeout=60)
        try:   # set the pool only once setup has worked, so a failed setup is retried, not half-used
            async with pool.acquire() as con:
                await setup(con)
        except Exception:
            await pool.close()
            raise
        self.pool = pool
        log.info("Tiger Data connected; positions and statics hypertables ready")

    async def flush(self) -> None:
        for table, cols in (("positions", POS_COLS), ("statics", STATIC_COLS)):
            rows = self.buf[table]
            if not rows:
                continue
            self.buf[table] = []
            try:
                async with self.pool.acquire() as con:
                    await con.copy_records_to_table(table, records=rows, columns=["time", *cols])
                self.rows_written += len(rows)
                self.last_error = None
            except Exception as e:  # any failure (network, auth, schema) must keep the rows and the loop alive
                self.buf[table] = rows + self.buf[table]   # retry next tick
                self.last_error = f"{type(e).__name__}: {e}"
                log.warning("Tiger Data write failed, will retry: %s", self.last_error)
                return

    async def run(self) -> None:
        backoff = 2
        while self.pool is None:
            try:
                await self._connect()
            except Exception as e:  # bad URL, network, auth: keep retrying, ingest and the map carry on
                self.last_error = f"{type(e).__name__}: {e}"
                log.warning("Tiger Data connect failed (retry in %ss): %s", backoff, self.last_error)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
        while True:
            await asyncio.sleep(1)
            await self.flush()

    async def close(self) -> None:
        if self.pool:
            await self.flush()
            await self.pool.close()
