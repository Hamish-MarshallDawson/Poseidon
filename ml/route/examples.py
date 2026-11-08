"""Route examples: one row per case ("ship at as_of"), with truth at every horizon as columns.

Features and the baseline come only from `dvm.predict.features` (the backend's shared module: `features_at`,
`baseline_point`), so a model sees exactly what the live predictor computes. Truth is looked up separately, here,
from fixes after as_of, and never feeds a feature.

Kinds of case (`kind`):
- `track`: a moving ship (>= 1 kn, not anchored or moored, the live predictor's rule) at the first fix in each
  `step_min` bucket of a complete track. Truth `truth_lat_<h>`, `truth_lon_<h>`: the position at as_of + h,
  interpolated between fixes within 5 min, else NaN.
- synthetic dead zones, on a sample of Class A `track` cases: the track is hidden for a random duration after as_of
  (drawn from our detector's closed deliberate gaps: median 69 min, p90 178 min) and the case is graded on the first
  fix after it (`reap_kind = "synthetic"`, `reap_s`, `reap_lat`, `reap_lon`). Labelled synthetic: nobody went dark.
- `real_gap`: a closed gap from our Tiger `gaps` table (read-only): as_of = the last fix before the silence, graded
  on the fix that closed it (`reap_kind = "real"`), and at fixed horizons only once the ship is heard again.

Columns: case_id, mmsi, as_of, kind, source, the feature columns (`dvm.predict.features.FEATURE_NAMES`), the last fix
(`fix_*`), the baseline point per horizon (`base_lat_<h>`, `base_lon_<h>`), truth, and strata (`type_group`,
`speed_class`).
"""
from __future__ import annotations

import multiprocessing as mp
import os

import numpy as np
import pandas as pd

from ml.route import TRAIN_HORIZONS_S
from ml.route.geo import KN_TO_MS, haversine_m

from dvm.predict import features as F  # noqa: E402  (ml/__init__ puts backend/ on sys.path)

TRUTH_TOL_S = 300                          # truth at as_of + h must be within 5 min of a fix
GAP_MEDIAN_S, GAP_SIGMA = 69 * 60, 0.74    # lognormal fit to closed deliberate gaps (median 69 min, p90 178 min)
SPEED_EDGES_KN = (5.0, 12.0)
SPEED_CLASSES = ("<5kn", "5-12kn", ">=12kn")
TRACK_COLS = ["mmsi", "ts", "lat", "lon", "sog_kn", "cog_deg", "heading_deg", "nav_status", "cls"]

# Danish archive ship types are text; the live feed has AIS numeric codes. Map text to the code of its group so the
# `ship_type` feature means the same in training and live.
DMA_SHIP_TYPE = {"Cargo": 70, "Tanker": 80, "Passenger": 60, "Fishing": 30, "Pleasure": 37, "Sailing": 36,
                 "Tug": 52, "Pilot": 50, "SAR": 51, "Port tender": 53, "Anti-pollution": 54, "Law enforcement": 55,
                 "Medical": 58, "Not party to conflict": 59, "Dredging": 33, "Diving": 34, "Military": 35,
                 "Towing": 31, "Towing long/wide": 32, "HSC": 40, "WIG": 20, "Other": 90}


def type_group(ship_type) -> str:
    """Same groups as dvm.normalise.type_group."""
    try:
        s = int(ship_type)
    except (TypeError, ValueError):
        return "unknown"
    if not s: return "unknown"
    if 80 <= s <= 89: return "tanker"
    if 70 <= s <= 79: return "cargo"
    if 60 <= s <= 69: return "passenger"
    if s == 30: return "fishing"
    if s == 35: return "military"
    if s in (36, 37): return "pleasure"
    if s in (31, 32) or 50 <= s <= 59: return "tug_special"
    return "other"


def speed_class(sog) -> np.ndarray:
    s = np.nan_to_num(np.asarray(sog, float), nan=0.0)
    return np.array(SPEED_CLASSES)[np.digitize(s, SPEED_EDGES_KN)]


def normalise_statics(st: pd.DataFrame | None) -> pd.DataFrame:
    """mmsi, ship_type (AIS code), length_m, draught_m: what features_at's `static` reads."""
    if st is None or st.empty:
        return pd.DataFrame(columns=["mmsi", "ship_type", "length_m", "draught_m"])
    st = st.copy()
    if not pd.api.types.is_numeric_dtype(st["ship_type"]):
        st["ship_type"] = st["ship_type"].map(DMA_SHIP_TYPE)
    length = st["length"] if "length" in st else st.get("length_m")
    draught = st["draught"] if "draught" in st else st.get("draught_m")
    out = pd.DataFrame({"mmsi": st["mmsi"].astype("int64"),
                        "ship_type": pd.to_numeric(st["ship_type"], errors="coerce"),
                        "length_m": pd.to_numeric(length, errors="coerce") if length is not None else np.nan,
                        "draught_m": pd.to_numeric(draught, errors="coerce") if draught is not None else np.nan})
    for c in ("length_m", "draught_m"):
        out[c] = out[c].where(out[c] > 0)
    return out.drop_duplicates("mmsi", keep="last")


def speed_gate(track: pd.DataFrame, max_kn: float = 40.0) -> pd.DataFrame:
    """Drop fixes more than max_kn from the previous fix of the same ship (bad positions, spoofed jumps). The Danish
    archive is already gated this way by ml/data; our live feed is not."""
    tr = track.sort_values(["mmsi", "ts"], kind="stable").reset_index(drop=True)
    for _ in range(3):
        m = tr["mmsi"].to_numpy()
        la, lo = tr["lat"].to_numpy(), tr["lon"].to_numpy()
        d = haversine_m(la[:-1], lo[:-1], la[1:], lo[1:])
        dt = np.diff(tr["ts"].to_numpy()) / 1000.0
        fast = (m[1:] == m[:-1]) & (d > 500) & (d / np.maximum(dt, 1.0) > max_kn * KN_TO_MS)
        if not fast.any():
            break
        tr = tr.loc[~np.r_[False, fast]].reset_index(drop=True)
    return tr


def grid_cases(track: pd.DataFrame, step_min: int = 30, min_sog_kn: float = 1.0) -> pd.DataFrame:
    """One case per ship per `step_min` bucket, at the first fix in the bucket, if the ship is moving there."""
    b = track["ts"].to_numpy() // (step_min * 60_000)
    first = ~pd.DataFrame({"m": track["mmsi"].to_numpy(), "b": b}).duplicated().to_numpy()
    sog, nav = track["sog_kn"].to_numpy(float), track["nav_status"].to_numpy(float)
    keep = first & (sog >= min_sog_kn) & ~np.isin(nav, [1, 5])
    return pd.DataFrame({"mmsi": track["mmsi"].to_numpy()[keep], "as_of": track["ts"].to_numpy()[keep]})


# ---------------------------------------------------------------- features through dvm.predict.features

_SHARED: dict = {}          # set before forking: workers read the track from here instead of a pickled copy


def _work(job):
    lo, hi, case_lo, case_hi = job
    tr, cases, statics, horizons = _SHARED["track"], _SHARED["cases"], _SHARED["statics"], _SHARED["horizons"]
    rows = []
    starts = np.r_[lo, lo + np.flatnonzero(np.diff(tr["mmsi"][lo:hi])) + 1, hi]
    c_m, c_t = cases["mmsi"][case_lo:case_hi], cases["as_of"][case_lo:case_hi]
    ci = 0
    for s, e in zip(starts[:-1], starts[1:]):
        mmsi = int(tr["mmsi"][s])
        while ci < len(c_m) and c_m[ci] < mmsi:
            ci += 1
        cj = ci
        while cj < len(c_m) and c_m[cj] == mmsi:
            cj += 1
        if cj == ci:
            continue
        T = F.Track.from_columns(mmsi, tr["ts"][s:e], tr["lat"][s:e], tr["lon"][s:e], tr["sog_kn"][s:e],
                                 tr["cog_deg"][s:e], tr["heading_deg"][s:e], tr["nav_status"][s:e], tr["cls"][s:e])
        static = statics.get(mmsi)
        for a in c_t[ci:cj]:
            f = F.features_at(T, int(a), static)
            if f is None:
                continue
            fix = T.last_fix(int(a))
            r = {"mmsi": mmsi, "as_of": int(a), **f, "fix_ts": fix["ts"], "fix_lat": fix["lat"],
                 "fix_lon": fix["lon"], "fix_sog": fix["sog_kn"], "fix_cog": fix["cog_deg"],
                 "fix_hdg": fix["heading_deg"], "fix_nav": fix["nav_status"], "fix_cls": fix["cls"],
                 "stopped": F.is_stopped(fix)}
            for h in horizons:
                r[f"base_lat_{h}"], r[f"base_lon_{h}"] = F.baseline_point(fix, h)
            rows.append(r)
        ci = cj
    return rows


def compute_features(track: pd.DataFrame, cases: pd.DataFrame, statics: pd.DataFrame | None,
                     horizons=TRAIN_HORIZONS_S, workers: int | None = None) -> pd.DataFrame:
    """features_at + last fix + baseline points for every (mmsi, as_of) case, in parallel by ship."""
    tr = track[TRACK_COLS].sort_values(["mmsi", "ts"], kind="stable").reset_index(drop=True)
    cs = cases[["mmsi", "as_of"]].sort_values(["mmsi", "as_of"], kind="stable").reset_index(drop=True)
    st = normalise_statics(statics)
    stat = {int(m): {"ship_type": None if pd.isna(t) else float(t), "length_m": None if pd.isna(ln) else float(ln),
                     "draught_m": None if pd.isna(d) else float(d)}
            for m, t, ln, d in zip(st["mmsi"], st["ship_type"], st["length_m"], st["draught_m"])}
    _SHARED.update(track={c: tr[c].to_numpy() for c in TRACK_COLS},
                   cases={c: cs[c].to_numpy(np.int64) for c in ("mmsi", "as_of")}, statics=stat,
                   horizons=[int(h) for h in horizons])
    # jobs: contiguous ship ranges of the track, with the matching contiguous case ranges
    m = _SHARED["track"]["mmsi"]
    cm = _SHARED["cases"]["mmsi"]
    n_jobs = max(1, min(400, len(cs) // 500))
    cuts = np.searchsorted(m, np.unique(np.quantile(cm, np.linspace(0, 1, n_jobs + 1)[1:-1]).astype(np.int64)),
                           side="left") if len(cm) else np.array([], int)
    bounds = np.unique(np.r_[0, cuts, len(m)])
    jobs = []
    for lo, hi in zip(bounds[:-1], bounds[1:]):
        c_lo = np.searchsorted(cm, m[lo], side="left")
        c_hi = np.searchsorted(cm, m[hi - 1], side="right")
        if c_hi > c_lo:
            jobs.append((int(lo), int(hi), int(c_lo), int(c_hi)))
    workers = workers or int(os.environ.get("ROUTE_WORKERS", "6"))
    try:
        if workers > 1 and len(jobs) > 1:
            with mp.get_context("fork").Pool(workers) as pool:
                parts = pool.map(_work, jobs, chunksize=1)
        else:
            parts = [_work(j) for j in jobs]
    finally:
        _SHARED.clear()
    df = pd.DataFrame([r for p in parts for r in p])
    if df.empty:
        return df
    df = df.merge(st[["mmsi", "ship_type"]].rename(columns={"ship_type": "_st"}), on="mmsi", how="left")
    df["type_group"] = [type_group(x) for x in df["_st"]]
    df["speed_class"] = speed_class(df["fix_sog"])
    return df.drop(columns=["_st"])


# ---------------------------------------------------------------- truth

def _keys(track: pd.DataFrame, mmsi: np.ndarray, when: np.ndarray):
    """Exact int64 sort keys (ship rank << 42 | ms since the first fix) for a track sorted by mmsi, ts."""
    keys = track["mmsi"].to_numpy(np.int64)
    ts = track["ts"].to_numpy(np.int64)
    t0 = int(min(ts.min(), when.min())) - 1 if len(ts) and len(when) else 0
    uniq = np.unique(keys)
    rk = np.searchsorted(uniq, keys).astype(np.int64)
    qr = np.searchsorted(uniq, mmsi).astype(np.int64)
    return keys, ts, (rk << 42) | (ts - t0), (qr << 42) | np.clip(when - t0, 0, (1 << 42) - 1)


def truth_at(track: pd.DataFrame, mmsi, when, tol_s: int = TRUTH_TOL_S):
    """Position of each ship at `when` (ms): interpolated between the bracketing fixes when both are within tol_s,
    else the nearer fix if within tol_s, else NaN. Track sorted by mmsi, ts."""
    mmsi, when = np.asarray(mmsi, np.int64), np.asarray(when, np.int64)
    keys, ts, tk, qk = _keys(track, mmsi, when)
    la, lo = track["lat"].to_numpy(float), track["lon"].to_numpy(float)
    k = np.searchsorted(tk, qk, side="left")                   # first fix at or after `when`
    n = len(ts)
    kk, kp = np.clip(k, 0, n - 1), np.clip(k - 1, 0, n - 1)
    after_ok = (k < n) & (keys[kk] == mmsi) & (ts[kk] >= when) & (ts[kk] - when <= tol_s * 1000)
    before_ok = (k > 0) & (keys[kp] == mmsi) & (ts[kp] <= when) & (when - ts[kp] <= tol_s * 1000)
    both = after_ok & before_ok
    w = np.where(both, (when - ts[kp]) / np.maximum(ts[kk] - ts[kp], 1), 0.0)
    dlon = (lo[kk] - lo[kp] + 540) % 360 - 180
    lat = np.where(both, la[kp] + w * (la[kk] - la[kp]), np.nan)
    lon = np.where(both, (lo[kp] + w * dlon + 540) % 360 - 180, np.nan)
    only_a, only_b = after_ok & ~before_ok, before_ok & ~after_ok
    lat = np.where(only_a, la[kk], np.where(only_b, la[kp], lat))
    lon = np.where(only_a, lo[kk], np.where(only_b, lo[kp], lon))
    return lat, lon


def first_fix_after(track: pd.DataFrame, mmsi, when):
    mmsi, when = np.asarray(mmsi, np.int64), np.asarray(when, np.int64)
    keys, ts, tk, qk = _keys(track, mmsi, when)
    la, lo = track["lat"].to_numpy(float), track["lon"].to_numpy(float)
    k = np.searchsorted(tk, qk, side="left")
    kk = np.clip(k, 0, len(ts) - 1)
    ok = (k < len(ts)) & (keys[kk] == mmsi) & (ts[kk] >= when)
    return np.where(ok, ts[kk], -1), np.where(ok, la[kk], np.nan), np.where(ok, lo[kk], np.nan)


def add_truth(df: pd.DataFrame, track: pd.DataFrame, horizons=TRAIN_HORIZONS_S) -> pd.DataFrame:
    m, a = df["mmsi"].to_numpy(np.int64), df["as_of"].to_numpy(np.int64)
    for h in horizons:
        df[f"truth_lat_{h}"], df[f"truth_lon_{h}"] = truth_at(track, m, a + int(h) * 1000)
    return df


def add_synthetic_gaps(df: pd.DataFrame, track: pd.DataFrame, n: int, seed: int = 0) -> pd.DataFrame:
    """Hide a lognormal-length stretch after as_of on n Class A track cases; truth = the first fix after it."""
    for c, v in (("reap_kind", None), ("reap_s", np.nan), ("reap_lat", np.nan), ("reap_lon", np.nan)):
        if c not in df:
            df[c] = v
    df["reap_kind"] = df["reap_kind"].astype(object)
    pool = np.flatnonzero((df["is_class_a"].to_numpy() == 1) & (df["kind"].to_numpy() == "track"))
    if not n or not len(pool):
        return df
    rng = np.random.default_rng(seed)
    pick = np.sort(rng.choice(pool, min(n, len(pool)), replace=False))
    dur = np.clip(rng.lognormal(np.log(GAP_MEDIAN_S), GAP_SIGMA, len(pick)), 1800, 24 * 3600).astype(np.int64)
    m, a = df["mmsi"].to_numpy(np.int64)[pick], df["as_of"].to_numpy(np.int64)[pick]
    t, la, lo = first_fix_after(track, m, a + dur * 1000)
    ok = (t > 0) & ((t - a) // 1000 <= dur + 600)            # back within 10 min of the hidden stretch's end
    idx = df.index[pick[ok]]
    df.loc[idx, "reap_kind"] = "synthetic"
    df.loc[idx, "reap_s"] = ((t - a) // 1000)[ok]
    df.loc[idx, "reap_lat"], df.loc[idx, "reap_lon"] = la[ok], lo[ok]
    return df


def real_gap_cases(gaps: pd.DataFrame, track: pd.DataFrame, statics, horizons=TRAIN_HORIZONS_S, workers=None):
    """Closed gaps from our detector: reappearance truth, plus fixed horizons once the ship is back in our feed."""
    g = gaps[(gaps["state"] == "closed") & gaps["end_ts"].notna()].drop_duplicates("id")
    g = g.astype({"mmsi": "int64", "start_ts": "int64", "end_ts": "int64"})
    cases = pd.DataFrame({"mmsi": g["mmsi"].to_numpy(), "as_of": g["start_ts"].to_numpy()})
    df = compute_features(track, cases, statics, horizons, workers)
    if df.empty:
        return df
    g = g.rename(columns={"start_ts": "as_of"})
    df = df.merge(g[["mmsi", "as_of", "id", "end_ts", "next_lat", "next_lon", "coverage_flag"]],
                  on=["mmsi", "as_of"], how="inner").drop_duplicates("id")
    df = add_truth(df, track, horizons)
    end = df["end_ts"].to_numpy(np.int64)
    for h in horizons:                                        # dark at as_of + h: no truth there
        dark = df["as_of"].to_numpy(np.int64) + int(h) * 1000 < end
        df.loc[dark, [f"truth_lat_{h}", f"truth_lon_{h}"]] = np.nan
    df["case_id"] = df["id"].astype(str)
    df["kind"], df["reap_kind"] = "real_gap", "real"
    df["reap_s"] = (end - df["as_of"].to_numpy(np.int64)) // 1000
    df["reap_lat"], df["reap_lon"] = df["next_lat"].astype(float), df["next_lon"].astype(float)
    df["gap_flag"] = df["coverage_flag"]
    return df.drop(columns=["id", "end_ts", "next_lat", "next_lon", "coverage_flag"])


def build(track: pd.DataFrame, statics: pd.DataFrame | None = None, gaps: pd.DataFrame | None = None, *,
          step_min: int = 30, min_sog_kn: float = 1.0, horizons=TRAIN_HORIZONS_S, n_synthetic: int = 5000,
          source: str = "dma", seed: int = 0, gate: bool = True, workers: int | None = None) -> pd.DataFrame:
    """All route examples from one source (wide, one row per case), deterministic for the same input."""
    track = speed_gate(track) if gate else track.sort_values(["mmsi", "ts"], kind="stable").reset_index(drop=True)
    cases = grid_cases(track, step_min, min_sog_kn)
    df = compute_features(track, cases, statics, horizons, workers)
    df["case_id"] = source + "-" + df["mmsi"].astype(str) + "-" + df["as_of"].astype(str)
    df["kind"] = "track"
    df["gap_flag"] = None
    df = add_truth(df, track, horizons)
    df = add_synthetic_gaps(df, track, n_synthetic, seed)
    if gaps is not None and len(gaps):
        rg = real_gap_cases(gaps, track, statics, horizons, workers)
        if len(rg):
            df = pd.concat([df, rg], ignore_index=True)
    df["source"] = source
    first = ["case_id", "mmsi", "as_of", "kind", "source"]
    df = df[first + [c for c in df.columns if c not in first]]
    return df.sort_values(["as_of", "case_id"], kind="stable").reset_index(drop=True)
