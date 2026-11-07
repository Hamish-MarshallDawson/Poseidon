#!/usr/bin/env python3
"""AIS availability in t-model/t-match's Kattegat AOI at the S1C image times (2026-11-01)."""
import csv, os
from collections import defaultdict
from datetime import datetime
HERE = os.path.dirname(os.path.abspath(__file__))
F = os.path.join(HERE, "..", "..", "data", "t-ais-history", "day_2026-11-01",
                 "classa_1630_1700Z.csv")
AOI = (56.30, 56.70, 12.25, 12.85)   # t-model's AOI (lat0, lat1, lon0, lon1)
SLICE_AREA = (55.97, 57.86, 12.16, 16.73)  # S1C 16:44:27 slice bbox
T = [datetime(2026, 11, 1, 16, 43, 49), datetime(2026, 11, 1, 16, 44, 14),
     datetime(2026, 11, 1, 16, 44, 39), datetime(2026, 11, 1, 16, 45, 4)]
rows = list(csv.DictReader(open(F)))
def inb(r, b):
    la, lo = float(r["lat"]), float(r["lon"])
    return b[0] <= la <= b[1] and b[2] <= lo <= b[3]
for label, box in (("AOI 12.25-12.85E/56.30-56.70N", AOI), ("slice bbox 12.16-16.73E/55.97-57.86N", SLICE_AREA)):
    sub = [r for r in rows if inb(r, box)]
    v = {r["mmsi"] for r in sub}
    moving = {r["mmsi"] for r in sub if float(r["sog"] or 0) >= 3}
    print(f"{label}: {len(sub)} rows, {len(v)} vessels ({len(moving)} with sog>=3 kn)")
    if not sub:
        continue
    byv = defaultdict(list)
    for r in sub:
        byv[r["mmsi"]].append(datetime.strptime(r["ts_utc"], "%Y-%m-%dT%H:%M:%SZ"))
    for t in T:
        ages = [min(abs((t - x).total_seconds()) for x in ts) for ts in byv.values()]
        ages.sort()
        n60 = sum(1 for a in ages if a <= 60)
        print(f"  image time {t:%H:%M:%S}Z: vessels with a fix within 60 s: {n60}/{len(ages)}, "
              f"median staleness {ages[len(ages)//2]:.0f} s")
