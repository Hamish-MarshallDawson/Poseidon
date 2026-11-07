"""Tiger Data set-up and the coverage aggregate, against the real database. Skipped when TIGER_DATABASE_URL is unset."""
import asyncio
import json

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


def test_coverage_aggregates_split_by_class():
    async def go():
        con = await asyncpg.connect(config.TIGER_DATABASE_URL)
        try:
            await store.setup(con)
            for view in ("coverage_1m", "coverage_1h"):
                cols = {r["column_name"] for r in await con.fetch(
                    "SELECT column_name FROM information_schema.columns WHERE table_name = $1", view)}
                assert {"bucket", "lat_bin", "lon_bin", "cls", "ships", "msgs"} <= cols, view
        finally:
            await con.close()
    asyncio.run(go())


GAP = {"id": "gap-test-1", "version": 1, "mmsi": 999999999, "state": "open", "start_ts": 1_700_000_000_000,
       "detected_at": 1_700_000_900_000, "duration_s": 900, "last_lat": 59.5, "last_lon": 24.5,
       "neighbours_heard": 4, "neighbours_baseline": 5, "cell_id": "595_245", "coverage_flag": "unknown",
       "src": "derived"}
SCORE = {"id": "score-999999999-dark_6h-1700000000000", "mmsi": 999999999, "target": "dark_6h",
         "made_at": 1_700_000_000_000, "horizon_s": 21600, "p": 0.12, "model_version": "test",
         "feature_version": "test", "features": {"gaps_24h": 1, "sog_kn": None}, "mode": "backtest"}
OUTCOME = {"score_id": SCORE["id"], "mmsi": 999999999, "target": "dark_6h", "made_at": SCORE["made_at"],
           "horizon_s": 21600, "resolved_at": 1_700_023_400_000, "label": False}


def test_append_only_tables_take_rows_and_refuse_changes():
    """Runs inside a transaction that is rolled back, so nothing is left in the database."""
    async def go():
        con = await asyncpg.connect(config.TIGER_DATABASE_URL)
        try:
            await store.setup(con)
            tr = con.transaction()
            await tr.start()
            try:
                await store.append(con, "gaps", [GAP, {**GAP, "version": 2, "state": "closed", "end_ts": 1_700_001_000_000}])
                await store.append(con, "scores", [SCORE])
                await store.append(con, "outcomes", [OUTCOME])
                assert await con.fetchval("SELECT state FROM gaps WHERE id = $1 ORDER BY version DESC LIMIT 1",
                                          GAP["id"]) == "closed"
                row = await con.fetchrow("SELECT time, features FROM scores WHERE id = $1", SCORE["id"])
                assert int(row["time"].timestamp() * 1000) == SCORE["made_at"]
                assert json.loads(row["features"]) == SCORE["features"]
                for table, where in (("gaps", "id = 'gap-test-1'"), ("scores", f"id = '{SCORE['id']}'"),
                                     ("outcomes", f"score_id = '{SCORE['id']}'")):
                    for sql in (f"UPDATE {table} SET mmsi = 1 WHERE {where}", f"DELETE FROM {table} WHERE {where}"):
                        with pytest.raises(asyncpg.RaiseError, match="append-only"):
                            async with con.transaction():   # a savepoint, so the refusal doesn't end the outer test
                                await con.execute(sql)
                with pytest.raises(asyncpg.UniqueViolationError):
                    async with con.transaction():
                        await store.append(con, "scores", [SCORE])
            finally:
                await tr.rollback()
        finally:
            await con.close()
    asyncio.run(go())
