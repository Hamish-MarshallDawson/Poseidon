"""Route examples: "here at as_of, where at as_of + h", one row per (case, horizon).

Three kinds of case, in the `kind` column:
- `track`: a moving ship on a regular grid of as_of times along a complete track;
- `synthetic_gap`: a moving Class A ship whose track is hidden for a random duration after as_of (drawn from our
  detector's closed-gap durations), graded on where it reappears (`horizon_s` = time to the first fix after the hidden
  stretch). Labelled synthetic: nobody switched anything off;
- `real_gap`: a closed gap from our Tiger `gaps` table: as_of = the last fix before the silence, graded on the fix
  that closed it, plus any fixed horizon that has a fix after the ship came back.

Features come only from `features.track_features` (history up to as_of). Truth is looked up separately, here, and
never feeds a feature.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

from ml.route import TRAIN_HORIZONS_S as HORIZONS_S
from ml.route.features import sort_keys, track_features
from ml.route.geo import KN_TO_MS, haversine_m

TRUTH_TOL_S = 300                 # truth at as_of + h must be within 5 min of a fix
GAP_MEDIAN_S, GAP_SIGMA = 69 * 60, 0.74   # lognormal fit to closed deliberate gaps (median 69 min, p90 178 min)


def speed_gate(track: pd.DataFrame, max_kn: float = 40.0) -> pd.DataFrame:
    """Drop fixes that imply more than max_kn from the previous fix of the same ship (bad positions, spoofed jumps).
    One pass: a single bad fix is dropped; the fix after it is then compared with the one before it next time."""
    tr = track.sort_values(["mmsi", "ts"], kind="stable").reset_index(drop=True)
    for _ in range(3):
        same = tr["mmsi"].to_numpy()[1:] == tr["mmsi"].to_numpy()[:-1]
        d = haversine_m(tr["lat"].to_numpy()[:-1], tr["lon"].to_numpy()[:-1], tr["lat"].to_numpy()[1:],
                        tr["lon"].to_numpy()[1:])
        dt = np.diff(tr["ts"].to_numpy()) / 1000.0
        fast = same & (d > 500) & (d / np.maximum(dt, 1.0) > max_kn * KN_TO_MS)
        if not fast.any():
            break
        tr = tr.loc[~np.r_[False, fast]].reset_index(drop=True)
    return tr


def grid_cases(track: pd.DataFrame, step_min: int = 20, min_sog_kn: float = 1.0, seed: int = 0) -> pd.DataFrame:
    """One case per ship per `step_min` bucket, at the first fix in the bucket, if the ship is moving there."""
    tr = track[["mmsi", "ts", "sog_kn", "nav_status", "cls"]]
    b = tr["ts"] // (step_min * 60_000)
    first = tr.loc[~pd.DataFrame({"m": tr["mmsi"].to_numpy(), "b": b.to_numpy()}).duplicated().to_numpy()]
    moving = (first["sog_kn"] >= min_sog_kn) & ~first["nav_status"].isin([1, 5])
    c = first.loc[moving, ["mmsi", "ts", "cls"]].rename(columns={"ts": "as_of"}).reset_index(drop=True)
    c["kind"] = "track"
    return c


def truth_at(track: pd.DataFrame, mmsi: np.ndarray, when: np.ndarray, tol_s: int = TRUTH_TOL_S):
    """Position of each ship at `when` (ms): interpolated between the bracketing fixes when both are within tol_s,
    else the nearer fix if within tol_s, else NaN."""
    keys, ts, tk, qk, _, _ = sort_keys(track, mmsi, when)
    la, lo = track["lat"].to_numpy(float), track["lon"].to_numpy(float)
    k = np.searchsorted(tk, qk, side="left")                   # first fix at or after `when`
    n = len(ts)
    kk, kp = np.clip(k, 0, n - 1), np.clip(k - 1, 0, n - 1)
    after_ok = (k < n) & (keys[kk] == mmsi) & (ts[kk] - when <= tol_s * 1000)
    before_ok = (k > 0) & (keys[kp] == mmsi) & (when - ts[kp] <= tol_s * 1000)
    lat, lon = np.full(len(when), np.nan), np.full(len(when), np.nan)
    both = after_ok & before_ok
    w = np.where(both, (when - ts[kp]) / np.maximum(ts[kk] - ts[kp], 1), 0.0)
    lat = np.where(both, la[kp] + w * (la[kk] - la[kp]), lat)
    dlon = (lo[kk] - lo[kp] + 540) % 360 - 180
    lon = np.where(both, (lo[kp] + w * dlon + 540) % 360 - 180, lon)
    only_a = after_ok & ~before_ok
    only_b = before_ok & ~after_ok
    lat = np.where(only_a, la[kk], np.where(only_b, la[kp], lat))
    lon = np.where(only_a, lo[kk], np.where(only_b, lo[kp], lon))
    return lat, lon


def first_fix_after(track: pd.DataFrame, mmsi: np.ndarray, when: np.ndarray):
    keys, ts, tk, qk, _, _ = sort_keys(track, mmsi, when)
    la, lo = track["lat"].to_numpy(float), track["lon"].to_numpy(float)
    k = np.searchsorted(tk, qk, side="left")
    kk = np.clip(k, 0, len(ts) - 1)
    ok = (k < len(ts)) & (keys[kk] == mmsi)
    return np.where(ok, ts[kk], -1), np.where(ok, la[kk], np.nan), np.where(ok, lo[kk], np.nan)


def expand_horizons(feat: pd.DataFrame, track: pd.DataFrame, horizons=HORIZONS_S) -> pd.DataFrame:
    """Long format: one row per case and fixed horizon with a truth fix."""
    parts = []
    for h in horizons:
        p = feat.copy()
        p["horizon_s"] = int(h)
        p["true_lat"], p["true_lon"] = truth_at(track, p["mmsi"].to_numpy(np.int64), p["as_of"].to_numpy(np.int64) + h * 1000)
        parts.append(p[p["true_lat"].notna()])
    return pd.concat(parts, ignore_index=True)


def synthetic_gap_cases(feat: pd.DataFrame, track: pd.DataFrame, n: int, seed: int = 0) -> pd.DataFrame:
    """Hide a lognormal-length stretch after as_of for n moving Class A cases; truth = the first fix after it."""
    rng = np.random.default_rng(seed)
    pool = feat[(feat["is_class_a"] == 1) & (feat["kind"] == "track")]
    if pool.empty:
        return pool.assign(horizon_s=pd.Series(dtype=int), true_lat=pd.Series(dtype=float), true_lon=pd.Series(dtype=float))
    c = pool.sample(min(n, len(pool)), random_state=seed).copy()
    dur = np.clip(rng.lognormal(np.log(GAP_MEDIAN_S), GAP_SIGMA, len(c)), 1800, 24 * 3600).astype(np.int64)
    t, la, lo = first_fix_after(track, c["mmsi"].to_numpy(np.int64), c["as_of"].to_numpy(np.int64) + dur * 1000)
    c["horizon_s"] = (t - c["as_of"].to_numpy(np.int64)) // 1000
    c["true_lat"], c["true_lon"] = la, lo
    c["kind"] = "synthetic_gap"
    c["case_id"] = c["case_id"] + "-syn"
    ok = (t > 0) & (c["horizon_s"] <= dur + 600)               # reappeared within 10 min of the hidden stretch's end
    return c[ok].reset_index(drop=True)


def real_gap_cases(gaps: pd.DataFrame, track: pd.DataFrame, statics=None, horizons=HORIZONS_S) -> pd.DataFrame:
    """Closed gaps from our detector: reappearance truth, plus fixed horizons once the ship is back in our feed."""
    g = gaps[gaps["state"] == "closed"].drop_duplicates("id")
    cases = pd.DataFrame({"case_id": g["id"].to_numpy(), "mmsi": g["mmsi"].astype(np.int64).to_numpy(),
                          "as_of": g["start_ts"].astype(np.int64).to_numpy(), "cls": "A", "kind": "real_gap",
                          "gap_flag": g["coverage_flag"].to_numpy(), "_end": g["end_ts"].astype(np.int64).to_numpy(),
                          "_nlat": g["next_lat"].to_numpy(float), "_nlon": g["next_lon"].to_numpy(float)})
    feat = track_features(track, cases, statics)
    reap = feat.copy()
    reap["horizon_s"] = (reap["_end"] - reap["as_of"]) // 1000
    reap["true_lat"], reap["true_lon"] = reap["_nlat"], reap["_nlon"]
    reap["truth"] = "reappear"
    fixed = expand_horizons(feat, track, horizons)
    fixed = fixed[fixed["as_of"] + fixed["horizon_s"] * 1000 >= fixed["_end"]]   # only once it is heard again
    fixed["truth"] = "fixed"
    return pd.concat([reap, fixed], ignore_index=True).drop(columns=["_end", "_nlat", "_nlon"])


def build(track: pd.DataFrame, statics: pd.DataFrame | None = None, gaps: pd.DataFrame | None = None, *,
          step_min: int = 20, min_sog_kn: float = 1.0, horizons=HORIZONS_S, n_synthetic: int = 5000,
          source: str = "tiger", seed: int = 0) -> pd.DataFrame:
    """All route examples from one source, long format, ready for model.fit / model.predict."""
    track = speed_gate(track)
    cases = grid_cases(track, step_min, min_sog_kn, seed)
    cases["case_id"] = source + "-" + cases["mmsi"].astype(str) + "-" + cases["as_of"].astype(str)
    feat = track_features(track, cases, statics)
    out = [expand_horizons(feat, track, horizons).assign(truth="fixed")]
    if n_synthetic:
        out.append(synthetic_gap_cases(feat, track, n_synthetic, seed).assign(truth="reappear"))
    if gaps is not None and len(gaps):
        out.append(real_gap_cases(gaps, track, statics, horizons))
    ex = pd.concat(out, ignore_index=True)
    ex["source"] = source
    ex["horizon_s"] = ex["horizon_s"].astype(np.int64)
    if "gap_flag" not in ex:
        ex["gap_flag"] = None
    return ex.sort_values(["as_of", "case_id", "horizon_s"], kind="stable").reset_index(drop=True)
