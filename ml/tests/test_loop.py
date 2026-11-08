"""The whole loop on the toy target: no real data, no Gemini, no database (file registry)."""
import json
import os

import pandas as pd
import pytest

from ml.core import loop as lp
from ml.core import report
from ml.core.registry import FileRegistry, Model, SqlRegistry, load_artifact, save_artifact
from ml.core.run import run_one
from ml.core.toy import ToyTarget


@pytest.fixture
def spec():
    return ToyTarget(n_ships=18, days=6)


def test_loop_end_to_end(spec, tmp_path):
    reg = FileRegistry(tmp_path / "reg")
    art = tmp_path / "art"
    out = lp.loop(spec, 2, reg=reg, k=3, dry_run=True, artifacts=art, n_folds=2, log=lambda *_: None)
    runs = reg.list_runs("toy")
    champ = reg.champion("toy")
    assert champ and out["champion"] == champ["run_id"]
    assert sum(r["status"] == "champion" for r in runs) == 1
    assert champ["model"] != spec.baseline
    assert all(r["metrics"]["state"] == "done" for r in runs)
    # one holdout for every run, and every run scored on all of it
    assert len({r["metrics"]["holdout"]["hash"] for r in runs}) == 1
    # every proposal logged, invalid ones included
    props = reg.list_proposals("toy")
    assert any(not p["valid"] for p in props) and any(p["valid"] for p in props)
    assert all(p["run_id"] for p in props if p["valid"])
    # the champion pointer and artifact load and reproduce the predictions
    ptr = json.loads((art / "toy" / "champion.json").read_text())
    assert ptr["run_id"] == champ["run_id"]
    model, meta = load_artifact(ptr["artifact"], spec.models)
    assert meta["version"] == champ["run_id"] and meta["features"] and meta["horizons_s"] == spec.horizons_s
    assert not any(f.endswith((".pkl", ".joblib")) for f in meta["files"])
    ex = spec.load_examples(spec.default_config, None).head(50)
    a = model.predict(ex)
    b = spec.models[champ["model"]]().fit(ex, champ["config"]).predict(ex)   # shape check only
    assert list(a.columns) == list(b.columns) and len(a) == 50 * len(spec.horizons_s)
    # report
    html = open(out["report"]["html"]).read()
    rep = json.loads(open(out["report"]["json"]).read())
    assert champ["run_id"] in html and "Frozen held-out set" in html and "invalid" in html
    assert "fixed dry-run list" in html and all(p.get("source") for p in props)
    assert rep["champion"]["run_id"] == champ["run_id"] and rep["learning_curve"]


def test_loop_falls_back_on_429(spec, tmp_path, monkeypatch):
    from ml.core import propose

    def quota(*a, **k):
        raise propose.ProposerSkipped("Gemini returned 429")
    monkeypatch.setattr(propose, "gemini_proposals", quota)
    reg = FileRegistry(tmp_path / "reg")
    out = lp.loop(spec, 1, reg=reg, k=2, dry_run=False, artifacts=tmp_path / "art", n_folds=0, log=lambda *_: None)
    assert out["rounds"][-1]["proposer"] == "default" and "429" in out["rounds"][-1]["source"]
    r1 = [p for p in reg.list_proposals("toy") if p["round"] == 1]
    assert r1 and all(p["proposer"] == "default" and "fallback" in p["source"] for p in r1)
    assert "429" in open(out["report"]["html"]).read()


def test_promoted_champion_is_beaten_only_by_rule(spec, tmp_path):
    reg = FileRegistry(tmp_path / "reg")
    art = tmp_path / "art"
    kw = dict(reg=reg, artifacts=art, n_folds=0, log=lambda *_: None)
    first = run_one(spec, {"model": "linear", "features": ["f1", "f2", "f1_x_f2"], "l2": 1.0, "seed": 0}, **kw)
    assert first["status"] == "champion"
    same = run_one(spec, {"model": "linear", "features": ["f1", "f2", "f1_x_f2"], "l2": 1.0, "seed": 1}, **kw)
    assert same["status"] == "rejected"          # identical predictions: a tie keeps the champion
    worse = run_one(spec, {"model": "linear", "features": ["f3"], "l2": 1.0, "seed": 0}, **kw)
    assert worse["status"] == "rejected"
    assert reg.champion("toy")["run_id"] == first["run_id"]


def test_baseline_never_promotes_itself(spec, tmp_path):
    row = run_one(spec, {"model": "baseline", "seed": 0}, reg=FileRegistry(tmp_path / "r"), artifacts=tmp_path,
                  n_folds=0, log=lambda *_: None)
    assert row["status"] == "rejected"


def test_invalid_config_never_runs(spec, tmp_path):
    reg = FileRegistry(tmp_path / "r")
    with pytest.raises(ValueError, match="invalid config"):
        run_one(spec, {"model": "linear", "seed": 0, "l2": -1}, reg=reg, artifacts=tmp_path, log=lambda *_: None)
    assert reg.list_runs("toy") == []


def test_pickles_refused(tmp_path):
    class Bad(Model):
        name, target = "bad", "toy"

        def save(self, dir):
            (dir / "m.pkl").write_bytes(b"x")
            return {"features": [], "horizons_s": []}

    with pytest.raises(ValueError, match="pickles"):
        save_artifact(Bad(), tmp_path / "a", {})


def test_report_with_no_runs(spec, tmp_path):
    paths = report.write(spec, FileRegistry(tmp_path / "r"), tmp_path / "out")
    assert "No champion yet" in paths["html"].read_text()


def test_registry_refuses_tiger(monkeypatch):
    monkeypatch.setenv("TIGER_DATABASE_URL", "postgresql://u:p@abc.tsdb.example.com:5432/tsdb")
    with pytest.raises(SystemExit):
        SqlRegistry("postgresql://u:p@abc.tsdb.example.com:5432/other")
    with pytest.raises(SystemExit):
        SqlRegistry("postgresql://u:p@x.y.tsdb.cloud.timescale.com:5432/tsdb")


DB = os.getenv("ML_TEST_DATABASE_URL")


@pytest.mark.skipif(not DB, reason="ML_TEST_DATABASE_URL not set (a local TimescaleDB)")
def test_sql_registry_loop(spec, tmp_path):
    import asyncio

    import asyncpg

    async def reset():
        c = await asyncpg.connect(DB)
        await c.execute("DROP TABLE IF EXISTS model_runs, model_proposals")
        await c.close()
    asyncio.run(reset())
    reg = SqlRegistry(DB)
    out = lp.loop(spec, 1, reg=reg, k=2, dry_run=True, artifacts=tmp_path, n_folds=0, log=lambda *_: None)
    runs = reg.list_runs("toy")
    assert reg.champion("toy")["run_id"] == out["champion"]
    assert isinstance(runs[0]["config"], dict) and isinstance(runs[0]["metrics"], dict)
    assert reg.list_proposals("toy") and any(not p["valid"] for p in reg.list_proposals("toy"))
    assert all(p["source"] for p in reg.list_proposals("toy"))
    # one champion per target is enforced by the database, not just the code
    other = next(r for r in runs if r["status"] != "champion")
    with pytest.raises(asyncpg.UniqueViolationError):
        reg.update_run(other["run_id"], status="champion")
    reg.set_champion("toy", other["run_id"])   # the supported way flips it atomically
    assert reg.champion("toy")["run_id"] == other["run_id"]
    assert {r["status"] for r in reg.list_runs("toy") if r["run_id"] == out["champion"]} == {"retired"}
    pd.DataFrame(runs)   # rows are plain dicts
