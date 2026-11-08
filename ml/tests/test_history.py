"""The Model Lab history bundle: conversion of pre-registry artifacts, registry runs, events and ml.auto appends."""
import json

from ml.core import history as H
from ml.core.registry import FileRegistry

H6 = {"n": 100, "median_m": 900.0, "base_median_m": 1000.0, "skill": 0.1, "skill_lo": 0.05, "skill_hi": 0.15,
      "cover80": 0.81, "cover95": 0.90}


def _write(p, doc):
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(doc))


def _route_model(version, skill):
    h = dict(H6, skill=skill)
    return {"target": "route", "model": "lgbm", "version": version, "data_hash": "abc",
            "created_at": "2026-11-08T05:34:34+00:00", "config": {"model": "lgbm", "seed": 0},
            "fit_meta": {"n_fit": {"3600": 500, "86400": 200}, "train_from": 1, "train_to": 2},
            "metrics": {"holdout": {"target": "route", "name": "v1", "start": 1, "end": 2, "hash": "h", "n": 100,
                                    "extra": "dropped"},
                        "by_horizon": {"3600": h, "10800": h}}}


def _registry_run(run_id, status, target="fishing", loop_id=None, proposer="human", created="2026-11-08T07:19:22+00:00"):
    return {"run_id": run_id, "target": target, "model": "lgbm", "config": {"seed": 7}, "data_hash": "d",
            "train_from": 1, "train_to": 2, "artifact": None, "proposer": proposer, "parent_run": None,
            "status": status, "created_at": created, "loop_id": loop_id, "round": 1 if loop_id else None,
            "git_sha": "x", "metrics": {"state": "done", "skill": {"604800": {"n": 10, "skill": 0.2}},
                                        "decision": {"promote": status == "champion", "against": "baseline",
                                                     "reasons": [] if status == "champion" else ["no win at 7 d"]}}}


def test_ms_accepts_iso_seconds_and_ms():
    assert H.ms("2026-11-08T07:19:22+00:00") == 1794122362000
    assert H.ms(1794122362) == 1794122362000
    assert H.ms(1794122362000) == 1794122362000
    assert H.ms(None) is None


def test_route_conversion_fills_skill_calibration_and_decision():
    leg = {"promote": True, "against": "parent", "reasons": ["why"]}
    parent = H.route_metrics(_route_model("p", 0.30), leg, None)
    m = H.route_metrics(_route_model("c", 0.35), leg, parent)
    assert m["statistic"] == "median" and m["loss_unit"] == "m"
    assert m["holdout"] == {"target": "route", "name": "v1", "start": 1, "end": 2, "hash": "h", "n": 100}
    assert m["split"]["n_train"] == 500 and m["split"]["n_test"] == 100
    assert m["skill"]["3600"] == {"n": 100, "stat": 900.0, "baseline_stat": 1000.0, "skill": 0.35,
                                  "skill_lo": 0.05, "skill_hi": 0.15, "win_rate": None}
    cal = {(c["horizon_s"], c["nominal"]): c for c in m["calibration"]}
    assert cal[(3600, 0.8)]["ok"] is True          # 0.81 within 0.05 of 0.80
    assert cal[(3600, 0.95)]["ok"] is True         # 0.90 within 0.05 of 0.95 (boundary)
    assert m["decision"]["horizons"] == {}                 # no paired test: a person decided
    d = m["decision"]["comparison"]["3600"]
    assert d["cand"] == 0.35 and d["ref"] == 0.30 and abs(d["diff"] - 0.05) < 1e-12 and d["lo"] is None
    assert m["decision"]["reasons"] == ["why"] and m["decision"]["by"] == "human"
    assert m["strata"] is None and m["cv"] is None


def test_godark_conversion_uses_log_loss_skill_over_base_rate():
    model = {"target": "godark", "model": "lgbm", "version": "g", "targets": {"21600": "dark_6h"},
             "fit_info": {"21600": {"n_fit": 900}, "86400": {"skipped": "x", "n": 0}},
             "metrics": {"21600": {"n": 50, "positives": 5, "log_loss": 0.30, "brier": 0.08, "auc_pr": 0.1,
                                   "ece": 0.02, "vs_baseline": {"skill_brier": 0.01, "skill_brier_ci": [-0.02, 0.04],
                                                                "logloss_gain": 0.03, "logloss_gain_ci": [-0.01, 0.06]}}}}
    m = H.godark_metrics(model, {"promote": True, "against": "base rate", "reasons": []})
    s = m["skill"]["21600"]
    assert abs(s["baseline_stat"] - 0.33) < 1e-12
    assert abs(s["skill"] - 0.03 / 0.33) < 1e-12 and abs(s["skill_lo"] + 0.01 / 0.33) < 1e-12
    assert m["summary"]["21600"]["target_name"] == "dark_6h" and m["summary"]["21600"]["brier_skill"] == 0.01
    assert m["calibration"] == [{"name": "ece", "horizon_s": 21600, "value": 0.02, "nominal": 0.0, "tol": 0.05,
                                 "ok": True}]
    assert m["split"]["n_train"] == 900


def test_registry_run_keeps_record_and_maps_target(tmp_path):
    row = _registry_run("godark_gfw-1", "rejected", target="godark_gfw")
    row["artifact"] = str(tmp_path / "models" / "godark_gfw" / "godark_gfw-1")
    r = H.registry_run(row, tmp_path, "pc-aiden")
    assert r["target"] == "godark" and r["registry_target"] == "godark_gfw"
    assert r["created_at"] == 1794122362000 and r["source"] == "pc-aiden"
    assert r["artifact"] == "models/godark_gfw/godark_gfw-1"
    assert r["metrics"] == row["metrics"] and r["config"] == row["config"]


def test_events_for_champion_and_rejected_runs():
    champ = H.registry_run(_registry_run("f-1", "champion"), H.DATA, "pc-aiden")
    rej = H.registry_run(_registry_run("f-2", "rejected"), H.DATA, "pc-aiden")
    cand = H.registry_run(_registry_run("f-3", "candidate"), H.DATA, "pc-aiden")
    assert [e["kind"] for e in H.run_events(champ)] == ["trained", "promoted"]
    ev = H.run_events(rej)
    assert [e["kind"] for e in ev] == ["trained", "rejected"] and "no win at 7 d" in ev[1]["label"]
    assert ev[0]["detail"]["horizon_s"] == 604800 and ev[0]["detail"]["skill"] == 0.2
    assert [e["kind"] for e in H.run_events(cand)] == ["trained"]


def test_proposal_outcomes():
    runs = {"r1": {"status": "retired"}, "r2": {"status": "rejected"}}
    base = {"target": "fishing", "loop_id": "L", "round": 1, "proposer": "gemini", "proposal": {"seed": 1},
            "created_at": "2026-11-08T07:00:00+00:00"}
    out = lambda **kw: H.proposal_record(base | kw, runs, "server")["outcome"]  # noqa: E731
    assert out(valid=True, run_id="r1") == "champion"
    assert out(valid=True, run_id="r2") == "rejected"
    assert out(valid=False, errors=["duplicate of run r2: already evaluated"]) == "duplicate"
    assert out(valid=False, errors=["num_leaves: 9999 is greater than the maximum"]) == "invalid"
    a = H.proposal_record(base | {"valid": True, "id": 1}, runs, "server")
    b = H.proposal_record(base | {"valid": True, "id": 1}, runs, "server")
    c = H.proposal_record(base | {"valid": True, "id": 2}, runs, "server")
    assert a["id"] == b["id"] != c["id"] and a["created_at"] == 1794121200000


def _fake_root(tmp_path):
    _write(tmp_path / "route/artifacts/route-dma14-v3/model.json", _route_model("route-dma14-v3", 0.33))
    _write(tmp_path / "registry/fishing/runs/f-1.json", _registry_run("f-1", "champion"))
    _write(tmp_path / "registry/fishing/proposals/000001.json",
           {"id": 1, "target": "fishing", "loop_id": "L", "round": 1, "proposer": "gemini", "proposal": {"seed": 8},
            "valid": False, "errors": ["bad"], "created_at": "2026-11-08T08:00:00+00:00", "rationale": "try it"})
    m = _route_model("route-dma90-v2-cal1", 0.36)
    m["recalibration"] = {"method": "radius x quantile", "factors": {"3600": {"k80": 1.6}}, "parent": "route-dma90-v2"}
    _write(tmp_path / "recal/route-dma90-v2-cal1/model.json", m)
    return tmp_path


def test_collect_and_export_rerun_identically(tmp_path):
    root = _fake_root(tmp_path / "data")
    b = H.collect(root)
    assert [r["run_id"] for r in b["runs"]] == ["f-1", "route-dma14-v3"]          # newest first
    leg = b["runs"][1]
    assert leg["source"] == "pc-aiden" and leg["status"] == "retired" and leg["version"] == "dma14-v2"
    assert leg["config"]["data"].startswith("dma:14") and leg["parent_run"] == "route-dma14-v1"
    assert b["proposals"][0]["outcome"] == "invalid" and b["proposals"][0]["target"] == "fishing"
    kinds = [(e["kind"], e["run_id"]) for e in b["events"]]
    assert ("recalibrated", "route-dma90-v2") in kinds and ("proposal", None) in kinds
    # deploys only for runs in the bundle: route-dma14-v3 is, route-dma90-v2 is not
    assert ("deployed", "route-dma14-v3") in kinds and ("deployed", "route-dma90-v2") not in kinds
    assert [e["ts"] for e in b["events"]] == sorted(e["ts"] for e in b["events"])
    out = tmp_path / "bundle"
    H.write_bundle(b, out)
    first = {n: (out / f"{n}.jsonl").read_bytes() for n in H.FILES}
    H.write_bundle(H.collect(root), out)
    assert first == {n: (out / f"{n}.jsonl").read_bytes() for n in H.FILES}
    assert H.read_bundle(out)["runs"][0]["run_id"] == "f-1"


def test_append_cycle_adds_loop_runs_proposals_and_events(tmp_path):
    reg = FileRegistry(tmp_path / "reg")
    reg.create_run(_registry_run("f-old", "retired", created="2026-11-08T06:00:00+00:00"))
    reg.create_run(_registry_run("f-new", "champion", loop_id="L1", proposer="gemini"))
    reg.create_run(_registry_run("f-other", "rejected", loop_id="L0"))
    reg.log_proposal({"target": "fishing", "loop_id": "L1", "round": 1, "proposer": "gemini",
                      "proposal": {"seed": 9}, "valid": True, "run_id": "f-new", "rationale": "deeper trees"})
    status = {"started": "2026-11-08T10:00:00+00:00", "finished": "2026-11-08T10:05:00+00:00",
              "recalibrate": {"rows": {"route": 10}, "changed": {"route": "route-dma90-v2-cal2"}},
              "targets": {"fishing": {"loop_id": "L1", "champion_before": "f-old", "champion_after": "f-new"},
                          "route": {"error": "boom"}}}
    out = tmp_path / "lab-history"
    n = H.append_cycle(status, reg, tmp_path, out)
    b = H.read_bundle(out)
    assert {r["run_id"] for r in b["runs"]} == {"f-new", "f-old"} and n["runs"] == 2
    assert all(r["source"] == "server" for r in b["runs"])
    assert b["proposals"][0]["outcome"] == "champion" and b["proposals"][0]["rationale"] == "deeper trees"
    kinds = sorted(e["kind"] for e in b["events"])
    assert kinds == ["promoted", "proposal", "recalibrated", "trained"]
    rc = next(e for e in b["events"] if e["kind"] == "recalibrated")
    assert rc["run_id"] == "route-dma90-v2" and rc["version"] == "route-dma90-v2-cal2"
    H.append_cycle(status, reg, tmp_path, out)              # appends; the importer dedupes
    assert len(H.read_bundle(out)["runs"]) == 4


def test_deploy_events_map_versions_to_runs_and_skip_baselines():
    vr = {"dma14-v2": "route-dma14-v3", "route-dma90-v2-cal1": "route-dma90-v2"}
    ev = H.deploy_events([{"ts": 2, "target": "route", "version": "route-dma90-v2-cal1"},
                          {"ts": 1, "target": "route", "version": "dma14-v2"},
                          {"ts": 0, "target": "route", "version": "baseline-dr-v1"}], vr, "test")
    assert [(e["run_id"], e["version"]) for e in ev] == [("route-dma14-v3", "dma14-v2"),
                                                         ("route-dma90-v2", "route-dma90-v2-cal1")]
    assert all(e["kind"] == "deployed" for e in ev)


def test_recalibration_not_live_is_marked(tmp_path):
    root = _fake_root(tmp_path / "data")
    m = _route_model("route-dma90-v2", 0.36)
    _write(root / "route/artifacts/dl-dma90-v2/route-dma90-v2/model.json", m)
    b = H.collect(root)
    rc = next(e for e in b["events"] if e["kind"] == "recalibrated")
    assert rc["run_id"] == "route-dma90-v2" and rc["detail"]["deployed"] is False
    assert "not live" in rc["detail"]["status"]
    live = {e["version"] for e in b["events"] if e["kind"] == "deployed"}
    assert live == {"dma14-v2", "route-dma90-v2"}
