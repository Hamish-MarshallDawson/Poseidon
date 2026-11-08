"""Train and evaluate the route model on its own, with the full route report (strata, synthetic and real dead zones,
transfer to our live AIS). The loop (`ml.core.run/loop --target route`) is the path that registers and promotes;
this is the quick, detailed look.

    python -m ml.route.train [--data dma] [--cfg cfg.json] [--test-frac 0.2] [--out DIR] [--report FILE.json]
                             [--transfer tiger]

The newest `--test-frac` of the as_of span is the test window. A training case for horizon h must have its truth
before the test window starts (embargo = h). Inside training, each model keeps its own newest slice for conformal
radii (model.py). Model and baseline are fitted on the same rows and scored on the same test rows; skill intervals
are paired bootstraps. `--transfer tiger` also scores the model trained here on our own live AIS and real gaps
(features, baseline and truth exactly as for the Danish cases).
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import pandas as pd

from ml.core.registry import save_artifact
from ml.route import metrics as M
from ml.route.model import RouteBaseline, RouteLGBM, examples_hash
from ml.route.target import SPEC


def time_split(ex: pd.DataFrame, test_frac: float, horizons):
    t_lo, t_hi = int(ex["as_of"].min()), int(ex["as_of"].max())
    test_start = t_hi - int((t_hi - t_lo) * test_frac)
    train = ex[ex["as_of"] < test_start].copy()
    for h in horizons:                                    # embargo per horizon: truth must end before the test window
        late = train["as_of"] + int(h) * 1000 > test_start
        train.loc[late, [f"truth_lat_{h}", f"truth_lon_{h}"]] = float("nan")
    test = ex[ex["as_of"] >= test_start]
    return train, test, test_start


def evaluate(model, base, test: pd.DataFrame, reps: int = 400) -> dict:
    pairs = M.paired(M.score(test, model.predict(test)), M.score(test, base.predict(test)))
    return M.report(pairs, M.reappear_frame(model, base, test), reps)


def run(ex: pd.DataFrame, cfg: dict, test_frac: float = 0.2, out: Path | None = None,
        transfer: pd.DataFrame | None = None) -> dict:
    hs = SPEC.horizons_s
    train, test, test_start = time_split(ex, test_frac, hs)
    t0 = time.time()
    model = RouteLGBM().fit(train, {**SPEC.default_config, **cfg})
    base = RouteBaseline().fit(train, {**SPEC.default_config, **cfg, "model": "baseline"})
    fit_s = time.time() - t0
    rep = evaluate(model, base, test)
    rep["meta"] = {"rows_train": int(len(train)), "rows_test": int(len(test)), "test_start": test_start,
                   "test_to": int(test["as_of"].max()), "train_from": int(train["as_of"].min()),
                   "fit_seconds": round(fit_s, 1), "n_fit": model.meta["n_fit"], "n_calib": model.meta["n_calib"],
                   "horizons_s": model.horizons, "cfg": model.cfg, "examples_hash": examples_hash(ex),
                   "test_kinds": test["kind"].value_counts().to_dict(),
                   "test_reappear": test["reap_kind"].value_counts().to_dict()}
    if transfer is not None and len(transfer):
        rep["transfer"] = {"all": evaluate(model, base, transfer)}
        dk = transfer[transfer["fix_lat"].between(53.5, 58.5) & transfer["fix_lon"].between(7, 16)]
        if len(dk):
            rep["transfer"]["danish_box"] = evaluate(model, base, dk)
    if out:
        meta = {"version": out.name, "data_hash": examples_hash(ex), "config": model.cfg,
                "metrics": {"by_horizon": rep["by_horizon"],
                            "reappear": {k: v["all"] for k, v in rep["reappear"].items()}},
                "created_at": pd.Timestamp.now(tz="UTC").isoformat(timespec="seconds")}
        save_artifact(model, out, meta)
    return rep


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", default="dma", help="dma | dma:N | tiger | dma+tiger | FILE.parquet")
    ap.add_argument("--cfg", type=Path, help="JSON config (keys of the route config schema)")
    ap.add_argument("--test-frac", type=float, default=0.2)
    ap.add_argument("--transfer", help="also score on this source (e.g. tiger) with the model trained here")
    ap.add_argument("--out", type=Path, help="write the artifact (backend format) to this directory")
    ap.add_argument("--report", type=Path, help="write the JSON report here")
    a = ap.parse_args()
    cfg = json.loads(a.cfg.read_text()) if a.cfg else {}
    t0 = time.time()
    ex = SPEC.load_examples(cfg, a.data)
    tr = SPEC.load_examples(cfg, a.transfer) if a.transfer else None
    print(f"examples: {len(ex)} cases in {time.time() - t0:.0f}s"
          + (f"; transfer: {len(tr)} cases" if tr is not None else ""))
    rep = run(ex, cfg, a.test_frac, a.out, tr)
    print(M.table(rep))
    for k, v in rep.get("transfer", {}).items():
        print(f"\ntransfer to {a.transfer} ({k}):\n{M.table(v)}")
    if a.report:
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(json.dumps(rep, indent=1, default=str))


if __name__ == "__main__":
    main()
