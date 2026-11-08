"""Concurrent windows: the GFW request gate, shards, and N workers writing exactly what one worker writes.

The database tests run against a LOCAL TimescaleDB (SOURCES_TEST_DATABASE_URL, see test_db.py) with a fake fetch, on
days in 2015 so they never touch real rows.
"""
import asyncio
import os
import random
import threading
import time
from datetime import date, timedelta

import asyncpg
import pytest

from dvm.sources import gfw, jobs
from dvm.sources.common import DAY_MS, day_ms, days
from dvm.sources.common import Observation

URL = os.getenv("SOURCES_TEST_DATABASE_URL", "")
needs_db = pytest.mark.skipif(not URL or "tsdb.cloud" in URL or "timescale.com" in URL,
                              reason="set SOURCES_TEST_DATABASE_URL to a local TimescaleDB")
REGIONS = ["danish_straits", "gulf_of_finland", "hormuz", "gulf_of_oman"]
D0, D1 = date(2015, 3, 1), date(2015, 3, 12)


# ---------- no database ----------

class GateProbe:
    """A client whose one request method records how many calls (and reports) overlap."""

    def __init__(self):
        self.lock = threading.Lock()
        self.now = {"all": 0, "report": 0}
        self.peak = {"all": 0, "report": 0}

    def _post(self, path, params, body):
        kinds = ["all"] + (["report"] if path.startswith("/4wings/report") else [])
        with self.lock:
            for k in kinds:
                self.now[k] += 1
                self.peak[k] = max(self.peak[k], self.now[k])
        time.sleep(0.02)
        with self.lock:
            for k in kinds:
                self.now[k] -= 1
        return {}


def test_share_client_serialises_reports_and_bounds_inflight():
    c = jobs.share_client(GateProbe(), inflight=3)
    assert jobs.share_client(c, inflight=99) is c          # wrapping twice is a no-op
    calls = [("/4wings/report", {}, {})] * 12 + [("/events", {}, {})] * 24
    random.Random(1).shuffle(calls)
    ts = [threading.Thread(target=c._post, args=a) for a in calls]
    for t in ts:
        t.start()
    for t in ts:
        t.join()
    assert c.peak["report"] == 1
    assert c.peak["all"] == 3


def test_share_client_covers_gfw_client_methods():
    """The real Client's report() and events() both go through the gate (no network: _post is replaced first)."""
    c = gfw.Client(token="x")
    try:
        seen = []
        c._post = lambda path, params, body: seen.append(path) or {"entries": []}
        jobs.share_client(c, inflight=2)
        c.report(gfw.PRESENCE, (0, 0, 1, 1), D0, vessels=False)
        c.events(gfw.EVENT_DATASETS["encounter"], (0, 0, 1, 1), D0)
        assert seen == ["/4wings/report", "/events"] and c._shared
    finally:
        c.close()


def test_shards_and_blocks():
    span = days(D0, D1)                                      # 12 days
    sh = jobs.shards(span, 5)
    assert [len(s) for s in sh] == [3, 3, 2, 2, 2] and [d for s in sh for d in s] == span
    assert jobs.shards(span[:2], 8) == [[span[0]], [span[1]]]
    assert [len(b) for b in jobs.blocks(span, 5)] == [5, 5, 2]
    assert jobs.blocks(span, 1) == [[d] for d in span]


# ---------- local database ----------

class FakeFetch:
    """Deterministic rows per (region, day), with jitter so concurrent windows finish out of order."""

    def __init__(self, crash_after=None):
        self.calls, self.lock = [], threading.Lock()
        self.crash_after, self.crashed = crash_after, threading.Event()

    def rows(self, region, day, recv_ts):
        n = (day.toordinal() + len(region)) % 4               # some windows are empty
        start = day_ms(day)
        return [Observation(id=f"ptest:{region}:{day}:{i}", src="gfw", kind="gap", ts=start + i * 1000,
                            end_ts=start + i * 1000 + 10, recv_ts=recv_ts, available_ts=start + DAY_MS,
                            mmsi=230099951, lat=60.0, lon=25.0, value=float(i), attrs={"r": region})
                for i in range(n)]

    def __call__(self, src, region, bbox, day, recv_ts, data_dir, client=None):
        with self.lock:
            self.calls.append((region, day))
            if self.crash_after is not None and len(self.calls) >= self.crash_after:
                self.crashed.set()
        time.sleep(random.uniform(0, 0.03))
        obs = self.rows(region, day, recv_ts)
        return obs, [], {"fake": True}


async def _clean(con):
    await con.execute("DELETE FROM observations WHERE id LIKE 'ptest:%'")
    await con.execute("DELETE FROM source_windows WHERE src = 'gfw' AND start_ts >= $1 AND start_ts < $2",
                      day_ms(D0) - 40 * DAY_MS, day_ms(D1) + DAY_MS)


async def _snapshot(con):
    rows = await con.fetch("SELECT id, ts, end_ts, value, attrs FROM observations WHERE id LIKE 'ptest:%' ORDER BY id")
    ledger = await con.fetch(
        "SELECT region, start_ts, end_ts, rows, status FROM source_windows WHERE src = 'gfw' "
        "AND start_ts >= $1 AND start_ts < $2 ORDER BY region, start_ts",
        day_ms(D0) - 40 * DAY_MS, day_ms(D1) + DAY_MS)
    return [tuple(r) for r in rows], [tuple(r) for r in ledger]


def _expected_ledger(span):
    f = FakeFetch()
    return sorted((r, day_ms(d), day_ms(d) + DAY_MS, len(f.rows(r, d, 0)), "ok") for r in REGIONS for d in span)


async def _with_db(body):
    await (await jobs.connect(URL)).close()                   # tables exist
    con = await asyncpg.connect(URL)
    try:
        await _clean(con)
        return await body(con)
    finally:
        await _clean(con)
        await con.close()


@needs_db
def test_workers_write_what_one_worker_writes(monkeypatch):
    async def body(con):
        snaps = []
        for workers in (1, 4):
            fake = FakeFetch()
            monkeypatch.setattr(jobs, "fetch", fake)
            out = await jobs.backfill(URL, "gfw", REGIONS, D0, D1, workers=workers, client=object())
            assert len(out) == len(fake.calls) == 12 * len(REGIONS) and not any("error" in r for r in out)
            snaps.append(await _snapshot(con))
            await _clean(con)
        assert snaps[0] == snaps[1]
        assert snaps[0][1] == _expected_ledger(days(D0, D1))
        assert len(snaps[0][0]) == sum(r[3] for r in snaps[0][1]) > 0
    asyncio.run(_with_db(body))


@needs_db
def test_crash_and_restart_leaves_no_gaps_or_duplicates(monkeypatch):
    async def body(con):
        fake = FakeFetch(crash_after=17)
        monkeypatch.setattr(jobs, "fetch", fake)
        task = asyncio.create_task(jobs.backfill(URL, "gfw", REGIONS, D0, D1, workers=3, client=object()))
        while not fake.crashed.is_set():
            await asyncio.sleep(0.005)
        task.cancel()                                          # the process dies mid-run
        with pytest.raises(asyncio.CancelledError):
            await task
        _, partial = await _snapshot(con)
        assert 0 < len(partial) < 12 * len(REGIONS)
        done = {(r[0], r[1]) for r in partial}

        again = FakeFetch()
        monkeypatch.setattr(jobs, "fetch", again)
        await jobs.backfill(URL, "gfw", REGIONS, D0, D1, workers=3, client=object())
        assert not {(r, day_ms(d)) for r, d in again.calls} & done   # settled windows were not fetched again
        rows, ledger = await _snapshot(con)
        assert ledger == _expected_ledger(days(D0, D1))
        assert len(rows) == len({r[0] for r in rows}) == sum(r[3] for r in ledger)
    asyncio.run(_with_db(body))


@needs_db
def test_backfill_back_workers_match_one_worker(monkeypatch):
    async def body(con):
        results = []
        for workers, block in ((1, 1), (3, 1), (2, 5)):
            monkeypatch.setattr(jobs, "fetch", FakeFetch())
            res = await jobs.backfill_back(URL, "gfw", REGIONS, until=D0, newest=D1, workers=workers,
                                           block_days=block, client=object())
            results.append((res["oldest_day"], res["stopped"], res["observations"], await _snapshot(con)))
            await _clean(con)
        assert results[0] == results[1] == results[2]
        assert results[0][0] == D0.isoformat() and "until" in results[0][1]
        assert results[0][3][1] == _expected_ledger(days(D0, D1))
    asyncio.run(_with_db(body))


@needs_db
def test_range_seam_used_when_gfw_has_fetch_range(monkeypatch):
    async def body(con):
        per_day = FakeFetch()
        monkeypatch.setattr(jobs, "fetch", per_day)
        await jobs.backfill(URL, "gfw", REGIONS, D0, D1, client=object())
        want = await _snapshot(con)
        await _clean(con)
        # One window already settled: the range fetch must not ask for it again, nor rewrite it.
        await jobs.backfill(URL, "gfw", ["hormuz"], D0, D0, client=object())

        ranges = []

        def fetch_range(client, region, bbox, first, last, recv_ts, raw_sink=None):
            ranges.append((region, first, last))
            out = {d.isoformat(): per_day(None, region, bbox, d, recv_ts, None) for d in days(first, last)}
            if region == "hormuz":
                out.pop((D0 + timedelta(2)).isoformat(), None)   # the provider left one day out
            return out

        monkeypatch.setattr(gfw, "fetch_range", fetch_range, raising=False)
        out = await jobs.backfill(URL, "gfw", REGIONS, D0, D1, workers=2, block_days=4, client=object())
        assert ("hormuz", D0 + timedelta(1), D0 + timedelta(3)) in ranges     # skipped D0, kept the rest
        assert all(last - first <= timedelta(3) for _, first, last in ranges)
        missing = [r for r in out if "error" in r]
        assert [(r["region"], r["day"]) for r in missing] == [("hormuz", (D0 + timedelta(2)).isoformat())]
        # The missing day is retried by the next run and then everything matches the per-day path.
        monkeypatch.delattr(gfw, "fetch_range")
        await jobs.backfill(URL, "gfw", REGIONS, D0, D1, client=object())
        assert await _snapshot(con) == want
    asyncio.run(_with_db(body))
