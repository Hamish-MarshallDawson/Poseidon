"""python -m dvm.replay_raw on small recorded raw logs (written with dvm.rawlog.RawLog itself).

The pipeline tests run anywhere; the database tests need a LOCAL TimescaleDB:
  docker run -d --name replay-tsdb -p 55545:5432 -e POSTGRES_PASSWORD=local timescale/timescaledb:latest-pg17
  SOURCES_TEST_DATABASE_URL=postgresql://postgres:local@127.0.0.1:55545/postgres pytest tests/test_replay_raw.py
"""
import asyncio
import gzip
import os
import shutil
from datetime import datetime, timezone

import asyncpg
import pytest

from dvm import replay_raw, store
from dvm.rawlog import RawLog

URL = os.getenv("SOURCES_TEST_DATABASE_URL", "")
needs_db = pytest.mark.skipif(not URL or "tsdb.cloud" in URL or "timescale.com" in URL,
                              reason="set SOURCES_TEST_DATABASE_URL to a local TimescaleDB")

T0 = replay_raw.parse_time("2023-11-14T22:57:00Z")   # 6 minutes over an hour boundary, far from any live rows
MIN = 60_000
BOTH, AIS_ONLY, DT_ONLY = 230_990_001, 230_990_002, 230_990_003   # the first is heard by both feeds
SHIPS = (BOTH, AIS_ONLY, DT_ONLY)
FLEET0 = 230_991_000   # extra AISStream-only ships for the batching test


def _utc(ms: int) -> str:
    d = datetime.fromtimestamp(ms / 1000, timezone.utc)
    return d.strftime("%Y-%m-%d %H:%M:%S.") + f"{d.microsecond:06d} +0000 UTC"


def ais(mmsi, fix_ms, recv, lat, lon):
    return {"MessageType": "PositionReport",
            "MetaData": {"MMSI": mmsi, "ShipName": f"SHIP {mmsi % 10}", "time_utc": _utc(recv)},
            "Message": {"PositionReport": {"MessageID": 1, "UserID": mmsi, "Sog": 10.0, "Cog": 90.0,
                                           "TrueHeading": 90, "Latitude": lat, "Longitude": lon,
                                           "Timestamp": (fix_ms // 1000) % 60, "NavigationalStatus": 0,
                                           "Valid": True}}}


def dt_loc(mmsi, fix_ms, lat, lon):
    return {"topic": f"vessels-v2/{mmsi}/location",
            "payload": {"lat": lat, "lon": lon, "time": fix_ms // 1000, "sog": 10.0, "cog": 90.0, "heading": 90,
                        "navStat": 0}}


def dt_meta(mmsi, ts):
    return {"topic": f"vessels-v2/{mmsi}/metadata",
            "payload": {"timestamp": ts, "name": f"SHIP {mmsi % 10}", "callSign": "OH123", "imo": 0, "type": 70,
                        "draught": 85, "destination": "HELSINKI", "eta": 0, "refA": 100, "refB": 20, "refC": 10,
                        "refD": 10}}


def record_logs(root, extra=0):
    """6 minutes from T0: every ship one fix every 10 s. BOTH's fixes arrive on both feeds (Digitraffic 0.4 s after
    the fix, AISStream 0.9 s), with a Digitraffic repeat now and then; plus Digitraffic metadata once a minute."""
    events = []
    for i in range(36):
        fix = T0 + i * 10_000
        lat, lon = 60.0 + i * 1e-3, 25.0 + i * 1e-3
        events.append((fix + 400, "digitraffic", dt_loc(BOTH, fix, lat, lon)))
        if i % 7 == 0:
            events.append((fix + 450, "digitraffic", dt_loc(BOTH, fix, lat, lon)))   # QoS 0 redelivery
        events.append((fix + 900, "aisstream", ais(BOTH, fix, fix + 900, lat, lon)))
        events.append((fix + 1_100, "aisstream", ais(AIS_ONLY, fix + 200, fix + 1_100, lat - 1, lon)))
        events.append((fix + 300, "digitraffic", dt_loc(DT_ONLY, fix + 300 - 300, lat + 1, lon)))
        if i % 6 == 0:
            events.append((fix + 500, "digitraffic", dt_meta(DT_ONLY, fix)))
        for k in range(extra):
            m = FLEET0 + k
            events.append((fix + 1_200 + k, "aisstream", ais(m, fix + 1_000, fix + 1_200 + k, 58 + k * 0.01, lon)))
    events.append((T0 + 5_000, "aisstream", "not json"))   # junk lines are logged raw too
    events.append((T0 + 6_000, "aisstream", {"MessageType": "SubscriptionConfirmation", "Message": {}}))
    # one RawLog per hour, closed without rotating (its rotation gzips in a background thread); gzipped by hand below
    hour1 = replay_raw.parse_time("2023-11-14T23:00:00Z")
    for first in (True, False):
        log = RawLog(root)
        for recv, s, raw in sorted(events, key=lambda e: e[0]):
            if (recv < hour1) == first:
                log.write(s, recv, raw)
        log.close()
    # the first hour was rotated (gzipped) for AISStream; for Digitraffic the rotation was cut short: both files
    for src in ("aisstream", "digitraffic"):
        p = root / "raw" / src / "2023-11-14T22.jsonl"
        with p.open("rb") as a, gzip.open(p.with_suffix(".jsonl.gz"), "wb") as b:
            shutil.copyfileobj(a, b)
        if src == "aisstream":
            p.unlink()
    with (root / "raw" / "aisstream" / "2023-11-14T23.jsonl").open("a") as f:
        f.write('{"v":1,"src":"aisstream","recv_ts":%d,"raw":{"Mess' % (T0 + 5 * MIN + 59_000))   # half-written
    return events


def test_reads_both_formats_and_runs_the_live_pipeline(tmp_path):
    record_logs(tmp_path)
    envs, st = replay_raw.read_window(tmp_path, T0, T0 + 6 * MIN)
    assert st["files"] == 5 and st["repeat_lines"] > 0 and st["bad_lines"] == 1
    assert [e.recv_ts for e in envs] == sorted(e.recv_ts for e in envs)
    recs, ms = replay_raw.run_pipeline(envs, T0 + 6 * MIN)
    pos = [r for r in recs if r.kind == "pos"]
    assert len(pos) == 3 * 36   # one row per real fix: both-feed copies merged, the repeats dropped
    assert ms["merged"] + ms["late_dup_dropped"] == 36   # every BOTH fix heard twice, stored once
    assert len({(r.mmsi, r.ts) for r in pos}) == len(pos)
    # a narrower window only takes lines whose recv_ts is in it
    envs2, _ = replay_raw.read_window(tmp_path, T0 + MIN, T0 + 2 * MIN)
    assert envs2 and all(T0 + MIN <= e.recv_ts < T0 + 2 * MIN for e in envs2)


async def _rows(con):
    return await con.fetch("SELECT mmsi, ts, src FROM positions WHERE mmsi = ANY($1::int[]) ORDER BY ts, mmsi",
                           list(SHIPS))


async def _db_flow(tmp_path):
    record_logs(tmp_path)
    con = await asyncpg.connect(URL)
    try:
        await store.setup(con)
        for t in ("positions", "statics"):
            await con.execute(f"DELETE FROM {t} WHERE mmsi = ANY($1::int[])", list(SHIPS))
        # the live store wrote everything but minutes 3 and 4 (the database was read-only then)
        envs, _ = replay_raw.read_window(tmp_path, T0, T0 + 6 * MIN)
        recs, _ = replay_raw.run_pipeline(envs, T0 + 6 * MIN)
        live = [r for r in recs if not T0 + 3 * MIN <= r.ts < T0 + 5 * MIN]
        for kind, table, cols in (("pos", "positions", store.POS_COLS), ("static", "statics", store.STATIC_COLS)):
            await con.copy_records_to_table(table, records=[store._row(r, cols) for r in live if r.kind == kind],
                                            columns=["time", *cols])
        before = await _rows(con)
        n_static_before = await con.fetchval("SELECT count(*) FROM statics WHERE mmsi = ANY($1::int[])", list(SHIPS))

        out = []
        dry = await replay_raw.replay(URL, tmp_path, T0, T0 + 6 * MIN, dry_run=True, echo=out.append)
        assert await _rows(con) == before   # a dry run writes nothing
        assert dry["pos_write"] == 3 * 12 and dry["written_positions"] == 0   # 2 minutes x 3 ships x 6 fixes
        assert any("2023-11-14T23:00Z" in line and "aisstream" in line for line in out)

        res = await replay_raw.replay(URL, tmp_path, T0, T0 + 6 * MIN, dry_run=False, echo=out.append)
        assert res["written_positions"] == 3 * 12 and res["pos_skip"] == 3 * 24
        after = await _rows(con)
        assert len(after) == 3 * 36 and len({tuple(r) for r in after}) == len(after)   # no duplicates
        written = {tuple(r) for r in after} - {tuple(r) for r in before}
        assert all(T0 + 3 * MIN <= ts < T0 + 5 * MIN for _, ts, _ in written)
        # statics: replay starts cold, but repeats of a stored identity are not written again
        assert res["written_statics"] == 0 and await con.fetchval(
            "SELECT count(*) FROM statics WHERE mmsi = ANY($1::int[])", list(SHIPS)) == n_static_before

        again = await replay_raw.replay(URL, tmp_path, T0, T0 + 6 * MIN, dry_run=False, echo=out.append)
        assert again["written_positions"] == 0 and again["written_statics"] == 0
        assert await _rows(con) == after

        # a window the store never saw at all: everything is written once, statics included
        for t in ("positions", "statics"):
            await con.execute(f"DELETE FROM {t} WHERE mmsi = ANY($1::int[])", list(SHIPS))
        fresh = await replay_raw.replay(URL, tmp_path, T0, T0 + 6 * MIN, dry_run=False, echo=out.append)
        assert fresh["written_positions"] == 3 * 36 and fresh["written_statics"] == 3
        for t in ("positions", "statics"):
            await con.execute(f"DELETE FROM {t} WHERE mmsi = ANY($1::int[])", list(SHIPS))
    finally:
        await con.close()


@needs_db
def test_replay_writes_only_missing_rows(tmp_path):
    asyncio.run(_db_flow(tmp_path))


def test_refuses_tiger_writes(monkeypatch):
    monkeypatch.setenv("TIGER_DATABASE_URL", "postgres://u:p@x.tsdb.cloud.timescale.com:5432/tsdb")
    with pytest.raises(SystemExit, match="allow-tiger"):
        replay_raw.main(["--from", "2023-11-14T22:57:00Z", "--to", "2023-11-14T23:00:00Z", "--write"])


class Spy:
    """Wraps the replay's connection to record each existence query's mmsi list and time range."""

    def __init__(self, con, calls):
        self._con, self.calls = con, calls

    async def fetch(self, sql, *args):
        self.calls.append((sql, args))
        return await self._con.fetch(sql, *args)

    def __getattr__(self, name):
        return getattr(self._con, name)


async def _batch_flow(tmp_path, monkeypatch):
    extra = 40
    ships = list(SHIPS) + [FLEET0 + k for k in range(extra)]
    record_logs(tmp_path, extra=extra)
    calls = []
    real_connect = asyncpg.connect

    async def spy_connect(*a, **kw):
        return Spy(await real_connect(*a, **kw), calls)

    monkeypatch.setattr(replay_raw, "BATCH_KEYS", 7)
    monkeypatch.setattr(replay_raw.asyncpg, "connect", spy_connect)
    con = await real_connect(URL)
    try:
        await store.setup(con)
        for t in ("positions", "statics"):
            await con.execute(f"DELETE FROM {t} WHERE mmsi = ANY($1::int[])", ships)
        envs, _ = replay_raw.read_window(tmp_path, T0, T0 + 6 * MIN)
        recs, _ = replay_raw.run_pipeline(envs, T0 + 6 * MIN)
        assert sum(r.kind == "pos" for r in recs) == len(ships) * 36
        live = [r for r in recs if not T0 + 3 * MIN <= r.ts < T0 + 5 * MIN]
        for kind, table, cols in (("pos", "positions", store.POS_COLS), ("static", "statics", store.STATIC_COLS)):
            await con.copy_records_to_table(table, records=[store._row(r, cols) for r in live if r.kind == kind],
                                            columns=["time", *cols])
        out = []
        res = await replay_raw.replay(URL, tmp_path, T0, T0 + 6 * MIN, dry_run=False, echo=out.append)
        assert res["written_positions"] == len(ships) * 12 and res["pos_skip"] == len(ships) * 24
        assert res["written_statics"] == 0
        rows = await con.fetch("SELECT mmsi, ts, src FROM positions WHERE mmsi = ANY($1::int[])", ships)
        assert len(rows) == len(ships) * 36 and len({tuple(r) for r in rows}) == len(rows)
        # every existence query: at most BATCH_KEYS mmsis, and positions over about one minute only
        assert calls and all(len(args[0]) <= 7 for _, args in calls)
        pos_q = [args for sql, args in calls if "FROM positions" in sql]
        assert len(pos_q) >= 6 * -(-len(ships) // 7)   # 6 minutes x 7 batches
        assert all((hi - lo).total_seconds() <= 62 for _, lo, hi in pos_q)
        calls.clear()
        again = await replay_raw.replay(URL, tmp_path, T0, T0 + 6 * MIN, dry_run=False, echo=out.append)
        assert again["written_positions"] == 0 and again["written_statics"] == 0
        for t in ("positions", "statics"):
            await con.execute(f"DELETE FROM {t} WHERE mmsi = ANY($1::int[])", ships)
    finally:
        await con.close()


@needs_db
def test_replay_batches_queries_and_writes_per_minute(tmp_path, monkeypatch):
    asyncio.run(_batch_flow(tmp_path, monkeypatch))
