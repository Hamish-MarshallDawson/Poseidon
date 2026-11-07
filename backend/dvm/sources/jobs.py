"""Polling, backfill and streaming jobs. Each delayed source is fetched in windows of one region and one UTC day.

The `source_windows` ledger makes every job idempotent and resumable: a window is fetched again only while the
provider may still be changing it (younger than `settle_days`) and not more often than `refetch_ms`; after that it
is frozen. Rows themselves are upserts on a deterministic id, so even a forced re-run writes no duplicates.
"""
from __future__ import annotations

import asyncio
import gzip
import json
import logging
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import asyncpg

from dvm import store as dvm_store
from dvm.normalise import normalise
from dvm.models import Envelope
from dvm.sources import gfw, schema, sentinel1
from dvm.sources.common import DAY_MS, REGIONS, day_ms, days, now_ms, utc_today
from dvm.sources.digitraffic import Dedup, normalise_digitraffic

log = logging.getLogger(__name__)

SPEC = {
    # newest = days back from today for the newest window worth asking for; lookback = how many windows each poll
    "gfw": {"stream": "all", "newest": 1, "lookback": 8, "settle_days": 7, "refetch_ms": 6 * 3_600_000},
    "sentinel1": {"stream": "scenes", "newest": 0, "lookback": 2, "settle_days": 2, "refetch_ms": 30 * 60_000},
}


def needs_fetch(row, day_end: int, now: int, spec: dict, force: bool = False) -> bool:
    if force or row is None or row["status"] != "ok":
        return True
    if row["fetched_at"] >= day_end + spec["settle_days"] * DAY_MS:
        return False                                   # fetched after it settled: frozen
    return now - row["fetched_at"] >= spec["refetch_ms"]


class RawDump:
    """Original responses, gzipped, under <data>/raw/<src>/<region>/<day>/<name>.json.gz (outside the repo)."""

    def __init__(self, root: Path | None, src: str, region: str, day: date):
        self.dir = root / "raw" / src / region / day.isoformat() if root else None

    def __call__(self, name: str, body) -> None:
        if self.dir is None:
            return
        self.dir.mkdir(parents=True, exist_ok=True)
        with gzip.open(self.dir / f"{name}.json.gz", "wt", encoding="utf-8") as f:
            json.dump(body, f, separators=(",", ":"))


def fetch(src: str, region: str, bbox, day: date, recv_ts: int, data_dir: Path | None, client=None):
    """Blocking fetch of one window -> (observations, statics, info)."""
    raw = RawDump(data_dir, src, region, day)
    if src == "gfw":
        return gfw.fetch_day(client, region, bbox, day, recv_ts, raw)
    if src == "sentinel1":
        start = datetime(day.year, day.month, day.day, tzinfo=timezone.utc)
        items = sentinel1.search(bbox, start.strftime("%Y-%m-%dT%H:%M:%SZ"),
                                 (start + timedelta(1)).strftime("%Y-%m-%dT%H:%M:%SZ"), raw_sink=raw)
        return sentinel1.parse_items(items, recv_ts), [], {"items": len(items)}
    raise ValueError(f"no windowed fetch for {src}")


async def run_window(pool, src: str, region: str, day: date, *, force=False, data_dir=None, client=None) -> dict:
    spec, bbox = SPEC[src], REGIONS[region]
    start = day_ms(day)
    now = now_ms()
    async with pool.acquire() as con:
        row = await schema.get_window(con, src, spec["stream"], region, start)
    if not needs_fetch(row, start + DAY_MS, now, spec, force):
        return {"src": src, "region": region, "day": day.isoformat(), "skipped": True}
    try:
        obs, statics, info = await asyncio.to_thread(fetch, src, region, bbox, day, now, data_dir, client)
    except Exception as e:   # one bad window is recorded and retried later; it never stops the others
        async with pool.acquire() as con:
            await schema.record_window(con, src, spec["stream"], region, start, start + DAY_MS, now, 0, "error",
                                       f"{type(e).__name__}: {e}"[:500])
        log.warning("%s %s %s failed: %s", src, region, day, e)
        return {"src": src, "region": region, "day": day.isoformat(), "error": str(e)[:200]}
    async with pool.acquire() as con:
        async with con.transaction():
            n_obs = await schema.write_observations(con, obs)
            n_st = await schema.write_statics(con, statics)
            await schema.record_window(con, src, spec["stream"], region, start, start + DAY_MS, now,
                                       n_obs + n_st, "ok")
    kinds: dict[str, int] = {}
    for o in obs:
        kinds[o.kind] = kinds.get(o.kind, 0) + 1
    res = {"src": src, "region": region, "day": day.isoformat(), "observations": n_obs, "statics": n_st,
           "kinds": kinds, **info}
    log.info("%s", res)
    return res


async def connect(url: str):
    pool = await asyncpg.create_pool(url, min_size=1, max_size=4, command_timeout=300)
    async with pool.acquire() as con:
        await dvm_store.setup(con)    # positions/statics and the rest, exactly as the backend creates them
        await schema.setup(con)
    return pool


def _client(src: str):
    return gfw.Client() if src == "gfw" else None


async def backfill(url: str, src: str, regions: list[str], start: date, end: date, *, force=False, data_dir=None):
    pool = await connect(url)
    client = _client(src)
    out = []
    try:
        for region in regions:
            for d in days(start, end):
                out.append(await run_window(pool, src, region, d, force=force, data_dir=data_dir, client=client))
    finally:
        if client:
            client.close()
        await pool.close()
    return out


async def poll(url: str, src: str, regions: list[str], *, once=False, data_dir=None):
    """Fetch the recent windows that may have changed, then sleep; forever unless once=True."""
    spec = SPEC[src]
    pool = await connect(url)
    client = _client(src)
    out = []
    try:
        while True:
            today = utc_today()
            newest = today - timedelta(spec["newest"])
            for region in regions:
                for d in days(newest - timedelta(spec["lookback"] - 1), newest):
                    out.append(await run_window(pool, src, region, d, data_dir=data_dir, client=client))
            if once:
                return out
            await asyncio.sleep(min(spec["refetch_ms"] / 1000, 1800))
    finally:
        if client:
            client.close()
        await pool.close()


async def stream_digitraffic(url: str, seconds: float | None, data_dir: Path | None):
    """Live Digitraffic -> raw log + positions/statics through the backend's own Store (COPY once a second)."""
    from dvm.rawlog import RawLog
    from dvm.sources import digitraffic

    pool = await connect(url)
    await pool.close()
    st = dvm_store.Store(url)
    writer = asyncio.create_task(st.run())
    rawlog = RawLog(data_dir) if data_dir else None
    try:
        stats = await digitraffic.run(st.add, rawlog, seconds)
    finally:
        if rawlog:
            rawlog.close()
        for _ in range(30):   # let the writer connect and drain before stopping it
            if st.pool and not any(st.buf.values()):
                break
            await asyncio.sleep(1)
        writer.cancel()
        await st.close()
    return {"received": stats.received, "positions": stats.positions, "statics": stats.statics,
            "rows_written": st.rows_written, "last_error": stats.last_error}


def _read_raw(path: Path):
    op = gzip.open if path.suffix == ".gz" else open
    with op(path, "rt", encoding="utf-8") as f:
        for line in f:
            try:
                yield Envelope.model_validate_json(line)
            except ValueError:
                continue


async def backfill_digitraffic_raw(url: str, data_dir: Path, force=False):
    """Digitraffic has no history API: replay our own raw log into the database, one hour file at a time.

    An hour is skipped when the ledger has it, or when positions already hold Digitraffic rows for it (the live
    writer got there first), so re-runs add nothing.
    """
    pool = await connect(url)
    out = []
    try:
        files = sorted((data_dir / "raw" / "digitraffic").glob("*.jsonl*"))
        for path in files:
            hour = path.name.split(".")[0]
            h0 = int(datetime.strptime(hour, "%Y-%m-%dT%H").replace(tzinfo=timezone.utc).timestamp() * 1000)
            async with pool.acquire() as con:
                row = await schema.get_window(con, "digitraffic", "raw", "-", h0)
                have = await con.fetchval(
                    "SELECT count(*) FROM positions WHERE src='digitraffic' AND recv_ts >= $1 AND recv_ts < $2",
                    h0, h0 + 3_600_000)
            # Existing rows always win (positions has no unique key, so a second copy would be a duplicate);
            # --force only ignores the ledger. The current hour is still being written, so it waits.
            if have or (not force and row and row["status"] == "ok") or h0 + 3_600_000 > now_ms():
                out.append({"hour": hour, "skipped": True, "existing": have})
                continue
            dedup = Dedup()   # the same rule as the live stream, so replay writes the same rows
            recs = [r for env in _read_raw(path) for r in
                    (normalise_digitraffic(env) if env.src == "digitraffic" else normalise(env)) if dedup.keep(r)]
            pos = [dvm_store._row(r, dvm_store.POS_COLS) for r in recs if r.kind == "pos"]
            sta = [dvm_store._row(r, dvm_store.STATIC_COLS) for r in recs if r.kind == "static"]
            async with pool.acquire() as con:
                async with con.transaction():
                    if pos:
                        await con.copy_records_to_table("positions", records=pos,
                                                        columns=["time", *dvm_store.POS_COLS])
                    if sta:
                        await con.copy_records_to_table("statics", records=sta,
                                                        columns=["time", *dvm_store.STATIC_COLS])
                    await schema.record_window(con, "digitraffic", "raw", "-", h0, h0 + 3_600_000, now_ms(),
                                               len(pos) + len(sta), "ok")
            out.append({"hour": hour, "positions": len(pos), "statics": len(sta)})
    finally:
        await pool.close()
    return out
