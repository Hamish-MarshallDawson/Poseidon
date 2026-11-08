"""Train and evaluate route models on one source, time split with an embargo.

    python -m ml.route.train --source tiger [--data DIR] [--cfg cfg.json] [--out ARTIFACT_DIR] [--report FILE.json]
    python -m ml.route.train --source dma   [--data /home/aiden/data/poseidon/dma] [--days N]

The newest `--test-frac` of the as_of span is the test window. A training row for horizon h must have its truth
before the test window starts (embargo = h), so no training label overlaps test time. Inside training, the model
keeps its own newest slice for conformal radii (model.py). Both the baseline and LightGBM are fitted on the same
rows and scored on the same test rows; skill intervals are paired bootstraps.
"""
from __future__ import annotations

import argparse
import json
import time
from pathlib import Path

import numpy as np
import pandas as pd

from ml.route import TRAIN_HORIZONS_S, examples
from ml.route.metrics import errors, report, table
from ml.route.model import RouteModel

DATA = Path("/home/aiden/data/poseidon")


def load_tiger(d: Path):
    return (pd.read_parquet(d / "positions.parquet"), pd.read_parquet(d / "statics.parquet"),
            pd.read_parquet(d / "gaps.parquet"))


def load_dma(d: Path, days: int | None = None, thinned: bool = True):
    """Danish archive Parquet from ml/data/dma.py. Layout per its manifest; see dma_files()."""
    from ml.route.dma_io import load
    return load(d, days=days, thinned=thinned)


def time_split(ex: pd.DataFrame, test_frac: float):
    t_lo, t_hi = int(ex["as_of"].min()), int(ex["as_of"].max())
    test_start = t_hi - int((t_hi - t_lo) * test_frac)
    end = ex["as_of"] + ex["horizon_s"] * 1000
    train = ex[end <= test_start]
    test = ex[ex["as_of"] >= test_start]
    return train, test, test_start


def run(ex: pd.DataFrame, cfg: dict, test_frac: float = 0.25, reps: int = 400, out: Path | None = None) -> dict:
    train, test, test_start = time_split(ex, test_frac)
    t0 = time.time()
    base = RouteModel({**cfg, "model": "baseline"}).fit(train)
    model = RouteModel(cfg).fit(train)
    fit_s = time.time() - t0
    # evaluate only horizons the model was trained on; reappearance rows at any duration
    hs = model.horizons
    test = test[(test["truth"] == "reappear") | test["horizon_s"].isin(hs)]
    pm, pb = model.predict(test), base.predict(test)
    e = errors(test, pm, pb)
    rep = report(e, reps)
    rep["meta"] = {"rows_train": int(len(train)), "rows_test": int(len(test)), "test_start": test_start,
                   "test_to": int(test["as_of"].max()) if len(test) else None, "fit_seconds": round(fit_s, 1),
                   "n_fit": model.meta["n_fit"], "n_calib": model.meta["n_calib"], "model": model.version,
                   "baseline": base.version, "horizons_s": hs, "cfg": model.cfg,
                   "test_kinds": test.groupby(["kind", "truth"]).size().rename("n").reset_index().to_dict("records")}
    rep["baseline_coverage"] = {str(h): {"cover80": float(np.mean(g["base_err_m"] <= g["base_radius_m_80"])),
                                         "cover95": float(np.mean(g["base_err_m"] <= g["base_radius_m_95"]))}
                                for h, g in e[e["truth"] == "fixed"].groupby("horizon_s")}
    if out:
        model.meta["metrics"] = {"by_horizon": rep["by_horizon"], "reappear": {k: v["all"] for k, v in rep["reappear"].items()}}
        model.save(out)
        base.save(Path(str(out) + "-baseline"))
    return rep


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--source", choices=["tiger", "dma"], default="tiger")
    ap.add_argument("--data", type=Path)
    ap.add_argument("--days", type=int, default=None, help="dma: newest N days only")
    ap.add_argument("--cfg", type=Path, help="JSON config overriding model.DEFAULT_CFG")
    ap.add_argument("--horizons", default=None, help="comma list of hours, default 0.5,1,2,3,6,12,24 (as the data allows)")
    ap.add_argument("--step-min", type=int, default=20)
    ap.add_argument("--synthetic", type=int, default=5000)
    ap.add_argument("--test-frac", type=float, default=0.25)
    ap.add_argument("--examples", type=Path, help="cache: read examples here if present, else build and write")
    ap.add_argument("--out", type=Path, help="write the LightGBM artifact here (and the baseline to OUT-baseline)")
    ap.add_argument("--report", type=Path, help="write the JSON report here")
    a = ap.parse_args()
    cfg = json.loads(a.cfg.read_text()) if a.cfg else {}
    hs = [int(float(x) * 3600) for x in a.horizons.split(",")] if a.horizons else list(TRAIN_HORIZONS_S)
    t0 = time.time()
    if a.examples and a.examples.exists():
        ex = pd.read_parquet(a.examples)
    else:
        if a.source == "tiger":
            pos, st, gaps = load_tiger(a.data or DATA / "route" / "tiger")
        else:
            pos, st = load_dma(a.data or DATA / "dma", a.days)
            gaps = None
        ex = examples.build(pos, st, gaps, step_min=a.step_min, horizons=hs, n_synthetic=a.synthetic, source=a.source)
        if a.examples:
            ex.to_parquet(a.examples, index=False)
    print(f"examples: {len(ex)} rows in {time.time() - t0:.0f}s")
    span_h = (ex["as_of"].max() - ex["as_of"].min()) / 3.6e6
    usable = [h for h in hs if h / 3600 < span_h * (1 - a.test_frac) * 0.8]
    cfg = {"horizons_s": usable, **cfg}
    print(f"as_of span {span_h:.1f} h; horizons asked: {[h / 3600 for h in cfg['horizons_s']]} h")
    rep = run(ex, cfg, a.test_frac, out=a.out)
    print(table(rep))
    if a.report:
        a.report.parent.mkdir(parents=True, exist_ok=True)
        a.report.write_text(json.dumps(rep, indent=1, default=str))


if __name__ == "__main__":
    main()
