import json

from ml import auto


def _cycle(tmp_path, monkeypatch, env):
    seen = {}

    def fake(models_dir, url, apply=False, log=print, **kw):
        seen["apply"] = apply
        return {"rows": {"route": 700}, "changed": {"route": "route-x-cal1"}}
    import ml.core.recalibrate as R
    monkeypatch.setattr(R, "recalibrate", fake)
    monkeypatch.setenv("TIGER_DATABASE_URL", "postgresql://unused")
    monkeypatch.delenv("ML_DEPLOY_RECAL", raising=False)
    for k, v in env.items():
        monkeypatch.setenv(k, v)
    (tmp_path / "champions.json").write_text(json.dumps({"route": "route-x"}))
    st = auto.cycle([], 1, 1, retrain=False, do_deploy=True, models_dir=tmp_path, log=lambda m: None)
    return seen["apply"], st["recalibrate"]


def test_recalibration_is_recorded_not_installed_by_default(tmp_path, monkeypatch):
    applied, rc = _cycle(tmp_path, monkeypatch, {})
    assert applied is False and rc["applied"] is False and "not installed" in rc["note"]


def test_recalibration_installs_only_with_ml_deploy_recal(tmp_path, monkeypatch):
    applied, rc = _cycle(tmp_path, monkeypatch, {"ML_DEPLOY_RECAL": "1"})
    assert applied is True and rc["applied"] is True and "note" not in rc


def test_lab_import_is_off_by_default(tmp_path, monkeypatch):
    for k in ("ML_LAB_IMPORT_URL", "ML_LAB_IMPORT"):
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setenv("TIGER_DATABASE_URL", "postgresql://tiger")   # Tiger alone is not an opt-in
    assert auto.lab_import_url() is None
    assert "skipped" in auto.lab_import(tmp_path, log=lambda m: None)


def test_lab_import_url_needs_an_explicit_opt_in(monkeypatch):
    monkeypatch.delenv("ML_LAB_IMPORT_URL", raising=False)
    monkeypatch.setenv("TIGER_DATABASE_URL", "postgresql://tiger")
    monkeypatch.setenv("ML_LAB_IMPORT", "1")
    assert auto.lab_import_url() == "postgresql://tiger"
    monkeypatch.setenv("ML_LAB_IMPORT_URL", "postgresql://local")
    assert auto.lab_import_url() == "postgresql://local"


def test_lab_import_runs_the_importer_without_the_url_on_the_command_line(tmp_path, monkeypatch):
    seen = {}

    class P:
        returncode, stdout, stderr = 0, 'INFO x\n{"runs": 2}', ""

    def fake(cmd, cwd, env, **kw):
        seen.update(cmd=cmd, cwd=cwd, url=env["SOURCES_DATABASE_URL"])
        return P()
    monkeypatch.setattr(auto.subprocess, "run", fake)
    monkeypatch.setenv("ML_LAB_IMPORT_URL", "postgresql://secret@local/db")
    out = auto.lab_import(tmp_path, log=lambda m: None)
    assert out["rc"] == 0 and out["counts"] == {"runs": 2}
    assert seen["url"] == "postgresql://secret@local/db" and not any("secret" in c for c in seen["cmd"])
    assert seen["cmd"][1:4] == ["-m", "dvm.lab.importer", "--bundle"] and str(seen["cwd"]).endswith("backend")


def test_lab_import_into_a_real_database(tmp_path, monkeypatch):
    """End to end against a local TimescaleDB (ML_LAB_TEST_DATABASE_URL, a scratch database with the backend's
    store schema, as on the server), with the backend's importer."""
    import os
    import pytest
    url = os.getenv("ML_LAB_TEST_DATABASE_URL")
    if not url:
        pytest.skip("set ML_LAB_TEST_DATABASE_URL to a local scratch database")
    run = {"run_id": "t-auto-1", "target": "godark", "model": "lgbm", "status": "candidate",
           "created_at": 1762588800000, "source": "test"}
    (tmp_path / "runs.jsonl").write_text(json.dumps(run) + "\n")
    monkeypatch.setenv("ML_LAB_IMPORT_URL", url)
    out = auto.lab_import(tmp_path, log=lambda m: None)
    assert out["rc"] == 0, out
    again = auto.lab_import(tmp_path, log=lambda m: None)   # idempotent
    assert again["rc"] == 0, again


def test_every_refresh_writes_under_poseidon_data(tmp_path):
    """On the server POSEIDON_DATA=/opt/dvm/ml-data: no refresh may fall back to the laptop's data folder."""
    import os
    import subprocess
    import sys
    code = ("from ml.fishing import fetch, dataset as f; from ml.godark_gfw import tiger as g; "
            "from ml.godark import tiger as t, replay as r; from ml.route import tiger as rt; "
            "import ml.godark.dataset as d; print(fetch.DEFAULT_OUT, f.DEFAULT_OUT, g.DEFAULT_OUT, t.DEFAULT_OUT, r.OUT, d.OUT)")
    env = {k: v for k, v in os.environ.items() if k not in ("FISHING_DATA", "GODARK_GFW_DATA")}
    out = subprocess.run([sys.executable, "-c", code], env=env | {"POSEIDON_DATA": str(tmp_path)},
                         capture_output=True, text=True, check=True, cwd=auto.ROOT).stdout.split()
    assert len(out) == 6 and all(p.startswith(str(tmp_path)) for p in out), out
