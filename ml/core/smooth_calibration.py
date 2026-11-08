"""Smooth, strictly increasing calibration maps for a go-dark champion, chosen on our own graded ledger.

    ml/.venv/bin/python -m ml.core.smooth_calibration \
        --artifact /home/aiden/data/poseidon/models/godark-lgbm-20261108T051156 \
        --compare /home/aiden/data/poseidon/recal/godark-lgbm-20261108T051156-cal1 \
        --out-dir /home/aiden/data/poseidon/recal [--write]

Why: the isotonic map in `heads.<h>.calibration` is a staircase (flat runs joined by near-vertical steps), so a
few dozen raw-score ranges collapse to one probability each and the watchlist ties (hundreds of ships at exactly the
same dark_6h figure). This module re-derives each graded row's raw LightGBM score from the stored feature snapshot
(`scores.features`, following `same_as` to the dark_6h row) through the backend's own `GodarkModel` boosters, then
fits candidate maps on the older half of the graded rows (split at a snapshot boundary, by made_at) and compares them
on the newer half: log loss, Brier, AUC, distinct values, top-10% hit rate. Candidates, each written as the same
piecewise-linear `{"x": [...], "y": [...]}` the backend reads (`dvm.predict.artifact.calibrate`):

- `platt`: p = expit(a + b * logit(raw)), b > 0, sampled on a dense logit grid (strictly increasing);
- `iso_mid`: isotonic regression on the older half, each block's (mean raw, rate) joined piecewise-linearly;
- `current_mid_shift`: the current map's step midpoints joined, then a logit shift fitted on the older half.

Baselines on the same newer half: the artifact's own map (`current`), the map of `--compare` (the cal1 shift, which
was fitted on graded rows that include the newer half, so it is optimistic), and `current_shift` (the cal1 method
refitted on the older half only, the fair version of it). With --write, the winner (by newer-half log loss, among
the smooth candidates that also do not lose on Brier) is refitted on all graded rows and written as
`<version>-smooth1` under --out-dir. Tiger is opened read-only. Nothing goes live here: champions.json is not touched.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import math
import os
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd

import ml  # noqa: F401  (backend/ on sys.path)
from dvm.predict import artifact as A
from dvm.predict import features as F

EPS = 1e-6
HEAD_TARGET = {"3600": "dark_1h", "21600": "dark_6h", "86400": "dark_24h"}
GRID_N = 161                 # Platt map breakpoints, uniform in logit(raw)
GRID_LO, GRID_HI = 1e-5, 1 - 1e-5
Y_FLOOR = 1e-4               # no smooth map says 0 or 1


def _logit(p):
    p = np.clip(np.asarray(p, float), EPS, 1 - EPS)
    return np.log(p / (1 - p))


def _expit(x):
    return 1 / (1 + np.exp(-np.asarray(x, float)))


# ---------------------------------------------------------------- maps

def apply_map(raw, cal: dict) -> np.ndarray:
    """dvm.predict.artifact.calibrate over an array (the backend's exact function, so ties behave as live)."""
    return np.array([A.calibrate(float(r), cal) for r in np.asarray(raw, float)])


def strictly_increasing(cal: dict) -> bool:
    x, y = np.asarray(cal["x"]), np.asarray(cal["y"])
    return bool(len(x) >= 2 and np.all(np.diff(x) > 0) and np.all(np.diff(y) > 0))


def _nll(p, y) -> float:
    p = np.clip(p, EPS, 1 - EPS)
    return float(-np.mean(y * np.log(p) + (1 - y) * np.log(1 - p)))


def fit_shift(p, y) -> float:
    from scipy.optimize import minimize_scalar
    lp = _logit(p)
    return float(minimize_scalar(lambda s: _nll(_expit(lp + s), y), bounds=(-5, 5), method="bounded").x)


def fit_platt(raw, y) -> tuple[float, float]:
    """(a, b) of p = expit(a + b * logit(raw)) by maximum likelihood, with b kept positive (an increasing map)."""
    from scipy.optimize import minimize
    z, y = _logit(raw), np.asarray(y, float)

    def f(t):
        a, lb = t
        q = np.clip(_expit(a + math.exp(lb) * z), EPS, 1 - EPS)
        return -np.sum(y * np.log(q) + (1 - y) * np.log(1 - q))
    r = minimize(f, x0=[float(_logit(y.mean() or EPS)) - float(z.mean()), 0.0], method="Nelder-Mead",
                 options={"xatol": 1e-6, "fatol": 1e-8, "maxiter": 4000})
    return float(r.x[0]), float(math.exp(r.x[1]))


def platt_map(a: float, b: float) -> dict:
    z = np.linspace(_logit(GRID_LO), _logit(GRID_HI), GRID_N)
    y = np.clip(_expit(a + b * z), Y_FLOOR, 1 - Y_FLOOR)
    return _clean({"x": _expit(z), "y": y})


def iso_mid_map(raw, y) -> dict:
    """Isotonic regression, then each block's (mean raw score, fitted rate) joined into a piecewise-linear map."""
    from sklearn.isotonic import IsotonicRegression
    raw, y = np.asarray(raw, float), np.asarray(y, float)
    fit = IsotonicRegression(out_of_bounds="clip", y_min=0, y_max=1).fit_transform(raw, y)
    d = pd.DataFrame({"raw": raw, "fit": fit}).groupby("fit", sort=True)["raw"].mean().reset_index()
    d = d.sort_values("raw")
    return _clean({"x": d["raw"].to_numpy(), "y": np.clip(d["fit"].to_numpy(), Y_FLOOR, 1 - Y_FLOOR)})


def step_midpoints(cal: dict) -> dict:
    """A staircase map (flat runs x[i]..x[i+1] at one y) as its runs' midpoints, one point per distinct y."""
    x, y = np.asarray(cal["x"], float), np.asarray(cal["y"], float)
    pts: dict[float, list[float]] = {}
    for i in range(len(x)):
        pts.setdefault(float(y[i]), []).append(float(x[i]))
    ys = sorted(pts)
    return {"x": np.array([(min(pts[v]) + max(pts[v])) / 2 for v in ys]), "y": np.array(ys)}


def shifted(cal: dict, s: float) -> dict:
    return _clean({"x": np.asarray(cal["x"], float),
                   "y": np.clip(_expit(_logit(cal["y"]) + s), Y_FLOOR, 1 - Y_FLOOR)})


def _clean(cal: dict) -> dict:
    """Plain floats, x and y both strictly increasing (points that would not be are dropped)."""
    x, y = np.asarray(cal["x"], float), np.asarray(cal["y"], float)
    keep_x, keep_y = [], []
    for a, b in zip(x, y):
        if not keep_x or (a > keep_x[-1] and b > keep_y[-1]):
            keep_x.append(float(a))
            keep_y.append(float(b))
    return {"x": keep_x, "y": keep_y}


# ---------------------------------------------------------------- evaluation

def top_hit_rate(p, y, frac: float = 0.1) -> float:
    """Hit rate among the top `frac` of rows by p; a tie group straddling the cut counts pro rata (random order)."""
    p, y = np.asarray(p, float), np.asarray(y, float)
    k = max(1, int(round(frac * len(p))))
    t = np.sort(p)[::-1][k - 1]
    above, tie = p > t, p == t
    need = k - int(above.sum())
    return float((y[above].sum() + y[tie].sum() * need / tie.sum()) / k)


def metrics(p, y) -> dict:
    from sklearn.metrics import roc_auc_score
    p, y = np.asarray(p, float), np.asarray(y, int)
    vals, counts = np.unique(p, return_counts=True)
    return {"n": int(len(p)), "positives": int(y.sum()), "log_loss": round(_nll(p, y), 5),
            "brier": round(float(np.mean((p - y) ** 2)), 6),
            "auc": round(float(roc_auc_score(y, p)), 4) if 0 < y.sum() < len(y) else None,
            "distinct": int(len(vals)), "largest_tie": int(counts.max()),
            "top10_hit": round(top_hit_rate(p, y), 4), "mean_p": round(float(p.mean()), 5),
            "hit_rate": round(float(y.mean()), 5)}


def snapshot_halves(d: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Older and newer half by made_at, cut at the snapshot boundary closest to half the rows (a snapshot is never
    split between fit and check)."""
    counts = d.groupby("made_at").size().sort_index()
    cum = counts.cumsum().to_numpy()
    if len(counts) < 2:
        raise ValueError("need at least two snapshots for a time split")
    i = int(np.argmin(np.abs(cum[:-1] - len(d) / 2)))
    cut = counts.index[i]
    return d[d.made_at <= cut], d[d.made_at > cut]


def candidates(fit_raw, fit_y, fit_p_current, current_cal: dict) -> dict:
    """{name: map} fitted on one slice. `current_shift` is the cal1 method (a logit shift of the staircase)."""
    a, b = fit_platt(fit_raw, fit_y)
    mid = step_midpoints(current_cal)
    s_mid = fit_shift(apply_map(fit_raw, _clean(mid)), fit_y)
    return {"platt": platt_map(a, b) | {"params": {"a": round(a, 5), "b": round(b, 5)}},
            "iso_mid": iso_mid_map(fit_raw, fit_y),
            "current_mid_shift": shifted(mid, s_mid) | {"params": {"shift": round(s_mid, 4)}},
            "current_shift": {"x": list(map(float, current_cal["x"])),
                              "y": [float(v) for v in np.maximum.accumulate(
                                  _expit(_logit(current_cal["y"]) + fit_shift(fit_p_current, fit_y)))]}}


SMOOTH = ("platt", "iso_mid", "current_mid_shift")


def evaluate_head(d: pd.DataFrame, current_cal: dict, compare_cal: dict | None) -> dict:
    """Fit on the older half, check on the newer half. `d` has made_at, raw, label."""
    old, new = snapshot_halves(d)
    yo, yn = old.label.astype(int).to_numpy(), new.label.astype(int).to_numpy()
    maps = candidates(old.raw.to_numpy(), yo, apply_map(old.raw, current_cal), current_cal)
    maps["current"] = current_cal
    if compare_cal:
        maps["compare"] = compare_cal
    res = {k: metrics(apply_map(new.raw, {"x": m["x"], "y": m["y"]}), yn) | {
        "strictly_increasing": strictly_increasing(m), "breakpoints": len(m["x"])} for k, m in maps.items()}
    for k in res:
        if "params" in maps[k]:
            res[k]["params"] = maps[k]["params"]
    ok = [k for k in SMOOTH if res[k]["strictly_increasing"] and res[k]["brier"] <= res["current_shift"]["brier"]]
    winner = min(ok, key=lambda k: res[k]["log_loss"]) if ok else None
    beats = bool(winner and res[winner]["log_loss"] < min(res["current"]["log_loss"], res["current_shift"]["log_loss"]))
    return {"split": {"older": [int(old.made_at.min()), int(old.made_at.max()), len(old), int(yo.sum())],
                      "newer": [int(new.made_at.min()), int(new.made_at.max()), len(new), int(yn.sum())]},
            "newer_half": res, "winner": winner, "winner_beats_current": beats}


# ---------------------------------------------------------------- data

GRADED_SQL = """
SELECT s.made_at, s.mmsi, o.target, s.horizon_s, s.p, o.label, s.mode,
       COALESCE(f.features, s.features)::text AS features
FROM outcomes o JOIN scores s ON s.id = o.score_id
LEFT JOIN scores f ON s.features ? 'same_as' AND f.id = s.features->>'same_as'
WHERE o.label IS NOT NULL AND s.model_version = $1"""

LATEST_SQL = """
SELECT s.mmsi, s.features::text AS features FROM scores s
WHERE s.target = 'dark_6h' AND s.model_version LIKE $1 || '%'
  AND s.made_at = (SELECT max(made_at) FROM scores WHERE target = 'dark_6h' AND model_version LIKE $1 || '%')"""


async def _fetch(url: str, version: str):
    import asyncpg
    con = await asyncpg.connect(url, server_settings={"default_transaction_read_only": "on",
                                                      "statement_timeout": "300000"})
    try:
        graded = await con.fetch(GRADED_SQL, version)
        latest = await con.fetch(LATEST_SQL, version)
    finally:
        await con.close()
    g = pd.DataFrame([dict(r) for r in graded])
    g["features"] = g["features"].map(json.loads)
    lat = pd.DataFrame([dict(r) for r in latest])
    if len(lat):
        lat["features"] = lat["features"].map(json.loads)
    return g, lat


def raw_scores(model: A.GodarkModel, feats: list[dict], h: int) -> np.ndarray:
    """The booster's own output for each snapshot, as GodarkModel.predict computes it before calibration."""
    x = np.array([F.vector(f, model.features) for f in feats], dtype=float)
    return model.heads[h][0].predict(x)


# ---------------------------------------------------------------- artifact

def write_artifact(src: Path, dst: Path, maps: dict, report: dict, previous: dict | None) -> None:
    shutil.copytree(src, dst)
    m = json.loads((dst / "model.json").read_text())
    parent = m["version"]
    for hs, cal in maps.items():
        m["heads"][hs]["calibration"] = {"x": cal["x"], "y": cal["y"]}
    m["version"] = dst.name
    m["recalibration"] = {
        "parent": parent, "method": "smooth strictly increasing calibration (ml/core/smooth_calibration.py)",
        "heads": {hs: {"target": HEAD_TARGET.get(hs), "method": cal["method"], "params": cal.get("params"),
                       "fit_rows": cal["fit_rows"]} for hs, cal in maps.items()},
        "check": report, "previous": previous,
        "note": "replaces the isotonic staircase so scores keep their resolution; ranking follows the raw score"}
    (dst / "model.json").write_text(json.dumps(m, indent=1))


def run(artifact: Path, compare: Path | None, url: str, out_dir: Path, write: bool, log=print) -> dict:
    model = A.load(artifact)
    meta = json.loads((artifact / "model.json").read_text())
    cmeta = json.loads((compare / "model.json").read_text()) if compare else None
    graded, latest = asyncio.run(_fetch(url, model.version))
    out: dict = {"version": model.version, "graded_rows": len(graded), "heads": {}}
    final: dict = {}
    for h in model.horizons_s:
        hs, tg = str(h), HEAD_TARGET.get(str(h))
        d = graded[graded.target == tg].copy()
        if d.empty:
            continue
        d["raw"] = raw_scores(model, list(d.features), h)
        cur = meta["heads"][hs]["calibration"]
        # the recomputed raw score must reproduce what the ledger stored for this exact model version
        repro = float(np.max(np.abs(apply_map(d.raw, cur) - d.p.to_numpy())))
        ev = evaluate_head(d, cur, cmeta["heads"][hs]["calibration"] if cmeta else None)
        ev["reproduced_stored_p_max_abs_err"] = repro
        ev["modes"] = d["mode"].value_counts().to_dict()
        if len(latest):
            lraw = raw_scores(model, list(latest.features), h)
            ev["latest_snapshot"] = {"ships": len(latest), "distinct": {
                "current": int(len(np.unique(apply_map(lraw, cur)))),
                **({"compare": int(len(np.unique(apply_map(lraw, cmeta["heads"][hs]["calibration"]))))}
                   if cmeta else {})}}
        if ev["winner"]:
            y_all = d.label.astype(int).to_numpy()
            fm = candidates(d.raw.to_numpy(), y_all, apply_map(d.raw, cur), cur)[ev["winner"]]
            final[hs] = fm | {"method": ev["winner"], "fit_rows": f"{len(d)} graded rows, {int(y_all.sum())} positive"}
            if len(latest):
                fl = apply_map(lraw, fm)
                ev["latest_snapshot"]["distinct"]["smooth_final"] = int(len(np.unique(fl)))
                ev["latest_snapshot"]["largest_tie_smooth_final"] = int(np.unique(fl, return_counts=True)[1].max())
        out["heads"][hs] = ev
        log(f"{tg}: winner {ev['winner']}, beats current {ev['winner_beats_current']}")
    if write and final:
        dst = out_dir / f"{meta['version']}-smooth1"
        if dst.exists():
            raise FileExistsError(dst)
        # heads without a winner keep the artifact's map
        write_artifact(artifact, dst, final, out["heads"], (cmeta or {}).get("recalibration"))
        out["written"] = str(dst)
    return out


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python -m ml.core.smooth_calibration", description=__doc__.split("\n\n")[0])
    ap.add_argument("--artifact", type=Path, required=True)
    ap.add_argument("--compare", type=Path, help="another artifact of the same model (e.g. its -cal1) to compare")
    ap.add_argument("--out-dir", type=Path, default=Path("/home/aiden/data/poseidon/recal"))
    ap.add_argument("--write", action="store_true")
    a = ap.parse_args(argv)
    from ml.core import env  # noqa: F401  (loads the repo .env)
    print(json.dumps(run(a.artifact, a.compare, os.environ["TIGER_DATABASE_URL"], a.out_dir, a.write,
                         log=lambda m: print(m, file=sys.stderr)),
                     indent=1, default=str))


if __name__ == "__main__":
    main()
