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
