"""Analyse gfw-identities.jsonl for IMO integrity, identity-period structure and leads.

python3 -I gfw_ids.py <gfw.jsonl> <out.json>
"""
import json, sys, collections, datetime as dt

src, out = sys.argv[1], sys.argv[2]

def imo_ok(s):
    s = str(s)
    if len(s) != 7 or not s.isdigit():
        return False
    return (7*int(s[0]) + 6*int(s[1]) + 5*int(s[2]) + 4*int(s[3])
            + 3*int(s[4]) + 2*int(s[5])) % 10 == int(s[6])

def tp(s):
    if not s:
        return None
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00"))

rows = [json.loads(l) for l in open(src)]
q_imo_bad = []
q_imo_missing = []
self_imo_mismatch = []
multi_mmsi = []
name_flags = []
overlaps = []
gaps = []
periods_per_ship = []
reg_sources = collections.Counter()
self_sources = collections.Counter()
registries = collections.Counter()
n_self = 0

for r in rows:
    imo = r["imo"]
    if not imo or imo in ("0", "None"):
        q_imo_missing.append(r)
        continue
    if not imo_ok(imo):
        q_imo_bad.append((imo, r["group"], r["region"]))
    e = r["entries"][0]
    sri = e.get("selfReportedInfo") or []
    ri = e.get("registryInfo") or []
    n_self += len(sri)
    for s in sri:
        for sc in s.get("sourceCode") or []:
            self_sources[sc] += 1
        if s.get("imo") and str(s["imo"]) != str(imo):
            self_imo_mismatch.append({"q": imo, "self": s["imo"], "ssvid": s.get("ssvid"),
                                      "name": s.get("shipname"), "flag": s.get("flag"),
                                      "from": s.get("transmissionDateFrom"),
                                      "to": s.get("transmissionDateTo"),
                                      "group": r["group"], "region": r["region"]})
    for x in ri:
        for sc in x.get("sourceCode") or []:
            reg_sources[sc] += 1
        if x.get("flag"):
            registries[x["flag"]] += 1
    mmsis = {s.get("ssvid") for s in sri if s.get("ssvid")}
    if len(mmsis) > 1:
        multi_mmsi.append({"imo": imo, "n": len(mmsis),
                           "names": sorted({s.get("shipname") for s in sri if s.get("shipname")}),
                           "flags": sorted({s.get("flag") for s in sri if s.get("flag")}),
                           "group": r["group"], "region": r["region"]})
    names = {(s.get("shipname") or "").strip() for s in sri if s.get("shipname")}
    if len(names) > 1:
        name_flags.append({"imo": imo, "names": sorted(names), "group": r["group"],
                           "region": r["region"], "n": len(names)})
    # periods sorted by start
    per = []
    for s in sri:
        a, b = tp(s.get("transmissionDateFrom")), tp(s.get("transmissionDateTo"))
        if a and b:
            per.append((a, b, s.get("ssvid"), s.get("shipname"), s.get("flag")))
    per.sort()
    periods_per_ship.append(len(per))
    for i in range(1, len(per)):
        a0, b0 = per[i-1][0], per[i-1][1]
        a1, b1 = per[i][0], per[i][1]
        if a1 < b0:
            overlaps.append({"imo": imo, "prev_end": str(b0), "next_start": str(a1),
                             "days": (b0-a1).days, "prev": per[i-1][2:], "next": per[i][2:],
                             "group": r["group"], "region": r["region"]})
        else:
            d = (a1-b0).days
            if d > 0:
                gaps.append({"imo": imo, "gap_days": d, "end": str(b0), "start": str(a1),
                             "prev": per[i-1][2:], "next": per[i][2:],
                             "group": r["group"], "region": r["region"]})

res = {
    "n_records": len(rows),
    "groups": dict(collections.Counter(r["group"] for r in rows)),
    "regions": dict(collections.Counter(r["region"] for r in rows)),
    "imo_missing": len(q_imo_missing),
    "imo_bad_check": len(q_imo_bad),
    "imo_bad_check_list": q_imo_bad,
    "self_imo_records": n_self,
    "self_imo_mismatch": self_imo_mismatch,
    "n_self_imo_mismatch": len(self_imo_mismatch),
    "multi_mmsi": multi_mmsi,
    "n_multi_mmsi": len(multi_mmsi),
    "multi_name": name_flags,
    "n_multi_name": len(name_flags),
    "overlaps": overlaps,
    "n_overlaps": len(overlaps),
    "gaps": sorted(gaps, key=lambda x: -x["gap_days"])[:40],
    "n_gaps": len(gaps),
    "self_periods": dict(collections.Counter(periods_per_ship)),
    "registry_sources": dict(reg_sources),
    "self_sources": dict(self_sources),
    "registry_flags": dict(registries.most_common(30)),
}
with open(out, "w") as f:
    json.dump(res, f, indent=1)
print("ok", len(rows))
