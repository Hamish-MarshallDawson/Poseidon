#!/usr/bin/env python3
"""Characterise the DMA day from the tables dma_day.py produced, and join to OpenSanctions."""
import csv
import json
import os
import statistics as st
from collections import Counter, defaultdict

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "..", "..", "data", "t-ais-history")
DAY = os.path.join(D, "day_2026-11-01")


def rows(path):
    with open(path) as f:
        yield from csv.DictReader(f)


def pct(a, p):
    a = sorted(a)
    return a[min(len(a) - 1, int(p * len(a)))] if a else None


v = list(rows(os.path.join(DAY, "vessels.csv")))
g = list(rows(os.path.join(DAY, "gaps.csv")))
print(f"vessel rows {len(v)}  gap rows {len(g)}")

ca = [r for r in v if r["cls"] == "Class A" and int(r["n_pos"] or 0) > 2]
cb = [r for r in v if r["cls"] == "Class B" and int(r["n_pos"] or 0) > 2]
print(f"Class A vessels >2 pos: {len(ca)}; Class B: {len(cb)}")

print("\n=== identity completeness, Class A (n=%d) ===" % len(ca))
for f in ["name", "imo", "shiptype", "length", "width", "draught", "dest", "callsign"]:
    k = sum(1 for r in ca if r[f].strip())
    print(f"  {f:9s} {k:5d}  {100*k/len(ca):5.1f}%")

print("\n=== vessel types present (Class A, by ship type text) ===")
tc = Counter(r["shiptype"] for r in ca)
for t, n in tc.most_common(14):
    print(f"  {t or '(blank)':28s} {n:5d}")

print("\n=== reporting interval (median per vessel, seconds) ===")
med = [float(r["median_interval_s"]) for r in ca if r["median_interval_s"]]
print(f"  n={len(med)} min {min(med):.0f} p10 {pct(med,.1):.0f} median {st.median(med):.0f} "
      f"p90 {pct(med,.9):.0f} max {max(med):.0f}")
slow = [m for m in med if m > 180]
print(f"  vessels with median interval > 180 s: {len(slow)} ({100*len(slow)/len(med):.1f}%)")
slow2 = [m for m in med if m > 600]
print(f"  vessels with median interval > 600 s: {len(slow2)}")

print("\n=== duplicate timestamps / bad positions (whole day, all classes) ===")
dup = sum(int(r["dup_ts"] or 0) for r in v)
badp = sum(int(r["pos_bad"] or 0) for r in v)
tot = sum(int(r["n_pos"] or 0) for r in v)
print(f"  rows kept {tot}, same-MMSI-same-second duplicates {dup} "
      f"({100*dup/(tot+dup):.2f}%), unusable positions {badp}")

print("\n=== gaps >= 20 min while moving (n=%d) ===" % len(g))
gm = [float(r["gap_min"]) for r in g]
print(f"  minutes: min {min(gm):.0f} median {st.median(gm):.0f} p90 {pct(gm,.9):.0f} max {max(gm):.0f}")
for thr in (30, 60, 180, 360, 720):
    n = sum(1 for x in gm if x >= thr)
    print(f"  gaps >= {thr:4d} min: {n:5d} events, {sum(1 for r in g if float(r['gap_min'])>=thr)} ")
byc = Counter(r["cls"] for r in g)
print("  by class:", dict(byc))
byt = Counter(r["shiptype"] for r in g)
print("  top ship types with gaps:", byt.most_common(8))
byv = Counter(r["mmsi"] for r in g)
print(f"  distinct vessels with any gap: {len(byv)}; top repeaters: {byv.most_common(5)}")
# how far from Danish coast are they? use latitude bands as a proxy
bands = Counter()
for r in g:
    try:
        la, lo = float(r["lat"]), float(r["lon"])
    except ValueError:
        continue
    bands[(round(la), round(lo))] += 1
print("  top 1-degree cells:", bands.most_common(8))
# gaps that start/end nearly stationary vs fast
print("  gap start SOG: median %.1f, share >10 kn %.0f%%" % (
    st.median([float(r["sog"]) for r in g if r["sog"]]),
    100 * sum(1 for r in g if r["sog"] and float(r["sog"]) > 10) / len(g)))
dist = [float(r["dist_nm"]) for r in g if r["dist_nm"]]
print("  displacement across the gap: median %.1f nm, p90 %.1f nm, max %.1f nm" % (
    st.median(dist), pct(dist, .9), max(dist)))

# ---------- OpenSanctions join
print("\n=== OpenSanctions join ===")
os_rows = list(csv.DictReader(open(os.path.join(D, "os", "maritime.csv"), encoding="utf-8")))
osv = [r for r in os_rows if r["type"] == "VESSEL"]
by_mmsi, by_imo = {}, {}
for r in osv:
    for m in filter(None, r["mmsi"].split(";")):
        by_mmsi.setdefault(m.strip(), []).append(r)
    im = r["imo"].strip().lstrip("IMO")
    if im:
        by_imo.setdefault(im, []).append(r)
print(f"  OpenSanctions vessels {len(osv)}, with MMSI {len(by_mmsi)}, with IMO {len(by_imo)}")

def tags(rs):
    t = set()
    for r in rs:
        t |= {x for x in r["risk"].split(";") if x}
    return t

hits = defaultdict(list)
unmatched_ca = 0
for r in ca:
    hs = by_mmsi.get(r["mmsi"], [])
    imo = r["imo"].strip().lstrip("IMO")
    src = "mmsi"
    if not hs and imo:
        hs = by_imo.get(imo, [])
        src = "imo"
    if hs:
        hits[r["mmsi"]].append((r, hs, src))
    else:
        unmatched_ca += 1
print(f"  Class A vessels matched to OpenSanctions: {len(hits)} of {len(ca)} "
      f"({100*len(hits)/len(ca):.1f}%)")
cat = Counter()
for m, lst in hits.items():
    r, hs, src = lst[0]
    t = tags(hs)
    if "mare.shadow" in t:
        cat["mare.shadow"] += 1
    elif "sanction" in t:
        cat["sanction only"] += 1
    elif "mare.detained" in t:
        cat["detention only"] += 1
    else:
        cat["other tag"] += 1
print("  by strongest tag:", dict(cat))
print("\n  the shadow-tagged and sanctioned-only vessels present on 2026-11-01:")
for m, lst in sorted(hits.items()):
    r, hs, src = lst[0]
    t = tags(hs)
    if "mare.shadow" in t or "sanction" in t:
        cap = hs[0]["caption"][:28]
        print(f"   {m} {r['name'][:26]:26s} {r['shiptype'][:18]:18s} "
              f"sog_max {r['sog_max']:>5s} gaps {len([x for x in g if x['mmsi']==m]):2d} "
              f"via {src:4s} {'SHADOW' if 'mare.shadow' in t else ''} "
              f"{'SANCTION' if 'sanction' in t else ''} | {cap}")
with open(os.path.join(DAY, "sanctions_match.json"), "w") as f:
    json.dump({m: dict(mmsi=m, name=lst[0][0]["name"], imo=lst[0][0]["imo"],
                       shiptype=lst[0][0]["shiptype"], via=lst[0][2],
                       tags=sorted(tags(lst[0][1])),
                       captions=[x["caption"] for x in lst[0][1]][:3],
                       risk=[x["risk"] for x in lst[0][1]][:3],
                       datasets=[x["datasets"] for x in lst[0][1]][:3])
               for m, lst in hits.items()}, f, indent=1)
