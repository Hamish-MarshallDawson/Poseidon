"""Compare rslearn detector output against Danish Class A AIS at the image time.

Uses t-ais-history's extract: data/t-ais-history/day_2026-11-01/classa_1630_1700Z.csv
(Class A position reports, 16:30-17:00Z, one day). Linear-interpolates each MMSI to the
Sentinel-1 target scene time 16:44:39Z, then matches detector output within a radius.
"""

import json
import sys

import numpy as np
import pandas as pd

W = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave"
AIS = f"{W}/data/t-ais-history/day_2026-11-01/classa_1630_1700Z.csv"
T = pd.Timestamp("2026-11-01T16:44:39Z")
AOIS = {
    "aoi1": (12.25, 56.30, 12.85, 56.70),
    "aoi3": (12.60, 56.30, 13.20, 56.70),
}


def interp_positions(df: pd.DataFrame, t: pd.Timestamp) -> pd.DataFrame:
    rows = []
    for mmsi, g in df.sort_values("ts_utc").groupby("mmsi"):
        if len(g) < 2:
            continue
        ts = g["ts_utc"].values.astype("datetime64[s]").astype(np.int64)
        tt = t.value // 10**9
        if ts[0] > tt or ts[-1] < tt:
            continue
        lon = np.interp(tt, ts, g["lon"].values)
        lat = np.interp(tt, ts, g["lat"].values)
        sog = np.interp(tt, ts, g["sog"].values)
        last = g.iloc[-1]
        rows.append(
            {
                "mmsi": mmsi,
                "lon": lon,
                "lat": lat,
                "sog": sog,
                "name": last.get("name"),
                "ship_type": last.get("ship_type"),
                "length": last.get("length"),
                "width": last.get("width"),
                "draught": last.get("draught"),
                "destination": last.get("destination"),
                "imo": last.get("imo"),
            }
        )
    return pd.DataFrame(rows)


def haversine_m(lon1, lat1, lon2, lat2):
    r = 6371000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dp = p2 - p1
    dl = np.radians(np.asarray(lon2) - np.asarray(lon1))
    a = np.sin(dp / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))


def main() -> None:
    df = pd.read_csv(AIS, parse_dates=["ts_utc"])
    print(f"AIS rows {len(df)} vessels {df.mmsi.nunique()} "
          f"time {df.ts_utc.min()} .. {df.ts_utc.max()}", flush=True)
    pos = interp_positions(df, T)
    print(f"vessels with a bracketing fix across {T}: {len(pos)}", flush=True)
    for name, (lon0, lat0, lon1, lat1) in AOIS.items():
        sel = pos[(pos.lon >= lon0) & (pos.lon <= lon1) & (pos.lat >= lat0)
                  & (pos.lat <= lat1)]
        print(f"\n== {name} {lon0}-{lon1}E {lat0}-{lat1}N: "
              f"{len(sel)} AIS vessels at image time "
              f"({(sel.sog >= 3).sum()} moving >=3 kn, "
              f"{(sel.sog < 0.5).sum()} near-stationary)")
        if len(sel):
            print(sel[["mmsi", "name", "ship_type", "length", "sog", "lon",
                       "lat", "destination"]].to_string(index=False))
        dets_path = f"{W}/data/t-model/summary_{name}.json"
        try:
            dets = json.load(open(dets_path))["detections"]
        except FileNotFoundError:
            print("  (no detector summary yet)")
            continue
        print(f"  detections {len(dets)}")
        unmatched_dets, matched = [], []
        used = set()
        for d in dets:
            if not sel.size:
                unmatched_dets.append(d)
                continue
            dist = haversine_m(d["longitude"], d["latitude"], sel.lon.values,
                               sel.lat.values)
            j = int(np.argmin(dist))
            if dist[j] <= 1000:
                matched.append((d, sel.iloc[j], float(dist[j])))
                used.add(int(sel.index[j]))
            else:
                unmatched_dets.append(d)
        unmatched_ais = [r for i, r in sel.iterrows() if int(i) not in used]
        print(f"  matched within 1 km: {len(matched)} / {len(dets)} detections")
        for d, a, dist in matched:
            print(f"    {dist:6.0f} m  model len {d['attributes']['length']:.0f} m "
                  f"{d['attributes']['vessel_type']} score {d['score']:.2f} "
                  f"-> AIS {a['name']} len {a['length']} type {a['ship_type']} "
                  f"sog {a['sog']:.1f}")
        for d in unmatched_dets:
            print(f"    UNMATCHED radar {d['longitude']:.4f},{d['latitude']:.4f} "
                  f"score {d['score']:.2f} len {d['attributes']['length']:.0f} m")
        for a in unmatched_ais:
            print(f"    UNMATCHED AIS {a['mmsi']} {a['name']} len {a['length']} "
                  f"type {a['ship_type']} sog {a['sog']:.1f}")


if __name__ == "__main__":
    main()
