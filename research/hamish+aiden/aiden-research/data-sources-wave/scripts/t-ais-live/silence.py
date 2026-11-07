"""Silence vs reception-loss analysis on the Digitraffic MQTT collection.

Run from $WAVE/scripts/t-ais-live:  ../../venv-t-ais-live/bin/python silence.py <mqtt.jsonl>

For every internal silence (>=MIN_GAP s with no report, both sides inside the window), ask the
reception question: was the vessel's own 0.1 deg cell still receiving other vessels during the gap,
and were >=3 other vessels reporting within 20 km? Anchored/moored ships are split out.
"""
import json
import math
import collections
import datetime as dt
import sys

MQ = sys.argv[1]
MIN_GAP = 300  # s
R_NEIGHBOUR = 20_000  # m


def ts(x):
    return dt.datetime.fromtimestamp(x, dt.timezone.utc).strftime("%H:%M:%SZ")


def hav(a, b, c, d):
    R = 6371000.0
    p1, p2 = math.radians(a), math.radians(c)
    dp = p2 - p1
    dl = math.radians(d - b)
    x = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(math.sqrt(x))


fix = []  # (mmsi, t, lat, lon, sog, navstat)
meta = {}
for line in open(MQ):
    r = json.loads(line)
    top = r["topic"]
    if top.endswith("/location"):
        try:
            p = json.loads(r["payload"])
        except Exception:
            continue
        if not isinstance(p.get("time"), (int, float)) or p.get("lat") is None:
            continue
        fix.append((int(top.split("/")[1]), p["time"], p["lat"], p["lon"], p.get("sog"), p.get("navStat")))
    elif top.endswith("/metadata"):
        try:
            meta[int(top.split("/")[1])] = json.loads(r["payload"])
        except Exception:
            pass

fix.sort(key=lambda x: x[1])
t0, t1 = fix[0][1], fix[-1][1]
print(f"window {ts(t0)} .. {ts(t1)}  {(t1-t0)/60:.1f} min, {len(fix)} fixes, {len({f[0] for f in fix})} vessels")

byv = collections.defaultdict(list)
for m, t, la, lo, sog, ns in fix:
    byv[m].append((t, la, lo, sog, ns))

# ---- internal silences ----
events = []
for m, recs in byv.items():
    for (ta, laa, loa, soga, nsa), (tb, lab, lob, sogb, nsb) in zip(recs, recs[1:]):
        if tb - ta < MIN_GAP:
            continue
        if ta < t0 + 120 or tb > t1 - 60:
            continue  # need a clean view of both sides
        events.append((m, ta, tb, tb - ta, laa, loa, soga, nsa))

print(f"\n== internal silences >= {MIN_GAP/60:.0f} min with both sides observable: {len(events)} "
      f"from {len(byv)} vessels ({100*len(events)/len(byv):.0f} per 100 vessels)")

cells = collections.defaultdict(list)  # (cx,cy) -> [(t, mmsi, lat, lon)]
for m, t, la, lo, sog, ns in fix:
    cells[(round(lo, 1), round(la, 1))].append((t, m, la, lo))

rows = []
for m, ta, tb, gap, la, lo, sog, ns in events:
    cell = (round(lo, 1), round(la, 1))
    # reception in the vessel's own cell during the gap (other vessels)
    cell_msgs = [x for x in cells[cell] if x[0] >= ta and x[0] <= tb and x[1] != m]
    other_vessels = len({x[1] for x in cell_msgs})
    # neighbours within 20 km during the gap (sampled: fixes in the gap)
    near = set()
    for m2, t2, la2, lo2, sog2, ns2 in fix:
        if m2 == m or t2 < ta or t2 > tb:
            continue
        if abs(la2 - la) < 0.35 and abs(lo2 - lo) < 0.6 and hav(la, lo, la2, lo2) <= R_NEIGHBOUR:
            near.add(m2)
    # baseline: own cell message rate per 10 min in the 20 min before the gap
    base = [x for x in cells[cell] if ta - 1200 <= x[0] < ta and x[1] != m]
    base_rate = len(base) / 20.0  # msgs per minute
    gap_rate = len(cell_msgs) / (gap / 60.0)
    rows.append(dict(m=m, ta=ta, tb=tb, gap=gap, la=la, lo=lo, sog=sog, ns=ns, cell=cell,
                     other_vessels=other_vessels, near=len(near), base_rate=base_rate, gap_rate=gap_rate))

if not rows:
    print("   (no qualifying silence events in this window)")
    rows = []
movers = [r for r in rows if (r["sog"] or 0) >= 3]
static = [r for r in rows if (r["sog"] or 0) < 3]
print(f"   by last-known speed: under way (>=3 kn) {len(movers)}, slow/anchor/moored {len(static)}")
if rows:
    gaps = sorted(r["gap"] for r in rows)
    print(f"   gap length: median {gaps[len(gaps)//2]/60:.1f} min, max {gaps[-1]/60:.1f} min")

iso = [r for r in rows if r["near"] >= 3 and r["gap_rate"] > 0]
cell_dark = [r for r in rows if r["near"] < 3 or r["gap_rate"] == 0]
print(f"   isolated silence (>=3 neighbours within 20 km still reporting): {len(iso)}")
print(f"   silence with dead local reception (<3 neighbours or zero cell traffic): {len(cell_dark)}")
print(f"   isolated AND under way: {len([r for r in iso if (r['sog'] or 0) >= 3])}")
print(f"   isolated, under way, not anchored/moored navstat: "
      f"{len([r for r in iso if (r['sog'] or 0) >= 3 and r['ns'] not in (1, 5)])}")
print("   examples (mmsi, gap start-end, minutes, sog, navstat, neighbours, cell msgs during gap):")
for r in sorted(iso, key=lambda r: -r["gap"])[:8]:
    nm = (meta.get(r["m"]) or {}).get("name", "?")
    ty = (meta.get(r["m"]) or {}).get("type")
    print(f"     {r['m']} {nm[:18]:18s} type={ty} {ts(r['ta'])}->{ts(r['tb'])} {r['gap']/60:5.1f} min "
          f"sog={r['sog']} nav={r['ns']} near={r['near']:3d} cellmsgs={int(r['gap_rate']*(r['gap']/60))}")

# ---- vessels silent through the end of the window ----
cut = t1 - 600
live_late = {m for m, t, *_ in fix if t >= cut}
early = {m for m, t, *_ in fix if t <= t0 + 900}
silent_end = early - live_late
print(f"\n== vessels heard in the first 15 min but NOT in the last 10 min: {len(silent_end)} of {len(early)}")
last = {}
for m, t, la, lo, sog, ns in fix:
    if m in silent_end and (m not in last or t > last[m][0]):
        last[m] = (t, la, lo, sog, ns)
lon_west = sum(1 for v in last.values() if v[2] < 20)
print(f"   of those, last seen west of 20E (coverage edge): {lon_west}")
anch = sum(1 for v in last.values() if v[4] in (1, 5))
print(f"   last navStat anchored(1)/moored(5): {anch}")
sig = [(m, v) for m, v in last.items() if v[3] is not None and v[3] >= 3 and v[4] not in (1, 5) and v[2] >= 20]
print(f"   under way (>=3 kn), not anchored/moored, east of 20E, last fix >=10 min before end: {len(sig)}")
for m, v in sorted(sig, key=lambda x: -x[1][0])[:8]:
    nm = (meta.get(m) or {}).get("name", "?")
    print(f"     {m} {nm[:18]:18s} last {ts(v[0])} at {v[2]:.2f}E {v[1]:.2f}N sog={v[3]}")

# ---- per-cell reception map ----
print("\n== per-cell reception, 0.1 deg, 5-min bins")
bins = collections.Counter()
for m, t, la, lo, sog, ns in fix:
    bins[(round(lo, 1), round(la, 1), int((t - t0) // 300))] += 1
nb = int((t1 - t0) // 300) + 1
percell = collections.defaultdict(set)
for (cx, cy, b), n in bins.items():
    percell[(cx, cy)].add(b)
full = sum(1 for c, s in percell.items() if len(s) == nb)
print(f"   {len(percell)} cells seen; {full} active in all {nb} bins; "
      f"{sum(1 for c,s in percell.items() if len(s)<=nb//2)} active in half the bins or fewer")
west = [c for c in percell if c[0] < 20]
east = [c for c in percell if c[0] >= 20]
print(f"   cells east of 20E: {len(east)}, west of 20E: {len(west)}")
