#!/usr/bin/env python3
"""Profile the OpenSanctions-matched vessels in the Danish day, and count silent ends."""
import csv
import json
import os
import statistics as st
from collections import Counter

HERE = os.path.dirname(os.path.abspath(__file__))
DAY = os.path.join(HERE, "..", "..", "data", "t-ais-history", "day_2026-11-01")
sv = list(csv.DictReader(open(os.path.join(DAY, "vessels.csv"))))
match = json.load(open(os.path.join(DAY, "sanctions_match.json")))

shadow = {m for m, d in match.items() if "mare.shadow" in d["tags"]}
sanct = {m for m, d in match.items() if "sanction" in d["tags"]}
print(f"matched {len(match)}; mare.shadow {len(shadow)}; sanction {len(sanct)}")

vmap = {r["mmsi"]: r for r in sv}


def prof(mmsis, label):
    rs = [vmap[m] for m in mmsis if m in vmap]
    n = len(rs)
    f = lambda k: sum(1 for r in rs if r[k].strip())
    print(f"\n{label} (n={n})")
    print(f"  name {f('name')} imo {f('imo')} shiptype {f('shiptype')} "
          f"draught {f('draught')} dest {f('dest')} length {f('length')}")
    itv = [float(r["median_interval_s"]) for r in rs if r["median_interval_s"]]
    print(f"  median report interval: p50 {st.median(itv):.0f} s" if itv else "  no intervals")
    print("  ship types:", dict(Counter(r["shiptype"] for r in rs)))
    print("  MMSI first digits:", dict(Counter(r["mmsi"][:3] for r in rs)))


prof(shadow, "mare.shadow vessels in Danish waters on 2026-11-01")
prof([m for m in match if m not in shadow], "other OpenSanctions matches")

# AIS name vs OpenSanctions caption
diff = 0
print("\nAIS name vs OpenSanctions caption differences (identity-laundering evidence):")
for m, d in sorted(match.items()):
    r = vmap.get(m)
    if not r:
        continue
    a = r["name"].strip().upper()
    caps = {c.strip().upper() for c in d["captions"]}
    if a and not any(a in c or c in a for c in caps):
        diff += 1
        print(f"  {m} AIS '{r['name']}' vs listed {sorted(caps)[:2]}")
print(f"  {diff} of {len(match)} differ")

# vessels that stop reporting while they were moving
END = "2026-11-01 23:59:59"
silent = []
for r in sv:
    if not r["last_ts"] or not r["sog_max"]:
        continue
    try:
        sog = float(r["sog_max"])
    except ValueError:
        continue
    if r["cls"] != "Class A" or sog < 5:
        continue
    hh = r["last_ts"][11:19]
    if hh < "22:00:00":
        silent.append(r)
print(f"\nClass A vessels fast at some point whose last fix was before 22:00Z: {len(silent)}")
print("  of those, matched to OpenSanctions:",
      len([r for r in silent if r["mmsi"] in match]))
print("  sample:", [(r["mmsi"], r["name"], r["sog_max"], r["last_ts"]) for r in silent[:8]])
