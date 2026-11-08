"""The Model Lab history bundle: every model run we have, as run records, proposals and events.

    python -m ml.core.history export [--data $POSEIDON_DATA] [--out data/lab-history]

Writes `runs.jsonl`, `proposals.jsonl` and `events.jsonl` (one record per line, sorted, so a rerun on the same files
gives the same bytes). The server imports it with `python -m dvm.lab.importer --bundle data/lab-history --allow-tiger`.

Sources under the data root (default POSEIDON_DATA, else /home/aiden/data/poseidon):
- `registry/<target>/runs/*.json` and `registry/<target>/proposals/*.json`: the ML registry, copied unchanged
  except `created_at` in epoch ms, `artifact` relative to the data root, and `source`.
- Pre-registry artifacts (route dma14-v1, route-dma14-v2/v3, Hamish's route-dma90-v2, godark-lgbm-*): converted into
  the run record shape from their model.json metrics; fields they lack are null. Their status, parent and the reason
  they were kept or replaced are the facts in `LEGACY` below (they were decided by people, not by the rule).
- Recalibrations (`recal/*/model.json` `recalibration` blocks, `route/artifacts/*/recalibration.json`): events of
  kind `recalibrated`.
- Deploys: `DEPLOYS` below, the times the server's champions.json changed (from the team board and
  docs/prediction-loop/PLAN.md).

`append_cycle(...)` adds one ml.auto cycle's runs, proposals and events to a bundle in the same format.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

DATA = Path(os.environ.get("POSEIDON_DATA", "/home/aiden/data/poseidon"))
FILES = ("runs", "proposals", "events")
# Registry targets -> the Lab's three models. godark_gfw is the go-dark model on GFW's gap labels.
LAB_TARGET = {"route": "route", "godark": "godark", "godark_gfw": "godark", "fishing": "fishing"}
ROUTE_PRIMARY = ["3600", "10800", "21600", "86400"]
GODARK_PRIMARY = ["21600", "3600"]
PRIMARY = {"route": ROUTE_PRIMARY, "godark": GODARK_PRIMARY, "godark_gfw": ["2592000", "1209600"],
           "fishing": ["604800"]}   # the horizons each target's promotion rule tests, first = headline
TOL = 0.05


def ms(t: Any) -> int | None:
    """ISO string, datetime, epoch s or ms -> epoch ms."""
    if t is None:
        return None
    if isinstance(t, (int, float)):
        return int(t if t > 1e11 else t * 1000)
    if isinstance(t, datetime):
        dt = t
    else:
        dt = datetime.fromisoformat(str(t).replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def utc(hhmm: str, day: str = "2026-11-08") -> int:
    return ms(f"{day}T{hhmm}:00+00:00")


def rel(path: str | None, root: Path) -> str | None:
    if not path:
        return path
    try:
        return str(Path(path).resolve().relative_to(root.resolve()))
    except ValueError:
        return path


# ---------------------------------------------------------------- facts no file records

# Pre-registry runs: where the artifact is, who made it, and what happened to it.
LEGACY = [
    {"run_id": "route-dma14-v1", "path": "route/artifacts/dma14-v1", "kind": "route_v1", "source": "pc-aiden",
     "created_at": utc("05:15"), "status": "retired", "parent_run": None, "data": "dma:14 (Danish AIS, 23 Oct-2 Nov)",
     "promote": True, "against": "dead reckoning (no champion yet)",
     "reasons": ["first route model: beat dead reckoning at every horizon on 3-5 Nov",
                 "replaced by route-dma14-v3: saved as along/cross heads (route-f1), which the live loader rejects"]},
    {"run_id": "route-dma14-v2", "path": "route/artifacts/route-dma14-v2", "kind": "route", "source": "pc-aiden",
     "status": "candidate", "parent_run": "route-dma14-v1", "data": "dma:14 (Danish AIS)",
     "promote": False, "against": "route-dma14-v1",
     "reasons": ["retrained with east/north heads for the live loader, no frozen held-out set",
                 "never promoted: route-dma14-v3 retrained it 5 min later against the frozen held-out set"]},
    {"run_id": "route-dma14-v3", "path": "route/artifacts/route-dma14-v3", "kind": "route", "source": "pc-aiden",
     "status": "retired", "parent_run": "route-dma14-v1", "data": "dma:14 (Danish AIS)", "version": "dma14-v2",
     "promote": True, "against": "route-dma14-v1",
     "reasons": ["promoted by hand because it loads in the live predictor, not because it scored better: "
                 "skill 0.33 against 0.35 at 1 h, 0.59 against 0.58 at 3 h (different test windows)",
                 "deployed as the folder dma14-v2 (same model, saved again at 06:48)",
                 "replaced at 07:32 by route-dma90-v2 (90 days of training data)"]},
    {"run_id": "route-dma90-v2", "path": "route/artifacts/dl-dma90-v2/route-dma90-v2", "kind": "route",
     "source": "desktop-hamish", "status": "champion", "parent_run": "route-dma14-v3",
     "data": "dma:90 (Danish AIS, 90 days)", "promote": True, "against": "route-dma14-v3",
     "reasons": ["promoted by hand: higher skill than route-dma14-v3 at every horizon "
                 "(+0.03 at 1 h, +0.04 at 3 h, +0.01 at 24 h)",
                 "not a paired test: the two runs were scored on different held-out sets (14 and 90 days)",
                 "trained on Hamish's desktop (90 days, about 25 min)"]},
    {"run_id": "godark-lgbm-20261108T050756", "path": "models/godark-lgbm-20261108T050756", "kind": "godark",
     "source": "pc-aiden", "status": "candidate", "parent_run": None, "data": "tiger (our feed, 11 h)",
     "promote": False, "against": "global base rate",
     "reasons": ["first go-dark model on our own gap detector's labels",
                 "never deployed: godark-lgbm-20261108T051156 is the same model saved with its target names"]},
    {"run_id": "godark-lgbm-20261108T051156", "path": "models/godark-lgbm-20261108T051156", "kind": "godark",
     "source": "pc-aiden", "status": "champion", "parent_run": "godark-lgbm-20261108T050756",
     "data": "tiger (our feed, 11 h)", "promote": True, "against": "global base rate",
     "reasons": ["promoted by hand to give the live predictor a go-dark model",
                 "Brier skill over the base rate does not exclude zero (6 h: +0.012 [-0.018, +0.039]); "
                 "shown as a ranking, not a probability claim"]},
]

# When the server's champions.json changed (team board posts; times UTC on 8 Nov).
DEPLOYS = [
    {"ts": utc("07:01"), "target": "route", "run_id": "route-dma14-v3", "version": "dma14-v2",
     "label": "route dma14-v2 live (PREDICT=1)", "detail": {"by": "Hamish's laptop agent", "evidence": "board 07:01"}},
    {"ts": utc("07:01"), "target": "godark", "run_id": "godark-lgbm-20261108T051156",
     "version": "godark-lgbm-20261108T051156", "label": "go-dark godark-lgbm-20261108T051156 live (PREDICT=1)",
     "detail": {"by": "Hamish's laptop agent", "evidence": "board 07:01"}},
    {"ts": utc("07:32"), "target": "route", "run_id": "route-dma90-v2", "version": "route-dma90-v2",
     "label": "route route-dma90-v2 live", "detail": {"by": "Hamish's laptop agent", "evidence": "board 07:32"}},
    {"ts": utc("08:38"), "target": "route", "run_id": "route-dma90-v2", "version": "route-dma90-v2-cal1",
     "label": "route route-dma90-v2-cal1 live (wider circles)",
     "detail": {"by": "Hamish's laptop agent", "evidence": "released 08:20 (models-recal-v1), live by 08:38 (board)",
                "time": "approximate: installed between 08:20 and 08:38"}},
    {"ts": utc("08:38"), "target": "godark", "run_id": "godark-lgbm-20261108T051156",
     "version": "godark-lgbm-20261108T051156-cal1", "label": "go-dark godark-lgbm-20261108T051156-cal1 live",
     "detail": {"by": "Hamish's laptop agent", "evidence": "released 08:20 (models-recal-v1), live by 08:38 (board)",
                "time": "approximate: installed between 08:20 and 08:38"}},
]

# Recalibrations that were made but not put live, and why.
RECAL_KEPT = {"route-dma90-v2-cal1": True, "godark-lgbm-20261108T051156-cal1": True,
              "route-dma90-v2-cal202611080819": False}
RECAL_WHY = {"route-dma90-v2-cal202611080819":
             "not deployed: route-dma90-v2-cal1 (fitted on the 11 h backtest) was released instead; on its own "
             "check window this one's 80% circle held 77-85%"}


# ---------------------------------------------------------------- conversion

def _empty_metrics() -> dict:
    return {"state": "done", "holdout": None, "split": None, "statistic": None, "loss_name": None, "loss_unit": None,
            "summary": None, "skill": None, "calibration": None, "strata": None, "strata_baseline": None, "cv": None,
            "decision": None, "seconds": None}


def _decision(leg: dict, horizons: dict | None, calibration: list | None) -> dict:
    return {"promote": leg["promote"], "against": leg["against"], "alpha": None, "n_comparisons": None,
            "horizons": horizons, "calibration": calibration, "reasons": leg["reasons"], "by": "human"}


def route_metrics(m: dict, leg: dict, ref: dict | None) -> dict:
    """A pre-registry route model.json -> run metrics. `ref` is the parent's converted metrics (for the decision)."""
    met = m.get("metrics") or (m.get("meta") or {}).get("metrics") or {}
    by_h = met.get("by_horizon") or {}
    fit = m.get("fit_meta") or m.get("meta") or {}
    out = _empty_metrics() | {"statistic": "median", "loss_name": "error_m", "loss_unit": "m"}
    h = met.get("holdout")
    out["holdout"] = ({k: h.get(k) for k in ("target", "name", "start", "end", "hash", "n")} if h else None)
    n_fit = fit.get("n_fit") or {}
    out["split"] = {"n_train": max(n_fit.values()) if n_fit else None, "n_test": (h or {}).get("n"),
                    "embargo_s": None}
    out["summary"] = {k: dict(v) for k, v in by_h.items()}
    out["skill"] = {k: {"n": v.get("n"), "stat": v.get("median_m"), "baseline_stat": v.get("base_median_m"),
                        "skill": v.get("skill"), "skill_lo": v.get("skill_lo"), "skill_hi": v.get("skill_hi"),
                        "win_rate": None} for k, v in by_h.items()}
    cal = []
    for k in ROUTE_PRIMARY:
        v = by_h.get(k)
        if not v:
            continue
        for nom, col in ((0.8, "cover80"), (0.95, "cover95")):
            if v.get(col) is not None:
                cal.append({"name": f"{int(nom * 100)}% radius coverage", "horizon_s": int(k), "value": v[col],
                            "nominal": nom, "tol": TOL, "ok": abs(v[col] - nom) <= TOL})
    out["calibration"] = cal
    rs = (ref or {}).get("skill") or {}
    horizons = {k: _cmp(out["skill"].get(k), rs.get(k), bool(ref)) for k in ROUTE_PRIMARY if k in out["skill"]}
    out["decision"] = _decision(leg, horizons, cal)
    if met.get("reappear"):
        out["reappear"] = met["reappear"]
    return out


def _cmp(c: dict | None, r: dict | None, has_ref: bool) -> dict:
    """Skill of the candidate against the reference (the parent, else the baseline at skill 0). Pre-registry runs
    have no paired bootstrap of the difference, so lo/hi/win are null."""
    cs = (c or {}).get("skill")
    rf = (r or {}).get("skill") if has_ref else 0.0
    return {"cand": cs, "ref": rf, "diff": (cs - rf) if cs is not None and rf is not None else None,
            "lo": None, "hi": None, "win": None}


def godark_metrics(m: dict, leg: dict) -> dict:
    """A godark-lgbm model.json -> run metrics. Skill is log-loss skill over the global base rate (the loop's
    statistic); its interval is the bootstrap interval of the log-loss gain divided by the baseline's log loss."""
    out = _empty_metrics() | {"statistic": "mean", "loss_name": "log_loss", "loss_unit": ""}
    met = m.get("metrics") or {}
    fit = m.get("fit_info") or {}
    out["split"] = {"n_train": max((f.get("n_fit") or 0) for f in fit.values()) or None,
                    "n_test": max((v.get("n") or 0) for v in met.values()) or None, "embargo_s": None}
    names = m.get("targets") or {}
    out["summary"], out["skill"], cal = {}, {}, []
    for k, v in met.items():
        vb = v.get("vs_baseline") or {}
        base = v["log_loss"] + vb["logloss_gain"] if "logloss_gain" in vb else None
        ci = vb.get("logloss_gain_ci") or [None, None]
        div = (lambda x: x / base if x is not None and base else None)
        out["summary"][k] = {"target_name": names.get(k), **{c: v.get(c) for c in
                                                             ("n", "positives", "log_loss", "brier", "auc_pr", "ece")},
                             "brier_skill": vb.get("skill_brier"), "brier_skill_ci": vb.get("skill_brier_ci")}
        out["skill"][k] = {"n": v.get("n"), "stat": v.get("log_loss"), "baseline_stat": base,
                           "skill": div(vb.get("logloss_gain")), "skill_lo": div(ci[0]), "skill_hi": div(ci[1]),
                           "win_rate": None}
        if v.get("ece") is not None:
            cal.append({"name": "ece", "horizon_s": int(k), "value": v["ece"], "nominal": 0.0, "tol": TOL,
                        "ok": abs(v["ece"]) <= TOL})
    out["calibration"] = cal
    horizons = {k: _cmp(out["skill"].get(k), None, False) for k in GODARK_PRIMARY if k in out["skill"]}
    out["decision"] = _decision(leg, horizons, cal)
    return out


def legacy_run(leg: dict, root: Path, converted: dict[str, dict]) -> dict | None:
    p = root / leg["path"] / "model.json"
    if not p.exists():
        return None
    m = json.loads(p.read_text())
    fit = m.get("fit_meta") or m.get("meta") or {}
    target = "route" if leg["kind"].startswith("route") else "godark"
    cfg = dict(m.get("config") or m.get("cfg") or {})
    cfg["data"] = leg["data"]
    if target == "route":
        parent = converted.get(leg.get("parent_run") or "")
        metrics = route_metrics(m, leg, parent["metrics"] if parent else None)
    else:
        metrics = godark_metrics(m, leg)
        cfg.setdefault("model", m.get("model"))
        cfg["label"] = m.get("label")
    created = leg.get("created_at") or ms(m.get("created_at")) or ms(p.stat().st_mtime)
    return {"run_id": leg["run_id"], "target": target, "model": m.get("model"), "config": cfg,
            "data_hash": m.get("data_hash"), "train_from": m.get("train_from") or fit.get("train_from"),
            "train_to": m.get("train_to") or fit.get("train_to"), "artifact": leg["path"],
            "proposer": "human", "parent_run": leg.get("parent_run"), "status": leg["status"],
            "created_at": created, "loop_id": None, "round": None, "git_sha": None, "source": leg["source"],
            "version": leg.get("version") or m.get("version"), "metrics": metrics}


def registry_run(row: dict, root: Path, source: str) -> dict:
    """A registry run JSON -> run record: unchanged but for ms times, a portable artifact path, target and source."""
    r = dict(row)
    r["registry_target"] = row["target"]
    r["target"] = LAB_TARGET.get(row["target"], row["target"])
    r["created_at"] = ms(row.get("created_at"))
    r["artifact"] = rel(row.get("artifact"), root)
    r["source"] = row.get("source") or source
    r["version"] = row.get("version") or row["run_id"]
    if r["target"] != row["target"]:
        r["model"] = f"{row['model']} ({row['target']})"
    return r


def proposal_record(p: dict, runs: dict[str, dict], source: str) -> dict:
    errors = p.get("errors") or []
    run = runs.get(p.get("run_id") or "")
    if not p.get("valid"):
        outcome = "duplicate" if any("duplicate" in str(e) for e in errors) else "invalid"
    elif run is None:
        outcome = "invalid" if errors else "rejected"
    else:
        outcome = {"retired": "champion"}.get(run["status"], run["status"])
    created = ms(p.get("created_at"))
    key = json.dumps([p.get("target"), p.get("loop_id"), p.get("round"), p.get("id"), created,
                      p.get("proposal")], sort_keys=True, default=str)
    return {"id": f"{p.get('target')}-{hashlib.sha256(key.encode()).hexdigest()[:12]}",
            "target": LAB_TARGET.get(p.get("target"), p.get("target")), "loop_id": p.get("loop_id"),
            "round": p.get("round"), "proposer": p.get("proposer"), "created_at": created,
            "proposal": p.get("proposal"), "valid": bool(p.get("valid")), "errors": errors,
            "rationale": p.get("rationale"), "source": p.get("source") or source, "run_id": p.get("run_id"),
            "outcome": outcome, "origin": source}


def _primary(run: dict) -> tuple[str | None, dict]:
    sk = (run.get("metrics") or {}).get("skill") or {}
    for k in PRIMARY.get(run.get("registry_target") or run["target"], []):
        if k in sk:
            return k, sk[k]
    k = next(iter(sk), None)
    return k, sk.get(k, {}) if k else {}


def _fmt_h(k: str | None) -> str:
    if not k:
        return "?"
    s = int(k)
    return f"{s // 86400} d" if s >= 86400 and s % 86400 == 0 else f"{s // 3600} h" if s >= 3600 else f"{s // 60} min"


def run_events(run: dict) -> list[dict]:
    """trained, then promoted or rejected (or nothing for a candidate) for one run record."""
    k, s = _primary(run)
    sk = s.get("skill")
    head = f"{run['run_id']}: skill {sk:+.3f} at {_fmt_h(k)}" if sk is not None else run["run_id"]
    base = {"target": run["target"], "run_id": run["run_id"], "version": run.get("version") or run["run_id"]}
    ev = [base | {"ts": run["created_at"], "kind": "trained", "label": f"trained {head}",
                  "detail": {"proposer": run.get("proposer"), "source": run.get("source"),
                             "parent_run": run.get("parent_run"), "horizon_s": int(k) if k else None,
                             "skill": sk, "skill_lo": s.get("skill_lo"), "skill_hi": s.get("skill_hi")}}]
    dec = (run.get("metrics") or {}).get("decision") or {}
    reasons = dec.get("reasons") or []
    if run["status"] in ("champion", "retired"):
        ev.append(base | {"ts": run["created_at"] + 1, "kind": "promoted",
                          "label": f"promoted {run['run_id']} over {dec.get('against') or 'the champion'}",
                          "detail": {"against": dec.get("against"), "by": dec.get("by", "rule"),
                                     "reasons": reasons}})
    elif run["status"] == "rejected":
        why = reasons[0] if reasons else "did not beat the champion"
        ev.append(base | {"ts": run["created_at"] + 1, "kind": "rejected", "label": f"rejected {run['run_id']}: {why}",
                          "detail": {"against": dec.get("against"), "reasons": reasons}})
    return ev


def recal_events(root: Path) -> list[dict]:
    out = []
    paths = sorted(root.glob("recal/*/model.json")) + sorted(root.glob("route/artifacts/*/recalibration.json"))
    for p in paths:
        if p.name == "recalibration.json":
            m = json.loads((p.parent / "model.json").read_text())
            rc = json.loads(p.read_text())
            parent = m.get("parent_version") or m["version"].rsplit("-cal", 1)[0]
        else:
            m = json.loads(p.read_text())
            rc = m.get("recalibration") or (m.get("recalibrations") or [None])[-1]
            if not rc:
                continue
            parent = rc.get("parent")
        version = m["version"]
        target = m.get("target", "route")
        kept = RECAL_KEPT.get(version, True)
        detail = {"parent": parent, "kept": kept, "method": rc.get("method") or "conformal inflation on our feed",
                  "why": RECAL_WHY.get(version) or rc.get("caveat") or rc.get("check")}
        if "factors" in rc:
            detail["factors"] = rc["factors"]
        if "heads" in rc:
            detail["heads"] = rc["heads"]
        if "per_horizon" in rc:
            detail["factors"] = {h: {"k80": v.get("inflation80"), "k95": v.get("inflation95"), "n": v.get("n"),
                                     "from": v.get("how")} for h, v in rc["per_horizon"].items()}
            detail["before"], detail["after"] = rc.get("before"), rc.get("after")
        if target == "route" and version.endswith("-cal1"):
            detail["before"] = {"cover80": [0.58, 0.64], "cover95": [0.87, 0.89], "on": "11 h backtest of our feed"}
            detail["after"] = {"cover80": [0.79, 0.82], "cover95": [0.95, 0.97],
                               "on": "later half of the backtest (fitted on the first half)"}
        out.append({"ts": ms(p.stat().st_mtime), "target": target, "kind": "recalibrated", "run_id": parent,
                    "version": version, "label": f"recalibrated {parent} -> {version}"
                    + ("" if kept else " (not deployed)"), "detail": detail})
    return out


def proposal_events(props: list[dict]) -> list[dict]:
    return [{"ts": p["created_at"], "target": p["target"], "kind": "proposal", "run_id": p.get("run_id"),
             "version": None, "label": f"{p['proposer']} proposal: {p['outcome']}",
             "detail": {"id": p["id"], "rationale": p.get("rationale"), "errors": p.get("errors")}} for p in props]


def collect(root: Path = DATA) -> dict[str, list[dict]]:
    runs: dict[str, dict] = {}
    for leg in LEGACY:
        r = legacy_run(leg, root, runs)
        if r:
            runs[r["run_id"]] = r
    raw_props = []
    for p in sorted(root.glob("registry/*/runs/*.json")):
        r = registry_run(json.loads(p.read_text()), root, "pc-aiden")
        runs[r["run_id"]] = r
    for p in sorted(root.glob("registry/*/proposals/*.json")):
        raw_props.append(json.loads(p.read_text()))
    props = [proposal_record(p, runs, "pc-aiden") for p in raw_props]
    events = [e for r in runs.values() for e in run_events(r)]
    events += recal_events(root)
    events += [d | {"kind": "deployed"} for d in DEPLOYS if d["run_id"] in runs]
    events += proposal_events(props)
    return {"runs": sorted(runs.values(), key=lambda r: (r["created_at"], r["run_id"]), reverse=True),
            "proposals": sorted(props, key=lambda p: (p["created_at"] or 0, p["id"]), reverse=True),
            "events": sorted(events, key=lambda e: (e["ts"], e["target"], e["kind"], e["run_id"] or ""))}


def _line(rec: dict) -> str:
    return json.dumps(rec, sort_keys=True, default=str, allow_nan=False)


def write_bundle(bundle: dict[str, list[dict]], out: Path) -> dict[str, int]:
    out.mkdir(parents=True, exist_ok=True)
    for name in FILES:
        tmp = out / f"{name}.jsonl.tmp"
        tmp.write_text("".join(_line(r) + "\n" for r in bundle.get(name, [])))
        os.replace(tmp, out / f"{name}.jsonl")
    return {k: len(bundle.get(k, [])) for k in FILES}


def read_bundle(path: Path) -> dict[str, list[dict]]:
    out = {}
    for name in FILES:
        p = path / f"{name}.jsonl"
        out[name] = [json.loads(x) for x in p.read_text().splitlines() if x.strip()] if p.exists() else []
    return out


# ---------------------------------------------------------------- ml.auto cycles

def append_cycle(status: dict, reg, root: Path, out: Path, source: str = "server") -> dict[str, int]:
    """Append one ml.auto cycle to the bundle at `out`: the runs and proposals of each target's loop (by loop_id),
    their events, a `recalibrated` event per changed champion and a `deployed` event per deploy. Appends only;
    the importer keeps the newest row of a run, so a run whose status changes later is simply appended again."""
    runs, props, events = [], [], []
    for t, st in (status.get("targets") or {}).items():
        lid = st.get("loop_id")
        if not lid:
            continue
        rows = [r for r in reg.list_runs(t) if r.get("loop_id") == lid]
        before = st.get("champion_before")
        if before and before != st.get("champion_after"):
            old = reg.get_run(before)
            if old:
                rows.append(old)          # now retired
        recs = {r["run_id"]: registry_run(r, root, source) for r in rows}
        runs += recs.values()
        cyc = [proposal_record(p, recs, source) for p in reg.list_proposals(t) if p.get("loop_id") == lid]
        props += cyc
        events += [e for r in recs.values() if r.get("loop_id") == lid for e in run_events(r)]
        events += proposal_events(cyc)
        if st.get("deployed"):
            after = recs.get(st.get("champion_after") or "")
            events.append({"ts": ms(st.get("finished")) or ms(datetime.now(timezone.utc)),
                           "target": LAB_TARGET.get(t, t), "kind": "deployed",
                           "run_id": st.get("champion_after"), "version": st["deployed"],
                           "label": f"{t} {st['deployed']} live", "detail": {"by": "ml.auto",
                                                                              "run": (after or {}).get("run_id")}})
    rc = status.get("recalibrate") or {}
    for t, version in (rc.get("changed") or {}).items():
        events.append({"ts": ms(status.get("started")), "target": t, "kind": "recalibrated",
                       "run_id": version.split("-cal")[0], "version": version,
                       "label": f"recalibrated -> {version}", "detail": {"by": "ml.auto", "rows": rc.get("rows"),
                                                                         "kept": True}})
    out.mkdir(parents=True, exist_ok=True)
    for name, recs in (("runs", runs), ("proposals", props), ("events", events)):
        with open(out / f"{name}.jsonl", "a") as f:
            f.writelines(_line(r) + "\n" for r in recs)
    return {"runs": len(runs), "proposals": len(props), "events": len(events)}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python -m ml.core.history", description=__doc__.split("\n\n")[0])
    sub = ap.add_subparsers(dest="cmd", required=True)
    ex = sub.add_parser("export", help="write the bundle from every run on this machine")
    ex.add_argument("--data", type=Path, default=DATA)
    ex.add_argument("--out", type=Path, default=Path("data/lab-history"))
    a = ap.parse_args(argv)
    counts = write_bundle(collect(a.data), a.out)
    print(json.dumps({"out": str(a.out), **counts}))


if __name__ == "__main__":
    main()
