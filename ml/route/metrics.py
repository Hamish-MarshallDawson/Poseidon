"""Route metrics per the contract: median and p90 error (m) per horizon, coverage of the 80% and 95% radius, and
skill = 1 - median_err / median_err_baseline with a paired bootstrap 95% interval (cases resampled together, so
model and baseline see the same draw). Stratified by horizon, ship type, speed and case kind."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ml.route.geo import haversine_m
from ml.route.model import SPEED_BUCKETS_KN, speed_bucket

SPEED_LABELS = ["<5kn", "5-12kn", ">=12kn"]
MIN_STRATUM_N = 30


def errors(ex: pd.DataFrame, pred: pd.DataFrame, base: pd.DataFrame | None = None) -> pd.DataFrame:
    """Per-row model and baseline error. `base` is the baseline model's predict() output (for its radii); without
    it the baseline point in `pred` is used."""
    tl, tn = ex["true_lat"].to_numpy(float), ex["true_lon"].to_numpy(float)
    out = pd.DataFrame({
        "case_id": ex["case_id"].to_numpy(), "horizon_s": ex["horizon_s"].to_numpy(), "kind": ex["kind"].to_numpy(),
        "truth": ex["truth"].to_numpy(), "type_group": ex["type_group"].astype(str).to_numpy(),
        "speed": np.array(SPEED_LABELS)[speed_bucket(ex["last_sog"])],
        "gap_flag": ex["gap_flag"].to_numpy() if "gap_flag" in ex else None,
        "err_m": haversine_m(pred["pred_lat"].to_numpy(), pred["pred_lon"].to_numpy(), tl, tn),
        "base_err_m": haversine_m(pred["base_lat"].to_numpy(), pred["base_lon"].to_numpy(), tl, tn),
        "radius_m_80": pred["radius_m_80"].to_numpy(), "radius_m_95": pred["radius_m_95"].to_numpy(),
    }, index=ex.index)
    if base is not None:
        out["base_radius_m_80"], out["base_radius_m_95"] = base["radius_m_80"].to_numpy(), base["radius_m_95"].to_numpy()
    return out


def skill_ci(err: np.ndarray, base: np.ndarray, reps: int = 400, seed: int = 0) -> tuple[float, float, float]:
    """Point skill and paired bootstrap 95% interval."""
    err, base = np.asarray(err, float), np.asarray(base, float)
    n = len(err)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    s = 1 - np.median(err) / max(np.median(base), 1e-9)
    rng = np.random.default_rng(seed)
    m = min(n, 20000)                      # bootstrap on at most 20k cases (intervals scale as 1/sqrt(n) anyway)
    sub = rng.choice(n, m, replace=False) if m < n else np.arange(n)
    e, b = err[sub], base[sub]
    idx = rng.integers(0, m, size=(reps, m))
    boot = 1 - np.median(e[idx], axis=1) / np.maximum(np.median(b[idx], axis=1), 1e-9)
    if m < n:                              # widen to the full n: interval from m cases, centred on the full-n value
        half = (np.quantile(boot, 0.975) - np.quantile(boot, 0.025)) / 2 * np.sqrt(m / n)
        return float(s), float(s - half), float(s + half)
    return float(s), float(np.quantile(boot, 0.025)), float(np.quantile(boot, 0.975))


def summarise(e: pd.DataFrame, reps: int = 400) -> dict:
    if len(e) == 0:
        return {"n": 0}
    s, lo, hi = skill_ci(e["err_m"].to_numpy(), e["base_err_m"].to_numpy(), reps)
    r = {"n": int(len(e)), "cases": int(e["case_id"].nunique()),
         "median_m": float(np.median(e["err_m"])), "p90_m": float(np.quantile(e["err_m"], 0.9)),
         "base_median_m": float(np.median(e["base_err_m"])), "base_p90_m": float(np.quantile(e["base_err_m"], 0.9)),
         "skill": s, "skill_lo": lo, "skill_hi": hi,
         "cover80": float(np.mean(e["err_m"] <= e["radius_m_80"])),
         "cover95": float(np.mean(e["err_m"] <= e["radius_m_95"])),
         "median_radius_m_80": float(np.nanmedian(e["radius_m_80"])),
         "median_radius_m_95": float(np.nanmedian(e["radius_m_95"]))}
    if "base_radius_m_80" in e:
        r["base_cover80"] = float(np.mean(e["base_err_m"] <= e["base_radius_m_80"]))
        r["base_cover95"] = float(np.mean(e["base_err_m"] <= e["base_radius_m_95"]))
    return r


def report(e: pd.DataFrame, reps: int = 400) -> dict:
    """Headline per horizon on fixed-horizon rows, strata per horizon, and the reappearance sets."""
    fixed = e[e["truth"] == "fixed"]
    out: dict = {"by_horizon": {}, "strata": {}, "reappear": {}}
    for h, g in fixed.groupby("horizon_s"):
        out["by_horizon"][str(int(h))] = summarise(g, reps)
        st = {}
        for col in ("type_group", "speed", "kind"):
            st[col] = {str(k): summarise(gg, 200) for k, gg in g.groupby(col) if len(gg) >= MIN_STRATUM_N}
        out["strata"][str(int(h))] = st
    rp = e[e["truth"] == "reappear"]
    for kind, g in rp.groupby("kind"):
        d = {"all": summarise(g, reps)}
        hb = pd.cut(g["horizon_s"] / 3600, [0, 1, 2, 4, 8, 1e9], labels=["<1h", "1-2h", "2-4h", "4-8h", ">=8h"])
        d["by_duration"] = {str(k): summarise(gg, 200) for k, gg in g.groupby(hb, observed=True)
                            if len(gg) >= MIN_STRATUM_N}
        if kind == "real_gap":
            d["by_flag"] = {str(k): summarise(gg, 200) for k, gg in g.groupby("gap_flag") if len(gg) >= MIN_STRATUM_N}
        out["reappear"][kind] = d
    return out


def table(rep: dict) -> str:
    """Plain-text headline table."""
    lines = [f"{'horizon':>8} {'n':>7} {'median_m':>9} {'base_m':>9} {'p90_m':>9} {'skill':>7} {'95% CI':>17} "
             f"{'cov80':>6} {'cov95':>6}"]
    rows = [(f"{int(h) / 3600:g}h", r) for h, r in rep["by_horizon"].items()]
    rows += [(f"{k}", v["all"]) for k, v in rep["reappear"].items()]
    for name, r in rows:
        if not r.get("n"):
            continue
        lines.append(f"{name:>8} {r['n']:>7} {r['median_m']:>9.0f} {r['base_median_m']:>9.0f} {r['p90_m']:>9.0f} "
                     f"{r['skill']:>7.3f} [{r['skill_lo']:>6.3f}, {r['skill_hi']:>6.3f}] "
                     f"{r['cover80']:>6.2f} {r['cover95']:>6.2f}")
    return "\n".join(lines)
