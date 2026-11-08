"""Recalibrate a route artifact's conformal radii on our own live feed, keeping its LightGBM heads.

    python -m ml.route.recalibrate --artifact DIR --data TIGER_EXPORT_DIR --out NEW_DIR [--calib-frac 0.6]

Why: a model trained on the Danish archive keeps its point skill on our worldwide feed but its radii are too narrow
there (the 8 Nov backtest: 80% circle held about 0.6). The points stay; only the radii are refitted.

How: route examples from a read-only Tiger export (`python -m ml.route.tiger --out DIR`), the same features,
baseline and truth as training. The older `--calib-frac` of the as_of span calibrates (truth must end before the
check window starts: embargo = horizon); the newer rest checks coverage before and after. Radii are split-conformal
per horizon and speed band (< 5, 5 to 12, >= 12 kn) with the finite-sample correction. A horizon the feed is too
short to calibrate (n < 50 in the calibration slice) keeps its Danish radius times the inflation (median of
new / old radius) of the longest horizon that could be calibrated, and is marked so in `recalibration`.

Writes NEW_DIR: the same model files, `model.json` with the new radii in `heads` and `all_heads`, a new `version`
(`<old>-cal<YYYYMMDDHHMM>`), a `recalibration` block, and `recalibration.json` (coverage before and after on the check
window, per horizon, plus reappearance after real gaps). The backend loads it like any artifact.
"""
from __future__ import annotations

import argparse
import json
import shutil
import time
from pathlib import Path

import numpy as np
import pandas as pd

from ml.route import metrics as M
from ml.route.model import MIN_BAND_N, RouteLGBM, band, conformal_q
from ml.route.examples import SPEED_EDGES_KN
from ml.route.geo import haversine_m
from ml.route.target import SPEC


def _errors(model, df, h):
    lat, lon = model._point(df, h)
    return haversine_m(lat, lon, df[f"truth_lat_{h}"].to_numpy(float), df[f"truth_lon_{h}"].to_numpy(float))


def _coverage(model, df) -> dict:
    s = M.score(df, model.predict(df))
    out = {}
    for h, g in s.groupby("horizon_s"):
        out[str(int(h))] = {"n": int(len(g)), "cover80": round(float(g["in80"].mean()), 3),
                            "cover95": round(float(g["in95"].mean()), 3),
                            "median_m": round(float(g["loss"].median()), 0),
                            "median_radius_m_80": round(float(g["radius_m_80"].median()), 0)}
    return out


def _reappear(model, df) -> dict:
    r = df[(df["reap_kind"] == "real") & df["reap_lat"].notna()]
    if r.empty:
        return {"n": 0}
    p = model.predict_at(r, r["reap_s"].to_numpy(float))
    err = haversine_m(p["pred_lat"].to_numpy(), p["pred_lon"].to_numpy(), r["reap_lat"].to_numpy(float),
                      r["reap_lon"].to_numpy(float))
    return {"n": int(len(r)), "cover80": round(float(np.mean(err <= p["radius_m_80"].to_numpy())), 3),
            "cover95": round(float(np.mean(err <= p["radius_m_95"].to_numpy())), 3)}


def recalibrate(model: RouteLGBM, ex: pd.DataFrame, calib_frac: float = 0.6) -> tuple[dict, dict]:
    lo, hi = int(ex["as_of"].min()), int(ex["as_of"].max())
    check_start = lo + int((hi - lo) * calib_frac)
    check = ex[ex["as_of"] >= check_start]
    before = {"fixed": _coverage(model, check), "real_gaps": _reappear(model, check)}
    new, info, ratio_last = {}, {}, None
    for h in model.horizons:                                # ascending
        col = f"truth_lat_{h}"
        cal = ex[(ex["as_of"] + h * 1000 <= check_start) & ex[col].notna()] if col in ex else ex.iloc[:0]
        old = model.radius[h]
        if len(cal) >= MIN_BAND_N:
            err = _errors(model, cal, h)
            b = band(cal["fix_sog"])
            pooled = (conformal_q(err, 0.8), conformal_q(err, 0.95))
            r80, r95, n = [], [], []
            for k in range(len(SPEED_EDGES_KN) + 1):
                e = err[b == k]
                ok = len(e) >= MIN_BAND_N
                r80.append(round(conformal_q(e, 0.8) if ok else pooled[0], 1))
                r95.append(round(conformal_q(e, 0.95) if ok else pooled[1], 1))
                n.append(int(len(e)))
            new[h] = {"r80": r80, "r95": r95, "n": n}
            ratio_last = (float(np.median(np.array(r80) / np.array(old["r80"]))),
                          float(np.median(np.array(r95) / np.array(old["r95"]))))
            info[str(h)] = {"how": "conformal on our feed", "n": int(len(cal)), "n_band": n,
                            "inflation80": round(ratio_last[0], 3), "inflation95": round(ratio_last[1], 3)}
        else:
            f80, f95 = ratio_last or (1.0, 1.0)
            new[h] = {"r80": [round(x * max(f80, 1.0), 1) for x in old["r80"]],
                      "r95": [round(x * max(f95, 1.0), 1) for x in old["r95"]], "n": []}
            info[str(h)] = {"how": "Danish radius x inflation of the longest calibrated horizon (never shrunk)",
                            "n": int(len(cal)), "inflation80": round(max(f80, 1.0), 3),
                            "inflation95": round(max(f95, 1.0), 3)}
    for h, r in new.items():
        model.radius[h] = r
    after = {"fixed": _coverage(model, check), "real_gaps": _reappear(model, check)}
    return info, {"check_start": check_start, "check_to": hi, "calib_from": lo, "before": before, "after": after}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--artifact", type=Path, required=True)
    ap.add_argument("--data", required=True, help="Tiger export dir (python -m ml.route.tiger --out DIR)")
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--calib-frac", type=float, default=0.6)
    a = ap.parse_args()
    t0 = time.time()
    model = RouteLGBM.load(a.artifact)
    ex = SPEC.load_examples({}, a.data)
    info, check = recalibrate(model, ex, a.calib_frac)
    spec = json.loads((a.artifact / "model.json").read_text())
    stamp = pd.Timestamp.now(tz="UTC").strftime("%Y%m%d%H%M")
    if a.out.exists():
        shutil.rmtree(a.out)
    shutil.copytree(a.artifact, a.out)
    for key in ("heads", "all_heads"):
        for h, s in spec.get(key, {}).items():
            r = model.radius[int(h)]
            s["radius_m_80"] = {"sog_edges_kn": list(SPEED_EDGES_KN), "r": r["r80"]}
            s["radius_m_95"] = {"sog_edges_kn": list(SPEED_EDGES_KN), "r": r["r95"]}
            s["radius_n"] = r.get("n", [])
    spec["parent_version"] = spec.get("version")
    spec["version"] = f"{spec.get('version', a.artifact.name)}-cal{stamp}"
    spec["recalibration"] = {"data": str(a.data), "examples": int(len(ex)), "per_horizon": info,
                             "check_start": check["check_start"], "created_at": stamp}
    (a.out / "model.json").write_text(json.dumps(spec, indent=1, default=str))
    (a.out / "recalibration.json").write_text(json.dumps({"per_horizon": info, **check}, indent=1, default=str))
    print(f"{len(ex)} examples from {a.data}; check window from {pd.Timestamp(check['check_start'], unit='ms')}")
    print(f"{'h':>6} {'how':>8} {'n_cal':>7} {'infl80':>7} | before cov80/95 | after cov80/95 (n)")
    for h in model.horizons:
        i, b, f = info[str(h)], check["before"]["fixed"].get(str(h), {}), check["after"]["fixed"].get(str(h), {})
        print(f"{h / 3600:>5g}h {'feed' if i['how'].startswith('conf') else 'scaled':>8} {i['n']:>7} "
              f"{i['inflation80']:>7.2f} | {b.get('cover80', float('nan')):.2f} / {b.get('cover95', float('nan')):.2f}"
              f"     | {f.get('cover80', float('nan')):.2f} / {f.get('cover95', float('nan')):.2f} ({f.get('n', 0)})")
    rb, ra = check["before"]["real_gaps"], check["after"]["real_gaps"]
    print(f"real gaps (n {ra['n']}): before {rb.get('cover80')}/{rb.get('cover95')}, after {ra.get('cover80')}/{ra.get('cover95')}")
    print(f"wrote {a.out} as {spec['version']} in {time.time() - t0:.0f}s")


if __name__ == "__main__":
    main()
