"""GET /track (#86): one ship's past track from Tiger positions, one point per minute, against a scratch database
of its own on a local TimescaleDB (never the database SOURCES_TEST_DATABASE_URL names; see test_routes.scratch_db)."""
import asyncio
import contextlib
import os
import time

import asyncpg
import pytest
from fastapi.testclient import TestClient

from dvm import store
from dvm.sources import query, schema
from tests.sources.test_routes import make_app, pos, real_login_app, scratch_db

URL = os.getenv("SOURCES_TEST_DATABASE_URL", "")
LOCAL = bool(URL) and "tsdb.cloud" not in URL and "timescale.com" not in URL
needs_db = pytest.mark.skipif(not LOCAL, reason="set SOURCES_TEST_DATABASE_URL to a local TimescaleDB")
SHIP, OTHER = 230000001, 244000002
MIN = 60_000
NOW = int(time.time() * 1000)
BASE = NOW - NOW % MIN - 30 * MIN          # a minute boundary 30 min ago, so bucket edges are known


def fixes():
    """(mmsi, ts, lon) rows. Minute 0 has three fixes (the latest wins), minutes 1 and 5 one each."""
    rows = [(SHIP, BASE + 1_000, 25.00), (SHIP, BASE + 20_000, 25.01), (SHIP, BASE + 59_000, 25.02),
            (SHIP, BASE + MIN + 5_000, 25.10), (SHIP, BASE + 5 * MIN, 25.50),
            (SHIP, NOW - 3 * 3_600_000, 24.00),        # 3 h ago: in hours=24, not in hours=2
            (SHIP, NOW - 25 * 3_600_000, 23.00),       # older than the 24 h cap
            (SHIP, NOW + 10 * MIN, 26.00),             # future-dated: never in the track
            (OTHER, BASE + 2_000, 10.00)]              # another ship
    return rows


DB = {"url": ""}


async def seed():
    con = await asyncpg.connect(DB["url"])
    try:
        await store.setup(con)
        recs = [(schema._dt(ts), m, *pos(m, ts, lon=lon)) for m, ts, lon in fixes()]
        await con.copy_records_to_table("positions", records=recs, columns=["time", "mmsi", *store.POS_COLS[1:]])
    finally:
        await con.close()


@pytest.fixture(scope="module")
def client():
    if not LOCAL:
        pytest.skip("set SOURCES_TEST_DATABASE_URL to a local TimescaleDB")
    name = f"poseidon_track_test_{os.getpid()}"
    DB["url"] = asyncio.run(scratch_db(URL, name, create=True))
    asyncio.run(seed())
    state = {}

    @contextlib.asynccontextmanager
    async def lifespan(app):
        state["pool"] = await asyncpg.create_pool(DB["url"], min_size=1, max_size=2)
        yield
        await state["pool"].close()

    try:
        with TestClient(make_app(lambda: state["pool"], lifespan=lifespan)) as c:
            yield c
    finally:
        asyncio.run(scratch_db(URL, name, create=False))


@needs_db
def test_one_point_per_minute_oldest_first(client):
    r = client.get("/track", params={"mmsi": SHIP, "hours": 2})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["mmsi"] == SHIP and body["hours"] == 2
    assert body["track"] == [[BASE + 59_000, 25.02, 60.0], [BASE + MIN + 5_000, 25.10, 60.0], [BASE + 5 * MIN, 25.50, 60.0]]
    assert "aisstream" in body["attribution"]


@needs_db
def test_default_is_24_hours_and_excludes_older_and_future(client):
    body = client.get("/track", params={"mmsi": SHIP}).json()
    assert body["hours"] == 24
    lons = [p[1] for p in body["track"]]
    assert lons == [24.00, 25.02, 25.10, 25.50]   # 3 h ago first; not the 25 h old fix, not the future one
    assert all(a[0] < b[0] for a, b in zip(body["track"], body["track"][1:]))


@needs_db
def test_unknown_ship_is_an_empty_track(client):
    body = client.get("/track", params={"mmsi": 211111111}).json()
    assert body["track"] == [] and body["attribution"] == {}


@needs_db
def test_track_uses_the_mmsi_time_index(client):
    async def plan():
        con = await asyncpg.connect(DB["url"])
        try:
            await con.execute("SET enable_seqscan = off")   # tiny table: make the planner show the index it would use
            rows = await con.fetch("EXPLAIN " + query.TRACK_SQL, SHIP, schema._dt(NOW - 86_400_000), schema._dt(NOW))
            return "\n".join(r[0] for r in rows)
        finally:
            await con.close()
    assert "positions_mmsi_time" in asyncio.run(plan())


@needs_db
@pytest.mark.parametrize("params", [{}, {"mmsi": "abc"}, {"mmsi": 12345678}, {"mmsi": 1_000_000_000},
                                    {"mmsi": SHIP, "hours": 0}, {"mmsi": SHIP, "hours": 25},
                                    {"mmsi": SHIP, "hours": "x"}])
def test_validation(client, params):
    assert client.get("/track", params=params).status_code == 422


def test_no_pool_is_503():
    c = TestClient(make_app(lambda: None))
    assert c.get("/track", params={"mmsi": SHIP}).status_code == 503
    assert c.get("/track", params={"mmsi": 1}).status_code == 422   # validation runs before the pool


def test_needs_login_when_auth0_configured(monkeypatch):
    c = real_login_app(monkeypatch, True)
    assert c.get("/track", params={"mmsi": SHIP}).status_code == 401
    monkeypatch.setenv("MODEL_API_TOKEN", "s3cret-train")
    assert c.get("/track", params={"mmsi": SHIP}, headers={"Authorization": "Bearer s3cret-train"}).status_code == 401
