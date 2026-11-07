#!/usr/bin/env python3
"""Analyse CetaHAV /ais poll + paired Digitraffic poll."""
import json, math, statistics, sys

WAVE = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave"
rows = [json.loads(l) for l in open(f"{WAVE}/data/t-feeds/ceta_ais_poll.jsonl")]
ok = [r for r in rows if r.get("status") == 200]
print(f"polls={len(rows)} ok={len(ok)} errors={len(rows)-len(ok)}")
els = [r["elapsed"] for r in ok]
print("elapsed s: median", statistics.median(els), "min", min(els), "max", max(els))
ns = [r["n"] for r in ok]
print("features: min", min(ns), "median", statistics.median(ns), "max", max(ns))
mmsi_sets = [{f["mmsi"] for f in r["features"]} for r in ok]
allm = set().union(*mmsi_sets)
print("distinct MMSI over run:", len(allm))
print("per-poll new MMSI (never seen before):",
      [len(s - set().union(*mmsi_sets[:i])) if i else len(s) for i, s in enumerate(mmsi_sets)])
print("stable across all polls:", len(set.intersection(*mmsi_sets)))

lons = [f["lon"] for r in ok for f in r["features"]]
lats = [f["lat"] for r in ok for f in r["features"]]
print(f"bbox lon {min(lons):.3f}..{max(lons):.3f} lat {min(lats):.3f}..{max(lats):.3f}")

def region(lat, lon):
    if lon < 12.6 and lat < 58.0: return "Danish straits/Kattegat"
    if lon < 14 and lat >= 57: return "Skagerrak"
    if lon < 19: return "Baltic proper (S)"
    if lon >= 19 and lat >= 58.5: return "Gulf of Finland"
    return "Baltic proper (E)"

reg = {}
for r in ok:
    for f in r["features"]:
        reg[region(f["lat"], f["lon"])] = reg.get(region(f["lat"], f["lon"]), 0) + 1
print("region share:", {k: round(100*v/sum(reg.values()), 1) for k, v in sorted(reg.items(), key=lambda x: -x[1])})
print("per region distinct-mmsi:", {k: len({f["mmsi"] for r in ok for f in r["features"] if region(f["lat"], f["lon"]) == k}) for k in reg})

# movement between consecutive polls for the same MMSI
def dist_nm(a, b):
    R = 3440.065
    p1, p2 = math.radians(a[1]), math.radians(b[1])
    dp = p2 - p1; dl = math.radians(b[0] - a[0])
    h = math.sin(dp/2)**2 + math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(h))

moved = same = 0
shifts = []
for a, b in zip(ok, ok[1:]):
    dt = b["t_req"] - a["t_req"]
    amap = {f["mmsi"]: f for f in a["features"]}
    for f in b["features"]:
        g = amap.get(f["mmsi"])
        if not g: continue
        d = dist_nm((g["lon"], g["lat"]), (f["lon"], f["lat"]))
        if d < 1e-6: same += 1
        else:
            moved += 1; shifts.append((d, dt, f["sog"]))
print(f"consecutive-poll comparison: identical position {same}, changed {moved}")
if shifts:
    ds = [s[0] for s in shifts]
    print("changed-position distance nm: median", round(statistics.median(ds), 3),
          "p90", round(sorted(ds)[int(.9*len(ds))], 3), "max", round(max(ds), 3))

# name presence
names = [f["name"] for r in ok for f in r["features"]]
print("empty name share:", round(100*sum(1 for n in names if not n)/len(names), 1), "%")

# ---- paired digitraffic comparison ----
try:
    crows = [json.loads(l) for l in open(f"{WAVE}/data/t-feeds/pair.ceta.jsonl")]
    drows = [json.loads(l) for l in open(f"{WAVE}/data/t-feeds/pair.digi.jsonl")]
except FileNotFoundError:
    sys.exit()
cok = [r for r in crows if r.get("status") == 200]
dok = [r for r in drows if r.get("status") == 200]
print(f"\npair: ceta ok {len(cok)}, digi ok {len(dok)}")
digi_mmsi = {f["mmsi"] for r in dok for f in r["features"]}
ceta_mmsi = {f["mmsi"] for r in cok for f in r["features"]}
print("ceta MMSI in digitraffic:", len(ceta_mmsi & digi_mmsi), "of", len(ceta_mmsi))
print("digi MMSI seen by ceta:", len(ceta_mmsi & digi_mmsi), "of", len(digi_mmsi))

# build digitraffic tracks
tracks = {}
for r in dok:
    for f in r["features"]:
        tracks.setdefault(f["mmsi"], []).append((f["ts"]/1000.0, f["lon"], f["lat"], f["sog"]))

lags, dists = [], []
for r in cok:
    for f in r["features"]:
        tr = tracks.get(f["mmsi"])
        if not tr: continue
        best = min(tr, key=lambda p: dist_nm((p[1], p[2]), (f["lon"], f["lat"])))
        d = dist_nm((best[1], best[2]), (f["lon"], f["lat"]))
        if d > 0.5: continue  # >0.5 nm: not the same fix, skip
        lags.append(r["t"] - best[0]); dists.append(d)
if lags:
    lags.sort()
    print(f"matched {len(lags)} ceta positions onto digitraffic fixes (within 0.5 nm)")
    print("  implied age of ceta position, seconds: median", round(statistics.median(lags)),
          "p10", round(lags[int(.1*len(lags))]), "p90", round(lags[int(.9*len(lags))]),
          "min", round(lags[0]), "max", round(lags[-1]))
    print("  match distance nm: median", round(statistics.median(dists), 3))
