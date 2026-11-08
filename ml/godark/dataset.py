"""Go-dark examples: one row per moving Class A ship and grid time `made_at`, with labels and features (#121).

Label (per horizon H in 1, 6, 24 h): a gap of ours starts within H of the ship's latest fix. Precisely, the ship's
latest fix at `made_at` is at most ACTIVE_MS old, and a gap with `start_ts` in [last_fix_ts, made_at + H] exists.
(A gap's `start_ts` is the ship's last fix before the silence, so a ship that goes silent right after the fix we
have is a positive.) `y_<flag>_<H>` is that label for one coverage flag: `deliberate_candidate` is the primary label,
`unknown`, `coverage_gap` and `any` (every flag but own_stall) are reported beside it.

Population: Class A ships whose latest fix at `made_at` is recent (ACTIVE_MS) and moving by the detector's own
test (speed at least 1 kn and not at anchor or moored). Only moving ships can open a gap, so stationary ships would
only add easy negatives. A ship heard within ACTIVE_MS is never inside an open gap (its next fix closed it).

Censoring: a row is labelled for H only if the detector had time to open any gap starting by made_at + H, i.e.
made_at + H + DETECT_MS <= the end of the data. Unlabelled horizons are NaN, never 0. Rows within WARMUP_MS of the
start of the data (thin history, detector state still filling) or within POST_STALL_MS after one of our outages are
left out.

Features: the shared track features (`dvm.predict.features.features_at`, what the live predictor computes), plus
context that is known at `made_at` (CONTEXT_FEATURES): area reception, gaps already detected nearby and for this
ship (only gaps whose first version was detected by made_at, with the flag they had then), ship type group, flag
state, source, local solar time. The context features are not in the live predictor's feature list yet.

    ml/.venv/bin/python -m ml.godark.dataset    # writes /home/aiden/data/poseidon/godark/examples.parquet
"""
from __future__ import annotations

import hashlib
import json
import math
import os
import time
from concurrent.futures import ProcessPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

import ml  # noqa: F401  (puts backend/ on sys.path)
from dvm.predict import features as F

MIN = 60_000
H_MS = 3_600_000
HORIZONS_S = [3600, 6 * 3600, 24 * 3600]
FLAGS = ["deliberate_candidate", "unknown", "coverage_gap"]
STEP_MS = 10 * MIN            # grid spacing
ACTIVE_MS = 10 * MIN          # the latest fix must be this recent
WARMUP_MS = 2 * H_MS          # skip the first 2 h of data
DETECT_MS = 35 * MIN          # a gap opens 30 min after its start (the floor), plus slack
POST_STALL_MS = 30 * MIN      # skip grid times just after one of our outages
MIN_SOG_KN = 1.0
AT_ANCHOR_OR_MOORED = {1, 5}
GRID_DEG = 0.2                # reception buckets, as the gap detector's neighbour index
AREA_DEG = 1.0                # cells for past-gap counts and the base-rate baseline

CONTEXT_FEATURES = [
    "rx_ships_10m", "rx_ships_30m", "rx_ships_2h_ago", "rx_drop", "rx_msgs_10m",
    "area_gaps_6h_any", "area_gaps_6h_delib", "area_gaps_6h_per_ship",
    "ship_gaps_any", "ship_gaps_delib", "src_digitraffic", "solar_sin", "solar_cos",
    "type_group", "flag_iso2",
]
CATEGORICAL = ["type_group", "flag_iso2"]
OUT = Path("/home/aiden/data/poseidon/godark")


def h_label(h_s: int) -> str:
    return f"{h_s // 3600}h"


# ---------------------------------------------------------------- inputs

def prepare_positions(pos: pd.DataFrame) -> pd.DataFrame:
    """Rows of ships that ever sent a Class A fix, de-duplicated on (mmsi, ts), sorted by mmsi, ts."""
    a = set(pos.loc[pos["cls"] == "A", "mmsi"].unique())
    p = pos[pos["mmsi"].isin(a)].copy()
    p = p.sort_values(["mmsi", "ts", "recv_ts"]).drop_duplicates(["mmsi", "ts"], keep="first")
    return p.reset_index(drop=True)


def gap_views(versions: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(final, first): the newest version of every gap (labels) and its first version (what was known at detection,
    for the past-gap features)."""
    v = versions.sort_values(["id", "version"])
    final = v.groupby("id", as_index=False).tail(1).reset_index(drop=True)
    first = v.groupby("id", as_index=False).head(1).reset_index(drop=True)
    return final, first


def statics_asof(statics: pd.DataFrame) -> pd.DataFrame:
    s = statics[["mmsi", "ts", "ship_type", "type_group", "length_m", "draught_m", "flag_iso2"]].copy()
    return s.sort_values("ts").reset_index(drop=True)


# ---------------------------------------------------------------- grid and labels

def grid_times(data_from: int, data_to: int, stalls: list[tuple[int, int]]) -> np.ndarray:
    t0 = (data_from + WARMUP_MS + STEP_MS - 1) // STEP_MS * STEP_MS
    g = np.arange(t0, data_to, STEP_MS, dtype=np.int64)
    keep = np.ones(len(g), bool)
    for a, b in stalls:
        keep &= ~((g >= a) & (g < b + POST_STALL_MS))
    return g[keep]


def base_rows(p: pd.DataFrame, grid: np.ndarray) -> pd.DataFrame:
    """Population rows (mmsi, made_at, i_last) from each ship's fixes: latest fix recent and moving."""
    out = []
    ts_all = p["ts"].to_numpy()
    sog_all = p["sog_kn"].to_numpy(dtype=float)
    nav_all = p["nav_status"].to_numpy(dtype=float)
    cls_all = p["cls"].to_numpy()
    mm = p["mmsi"].to_numpy()
    starts = np.flatnonzero(np.r_[True, mm[1:] != mm[:-1]])
    ends = np.r_[starts[1:], len(mm)]
    for s, e in zip(starts, ends):
        ts = ts_all[s:e]
        i = np.searchsorted(ts, grid, side="right") - 1
        ok = i >= 0
        g, i = grid[ok], i[ok]
        age = g - ts[i]
        sog, nav = sog_all[s + i], nav_all[s + i]
        first_a = np.flatnonzero(cls_all[s:e] == "A")
        moving = (age <= ACTIVE_MS) & (sog >= MIN_SOG_KN) & ~np.isin(nav, list(AT_ANCHOR_OR_MOORED)) \
            & (ts[i] >= ts[first_a[0]])
        if moving.any():
            out.append(pd.DataFrame({"mmsi": mm[s], "made_at": g[moving], "row": s + i[moving],
                                     "last_ts": ts[i[moving]]}))
    return pd.concat(out, ignore_index=True)


def add_labels(rows: pd.DataFrame, final: pd.DataFrame, data_to: int) -> pd.DataFrame:
    rows = rows.copy()
    gaps = final[["mmsi", "start_ts", "coverage_flag"]].sort_values(["mmsi", "start_ts"])
    by_flag = {f: gaps[gaps.coverage_flag == f] for f in FLAGS}
    by_flag["any"] = gaps[gaps.coverage_flag != "own_stall"]
    for h in HORIZONS_S:
        lab = h_label(h)
        known = rows["made_at"].to_numpy() + h * 1000 + DETECT_MS <= data_to
        for flag, g in by_flag.items():
            y = _gap_in_window(rows, g, rows["last_ts"].to_numpy(), rows["made_at"].to_numpy() + h * 1000)
            rows[f"y_{flag}_{lab}"] = np.where(known, y.astype(float), np.nan)
    return rows


def _gap_in_window(rows: pd.DataFrame, gaps: pd.DataFrame, lo: np.ndarray, hi: np.ndarray) -> np.ndarray:
    """For each row, is there a gap of the row's ship with lo <= start_ts <= hi."""
    y = np.zeros(len(rows), bool)
    if gaps.empty:
        return y
    starts = {m: g["start_ts"].to_numpy() for m, g in gaps.groupby("mmsi")}
    mm = rows["mmsi"].to_numpy()
    order = np.argsort(mm, kind="stable")
    sm = mm[order]
    bounds = np.flatnonzero(np.r_[True, sm[1:] != sm[:-1], True])
    for a, b in zip(bounds[:-1], bounds[1:]):
        st = starts.get(sm[a])
        if st is None:
            continue
        idx = order[a:b]
        j = np.searchsorted(st, lo[idx], side="left")
        y[idx] = (j < len(st)) & (st[np.minimum(j, len(st) - 1)] <= hi[idx])
    return y


# ---------------------------------------------------------------- context features

def _bucket(lat: np.ndarray, lon: np.ndarray, deg: float) -> np.ndarray:
    return np.floor(lat / deg).astype(np.int64) * 100_000 + np.floor(lon / deg).astype(np.int64)


def _neigh_sum(counts: dict, keys: np.ndarray) -> np.ndarray:
    """Sum over the 3x3 bucket neighbourhood of each key (the detector looks 20 km around; a 0.2 degree bucket is
    about 22 km north-south)."""
    out = np.zeros(len(keys))
    for dlat in (-1, 0, 1):
        for dlon in (-1, 0, 1):
            k = keys + dlat * 100_000 + dlon
            out += np.array([counts.get(x, 0) for x in k], dtype=float)
    return out


def add_context(rows: pd.DataFrame, p: pd.DataFrame, first: pd.DataFrame, statics: pd.DataFrame) -> pd.DataFrame:
    rows = rows.copy()
    lat, lon = p["lat"].to_numpy()[rows["row"]], p["lon"].to_numpy()[rows["row"]]
    rows["lat_last"], rows["lon_last"] = lat, lon
    rows["bucket"] = _bucket(lat, lon, GRID_DEG)
    rows["area"] = _bucket(lat, lon, AREA_DEG)
    rows["src_digitraffic"] = (p["src"].to_numpy()[rows["row"]] == "digitraffic").astype(float)
    solar = ((rows["made_at"].to_numpy() / H_MS) + lon / 15.0) % 24
    rows["solar_sin"], rows["solar_cos"] = np.sin(2 * np.pi * solar / 24), np.cos(2 * np.pi * solar / 24)

    # Reception: distinct Class A ships and messages heard per 0.2 degree bucket, on the receive clock.
    pa = p[p["cls"] == "A"].sort_values("recv_ts")
    r_ts = pa["recv_ts"].to_numpy()
    r_b = _bucket(pa["lat"].to_numpy(), pa["lon"].to_numpy(), GRID_DEG)
    r_m = pa["mmsi"].to_numpy()
    r_area = _bucket(pa["lat"].to_numpy(), pa["lon"].to_numpy(), AREA_DEG)

    def heard(t0, t1):
        a, b = np.searchsorted(r_ts, [t0, t1], side="right")
        d = pd.DataFrame({"b": r_b[a:b], "m": r_m[a:b], "area": r_area[a:b]})
        return (d.groupby("b")["m"].nunique().to_dict(), d.groupby("b").size().to_dict(),
                d.groupby("area")["m"].nunique().to_dict())

    cols = {c: np.zeros(len(rows)) for c in ("rx_ships_10m", "rx_ships_30m", "rx_ships_2h_ago", "rx_msgs_10m",
                                            "area_gaps_6h_any", "area_gaps_6h_delib", "area_ships_1h")}
    f_det = first["detected_at"].to_numpy()
    f_area = _bucket(first["last_lat"].to_numpy(), first["last_lon"].to_numpy(), AREA_DEG)
    f_flag = first["coverage_flag"].to_numpy()
    for t, idx in rows.groupby("made_at").indices.items():
        keys, akeys = rows["bucket"].to_numpy()[idx], rows["area"].to_numpy()[idx]
        s10, m10, _ = heard(t - 10 * MIN, t)
        s30, _, _ = heard(t - 30 * MIN, t)
        s2h, _, _ = heard(t - 2 * H_MS, t - 2 * H_MS + 30 * MIN)
        _, _, a1h = heard(t - H_MS, t)
        cols["rx_ships_10m"][idx] = _neigh_sum(s10, keys)
        cols["rx_ships_30m"][idx] = _neigh_sum(s30, keys)
        cols["rx_ships_2h_ago"][idx] = _neigh_sum(s2h, keys)
        cols["rx_msgs_10m"][idx] = _neigh_sum(m10, keys)
        cols["area_ships_1h"][idx] = np.array([a1h.get(k, 0) for k in akeys], float)
        w = (f_det > t - 6 * H_MS) & (f_det <= t)
        anyc = pd.Series(f_area[w & (f_flag != "own_stall")]).value_counts().to_dict()
        dlc = pd.Series(f_area[w & (f_flag == "deliberate_candidate")]).value_counts().to_dict()
        cols["area_gaps_6h_any"][idx] = [anyc.get(k, 0) for k in akeys]
        cols["area_gaps_6h_delib"][idx] = [dlc.get(k, 0) for k in akeys]
    for k, v in cols.items():
        rows[k] = v
    rows["rx_drop"] = (rows["rx_ships_30m"] + 1) / (rows["rx_ships_2h_ago"] + 1)
    rows["area_gaps_6h_per_ship"] = rows["area_gaps_6h_any"] / (rows["area_ships_1h"] + 1)
    rows = rows.drop(columns=["area_ships_1h"])

    # This ship's own earlier gaps, as known at detection time.
    fm = first[first["coverage_flag"] != "own_stall"]
    for col, sub in (("ship_gaps_any", fm), ("ship_gaps_delib", fm[fm["coverage_flag"] == "deliberate_candidate"])):
        det = {m: np.sort(g["detected_at"].to_numpy()) for m, g in sub.groupby("mmsi")}
        rows[col] = [float(np.searchsorted(det[m], t, side="right")) if m in det else 0.0
                     for m, t in zip(rows["mmsi"].to_numpy(), rows["made_at"].to_numpy())]

    # Latest static at made_at.
    st = statics.rename(columns={"ts": "st_ts"}).sort_values("st_ts")
    r = rows.reset_index().sort_values("made_at")
    r = pd.merge_asof(r, st, left_on="made_at", right_on="st_ts", by="mmsi", direction="backward")
    r = r.sort_values("index").set_index("index")
    r.index.name = None
    for c in ("type_group", "flag_iso2"):
        r[c] = r[c].astype("string").fillna("unknown")
    return r


# ---------------------------------------------------------------- track features (shared code, in parallel)

def _track_chunk(args):
    cols, groups = args
    out = []
    for mmsi, s, e, made, static_rows in groups:
        t = F.Track.from_columns(mmsi, *(c[s:e] for c in cols), )
        for a, st in zip(made, static_rows):
            f = F.features_at(t, int(a), st)
            out.append(F.vector(f) if f else [math.nan] * len(F.FEATURE_NAMES))
    return out


def add_track_features(rows: pd.DataFrame, p: pd.DataFrame, workers: int | None = None) -> pd.DataFrame:
    rows = rows.sort_values(["mmsi", "made_at"]).reset_index(drop=True)
    cols = [p[c].to_numpy() for c in ("ts", "lat", "lon", "sog_kn", "cog_deg", "heading_deg", "nav_status", "cls")]
    mm = p["mmsi"].to_numpy()
    starts = np.flatnonzero(np.r_[True, mm[1:] != mm[:-1]])
    ends = np.r_[starts[1:], len(mm)]
    span = {mm[s]: (s, e) for s, e in zip(starts, ends)}
    groups = []
    for m, g in rows.groupby("mmsi", sort=True):
        s, e = span[m]
        # Only the fixes a feature can read: up to the last made_at, back to 6 h before the first.
        ts = cols[0][s:e]
        lo = s + int(np.searchsorted(ts, g["made_at"].min() - F.MAX_HISTORY_MS, side="left"))
        hi = s + int(np.searchsorted(ts, g["made_at"].max(), side="right"))
        static = [{"ship_type": a, "length_m": b, "draught_m": c}
                  for a, b, c in zip(g["ship_type"], g["length_m"], g["draught_m"])]
        groups.append((m, lo, hi, g["made_at"].to_numpy(), static))
    from ml.godark import MAX_THREADS
    workers = min(workers or MAX_THREADS, MAX_THREADS)
    n = max(1, len(groups) // (workers * 4))
    chunks = [groups[i:i + n] for i in range(0, len(groups), n)]
    # Each chunk carries only its own slices of the columns.
    jobs = []
    for ch in chunks:
        lo, hi = min(g[1] for g in ch), max(g[2] for g in ch)
        sl = [c[lo:hi] for c in cols]
        jobs.append((sl, [(m, s - lo, e - lo, made, st) for m, s, e, made, st in ch]))
    import multiprocessing as mp
    # forkserver: the parent has pyarrow and LightGBM threads, and fork() under threads can deadlock
    with ProcessPoolExecutor(workers, mp_context=mp.get_context("forkserver")) as ex:
        vecs = [v for part in ex.map(_track_chunk, jobs) for v in part]
    feats = pd.DataFrame(vecs, columns=F.FEATURE_NAMES)
    # The statics went into the shared features (same values), so keep only those copies.
    rows = rows.drop(columns=[c for c in rows.columns if c in feats.columns or c == "st_ts"])
    return pd.concat([rows, feats], axis=1)


# ---------------------------------------------------------------- build

def build(pos: pd.DataFrame, gap_versions: pd.DataFrame, statics: pd.DataFrame, stalls: list[tuple[int, int]],
          data_from: int, data_to: int, workers: int | None = None) -> pd.DataFrame:
    p = prepare_positions(pos)
    final, first = gap_views(gap_versions)
    grid = grid_times(data_from, data_to, stalls)
    rows = base_rows(p, grid)
    rows = add_labels(rows, final, data_to)
    rows = add_context(rows, p, first, statics_asof(statics))
    rows = add_track_features(rows, p, workers)
    rows["case_id"] = rows["mmsi"].astype(str) + "-" + rows["made_at"].astype(str)
    rows["as_of"] = rows["made_at"]
    lead = ["case_id", "mmsi", "as_of"]
    return rows[lead + [c for c in rows.columns if c not in lead]].drop(columns=["row"])


def main() -> None:
    import argparse
    from ml.godark.tiger import DEFAULT_OUT, load_positions, load_statics
    ap = argparse.ArgumentParser(description="Build the go-dark examples from the Tiger export and the replay")
    ap.add_argument("--gaps", choices=["replay", "table"], default="replay")
    ap.add_argument("--out", type=Path, default=OUT / "examples.parquet")
    a = ap.parse_args()
    t = time.time()
    pos, statics = load_positions(DEFAULT_OUT), load_statics(DEFAULT_OUT)
    meta = json.loads((OUT / "replay_meta.json").read_text())
    if a.gaps == "replay":
        versions = pd.read_parquet(OUT / "replay_gaps.parquet")
    else:
        versions = pd.read_parquet(DEFAULT_OUT / "gaps.parquet")
    ex = build(pos, versions, statics, [tuple(s) for s in meta["stalls"]], meta["data_from"], meta["data_to"])
    ex["label_source"] = a.gaps
    ex.to_parquet(a.out, index=False)
    y = {c: [int(ex[c].notna().sum()), float(ex[c].mean())] for c in ex.columns if c.startswith("y_")}
    digest = hashlib.sha256(pd.util.hash_pandas_object(ex[["case_id"]], index=False).values.tobytes()).hexdigest()
    print(f"{len(ex)} rows, {ex.mmsi.nunique()} ships, {time.time() - t:.0f} s, case hash {digest[:12]}")
    for k, v in y.items():
        print(f"  {k}: n={v[0]} rate={v[1]:.4f}")


if __name__ == "__main__":
    main()
