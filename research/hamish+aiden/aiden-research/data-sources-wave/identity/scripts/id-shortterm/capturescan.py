#!/usr/bin/env python3
"""Scan an AISStream capture file for short-window identity conflicts.

Usage: python3 -I capturescan.py <capture.jsonl> <out.json> [min_minutes]
"""
import json, sys, collections, math, datetime

src, out = sys.argv[1], sys.argv[2]

names = collections.defaultdict(dict)      # mmsi -> name -> [first,last,n]
imos = collections.defaultdict(dict)       # mmsi -> imo -> [first,last,n]
calls = collections.defaultdict(dict)
types = collections.defaultdict(dict)
dims = collections.defaultdict(dict)
seen = collections.Counter()
pos = collections.defaultdict(list)        # mmsi -> [(ts,lat,lon)]
tmin = tmax = None

def ts_of(md):
    s = md.get("time_utc")
    if s:
        try:
            return datetime.datetime.strptime(s[:19], "%Y-%m-%d %H:%M:%S").timestamp()
        except ValueError:
            pass
    return None

def norm(v):
    v = " ".join((v or "").split())
    return "" if v.lower() in ("", "unknown", "undefined", "0") else v

def gc_m(a, b):
    R = 6371000.0
    la1, lo1, la2, lo2 = map(math.radians, (a[0], a[1], b[0], b[1]))
    d = math.sin((la2-la1)/2)**2 + math.cos(la1)*math.cos(la2)*math.sin((lo2-lo1)/2)**2
    return 2*R*math.asin(min(1.0, math.sqrt(d)))

for line in open(src):
    try:
        d = json.loads(line)
    except json.JSONDecodeError:
        continue
    m = d.get("msg") or {}
    mt = m.get("MessageType")
    if mt not in ("PositionReport", "StandardClassBPositionReport",
                  "ExtendedClassBPositionReport", "ShipStaticData",
                  "StaticDataReport"):
        continue
    md = m.get("MetaData") or {}
    mmsi = md.get("MMSI") or md.get("MMSI_String")
    if not mmsi:
        continue
    t = ts_of(md) or d.get("recv")
    tmin = t if tmin is None or t < tmin else tmin
    tmax = t if tmax is None or t > tmax else tmax
    seen[mmsi] += 1
    body = m.get("Message") or {}

    def put(store, key, val, t):
        if not val:
            return
        e = store[mmsi].get(val)
        if e is None:
            store[mmsi][val] = [t, t, 1]
        else:
            e[1] = t; e[2] += 1

    nm = norm(md.get("ShipName"))
    if nm:
        put(names, "n", nm, t)
    if mt == "StaticDataReport":
        r = body.get("StaticDataReport") or {}
        for part in ("ReportA", "ReportB"):
            p = r.get(part) or {}
            if p.get("Name"):
                put(names, "n", norm(p["Name"]), t)
            if p.get("CallSign"):
                put(calls, "c", norm(p["CallSign"]), t)
            if p.get("ShipType"):
                put(types, "t", str(p["ShipType"]), t)
            dm = p.get("Dimension") or {}
            if any(dm.values()):
                put(dims, "d", f'{dm.get("A")}x{dm.get("B")}x{dm.get("C")}x{dm.get("D")}', t)
    elif mt == "ShipStaticData":
        sd = body.get("ShipStaticData") or {}
        nm2 = norm(sd.get("Name"))
        if nm2:
            put(names, "n", nm2, t)
        imo = sd.get("ImoNumber")
        if imo and int(imo) != 0:
            put(imos, "i", str(imo), t)
        if sd.get("CallSign"):
            put(calls, "c", norm(sd["CallSign"]), t)
        if sd.get("Type"):
            put(types, "t", str(sd["Type"]), t)
        dm = sd.get("Dimension") or {}
        if any(dm.values()):
            put(dims, "d", f'{dm.get("A")}x{dm.get("B")}x{dm.get("C")}x{dm.get("D")}', t)
    else:
        lat, lon = md.get("latitude"), md.get("longitude")
        if lat is not None and lon is not None:
            pos[mmsi].append((t, lat, lon))

span = (tmax - tmin) if tmin is not None else 0

def report(store, label):
    multi = {k: v for k, v in store.items() if len(v) > 1}
    trans = 0
    pairs = []
    for k, v in multi.items():
        items = sorted(v.items(), key=lambda kv: kv[1][0])
        trans += len(items) - 1
        pairs.append((k, [(x[0], round(x[1][0] - tmin), x[1][2]) for x in items]))
    return {"field": label, "mmsi_with_2plus": len(multi), "items": trans,
            "examples": pairs[:10]}

# same IMO on several MMSIs in the window
imo_map = collections.defaultdict(list)
for mmsi, d in imos.items():
    for imo, (t0, t1, n) in d.items():
        imo_map[imo].append((mmsi, t0, t1, n))
shared_imo = {imo: v for imo, v in imo_map.items() if len({x[0] for x in v}) > 1}

# duplicate MMSI: two positions far apart in a short time
jumps = {}
for mmsi, ps in pos.items():
    ps.sort()
    n = 0
    ex = None
    for i in range(1, len(ps)):
        t1, la1, lo1 = ps[i-1]
        t2, la2, lo2 = ps[i]
        dist = gc_m((la1, lo1), (la2, lo2))
        dt = max(t2 - t1, 1)
        if dist > 3000 and dist / dt * 1.94384 > 100:
            n += 1
            if ex is None:
                ex = {"dist_m": round(dist), "dt_s": round(t2 - t1),
                      "knots": round(dist / dt * 1.94384), "at": round(t1 - tmin)}
    if n:
        jumps[mmsi] = {"count": n, **ex}

res = {
    "file": src, "messages_scanned": sum(seen.values()),
    "distinct_mmsi": len(seen), "window_minutes": round(span / 60, 1),
    "fields": [report(names, "name"), report(imos, "imo"), report(calls, "callsign"),
               report(types, "type"), report(dims, "dimension")],
    "imo_on_multiple_mmsi": {k: v for k, v in list(shared_imo.items())[:20]},
    "n_imo_on_multiple_mmsi": len(shared_imo),
    "duplicate_mmsi_jumps": {"n": len(jumps), "examples": dict(list(jumps.items())[:15])},
}
json.dump(res, open(out, "w"), indent=1)
print(json.dumps({k: res[k] for k in ("messages_scanned", "distinct_mmsi",
      "window_minutes", "n_imo_on_multiple_mmsi")}))
for f in res["fields"]:
    print(f["field"], f["mmsi_with_2plus"], f["items"])
print("dup_mmsi_jumps", len(jumps))
