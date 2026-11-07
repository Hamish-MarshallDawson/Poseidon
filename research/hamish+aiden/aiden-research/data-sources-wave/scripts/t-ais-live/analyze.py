"""Analyse the Digitraffic MQTT + REST collections.

Run from $WAVE/scripts/t-ais-live:
  ../../venv-t-ais-live/bin/python analyze.py <mqtt.jsonl> <rest-prefix>
"""
import json
import sys
import statistics as st
import collections
import datetime as dt

MQ = sys.argv[1]
REST = sys.argv[2]


def pct(xs, p):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * p / 100
    lo, hi = int(k), min(int(k) + 1, len(xs) - 1)
    return xs[lo] + (xs[hi] - xs[lo]) * (k - lo)


def ts(x):
    return dt.datetime.fromtimestamp(x, dt.timezone.utc).strftime("%H:%M:%SZ")


# ---------- MQTT ----------
loc = []  # (mmsi, fix_s, recv_ms, lat, lon, sog, navstat)
meta = {}
status = []
for line in open(MQ):
    r = json.loads(line)
    top = r["topic"]
    if top.endswith("/location"):
        mmsi = int(top.split("/")[1])
        try:
            p = json.loads(r["payload"])
        except Exception:
            continue
        loc.append((mmsi, p.get("time"), r["recv_ts"], p.get("lat"), p.get("lon"), p.get("sog"), p.get("navStat")))
    elif top.endswith("/metadata"):
        mmsi = int(top.split("/")[1])
        try:
            meta[mmsi] = json.loads(r["payload"])
        except Exception:
            pass
    else:
        status.append(r)

loc = [x for x in loc if isinstance(x[1], (int, float))]
t0 = min(x[1] for x in loc)
t1 = max(x[1] for x in loc)
dur = t1 - t0
print(f"== Window {ts(t0)} .. {ts(t1)}  ({dur:.0f}s = {dur/60:.1f} min)")
print(f"location messages: {len(loc)}  rate {len(loc)/dur:.2f} msg/s   distinct MMSI: {len({x[0] for x in loc})}")

per_min = collections.Counter(int((x[1] - t0) // 60) for x in loc)
print("msgs/min:", [per_min.get(i, 0) for i in range(int(dur // 60) + 1)])

delays = [x[2] / 1000 - x[1] for x in loc]
print(f"delay recv-fix (s): n={len(delays)} median={pct(delays,50):.1f} p10={pct(delays,10):.1f} p90={pct(delays,90):.1f} p99={pct(delays,99):.1f} max={max(delays):.1f} min={min(delays):.1f}")
neg = sum(1 for d in delays if d < 0)
print(f"negative delays (clock skew / future stamps): {neg} ({100*neg/len(delays):.2f}%)")

# duplicates: identical (mmsi, fix time)
dup = collections.Counter((x[0], x[1]) for x in loc)
ndup = sum(c - 1 for c in dup.values() if c > 1)
print(f"duplicate (mmsi,fix-time) messages: {ndup} of {len(loc)} ({100*ndup/len(loc):.2f}%)")

# reporting interval per vessel
byv = collections.defaultdict(list)
for m, t, *_ in loc:
    byv[m].append(t)
ints_all = []
med_by_v = {}
for m, tsx in byv.items():
    tsx.sort()
    d = [b - a for a, b in zip(tsx, tsx[1:]) if b > a]
    if len(tsx) >= 5:
        med_by_v[m] = st.median(d) if d else None
    ints_all += d
print(f"reporting interval (all gaps between consecutive msgs): median={pct(ints_all,50):.0f}s p10={pct(ints_all,10):.0f} p90={pct(ints_all,90):.0f} p99={pct(ints_all,99):.0f}")
print(f"per-vessel median interval: median={st.median([v for v in med_by_v.values() if v]):.0f}s  n_vessels_with>=5msgs={len(med_by_v)}")
buckets = collections.Counter()
for v in med_by_v.values():
    if not v: continue
    b = "<10s" if v < 10 else "10-30s" if v < 30 else "30-120s" if v < 120 else "2-5min" if v < 300 else "5-15min" if v < 900 else ">=15min"
    buckets[b] += 1
print("vessel median-interval buckets:", dict(buckets))

# geography
lats = [x[3] for x in loc]; lons = [x[4] for x in loc]
print(f"bbox: lon {min(lons):.2f}..{max(lons):.2f}  lat {min(lats):.2f}..{max(lats):.2f}")
cells = collections.Counter((round(x[4], 1), round(x[3], 1)) for x in loc)
print(f"distinct 0.1deg cells with traffic: {len(cells)}; top cells:", cells.most_common(5))
gof = sum(1 for x in loc if 21 <= x[4] <= 30 and 59.2 <= x[3] <= 61)
print(f"positions in Gulf of Finland box (21-30E,59.2-61N): {gof} ({100*gof/len(loc):.1f}%)")
print(f"positions east of 20E: {sum(1 for x in loc if x[4] >= 20)}; west of 20E: {sum(1 for x in loc if x[4] < 20)}")

# static-data completeness (MQTT metadata)
print(f"\n== metadata messages: {len(meta)} distinct MMSI; location MMSI {len(byv)}; overlap {len(set(meta) & set(byv))}")
fields = ["name", "imo", "type", "draught", "destination", "callSign", "eta", "posType"]
for f in fields:
    have = sum(1 for m, d in meta.items() if d.get(f) not in (None, "", 0))
    print(f"  metadata has {f:12s}: {have:5d}/{len(meta)} ({100*have/max(1,len(meta)):.0f}%)")
ptype = collections.Counter(d.get("posType") for d in meta.values())
print("  posType distribution:", dict(ptype), "(Digitraffic: 1=Class A, 2=Class B)")
# class A vessels in location stream
clsA = {m for m, d in meta.items() if d.get("posType") == 1}
clsB = {m for m, d in meta.items() if d.get("posType") == 2}
print(f"  location msgs from Class A mmsi: {sum(1 for x in loc if x[0] in clsA)}; Class B: {sum(1 for x in loc if x[0] in clsB)}; unknown: {sum(1 for x in loc if x[0] not in clsA and x[0] not in clsB)}")

# ---------- silence / reception ----------
print("\n== silence test: vessels reporting in the first 10 min, then quiet in the last 8 min")
cut_early = t0 + 600
cut_late = t1 - 480
early = {m for m, t, *_ in loc if t <= cut_early}
late = {m for m, t, *_ in loc if t >= cut_late}
silent = early - late
print(f"vessels heard in first 10 min: {len(early)}; still heard in last 8 min: {len(early & late)} ({100*len(early&late)/len(early):.0f}%)")
print(f"silent through the last 8 min: {len(silent)}")
# for each silent vessel, last position and whether other ships still report nearby
lastpos = {}
for m, t, rt, la, lo, sog, ns in loc:
    if m in silent and (m not in lastpos or t > lastpos[m][0]):
        lastpos[m] = (t, la, lo, sog, ns)
near = 0
for m, (t, la, lo, sog, ns) in lastpos.items():
    if la is None: continue
    others = 0
    for m2, t2, rt2, la2, lo2, sog2, ns2 in loc:
        if m2 == m or la2 is None or t2 < cut_late: continue
        if abs(la2 - la) < 0.2 and abs(lo2 - lo) < 0.35:
            others += 1
    if others >= 3: near += 1
print(f"of those {len(lastpos)} with a last position, {near} had >=3 other vessels still reporting within ~0.2deg/0.35deg in the last 8 min")
# where were the silent ones last seen
sc = collections.Counter((round(v[2], 1), round(v[1], 1)) for v in lastpos.values() if v[1] is not None)
print("silent-vessel last-seen cells (0.1deg):", sc.most_common(8))
tankers = [m for m in silent if meta.get(m, {}).get("type") == 80]
print(f"silent vessels with ship type 80 (tanker): {len(tankers)}")

# reception: per 0.5deg cell message rate per 10 min
print("\n== per-cell reception (0.5 deg cells, 10-min bins) to separate coverage loss from vessel silence")
bins = collections.Counter()
for m, t, rt, la, lo, sog, ns in loc:
    if la is None: continue
    bins[(round(lo * 2) / 2, round(la * 2) / 2, int((t - t0) // 600))] += 1
nb = int(dur // 600) + 1
cellrates = collections.defaultdict(list)
for (cx, cy, b), n in bins.items():
    cellrates[(cx, cy)].append(n)
hot = {c: v for c, v in cellrates.items() if len(v) == nb}
print(f"cells active in all {nb} bins: {len(hot)} of {len(cellrates)} cells seen")
empty_bins = sum(1 for c, v in cellrates.items() if len(v) < nb)
print(f"cells missing at least one 10-min bin: {empty_bins}")

# ---------- REST ----------
print("\n== REST polls")
polls = []
for line in open(REST + "-locations.jsonl"):
    r = json.loads(line)
    if "body" in r:
        feats = r["body"].get("features", [])
        polls.append((r["recv_ts"], r["latency_ms"], feats))
if polls:
    print(f"polls: {len(polls)}  latency_ms median={st.median([p[1] for p in polls]):.0f} min={min(p[1] for p in polls)} max={max(p[1] for p in polls)}")
    ns = [len(p[2]) for p in polls]
    print(f"features per poll: median={st.median(ns):.0f} min={min(ns)} max={max(ns)}")
    sets = [frozenset(f["mmsi"] for f in p[2]) for p in polls]
    print(f"distinct MMSI across all polls: {len(set().union(*sets))}")
    if len(sets) > 2:
        print(f"churn between consecutive polls: median new={st.median([len(b-a) for a,b in zip(sets,sets[1:])]):.0f} dropped={st.median([len(a-b) for a,b in zip(sets,sets[1:])]):.0f}")
    # delay of REST positions
    dl = []
    for recv, lat, feats in polls:
        for f in feats:
            tex = f["properties"].get("timestampExternal")
            if tex: dl.append(recv / 1000 - tex / 1000)
    print(f"REST position age at receipt (s): median={pct(dl,50):.0f} p10={pct(dl,10):.0f} p90={pct(dl,90):.0f} p99={pct(dl,99):.0f} max={max(dl):.0f}")
    # field completeness
    print("REST features carry only: mmsi, sog, cog, navStat, rot, posAcc, raim, heading, timestamp, timestampExternal -> no name/IMO/type")
    # same vessel in MQTT?
    restm = sets[-1]
    print(f"REST MMSI set vs MQTT MMSI set: REST-only {len(restm - set(byv))}, MQTT-only {len(set(byv) - restm)}")

# ---------- extra: metadata republish interval, navstat, tankers near Russian ports ----------
print("\n== metadata republish interval (static data is re-broadcast by the ship)")
mt = collections.defaultdict(list)
for line in open(MQ):
    r = json.loads(line)
    if r["topic"].endswith("/metadata"):
        try:
            d = json.loads(r["payload"])
        except Exception:
            continue
        if isinstance(d.get("timestamp"), (int, float)):
            mt[int(r["topic"].split("/")[1])].append(d["timestamp"] / 1000)
deltas = []
for m, tl in mt.items():
    tl.sort()
    deltas += [b - a for a, b in zip(tl, tl[1:]) if b > a]
if deltas:
    print(f"   n={len(deltas)} repeats, median={pct(deltas,50)/60:.1f} min, p10={pct(deltas,10)/60:.1f}, p90={pct(deltas,90)/60:.1f}")
print(f"   vessels with metadata: {len(mt)}")

print("\n== navStat distribution (location msgs)")
ns_count = collections.Counter(x[6] for x in loc)
print("  ", dict(ns_count.most_common()))
sog = [x[5] for x in loc if isinstance(x[5], (int, float))]
print(f"   sog: moving >3kn {sum(1 for s in sog if s>3)} ({100*sum(1 for s in sog if s>3)/max(1,len(sog)):.0f}%), "
      f"0-3kn {sum(1 for s in sog if s<=3)}")

print("\n== ship types present (metadata 'type')")
types = collections.Counter((d.get("type") // 10) * 10 for d in meta.values() if isinstance(d.get("type"), int))
names = {70: "cargo", 80: "tanker", 60: "passenger", 30: "fishing", 50: "pilot/SAR/service", 31: "towing", 52: "tug", 36: "sailing", 37: "pleasure", 0: "unknown"}
print("  ", {(names.get(k, str(k))): v for k, v in types.most_common(8)})

print("\n== tankers near the Russian Baltic oil ports (positions within 30 km)")
def hav(a, b, c, d):
    import math
    R = 6371000.0
    p1, p2 = math.radians(a), math.radians(c)
    dp, dl = p2 - p1, math.radians(d - b)
    x = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(x))
PORTS = {"Primorsk": (60.34, 28.72), "Ust-Luga": (59.87, 28.30), "Vysotsk": (60.63, 28.57), "St Petersburg": (59.87, 30.20)}
tankers = {m for m, d in meta.items() if isinstance(d.get("type"), int) and 80 <= d["type"] <= 89}
print(f"   tanker MMSI with metadata: {len(tankers)}; tanker location msgs: {sum(1 for x in loc if x[0] in tankers)}")
for pn, (pla, plo) in PORTS.items():
    tv = {x[0] for x in loc if x[0] in tankers and hav(pla, plo, x[3], x[4]) <= 30000}
    allv = {x[0] for x in loc if hav(pla, plo, x[3], x[4]) <= 30000}
    print(f"   {pn:14s} tankers seen {len(tv):3d}, all vessels {len(allv):3d} within 30 km")
