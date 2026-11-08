"""dvm.predict.backtest: availability at t, the walk, grading and idempotence.

The database test runs only against a LOCAL TimescaleDB (never Tiger); it drops and recreates the tables:

  docker run -d --name backtest-tsdb -p 55542:5432 -e POSTGRES_PASSWORD=local timescale/timescaledb:latest-pg17
  docker exec backtest-tsdb psql -U postgres -c "CREATE DATABASE bt_test"
  SOURCES_TEST_DATABASE_URL=postgresql://postgres:local@127.0.0.1:55542/bt_test pytest tests/test_predict_backtest.py
"""
import argparse
import asyncio
import json
import os
from datetime import datetime, timezone

import asyncpg
import pytest

from dvm import store as store_sql
from dvm.predict import backtest as BT, features as F

URL = os.getenv("SOURCES_TEST_DATABASE_URL", "")
needs_db = pytest.mark.skipif(not URL or BT.is_tiger(URL), reason="set SOURCES_TEST_DATABASE_URL to a local TimescaleDB")
MIN, H = 60_000, 3_600_000
T = 1_690_000_000_000 - (1_690_000_000_000 % H)   # 2023-07-22, on the hour: away from anything live and test_predict
DROP = "DROP TABLE IF EXISTS outcomes, scores, route_predictions, model_runs, gaps, positions, statics CASCADE"
A, B, C = 211_000_011, 211_000_012, 211_000_013


def gap(id_, version, start, end=None, detected=None, interval=10.0, flag="deliberate_candidate", **kw):
    return {"id": id_, "version": version, "mmsi": B, "state": "closed" if end else "open", "start_ts": start,
            "end_ts": end, "detected_at": detected if detected is not None else start + 30 * MIN,
            "expected_interval_s": interval, "last_lat": 55.0, "last_lon": 11.0, "next_lat": kw.get("next_lat"),
            "next_lon": kw.get("next_lon"), "coverage_flag": flag}


def test_opened_at_uses_the_detector_rule_and_never_later_than_stored():
    g = gap("g", 1, T, detected=T + 10 * H)                 # re-detected by a warm start 10 h later
    assert BT.opened_at(g, g["detected_at"]) == T + 30 * MIN
    assert BT.opened_at({**g, "expected_interval_s": 180}, g["detected_at"]) == T + 60 * MIN   # 20 x 3 min
    assert BT.opened_at(g, T + 31 * MIN) == T + 30 * MIN
    assert BT.opened_at(g, T + 20 * MIN) == T + 20 * MIN


def test_gaps_known_at_t():
    rows = [gap("g1", 1, T), gap("g1", 2, T, end=T + 2 * H, next_lat=55.1, next_lon=11.1),
            gap("g2", 1, T + 3 * H, flag="coverage_gap")]
    g = BT.Gaps(rows, history_start=T)
    assert [x["id"] for x in g.open_at(T + 29 * MIN)] == []           # not yet detectable
    assert [x["id"] for x in g.open_at(T + 30 * MIN)] == ["g1"]
    assert [x["id"] for x in g.open_at(T + 2 * H)] == []              # closed by then: the ship was heard again
    assert [x["id"] for x in g.open_at(T + 4 * H)] == ["g2"]
    assert g.deliberate_between(T - H, T + 4 * H, T + 4 * H) == 1     # g2 is a coverage gap
    assert g.deliberate_between(T - H, T + 4 * H, T + 10 * MIN) == 0  # g1 not known yet


def test_score_slot_is_stable_and_spread():
    assert BT.score_slot(A, 6) == BT.score_slot(A, 6)
    assert len({BT.score_slot(m, 6) for m in range(211_000_000, 211_000_100)}) == 6


def test_refuses_tiger_target(monkeypatch):
    monkeypatch.setenv("TIGER_DATABASE_URL", "postgresql://u:p@x.tsdb.cloud.timescale.com:5432/tsdb")
    with pytest.raises(SystemExit, match="Refusing"):
        BT.main(["--from", "2026-11-07T20:00Z", "--to", "2026-11-07T21:00Z", "--source", "postgresql://local/x",
                 "--db", "postgresql://u:p@x.tsdb.cloud.timescale.com:5432/tsdb"])


def test_parse_ts():
    assert BT.parse_ts("2023-11-14T22:13:20Z") == BT.parse_ts("2023-11-14T22:13:20+00:00") == BT.parse_ts("1700000000000")


def _fixes(mmsi, t0, t1, lat, lon, cog=90.0, sog=10.0, step=MIN, late_ms=0):
    out, t = [], t0
    while t <= t1:
        out.append((mmsi, t, t + late_ms, lat, lon, sog, cog, int(cog), 0, "A", 1, "ok", "test"))
        lat, lon = F.destination(lat, lon, cog, sog * F.KN_MS * step / 1000)
        t += step
    return out


async def _seed(con):
    await con.execute(DROP)
    await con.execute(store_sql.SCHEMA)
    rows = (_fixes(A, T - H, T + 8 * H, 55.0, 11.0)
            + _fixes(B, T - H, T + H + 5 * MIN, 55.2, 11.0)            # B goes silent at T + 1:05 ...
            + _fixes(B, T + 3 * H, T + 8 * H, 55.2, 11.6)              # ... and is heard again at T + 3:00
            + _fixes(C, T - H, T + 8 * H, 55.4, 11.0, late_ms=5 * MIN))   # every fix of C arrives 5 min late
    await con.copy_records_to_table("positions", records=[
        (datetime.fromtimestamp(r[1] / 1000, timezone.utc), *r)
        for r in rows], columns=["time", "mmsi", "ts", "recv_ts", "lat", "lon", "sog_kn", "cog_deg", "heading_deg",
                                 "nav_status", "cls", "msg_type", "ts_quality", "src"])
    start, end = T + H + 5 * MIN, T + 3 * H
    early = {**gap("gx", 1, T - 2 * H, end=T - H, flag="own_stall", next_lat=56.0, next_lon=12.0), "mmsi": 211_000_099}
    for g in (early, gap("gb", 1, start, detected=T + 5 * H),               # stored detected_at from a later warm start
              gap("gb", 2, start, end=end, detected=T + 5 * H, next_lat=55.2, next_lon=11.6)):
        await con.execute(
            "INSERT INTO gaps (id, version, mmsi, state, start_ts, end_ts, detected_at, duration_s, expected_interval_s, "
            "last_lat, last_lon, next_lat, next_lon, neighbours_heard, neighbours_baseline, cell_id, coverage_flag, src) "
            "VALUES ($1, $2, $3, $4, $5, $6, $7, 0, $8, $9, $10, $11, $12, 5, 5, 'c', $13, 'derived')",
            g["id"], g["version"], g["mmsi"], g["state"], g["start_ts"], g["end_ts"], g["detected_at"], g["expected_interval_s"],
            55.2, 11.0 + 0.0, g["next_lat"], g["next_lon"], g["coverage_flag"])


def _args(**kw):
    d = dict(from_=str(T), to=str(T + 4 * H), step_min=10, db=URL, source=URL, allow_tiger=False, model_dir=None,
             sample=10, data_end=str(T + 8 * H), json=None)
    d.update(kw)
    return argparse.Namespace(**d)


@needs_db
def test_backtest_walk_grade_and_rerun():
    async def go():
        con = await asyncpg.connect(URL)
        try:
            await _seed(con)
        finally:
            await con.close()
        first = await BT.run(_args())
        con = await asyncpg.connect(URL)
        try:
            gap_rows = await con.fetch("SELECT * FROM route_predictions WHERE gap_id = 'gb' ORDER BY horizon_s")
            scores = await con.fetch("SELECT * FROM scores ORDER BY made_at, mmsi, target")
            outs = {r["score_id"]: r for r in await con.fetch("SELECT * FROM outcomes")}
            c_rows = await con.fetch("SELECT features FROM scores WHERE mmsi = $1 AND target = 'dark_6h'", C)
        finally:
            await con.close()
        try:
            second = await BT.run(_args())
        finally:   # leave the shared test database as the other suites expect it
            con = await asyncpg.connect(URL)
            await con.execute(DROP)
            await store_sql.setup(con)
            await con.close()
        return first, second, gap_rows, scores, outs, c_rows

    first, second, gap_rows, scores, outs, c_rows = asyncio.run(go())
    # B's gap: predicted once, from its last fix, at the first step after the detector would have opened it
    # (T + 1:35 -> the T + 1:40 step), not at the stored warm-start detected_at (T + 5 h).
    assert [r["horizon_s"] for r in gap_rows] == [3600, 10800, 21600, 86400]
    assert {r["as_of"] for r in gap_rows} == {T + H + 5 * MIN} and {r["made_at"] for r in gap_rows} == {T + H + 40 * MIN}
    assert {r["mode"] for r in gap_rows} == {"backtest"}
    # Hourly frozen sets: the first full hour of the walk is (T, T + 1 h], so sets at T + 1 h .. T + 4 h.
    assert sorted({s["made_at"] for s in scores}) == [T + H, T + 2 * H, T + 3 * H, T + 4 * H]
    assert {s["mode"] for s in scores} == {"backtest"}
    assert B not in {s["mmsi"] for s in scores if s["made_at"] == T + 2 * H}   # dark through that hour
    # C's fixes arrive 5 min late: its newest usable fix at t is at least 5 min old (age_s at scoring time).
    ages = [json.loads(r["features"])["age_s"] for r in c_rows]
    assert ages and min(ages) >= 300
    # Grades: B's dark_1h at T + 1 h is a hit (its gap starts at T + 1:05); A's is a miss; the gap's reappearance.
    assert outs[f"score-{B}-dark_1h-{T + H}"]["label"] is True
    assert outs[f"score-{B}-dark_1h-{T + H}"]["lead_s"] == 300
    assert outs[f"score-{A}-dark_1h-{T + H}"]["label"] is False
    re = outs[f"reappear-gb-{gap_rows[0]['model_version']}"]
    assert re["truth_source"] == "gap_close" and re["error_m"] is not None and re["resolved_at"] == T + 3 * H
    graded = [o for o in outs.values() if o["target"] == "route" and o["error_m"] is not None]
    assert graded and all(abs(o["truth_ts"] - (o["resolved_at"] - 5 * MIN)) <= 5 * MIN for o in graded)
    assert first["new_rows"]["route_predictions"] > 0 and first["new_rows"]["outcomes"] > 0
    assert first["skill"]["route"] and first["skill"]["godark"]
    # Idempotent: a re-run of the same range writes nothing new.
    assert second["new_rows"] == {"route_predictions": 0, "scores": 0, "outcomes": 0}
    assert second["total_rows"] == first["total_rows"]


def test_backtest_loads_the_champions_from_model_dir(tmp_path):
    """The backtest must use the champions in --model-dir from its first step, like the live predictor (which
    refreshes every cycle); without a refresh it silently ran the baselines."""
    from tests.test_predict import _toy_godark_artifact, _toy_route_artifact
    (tmp_path / "route-a").mkdir(); (tmp_path / "godark-a").mkdir()
    _toy_route_artifact(tmp_path / "route-a", version="route-toy-bt")
    _toy_godark_artifact(tmp_path / "godark-a")
    (tmp_path / "champions.json").write_text(json.dumps({"route": "route-a", "godark": "godark-a"}))
    bt = BT.Backtest(object(), object(), tmp_path, 10 * 60_000)
    assert bt.champions.route.version == "route-toy-bt"
    assert not bt.champions.errors
    assert "baseline" not in bt.champions.godark.version
