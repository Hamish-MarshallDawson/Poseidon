"""Route metrics per the contract: median and p90 error (m) per horizon, coverage of the 80% and 95% radius, and
skill = 1 - median_err / median_err_baseline with a paired bootstrap 95% interval (cases resampled together, so the
model and the baseline see the same draw). Stratified by horizon, ship type, speed and case kind; plus the
reappearance sets (synthetic dead zones and our own closed gaps), graded where the ship came back."""
from __future__ import annotations

import numpy as np
import pandas as pd

from ml.route.geo import haversine_m

MIN_STRATUM_N = 30


def score(examples: pd.DataFrame, preds: pd.DataFrame, strata=("type_group", "speed_class", "kind")) -> pd.DataFrame:
    """Long frame: case_id, mmsi, as_of, horizon_s, loss (error m), in80, in95, strata. Cases without truth at a
    horizon are left out."""
    ex = examples.set_index("case_id")
    out = []
    for h, p in preds.groupby("horizon_s"):
        h = int(h)
        if f"truth_lat_{h}" not in ex:
            continue
        j = p.set_index("case_id").join(ex[["mmsi", "as_of", f"truth_lat_{h}", f"truth_lon_{h}", *strata]], how="inner")
        j = j[j[f"truth_lat_{h}"].notna()]
        err = haversine_m(j["pred_lat"].to_numpy(), j["pred_lon"].to_numpy(), j[f"truth_lat_{h}"].to_numpy(),
                          j[f"truth_lon_{h}"].to_numpy())
        out.append(pd.DataFrame({"case_id": j.index.to_numpy(), "mmsi": j["mmsi"].to_numpy(),
                                 "as_of": j["as_of"].to_numpy(), "horizon_s": h, "loss": err,
                                 "in80": err <= j["radius_m_80"].to_numpy(), "in95": err <= j["radius_m_95"].to_numpy(),
                                 "radius_m_80": j["radius_m_80"].to_numpy(), "radius_m_95": j["radius_m_95"].to_numpy(),
                                 **{s: j[s].to_numpy() for s in strata}}))
    cols = ["case_id", "mmsi", "as_of", "horizon_s", "loss", "in80", "in95", "radius_m_80", "radius_m_95", *strata]
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=cols)


def skill_ci(err: np.ndarray, base: np.ndarray, reps: int = 400, seed: int = 0) -> tuple[float, float, float]:
    """Point skill and paired bootstrap 95% interval (at most 20k cases resampled; the interval is then narrowed
    by sqrt(m / n) to the full n)."""
    err, base = np.asarray(err, float), np.asarray(base, float)
    n = len(err)
    if n == 0:
        return float("nan"), float("nan"), float("nan")
    s = 1 - np.median(err) / max(np.median(base), 1e-9)
    rng = np.random.default_rng(seed)
    m = min(n, 20000)
    sub = rng.choice(n, m, replace=False) if m < n else np.arange(n)
    e, b = err[sub], base[sub]
    idx = rng.integers(0, m, size=(reps, m))
    boot = 1 - np.median(e[idx], axis=1) / np.maximum(np.median(b[idx], axis=1), 1e-9)
    lo, hi = np.quantile(boot, 0.025), np.quantile(boot, 0.975)
    if m < n:
        half = (hi - lo) / 2 * np.sqrt(m / n)
        return float(s), float(s - half), float(s + half)
    return float(s), float(lo), float(hi)


def summarise(g: pd.DataFrame, reps: int = 400) -> dict:
    """g: paired rows with loss (model) and base_loss (baseline)."""
    if len(g) == 0:
        return {"n": 0}
    s, lo, hi = skill_ci(g["loss"].to_numpy(), g["base_loss"].to_numpy(), reps)
    r = {"n": int(len(g)), "median_m": float(np.median(g["loss"])), "p90_m": float(np.quantile(g["loss"], 0.9)),
         "base_median_m": float(np.median(g["base_loss"])), "base_p90_m": float(np.quantile(g["base_loss"], 0.9)),
         "skill": s, "skill_lo": lo, "skill_hi": hi, "cover80": float(g["in80"].mean()),
         "cover95": float(g["in95"].mean()), "median_radius_m_80": float(np.median(g["radius_m_80"])),
         "median_radius_m_95": float(np.median(g["radius_m_95"]))}
    if "base_in80" in g:
        r["base_cover80"], r["base_cover95"] = float(g["base_in80"].mean()), float(g["base_in95"].mean())
    return r


def paired(model_scored: pd.DataFrame, base_scored: pd.DataFrame) -> pd.DataFrame:
    b = base_scored[["case_id", "horizon_s", "loss", "in80", "in95"]].rename(
        columns={"loss": "base_loss", "in80": "base_in80", "in95": "base_in95"})
    return model_scored.merge(b, on=["case_id", "horizon_s"], how="inner")


def reappear_frame(model, base, test: pd.DataFrame) -> pd.DataFrame:
    """Grade predictions at each case's reappearance time (synthetic dead zones and real gaps)."""
    r = test[test["reap_kind"].notna() & test["reap_lat"].notna()]
    if r.empty:
        return pd.DataFrame()
    pm, pb = model.predict_at(r, r["reap_s"].to_numpy(float)), base.predict_at(r, r["reap_s"].to_numpy(float))
    tl, tn = r["reap_lat"].to_numpy(float), r["reap_lon"].to_numpy(float)
    err = haversine_m(pm["pred_lat"].to_numpy(), pm["pred_lon"].to_numpy(), tl, tn)
    berr = haversine_m(pb["pred_lat"].to_numpy(), pb["pred_lon"].to_numpy(), tl, tn)
    return pd.DataFrame({"case_id": r["case_id"].to_numpy(), "reap_kind": r["reap_kind"].to_numpy(),
                         "reap_s": r["reap_s"].to_numpy(), "gap_flag": r["gap_flag"].to_numpy(), "loss": err,
                         "base_loss": berr, "in80": err <= pm["radius_m_80"].to_numpy(),
                         "in95": err <= pm["radius_m_95"].to_numpy(), "radius_m_80": pm["radius_m_80"].to_numpy(),
                         "radius_m_95": pm["radius_m_95"].to_numpy(), "base_in80": berr <= pb["radius_m_80"].to_numpy(),
                         "base_in95": berr <= pb["radius_m_95"].to_numpy()})


def report(pairs: pd.DataFrame, reap: pd.DataFrame | None = None, reps: int = 400,
           strata=("type_group", "speed_class", "kind")) -> dict:
    out: dict = {"by_horizon": {}, "strata": {}, "reappear": {}}
    for h, g in pairs.groupby("horizon_s"):
        out["by_horizon"][str(int(h))] = summarise(g, reps)
        out["strata"][str(int(h))] = {c: {str(k): summarise(gg, 200) for k, gg in g.groupby(c)
                                          if len(gg) >= MIN_STRATUM_N} for c in strata if c in g}
    if reap is not None and len(reap):
        for kind, g in reap.groupby("reap_kind"):
            d = {"all": summarise(g, reps)}
            hb = pd.cut(g["reap_s"] / 3600, [0, 1, 2, 4, 8, 1e9], labels=["<1h", "1-2h", "2-4h", "4-8h", ">=8h"])
            d["by_duration"] = {str(k): summarise(gg, 200) for k, gg in g.groupby(hb, observed=True)
                                if len(gg) >= MIN_STRATUM_N}
            if kind == "real":
                d["by_flag"] = {str(k): summarise(gg, 200) for k, gg in g.groupby("gap_flag") if len(gg) >= MIN_STRATUM_N}
            out["reappear"][str(kind)] = d
    return out


def table(rep: dict) -> str:
    lines = [f"{'horizon':>10} {'n':>7} {'median_m':>9} {'base_m':>9} {'p90_m':>9} {'skill':>7} {'95% CI':>17} "
             f"{'cov80':>6} {'cov95':>6}"]
    rows = [(f"{int(h) / 3600:g}h", r) for h, r in rep["by_horizon"].items()]
    rows += [(f"{k} gaps", v["all"]) for k, v in rep["reappear"].items()]
    for name, r in rows:
        if r.get("n"):
            lines.append(f"{name:>10} {r['n']:>7} {r['median_m']:>9.0f} {r['base_median_m']:>9.0f} {r['p90_m']:>9.0f} "
                         f"{r['skill']:>7.3f} [{r['skill_lo']:>6.3f}, {r['skill_hi']:>6.3f}] "
                         f"{r['cover80']:>6.2f} {r['cover95']:>6.2f}")
    return "\n".join(lines)
