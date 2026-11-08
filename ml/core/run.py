"""One training run: validate the config, split by time around the frozen held-out set, cross-validate on rolling
folds, fit, score on the held-out set against the baseline and the champion, apply the promotion rule, save the
artifact and log everything in the registry.

    python -m ml.core.run --target route --config cfg.json [--data PATH] [--holdout v1] [--no-promote]
"""
from __future__ import annotations

import argparse
import json
import time
import traceback
from pathlib import Path

import numpy as np
import pandas as pd

from ml.core import env  # noqa: F401  (loads the repo .env)
from ml.core import evaluate as ev
from ml.core.propose import validate
from ml.core.registry import (DEFAULT_ARTIFACTS, Registry, data_hash, elapsed, git_sha, load_artifact,
                              new_run_id, open_registry, save_artifact)
from ml.core.target import TargetSpec, get_target

DAY_MS = 86_400_000


def window(train: pd.DataFrame, cfg: dict) -> pd.DataFrame:
    """Keep the last `train_window_days` of training examples, if the config sets it."""
    days = cfg.get("train_window_days")
    if not days or train.empty:
        return train
    return train[train["as_of"] >= int(train["as_of"].max()) - int(days) * DAY_MS]


def fit_score(spec: TargetSpec, cfg: dict, train: pd.DataFrame, test: pd.DataFrame):
    model = spec.models[cfg["model"]]().fit(train, cfg)
    return model, spec.score(test, model.predict(test))


def cross_validate(spec: TargetSpec, cfg: dict, train: pd.DataFrame, n_folds: int) -> dict:
    """Mean over rolling-origin folds of the statistic and the skill over the baseline, per horizon."""
    per_h: dict[str, list] = {}
    folds = ev.rolling_folds(spec, train, n_folds)
    for fit, val in folds:
        _, s = fit_score(spec, cfg, fit, val)
        _, b = fit_score(spec, {**cfg, "model": spec.baseline}, fit, val)
        for h in spec.horizons_s:
            a, bb, _ = ev.paired(s, b, h)
            if len(a):
                per_h.setdefault(str(h), []).append((ev.stat(a, spec.statistic), ev.skill_fn(spec.statistic)(a, bb)))
    return {"n_folds": len(folds), "horizons": {h: {"stat": float(np.mean([v[0] for v in vs])),
                                                   "skill": float(np.mean([v[1] for v in vs]))}
                                               for h, vs in per_h.items()}}


def champion_pointer(target: str, artifacts: Path) -> Path:
    return artifacts / target / "champion.json"


def write_champion_pointer(target: str, run: dict, artifacts: Path) -> None:
    p = champion_pointer(target, artifacts)
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps({"target": target, "run_id": run["run_id"], "artifact": run["artifact"],
                             "model": run["model"]}, indent=2))


def promote(reg: Registry, spec: TargetSpec, run: dict, artifacts: Path) -> None:
    reg.set_champion(spec.name, run["run_id"])
    write_champion_pointer(spec.name, run, artifacts)


def run_one(spec: TargetSpec, cfg: dict, *, reg: Registry, examples: pd.DataFrame | None = None,
            data: str | None = None, holdout_name: str | None = None, proposer: str = "human",
            parent_run: str | None = None, loop_id: str | None = None, round_: int | None = None,
            n_comparisons: int = 1, allow_promote: bool = True, n_folds: int = 3,
            artifacts: Path = DEFAULT_ARTIFACTS, log=print) -> dict:
    """Returns the registry row as finally written. `allow_promote=False` (the loop) logs a passing run as
    `candidate` and leaves promotion to the caller; otherwise a passing run becomes the champion."""
    errs = validate(spec, cfg)
    if errs:
        raise ValueError(f"invalid config: {errs}")
    t0 = time.monotonic()
    if examples is None:
        examples = spec.load_examples(cfg, data)
    holdout = ev.load_holdout(spec.name, holdout_name, artifacts) or ev.freeze_holdout(
        spec, examples, holdout_name or "v1", root=artifacts)
    train, test, split_info = ev.split(spec, examples, holdout)
    train = window(train, cfg)
    split_info["n_train"] = len(train)
    if train.empty or test.empty:
        raise ValueError(f"nothing to train or test on: {split_info}")

    run_id = new_run_id(spec.name)
    champ = reg.champion(spec.name)
    row = {"run_id": run_id, "target": spec.name, "model": cfg["model"], "config": cfg,
           "data_hash": data_hash(examples), "train_from": int(train["as_of"].min()),
           "train_to": int(train["as_of"].max()), "proposer": proposer,
           "parent_run": parent_run or (champ or {}).get("run_id"), "status": "candidate",
           "loop_id": loop_id, "round": round_, "git_sha": git_sha(), "metrics": {"state": "running"}}
    reg.create_run(row)
    log(f"[{run_id}] {cfg['model']} by {proposer}: train {len(train)} cases, held-out {len(test)} "
        f"({holdout.name}, {holdout.hash})")
    try:
        cv = cross_validate(spec, cfg, train, n_folds)
        model, scored = fit_score(spec, cfg, train, test)
        _, base = fit_score(spec, {**cfg, "model": spec.baseline}, train, test)
        if champ:
            cm, _ = load_artifact(champ["artifact"], spec.models)
            ref, ref_label = spec.score(test, cm.predict(test)), f"champion {champ['run_id']}"
        else:
            ref, ref_label = base, "baseline (no champion yet)"
        summary = spec.summarise(scored)
        decision = ev.decide(spec, scored, ref, n_comparisons, ref_label)
        insane = spec.sanity(summary)
        if insane:
            decision["promote"] = False
            decision["reasons"] += [f"sanity: {r}" for r in insane]
        if cfg["model"] == spec.baseline and not champ:
            decision["promote"] = False
            decision["reasons"].append("the baseline is the reference, not a candidate")
        metrics = {
            "state": "done", "holdout": holdout.describe(), "split": split_info, "statistic": spec.statistic,
            "loss_name": spec.loss_name, "loss_unit": spec.loss_unit, "summary": summary,
            "skill": ev.skill_table(spec, scored, base), "calibration": spec.calibration(scored),
            "strata": ev.strata_table(spec, scored), "strata_baseline": ev.strata_table(spec, base),
            "cv": cv, "decision": decision, "sanity": insane, "seconds": elapsed(t0)}
        art = save_artifact(model, artifacts / spec.name / run_id, {
            "version": run_id, "data_hash": row["data_hash"], "config": cfg, "metrics": {
                "holdout": metrics["holdout"], "summary": summary, "skill": metrics["skill"]},
            "created_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")})
        passes = decision["promote"]
        status = "candidate" if passes else "rejected"
        reg.update_run(run_id, metrics=metrics, artifact=str(art), status=status)
        row |= {"metrics": metrics, "artifact": str(art), "status": status}
        if passes and allow_promote:
            promote(reg, spec, row, artifacts)
            row["status"] = "champion"
        pv = " ".join(f"{h}s skill {v['skill']:+.3f} [{v['skill_lo']:+.3f},{v['skill_hi']:+.3f}]"
                      for h, v in metrics["skill"].items() if int(h) in spec.primary_horizons_s)
        log(f"[{run_id}] {row['status']}: {pv}" + ("" if passes else f"; {decision['reasons'][:2]}"))
        return row
    except Exception as e:
        reg.update_run(run_id, status="rejected", metrics={"state": "failed", "error": repr(e)[:500],
                                                            "trace": traceback.format_exc()[-2000:]})
        raise


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python -m ml.core.run", description=__doc__.split("\n\n")[0])
    ap.add_argument("--target", required=True)
    ap.add_argument("--config", help="JSON file; default: the target's default config")
    ap.add_argument("--data", help="data path or URL the target understands")
    ap.add_argument("--holdout", help="held-out set name (default: newest, or freeze v1)")
    ap.add_argument("--registry", help="postgresql://... or a directory (default ML_DATABASE_URL)")
    ap.add_argument("--folds", type=int, default=3)
    ap.add_argument("--proposer", default="human", choices=["human", "default", "gemini"])
    ap.add_argument("--no-promote", action="store_true")
    a = ap.parse_args(argv)
    spec = get_target(a.target)
    cfg = json.loads(Path(a.config).read_text()) if a.config else dict(spec.default_config)
    row = run_one(spec, cfg, reg=open_registry(a.registry), data=a.data, holdout_name=a.holdout,
                  proposer=a.proposer, n_folds=a.folds, allow_promote=not a.no_promote)
    print(json.dumps({k: row[k] for k in ("run_id", "status", "artifact")}))


if __name__ == "__main__":
    main()
