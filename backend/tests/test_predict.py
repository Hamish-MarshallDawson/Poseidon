"""dvm.predict: artifacts, graders, the predictor cycle and the routes.

The database test runs only against a LOCAL TimescaleDB (never Tiger):

  docker run -d --name be-predict-tsdb -p 55525:5432 -e POSTGRES_PASSWORD=local timescale/timescaledb:latest-pg17
  SOURCES_TEST_DATABASE_URL=postgresql://postgres:local@127.0.0.1:55525/postgres pytest tests/test_predict.py
"""
import asyncio
import json
import math
import os
import random
from datetime import datetime, timezone

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from dvm import store as store_sql
from dvm.predict import artifact, features as F, grader, predictor as P, schema
from dvm.predict.routes import make_router

URL = os.getenv("SOURCES_TEST_DATABASE_URL", "")
needs_db = pytest.mark.skipif(not URL or "tsdb.cloud" in URL or "timescale.com" in URL,
                              reason="set SOURCES_TEST_DATABASE_URL to a local TimescaleDB")
T = 1_700_000_000_000 - (1_700_000_000_000 % 60_000)   # 2023-11-14: away from anything live
MIN, H = 60_000, 3_600_000
A, B = 211_000_001, 211_000_002


def fixes(mmsi, t0, t1, lat, lon, cog, sog=10.0, step=MIN):
    out, t = [], t0
    while t <= t1:
        out.append({"mmsi": mmsi, "ts": t, "lat": lat, "lon": lon, "sog_kn": sog, "cog_deg": cog, "heading_deg": int(cog),
                    "nav_status": 0, "cls": "A"})
        lat, lon = F.destination(lat, lon, cog, sog * F.KN_MS * step / 1000)
        t += step
    return out


# ---------------------------------------------------------------- toy LightGBM artifacts

def _toy_route_artifact(d, version="route-toy-1", east=500.0):
    lgb = pytest.importorskip("lightgbm")
    np = pytest.importorskip("numpy")
    names = ["sog_kn", "cog_sin", "cog_cos", "age_s"]
    rng = np.random.default_rng(0)
    x = rng.normal(size=(200, len(names)))
    heads = {}
    for h in artifact.ROUTE_HORIZONS_S:
        for axis, val in (("east", east), ("north", 0.0)):
            b = lgb.train({"objective": "regression", "verbose": -1, "min_data_in_leaf": 5}, lgb.Dataset(x, np.full(200, val)),
                          num_boost_round=2)
            b.save_model(str(d / f"h{h}_{axis}.txt"))
        heads[str(h)] = {"east": f"h{h}_east.txt", "north": f"h{h}_north.txt", "radius_m_80": 1000,
                         "radius_m_95": {"sog_edges_kn": [5], "r": [1500, 3000]}}
    (d / "model.json").write_text(json.dumps({
        "target": "route", "model": "lgbm-offset", "version": version, "kind": "lightgbm",
        "feature_version": F.FEATURE_VERSION, "features": names, "horizons_s": list(artifact.ROUTE_HORIZONS_S),
        "heads": heads}))
    return d


def _toy_godark_artifact(d):
    lgb = pytest.importorskip("lightgbm")
    np = pytest.importorskip("numpy")
    rng = np.random.default_rng(1)
    x, y = rng.normal(size=(300, 2)), (rng.random(300) < 0.3).astype(int)
    heads = {}
    for h in artifact.GODARK_HORIZONS_S:
        b = lgb.train({"objective": "binary", "verbose": -1}, lgb.Dataset(x, y), num_boost_round=3)
        b.save_model(str(d / f"h{h}.txt"))
        heads[str(h)] = {"model": f"h{h}.txt", "calibration": {"x": [0, 1], "y": [0, 0.5]}}
    (d / "model.json").write_text(json.dumps({
        "target": "godark", "model": "lgbm", "version": "godark-toy-1", "kind": "lightgbm",
        "feature_version": F.FEATURE_VERSION, "features": ["sog_kn", "w30m_sog_std"],
        "horizons_s": list(artifact.GODARK_HORIZONS_S), "heads": heads}))
    return d


def test_route_artifact_adds_the_offset_to_the_baseline(tmp_path):
    m = artifact.load(_toy_route_artifact(tmp_path))
    t = F.Track.from_rows(fixes(A, T, T + 30 * MIN, 55.0, 11.0, 0.0))
    out = m.predict(t.last_fix(T + 30 * MIN), F.features_at(t, T + 30 * MIN))
    assert [p["horizon_s"] for p in out] == list(artifact.ROUTE_HORIZONS_S)
    for p in out:
        e, n = F.enu_offset(p["base_lat"], p["base_lon"], p["lat"], p["lon"])
        assert e == pytest.approx(500, abs=1) and abs(n) < 1
        assert p["radius_m_80"] == 1000 and p["radius_m_95"] == 3000   # 10 kn is in the >= 5 kn band


def test_artifact_refusals(tmp_path):
    d = _toy_route_artifact(tmp_path)
    meta = json.loads((d / "model.json").read_text())
    for bad in ({"feature_version": "f0"}, {"features": ["no_such_feature"]}, {"horizons_s": [3600, 7200]},
                {"target": "weather"}):
        (d / "model.json").write_text(json.dumps({**meta, **bad}))
        with pytest.raises(artifact.ArtifactError):
            artifact.load(d)
    (d / "model.json").write_text("{")
    with pytest.raises(artifact.ArtifactError):
        artifact.load(d)


def test_godark_artifact_and_calibration(tmp_path):
    m = artifact.load(_toy_godark_artifact(tmp_path))
    ps = m.predict({"sog_kn": 0.1, "w30m_sog_std": None})
    assert set(ps) == set(artifact.GODARK_HORIZONS_S) and all(0 <= p <= 0.5 for p in ps.values())
    cal = {"x": [0.0, 0.2, 1.0], "y": [0.0, 0.1, 0.9]}
    assert artifact.calibrate(-1, cal) == 0 and artifact.calibrate(2, cal) == 0.9
    assert artifact.calibrate(0.1, cal) == pytest.approx(0.05) and artifact.calibrate(0.6, cal) == pytest.approx(0.5)
    assert artifact.calibrate(1.4, None) == 1.0


def test_champions_fall_back_to_baseline_and_reload(tmp_path):
    ch = artifact.Champions(tmp_path)
    ch.refresh()
    assert ch.route.version == artifact.ROUTE_BASELINE_VERSION and ch.godark.version == artifact.GODARK_BASELINE_VERSION
    (tmp_path / "r1").mkdir()
    _toy_route_artifact(tmp_path / "r1")
    (tmp_path / "champions.json").write_text(json.dumps({"route": "r1", "godark": "missing"}))
    ch.refresh()
    assert ch.route.version == "route-toy-1"
    assert ch.godark.version == artifact.GODARK_BASELINE_VERSION and "godark" in ch.errors


def test_baseline_rows_and_ids():
    t = F.Track.from_rows(fixes(A, T, T + 30 * MIN, 55.0, 11.0, 90.0))
    rows = P.route_rows(artifact.RouteBaseline(), A, t, T + 30 * MIN, T + 31 * MIN, None, "gap-x", "live")
    assert len(rows) == 4 and len({r["id"] for r in rows}) == 4
    r1 = rows[0]
    assert (r1["lat"], r1["lon"]) == (r1["base_lat"], r1["base_lon"]) and r1["radius_m_80"] < r1["radius_m_95"]
    assert F.haversine_m(t.lat[-1], t.lon[-1], r1["lat"], r1["lon"]) == pytest.approx(18_520, rel=1e-6)
    assert P.route_rows(artifact.RouteBaseline(), A, t, T + 7 * H, T + 7 * H, None, None, "live") == []
    s = P.godark_rows(artifact.GodarkBaseline(0.01), A, t, T + 30 * MIN, None, "live")
    assert [x["target"] for x in s] == ["dark_1h", "dark_6h", "dark_24h"]
    assert s[0]["p"] == pytest.approx(1 - math.exp(-0.01)) and s[0]["p"] < s[1]["p"] < s[2]["p"]
    assert "sog_kn" in s[0]["features"] and s[1]["features"] == {"same_as": s[0]["id"]}
    json.dumps(s[0]["features"])   # JSON-safe


def test_grade_route_and_reappear_and_dark():
    row = {"id": "r", "mmsi": A, "made_at": T, "as_of": T, "horizon_s": 3600, "model_version": "m", "lat": 55.0,
           "lon": 11.0, "radius_m_80": 500, "radius_m_95": 1000, "base_lat": 55.01, "base_lon": 11.0, "gap_id": None}
    assert grader.grade_route(row, None, T + H + MIN) is None
    assert grader.grade_route(row, None, T + 2 * H)["censored"] == "no_truth"
    o = grader.grade_route(row, (T + H, 55.005, 11.0), T + H + 6 * MIN)
    assert o["error_m"] == pytest.approx(556, rel=0.01) and o["baseline_error_m"] == pytest.approx(556, rel=0.01)
    assert o["in_r80"] is False and o["in_r95"] is True and o["truth_source"] == "own_ais"

    # Ship heading north at 10 kn: predicted points on its line; it comes back 1.5 h later 1 km east of the line.
    hs = list(artifact.ROUTE_HORIZONS_S)
    pts = [F.destination(55.0, 11.0, 0.0, 10 * F.KN_MS * h) for h in hs]
    true = F.apply_offset(*F.destination(55.0, 11.0, 0.0, 10 * F.KN_MS * 5400), 1000, 0)
    rr = {"gap_id": "g", "mmsi": B, "start_ts": T, "end_ts": T + 90 * MIN, "last_lat": 55.0, "last_lon": 11.0,
          "next_lat": true[0], "next_lon": true[1], "model_version": "m", "made_at": T + 30 * MIN, "as_of": T, "hs": hs,
          "lats": [p[0] for p in pts], "lons": [p[1] for p in pts], "blats": [p[0] for p in pts],
          "blons": [p[1] for p in pts], "r80s": [800, 2000, 4000, 9000], "r95s": [1600, 4000, 8000, 18000]}
    o = grader.grade_reappear(rr, T + 2 * H)
    assert o["score_id"] == "reappear-g-m" and o["lead_s"] == 5400
    assert o["error_m"] == pytest.approx(1000, rel=0.01) and o["in_r80"] is True   # r80 at 1.5 h is 1,400 m
    assert grader.grade_reappear({**rr, "end_ts": T + 25 * H}, T + 26 * H)["censored"] == "beyond_horizon"

    s = {"id": "s", "mmsi": A, "target": "dark_6h", "made_at": T, "horizon_s": 6 * 3600, "model_version": "m"}
    g = lambda i, ts, flag: {"id": i, "mmsi": A, "start_ts": ts, "coverage_flag": flag}   # noqa: E731
    assert grader.grade_dark(s, [], T + 7 * H)["label"] is False
    o = grader.grade_dark(s, [g("a", T + H, "coverage_gap"), g("b", T + 2 * H, "deliberate_candidate")], T + 7 * H)
    assert o["label"] is True and o["event_id"] == "b" and o["lead_s"] == 7200
    o = grader.grade_dark(s, [g("a", T + H, "own_stall"), g("c", T + 7 * H, "deliberate_candidate")], T + 7 * H)
    assert o["label"] is None and o["censored"] == "own_stall"
    assert grader.grade_dark(s, [g("a", T, "deliberate_candidate")], T + 7 * H)["label"] is False   # started before


# ---------------------------------------------------------------- database: predict, grade, serve

def _gap(mmsi, start, state, version, flag="deliberate_candidate", end=None, nxt=None, last=(55.0, 11.0)):
    return {"id": f"gap-{mmsi}-{start}", "version": version, "mmsi": mmsi, "state": state, "start_ts": start,
            "end_ts": end, "detected_at": start + 30 * MIN, "duration_s": 1800, "expected_interval_s": 60.0,
            "last_lat": last[0], "last_lon": last[1], "last_sog_kn": 10.0, "last_cog_deg": 0.0, "last_nav_status": 0,
            "next_lat": nxt[0] if nxt else None, "next_lon": nxt[1] if nxt else None, "implied_speed_kn": None,
            "draught_before_m": None, "draught_after_m": None, "neighbours_heard": 5, "neighbours_baseline": 5,
            "cell_id": "x", "coverage_flag": flag, "src": "derived", "gfw_intentional": None, "q": []}


async def _positions(con, rows):
    await con.copy_records_to_table("positions", columns=["time", *store_sql.POS_COLS], records=[
        (datetime.fromtimestamp(r["ts"] / 1000, timezone.utc), r["mmsi"], r["ts"], r["ts"],
         r["lat"], r["lon"], r["sog_kn"], r["cog_deg"], r["heading_deg"], r["nav_status"], "A", 1, "ok", "aisstream", [])
        for r in rows])


async def _reset(con):
    await store_sql.setup(con)
    await schema.setup(con)
    for t in ("route_predictions", "scores", "outcomes", "gaps", "model_runs"):   # test database only
        await con.execute(f"ALTER TABLE {t} DISABLE TRIGGER USER")
        await con.execute(f"TRUNCATE {t}")
        await con.execute(f"ALTER TABLE {t} ENABLE TRIGGER USER")
    await con.execute("DELETE FROM positions WHERE mmsi IN ($1, $2)", A, B)


async def _db_flow(tmp_path):
    con = await asyncpg.connect(URL)
    try:
        await _reset(con)
        a_fix = fixes(A, T - 2 * H, T + 2 * H + 10 * MIN, 55.0, 11.0, 90.0)   # A sails east all along
        b_all = fixes(B, T - 2 * H, T + 2 * H + 10 * MIN, 56.0, 11.0, 0.0)    # B sails north, silent T-1h..T+30m
        b_gap_start = T - H
        b_fix = [r for r in b_all if not b_gap_start < r["ts"] < T + 30 * MIN]
        b_back = next(r for r in b_fix if r["ts"] >= T + 30 * MIN)
        await _positions(con, [r for r in a_fix if r["ts"] <= T] + [r for r in b_fix if r["ts"] <= T])
        b_last = next(r for r in b_fix if r["ts"] == b_gap_start)
        await store_sql.append(con, "gaps", [_gap(B, b_gap_start, "open", 1, last=(b_last["lat"], b_last["lon"]))])

        clock = {"now": T}
        p = P.Predictor(URL, tmp_path, sample_n=50, clock=lambda: clock["now"], rng=random.Random(0))
        await p.connect()
        try:
            c1 = await p.cycle()
            assert c1 == {"gaps": 1, "active": 1, "route_rows": 8, "score_rows": 3,
                          "graded": {"route": 0, "route_reappear": 0, "dark": 0}}
            assert (await p.cycle())["gaps"] == 0   # a gap is predicted once per model version
            assert p.status["rate_per_h"] == pytest.approx(1 / 6)   # 1 deliberate gap, 1 moving ship, 6 h

            # Time passes: the rest of both tracks arrives, B's gap closes when it comes back, A goes dark at T+90m.
            await _positions(con, [r for r in a_fix if r["ts"] > T] + [r for r in b_fix if r["ts"] > T])
            await store_sql.append(con, "gaps", [
                _gap(B, b_gap_start, "closed", 2, end=b_back["ts"], nxt=(b_back["lat"], b_back["lon"]),
                     last=(b_last["lat"], b_last["lon"])),
                _gap(A, T + 90 * MIN, "closed", 1, end=T + 95 * MIN, nxt=(55.0, 11.5))])
            clock["now"] = T + 2 * H + 10 * MIN
            c2 = await p.cycle()
            # A: 1 h graded by its fix; 3/6/24 h not due. B: 1 h (target T, still dark) censored no_truth,
            # 3 h (target T+2h) graded by its fix, plus the reappearance. dark_1h of A: no gap in (T, T+1h].
            assert c2["graded"] == {"route": 3, "route_reappear": 1, "dark": 1}
            got = {r["score_id"]: r for r in await con.fetch("SELECT * FROM outcomes")}
            a1 = got[f"route-{A}-{T}-3600-{artifact.ROUTE_BASELINE_VERSION}"]
            assert a1["error_m"] < 5 and a1["baseline_error_m"] < 5 and a1["in_r80"]   # straight track: DR is exact
            b1 = got[f"route-{B}-{b_gap_start}-3600-{artifact.ROUTE_BASELINE_VERSION}"]
            assert b1["censored"] == "no_truth" and b1["event_id"] == f"gap-{B}-{b_gap_start}"
            assert got[f"route-{B}-{b_gap_start}-10800-{artifact.ROUTE_BASELINE_VERSION}"]["error_m"] < 5
            rp = got[f"reappear-gap-{B}-{b_gap_start}-{artifact.ROUTE_BASELINE_VERSION}"]
            assert rp["lead_s"] == 5400 and rp["error_m"] < 30 and rp["truth_source"] == "gap_close"
            assert got[f"score-{A}-dark_1h-{T}"]["label"] is False
            assert (await p.cycle())["graded"] == {"route": 0, "route_reappear": 0, "dark": 0}   # graded once

            # The ledger is append-only.
            with pytest.raises(asyncpg.RaiseError):
                await con.execute("UPDATE route_predictions SET lat = 0")

            # A champion appears, with a registry export: the next cycle uses it and the leaderboard lists it.
            (tmp_path / "route-toy-1").mkdir()
            _toy_route_artifact(tmp_path / "route-toy-1")
            (tmp_path / "champions.json").write_text(json.dumps({"route": "route-toy-1"}))
            run = {"run_id": "route-toy-1", "target": "route", "model": "lgbm-offset", "config": {"lr": 0.1},
                   "metrics": {"skill_1h": 0.2}, "status": "champion", "created_at": T, "recorded_at": T + 1,
                   "proposer": "default"}
            (tmp_path / "runs.jsonl").write_text(json.dumps({**run, "status": "candidate"}) + "\n" + json.dumps(run)
                                                 + "\nnot json\n")
            clock["now"] += 5 * MIN
            c3 = await p.cycle()
            assert c3["route_rows"] == 8   # A and B, both active now, with the champion
            assert await con.fetchval("SELECT count(*) FROM route_predictions WHERE model_version = 'route-toy-1'") == 8
            assert await con.fetchval("SELECT count(*) FROM model_runs") == 2

            app = FastAPI()
            app.include_router(make_router(lambda: p.pool, p.health, lambda: None, clock=lambda: clock["now"]))
            async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as http:
                r = (await http.get("/predictions", params={"mmsi": B, "hours": 72})).json()
                lb = (await http.get("/model/leaderboard", params={"hours": 168})).json()
            gapset = next(s for s in r["route"] if s["gap_id"])
            assert len(gapset["points"]) == 4 and gapset["points"][0]["grade"]["censored"] == "no_truth"
            assert r["reappear"][0]["lead_s"] == 5400
            assert lb["champions"] == {"route": "route-toy-1"} and lb["runs"][0]["status"] == "champion"
            assert lb["running"]["route_model"] == "route-toy-1"
            rows = {(x["target"], x["model_version"], x["horizon_s"]): x for x in lb["live_route"]}
            assert rows[("route", artifact.ROUTE_BASELINE_VERSION, 3600)]["n"] == 1   # B's 1 h was censored
            assert rows[("route_reappear", artifact.ROUTE_BASELINE_VERSION, 10800)]["n"] == 1
            assert lb["live_godark"][0]["n"] == 1 and lb["live_godark"][0]["positives"] == 0
        finally:
            await p.close()
    finally:
        await con.close()


@needs_db
def test_predict_grade_serve_on_local_db(tmp_path):
    asyncio.run(_db_flow(tmp_path))
