"""GET /observations?mmsi= (one ship's history) and GET /observations/heat against a scratch local TimescaleDB."""
import asyncio
import contextlib
import os

import asyncpg
import pytest
from fastapi.testclient import TestClient

from dvm import store
from dvm.sources import query, routes, schema
from dvm.sources.common import Observation
from tests.sources.test_routes import URL, make_app, scratch_db

DAY = 86_400_000
T0 = 1_700_000_000_000 - 1_700_000_000_000 % DAY      # a UTC midnight
A, B, C = 230000001, 230000002, 230000003
BOX = "24,59,26,61"


def ev(id_, kind, ts, mmsi, lat=60.0, lon=25.0, end=None, **kw):
    return Observation(id=id_, src="gfw", kind=kind, ts=ts, end_ts=end if end is not None else ts + 3_600_000,
                       recv_ts=ts + DAY, available_ts=ts + DAY, mmsi=mmsi, lat=lat, lon=lon,
                       attrs={"name": "SHIP", "vessel_id": "heavy"}, **kw)


def cell(id_, kind, day, lat, lon, value, n, matched=None, cell_deg=0.01):
    ts = T0 + day * DAY
    return Observation(id=id_, src="gfw", kind=kind, ts=ts, end_ts=ts + DAY, recv_ts=ts + DAY, available_ts=ts + DAY,
                       lat=lat, lon=lon, bbox=(lon, lat, lon + cell_deg, lat + cell_deg), cell_deg=cell_deg,
                       value=value, n=n, matched=matched)


ROWS = [
    ev("h:a-port", "port_visit", T0 - 300 * DAY, A, end=T0 - 299 * DAY),
    ev("h:a-gap", "gap", T0 - 10 * DAY, A, lat=10.0, lon=100.0),          # far away: no bbox needed with mmsi
    ev("h:a-enc", "encounter", T0 - 1 * DAY, A),
    ev("h:a-pres", "ais_presence", T0 - 2 * DAY, A, end=T0 - 1 * DAY, value=5.0),
    ev("h:a-sar", "sar_detection", T0 - 3 * DAY, A, end=T0 - 2 * DAY, value=2.0, matched=True),
    ev("h:a-old", "gap", T0 - 500 * DAY, A),                              # older than 400 days
    ev("h:b-loit", "loitering", T0 - 5 * DAY, B),
    ev("h:c-gap", "gap", T0 - 4 * DAY, C),                                # another ship: never in A's answer
    # heat: day 0 and day 1 cells; 60.00-60.09 / 25.00-25.09 land in one 0.1 cell
    cell("c:p0a", "ais_presence", 0, 60.00, 25.00, 1.5, 2),
    cell("c:p0b", "ais_presence", 0, 60.09, 25.09, 2.5, 1),
    cell("c:p1a", "ais_presence", 1, 60.00, 25.00, 4.0, 3),
    cell("c:p0c", "ais_presence", 0, 60.10, 25.00, 0.5, 1),                # next cell north (on the grid line)
    cell("c:p0far", "ais_presence", 0, 10.0, 100.0, 99.0, 9),              # outside bbox
    cell("c:p-late", "ais_presence", 40, 60.00, 25.00, 77.0, 7),           # outside window
    cell("c:s0m", "sar_detection", 0, 60.00, 25.00, 3.0, 1, matched=True),
    cell("c:s0u", "sar_detection", 0, 60.05, 25.05, 2.0, 2, matched=False),
    ev("h:pres-vessel", "ais_presence", T0, A, value=50.0),                # per-vessel row: not a heat cell
]


@pytest.fixture(scope="module")
def client():
    if not URL or "tsdb.cloud" in URL or "timescale.com" in URL:
        pytest.skip("set SOURCES_TEST_DATABASE_URL to a local TimescaleDB")
    name = f"poseidon_hist_heat_test_{os.getpid()}"
    db = asyncio.run(scratch_db(URL, name, create=True))

    async def seed():
        con = await asyncpg.connect(db)
        try:
            await store.setup(con)
            await schema.setup(con)
            await schema.write_observations(con, ROWS)
        finally:
            await con.close()
    asyncio.run(seed())
    state = {}

    @contextlib.asynccontextmanager
    async def lifespan(app):
        state["pool"] = await asyncpg.create_pool(db, min_size=1, max_size=2)
        yield
        await state["pool"].close()

    try:
        with TestClient(make_app(lambda: state["pool"], lifespan=lifespan)) as c:
            yield c
    finally:
        asyncio.run(scratch_db(URL, name, create=False))


def hist(client, **params):
    r = client.get("/observations", params={"end": T0 + 2 * DAY, **params})
    assert r.status_code == 200, r.text
    return r.json()


def test_ship_history_newest_first_no_bbox(client):
    body = hist(client, mmsi=A)
    ids = [o["id"] for o in body["observations"]]
    assert ids == ["h:pres-vessel", "h:a-enc", "h:a-pres", "h:a-sar", "h:a-gap", "h:a-port"]   # not h:a-old
    assert "CC BY-NC" in body["attribution"]["gfw"]
    assert body["observations"][1]["attrs"] == {"name": "SHIP"}            # same light map attrs as before


def test_ship_history_filters(client):
    both = [o["id"] for o in hist(client, mmsi=[A, B], kinds="loitering,gap")["observations"]]
    assert both == ["h:b-loit", "h:a-gap"]
    boxed = [o["id"] for o in hist(client, mmsi=A, bbox="99,9,101,11")["observations"]]
    assert boxed == ["h:a-gap"]
    assert len(hist(client, mmsi=A, limit=2)["observations"]) == 2
    old = hist(client, mmsi=A, start=T0 - 510 * DAY, end=T0 - 490 * DAY)["observations"]
    assert [o["id"] for o in old] == ["h:a-old"]


@pytest.mark.parametrize("params", [
    {"mmsi": 12345},                                       # not 9 digits
    {"mmsi": "x"},
    {"mmsi": [230000000 + i for i in range(101)]},         # over 100 ships
    {"mmsi": A, "start": T0 - 401 * DAY, "end": T0},       # over 400 days
    {"bbox": BOX, "start": T0 - 8 * DAY, "end": T0},       # no mmsi: still 7 days
    {},                                                    # no mmsi: bbox still required
])
def test_ship_history_validation(client, params):
    assert client.get("/observations", params=params).status_code == 422


def heat(client, **params):
    r = client.get("/observations/heat", params={"bbox": BOX, "start": T0, "end": T0 + 2 * DAY, **params})
    assert r.status_code == 200, r.text
    return r.json()


def test_heat_presence_grid(client):
    body = heat(client)
    assert body["cell_deg"] == 0.1 and body["kinds"] == ["ais_presence"] and body["truncated"] is False
    assert "CC BY-NC" in body["attribution"]["gfw"]
    assert body["cells"] == [{"lat": 60.05, "lon": 25.05, "value": 8.0, "n": 6},
                             {"lat": 60.15, "lon": 25.05, "value": 0.5, "n": 1}]
    one_day = heat(client, end=T0 + DAY - 1)["cells"]
    assert one_day[0]["value"] == 4.0                        # day-1 cell left out
    coarse = heat(client, cell_deg=1)["cells"]
    assert coarse == [{"lat": 60.5, "lon": 25.5, "value": 8.5, "n": 7}]


def test_heat_sar_counts_matched_and_unmatched(client):
    body = heat(client, kinds="sar_detection")
    assert body["cells"] == [{"lat": 60.05, "lon": 25.05, "value": 5.0, "n": 3}]


def test_heat_90_days_with_clock_drift(client):
    # popular.ts sends start = now - 90 days and end = a later Date.now(): a few ms over 90 days must still answer
    assert heat(client, start=T0 - 90 * DAY, end=T0 + 25)["cells"]


def test_heat_empty(client):
    body = heat(client, bbox="0,0,1,1")
    assert body["cells"] == [] and body["attribution"] == {}


@pytest.mark.parametrize("params", [
    {"bbox": None},
    {"cell_deg": 0.01}, {"cell_deg": 2},
    {"kinds": "gap"}, {"kinds": "ais_presence,sar_detection"},
    {"start": T0 - 91 * DAY, "end": T0},
])
def test_heat_validation(client, params):
    q = {"bbox": BOX, "start": T0, "end": T0 + DAY, **params}
    assert client.get("/observations/heat", params={k: v for k, v in q.items() if v is not None}).status_code == 422


def test_heat_cap(client, monkeypatch):
    monkeypatch.setattr(query, "HEAT_MAX_CELLS", 1)
    body = heat(client)
    assert len(body["cells"]) == 1 and body["truncated"] is True and body["cells"][0]["value"] == 8.0


def test_no_pool_is_503():
    c = TestClient(make_app(lambda: None))
    assert c.get("/observations", params={"mmsi": A}).status_code == 503
    assert c.get("/observations/heat", params={"bbox": BOX}).status_code == 503
