"""The two new tables (observations, source_windows) and the idempotent writes into them and into statics.

Nothing here alters an existing table. On a database that already runs dvm/store.py the new DDL only creates
objects that do not exist yet (IF NOT EXISTS everywhere), so it is safe to run on every start-up.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime, timezone
from typing import Iterable

import asyncpg

from dvm.models import VesselStatic
from dvm.sources.common import Observation

log = logging.getLogger(__name__)

OBS_CHUNK = "7 days"   # delayed sources span weeks to years; live-sized 15-minute chunks would explode

SCHEMA = f"""
CREATE TABLE IF NOT EXISTS observations (
  time timestamptz NOT NULL, id text NOT NULL, src text NOT NULL, kind text NOT NULL,
  ts bigint NOT NULL, end_ts bigint, recv_ts bigint NOT NULL, available_ts bigint NOT NULL,
  mmsi integer, lat double precision, lon double precision,
  min_lon double precision, min_lat double precision, max_lon double precision, max_lat double precision,
  cell_deg real, value double precision, n integer, matched boolean, geom jsonb,
  attrs jsonb NOT NULL DEFAULT '{{}}', q text[] NOT NULL DEFAULT '{{}}'
);
SELECT create_hypertable('observations', by_range('time', INTERVAL '{OBS_CHUNK}'), if_not_exists => TRUE);
CREATE UNIQUE INDEX IF NOT EXISTS observations_id_time ON observations (id, time);
CREATE INDEX IF NOT EXISTS observations_kind_time ON observations (kind, time DESC);
CREATE INDEX IF NOT EXISTS observations_mmsi_time ON observations (mmsi, time DESC) WHERE mmsi IS NOT NULL;
CREATE INDEX IF NOT EXISTS observations_available ON observations (available_ts);

CREATE TABLE IF NOT EXISTS source_windows (
  src text NOT NULL, stream text NOT NULL, region text NOT NULL, start_ts bigint NOT NULL, end_ts bigint NOT NULL,
  fetched_at bigint NOT NULL, first_fetched_at bigint NOT NULL, rows integer NOT NULL, status text NOT NULL,
  error text, PRIMARY KEY (src, stream, region, start_ts)
);
"""

OBS_COLS = ["time", "id", "src", "kind", "ts", "end_ts", "recv_ts", "available_ts", "mmsi", "lat", "lon",
            "min_lon", "min_lat", "max_lon", "max_lat", "cell_deg", "value", "n", "matched", "geom", "attrs", "q"]

# A provider may revise a row (an open event's end, a day's hours as late data lands). Keep the first recv_ts and
# available_ts, so "what did we know at T" stays answerable; take the provider's latest numbers otherwise.
UPSERT_OBS = f"""
INSERT INTO observations ({', '.join(OBS_COLS)})
VALUES ({', '.join(f'${i}' for i in range(1, len(OBS_COLS) + 1))})
ON CONFLICT (id, time) DO UPDATE SET end_ts = EXCLUDED.end_ts, value = EXCLUDED.value, n = EXCLUDED.n,
  matched = EXCLUDED.matched, geom = EXCLUDED.geom, attrs = EXCLUDED.attrs, lat = EXCLUDED.lat, lon = EXCLUDED.lon,
  min_lon = EXCLUDED.min_lon, min_lat = EXCLUDED.min_lat, max_lon = EXCLUDED.max_lon, max_lat = EXCLUDED.max_lat
WHERE (observations.end_ts, observations.value, observations.n, observations.attrs)
  IS DISTINCT FROM (EXCLUDED.end_ts, EXCLUDED.value, EXCLUDED.n, EXCLUDED.attrs)
"""

# statics has no unique key, so idempotency is a NOT EXISTS check on (mmsi, time, src): one row per vessel and day.
STATIC_COLS = ["time", "mmsi", "ts", "recv_ts", "imo", "name", "callsign", "ship_type", "type_group",
               "dim_a_m", "dim_b_m", "dim_c_m", "dim_d_m", "length_m", "beam_m", "draught_m",
               "destination", "eta_utc", "mid", "flag_iso2", "src", "q"]
_STATIC_TYPES = ["timestamptz", "integer", "bigint", "bigint", "integer", "text", "text", "smallint", "text",
                 "smallint", "smallint", "smallint", "smallint", "smallint", "smallint", "real",
                 "text", "bigint", "smallint", "text", "text", "text[]"]
INSERT_STATIC = f"""
INSERT INTO statics ({', '.join(STATIC_COLS)})
SELECT {', '.join(f'${i}::{t}' for i, t in enumerate(_STATIC_TYPES, 1))}
WHERE NOT EXISTS (SELECT 1 FROM statics WHERE mmsi = $2 AND time = $1 AND src = $21)
"""

UPSERT_WINDOW = """
INSERT INTO source_windows (src, stream, region, start_ts, end_ts, fetched_at, first_fetched_at, rows, status, error)
VALUES ($1, $2, $3, $4, $5, $6, $6, $7, $8, $9)
ON CONFLICT (src, stream, region, start_ts) DO UPDATE SET end_ts = EXCLUDED.end_ts, fetched_at = EXCLUDED.fetched_at,
  rows = EXCLUDED.rows, status = EXCLUDED.status, error = EXCLUDED.error
"""


def _dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, timezone.utc)


def obs_args(o: Observation) -> tuple:
    b = o.bbox or (None, None, None, None)
    return (_dt(o.ts), o.id, o.src, o.kind, o.ts, o.end_ts, o.recv_ts, o.available_ts, o.mmsi, o.lat, o.lon,
            *b, o.cell_deg, o.value, o.n, o.matched, json.dumps(o.geom) if o.geom is not None else None,
            json.dumps(o.attrs, separators=(",", ":")), list(o.q))


def static_args(s: VesselStatic) -> tuple:
    return (_dt(s.ts), *(getattr(s, c) for c in STATIC_COLS[1:]))


# Columnstore: order by kind, then time, no segment-by (rows per kind and chunk are few thousand, as for positions).
# Chunks compress 30 days after their range ends, so recent days that providers still revise stay row-store;
# backfilled history compresses on the next policy run. Each step is best-effort, like store.SETUP.
SETUP = [
    "DO $$ BEGIN IF NOT (SELECT compression_enabled FROM timescaledb_information.hypertables "
    "WHERE hypertable_name = 'observations') THEN ALTER TABLE observations SET (timescaledb.enable_columnstore = true, "
    "timescaledb.segmentby = '', timescaledb.orderby = 'kind, time'); END IF; END $$",
    "CALL add_columnstore_policy('observations', after => interval '30 days', if_not_exists => true)",
]


async def setup(con: asyncpg.Connection) -> None:
    await con.execute(SCHEMA)
    for sql in SETUP:
        try:
            await con.execute(sql)
        except asyncpg.PostgresError as e:
            log.warning("observations setup step failed, continuing without it: %s", e)


async def db_size_bytes(con) -> int:
    return await con.fetchval("SELECT pg_database_size(current_database())")


async def write_observations(con: asyncpg.Connection, obs: Iterable[Observation]) -> int:
    rows = [obs_args(o) for o in obs]
    if rows:
        await con.executemany(UPSERT_OBS, rows)
    return len(rows)


async def write_statics(con: asyncpg.Connection, statics: Iterable[VesselStatic]) -> int:
    rows = [static_args(s) for s in statics]
    if rows:
        await con.executemany(INSERT_STATIC, rows)
    return len(rows)


async def record_window(con, src: str, stream: str, region: str, start_ts: int, end_ts: int, fetched_at: int,
                        rows: int, status: str, error: str | None = None) -> None:
    await con.execute(UPSERT_WINDOW, src, stream, region, start_ts, end_ts, fetched_at, rows, status, error)


async def get_window(con, src: str, stream: str, region: str, start_ts: int):
    return await con.fetchrow("SELECT * FROM source_windows WHERE src=$1 AND stream=$2 AND region=$3 AND start_ts=$4",
                              src, stream, region, start_ts)
