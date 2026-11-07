#!/usr/bin/env python3
"""Cross-check: does OFAC SDN catch vessel IMOs that OpenSanctions missed in the Danish day?"""
import csv, json, os, re
from collections import Counter
HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "..", "..", "data", "t-ais-history")
DAY = os.path.join(D, "day_2026-11-01")

# --- OFAC SDN: IMO numbers live in the remarks column
imos = {}
rows = 0
with open(os.path.join(D, "ofac", "sdn.csv"), encoding="utf-8", errors="replace") as f:
    for r in csv.reader(f):
        rows += 1
        if len(r) < 12:
            continue
        remark = r[11]
        for m in re.findall(r"Vessel Registration Identification\s*IMO\s*(\d{7})", remark):
            imos.setdefault(m, r[1])
print("SDN rows:", rows, "distinct IMO in remarks:", len(imos))

v = list(csv.DictReader(open(os.path.join(DAY, "vessels.csv"))))
have = {}
for x in v:
    im = x["imo"].strip().lstrip("IMO")
    if im:
        have.setdefault(im, x)
print("AIS vessels with IMO:", len(have))

os_match = json.load(open(os.path.join(DAY, "sanctions_match.json")))
os_imos = {d["imo"].strip().lstrip("IMO") for d in os_match.values() if d.get("imo")}

hits = [(im, have[im], nm) for im, nm in imos.items() if im in have]
print("AIS vessels on OFAC SDN (by IMO):", len(hits))
extra = [(im, x, nm) for im, x, nm in hits if im not in os_imos]
print("  of which NOT in my OpenSanctions match:", len(extra))
for im, x, nm in extra:
    print(f"   IMO {im} AIS '{x['name']}' ({x['shiptype']}, sog_max {x['sog_max']}, "
          f"median interval {x['median_interval_s']} s) SDN '{nm[:40]}'")
