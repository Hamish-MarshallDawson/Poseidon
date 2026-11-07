"""The new tables against a real TimescaleDB. Skipped unless SOURCES_TEST_DATABASE_URL points at a LOCAL database:

  docker run -d --name poseidon-tsdb -p 55433:5432 -e POSTGRES_PASSWORD=local timescale/timescaledb:latest-pg17
  SOURCES_TEST_DATABASE_URL=postgresql://postgres:local@127.0.0.1:55433/postgres pytest tests/sources
"""
import asyncio
import os

import asyncpg
import pytest

from dvm.models import VesselStatic
from dvm.sources import jobs, query, schema
from dvm.sources.__main__ import database_url
from dvm.sources.common import Observation

URL = os.getenv("SOURCES_TEST_DATABASE_URL", "")
needs_db = pytest.mark.skipif(not URL or "tsdb.cloud" in URL or "timescale.com" in URL,
                              reason="set SOURCES_TEST_DATABASE_URL to a local TimescaleDB")
T0 = 1_700_000_000_000   # 2023-11-14, well away from any live rows


def obs(i, **kw):
    base = dict(id=f"test:{i}", src="gfw", kind="gap", ts=T0 + i, end_ts=T0 + i + 10, recv_ts=T0 + 100,
                available_ts=T0 + 100, mmsi=230099950, lat=60.0, lon=25.0, value=1.0, attrs={"k": i})
    return Observation(**{**base, **kw})


async def _run():
    con = await asyncpg.connect(URL)
    try:
        pool = await jobs.connect(URL)   # full setup, twice: must be idempotent
        await pool.close()
        await schema.setup(con)
        await con.execute("DELETE FROM observations WHERE id LIKE 'test:%'")
        await con.execute("DELETE FROM statics WHERE src = 'gfw' AND mmsi = 230099950 AND ts = $1", T0)

        await schema.write_observations(con, [obs(1), obs(2)])
        await schema.write_observations(con, [obs(1), obs(2)])
        assert await con.fetchval("SELECT count(*) FROM observations WHERE id LIKE 'test:%'") == 2

        # A revision updates the provider's numbers but keeps the first available_ts (the as-of clock).
        await schema.write_observations(con, [obs(1, end_ts=T0 + 999, available_ts=T0 + 5000, value=7.0)])
        r = await con.fetchrow("SELECT end_ts, available_ts, value FROM observations WHERE id = 'test:1'")
        assert (r["end_ts"], r["available_ts"], r["value"]) == (T0 + 999, T0 + 100, 7.0)

        st = VesselStatic(mmsi=230099950, ts=T0, recv_ts=T0, name="X", mid=230, src="gfw")
        await schema.write_statics(con, [st])
        await schema.write_statics(con, [st])
        assert await con.fetchval("SELECT count(*) FROM statics WHERE src='gfw' AND mmsi=230099950 AND ts=$1", T0) == 1

        before = await query.observations(con, kinds=["gap"], as_of=T0 + 50, start_ts=T0, end_ts=T0 + 10_000)
        after = await query.observations(con, kinds=["gap"], as_of=T0 + 100, start_ts=T0, end_ts=T0 + 10_000,
                                         bbox=(24, 59, 26, 61))
        assert before["observations"] == [] and len(after["observations"]) == 2
        assert "gfw" in after["attribution"]
        outside = await query.observations(con, kinds=["gap"], start_ts=T0, end_ts=T0 + 10_000, bbox=(0, 0, 1, 1))
        assert outside["observations"] == []

        await schema.record_window(con, "gfw", "all", "test", T0, T0 + 1, T0 + 5, 3, "ok")
        await schema.record_window(con, "gfw", "all", "test", T0, T0 + 1, T0 + 9, 4, "ok")
        w = await schema.get_window(con, "gfw", "all", "test", T0)
        assert (w["rows"], w["fetched_at"], w["first_fetched_at"]) == (4, T0 + 9, T0 + 5)
        await con.execute("DELETE FROM source_windows WHERE region = 'test'")
        await con.execute("DELETE FROM observations WHERE id LIKE 'test:%'")
        await con.execute("DELETE FROM statics WHERE src = 'gfw' AND mmsi = 230099950 AND ts = $1", T0)
    finally:
        await con.close()


@needs_db
def test_tables_idempotent_and_as_of():
    asyncio.run(_run())


def test_tiger_is_refused(monkeypatch):
    class A:
        db, allow_tiger = "postgres://u:p@abc.tsdb.cloud.timescale.com:5432/tsdb", False
    with pytest.raises(SystemExit):
        database_url(A)
    monkeypatch.setenv("TIGER_DATABASE_URL", "postgres://u:p@somehost:5432/tsdb")
    A.db = "postgres://u:p@somehost:5432/tsdb"
    with pytest.raises(SystemExit):
        database_url(A)
