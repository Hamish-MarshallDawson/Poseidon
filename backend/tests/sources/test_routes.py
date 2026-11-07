"""The /observations, /sources and /model/* routes against a real local TimescaleDB (see test_db.py for the setup).

The routes are mounted on a tiny FastAPI app whose lifespan owns the asyncpg pool, so TestClient exercises the real
SQL. The 503 and auth tests need no database.
"""
import asyncio
import contextlib
import os
import time

import asyncpg
import jwt
import pytest
from fastapi import Depends, FastAPI, Header
from fastapi.testclient import TestClient

from dvm import auth, store
from dvm.sources import routes, schema
from dvm.sources.common import Observation
from dvm.models import VesselStatic

URL = os.getenv("SOURCES_TEST_DATABASE_URL", "")
needs_db = pytest.mark.skipif(not URL or "tsdb.cloud" in URL or "timescale.com" in URL,
                              reason="set SOURCES_TEST_DATABASE_URL to a local TimescaleDB")
T0 = 1_700_000_000_000
AVAIL = T0 + 1000
BOX = "24,59,26,61"


async def open_login(authorization: str | None = Header(None)) -> None:
    return None


def make_app(get_pool, login=open_login, lifespan=None) -> FastAPI:
    app = FastAPI(lifespan=lifespan)
    app.include_router(routes.make_router(get_pool, login))
    return app


def obs(i, **kw):
    base = dict(id=f"rt:{i:02d}", src="gfw", kind="gap", ts=T0 + i * 10, end_ts=T0 + i * 10 + 5, recv_ts=AVAIL,
                available_ts=AVAIL, mmsi=230099950, lat=60.0, lon=25.0, value=1.0,
                attrs={"name": "X", "vessel_id": "secret-heavy", "detail": {"a": 1}})
    return Observation(**{**base, **kw})


def pos(mmsi, ts, recv_ts=None, lat=60.0, lon=25.0, src="aisstream", msg_type=1):
    return (ts, recv_ts if recv_ts is not None else ts + 500, lat, lon, 5.0, 90.0, 90, 0, "A", msg_type,
            "source", src, [])


def static(mmsi, ts, src, **kw):
    return VesselStatic(mmsi=mmsi, ts=ts, recv_ts=ts + 100, mid=230, src=src, **kw)


async def seed():
    con = await asyncpg.connect(URL)
    try:
        await store.setup(con)
        await schema.setup(con)
        for t in ("observations", "positions", "statics", "source_windows"):
            await con.execute(f"DELETE FROM {t}")
        rows = [obs(i) for i in range(1, 6)]
        rows += [obs(6, ts=T0 + 20, end_ts=None, kind="ais_presence", mmsi=None, id="rt:tie-a"),    # ties with obs(2)
                 obs(7, ts=T0 + 20, end_ts=None, kind="ais_presence", mmsi=None, id="rt:tie-b"),
                 obs(8, id="rt:late", available_ts=AVAIL + 5000),
                 obs(9, id="rt:far", lat=10.0, lon=100.0),
                 obs(10, id="rt:scene", kind="radar_scene", src="sentinel1", mmsi=None, bbox=(24, 59, 27, 62),
                     geom={"type": "Polygon", "coordinates": [[[24, 59], [27, 59], [27, 62], [24, 62], [24, 59]]]},
                     attrs={"platform": "sentinel-1a", "vv_href": "s3://big/asset.tiff"})]
        await schema.write_observations(con, rows)
        ps = [pos(1, T0), pos(1, T0 + 1000), pos(2, T0 + 1000), pos(2, T0 + 1000, src="digitraffic"),   # tie on ts+mmsi
              pos(3, T0 + 2000, lat=10.0, lon=100.0), pos(1, T0 + 3000, recv_ts=T0 + 90_000)]
        await con.copy_records_to_table("positions", records=[
            (schema._dt(p[0]), m, *p) for m, p in zip([1, 1, 2, 2, 3, 1], ps)],
            columns=["time", "mmsi", *store.POS_COLS[1:]])
        await schema.write_statics(con, [
            static(7, T0, "aisstream", name="OLD NAME", type_group="cargo", length_m=100),
            static(7, T0 + 5000, "gfw", name="NEW NAME", type_group="cargo", flag_iso2="DK"),
            static(8, T0, "digitraffic", name="OTHER", type_group="tanker")])
        for src in ("gfw", "sentinel1"):
            await schema.record_window(con, src, "all", "rt", T0, T0 + 1, time.time_ns() // 10**6, 3, "ok")
    finally:
        await con.close()


@pytest.fixture(scope="module")
def client():
    if not URL or "tsdb.cloud" in URL or "timescale.com" in URL:
        pytest.skip("set SOURCES_TEST_DATABASE_URL to a local TimescaleDB")
    asyncio.run(seed())
    state = {}

    @contextlib.asynccontextmanager
    async def lifespan(app):
        state["pool"] = await asyncpg.create_pool(URL, min_size=1, max_size=3)
        yield
        await state["pool"].close()

    with TestClient(make_app(lambda: state["pool"], lifespan=lifespan)) as c:
        yield c


def page_all(client, path, key, **params):
    """Follow next_cursor to the end; returns (all rows, number of pages)."""
    out, pages, cursor = [], 0, None
    while True:
        r = client.get(path, params={**params, **({"cursor": cursor} if cursor else {})})
        assert r.status_code == 200, r.text
        body = r.json()
        out += body[key]
        pages += 1
        cursor = body["next_cursor"]
        if not cursor:
            return out, pages


@needs_db
@pytest.mark.parametrize("path, params", [
    ("/observations", {}),                                                    # bbox missing
    ("/observations", {"bbox": "1,2,3"}),
    ("/observations", {"bbox": "a,b,c,d"}),
    ("/observations", {"bbox": "0,0,200,10"}),
    ("/observations", {"bbox": "5,5,5,9"}),
    ("/observations", {"bbox": BOX, "start": 2000, "end": 1000}),
    ("/observations", {"bbox": BOX, "start": 0, "end": 8 * 86_400_000}),     # window over 7 days
    ("/observations", {"bbox": BOX, "kinds": "gap,nonsense"}),
    ("/observations", {"bbox": BOX, "limit": 5001}),
    ("/model/observations", {}),                                              # as_of missing
    ("/model/observations", {"as_of": "yesterday"}),
    ("/model/observations", {"as_of": -5}),
    ("/model/observations", {"as_of": T0, "start": 5, "end": 1}),
    ("/model/observations", {"as_of": T0, "cursor": "!!"}),
    ("/model/observations", {"as_of": T0, "limit": 50_001}),
    ("/model/positions", {}),
    ("/model/positions", {"as_of": T0, "cursor": "e30"}),                    # valid base64, wrong shape
    ("/model/positions", {"as_of": T0, "mmsi": "x"}),
    ("/model/statics", {}),
])
def test_validation(client, path, params):
    assert client.get(path, params=params).status_code == 422


@needs_db
def test_map_observations(client):
    r = client.get("/observations", params={"bbox": BOX, "start": T0, "end": T0 + 100})
    assert r.status_code == 200
    body = r.json()
    ids = {o["id"] for o in body["observations"]}
    assert ids == {f"rt:{i:02d}" for i in range(1, 6)} | {"rt:tie-a", "rt:tie-b", "rt:late", "rt:scene"}   # not rt:far
    assert "CC BY-NC" in body["attribution"]["gfw"] and "sentinel1" in body["attribution"]
    by = {o["id"]: o for o in body["observations"]}
    assert by["rt:01"]["attrs"] == {"name": "X"}                     # heavy attrs dropped
    assert "geom" not in by["rt:01"] and by["rt:scene"]["geom"]["type"] == "Polygon"
    assert by["rt:scene"]["attrs"] == {"platform": "sentinel-1a"}
    assert "recv_ts" not in by["rt:01"]
    only = client.get("/observations", params={"bbox": BOX, "start": T0, "end": T0 + 100, "kinds": "radar_scene"})
    assert [o["id"] for o in only.json()["observations"]] == ["rt:scene"]
    far = client.get("/observations", params={"bbox": "99,9,101,11", "start": T0, "end": T0 + 100}).json()
    assert [o["id"] for o in far["observations"]] == ["rt:far"]
    lim = client.get("/observations", params={"bbox": BOX, "start": T0, "end": T0 + 100, "limit": 2}).json()
    assert len(lim["observations"]) == 2


@needs_db
def test_map_default_window_is_recent(client):
    assert client.get("/observations", params={"bbox": BOX}).json()["observations"] == []   # 2023 rows are old


@needs_db
def test_sources(client):
    body = client.get("/sources").json()
    by = {s["src"]: s for s in body["sources"]}
    assert {"gfw", "sentinel1", "aisstream", "digitraffic"} <= set(by)
    assert by["gfw"]["attribution"] and by["gfw"]["last_fetch_ts"] and body["now"] > T0


@needs_db
def test_model_as_of_leakage(client):
    early = client.get("/model/observations", params={"as_of": AVAIL - 1, "start": T0, "end": T0 + 100}).json()
    assert early["observations"] == [] and early["next_cursor"] is None
    ok = client.get("/model/observations", params={"as_of": AVAIL, "start": T0, "end": T0 + 100}).json()
    ids = {o["id"] for o in ok["observations"]}
    assert "rt:late" not in ids and "rt:01" in ids and ok["as_of"] == AVAIL
    later = client.get("/model/observations", params={"as_of": AVAIL + 5000, "start": T0, "end": T0 + 100}).json()
    assert "rt:late" in {o["id"] for o in later["observations"]}
    full = ok["observations"][0]
    assert full["attrs"]["vessel_id"] == "secret-heavy" and "recv_ts" in full and "available_ts" in full   # full cols
    assert "CC BY-NC" in ok["attribution"]["gfw"]
    boxed = client.get("/model/observations", params={"as_of": AVAIL, "bbox": "99,9,101,11", "start": T0,
                                                      "end": T0 + 100}).json()
    assert [o["id"] for o in boxed["observations"]] == ["rt:far"]


@needs_db
def test_model_observation_paging_no_gaps_no_repeats(client):
    params = {"as_of": AVAIL + 5000, "start": T0, "end": T0 + 100}
    whole = client.get("/model/observations", params={**params, "limit": 100}).json()["observations"]
    for limit in (1, 2, 3, 4):
        rows, pages = page_all(client, "/model/observations", "observations", **params, limit=limit)
        assert [o["id"] for o in rows] == [o["id"] for o in whole], limit    # same order, nothing lost or doubled
        assert pages == -(-len(whole) // limit) or pages == len(whole) // limit + 1


@needs_db
def test_model_positions(client):
    base = {"as_of": T0 + 10_000, "start": T0, "end": T0 + 5000}
    whole = client.get("/model/positions", params={**base, "limit": 100}).json()
    keys = [(p["ts"], p["mmsi"]) for p in whole["positions"]]
    assert keys == sorted(keys) and len(keys) == 5                       # recv_ts > as_of row (mmsi 1 @ +3000) excluded
    assert "aisstream" in whole["attribution"] and "digitraffic" in whole["attribution"]
    for limit in (1, 2, 3):
        rows, _ = page_all(client, "/model/positions", "positions", **base, limit=limit)
        assert [(p["ts"], p["mmsi"], p["src"]) for p in rows] == [(p["ts"], p["mmsi"], p["src"])
                                                                  for p in whole["positions"]], limit
    late = client.get("/model/positions", params={**base, "as_of": T0 + 100_000, "limit": 100}).json()
    assert len(late["positions"]) == 6
    assert [p["mmsi"] for p in client.get("/model/positions", params={**base, "mmsi": [2, 3], "limit": 100})
            .json()["positions"]] == [2, 2, 3]
    boxed = client.get("/model/positions", params={**base, "bbox": "99,9,101,11"}).json()["positions"]
    assert [p["mmsi"] for p in boxed] == [3]
    tight = client.get("/model/positions", params={"as_of": T0 + 10_000, "end": T0 + 999}).json()["positions"]
    assert [p["ts"] for p in tight] == [T0]


@needs_db
def test_model_statics(client):
    now = client.get("/model/statics", params={"as_of": T0 + 10_000, "mmsi": 7}).json()
    s = now["statics"][0]
    assert s["name"] == "NEW NAME" and s["sources"]["name"] == "gfw"
    assert s["length_m"] == 100 and s["sources"]["length_m"] == "aisstream"    # field-wise newest non-null
    assert s["flag_iso2"] == "DK" and set(now["attribution"]) == {"aisstream", "gfw"}
    before = client.get("/model/statics", params={"as_of": T0 + 1000, "mmsi": 7}).json()["statics"][0]
    assert before["name"] == "OLD NAME" and before["flag_iso2"] is None        # nothing from the future
    assert client.get("/model/statics", params={"as_of": T0 - 1, "mmsi": 7}).json()["statics"] == []
    rows, pages = page_all(client, "/model/statics", "statics", as_of=T0 + 10_000, limit=1)
    assert [r["mmsi"] for r in rows] == [7, 8] and pages == 2


def test_no_pool_is_503():
    c = TestClient(make_app(lambda: None))
    assert c.get("/observations", params={"bbox": BOX}).status_code == 503
    assert c.get("/sources").status_code == 503
    assert c.get("/model/observations", params={"as_of": T0}).status_code == 503
    assert c.get("/model/positions", params={"as_of": T0}).status_code == 503
    assert c.get("/model/statics", params={"as_of": T0}).status_code == 503
    assert c.get("/model/observations").status_code == 422     # validation still runs before the pool



def real_login_app(monkeypatch, enabled):
    from dvm import app as backend
    monkeypatch.setattr(auth, "ENABLED", enabled)

    async def verify(token):
        raise jwt.InvalidTokenError("nope")
    monkeypatch.setattr(auth, "verify_async", verify)
    return TestClient(make_app(lambda: None, login=backend.require_login))


def test_auth_required_when_auth0_configured(monkeypatch):
    monkeypatch.setenv("MODEL_API_TOKEN", "s3cret-train")
    c = real_login_app(monkeypatch, True)
    for path, q in (("/observations", {"bbox": BOX}), ("/sources", {}), ("/model/observations", {"as_of": T0}),
                    ("/model/positions", {"as_of": T0}), ("/model/statics", {"as_of": T0})):
        assert c.get(path, params=q).status_code == 401, path
        assert c.get(path, params=q, headers={"Authorization": "Bearer junk"}).status_code == 401, path
    # the service token opens the model routes only (503 = past auth, pool is None), never the map routes
    tok = {"Authorization": "Bearer s3cret-train"}
    assert c.get("/model/statics", params={"as_of": T0}, headers=tok).status_code == 503
    assert c.get("/model/positions", params={"as_of": T0}, headers=tok).status_code == 503
    assert c.get("/sources", headers=tok).status_code == 401
    assert c.get("/model/statics", params={"as_of": T0}, headers={"Authorization": "Bearer s3cret-trai"}
                 ).status_code == 401


def test_open_when_auth0_not_configured(monkeypatch):
    c = real_login_app(monkeypatch, False)
    assert c.get("/sources").status_code == 503      # past auth, no pool
    assert c.get("/model/statics", params={"as_of": T0}).status_code == 503
