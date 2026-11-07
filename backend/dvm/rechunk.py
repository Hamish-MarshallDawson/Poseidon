"""Move positions and statics to a new chunk size without losing rows: `python -m dvm.rechunk`.

Hypertables can't change the size of existing chunks, so this copies into new hypertables and swaps names:
1. While the backend runs: create `<table>_new` with CHUNK_INTERVAL chunks and copy every row received more
   than 2 minutes ago.
2. It then waits until the backend is stopped (stop it with Ctrl+C, never a kill: dvm/limits.py), copies the rest,
   refuses to go on unless the row counts match, drops coverage_1m (it is tied to the old table), and swaps names.
   The old tables stay as `<table>_old`.
3. Start the backend again: its setup recreates coverage_1m and the columnstore policy on the new tables.
4. `python -m dvm.rechunk --drop-old` drops `<table>_old` once the new tables hold at least as many rows.

Set CHUNK_INTERVAL in dvm/store.py first, so the restarted backend keeps the new size.
"""
from __future__ import annotations

import argparse
import asyncio
import socket
import time

import asyncpg

from dvm import config, limits
from dvm.store import CHUNK_INTERVAL

TABLES = ("positions", "statics")


def backend_running() -> bool:
    """The backend holds the AISStream host lock port while it runs (dvm/limits.py)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    try:
        s.bind(("127.0.0.1", limits.HOST_LOCK_PORT))
        return False
    except OSError:
        return True
    finally:
        s.close()


async def counts(con, suffix: str = "") -> dict[str, int]:
    return {t: await con.fetchval(f"SELECT count(*) FROM {t}{suffix}") for t in TABLES}


async def migrate(con) -> None:
    existing = [r[0] for r in await con.fetch("SELECT tablename FROM pg_tables WHERE tablename = ANY($1)",
                                              [f"{t}_{s}" for t in TABLES for s in ("new", "old")])]
    if existing:
        raise SystemExit(f"Refusing: {existing} already exist from an earlier run. Check them, then drop or rename.")

    cutoff = time.time_ns() // 1_000_000 - 120_000   # rows received before this are surely in the table already
    for t in TABLES:
        await con.execute(f"CREATE TABLE {t}_new (LIKE {t} INCLUDING DEFAULTS INCLUDING CONSTRAINTS)")
        await con.execute(f"SELECT create_hypertable('{t}_new', by_range('time', INTERVAL '{CHUNK_INTERVAL}'))")
        await con.execute(f"CREATE INDEX {t}_mmsi_time_new ON {t}_new (mmsi, time DESC)")
        n = await con.execute(f"INSERT INTO {t}_new SELECT * FROM {t} WHERE recv_ts < $1", cutoff)
        print(f"{t}: copied {n.split()[-1]} rows live into {t}_new ({CHUNK_INTERVAL} chunks)")

    if backend_running():
        print("Now stop the backend with Ctrl+C in its terminal (not a kill). Waiting...", flush=True)
        while backend_running():
            await asyncio.sleep(1)
    paused = time.monotonic()
    print("Backend stopped: copying the rest")
    for t in TABLES:
        n = await con.execute(f"INSERT INTO {t}_new SELECT * FROM {t} WHERE recv_ts >= $1", cutoff)
        print(f"{t}: copied {n.split()[-1]} more rows")
    old, new = await counts(con), await counts(con, "_new")
    if old != new:
        raise SystemExit(f"Refusing to swap: row counts differ, old {old} new {new}. Nothing renamed; "
                         "the backend can be restarted on the old tables.")

    await con.execute("DROP MATERIALIZED VIEW IF EXISTS coverage_1m")   # recreated by the backend's setup
    for t in TABLES:
        await con.execute(f"ALTER TABLE {t} RENAME TO {t}_old")
        await con.execute(f"ALTER INDEX IF EXISTS {t}_mmsi_time RENAME TO {t}_mmsi_time_old")
        await con.execute(f"ALTER TABLE {t}_new RENAME TO {t}")
        await con.execute(f"ALTER INDEX {t}_mmsi_time_new RENAME TO {t}_mmsi_time")
    print(f"Swapped. Rows: {new}. Copy and swap took {time.monotonic() - paused:.1f} s after the stop.")
    print("Start the backend again now (it recreates coverage_1m and the columnstore policy), "
          "then run `python -m dvm.rechunk --drop-old`.")


async def drop_old(con) -> None:
    old, new = await counts(con, "_old"), await counts(con)
    short = {t: (new[t], old[t]) for t in TABLES if new[t] < old[t]}
    if short:
        raise SystemExit(f"Refusing: the new tables have fewer rows than the old ones (new, old): {short}")
    for t in TABLES:
        await con.execute(f"DROP TABLE {t}_old")   # also drops its chunks and compression policy
    print(f"Dropped {', '.join(t + '_old' for t in TABLES)}. Rows now (new, old): {({t: (new[t], old[t]) for t in TABLES})}")


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--drop-old", action="store_true", help="drop <table>_old once the new tables are complete")
    args = ap.parse_args()
    if not config.TIGER_DATABASE_URL:
        raise SystemExit("TIGER_DATABASE_URL is not set in .env")
    con = await asyncpg.connect(config.TIGER_DATABASE_URL, command_timeout=600)
    try:
        await (drop_old(con) if args.drop_old else migrate(con))
    finally:
        await con.close()


if __name__ == "__main__":
    asyncio.run(main())
