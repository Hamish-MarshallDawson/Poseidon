"""The improvement loop: each round, the proposer reads a summary of past runs and proposes K configs; each valid
one is trained and scored against the champion on the frozen held-out set (Bonferroni over K); the best one that
passes the rule is re-run with a second seed and promoted only if it passes again. Every proposal is logged.

    python -m ml.core.loop --target route --rounds 3 [--proposals 4] [--dry-run] [--data PATH]
"""
from __future__ import annotations

import argparse
import json
import secrets
from datetime import datetime, timezone
from pathlib import Path

import pandas as pd

from ml.core import env  # noqa: F401
from ml.core import report
from ml.core.propose import ProposerError, propose, validate
from ml.core.registry import DEFAULT_ARTIFACTS, Registry, open_registry
from ml.core.run import promote, run_one
from ml.core.target import TargetSpec, get_target

SUMMARY_RUNS = 12


def summary_for_proposer(spec: TargetSpec, reg: Registry) -> dict:
    """Aggregates only: per-horizon and per-stratum metrics of recent runs, the champion, data volume and the
    rejected proposals. No case-level rows, no held-out case ids."""
    runs = [r for r in reg.list_runs(spec.name) if (r.get("metrics") or {}).get("state") == "done"]
    champ = reg.champion(spec.name)

    def brief(r):
        m = r["metrics"]
        return {"run_id": r["run_id"], "status": r["status"], "proposer": r["proposer"], "config": r["config"],
                "skill_vs_baseline": {h: {k: round(v[k], 4) for k in ("skill", "skill_lo", "skill_hi", "stat")}
                                      for h, v in m["skill"].items()},
                "calibration": [{k: c[k] for k in ("name", "horizon_s", "value", "nominal")} for c in m["calibration"]],
                "cv": m["cv"], "decision_reasons": m["decision"]["reasons"][:4], "n_train": m["split"]["n_train"]}

    weak = []
    if champ:
        st, sb = champ["metrics"].get("strata", {}), champ["metrics"].get("strata_baseline", {})
        for col, rows in st.items():
            base = {(b["horizon_s"], b["value"]): b["stat"] for b in sb.get(col, [])}
            for x in rows:
                b = base.get((x["horizon_s"], x["value"]))
                if b and x["n"] >= 30:
                    weak.append({"stratum": col, "value": x["value"], "horizon_s": x["horizon_s"], "n": x["n"],
                                 "stat": round(x["stat"], 4), "baseline_stat": round(b, 4)})
        weak.sort(key=lambda w: w["stat"] / w["baseline_stat"] if w["baseline_stat"] else 0, reverse=True)
    rejected = [{"proposal": p["proposal"], "errors": p["errors"]} for p in reg.list_proposals(spec.name)
                if not p["valid"]][-5:]
    hold = (runs[-1]["metrics"]["holdout"] if runs else {})
    return {"statistic": spec.statistic, "loss": spec.loss_name, "unit": spec.loss_unit,
            "horizons_s": spec.horizons_s, "primary_horizons_s": spec.primary_horizons_s,
            "holdout": {k: hold.get(k) for k in ("name", "n", "from", "to")},
            "champion": brief(champ) if champ else None, "recent_runs": [brief(r) for r in runs[-SUMMARY_RUNS:]],
            "champion_weakest_strata": weak[:6], "invalid_proposals": rejected,
            "promotion_rule": "beat the champion at every primary horizon with a paired bootstrap interval excluding "
                              "zero (Bonferroni over the round), calibration within 5 points, no stratum (n>=30) "
                              "worse by more than 10%, and win again with a second seed"}


def _key(cfg) -> str:
    return json.dumps(cfg, sort_keys=True, default=str)


def mean_gain(spec: TargetSpec, row: dict) -> float:
    """How much better than the reference, averaged over primary horizons (relative), to rank passing runs."""
    hs = row["metrics"]["decision"]["horizons"]
    vals = [-(v["diff"] / v["ref"]) for v in hs.values() if v["ref"]]
    return sum(vals) / len(vals) if vals else 0.0


def loop(spec: TargetSpec, rounds: int, *, reg: Registry, k: int = 4, dry_run: bool = False,
         data: str | None = None, examples: pd.DataFrame | None = None, holdout_name: str | None = None,
         confirm_seed: bool = True, n_folds: int = 3, artifacts: Path = DEFAULT_ARTIFACTS,
         report_dir: Path | None = None, log=print) -> dict:
    loop_id = f"loop-{datetime.now(timezone.utc):%Y%m%dT%H%M%S}-{secrets.token_hex(2)}"
    if examples is None:
        examples = spec.load_examples(spec.default_config, data)
    log(f"[{loop_id}] {spec.name}: {len(examples)} examples, {rounds} rounds of {k} proposals"
        f"{' (dry run)' if dry_run else ''}")
    common = dict(reg=reg, examples=examples, holdout_name=holdout_name, loop_id=loop_id, n_folds=n_folds,
                  artifacts=artifacts, log=log)
    history = []
    if not reg.champion(spec.name):
        # Round 0: the default config against the baseline, so there is something to beat.
        row = run_one(spec, dict(spec.default_config), proposer="default", round_=0, **common)
        reg.log_proposal({"target": spec.name, "loop_id": loop_id, "round": 0, "proposer": "default",
                          "proposal": spec.default_config, "valid": True, "run_id": row["run_id"],
                          "rationale": "default config: first run of the loop", "source": "target default config"})
        history.append({"round": 0, "promoted": row["run_id"] if row["status"] == "champion" else None})
    for r in range(1, rounds + 1):
        champ = reg.champion(spec.name)
        try:
            who, source, props = propose(spec, summary_for_proposer(spec, reg), k, r, dry_run)
        except ProposerError as e:
            log(f"[{loop_id}] round {r}: proposer failed ({e}); stopping")
            history.append({"round": r, "error": str(e)})
            break
        ran = {_key(x["config"]): x["run_id"] for x in reg.list_runs(spec.name)
               if (x.get("metrics") or {}).get("state") == "done"}
        if "fallback" in source:
            log(f"[{loop_id}] round {r}: {source}")
        valid = []
        for p in props:
            errs = validate(spec, p.get("config"))
            if not errs and _key(p["config"]) in ran:
                errs = [f"duplicate of run {ran[_key(p['config'])]}: already evaluated"]
            valid.append((p, errs))
        n_cmp = max(1, sum(1 for _, e in valid if not e))
        passing = []
        for p, errs in valid:
            pid_row = {"target": spec.name, "loop_id": loop_id, "round": r, "proposer": who,
                       "proposal": p.get("config"), "valid": not errs, "errors": errs,
                       "rationale": p.get("rationale"), "source": source}
            if errs:
                reg.log_proposal(pid_row)
                log(f"[{loop_id}] round {r}: rejected proposal {p.get('config')}: {errs[:2]}")
                continue
            try:
                row = run_one(spec, p["config"], proposer=who, round_=r, n_comparisons=n_cmp,
                              allow_promote=False, parent_run=(champ or {}).get("run_id"), **common)
            except Exception as e:   # a proposal that crashes training is a rejected proposal, not a dead loop
                reg.log_proposal(pid_row | {"valid": False, "errors": [f"run failed: {e!r}"[:300]]})
                log(f"[{loop_id}] round {r}: run failed: {e!r}")
                continue
            reg.log_proposal(pid_row | {"run_id": row["run_id"]})
            if row["status"] == "candidate":
                passing.append(row)
        promoted = None
        if passing:
            best = max(passing, key=lambda x: mean_gain(spec, x))
            ok = True
            if confirm_seed:
                cfg2 = {**best["config"], "seed": best["config"]["seed"] + 1}
                again = run_one(spec, cfg2, proposer=who, round_=r, n_comparisons=n_cmp, allow_promote=False,
                                parent_run=best["run_id"], **common)
                reg.log_proposal({"target": spec.name, "loop_id": loop_id, "round": r, "proposer": who,
                                  "proposal": cfg2, "valid": True, "run_id": again["run_id"],
                                  "rationale": f"second-seed confirmation of {best['run_id']}", "source": source})
                ok = again["status"] == "candidate"
                if not ok:
                    log(f"[{loop_id}] round {r}: {best['run_id']} did not win again with seed {cfg2['seed']}")
            if ok:
                promote(reg, spec, best, artifacts)
                promoted = best["run_id"]
                log(f"[{loop_id}] round {r}: promoted {promoted} (gain {mean_gain(spec, best):+.1%})")
        if not promoted:
            log(f"[{loop_id}] round {r}: champion kept ({(champ or {}).get('run_id', 'baseline')})")
        history.append({"round": r, "proposer": who, "source": source, "proposals": len(props), "valid": n_cmp,
                        "passing": [x["run_id"] for x in passing], "promoted": promoted})
    out = {"loop_id": loop_id, "target": spec.name, "rounds": history,
           "champion": (reg.champion(spec.name) or {}).get("run_id")}
    paths = report.write(spec, reg, report_dir or artifacts / "reports")
    out["report"] = {k: str(v) for k, v in paths.items()}
    log(f"[{loop_id}] done; champion {out['champion']}; report {paths['html']}")
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python -m ml.core.loop", description=__doc__.split("\n\n")[0])
    ap.add_argument("--target", required=True)
    ap.add_argument("--rounds", type=int, default=3)
    ap.add_argument("--proposals", type=int, default=4, help="configs per round (the Bonferroni K)")
    ap.add_argument("--dry-run", action="store_true", help="fixed proposals; never calls Gemini")
    ap.add_argument("--data")
    ap.add_argument("--holdout")
    ap.add_argument("--registry")
    ap.add_argument("--folds", type=int, default=3)
    ap.add_argument("--no-confirm", action="store_true", help="skip the second-seed confirmation")
    a = ap.parse_args(argv)
    out = loop(get_target(a.target), a.rounds, reg=open_registry(a.registry), k=a.proposals, dry_run=a.dry_run,
               data=a.data, holdout_name=a.holdout, confirm_seed=not a.no_confirm, n_folds=a.folds)
    print(json.dumps(out, indent=2))


if __name__ == "__main__":
    main()
