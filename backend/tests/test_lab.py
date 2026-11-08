"""Model Lab store (dvm/lab): record shaping, the bundle importer and the /lab routes.

The database part needs a local TimescaleDB; it creates and drops its own database `lab_store_test` there:
  SOURCES_TEST_DATABASE_URL=postgresql://postgres:local@127.0.0.1:55545/postgres pytest tests/test_lab.py
"""
from __future__ import annotations

import asyncio
import json
import os
from pathlib import Path

import asyncpg
import httpx
import pytest
from fastapi import FastAPI

from dvm import store as store_sql
from dvm.lab import importer, records as R, schema as lab_schema
from dvm.lab.routes import make_router
from dvm.predict import schema as predict_schema

URL = os.getenv("SOURCES_TEST_DATABASE_URL", "")
needs_db = pytest.mark.skipif(not URL or "tsdb.cloud" in URL or "timescale.com" in URL,
                              reason="set SOURCES_TEST_DATABASE_URL to a local TimescaleDB")
BUNDLE = Path(__file__).parent / "fixtures" / "lab-bundle"
CHAMP, REJ = "fishing-20261108T071922-e2db5c", "fishing-20261108T071925-be7ea1"
GEM, CONF = "fishing-20261108T090000-aaaaaa", "fishing-20261108T090500-bbbbbb"


# ---------------------------------------------------------------- pure shaping

def test_to_ms_and_horizon_label():
    assert R.to_ms("2026-11-08T07:19:22+00:00") == 1794122362000
    assert R.to_ms(1794122362000) == 1794122362000 and R.to_ms(1794122362) == 1794122362000
    assert R.to_ms(None) is None
    assert [R.horizon_label(h) for h in (3600, 10800, 1800, 604800, 2592000)] == ["1 h", "3 h", "30 min", "7 days",
                                                                                  "30 days"]


def test_config_diff():
    assert R.config_diff({"a": 1, "b": 2}, {"a": 1, "b": 3, "c": 0}) == [
        {"key": "b", "parent": 3, "value": 2}, {"key": "c", "parent": 0, "value": None}]
    assert R.config_diff({"a": 1}, None) == [{"key": "a", "parent": None, "value": 1}]


def test_runs_from_rows_newest_status_and_fill():
    rows = [{"run_id": "x", "target": "t", "model": "m", "config": '{"a": 1}', "metrics": "{}", "status": "candidate",
             "created_at": 5, "recorded_at": 5, "source": "pc-aiden", "loop_id": "L"},
            {"run_id": "x", "target": "t", "model": "m", "config": {"a": 1}, "metrics": {"k": 1}, "status": "champion",
             "created_at": 5, "recorded_at": 9},
            {"run_id": "y", "target": "t", "model": "m", "config": {}, "metrics": {}, "status": "champion",
             "created_at": 7, "recorded_at": 7},
            {"run_id": "y", "target": "t", "model": "m", "config": {}, "metrics": {}, "status": "rejected",
             "created_at": 7, "recorded_at": 7}]
    out = R.runs_from_rows(rows)
    assert [r["run_id"] for r in out] == ["y", "x"]                         # newest created first
    assert out[0]["status"] == "champion"                                   # tie: champion first, as the leaderboard
    x = out[1]
    assert x["status"] == "champion" and x["source"] == "pc-aiden" and x["loop_id"] == "L"
    assert x["config"] == {"a": 1} and x["metrics"] == {"k": 1} and "recorded_at" not in x


def _bundle_runs() -> list[dict]:
    rows = [{**d, "created_at": R.to_ms(d["created_at"]), "recorded_at": i}
            for i, d in enumerate(importer.read_jsonl(BUNDLE / "runs.jsonl"))]
    return R.runs_from_rows(rows)


def test_rule_checklist_from_decision():
    rej = next(r for r in _bundle_runs() if r["run_id"] == REJ)
    checks = R.rule(rej, None)
    assert checks[0]["check"] == f"beats the champion {CHAMP} at 7 days" and checks[0]["passed"] is False
    assert checks[0]["detail"].startswith("diff +0.07261 [")
    assert checks[1]["check"].startswith("calibration ece within 0.05 of 0") and checks[1]["passed"] is True
    assert checks[2]["check"] == "no group of 30+ cases more than 10% worse" and checks[2]["passed"] is False
    assert "and 4 more" in checks[2]["detail"]
    assert R.rule({"metrics": {}}, None) == []                              # pre-registry runs: no decision


def test_rule_horizon_without_interval():
    """Pre-registry runs converted by lab-history: a diff with null lo/hi, and win missing on one horizon."""
    rec = {"metrics": {"decision": {"against": "baseline", "horizons": {
        "3600": {"diff": -0.12, "lo": None, "hi": None, "win": True},
        "10800": {"diff": 0.05, "lo": None, "hi": None}}}}}
    checks = R.rule(rec, None)
    assert checks == [{"check": "beats the baseline at 1 h", "passed": True, "detail": "diff -0.12"},
                      {"check": "beats the baseline at 3 h", "passed": None, "detail": "diff +0.05"}]


def test_run_detail_confirm_rationale_parent():
    runs = _bundle_runs()
    props = [R.proposal_record({**p, "created_at": R.to_ms(p["created_at"])}, None)
             for p in importer.read_jsonl(BUNDLE / "proposals.jsonl")]
    g = next(r for r in runs if r["run_id"] == GEM)
    d = R.run_detail(g, runs, props)
    assert d["parent"]["run_id"] == CHAMP and d["parent"]["status"] == "retired"
    assert d["config_diff"] == [{"key": "num_leaves", "parent": 15, "value": 31}]
    assert d["rationale"] == "more leaves for the trawler cases"
    assert d["confirm"] == {"run_id": CONF, "passed": True}
    assert d["rule"][0]["check"] == f"beats the champion {CHAMP} at 7 days" and d["rule"][0]["passed"]
    assert d["rule"][-1] == {"check": "wins again with a second seed", "passed": True, "detail": CONF}
    c = R.run_detail(next(r for r in runs if r["run_id"] == CONF), runs, props)
    assert c["confirm"] is None and c["rationale"].startswith("second-seed confirmation of")


def test_proposal_outcome():
    assert R.proposal_outcome({"errors": ["duplicate of run x"], "valid": False}, None) == "duplicate"
    assert R.proposal_outcome({"errors": ["bad"], "valid": False}, None) == "invalid"
    assert R.proposal_outcome({"valid": True, "outcome": "candidate"}, "retired") == "champion"
    assert R.proposal_outcome({"valid": True}, "rejected") == "rejected"
    assert R.proposal_outcome({"valid": True, "outcome": "candidate"}, None) == "candidate"


def test_run_rows_never_roll_status_back():
    base = {"run_id": "x", "target": "t", "model": "m", "created_at": 100}
    have = {"x": [("champion", 500)]}
    rows = importer.run_rows([{**base, "status": "candidate"}, {**base, "status": "retired"},
                              {**base, "status": "champion"}], have, now=1000)
    at = {r[importer.COLS.index("status")]: r[importer.COLS.index("recorded_at")] for r in rows}
    assert set(at) == {"candidate", "retired"}                             # champion already there: skipped
    assert at["candidate"] < 500 < at["retired"]


def test_importer_refuses_tiger(monkeypatch):
    monkeypatch.setenv("TIGER_DATABASE_URL", "postgres://u:p@abc.tsdb.cloud.timescale.com:5432/tsdb")
    monkeypatch.delenv("SOURCES_DATABASE_URL", raising=False)
    with pytest.raises(SystemExit, match="Refusing"):
        importer.database_url(None, allow_tiger=False)
    assert importer.database_url(None, allow_tiger=True).endswith("/tsdb")


# ---------------------------------------------------------------- database: importer and routes

async def _fresh_db() -> str:
    admin = await asyncpg.connect(URL)
    try:
        await admin.execute("DROP DATABASE IF EXISTS lab_store_test WITH (FORCE)")
        await admin.execute("CREATE DATABASE lab_store_test")
    finally:
        await admin.close()
    return URL.rsplit("/", 1)[0] + "/lab_store_test"


async def _db_flow():
    url = await _fresh_db()
    con = await asyncpg.connect(url)
    pool = None
    try:
        await store_sql.setup(con)
        await predict_schema.setup(con)
        await lab_schema.setup(con)
        await lab_schema.setup(con)                                         # idempotent
        # a row the predictor mirrored before the import: no source, loop_id...
        await con.execute(predict_schema.RUN_INSERT, CHAMP, "fishing", "lgbm", "{}", None, None, None, "{}", None,
                          "human", None, "champion", 1794122362000, 1794122362000)
        first = await importer.import_bundle(con, BUNDLE, now=1794130000000)
        again = await importer.import_bundle(con, BUNDLE, now=1794130000001)
        assert first["runs"] == {"read": 5, "new_rows": 4} and first["events"]["new"] == 4
        assert again["runs"]["new_rows"] == 0 and again["events"]["new"] == 0
        assert await con.fetchval("SELECT count(*) FROM model_runs") == 5
        assert await con.fetchval("SELECT count(*) FROM ml_proposals") == 4
        assert await con.fetchval("SELECT count(*) FROM ml_events") == 4

        pool = await asyncpg.create_pool(url, min_size=1, max_size=2)
        app = FastAPI()
        app.include_router(make_router(lambda: pool, lambda: None, clock=lambda: 1794135600000))
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as http:
            runs = (await http.get("/lab/runs", params={"target": "fishing"})).json()
            none = (await http.get("/lab/runs", params={"target": "route"})).json()
            detail = (await http.get(f"/lab/runs/{GEM}")).json()
            champ = (await http.get(f"/lab/runs/{CHAMP}")).json()
            missing = await http.get("/lab/runs/nope")
            props = (await http.get("/lab/proposals", params={"target": "fishing"})).json()
            ev_all = (await http.get("/lab/events")).json()
            ev_3h = (await http.get("/lab/events", params={"hours": 3})).json()
            bad = await http.get("/lab/runs", params={"target": "x;drop"})
        assert [r["run_id"] for r in runs] == [CONF, GEM, REJ, CHAMP] and none == []
        by = {r["run_id"]: r for r in runs}
        assert by[CHAMP]["status"] == "retired" and by[CHAMP]["source"] == "pc-aiden"
        assert by[CHAMP]["created_at"] == 1794122362000 and by[GEM]["status"] == "champion"
        assert "strata" not in by[REJ]["metrics"] and "decision" in by[REJ]["metrics"]
        assert set(by[GEM]) == set(R.RUN_FIELDS)
        assert "strata" in detail["metrics"] and detail["confirm"] == {"run_id": CONF, "passed": True}
        assert detail["rationale"] == "more leaves for the trawler cases" and detail["parent"]["run_id"] == CHAMP
        assert champ["parent"] is None and champ["rule"][0]["check"] == "beats the baseline at 7 days"
        assert missing.status_code == 404 and bad.status_code == 422
        out = {p["proposal"].get("num_leaves"): p["outcome"] for p in props if p["proposal"]}
        assert out[31] == "champion" and out[9999] == "invalid" and out[15] == "duplicate"
        assert sum(p["outcome"] == "candidate" for p in props) == 1                     # the confirmation re-run
        assert all(isinstance(p["errors"], list) for p in props)
        assert [e["ts"] for e in ev_all] == sorted(e["ts"] for e in ev_all) and len(ev_all) == 4
        assert [e["kind"] for e in ev_3h] == ["promoted"] and ev_3h[0]["run_id"] == GEM

        # tables not there yet -> 503, not 500
        await con.execute("DROP TABLE ml_events")
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as http:
            assert (await http.get("/lab/events")).status_code == 503
    finally:
        if pool:
            await pool.close()
        await con.close()
        admin = await asyncpg.connect(URL)
        await admin.execute("DROP DATABASE IF EXISTS lab_store_test WITH (FORCE)")
        await admin.close()


@needs_db
def test_import_and_routes():
    asyncio.run(_db_flow())


def test_no_pool_is_503():
    app = FastAPI()
    app.include_router(make_router(lambda: None, lambda: None))

    async def go():
        async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://t") as http:
            return (await http.get("/lab/runs")).status_code
    assert asyncio.run(go()) == 503
