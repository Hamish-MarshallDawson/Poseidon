"""Examples for the fishing-in-protected-areas target: one row per fishing vessel and UTC week (#157).

    ml/.venv/bin/python -m ml.fishing.dataset [--data DIR] [--out FILE]

Input: the GFW fishing-event cache from `ml.fishing.fetch`, plus (optional, read-only and already local) the GFW port
visits and presence rows `ml.godark_gfw.tiger` cached from Tiger, for recent port visits and gear type.

- **Unit**: a vessel and a UTC Monday-to-Sunday week, for every vessel with at least one *known* fishing event in our
  regions that started in the 8 weeks before the week. `as_of` = the Monday 00:00 UTC that starts the week.
- **Features** use only events with `available_ts <= as_of` (GFW publishes an event about 4 days after it ends):
  fishing hours inside and outside marine protected areas (28 and 90 days), shares of events inside an MPA, a no-take
  MPA, the 12 nm zone, straddling an EEZ border (more than one EEZ tagged), flagged `potentialRisk`, recency, weeks
  active, distance from shore and speed, plus flag, gear type, latest public authorisation status, region, and port
  visits in our regions (count in 28 days, days since the last).
- **Labels**: `y_mpa_7d` = the vessel has a fishing event starting in `[as_of, as_of + 7 d)` inside an MPA (`mpa` or
  `mpa_no_take` non-empty), 0 if it fished only outside or not at all. `y_risk_next` (reported, not trained) = its next
  fishing event after `as_of` carries `potentialRisk = true`. Labels are null past the frontier (newest event start in
  the cache minus 2 days, since events still running are not published yet).
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from ml.fishing import fetch
from ml.godark_gfw.tiger import DEFAULT_OUT as GODARK_GFW   # read-only Tiger cache: port visits, presence (gear)

D = 86_400_000
WEEK = 7 * D
MONDAY0 = 4 * D                      # 1970-01-05 was a Monday
HORIZON_S = 7 * 86400
LABEL = "y_mpa_7d"
LOOKBACK_WEEKS = 8
CATEGORICAL = ["region", "flag", "gear", "auth_status"]
NUMERIC = [
    "events_28d", "events_90d", "hours_in_mpa_28d", "hours_out_mpa_28d", "hours_in_mpa_90d", "hours_out_mpa_90d",
    "share_mpa_90d", "share_no_take_90d", "share_12nm_90d", "share_border_90d", "share_risk_90d",
    "mpa_events_ever", "events_ever", "days_since_event", "days_since_mpa", "weeks_active_prev8",
    "shore_km_90d", "speed_kn_90d", "port_visits_28d", "days_since_port", "month",
]
FEATURES = CATEGORICAL + NUMERIC
DEFAULT_OUT = fetch.DEFAULT_OUT / "examples.parquet"


def _nonempty(s: pd.Series) -> np.ndarray:
    return s.fillna("").astype(str).str.len().to_numpy() > 0


def prepare(ev: pd.DataFrame) -> pd.DataFrame:
    ev = ev.copy()
    ev["in_mpa"] = _nonempty(ev["mpa"]) | _nonempty(ev["mpa_no_take"])
    ev["no_take"] = _nonempty(ev["mpa_no_take"])
    ev["in_12nm"] = _nonempty(ev["eez12nm"])
    ev["border"] = ev["eez"].fillna("").astype(str).str.count(r"\|").to_numpy() >= 1
    ev["risk"] = ev["potential_risk"].fillna(False).astype(bool)
    ev["hours"] = pd.to_numeric(ev["hours"], errors="coerce").fillna(0.0)
    return ev.sort_values(["mmsi", "ts"], kind="stable").reset_index(drop=True)


def cases(ev: pd.DataFrame) -> pd.DataFrame:
    """Vessel-weeks with a known event that started in the previous LOOKBACK_WEEKS weeks."""
    out = []
    for m, g in ev.groupby("mmsi", sort=True):
        # weeks whose Monday falls after an event became known and within the lookback of its start
        first = ((g["available_ts"].to_numpy() - MONDAY0 + WEEK - 1) // WEEK) * WEEK + MONDAY0
        last = ((g["ts"].to_numpy() - MONDAY0) // WEEK + LOOKBACK_WEEKS) * WEEK + MONDAY0
        wk = set()
        for a, b in zip(first, last):
            wk.update(range(int(a), int(b) + 1, WEEK))
        out.append(pd.DataFrame({"mmsi": m, "as_of": sorted(wk)}))
    return pd.concat(out, ignore_index=True) if out else pd.DataFrame(columns=["mmsi", "as_of"])


def _static(ev: pd.DataFrame, gfw_cache: Path) -> tuple[dict, dict]:
    """Per vessel: flag (most frequent) and gear type from the GFW presence cache (static, not time-dependent)."""
    flag = ev.groupby("mmsi")["flag"].agg(lambda s: s.value_counts().index[0]).to_dict()
    gear = {}
    pdir = gfw_cache / "ais_presence"
    if pdir.exists():
        cols = ["mmsi", "geartype"]
        p = pd.concat([pd.read_parquet(f, columns=cols) for f in sorted(pdir.glob("*.parquet"))], ignore_index=True)
        p = p[p["mmsi"].isin(set(flag)) & p["geartype"].notna()]
        gear = p.groupby("mmsi")["geartype"].agg(lambda s: s.value_counts().index[0]).to_dict()
    return flag, gear


def _ports(gfw_cache: Path) -> dict[int, tuple[np.ndarray, np.ndarray, np.ndarray]]:
    pdir = gfw_cache / "port_visit"
    if not pdir.exists():
        return {}
    p = pd.concat([pd.read_parquet(f, columns=["mmsi", "ts", "end_ts", "available_ts"])
                   for f in sorted(pdir.glob("*.parquet"))], ignore_index=True)
    p = p.sort_values(["mmsi", "ts"])
    return {int(m): (g["ts"].to_numpy(), g["end_ts"].to_numpy(float), g["available_ts"].to_numpy())
            for m, g in p.groupby("mmsi")}


def features(c: pd.DataFrame, ev: pd.DataFrame, gfw_cache: Path = GODARK_GFW) -> pd.DataFrame:
    flag, gear = _static(ev, gfw_cache)
    ports = _ports(gfw_cache)
    n = len(c)
    out = {k: np.full(n, np.nan) for k in NUMERIC}
    region = np.full(n, "", dtype=object)
    auth = np.full(n, "unknown", dtype=object)
    by = {int(m): g for m, g in ev.groupby("mmsi")}
    for m, idx in c.groupby("mmsi").indices.items():
        g = by[int(m)]
        a = c["as_of"].to_numpy()[idx][:, None].astype(float)
        ts, av = g["ts"].to_numpy(float)[None, :], g["available_ts"].to_numpy(float)[None, :]
        known = av <= a
        w28, w90 = known & (ts >= a - 28 * D), known & (ts >= a - 90 * D)
        hrs, mpa = g["hours"].to_numpy()[None, :], g["in_mpa"].to_numpy()[None, :]
        n90 = w90.sum(1)
        out["events_28d"][idx] = w28.sum(1)
        out["events_90d"][idx] = n90
        out["hours_in_mpa_28d"][idx] = (w28 * hrs * mpa).sum(1)
        out["hours_out_mpa_28d"][idx] = (w28 * hrs * ~mpa).sum(1)
        out["hours_in_mpa_90d"][idx] = (w90 * hrs * mpa).sum(1)
        out["hours_out_mpa_90d"][idx] = (w90 * hrs * ~mpa).sum(1)
        with np.errstate(invalid="ignore", divide="ignore"):
            for k, col in (("share_mpa_90d", "in_mpa"), ("share_no_take_90d", "no_take"), ("share_12nm_90d", "in_12nm"),
                           ("share_border_90d", "border"), ("share_risk_90d", "risk")):
                out[k][idx] = (w90 * g[col].to_numpy()[None, :]).sum(1) / n90
            for k, col in (("shore_km_90d", "shore_km"), ("speed_kn_90d", "avg_speed_kn")):
                v = pd.to_numeric(g[col], errors="coerce").to_numpy(float)[None, :]
                ok = w90 & ~np.isnan(v)
                out[k][idx] = np.where(ok, v, 0).sum(1) / ok.sum(1)
        out["mpa_events_ever"][idx] = (known & mpa).sum(1)
        out["events_ever"][idx] = known.sum(1)
        last = np.where(known, ts, -np.inf).max(1)
        out["days_since_event"][idx] = np.where(np.isfinite(last), (a[:, 0] - last) / D, np.nan)
        lastm = np.where(known & mpa, ts, -np.inf).max(1)
        out["days_since_mpa"][idx] = np.where(np.isfinite(lastm), (a[:, 0] - lastm) / D, np.nan)
        wk = (ts - MONDAY0) // WEEK
        aw = (a - MONDAY0) // WEEK
        act = known & (wk >= aw - LOOKBACK_WEEKS)
        out["weeks_active_prev8"][idx] = [len(np.unique(wk[0][r])) for r in act]
        # latest known authorisation status and region with most known events in 90 days
        li = np.where(known, np.arange(ts.shape[1])[None, :], -1).max(1)
        st, rg = g["authorization_status"].to_numpy(), g["region"].to_numpy()
        auth[idx] = np.where(li >= 0, st[np.maximum(li, 0)], "unknown")
        for j, row in zip(idx, np.where(n90[:, None] > 0, w90, known)):
            vals = rg[row]
            region[j] = pd.Series(vals).value_counts().index[0] if len(vals) else rg[0]
        pv = ports.get(int(m))
        if pv is None:
            out["port_visits_28d"][idx] = 0
        else:
            pts, pend, pav = pv[0][None, :], pv[1][None, :], pv[2][None, :]
            pk = (pav <= a) & (pts <= a)
            out["port_visits_28d"][idx] = (pk & (pts >= a - 28 * D)).sum(1)
            e = np.where(np.isnan(pend), a, np.minimum(pend, a))
            lp = np.where(pk, e, -np.inf).max(1)
            out["days_since_port"][idx] = np.where(np.isfinite(lp), (a[:, 0] - lp) / D, np.nan)
    f = pd.DataFrame(out, index=c.index)
    f["month"] = pd.to_datetime(c["as_of"], unit="ms").dt.month.to_numpy()
    f["region"] = region
    f["auth_status"] = auth
    f["flag"] = c["mmsi"].map(flag).fillna("UNK").to_numpy()
    f["gear"] = c["mmsi"].map(gear).fillna("UNKNOWN").astype(str).str.upper().to_numpy()
    return f


def labels(c: pd.DataFrame, ev: pd.DataFrame, frontier: int) -> pd.DataFrame:
    y_mpa = np.zeros(len(c))
    y_any = np.zeros(len(c))
    y_risk = np.full(len(c), np.nan)
    by = {int(m): g for m, g in ev.groupby("mmsi")}
    for m, idx in c.groupby("mmsi").indices.items():
        g = by[int(m)]
        ts, mpa, risk = g["ts"].to_numpy(), g["in_mpa"].to_numpy(), g["risk"].to_numpy()
        a = c["as_of"].to_numpy()[idx]
        lo, hi = np.searchsorted(ts, a, "left"), np.searchsorted(ts, a + WEEK, "left")
        cm = np.concatenate([[0], np.cumsum(mpa)])
        y_mpa[idx] = (cm[hi] - cm[lo]) > 0
        y_any[idx] = hi > lo
        nxt = lo < len(ts)
        y_risk[idx[nxt]] = risk[lo[nxt]]
    late = c["as_of"].to_numpy() + WEEK > frontier
    y_mpa[late] = np.nan
    y_any[late] = np.nan
    y_risk[late] = np.nan
    return pd.DataFrame({LABEL: y_mpa, "y_fish_7d": y_any, "y_risk_next": y_risk}, index=c.index)


def build(data: Path = fetch.DEFAULT_OUT, gfw_cache: Path = GODARK_GFW) -> tuple[pd.DataFrame, dict]:
    ev = prepare(fetch.load(data))
    frontier = int(ev["ts"].max()) - 2 * D
    c = cases(ev)
    c = c[c["as_of"] <= frontier].reset_index(drop=True)
    w = pd.concat([c, features(c, ev, gfw_cache), labels(c, ev, frontier)], axis=1)
    w["mmsi"] = w["mmsi"].astype("int64")
    w["as_of"] = w["as_of"].astype("int64")
    w.insert(0, "case_id", w["mmsi"].astype(str) + ":" + pd.to_datetime(w["as_of"], unit="ms").dt.strftime("%Y-%m-%d"))
    cols = ["case_id", "mmsi", "as_of"] + FEATURES + [LABEL, "y_fish_7d", "y_risk_next"]
    w = w[cols].sort_values(["as_of", "case_id"], kind="stable").reset_index(drop=True)
    iso = lambda ms: pd.Timestamp(int(ms), unit="ms", tz="UTC").isoformat(timespec="minutes")  # noqa: E731
    lab = w[w[LABEL].notna()]
    info = {"rows": len(w), "vessels": int(w["mmsi"].nunique()), "events": len(ev),
            "events_from": iso(ev["ts"].min()), "events_to": iso(ev["ts"].max()), "label_frontier": iso(frontier),
            "events_in_mpa": float(ev["in_mpa"].mean()), "events_risk": float(ev["risk"].mean()),
            "labels": {k: {"labelled": int(w[k].notna().sum()), "positives": int(w[k].sum()),
                           "rate": float(w[k].mean())} for k in (LABEL, "y_fish_7d", "y_risk_next")},
            "positive_vessels": int(lab.loc[lab[LABEL] > 0, "mmsi"].nunique()),
            "by_region": {r: {"rows": int(len(g)), "rate": float(g[LABEL].mean())} for r, g in lab.groupby("region")}}
    return w, info


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--data", type=Path, default=fetch.DEFAULT_OUT)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    a = ap.parse_args()
    w, info = build(a.data)
    a.out.parent.mkdir(parents=True, exist_ok=True)
    w.to_parquet(a.out, index=False)
    a.out.with_suffix(".json").write_text(json.dumps(info, indent=1))
    print(json.dumps(info, indent=1))


if __name__ == "__main__":
    main()
