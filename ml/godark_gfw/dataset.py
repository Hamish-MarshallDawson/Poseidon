"""Examples for the GFW go-dark target: one row per ship and week for every ship GFW saw in our four regions (#121).

    ml/.venv/bin/python -m ml.godark_gfw.dataset [--data DIR] [--out FILE]

Input: the Parquet cache from `ml.godark_gfw.tiger` (GFW rows of Tiger `observations`). Nothing here reads Tiger.

- **Unit**: a ship's presence in a UTC Monday-to-Sunday week (region rows of `ais_presence`, one per vessel, region
  and day). `as_of` is the newest `available_ts` of that week's presence rows: the moment we could know the week.
- **Features** use only rows with `available_ts <= as_of` (the leakage clock) and `ts <= as_of`: the week's
  presence, the previous weeks' presence trend, port visits, loitering, encounters and the ship's earlier GFW gap
  events (back to 2017), plus flag, vessel type and region.
- **Labels** `y_<H>`: a GFW gap event (AIS off, likely on purpose, anywhere in the world) starts for that ship in
  `(as_of, as_of + H]`, for H = 7, 14 and 30 days. A label is null when `as_of + H` is after the label frontier (the
  newest gap start in the cache), because GFW publishes a gap only once it closes.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.godark_gfw import tiger

D = 86_400_000
WEEK = 7 * D
MONDAY0 = 4 * D                      # 1970-01-05 was a Monday
HORIZONS_DAYS = [7, 14, 30]
HORIZONS_S = [d * 86400 for d in HORIZONS_DAYS]
CATEGORICAL = ["region", "flag", "type_group"]
NUMERIC = [
    "days_present", "hours_week", "n_regions", "hours_prev4w", "weeks_seen_prev8", "weeks_since_prev",
    "hours_trend", "days_since_port", "port_visits_90d", "port_hours_90d", "loiter_90d", "loiter_hours_90d",
    "loiter_shore_km_90d", "encounters_90d", "gaps_prev_365d", "gaps_prev_all", "days_since_gap",
    "last_gap_hours", "last_gap_shore_km",
]
FEATURES = CATEGORICAL + NUMERIC
DEFAULT_OUT = tiger.DEFAULT_OUT / "examples.parquet"


def label_col(h_s: int) -> str:
    return f"y_{h_s // 86400}d"


def weeks(presence: pd.DataFrame) -> pd.DataFrame:
    p = presence.copy()
    p["week"] = (p["ts"] - MONDAY0) // WEEK * WEEK + MONDAY0
    p = p.sort_values(["mmsi", "week", "hours"], kind="stable")
    g = p.groupby(["mmsi", "week"], sort=True)
    w = g.agg(as_of=("available_ts", "max"), days_present=("ts", "nunique"), hours_week=("hours", "sum"),
              n_regions=("region", "nunique"), region=("region", "last"), flag=("flag", "last"),
              vessel_type=("vessel_type", "last")).reset_index()
    w["type_group"] = w["vessel_type"].fillna("UNKNOWN").str.upper()
    w["flag"] = w["flag"].fillna("UNK")
    w = w.drop(columns="vessel_type")
    # previous weeks of the same ship (all published long before this week's as_of)
    w = w.sort_values(["mmsi", "week"], kind="stable").reset_index(drop=True)
    prev_week = w.groupby("mmsi")["week"].shift()
    w["weeks_since_prev"] = (w["week"] - prev_week) / WEEK
    hp, sp = [], []
    for _, idx in w.groupby("mmsi").indices.items():
        wk, hr = w["week"].to_numpy()[idx], w["hours_week"].to_numpy()[idx]
        lo4 = np.searchsorted(wk, wk - 4 * WEEK)
        lo8 = np.searchsorted(wk, wk - 8 * WEEK)
        cs = np.concatenate([[0.0], np.cumsum(hr)])
        pos = np.arange(len(idx))
        hp.append(pd.Series(cs[pos] - cs[lo4], index=idx))
        sp.append(pd.Series(pos - lo8, index=idx))
    w["hours_prev4w"] = pd.concat(hp).sort_index()
    w["weeks_seen_prev8"] = pd.concat(sp).sort_index()
    w["hours_trend"] = w["hours_week"] / 7 - w["hours_prev4w"] / 28
    return w


def _by_ship(df: pd.DataFrame, cols: list[str]) -> dict[int, dict[str, np.ndarray]]:
    if df.empty:
        return {}
    df = df.sort_values(["mmsi", "ts"], kind="stable")
    out = {}
    for m, idx in df.groupby("mmsi").indices.items():
        out[int(m)] = {c: df[c].to_numpy()[idx] for c in cols}
    return out


def _f(a) -> np.ndarray:
    return pd.to_numeric(pd.Series(a), errors="coerce").to_numpy(float)


def event_features(w: pd.DataFrame, events: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Per ship-week counts and recency of each event kind, from rows known at as_of only."""
    ev = {k: _by_ship(v, [c for c in ("ts", "end_ts", "available_ts", "hours", "shore_km", "off_shore_km")
                          if c in v]) for k, v in events.items()}
    out = {c: np.full(len(w), np.nan) for c in NUMERIC[NUMERIC.index("days_since_port"):]}
    mm, asof = w["mmsi"].to_numpy(), w["as_of"].to_numpy()
    for m, idx in w.groupby("mmsi").indices.items():
        a = asof[idx][:, None].astype(float)
        for kind, cnt, hrs in (("port_visit", "port_visits_90d", "port_hours_90d"),
                               ("loitering", "loiter_90d", "loiter_hours_90d"),
                               ("encounter", "encounters_90d", None)):
            e = ev.get(kind, {}).get(int(m))
            if e is None:
                out[cnt][idx] = 0
                if hrs:
                    out[hrs][idx] = 0
                continue
            ts, av = _f(e["ts"])[None, :], _f(e["available_ts"])[None, :]
            known = (av <= a) & (ts <= a)
            in90 = known & (ts >= a - 90 * D)
            out[cnt][idx] = in90.sum(1)
            h = np.nan_to_num(_f(e["hours"]))[None, :]
            if hrs:
                out[hrs][idx] = (in90 * h).sum(1)
            if kind == "port_visit":
                end = _f(e["end_ts"])[None, :]
                end = np.where(np.isnan(end), a, np.minimum(end, a))
                last = np.where(known, end, -np.inf).max(1)
                out["days_since_port"][idx] = np.where(np.isfinite(last), (a[:, 0] - last) / D, np.nan)
            if kind == "loitering":
                sk = _f(e["shore_km"])[None, :]
                with np.errstate(invalid="ignore", divide="ignore"):
                    s = np.where(in90 & ~np.isnan(sk), sk, 0).sum(1) / (in90 & ~np.isnan(sk)).sum(1)
                out["loiter_shore_km_90d"][idx] = s
        e = ev.get("gap", {}).get(int(m))
        if e is None:
            out["gaps_prev_365d"][idx] = 0
            out["gaps_prev_all"][idx] = 0
            continue
        ts, av = _f(e["ts"])[None, :], _f(e["available_ts"])[None, :]
        known = (av <= a) & (ts <= a)
        out["gaps_prev_all"][idx] = known.sum(1)
        out["gaps_prev_365d"][idx] = (known & (ts >= a - 365 * D)).sum(1)
        last_i = np.where(known, np.arange(ts.shape[1])[None, :], -1).max(1)   # events sorted by ts
        has = last_i >= 0
        li = np.maximum(last_i, 0)
        out["days_since_gap"][idx] = np.where(has, (a[:, 0] - ts[0, li]) / D, np.nan)
        out["last_gap_hours"][idx] = np.where(has, _f(e["hours"])[li], np.nan)
        out["last_gap_shore_km"][idx] = np.where(has, _f(e["off_shore_km"])[li], np.nan)
    del mm
    return pd.DataFrame(out, index=w.index)


def labels(w: pd.DataFrame, gaps: pd.DataFrame, frontier: int) -> pd.DataFrame:
    gb = {int(m): np.sort(g["ts"].to_numpy()) for m, g in gaps.groupby("mmsi")}
    out = pd.DataFrame(index=w.index)
    asof = w["as_of"].to_numpy()
    for h in HORIZONS_DAYS:
        y = np.zeros(len(w))
        for m, idx in w.groupby("mmsi").indices.items():
            t = gb.get(int(m))
            if t is None:
                continue
            a = asof[idx]
            y[idx] = (np.searchsorted(t, a + h * D, side="right") - np.searchsorted(t, a, side="right")) > 0
        y[asof + h * D > frontier] = np.nan
        out[f"y_{h}d"] = y
    return out


def build(data: Path = tiger.DEFAULT_OUT) -> tuple[pd.DataFrame, dict]:
    pres = tiger.load("ais_presence", data)
    gaps = tiger.load("gap", data)
    events = {k: tiger.load(k, data) for k in ("port_visit", "loitering", "encounter")}
    events["gap"] = gaps
    w = weeks(pres)
    w = pd.concat([w, event_features(w, events)], axis=1)
    frontier = int(gaps["ts"].max())
    w = pd.concat([w, labels(w, gaps, frontier)], axis=1)
    w["mmsi"] = w["mmsi"].astype("int64")
    w["as_of"] = w["as_of"].astype("int64")
    w.insert(0, "case_id", w["mmsi"].astype(str) + ":" + pd.to_datetime(w["week"], unit="ms").dt.strftime("%Y-%m-%d"))
    cols = ["case_id", "mmsi", "as_of", "week"] + FEATURES + [f"y_{h}d" for h in HORIZONS_DAYS]
    w = w[cols].sort_values(["as_of", "case_id"], kind="stable").reset_index(drop=True)
    iso = lambda ms: pd.Timestamp(int(ms), unit="ms", tz="UTC").isoformat(timespec="minutes")  # noqa: E731
    info = {"rows": len(w), "ships": int(w["mmsi"].nunique()),
            "presence_from": iso(pres["ts"].min()), "presence_to": iso(pres["ts"].max()),
            "gaps_from": iso(gaps["ts"].min()), "label_frontier": iso(frontier),
            "manifest": json.loads((data / "manifest.json").read_text()) if (data / "manifest.json").exists() else {},
            "labels": {f"y_{h}d": {"labelled": int(w[f"y_{h}d"].notna().sum()), "positives": int(w[f"y_{h}d"].sum())}
                       for h in HORIZONS_DAYS}}
    return w, info


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=Path, default=tiger.DEFAULT_OUT)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    w, info = build(a.data)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    w.to_parquet(a.out, index=False)
    info.pop("manifest")
    a.out.with_suffix(".json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info))


if __name__ == "__main__":
    main()
