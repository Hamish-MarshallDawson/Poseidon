"""Stricter identity-structure stats for GFW identity records.

python3 -I gfw_ids2.py <gfw.jsonl> <out.json>
Collapses periods per ssvid, then measures per IMO: distinct MMSIs, names, flags,
true concurrency between different MMSIs, and gaps between MMSI periods.
"""
import json, sys, collections, datetime as dt

src, out = sys.argv[1], sys.argv[2]

def tp(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None

rows = [json.loads(l) for l in open(src)]
stats = collections.Counter()
res = []
for r in rows:
    sri = r["entries"][0].get("selfReportedInfo") or []
    per_ssvid = {}
    for s in sri:
        ssvid = s.get("ssvid")
        a, b = tp(s.get("transmissionDateFrom")), tp(s.get("transmissionDateTo"))
        if not ssvid or not a or not b:
            continue
        d = per_ssvid.setdefault(ssvid, {"a": a, "b": b, "names": set(), "flags": set()})
        d["a"] = min(d["a"], a)
        d["b"] = max(d["b"], b)
        if s.get("shipname"):
            d["names"].add(s["shipname"].strip())
        if s.get("flag"):
            d["flags"].add(s["flag"])
    items = sorted(per_ssvid.items(), key=lambda kv: kv[1]["a"])
    stats["ships"] += 1
    if len(items) > 1:
        stats["multi_mmsi"] += 1
    if len({n for d in per_ssvid.values() for n in d["names"]}) > 1:
        stats["multi_name"] += 1
    if len({f for d in per_ssvid.values() for f in d["flags"]}) > 1:
        stats["multi_flag"] += 1
    if len(items) >= 3:
        stats["three_plus_mmsi"] += 1
    conc = []
    min_same_day = None
    for i in range(1, len(items)):
        prev = items[i-1][1]
        cur = items[i][1]
        if cur["a"] < prev["b"]:
            conc.append([items[i-1][0], items[i][0],
                         round((prev["b"]-cur["a"]).total_seconds()/3600, 1)])
        delta_days = (cur["a"] - prev["b"]).total_seconds()/86400
        if min_same_day is None or abs(delta_days) < abs(min_same_day):
            min_same_day = delta_days
    if conc:
        stats["concurrent_mmsi_ships"] += 1
    if min_same_day is not None and -1 <= min_same_day <= 1:
        stats["switch_within_1day"] += 1
    res.append({"imo": r["imo"], "group": r["group"], "region": r["region"],
                "n_mmsi": len(per_ssvid),
                "names": sorted({n for d in per_ssvid.values() for n in d["names"]}),
                "flags": sorted({f for d in per_ssvid.values() for f in d["flags"]}),
                "periods": [[k, str(v["a"]), str(v["b"]), sorted(v["names"])] for k, v in items],
                "concurrent_hours": conc,
                "min_switch_days": None if min_same_day is None else round(min_same_day, 2)})

conc_ships = [x for x in res if x["concurrent_hours"]]
fast = [x for x in res if x["min_switch_days"] is not None and -1 <= x["min_switch_days"] <= 1]
long_gap = [x for x in res if x["min_switch_days"] is not None and x["min_switch_days"] > 365]
outd = {"stats": dict(stats),
        "concurrent": sorted(conc_ships, key=lambda x: -len(x["concurrent_hours"]))[:15],
        "fast_switches": sorted(fast, key=lambda x: x["min_switch_days"])[:20],
        "long_gaps": sorted(long_gap, key=lambda x: -x["min_switch_days"])[:15]}
json.dump(outd, open(out, "w"), indent=1)
print("ok", dict(stats))
