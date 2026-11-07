"""Tiger Data (Tiger Cloud, TimescaleDB): positions and statics hypertables, written in batches with COPY.

Off the hot path: records are buffered and copied once a second. If the database is down the
buffer is capped and the raw JSONL log stays the source of truth for a later backfill.
"""
from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

import asyncpg

from dvm.models import PositionReport, Record, VesselStatic

log = logging.getLogger(__name__)

# `time` (timestamptz, = ts) is the partition column, as Tiger's docs recommend; ts and recv_ts stay epoch ms per 06.
SCHEMA = """
CREATE TABLE IF NOT EXISTS positions (
  time timestamptz NOT NULL, mmsi integer NOT NULL, ts bigint NOT NULL, recv_ts bigint NOT NULL,
  lat double precision NOT NULL, lon double precision NOT NULL,
  sog_kn real, cog_deg real, heading_deg smallint, nav_status smallint,
  cls text NOT NULL, msg_type smallint NOT NULL, ts_quality text NOT NULL, src text NOT NULL,
  q text[] NOT NULL DEFAULT '{}'
);
SELECT create_hypertable('positions', by_range('time'), if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS positions_mmsi_time ON positions (mmsi, time DESC);

CREATE TABLE IF NOT EXISTS statics (
  time timestamptz NOT NULL, mmsi integer NOT NULL, ts bigint NOT NULL, recv_ts bigint NOT NULL,
  imo integer, name text, callsign text, ship_type smallint, type_group text NOT NULL,
  dim_a_m smallint, dim_b_m smallint, dim_c_m smallint, dim_d_m smallint, length_m smallint, beam_m smallint,
  draught_m real, destination text, eta_utc bigint, mid smallint NOT NULL, flag_iso2 text,
  src text NOT NULL, q text[] NOT NULL DEFAULT '{}'
);
SELECT create_hypertable('statics', by_range('time'), if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS statics_mmsi_time ON statics (mmsi, time DESC);
"""

POS_COLS = ["mmsi", "ts", "recv_ts", "lat", "lon", "sog_kn", "cog_deg", "heading_deg", "nav_status",
            "cls", "msg_type", "ts_quality", "src", "q"]
STATIC_COLS = ["mmsi", "ts", "recv_ts", "imo", "name", "callsign", "ship_type", "type_group",
               "dim_a_m", "dim_b_m", "dim_c_m", "dim_d_m", "length_m", "beam_m", "draught_m",
               "destination", "eta_utc", "mid", "flag_iso2", "src", "q"]
MAX_BUFFER = 200_000


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
        self.pool = await asyncpg.create_pool(self.url, min_size=1, max_size=2, command_timeout=60)
        async with self.pool.acquire() as con:
            await con.execute(SCHEMA)
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
