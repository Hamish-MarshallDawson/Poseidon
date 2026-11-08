"""Model Lab metrics routes (dvm/lab/metrics.py): the shaping helpers, and the three routes on a local TimescaleDB.

  SOURCES_TEST_DATABASE_URL=postgresql://postgres:local@127.0.0.1:55545/lab_metrics_test pytest tests/test_lab_metrics.py
The database test truncates the ledger tables: point it at a database of its own.
"""
from __future__ import annotations

import asyncio
import json
import os

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from dvm import store as store_sql
from dvm.lab import metrics as M
from dvm.predict import schema
from dvm.sources import schema as sources_schema

URL = os.getenv("SOURCES_TEST_DATABASE_URL", "")
needs_db = pytest.mark.skipif(not URL or "tsdb.cloud" in URL or "timescale.com" in URL,
                              reason="set SOURCES_TEST_DATABASE_URL to a local TimescaleDB")
H = 3_600_000
T = 1_700_000_000_000 - (1_700_000_000_000 % H)   # on the hour, far from anything live
NOW = T + 20 * H


def test_brier_skill_and_route_row():
    assert M.brier_skill(0.0009, 0.0009) == pytest.approx(1 - 1 / 0.9991)
    assert M.brier_skill(0.1, 0.0) is None
    r = M.route_row({"median_err_m": 250.0, "baseline_median_err_m": 500.0})
    assert r["skill"] == pytest.approx(0.5)
    assert M.route_row({"median_err_m": 1.0, "baseline_median_err_m": 0.0})["skill"] is None


def test_pick_version_prefers_champion_then_its_base_then_real_models():
    v = {"baseline-rate-v1": 900, "godark-a": 10, "godark-b": 50}
    assert M.pick_version(v, "godark-a") == "godark-a"
    assert M.pick_version(v, "godark-a-cal2") == "godark-a"
    assert M.pick_version(v, "other") == "godark-b"
    assert M.pick_version({"baseline-rate-v1": 3}, None) == "baseline-rate-v1"
    assert M.pick_version({}, "x") is None


def test_cumulative_counts_from_before():
    rows = [{"t": 1, "mode": "backtest", "n": 5}, {"t": 1, "mode": "live", "n": 2}, {"t": 2, "mode": "live", "n": 3},
            {"t": 2, "mode": "unknown", "n": 1}]
    assert [x["cumulative"] for x in M.cumulative(rows, {"live": 10})] == [5, 12, 15, 1]


def test_offline_skill_and_find_run():
    run = {"run_id": "route-x", "target": "route", "status": "champion", "recorded_at": 5, "artifact": None,
           "metrics": {"skill": {"10800": {"skill": 0.6, "skill_lo": 0.5, "skill_hi": 0.7}},
                       "holdout": {"name": "v1", "n": 509061}}}
    old = {**run, "run_id": "route-old", "recorded_at": 1}
    off = M.offline_skill(run["metrics"], 10800)
    assert off == {"primary_h": 10800, "statistic": None, "skill": 0.6, "skill_lo": 0.5, "skill_hi": 0.7,
                   "holdout": "v1, 509,061 cases"}
    assert M.offline_skill({"skill": {"3600": {"skill": 0.1}}}, 10800)["primary_h"] == 3600   # falls back
    assert M.offline_skill({}, 10800)["skill"] is None
    assert M.find_run([old, run], "route", "route-x-cal1")["run_id"] == "route-x"
    assert M.find_run([old, run], "route", "unknown")["run_id"] == "route-x"   # newest champion
    assert M.find_run([old, run], "fishing", None) is None


ROUTE_M = {"loss_name": "error_m", "skill": {"10800": {"skill": 0.62, "skill_lo": 0.6, "skill_hi": 0.64}}}
# a converted go-dark run: log-loss skill in `skill`, Brier skill beside it in `summary`
DARK_M = {"loss_name": "log_loss", "skill": {"21600": {"skill": 0.026}, "3600": {"skill": -0.033}},
          "summary": {"21600": {"brier_skill": 0.012, "brier_skill_ci": [-0.018, 0.039]},
                      "3600": {"brier_skill": 0.0001, "brier_skill_ci": [-0.024, 0.027]}}}


def test_live_cards_and_note():
    rows = [{"model_version": "r", "n": 4, "cov80": 0.6, "med": 300.0, "base": 600.0}]
    live = M.route_live(rows, "r", ROUTE_M)
    assert live["primary"]["value"] == pytest.approx(0.5) and live["calibration"]["ok"] is False
    assert live["offline"] == {"statistic": "median-error skill", "horizon_s": 10800, "skill": 0.62, "skill_lo": 0.6,
                               "skill_hi": 0.64}
    assert M.note(live, True) == "live skill below offline; 80% circle coverage off target (60.0% vs 80.0%)"
    # the recalibrated champion has no grades of its own yet: no card under its name from the older model's grades
    assert M.route_live(rows, "r-cal1", ROUTE_M) is None
    assert M.note(None, True, "r") == "no live grades for this version yet (the last 24 h graded r)"
    dark = M.dark_live([{"model_version": "g", "n": 10, "mean_p": 0.05, "hit_rate": 0.046, "brier": 0.05}], "g",
                       "dark_1h", DARK_M)
    assert dark["primary"]["name"] == "Brier skill over the base rate, 1 h" and dark["calibration"]["ok"]
    assert (dark["statistic"], dark["horizon_s"]) == ("Brier skill", 3600)
    # compared with the held-out Brier skill at 1 h, never with the log-loss skill at 6 h
    assert dark["offline"] == {"statistic": "Brier skill", "horizon_s": 3600, "skill": 0.0001, "skill_lo": -0.024,
                               "skill_hi": 0.027}
    assert M.note(dark, True).startswith("live skill below offline")
    assert M.offline_skill(DARK_M, 21600)["statistic"] == "log-loss skill"
    no_match = M.dark_live([{"model_version": "g", "n": 10, "mean_p": 0.05, "hit_rate": 0.046, "brier": 0.05}], "g",
                           "dark_1h", {"loss_name": "log_loss", "skill": {"3600": {"skill": 0.5}}})
    assert no_match["offline"] is None and "offline" not in M.note(no_match, True)
    assert M.note(None, False) == "not served live yet"


def test_champion_since_counts_only_deployed_events():
    run = {"run_id": "r", "status": "champion", "recorded_at": 1}
    ev = [{"ts": 5, "target": "route", "kind": "promoted", "run_id": "r", "version": "r"},
          {"ts": 7, "target": "route", "kind": "deployed", "run_id": "r", "version": "r"},
          {"ts": 9, "target": "route", "kind": "recalibrated", "run_id": "r", "version": "r-cal1"}]
    assert M.champion_since(ev, "route", "r-cal1", run) == 7        # the cal1 build is not when it went live
    ev.append({"ts": 11, "target": "route", "kind": "deployed", "run_id": "r", "version": "r-cal1"})
    assert M.champion_since(ev, "route", "r-cal1", run) == 11
    assert M.champion_since(ev[:1], "route", "r", run) == 1        # no deploy recorded: the champion row


def test_reliability_and_lift_pick_one_model_per_target():
    rows = [{"target": "dark_6h", "model_version": "g", "bin": 2, "n": 3, "p_mean": 0.06, "hit_rate": 0.0},
            {"target": "dark_6h", "model_version": "g", "bin": 0, "n": 5, "p_mean": 0.01, "hit_rate": 0.0},
            {"target": "dark_6h", "model_version": "baseline-rate-v1", "bin": 0, "n": 99, "p_mean": 0.02,
             "hit_rate": 0.02}]
    rel = M.reliability(rows, None)
    assert rel == [{"target": "dark_6h", "model_version": "g", "bins": [
        {"p_mean": 0.01, "hit_rate": 0.0, "n": 5}, {"p_mean": 0.06, "hit_rate": 0.0, "n": 3}]}]
    lf = M.lift([{"target": "dark_6h", "model_version": "g", "n": 8, "top_hit_rate": 1.0, "all_hit_rate": 0.1}], "g")
    assert lf[0]["top_share"] == 0.1 and lf[0]["top_hit_rate"] == 1.0


async def _seed(con):
    await store_sql.setup(con)
    await schema.setup(con)
    await sources_schema.setup(con)
    for t in ("route_predictions", "scores", "outcomes", "model_runs", "source_windows"):   # test database only
        await con.execute(f"ALTER TABLE {t} DISABLE TRIGGER USER")
        await con.execute(f"TRUNCATE {t}")
        await con.execute(f"ALTER TABLE {t} ENABLE TRIGGER USER")
    await con.execute("TRUNCATE positions")
    await con.execute("DROP TABLE IF EXISTS ml_events, ml_proposals")   # lab-store's tables: absent at first
    await con.execute("ALTER TABLE model_runs DROP COLUMN IF EXISTS source")
    routes, outs = [], []
    # 4 live route-x predictions at 3 h: errors 100..400 against DR 200..800, 3 of 4 inside the 80% circle.
    for i, (err, base, in80) in enumerate([(100, 200, True), (200, 400, True), (300, 600, True), (400, 800, False)]):
        pid = f"route-{i}-{T}-10800-route-x"
        routes.append((pid, 1, T, T, "route-x", 10800, 55.0, 11.0, 1000.0, 2000.0, 55.0, 11.0, None, "f1", "live",
                       None, None, None, None))
        outs.append((pid, 1, "route", T, 10800, T + 4 * H, None, None, None, None, "route-x", "ais", T + 3 * H, 55.0,
                     11.0, float(err), float(base), in80, True))
    # one backtest baseline prediction at 1 h, an hour later
    routes.append(("route-9-b", 9, T + H, T + H, "baseline-dr-v1", 3600, 55.0, 11.0, 1.0, 2.0, 55.0, 11.0, None,
                   "f1", "backtest", None, None, None, None))
    outs.append(("route-9-b", 9, "route", T + H, 3600, T + 3 * H, None, None, None, None, "baseline-dr-v1", "ais",
                 T + 2 * H, 55.0, 11.0, 50.0, 50.0, False, True))
    # gap reappearance grades: one of a gap with a live route prediction (made_at T, the gap's first), one of a gap
    # whose predictions are gone (mode unknown)
    routes.append((f"route-1-{T}-3600-route-x-g", 1, T, T, "route-x", 3600, 55.0, 11.0, 1.0, 2.0, 55.0, 11.0,
                   f"gap-1-{T}", "f1", "live", None, None, None, None))
    outs.append((f"reappear-gap-1-{T}-route-x", 1, "route_reappear", T, 3000, T + H, None, None, f"gap-1-{T}", 3000,
                 "route-x", "gap_close", T + 3000_000, 55.0, 11.0, 10.0, 20.0, True, True))
    outs.append(("reappear-gap-2-x", 2, "route_reappear", T, 3000, T + H, None, None, "gap-2-x", 3000, "route-x",
                 "gap_close", T + 3000_000, 55.0, 11.0, 10.0, 20.0, True, True))
    # 10 live go-dark dark_1h scores: the top one went dark, the rest did not
    scores = []
    for i in range(10):
        p = 0.9 if i == 0 else 0.03
        sid = f"score-{i}-dark_1h-{T + H}"
        scores.append((sid, 100 + i, "dark_1h", T + H, 3600, p, "godark-x", "f1", "{}", None, "live"))
        outs.append((sid, 100 + i, "dark_1h", T + H, 3600, T + 2 * H + 1800_000, i == 0, None, None, None, None, None,
                     None, None, None, None, None, None, None))
    await con.executemany(schema.ROUTE_INSERT, routes)
    await con.executemany(schema.SCORE_INSERT, scores)
    await con.executemany(schema.OUTCOME_INSERT, outs)
    metrics = {"loss_name": "error_m", "skill": {"10800": {"skill": 0.6, "skill_lo": 0.55, "skill_hi": 0.65}},
               "holdout": {"name": "v1", "n": 1000, "start": 1, "end": 2, "hash": "h1"},
               "split": {"n_train": 5000}}
    runs = [("route-x", "route", "dma", "{}", "d", 0, 1, json.dumps(metrics), None, "human", None, "candidate", T - H,
             T - H),
            ("route-x", "route", "dma", "{}", "d", 0, 1, json.dumps(metrics), None, "human", None, "champion", T - H,
             T - H + 1),
            ("route-y", "route", "dma", "{}", "d", 0, 1, json.dumps(metrics), None, "gemini", "route-x", "rejected",
             T - H / 2, T - H / 2)]
    await con.executemany(schema.RUN_INSERT, runs)
    await con.execute("INSERT INTO source_windows VALUES ('gfw', 'gaps', 'baltic', $1, $2, $2, $2, 7, 'ok', NULL), "
                      "('gfw', 'gaps', 'baltic', $2, $3, $3, $3, 0, 'error', 'boom')", T - 48 * H, T - 24 * H, T)


async def _db_flow():
    con = await asyncpg.connect(URL)
    try:
        await _seed(con)
    finally:
        await con.close()
    pool = await asyncpg.create_pool(URL, min_size=1, max_size=1)
    running = {"route_model": "route-x", "godark_model": "godark-x"}
    app = FastAPI()
    app.include_router(M.make_router(lambda: pool, lambda: running, lambda: None, clock=lambda: NOW))
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as http:
            m = (await http.get("/lab/metrics", params={"hours": 24})).json()
            d = (await http.get("/lab/data", params={"hours": 24})).json()
            s = (await http.get("/lab/summary")).json()
            early = (await http.get("/lab/data", params={"hours": 19})).json()   # starts at T + 1 h
            bad = await http.get("/lab/metrics", params={"bucket": 10})
    finally:
        await pool.close()

    assert bad.status_code == 422
    assert m["bucket"] == H
    live = next(x for x in m["route"] if x["model_version"] == "route-x")
    assert live == {"t": T, "mode": "live", "model_version": "route-x", "horizon_s": 10800, "n": 4, "cov80": 0.75,
                    "cov95": 1.0, "median_err_m": 250.0, "baseline_median_err_m": 500.0, "skill": 0.5}
    bt = next(x for x in m["route"] if x["mode"] == "backtest")
    assert (bt["t"], bt["horizon_s"], bt["skill"]) == (T + H, 3600, 0.0)
    assert len(m["route"]) == 2   # the reappearance grade is not a horizon row
    (g,) = m["godark"]
    assert (g["t"], g["target"], g["n"], g["positives"], g["mode"]) == (T + H, "dark_1h", 10, 1, "live")
    assert g["hit_rate"] == pytest.approx(0.1) and g["mean_p"] == pytest.approx(0.117)
    assert g["brier"] == pytest.approx((0.1 ** 2 + 9 * 0.03 ** 2) / 10)
    assert g["brier_skill"] == pytest.approx(1 - g["brier"] / 0.09)
    (rel,) = m["reliability"]
    assert rel["model_version"] == "godark-x" and [b["n"] for b in rel["bins"]] == [9, 1]
    assert rel["bins"][1] == {"p_mean": 0.9, "hit_rate": 1.0, "n": 1}
    (lf,) = m["lift"]
    assert lf["top_hit_rate"] == 1.0 and lf["all_hit_rate"] == pytest.approx(0.1)

    # one row per bucket and mode, each mode with its own running total: live 4 route + 1 reappear at T, 10 dark at T+1h
    assert [(x["t"], x["mode"], x["n"], x["cumulative"]) for x in d["outcomes"]] == [
        (T, "live", 5, 5), (T, "unknown", 1, 1), (T + H, "backtest", 1, 1), (T + H, "live", 10, 15)]
    # a window from T + 1 h counts what came before it per mode
    assert [(x["mode"], x["cumulative"]) for x in early["outcomes"]] == [("backtest", 1), ("live", 15)]
    (src,) = d["sources"]   # positions is empty here, and the failed window does not count
    assert src == {"src": "gfw", "stream": "gaps", "label": "GFW AIS gap events", "oldest": T - 48 * H,
                   "newest": T - 24 * H, "windows": 1, "rows": 7}
    assert [x["run_id"] for x in d["training"]] == ["route-y", "route-x"] and d["training"][0]["n_train"] == 5000
    assert d["holdouts"] == [{"target": "route", "name": "v1", "n": 1000, "start": 1, "end": 2, "hash": "h1"}]

    route, godark, fishing = s["models"]
    assert route["champion"] == {"run_id": "route-x", "version": "route-x", "since": T - H + 1,
                                 "proposer": "human", "source": None}
    assert route["offline"]["skill"] == 0.6 and route["offline"]["holdout"] == "v1, 1,000 cases"
    assert route["live"]["n"] == 4 and route["live"]["primary"]["value"] == pytest.approx(0.5)
    assert route["live"]["calibration"]["value"] == 0.75 and route["live"]["calibration"]["ok"] is True
    assert route["deployed"] and route["note"] == "live skill below offline"
    assert godark["live"]["target"] == "dark_1h"   # no 6 h grades yet: the 1 h card
    assert godark["live"]["n"] == 10 and godark["champion"]["run_id"] is None
    assert fishing["deployed"] is False and fishing["live"] is None
    # plain-words cards: median 250 m at 3 h, 3 of 4 inside the circle; the 1 flagged ship of 10 went dark
    assert route["headline"] == {"text": "Finds a silent ship within 0.2 km after 3 hours", "value": 0.2, "unit": "km"}
    assert route["status"] == {"level": "ok", "text": "Circle held the ship 75% of the time · target 80%"}
    assert godark["headline"] == {"text": "Flagged ships go dark 10× more often", "value": 10, "unit": "×"}
    assert godark["status"] == {"level": "ok", "text": "Says 12%, actual 10%"}
    assert (M._pct(0.026), M._pct(0.117), M._pct(0.0)) == ("2.6%", "12%", "0%")
    assert fishing["headline"]["value"] is None and fishing["status"]["level"] == "none"
    assert (route["runs_total"], route["runs_gemini"], godark["runs_total"]) == (2, 1, 0)
    rp = route["pipeline"]
    assert {k: v["count"] for k, v in rp.items()} == {"new_data": 5000, "proposed": 0, "trained": 2, "judged": 0,
                                                      "promoted": 1, "rejected": 1, "graded": 7}
    assert rp["trained"]["last_ts"] == T - H / 2 and rp["graded"]["last_ts"] == T + 4 * H
    assert godark["pipeline"]["graded"]["count"] == 10
    for x in (route, godark, fishing):
        assert "dead reckoning" not in json.dumps(x).lower()
    assert s["totals"] == {"runs": 2, "proposals": 0, "graded_outcomes": 17, "graded_outcomes_estimated": False,
                           "graded_last_hour": 0}
    assert d["counted_from"] == T - 4 * H - 30 * 24 * H and d["truncated"] is False and m["truncated"] is False
    assert s["cycle"] == {"state": "manual", "last": T - H / 2, "next": None}

    # lab-store's columns and tables (dvm/lab/schema.py) arrive: source, since and the cycle come from them.
    con = await asyncpg.connect(URL)
    try:
        await con.execute("ALTER TABLE model_runs ADD COLUMN IF NOT EXISTS source text")
        await con.execute(LAB_DDL)
        await con.execute("INSERT INTO model_runs (run_id, target, model, status, created_at, recorded_at, source) "
                          "VALUES ('route-x', 'route', 'dma', 'deployed-note', $1, $1, 'desktop-hamish')", T - H)
        await con.executemany("INSERT INTO ml_events VALUES ($1, $2, $3, $4, $5, $6, NULL, '{}', 0)", [
            ("e1", T - H + 5, "route", "promoted", "route-x", "route-x"),
            ("e2", T + 2 * H, "route", "recalibrated", "route-x", "route-x-cal1"),
            ("e5", T + H, "route", "deployed", "route-x", "route-x"),
            ("e3", T + 3 * H, "route", "trained", "route-z", "route-z"),
            ("e4", T + 4 * H, "godark", "deployed", None, "godark-x")])
        await con.execute("INSERT INTO ml_proposals (id) VALUES ('p1'), ('p2')")
    finally:
        await con.close()
    running["route_model"] = "route-x-cal1"     # cal1 installed, no grades of its own yet
    pool = await asyncpg.create_pool(URL, min_size=1, max_size=1)
    try:
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as http:
            s = (await http.get("/lab/summary")).json()
    finally:
        await pool.close()
    route, godark, _ = s["models"]
    # since: route-x's deploy, not the cal1 build (a recalibrated event) nor the promotion
    assert route["champion"]["source"] == "desktop-hamish" and route["champion"]["since"] == T + H
    assert route["champion"]["version"] == "route-x-cal1" and route["live"] is None
    assert route["note"] == "no live grades for this version yet (the last 24 h graded route-x)"
    assert godark["champion"]["since"] == T + 4 * H
    assert s["cycle"]["last"] == T + 3 * H and s["totals"]["proposals"] == 2
    assert route["pipeline"]["promoted"]["last_ts"] == T - H + 5   # from the promoted event
    assert route["status"]["level"] == "none" and "yet" in route["headline"]["text"]


LAB_DDL = """
CREATE TABLE IF NOT EXISTS ml_events (id text PRIMARY KEY, ts bigint NOT NULL, target text NOT NULL, kind text NOT NULL,
  run_id text, version text, label text, detail jsonb NOT NULL DEFAULT '{}', recorded_at bigint NOT NULL);
CREATE TABLE IF NOT EXISTS ml_proposals (id text PRIMARY KEY);
"""


@needs_db
def test_routes_on_local_db():
    asyncio.run(_db_flow())


def test_truncation_keeps_the_newest_buckets():
    for sql in (M.ROUTE, M.GODARK, M.OUTCOME_COUNT):
        assert f"ORDER BY 1 DESC" in sql and f"LIMIT {M.MAX_ROWS}" in sql
    rows = [{"t": 2, "model_version": "a", "horizon_s": 1, "mode": "live"},
            {"t": 1, "model_version": "a", "horizon_s": 1, "mode": "live"}]
    assert [x["t"] for x in M._oldest_first(rows, "horizon_s")] == [1, 2]
    assert "o.made_at < $3" in M.OUTCOMES_BEFORE   # bounded on both sides
