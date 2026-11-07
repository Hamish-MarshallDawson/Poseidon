"""How stale is the closest AIS fix to a Sentinel-1 image time?

Reads the Danish Maritime Authority day file already downloaded by t-match /
t-ais-history (never re-download, never modify it), and for Class A vessels
under way inside the Denmark scene box, measures:
  - the inter-report interval distribution,
  - the time from the scene time (S1C ascending 2026-11-01 16:43:37Z, the first
    of four 25 s slices) to the nearest reported fix per vessel,
  - the position error that staleness implies at that vessel's reported speed.

Usage: python3 -I ais_interval_budget.py <path-to-aisdk-2026-11-01.zip>
"""

import sys
import zipfile
from datetime import datetime, timedelta

ZIP = sys.argv[1]
SCENE = datetime(2026, 11, 1, 16, 43, 37)          # UTC, first slice start
W0, W1 = datetime(2026, 11, 1, 16, 0, 0), datetime(2026, 11, 1, 17, 30, 0)
BBOX = (9.0, 54.0, 14.0, 58.0)                      # lon0, lat0, lon1, lat1
FMT = "%d/%m/%Y %H:%M:%S"

rows = {}       # mmsi -> list of (dt, lat, lon, sog)
n_lines = n_win = 0

with zipfile.ZipFile(ZIP) as z:
    name = z.namelist()[0]
    with z.open(name) as f:
        header = f.readline()
        for raw in f:
            n_lines += 1
            line = raw.decode("utf-8", "replace")
            # cheap time filter first: characters 0-18 are "dd/mm/yyyy HH:MM:SS"
            if line[:10] != "01/11/2026" or line[11:13] not in ("16", "17"):
                continue
            p = line.split(",")
            if len(p) < 10 or p[1] != "Class A":
                continue
            try:
                lat, lon = float(p[3]), float(p[4])
                sog = float(p[7]) if p[7] not in ("", "Unknown") else None
            except ValueError:
                continue
            if not (BBOX[0] <= lon <= BBOX[2] and BBOX[1] <= lat <= BBOX[3]):
                continue
            if sog is None or sog < 3.0:      # under way only
                continue
            try:
                dt = datetime.strptime(p[0], FMT)
            except ValueError:
                continue
            if not (W0 <= dt <= W1):
                continue
            n_win += 1
            rows.setdefault(p[2], []).append((dt, lat, lon, sog))

print("lines scanned: %d, class A under-way fixes in box+window: %d, vessels: %d"
      % (n_lines, n_win, len(rows)))

intervals = []
dup_pairs = 0
stale = []          # (seconds to nearest fix, speed kn)
for mmsi, fixes in rows.items():
    fixes.sort()
    for a, b in zip(fixes, fixes[1:]):
        d = (b[0] - a[0]).total_seconds()
        if d == 0:
            dup_pairs += 1
        else:
            intervals.append(d)
    before = [f for f in fixes if f[0] <= SCENE]
    after = [f for f in fixes if f[0] > SCENE]
    cands = []
    if before:
        cands.append((SCENE - before[-1][0]).total_seconds())
    if after:
        cands.append((after[0][0] - SCENE).total_seconds())
    if cands:
        stale.append((min(cands), before[-1][3] if before else after[0][3]))

intervals.sort()
stale.sort()


def pct(v, q):
    if not v:
        return float("nan")
    return v[min(len(v) - 1, int(q * (len(v) - 1)))]


print("consecutive fixes with an identical timestamp (duplicate receptions): "
      "%d of %d pairs (%.0f%%)"
      % (dup_pairs, dup_pairs + len(intervals), 100.0 * dup_pairs / (dup_pairs + len(intervals))))
print()
print("inter-report intervals, distinct timestamps only (s), Class A under way:")
print("  n=%d  p10=%.0f  median=%.0f  p90=%.0f  p99=%.0f  max=%.0f"
      % (len(intervals), pct(intervals, .1), pct(intervals, .5), pct(intervals, .9),
         pct(intervals, .99), intervals[-1] if intervals else float("nan")))
print()
print("seconds from the image time to the nearest fix, per vessel:")
if not stale:
    raise SystemExit("no fixes near the scene time")
print("  n=%d  p10=%.0f  median=%.0f  p90=%.0f  p99=%.0f  max=%.0f"
      % (len(stale), pct([s[0] for s in stale], .1), pct([s[0] for s in stale], .5),
         pct([s[0] for s in stale], .9), pct([s[0] for s in stale], .99),
         max(s[0] for s in stale)))
print()
print("vessels whose nearest fix is older/further than a threshold:")
for thr in (10, 20, 30, 60, 120, 300):
    k = sum(1 for s, _ in stale if s > thr)
    print("  > %4d s: %4d of %4d (%.0f%%)" % (thr, k, len(stale), 100.0 * k / len(stale)))
print()
print("implied position error at the image time, metres (speed x staleness):")
for lo, hi in ((3, 8), (8, 12), (12, 16), (16, 25)):
    sel = [s * (sp * 0.514444) for s, sp in stale if lo <= sp < hi]
    if sel:
        sel.sort()
        print("  %2d-%2d kn: n=%4d  median=%5.0f m  p90=%5.0f m"
              % (lo, hi, len(sel), pct(sel, .5), pct(sel, .9)))
