#!/usr/bin/env python3
"""Position quality + coverage geometry from the 30-minute Class A extract."""
import csv
import math
import os
import statistics as st
from collections import Counter, defaultdict
from datetime import datetime

HERE = os.path.dirname(os.path.abspath(__file__))
DAY = os.path.join(HERE, "..", "..", "data", "t-ais-history", "day_2026-11-01")
WIN = os.path.join(DAY, "classa_1630_1700Z.csv")


def hav_nm(a, b, c, d):
    r = 3440.065
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = p2 - p1, math.radians(d - b)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(h))


rows = list(csv.DictReader(open(WIN)))
print("window rows:", len(rows), "vessels:", len({r["mmsi"] for r in rows}))

lats = [float(r["lat"]) for r in rows]
lons = [float(r["lon"]) for r in rows]
print("lat range %.2f..%.2f  lon range %.2f..%.2f" % (min(lats), max(lats), min(lons), max(lons)))

cells = Counter((round(float(r["lat"]), 1), round(float(r["lon"]), 1)) for r in rows)
vper = defaultdict(set)
for r in rows:
    vper[(round(float(r["lat"]), 1), round(float(r["lon"]), 1))].add(r["mmsi"])
print("\ntop 0.1-degree cells by messages / distinct vessels (30 min):")
for c, n in cells.most_common(10):
    print(f"  {c} msgs {n:6d} vessels {len(vper[c]):4d}")

# implied speed between consecutive fixes, per vessel
byv = defaultdict(list)
for r in rows:
    byv[r["mmsi"]].append((r["ts_utc"], float(r["lat"]), float(r["lon"]),
                           float(r["sog"] or 0)))
imp, jumps = [], []
for m, lst in byv.items():
    lst.sort()
    for (t0, a0, b0, s0), (t1, a1, b1, s1) in zip(lst, lst[1:]):
        dt = (datetime.strptime(t1, "%Y-%m-%dT%H:%M:%SZ") -
              datetime.strptime(t0, "%Y-%m-%dT%H:%M:%SZ")).total_seconds()
        if dt <= 0:
            continue
        d = hav_nm(a0, b0, a1, b1)
        kn = d / (dt / 3600.0)
        imp.append((kn, dt, d, s0, s1, m))
print("\npairwise fixes analysed:", len(imp))
ks = [x[0] for x in imp]
print("implied speed kn: p50 %.1f p90 %.1f p99 %.1f max %.0f" % (
    st.median(ks), sorted(ks)[int(.9*len(ks))], sorted(ks)[int(.99*len(ks))], max(ks)))
for thr in (40, 60, 100):
    n = sum(1 for k in ks if k > thr)
    print(f"  fixes implying > {thr:3d} kn: {n:5d} ({100*n/len(ks):.3f}%)")

# discrepancy between reported SOG and implied speed for short intervals
short = [x for x in imp if x[1] <= 12]
print("\nonly intervals <= 12 s (n=%d): p50 %.1f p95 %.1f kn" % (
    len(short), st.median([x[0] for x in short]),
    sorted(x[0] for x in short)[int(.95*len(short))]))

fast = sorted(imp, reverse=True)[:8]
print("\nworst implied-speed jumps (candidates for GPS/spoof error):")
for k, dt, d, s0, s1, m in fast:
    print(f"  mmsi {m} {k:8.0f} kn over {dt:5.0f}s ({d:6.1f} nm), sog {s0}->{s1}")

# one-hour silence inside the window, per vessel: vessels present at 16:30 but not at 16:55
first = {r["mmsi"] for r in rows if r["ts_utc"] <= "2026-11-01T16:31:00Z"}
last = {r["mmsi"] for r in rows if r["ts_utc"] >= "2026-11-01T16:54:00Z"}
print("\nvessels seen 16:30-16:31: %d; seen 16:54-16:55: %d; in both: %d"
      % (len(first), len(last), len(first & last)))

# spatial normalisation: gaps per cell vs traffic per cell
gaps = list(csv.DictReader(open(os.path.join(DAY, "gaps.csv"))))
gcells = Counter()
for g in gaps:
    try:
        gcells[(round(float(g["lat"]), 1), round(float(g["lon"]), 1))] += 1
    except ValueError:
        pass
print("\n0.1-degree cells: gap starts, all day (top 10) vs same-cell 30-min traffic:")
for c, n in gcells.most_common(10):
    print(f"  {c} gaps {n:3d}  30-min msgs {cells.get(c,0):6d}")
