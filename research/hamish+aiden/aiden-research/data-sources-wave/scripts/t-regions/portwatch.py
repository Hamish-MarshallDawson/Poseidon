#!/usr/bin/env python3
"""PortWatch chokepoint transits, one chokepoint at a time (the FeatureServer caps paging).
Free, no account. Records lag and the 2026 level so it can be compared with radar counts.
"""
import json, urllib.request, urllib.parse, collections, datetime as dt

BASE = ("https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/"
        "Daily_Chokepoints_Data/FeatureServer/0/query")
OUT = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave/data/t-regions/portwatch.json"
WANT = {"chokepoint6": "Strait of Hormuz", "chokepoint5": "Malacca Strait",
        "chokepoint4": "Bab el-Mandeb Strait", "chokepoint15": "Lombok Strait",
        "chokepoint10": "Oresund Strait", "chokepoint9": "Dover Strait",
        "chokepoint19": "Sunda Strait"}

def q(portid, start="2025-10-01"):
    p = {"where": f"portid='{portid}' AND date>=DATE '{start}'", "outFields": "*",
         "f": "json", "resultRecordCount": 2000, "returnGeometry": "false",
         "orderByFields": "date"}
    return [f["attributes"] for f in
            json.load(urllib.request.urlopen(BASE + "?" + urllib.parse.urlencode(p), timeout=180))["features"]]

if __name__ == "__main__":
    out = {}
    for pid, name in WANT.items():
        rs = q(pid)
        if not rs:
            print(name, "no rows"); continue
        days = [r["date"] for r in rs]
        tot = [r["n_total"] or 0 for r in rs]
        tank = [r["n_tanker"] or 0 for r in rs]
        bym = collections.defaultdict(lambda: [0, 0, 0])
        for r in rs:
            k = r["date"][:7]
            bym[k][0] += r["n_total"] or 0; bym[k][1] += r["n_tanker"] or 0; bym[k][2] += 1
        out[name] = {"portid": pid, "days": len(rs), "first": days[0], "last": days[-1],
                     "mean_total": round(sum(tot) / len(tot), 1),
                     "mean_tanker": round(sum(tank) / len(tank), 1),
                     "last60": [{"date": r["date"], "total": r["n_total"], "tanker": r["n_tanker"]} for r in rs[-60:]],
                     "monthly": {k: {"total_per_day": round(v[0] / v[2], 1),
                                     "tanker_per_day": round(v[1] / v[2], 1), "days": v[2]}
                                 for k, v in sorted(bym.items())}}
        m = out[name]["monthly"]
        print(f"\n{name} ({pid}): {len(rs)} days {days[0]}..{days[-1]} "
              f"mean {out[name]['mean_total']}/day (tankers {out[name]['mean_tanker']}/day)")
        print("   monthly total/day:", {k: v["total_per_day"] for k, v in list(m.items())[-8:]})
        print("   last 8 days:", [(d["date"], d["total"]) for d in out[name]["last60"][-8:]])
    json.dump(out, open(OUT, "w"), indent=1)
    print("\nwrote", OUT)
