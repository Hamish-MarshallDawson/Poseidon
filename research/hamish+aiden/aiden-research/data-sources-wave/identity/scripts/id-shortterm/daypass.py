#!/usr/bin/env python3
"""Stream one Danish AIS day (from the zip on stdin) and measure short-term
identity flicker and duplicate-MMSI conflicts per MMSI.

Usage: unzip -p aisdk-2026-11-01.zip | python3 -I daypass.py <outdir> <day>
"""
import csv, sys, json, math, collections

outdir, day = sys.argv[1], sys.argv[2]

FIELDS = ["name", "imo", "callsign", "ship_type", "length", "width", "draught"]
MISSING = {"", "unknown", "undefined", "0", "none"}

def norm(v):
    v = (v or "").strip()
    v = " ".join(v.split())
    return v

def missing(v):
    return norm(v).lower() in MISSING

def gc_m(a, b):
    R = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    d = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(min(1.0, math.sqrt(d)))

ships = {}
recent = {}   # mmsi -> deque of (ts, lat, lon)
two_place = collections.Counter()   # mmsi -> count of impossible-jump pairs
two_place_ex = {}                   # mmsi -> one example
static_at = collections.defaultdict(list)  # mmsi -> [(ts, lat, lon, name, imo)]

r = csv.reader(sys.stdin)
hdr = next(r)
for row in r:
    if len(row) < 25:
        continue
    try:
        mmsi = row[2]
        if not mmsi:
            continue
        ts = row[0]
        lat = float(row[3]); lon = float(row[4])
    except (ValueError, IndexError):
        continue
    mob = row[1]
    if mob in ("Base Station", "AtoN", "Search and Rescue Transponder",
               "Emergency PIRB", "SAR Airborne"):
        continue
    s = ships.get(mmsi)
    if s is None:
        s = ships[mmsi] = {"cls": collections.Counter(), "n": 0,
                           "vals": {f: {} for f in FIELDS},
                           "last": {}, "trans": collections.Counter(),
                           "first_ts": ts, "last_ts": ts}
    s["cls"][mob] += 1
    s["n"] += 1
    s["last_ts"] = ts
    for f, col in (("name", 12), ("imo", 10), ("callsign", 11), ("ship_type", 13),
                   ("length", 16), ("width", 15), ("draught", 18)):
        raw = row[col] if col < len(row) else ""
        if f == "imo":
            v = norm(raw)
            if v.lower() in ("0", "", "unknown", "undefined"):
                v = ""
        else:
            v = "" if missing(raw) else norm(raw)
        if v == "":
            continue
        d = s["vals"][f]
        e = d.get(v)
        if e is None:
            d[v] = [ts, ts, 1]
        else:
            e[1] = ts; e[2] += 1
        lv = s["last"].get(f)
        if lv is not None and lv[0] != v:
            s["trans"][f] += 1
        s["last"][f] = (v, ts)

    # duplicate / two-place test: same MMSI in two far-apart spots within 120 s
    q = recent.get(mmsi)
    if q is None:
        q = recent[mmsi] = collections.deque()
    if q and q[-1][0] != ts:
        ts2, la2, lo2 = q[-1]
        dist = gc_m((lat, lon), (la2, lo2))
        # implied speed over the gap between the two fixes
        dt = (int(ts[11:13]) * 3600 + int(ts[14:16]) * 60 + int(ts[17:19])) - \
             (int(ts2[11:13]) * 3600 + int(ts2[14:16]) * 60 + int(ts2[17:19]))
        if dist > 2000 and (dt <= 0 or dist / max(dt, 1) * 1.94384 > 60):
            two_place[mmsi] += 1
            if mmsi not in two_place_ex:
                two_place_ex[mmsi] = {"t1": ts2, "t2": ts, "gap_m": round(dist), "gap_s": dt}
    q.append((ts, lat, lon))
    if len(q) > 2:
        q.popleft()

# ---- aggregate ----
summary = {"day": day, "mmsi_seen": len(ships), "fields": {}}
conflict = {"imo_multi_mmsi": {}, "mmsi_multi_imo": {}, "two_place": {}}
per_ship = []
for mmsi, s in ships.items():
    # ignore short appearances: need >= 20 fixes to judge flicker
    per_ship.append({
        "mmsi": mmsi, "n": s["n"], "cls": s["cls"].most_common(1)[0][0],
        "first": s["first_ts"], "last": s["last_ts"],
        "distinct": {f: len(v) for f, v in s["vals"].items()},
        "trans": dict(s["trans"]),
        "vals": {f: {k: v for k, v in d.items()} for f, d in s["vals"].items() if len(d) > 1},
    })

for f in FIELDS:
    multi = [x for x in per_ship if x["distinct"][f] > 1 and x["n"] >= 20]
    trans = sum(x["trans"].get(f, 0) for x in per_ship if x["n"] >= 20)
    flipped = [x for x in per_ship if x["trans"].get(f, 0) > 0 and x["n"] >= 20]
    summary["fields"][f] = {
        "mmsi_with_2plus_values": len(multi),
        "mmsi_with_transitions": len(flipped),
        "transitions": trans,
        "examples": [(x["mmsi"], x["vals"].get(f, {})) for x in multi[:8]],
    }

# one IMO on several MMSIs during the day
imo_map = collections.defaultdict(lambda: collections.defaultdict(list))
for x in per_ship:
    for val, (t0, t1, c) in x["vals"].get("imo", {}).items():
        imo_map[val][x["mmsi"]].append((t0, t1))
for imo, d in imo_map.items():
    if len(d) > 1:
        spans = sorted((v[0][0], v[0][1], m) for m, v in d.items())
        # overlap in time?
        overlap = False
        for i in range(1, len(spans)):
            if spans[i][0] <= spans[i-1][1]:
                overlap = True
        conflict["imo_multi_mmsi"][imo] = {"mmsis": {m: v[0] for m, v in d.items()},
                                           "time_overlap": overlap}

# one MMSI with several IMOs during the day
for x in per_ship:
    if len(x["vals"].get("imo", {})) > 1:
        conflict["mmsi_multi_imo"][x["mmsi"]] = x["vals"]["imo"]

for mmsi, c in two_place.items():
    conflict["two_place"][mmsi] = {"pairs": c, **two_place_ex.get(mmsi, {})}

summary["conflicts"] = {k: len(v) for k, v in conflict.items()}
summary["two_place_overall_pairs"] = sum(two_place.values())

with open(f"{outdir}/day-summary-{day}.json", "w") as fh:
    json.dump(summary, fh, indent=1)
with open(f"{outdir}/day-conflicts-{day}.json", "w") as fh:
    json.dump(conflict, fh, indent=1)
with open(f"{outdir}/day-pership-{day}.json", "w") as fh:
    json.dump(per_ship, fh)
print(json.dumps({k: summary[k] for k in ("day", "mmsi_seen", "conflicts", "two_place_overall_pairs")}))
for f, d in summary["fields"].items():
    print(f, d["mmsi_with_2plus_values"], d["mmsi_with_transitions"], d["transitions"])
