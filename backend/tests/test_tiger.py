"""Tiger Data set-up and the coverage aggregate, against the real database. Skipped when TIGER_DATABASE_URL is unset."""
import asyncio

import asyncpg
import pytest

from dvm import config, coverage, store

pytestmark = pytest.mark.skipif(not config.TIGER_DATABASE_URL, reason="TIGER_DATABASE_URL is not set")


async def _run():
    con = await asyncpg.connect(config.TIGER_DATABASE_URL)
    try:
        await store.setup(con)   # twice: the set-up must be safe to repeat
        await store.setup(con)
        assert await con.fetchval("SELECT count(*) FROM timescaledb_information.continuous_aggregates "
                                  "WHERE view_name = 'coverage_1m'") == 1
        assert await con.fetchval("SELECT count(*) FROM timescaledb_information.jobs "
                                  "WHERE proc_name = 'policy_refresh_continuous_aggregate'") >= 1
        # The aggregate and raw positions must agree on a window that is no longer being written to.
        raw, agg = await con.fetchrow(
            "SELECT (SELECT count(*) FROM positions WHERE time >= date_trunc('minute', now()) - interval '30 min' "
            "                                         AND time < date_trunc('minute', now()) - interval '5 min'), "
            "       (SELECT coalesce(sum(msgs), 0) FROM coverage_1m WHERE bucket >= date_trunc('minute', now()) - "
            "        interval '30 min' AND bucket < date_trunc('minute', now()) - interval '5 min')")
        assert raw == agg
    finally:
        await con.close()


def test_setup_twice_and_aggregate_matches_raw():
    asyncio.run(_run())


def test_coverage_query_runs_against_tiger():
    async def go():
        pool = await asyncpg.create_pool(config.TIGER_DATABASE_URL, min_size=1, max_size=1)
        try:
            rows = await coverage.coverage(pool, 10, (-180.0, -90.0, 180.0, 90.0))
            assert all({"cell_id", "bucket_ts", "ships", "msgs"} <= r.keys() for r in rows)
        finally:
            await pool.close()
    asyncio.run(go())
