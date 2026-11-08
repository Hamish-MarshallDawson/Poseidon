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
import threading
from concurrent.futures import ThreadPoolExecutor
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


RECENT_STATICS_DAYS = 30
DEFAULT_MAX_DB_GB = 60.0    # stop backfilling at this database size (Tiger bills storage; we have $1000 of credit)
EMPTY_STOP_DAYS = 21        # stop going back after this many consecutive days with no data in any region
DEFAULT_INFLIGHT = 4        # GFW requests in flight at once, across all regions and workers (see README)
REPORT_PATH = "/4wings/report"


def needs_fetch(row, day_end: int, now: int, spec: dict, force: bool = False) -> bool:
    if force or row is None or row["status"] != "ok":
        return True
    if row["fetched_at"] >= day_end + spec["settle_days"] * DAY_MS:
        return False                                   # fetched after it settled: frozen
    return now - row["fetched_at"] >= spec["refetch_ms"]


class RawDump:
    """Original responses, gzipped, under <data>/raw/<src>/<region>/<day>/<name>.json.gz (outside the repo).
    A multi-day fetch goes under <first day>_<last day>/ instead."""

    def __init__(self, root: Path | None, src: str, region: str, day: date, last: date | None = None):
        span = day.isoformat() if last is None or last == day else f"{day.isoformat()}_{last.isoformat()}"
        self.dir = root / "raw" / src / region / span if root else None

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


def has_range(src: str) -> bool:
    """gfw.fetch_range (one call per stream for a block of days) is used when that module provides it."""
    return src == "gfw" and hasattr(gfw, "fetch_range")


def fetch_block(src: str, region: str, bbox, first: date, last: date, recv_ts: int, data_dir: Path | None,
                client=None) -> dict:
    """Blocking fetch of several days at once -> {day: (observations, statics, info)}."""
    raw = RawDump(data_dir, src, region, first, last)
    res = gfw.fetch_range(client, region, bbox, first, last, recv_ts, raw)
    span = days(first, last)
    if isinstance(res, dict):
        return {d: res[k] for d in span for k in (d, d.isoformat()) if k in res}
    return dict(zip(span, res))


def share_client(client, inflight: int = DEFAULT_INFLIGHT):
    """Make one GFW client safe to use from many windows at once, within GFW's limits.

    GFW lets a token run only one 4Wings report at a time (a second one gets 429 "not currently enabled to perform
    more than one concurrent report"); /events took 8 at once without complaint. So reports go one at a time and
    every request, reports included, counts against `inflight`. The gate wraps the client's single request method,
    so it also covers whatever gfw.fetch_range calls.
    """
    if client is None or not hasattr(client, "_post") or getattr(client, "_shared", False):
        return client
    post, report, gate = client._post, threading.Lock(), threading.BoundedSemaphore(max(1, inflight))

    def _post(path, params, body):
        if str(path).startswith(REPORT_PATH):
            with report, gate:
                return post(path, params, body)
        with gate:
            return post(path, params, body)

    client._post, client._shared = _post, True
    return client


def _use_threads(n: int) -> None:
    """Concurrent windows each block a thread while fetching: make sure there are enough threads for all of them
    (the default pool is sized from the CPU count, which on a small server is fewer than the windows)."""
    asyncio.get_running_loop().set_default_executor(ThreadPoolExecutor(max(4, n), thread_name_prefix="window"))


async def _record_error(pool, src, region, day: date, now: int, e: Exception) -> dict:
    # one bad window is recorded and retried later; it never stops the others
    start = day_ms(day)
    async with pool.acquire() as con:
        await schema.record_window(con, src, SPEC[src]["stream"], region, start, start + DAY_MS, now, 0, "error",
                                   f"{type(e).__name__}: {e}"[:500])
    log.warning("%s %s %s failed: %s", src, region, day, e)
    return {"src": src, "region": region, "day": day.isoformat(), "error": str(e)[:200]}


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
    except Exception as e:
        return await _record_error(pool, src, region, day, now, e)
    return await _write_window(pool, src, region, day, now, obs, statics, info)


async def _write_window(pool, src: str, region: str, day: date, now: int, obs, statics, info) -> dict:
    spec, start = SPEC[src], day_ms(day)
    # GFW identity goes to statics only for recent days: statics has 15-minute chunks, and a year of daily rows would
    # make hundreds of tiny ones. Older identities stay in the region rows' attrs (name, flag, IMO, type).
    statics = [s for s in statics if s.ts >= now - RECENT_STATICS_DAYS * DAY_MS]
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


async def run_span(pool, src: str, region: str, span: list[date], *, force=False, data_dir=None, client=None
                   ) -> list[dict]:
    """The windows of one region over consecutive days (oldest first): one fetch for the days that need it when the
    provider has a range fetch, else one window at a time. Each day is still its own transaction and ledger row."""
    if len(span) == 1 or not has_range(src):
        return [await run_window(pool, src, region, d, force=force, data_dir=data_dir, client=client) for d in span]
    spec, now = SPEC[src], now_ms()
    out: dict[date, dict] = {}
    async with pool.acquire() as con:
        for d in span:
            row = await schema.get_window(con, src, spec["stream"], region, day_ms(d))
            if not needs_fetch(row, day_ms(d) + DAY_MS, now, spec, force):
                out[d] = {"src": src, "region": region, "day": d.isoformat(), "skipped": True}
    todo = [d for d in span if d not in out]
    if todo:
        try:
            got = await asyncio.to_thread(fetch_block, src, region, REGIONS[region], todo[0], todo[-1], now,
                                          data_dir, client)
        except Exception as e:
            got, err = {}, e
        else:
            err = RuntimeError("range fetch returned no result for this day")
        for d in todo:
            if d in got:
                out[d] = await _write_window(pool, src, region, d, now, *got[d])
            else:
                out[d] = await _record_error(pool, src, region, d, now, err)
    return [out[d] for d in span]


async def run_days(pool, src: str, regions: list[str], span: list[date], **kw) -> list[dict]:
    """Every region over the same days, concurrently (the client's gate bounds the requests in flight)."""
    per_region = await asyncio.gather(*(run_span(pool, src, r, span, **kw) for r in regions))
    return [res for rs in per_region for res in rs]


def blocks(span: list[date], size: int) -> list[list[date]]:
    size = max(1, size)
    return [span[i:i + size] for i in range(0, len(span), size)]


def shards(span: list, n: int) -> list[list]:
    """n contiguous, nearly equal pieces of span (fewer when span is shorter than n)."""
    n = max(1, min(n, len(span)))
    k, extra = divmod(len(span), n)
    out, i = [], 0
    for j in range(n):
        step = k + (j < extra)
        out.append(span[i:i + step])
        i += step
    return out


async def connect(url: str, max_size: int = 4):
    """Pool plus the new tables. The backend's own tables are created only on a database that lacks them (a fresh
    local one): on Tiger the backend owns its start-up steps, and several jobs re-running them would contend."""
    pool = await asyncpg.create_pool(url, min_size=1, max_size=max_size, command_timeout=300)
    async with pool.acquire() as con:
        if not await con.fetchval("SELECT to_regclass('public.positions') IS NOT NULL"):
            await dvm_store.setup(con)
        await schema.setup(con)
    return pool


def _client(src: str, inflight: int = DEFAULT_INFLIGHT):
    return share_client(gfw.Client(), inflight) if src == "gfw" else None


def _pool_size(workers: int, regions: list[str]) -> int:
    return max(4, min(16, workers * len(regions)))


async def backfill(url: str, src: str, regions: list[str], start: date, end: date, *, force=False, data_dir=None,
                   workers: int = 1, block_days: int = 1, inflight: int = DEFAULT_INFLIGHT, client=None):
    """Every window from start to end. The days are split into `workers` contiguous shards walked at the same time,
    oldest first within each; the regions of a day run concurrently. The ledger and the per-window transactions
    keep shards from double-writing, and a re-run skips what is settled."""
    _use_threads(workers * len(regions))
    pool = await connect(url, _pool_size(workers, regions))
    own = client is None
    client = _client(src, inflight) if own else share_client(client, inflight)

    async def walk(shard):
        res = []
        for b in blocks(shard, block_days):
            res += await run_days(pool, src, regions, b, force=force, data_dir=data_dir, client=client)
        return res

    try:
        out = [r for rs in await asyncio.gather(*(walk(s) for s in shards(days(start, end), workers))) for r in rs]
    finally:
        if client and own:
            client.close()
        await pool.close()
    return out


async def poll(url: str, src: str, regions: list[str], *, once=False, data_dir=None, inflight=DEFAULT_INFLIGHT):
    """Fetch the recent windows that may have changed, then sleep; forever unless once=True."""
    spec = SPEC[src]
    _use_threads(len(regions))
    pool = await connect(url, _pool_size(1, regions))
    client = _client(src, inflight)
    out = []
    try:
        while True:
            today = utc_today()
            newest = today - timedelta(spec["newest"])
            for d in days(newest - timedelta(spec["lookback"] - 1), newest):
                out += await run_days(pool, src, regions, [d], data_dir=data_dir, client=client)
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


class BackState:
    """Day-by-day walk backwards; stops at `until`, after EMPTY_STOP_DAYS empty days, or at the size cap."""

    def __init__(self, newest: date, until: date, empty_stop: int = EMPTY_STOP_DAYS):
        self.day, self.until, self.empty_stop = newest, until, empty_stop
        self.empty_run = 0
        self.stopped: str | None = None

    def record(self, rows_today: int, skipped_all: bool) -> None:
        if skipped_all:                # already settled from an earlier run: neither data nor proof of absence
            pass
        elif rows_today == 0:
            self.empty_run += 1
        else:
            self.empty_run = 0
        if self.empty_run >= self.empty_stop:
            self.stopped = f"{self.empty_run} consecutive empty days (provider history ends near {self.day})"
        self.day -= timedelta(1)
        if not self.stopped and self.day < self.until:
            self.stopped = f"reached --until {self.until}"


async def backfill_back(url: str, src: str, regions: list[str], *, until: date, max_db_gb: float = DEFAULT_MAX_DB_GB,
                        data_dir=None, newest: date | None = None, workers: int = 1, block_days: int = 1,
                        inflight: int = DEFAULT_INFLIGHT, client=None) -> dict:
    """From the newest available day backwards, all regions at a time, until stopped.

    `workers` take the next days (`block_days` at a time) from one shared cursor, newest first, so recent history
    always lands first; the regions of a day run concurrently. The stop rules are applied to the days in order as
    they complete, so a worker may finish up to one block past the stopping day. Windows already settled are
    skipped, so a restart resumes where it left off. Checks the database size before every block (every day with
    the default block of 1) and stops at max_db_gb. Interrupt with Ctrl+C at any point; nothing is half-written
    (one transaction per window).
    """
    _use_threads(workers * len(regions))
    pool = await connect(url, _pool_size(workers, regions))
    own = client is None
    client = _client(src, inflight) if own else share_client(client, inflight)
    st = BackState(newest or utc_today() - timedelta(SPEC[src]["newest"]), until)
    totals = {"days": 0, "observations": 0, "statics": 0, "errors": 0}
    cursor, done = st.day, {}

    async def worker():
        nonlocal cursor
        while not st.stopped and cursor >= until:
            async with pool.acquire() as con:
                size_gb = await schema.db_size_bytes(con) / 1e9
            if size_gb >= max_db_gb:
                st.stopped = st.stopped or f"database is {size_gb:.1f} GB, at the {max_db_gb:.0f} GB cap"
                return
            last = cursor
            first = max(until, last - timedelta(max(1, block_days) - 1))
            cursor = first - timedelta(1)
            res = await run_days(pool, src, regions, days(first, last), data_dir=data_dir, client=client)
            for d in days(first, last):
                rs = [r for r in res if r["day"] == d.isoformat()]
                rows = sum(r.get("observations", 0) for r in rs)
                totals["observations"] += rows
                totals["statics"] += sum(r.get("statics", 0) for r in rs)
                totals["errors"] += sum("error" in r for r in rs)
                totals["days"] += 1
                log.info("backfill %s %s: %d rows, db %.2f GB", src, d, rows, size_gb)
                done[d] = (rows, all(r.get("skipped") for r in rs))
            while not st.stopped and st.day in done:   # apply the stop rules in day order
                st.record(*done.pop(st.day))

    try:
        await asyncio.gather(*(worker() for _ in range(max(1, workers))))
    finally:
        if client and own:
            client.close()
        await pool.close()
    return {"src": src, "oldest_day": (st.day + timedelta(1)).isoformat(), "stopped": st.stopped, **totals}


async def create_readonly_role(url: str, role: str, password: str) -> None:
    """A login role that can read every table and view, now and later, and write nothing."""
    con = await asyncpg.connect(url)
    try:
        exists = await con.fetchval("SELECT 1 FROM pg_roles WHERE rolname = $1", role)
        ident = '"' + role.replace('"', '') + '"'
        pw = password.replace("'", "''")
        await con.execute(f"{'ALTER' if exists else 'CREATE'} ROLE {ident} LOGIN PASSWORD '{pw}'")
        db = await con.fetchval("SELECT current_database()")
        for sql in (f'GRANT CONNECT ON DATABASE "{db}" TO {ident}', f"GRANT USAGE ON SCHEMA public TO {ident}",
                    f"GRANT SELECT ON ALL TABLES IN SCHEMA public TO {ident}",
                    f"ALTER DEFAULT PRIVILEGES IN SCHEMA public GRANT SELECT ON TABLES TO {ident}",
                    f"ALTER ROLE {ident} SET default_transaction_read_only = on"):
            await con.execute(sql)
    finally:
        await con.close()
