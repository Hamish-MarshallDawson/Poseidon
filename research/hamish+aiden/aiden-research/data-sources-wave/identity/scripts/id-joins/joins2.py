#!/usr/bin/env python3
"""id-joins part 2: join-key cardinality, GFW self-report vs registry, OS IMO quality."""
import csv, json, re, collections as C
W = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave"
DJ = W + "/data/t-ais-history/day_2026-11-01"

def norm(n):
    return re.sub(r"[^A-Z0-9]", "", str(n or "").upper())
def imo_ok(s):
    s = str(s)
    if not (s.isdigit() and len(s) == 7): return False
    return sum(int(d) * (7 - i) for i, d in enumerate(s[:6])) % 10 == int(s[6])
def pct(a, b): return f"{a}/{b} = {100*a/max(b,1):.1f}%"

# DK cardinality: one IMO on how many MMSIs in one day
dk = [r for r in csv.DictReader(open(DJ + "/vessels.csv")) if r["cls"] != "Base Station"]
imo2mm = C.defaultdict(set)
for r in dk:
    i = r["imo"].strip()
    if i and i != "0": imo2mm[i].add(r["mmsi"])
print("DK 1 day: IMO->distinct MMSI:", C.Counter(len(v) for v in imo2mm.values()))
multi = {k: v for k, v in imo2mm.items() if len(v) > 1}
print(f"  IMOs on >1 MMSI in one day: {len(multi)}/{len(imo2mm)} = {100*len(multi)/len(imo2mm):.1f}%")
for k, v in list(multi.items())[:6]:
    print(f"    IMO {k}: {sorted(v)} names {[r['name'] for r in dk if r['mmsi'] in v][:4]}")
print("  DK invalid-MMSI by class:", {c: sum(1 for r in dk if r['cls'] == c and not (len(r['mmsi']) == 9 and r['mmsi'].isdigit() and 200 <= int(r['mmsi'][:3]) <= 799)) for c in {r['cls'] for r in dk}})

# AISStream cardinality
as_imo2mm = C.defaultdict(set)
for line in open(W + "/data/identity/aisstream-capture.jsonl"):
    try: m = json.loads(line)
    except Exception: continue
    md = m.get("msg", {}).get("MetaData", {}); mm = str(md.get("MMSI") or "")
    d = (m.get("msg", {}).get("Message", {}) or {}).get("ShipStaticData")
    if d and d.get("ImoNumber") and str(d["ImoNumber"]) not in ("0", "None"):
        as_imo2mm[str(d["ImoNumber"])].add(mm)
print("AISStream 30 min: IMO->distinct MMSI:", C.Counter(len(v) for v in as_imo2mm.values()))
print(f"  IMOs on >1 MMSI: {sum(1 for v in as_imo2mm.values() if len(v) > 1)}/{len(as_imo2mm)}")
for k, v in [(k, v) for k, v in as_imo2mm.items() if len(v) > 1][:6]:
    print(f"    IMO {k}: {sorted(v)}")

# OpenSanctions: IMO cardinality + invalid IMO examples
os_rows = list(csv.DictReader(open(W + "/data/t-ais-history/os/maritime.csv")))
def multi(v): return [x.strip() for x in re.split(r"[;,]", v or "") if x.strip()]
os_imo2mm = C.defaultdict(set); bad = []
for r in os_rows:
    for x in multi(r["imo"]):
        if x.upper().startswith("IMO") and x[3:].isdigit():
            i = x[3:]
            if not imo_ok(i): bad.append((i, r["caption"], r["datasets"]))
            for m in multi(r["mmsi"]):
                if m.isdigit(): os_imo2mm[i].add(m)
print("OpenSanctions: IMO->distinct listed MMSI:", C.Counter(len(v) for v in os_imo2mm.values() if v))
print(f"  bad check digit examples: {bad[:6]}  total {len(bad)}")
bad_ds = C.Counter(d for _, _, ds in bad for d in multi(ds))
print(f"  bad check digit by dataset: {bad_ds.most_common(6)}")

# GFW self-report vs registry
gfw = [json.loads(l) for l in open(W + "/data/identity/gfw-identities.jsonl")]
cnt = C.Counter(); ex = C.defaultdict(list)
for r in gfw:
    for e in r.get("entries") or []:
        sri = e.get("selfReportedInfo") or []
        ri = e.get("registryInfo") or []
        if not sri or not ri: continue
        s, g = sri[0], ri[0]
        cnt["records"] += 1
        for f in ("shipname", "flag", "callsign", "ssvid"):
            a, b = s.get(f), g.get(f)
            if not a or not b: cnt[f + "_missing"] += 1; continue
            if norm(a) == norm(b): cnt[f + "_match"] += 1
            else:
                cnt[f + "_differ"] += 1
                if len(ex[f]) < 5: ex[f].append((r["imo"], a, b))
        # how complete is registry side
        if g.get("lengthM") is None: cnt["registry_no_length"] += 1
        if g.get("tonnageGt") is None: cnt["registry_no_gt"] += 1
        if not e.get("registryOwners"): cnt["no_owner"] += 1
        # MMSI list per IMO in self-reported
        cnt["selfrep_per_imo_%d" % len(sri)] += 1
        cnt["reg_per_imo_%d" % len(ri)] += 1
print("\nGFW selfReportedInfo[0] vs registryInfo[0]:")
for k in sorted(cnt): print(f"  {k}: {cnt[k]}")
for k, v in ex.items(): print(f"  examples {k}: {v}")
# ssvid history per IMO
print("  distinct ssvid per IMO in GFW:", C.Counter(len({x.get('ssvid') for x in (e.get('selfReportedInfo') or [])}) for e2 in [0] for r in gfw for e in (r.get('entries') or [])).most_common(6))
print("  IMOs with >=2 self-reported ssvid:", sum(1 for r in gfw for e in (r.get('entries') or []) if len({x.get('ssvid') for x in (e.get('selfReportedInfo') or [])}) >= 2), "/", len(gfw))
