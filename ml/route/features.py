"""Route features and the dead-reckoning baseline: pure functions of a ship's track up to `as_of`.

Only numpy and pandas, no ml/ imports, so it can move verbatim into `backend/dvm/predict/features.py` (the
contract's shared home) and the live predictor computes exactly what training computed. Nothing after `as_of` is
read: `track_features` only looks at rows with ts <= as_of.

Track input: columns mmsi, ts (epoch ms), lat, lon, sog_kn, cog_deg, heading_deg, nav_status, cls, sorted by
mmsi, ts. Statics (optional): mmsi, ship_type, length.
"""
from __future__ import annotations

import numpy as np
import pandas as pd

try:  # inside ml/ (training) or copied into the backend
    from ml.route.geo import KN_TO_MS, angle_diff_deg, bearing_deg, destination, haversine_m
except ImportError:  # pragma: no cover
    from .geo import KN_TO_MS, angle_diff_deg, bearing_deg, destination, haversine_m  # type: ignore

FEATURE_VERSION = "route-f1"
WINDOWS_MIN = (10, 30, 60, 180)
STOPPED_NAV = (1, 5)          # at anchor, moored
STOPPED_SOG_KN = 0.5
TYPE_GROUPS = ["unknown", "cargo", "tanker", "passenger", "fishing", "military", "pleasure", "tug_special", "other"]


def type_group(ship_type) -> str:
    """Same groups as dvm.normalise.type_group."""
    if ship_type is None or (isinstance(ship_type, float) and np.isnan(ship_type)) or not ship_type:
        return "unknown"
    s = int(ship_type)
    if 80 <= s <= 89: return "tanker"
    if 70 <= s <= 79: return "cargo"
    if 60 <= s <= 69: return "passenger"
    if s == 30: return "fishing"
    if s == 35: return "military"
    if s in (36, 37): return "pleasure"
    if s in (31, 32) or 50 <= s <= 59: return "tug_special"
    return "other"


def _clean_track(tr: pd.DataFrame) -> pd.DataFrame:
    """AIS 'not available' sentinels to NaN (sog 102.3, cog 360, heading 511) in case a source left them in."""
    tr = tr.copy()
    for c, bad in (("sog_kn", 102.2), ("cog_deg", 359.95), ("heading_deg", 360.0)):
        v = tr[c].astype("float64")
        tr[c] = v.where(v < bad)
    tr["nav_status"] = tr["nav_status"].astype("float64")
    return tr


def sort_keys(track: pd.DataFrame, mmsi: np.ndarray, when: np.ndarray):
    """Exact int64 sort keys (ship rank << 42 | ms since the first fix) for a track sorted by mmsi, ts, and for
    queries (mmsi, when). A query for a ship not in the track gets a key that may land on a neighbour's rows, so
    callers check the ship of the row they land on."""
    keys = track["mmsi"].to_numpy(np.int64)
    ts = track["ts"].to_numpy(np.int64)
    t0 = int(min(ts.min(), when.min())) - 1 if len(ts) and len(when) else 0
    uniq = np.unique(keys)
    rk = np.searchsorted(uniq, keys).astype(np.int64)
    qr = np.searchsorted(uniq, mmsi).astype(np.int64)
    tk = (rk << 42) | (ts - t0)
    qk = (qr << 42) | np.clip(when - t0, 0, (1 << 42) - 1)
    return keys, ts, tk, qk, qr, t0


def track_features(track: pd.DataFrame, cases: pd.DataFrame, statics: pd.DataFrame | None = None) -> pd.DataFrame:
    """One feature row per case (mmsi, as_of ms), from that ship's fixes with ts <= as_of.

    Returns the cases' columns plus `last_ts, last_lat, last_lon` (the fix the prediction starts from) and the
    feature columns in `feature_names()`. Cases whose ship has no fix at or before as_of are dropped. Vectorised over
    all ships at once: the track must be sorted by mmsi, ts.
    """
    tr = _clean_track(track[["mmsi", "ts", "lat", "lon", "sog_kn", "cog_deg", "heading_deg", "nav_status", "cls"]])
    cs = cases.reset_index(drop=True)
    q_mmsi, q_t = cs["mmsi"].to_numpy(np.int64), cs["as_of"].to_numpy(np.int64)
    if len(tr) == 0 or len(cs) == 0:
        return pd.DataFrame(columns=[*cases.columns, "last_ts", "last_lat", "last_lon", *feature_names()])
    keys, t, tk, qk, qr, t0 = sort_keys(tr, q_mmsi, q_t)
    i = np.searchsorted(tk, qk, side="right") - 1             # last fix at or before as_of
    ok = (i >= 0) & (keys[np.clip(i, 0, None)] == q_mmsi)
    i = np.where(ok, i, 0)
    rank = tk >> 42
    lat, lon = tr["lat"].to_numpy(float), tr["lon"].to_numpy(float)
    sog, cog = tr["sog_kn"].to_numpy(float), tr["cog_deg"].to_numpy(float)
    hdg, nav = tr["heading_deg"].to_numpy(float), tr["nav_status"].to_numpy(float)
    f: dict = {"last_ts": t[i], "last_lat": lat[i], "last_lon": lon[i]}
    f["age_s"] = (q_t - t[i]) / 1000.0                       # time since last fix (gap length so far)
    f["last_sog"] = sog[i]
    f["last_cog_sin"], f["last_cog_cos"] = np.sin(np.radians(cog[i])), np.cos(np.radians(cog[i]))
    f["hdg_minus_cog"] = angle_diff_deg(hdg[i], cog[i])
    f["nav_status"] = nav[i]
    f["is_class_a"] = (tr["cls"].to_numpy()[i] == "A").astype(np.float64)
    f["lat"], f["lon"] = lat[i], lon[i]
    prev = np.maximum(i - 1, 0)
    f["dt_prev_s"] = np.where((i > 0) & (rank[prev] == rank[i]), (t[i] - t[prev]) / 1000.0, np.nan)
    # cumulative sums for window means of sog (NaN-safe) and path length; windows never cross into another ship
    # because the window start is searched with the same ship's key
    sv = np.nan_to_num(sog, nan=0.0)
    sn = (~np.isnan(sog)).astype(np.float64)
    cs_s, cs_s2, cs_n = np.r_[0, np.cumsum(sv)], np.r_[0, np.cumsum(sv * sv)], np.r_[0, np.cumsum(sn)]
    same = np.r_[False, keys[1:] == keys[:-1]]
    step = np.where(same, np.r_[0.0, haversine_m(lat[:-1], lon[:-1], lat[1:], lon[1:])], 0.0)
    cs_p = np.cumsum(step)
    ik = tk[i]
    for w in WINDOWS_MIN:
        lo = np.maximum(ik - w * 60_000, rank[i] << 42)         # never before this ship's first fix
        j = np.minimum(np.searchsorted(tk, lo, side="left"), i)
        span = (t[i] - t[j]) / 1000.0
        good = (i > j) & (span >= w * 30)                    # history covers at least half the window
        n = cs_n[i + 1] - cs_n[j]
        m = np.where(n > 0, (cs_s[i + 1] - cs_s[j]) / np.maximum(n, 1), np.nan)
        var = np.where(n > 1, (cs_s2[i + 1] - cs_s2[j]) / np.maximum(n, 1) - m * m, np.nan)
        var = np.where(var < 1e-6, 0.0, var)                 # cumsum rounding: same value live and in training
        d = haversine_m(lat[j], lon[j], lat[i], lon[i])
        b = bearing_deg(lat[j], lon[j], lat[i], lon[i])
        path = cs_p[i] - cs_p[j]
        f[f"sog_mean_{w}"] = m
        f[f"sog_std_{w}"] = np.sqrt(np.clip(var, 0, None))
        f[f"n_fix_{w}"] = (i - j + 1).astype(np.float64)
        v = np.where(good, d / np.maximum(span, 1.0) / KN_TO_MS, np.nan)
        f[f"disp_kn_{w}"] = v
        moving = good & (d > 50)
        f[f"disp_brg_rel_{w}"] = np.where(moving, angle_diff_deg(b, cog[i]), np.nan)
        f[f"turn_{w}"] = np.where(good, angle_diff_deg(cog[i], cog[j]), np.nan)
        f[f"straight_{w}"] = np.where(moving & (path > 0), d / np.maximum(path, 1e-6), np.nan)
        f[f"sog_minus_disp_{w}"] = sog[i] - v
    df = pd.concat([cs, pd.DataFrame(f)], axis=1).loc[ok].reset_index(drop=True)
    st = statics if statics is not None else pd.DataFrame(columns=["mmsi", "ship_type", "length"])
    if "type_group" not in st:                               # numeric AIS ship type (Tiger statics)
        st = st.assign(type_group=[type_group(x) for x in st["ship_type"]])
    st = st[["mmsi", "type_group", "length"]].drop_duplicates("mmsi", keep="last").astype({"mmsi": "int64"})
    df = df.merge(st, on="mmsi", how="left")
    df["type_group"] = pd.Categorical(df["type_group"].fillna("unknown").where(
        df["type_group"].isin(TYPE_GROUPS), "other"), categories=TYPE_GROUPS)
    df["type_code"] = df["type_group"].cat.codes.astype("int16")
    df["length_m"] = pd.to_numeric(df["length"], errors="coerce").where(lambda x: x > 0)
    hod = (df["as_of"] // 1000 % 86400) / 3600.0
    df["hod_sin"], df["hod_cos"] = np.sin(2 * np.pi * hod / 24), np.cos(2 * np.pi * hod / 24)
    return df.drop(columns=["length"])


def feature_names() -> list[str]:
    # age_s is not a model feature: models predict from the last fix with effective horizon age_s + horizon_s
    names = ["last_sog", "last_cog_sin", "last_cog_cos", "hdg_minus_cog", "nav_status", "is_class_a",
             "lat", "lon", "dt_prev_s"]
    for w in WINDOWS_MIN:
        names += [f"sog_mean_{w}", f"sog_std_{w}", f"n_fix_{w}", f"disp_kn_{w}", f"disp_brg_rel_{w}", f"turn_{w}",
                  f"straight_{w}", f"sog_minus_disp_{w}"]
    return names + ["type_code", "length_m", "hod_sin", "hod_cos"]


FEATURE_GROUPS = {
    "kinematics": ["last_sog", "last_cog_sin", "last_cog_cos", "hdg_minus_cog", "nav_status", "dt_prev_s"],
    "position": ["lat", "lon"],
    "history": [n for n in feature_names() if any(n.endswith(f"_{w}") for w in WINDOWS_MIN)],
    "ship": ["is_class_a", "type_code", "length_m"],
    "time": ["hod_sin", "hod_cos"],
}


def baseline_course(df: pd.DataFrame) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    """(bearing deg, speed kn, stopped) the baseline extrapolates with, from the last fix.

    Last course over ground and speed; heading if the course is missing; "stay put" when at anchor or moored,
    slower than 0.5 kn, or without a usable speed or direction.
    """
    sog = df["last_sog"].to_numpy(float)
    cog = np.degrees(np.arctan2(df["last_cog_sin"].to_numpy(float), df["last_cog_cos"].to_numpy(float))) % 360
    hdg = (cog + df["hdg_minus_cog"].to_numpy(float)) % 360 if "hdg_minus_cog" in df else np.full(len(df), np.nan)
    brg = np.where(np.isnan(cog), hdg, cog)
    nav = df["nav_status"].to_numpy(float)
    stopped = np.isin(nav, STOPPED_NAV) | ~(sog >= STOPPED_SOG_KN) | np.isnan(brg)
    return np.where(stopped, 0.0, brg), np.where(stopped, 0.0, sog), stopped


def baseline_position(df: pd.DataFrame, horizon_s) -> tuple[np.ndarray, np.ndarray]:
    """Dead reckoning on the sphere from the last fix, `horizon_s` after as_of (the time already elapsed since the
    last fix, `age_s`, is added so a prediction for a ship silent for an hour starts from where it was an hour ago).
    """
    brg, sog, _ = baseline_course(df)
    dt = np.asarray(horizon_s, float) + df["age_s"].to_numpy(float)
    return destination(df["last_lat"].to_numpy(float), df["last_lon"].to_numpy(float), brg, sog * KN_TO_MS * dt)
