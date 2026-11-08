"""Train and evaluate the route model in one command: build examples, fit the baseline and LightGBM per horizon,
score both on the frozen held-out set, write the artifact (backend format) and metrics.json.

    python -m ml.route.train --data DIR_OR_SOURCE --out ARTIFACT_DIR [--transfer tiger] [--cfg cfg.json]

`--data`: a Danish archive directory written by `python -m ml.data.dma --out DIR` (or `dma`, `dma:N`, `tiger`,
`dma+tiger`, an examples Parquet). Held-out set: the newest 20% of the as_of span, frozen on first use as
`<holdout root>/holdout/route-<name>.json` (case ids + hash) and reused after, exactly as `ml.core.run` does; training
labels end 24 h (the longest horizon) before it starts. Inside training, each model keeps its own newest slice for
the conformal radii. Model and baseline are fitted on the same rows and scored on the same held-out cases; skill
intervals are paired bootstraps; `decision` is ml/core's promotion rule against the baseline.

Writes into --out: `model.json` and `h<h>_east.txt` / `h<h>_north.txt` (what backend/dvm/predict loads), and
`metrics.json` (held-out description, per-horizon metrics with intervals, strata, dead-zone sets, the decision, run
time and peak memory). `--out` must not exist yet or will be replaced.
"""
from __future__ import annotations

import argparse
import json
import platform
import sys
import time
from pathlib import Path

import pandas as pd

from ml.core import evaluate as ev
from ml.core.registry import save_artifact
from ml.route import metrics as M
from ml.route.model import RouteBaseline, RouteLGBM, examples_hash
from ml.route.target import SPEC


def time_split(ex: pd.DataFrame, test_frac: float, horizons):
    """A plain time split with a per-horizon embargo (tests and quick looks; the CLI uses the frozen held-out)."""
    t_lo, t_hi = int(ex["as_of"].min()), int(ex["as_of"].max())
    test_start = t_hi - int((t_hi - t_lo) * test_frac)
    train = ex[ex["as_of"] < test_start].copy()
    for h in horizons:
        late = train["as_of"] + int(h) * 1000 > test_start
        train.loc[late, [f"truth_lat_{h}", f"truth_lon_{h}"]] = float("nan")
    return train, ex[ex["as_of"] >= test_start], test_start


def evaluate(model, base, test: pd.DataFrame, reps: int = 400):
    sm, sb = M.score(test, model.predict(test)), M.score(test, base.predict(test))
    return M.report(M.paired(sm, sb), M.reappear_frame(model, base, test), reps), sm, sb


def peak_rss_mb() -> float | None:
    try:
        import resource   # not on Windows
        r = resource.getrusage(resource.RUSAGE_SELF).ru_maxrss
        c = resource.getrusage(resource.RUSAGE_CHILDREN).ru_maxrss
        return round(max(r, c) / (1024 * 1024 if sys.platform == "darwin" else 1024), 0)
    except Exception:   # pragma: no cover - Windows
        return None


def run(ex: pd.DataFrame, cfg: dict, out: Path | None = None, transfer: pd.DataFrame | None = None,
        holdout_root: Path | None = None, holdout_name: str = "v1", t_start: float | None = None) -> dict:
    t0 = time.time()
    holdout = ev.freeze_holdout(SPEC, ex, holdout_name, root=holdout_root)
    train, test, split_info = ev.split(SPEC, ex, holdout)
    if train.empty or test.empty:
        raise ValueError(f"nothing to train or test on: {split_info}")
    cfg = {**SPEC.default_config, **cfg}
    model = RouteLGBM().fit(train, cfg)
    base = RouteBaseline().fit(train, {**cfg, "model": "baseline"})
    fit_s = time.time() - t0
    rep, sm, sb = evaluate(model, base, test)
    decision = ev.decide(SPEC, sm, sb, 1, "baseline")
    rep["decision"] = {k: decision[k] for k in ("promote", "reasons", "against") if k in decision}
    rep["calibration"] = SPEC.calibration(sm)
    rep["sanity"] = SPEC.sanity(SPEC.summarise(sm))
    rep["meta"] = {
        "target": "route", "model": model.name, "holdout": holdout.describe(), "split": split_info,
        "train_from": int(train["as_of"].min()), "train_to": int(train["as_of"].max()),
        "n_fit": model.meta["n_fit"], "n_calib": model.meta["n_calib"], "horizons_s": model.horizons,
        "live_horizons_s": [h for h in model.horizons if h in SPEC.primary_horizons_s],
        "config": model.cfg, "examples_hash": examples_hash(ex), "examples": int(len(ex)),
        "test_kinds": test["kind"].value_counts().to_dict(),
        "test_dead_zones": test["reap_kind"].value_counts().to_dict(),
        "fit_seconds": round(fit_s, 1), "python": platform.python_version(),
        "data_note": "Danish Maritime Authority AIS archive (http://aisdata.ais.dk/)"}
    if transfer is not None and len(transfer):
        rep["transfer"] = {"all": evaluate(model, base, transfer)[0]}
        dk = transfer[transfer["fix_lat"].between(53.5, 58.5) & transfer["fix_lon"].between(7, 16)]
        if len(dk):
            rep["transfer"]["danish_box"] = evaluate(model, base, dk)[0]
    rep["meta"]["total_seconds"] = round(time.time() - (t_start or t0), 1)
    rep["meta"]["peak_rss_mb"] = peak_rss_mb()
    if out:
        meta = {"version": out.name, "data_hash": examples_hash(ex), "config": model.cfg,
                "metrics": {"holdout": holdout.describe(), "by_horizon": rep["by_horizon"],
                            "reappear": {k: v["all"] for k, v in rep["reappear"].items()}},
                "created_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")}
        save_artifact(model, out, meta)
        (out / "metrics.json").write_text(json.dumps(rep, indent=1, default=str))
    return rep


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", default="dma", help="Danish archive dir | dma | dma:N | tiger | dma+tiger | FILE.parquet")
    ap.add_argument("--out", type=Path, help="artifact directory to write (model.json, LightGBM dumps, metrics.json)")
    ap.add_argument("--cfg", type=Path, help="JSON config (keys of the route config schema)")
    ap.add_argument("--transfer", help="also score on this source (e.g. tiger) with the model trained here")
    ap.add_argument("--holdout-root", type=Path, help="where held-out sets are frozen (default: ML_ARTIFACTS, else "
                                                       "<out>/../ when --out is given)")
    ap.add_argument("--holdout", default="v1", help="held-out set name (frozen on first use)")
    ap.add_argument("--report", type=Path, help="also write the JSON report here")
    a = ap.parse_args()
    t0 = time.time()
    cfg = json.loads(a.cfg.read_text()) if a.cfg else {}
    import os
    root = a.holdout_root or (Path(os.environ["ML_ARTIFACTS"]) if os.environ.get("ML_ARTIFACTS")
                              else (a.out.parent if a.out else None))
    ex = SPEC.load_examples(cfg, str(a.data))
    tr = SPEC.load_examples(cfg, a.transfer) if a.transfer else None
    print(f"examples: {len(ex)} cases in {time.time() - t0:.0f}s" + (f"; transfer: {len(tr)}" if tr is not None else ""),
          flush=True)
    rep = run(ex, cfg, a.out, tr, root, a.holdout, t0)
    h = rep["meta"]["holdout"]
    print(f"held-out {h.get('name')}: {h.get('n')} cases from {h.get('start')} (hash {h.get('hash')})")
    print(M.table(rep))
    for k, v in rep.get("transfer", {}).items():
        print(f"\ntransfer to {a.transfer} ({k}):\n{M.table(v)}")
    print(f"\npromote over baseline: {rep['decision']['promote']} {rep['decision']['reasons'][:3]}")
    print(f"total {rep['meta']['total_seconds']:.0f}s, peak RSS {rep['meta']['peak_rss_mb']} MB"
          + (f"; wrote {a.out}" if a.out else ""))
    if a.report:
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(json.dumps(rep, indent=1, default=str))


if __name__ == "__main__":
    main()
