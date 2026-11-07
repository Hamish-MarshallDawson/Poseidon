#!/usr/bin/env python3
"""id-joins: cross-source join rates and field conflicts for ship identity."""
import csv, json, re, sys, collections as C

W = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave"
DJ = W + "/data/t-ais-history/day_2026-11-01"
DS = W + "/data/id-joins"

def norm(n):
    if not n: return ""
    return re.sub(r"[^A-Z0-9]", "", str(n).upper())

def imo_ok(v):
    if not v: return None
    s = str(v).strip()
    if s in ("0", "", "None"): return None
    if not s.isdigit() or len(s) != 7: return False
    chk = sum(int(d) * (7 - i) for i, d in enumerate(s[:6]))
    return chk % 10 == int(s[6])

def num(v):
    try:
        f = float(v)
        return f if f > 0 else None
    except Exception:
        return None

out = {}
print("== SOURCE INVENTORIES ==")

# --- Danish vessels.csv (1 day, 2026-11-01, DK waters) ---
dk = []
for r in csv.DictReader(open(DJ + "/vessels.csv")):
    if r["cls"] == "Base Station": continue
    dk.append(r)
dk_mmsi = {r["mmsi"] for r in dk}
dk_imo = {str(int(r["imo"])) for r in dk if r["imo"].strip().isdigit() and r["imo"].strip() not in ("", "0")}
dk_by_mmsi = {r["mmsi"]: r for r in dk}
print(f"Danish vessels.csv: {len(dk)} ships; with name {sum(1 for r in dk if r['name'].strip())}; "
      f"with IMO {sum(1 for r in dk if r['imo'].strip() not in ('','0'))}; "
      f"with callsign {sum(1 for r in dk if r['callsign'].strip())}; "
      f"with shiptype {sum(1 for r in dk if r['shiptype'].strip())}; "
      f"with length {sum(1 for r in dk if r['length'].strip())}")
print("  by class:", C.Counter(r["cls"] for r in dk))
# IMO validity in Danish
dk_imo_vals = [r["imo"].strip() for r in dk if r["imo"].strip() not in ("", "0")]
ok = sum(1 for v in dk_imo_vals if imo_ok(v) is True)
print(f"  IMO values {len(dk_imo_vals)}: valid check digit {ok}, bad {sum(1 for v in dk_imo_vals if imo_ok(v) is False)}, zero/blank excluded")
dk_imo_by_class = C.Counter(r["cls"] for r in dk if r["imo"].strip() not in ("", "0"))
dk_cls = C.Counter(r["cls"] for r in dk)
print(f"  IMO coverage by class: " + ", ".join(f"{k} {dk_imo_by_class[k]}/{dk_cls[k]} = {100*dk_imo_by_class[k]/dk_cls[k]:.0f}%" for k in dk_cls if k != "Base Station"))

# --- Digitraffic vessels ---
dt = json.load(open(DS + "/digitraffic-vessels.json"))
dt_mmsi = {str(v["mmsi"]) for v in dt}
dt_imo = {str(v["imo"]) for v in dt if v.get("imo")}
print(f"Digitraffic /vessels: {len(dt)} vessels; with name {sum(1 for v in dt if v.get('name'))}; "
      f"with IMO {len(dt_imo)}; with callSign {sum(1 for v in dt if v.get('callSign'))}; "
      f"with shipType {sum(1 for v in dt if v.get('shipType'))}")
print("  posType (0=?, 1=A, 15=B):", C.Counter(v.get("posType") for v in dt).most_common())
dt_imo_cls = C.Counter("A" if v.get("posType") == 1 else "B/other" for v in dt if v.get("imo"))
dt_cls = C.Counter("A" if v.get("posType") == 1 else "B/other" for v in dt)
print("  IMO coverage by class:", {k: f"{dt_imo_cls[k]}/{dt_cls[k]} = {100*dt_imo_cls[k]/dt_cls[k]:.0f}%" for k in dt_cls})
print("  IMO coverage by posType:", {p: f"{sum(1 for v in dt if v.get('posType')==p and v.get('imo'))}/{sum(1 for v in dt if v.get('posType')==p)}" for p in sorted({v.get('posType') for v in dt})})

# --- AISStream capture ---
msgs = []
for line in open(W + "/data/identity/aisstream-capture.jsonl"):
    try: msgs.append(json.loads(line))
    except Exception: pass
print(f"AISStream capture: {len(msgs)} raw messages")
mt = C.Counter(m.get("msg", {}).get("MessageType") for m in msgs)
print("  message types:", mt.most_common())
stat = {}   # mmsi -> dict(name, imo, callsign, type, len, src, cls)
pos_mmsi = set()
for m in msgs:
    msg = m.get("msg", {})
    typ = msg.get("MessageType"); md = msg.get("MetaData", {})
    mm = str(md.get("MMSI") or md.get("MMSI_String") or "")
    if mm: pos_mmsi.add(mm)
    b = msg.get("Message", {})
    d = None; cls = None
    if typ == "ShipStaticData":
        d = b.get("ShipStaticData", {}); cls = "A"
    elif typ == "StaticDataReport":
        d = b.get("StaticDataReport", {}); cls = "B"
    if d is None: continue
    e = stat.setdefault(mm, {"name": "", "imo": "", "callsign": "", "type": "", "len": None, "cls": cls, "src": set()})
    e["src"].add(typ)
    if cls == "A":
        if d.get("Name"): e["name"] = e["name"] or d["Name"].strip()
        im = d.get("ImoNumber")
        if im and str(im) not in ("0", "None"): e["imo"] = str(im)
        if d.get("CallSign"): e["callsign"] = e["callsign"] or d["CallSign"].strip()
        if d.get("Type"): e["type"] = str(d["Type"])
        dim = d.get("Dimension") or {}
        L = (dim.get("A") or 0) + (dim.get("B") or 0)
        if L: e["len"] = L
    else:
        ra = d.get("ReportA") or {}; rb = d.get("ReportB") or {}
        if ra.get("Name"): e["name"] = e["name"] or ra["Name"].strip()
        if rb.get("CallSign"): e["callsign"] = e["callsign"] or rb["CallSign"].strip()
        if rb.get("ShipType"): e["type"] = str(rb["ShipType"])
        dim = rb.get("Dimension") or {}
        L = (dim.get("A") or 0) + (dim.get("B") or 0)
        if L: e["len"] = L
as_mmsi = set(stat) | pos_mmsi
as_imo = {e["imo"] for e in stat.values() if e["imo"]}
print(f"  distinct MMSI seen: {len(pos_mmsi)}; with static record {len(stat)}; "
      f"with name {sum(1 for e in stat.values() if e['name'])}; with IMO {len(as_imo)}; "
      f"with callsign {sum(1 for e in stat.values() if e['callsign'])}")
print("  static by class:", C.Counter(e["cls"] for e in stat.values()))
for cl in ("A", "B"):
    tot = sum(1 for e in stat.values() if e["cls"] == cl)
    w = sum(1 for e in stat.values() if e["cls"] == cl and e["imo"])
    print(f"    class {cl}: IMO on {w}/{tot} = {100*w/max(tot,1):.0f}%")

# --- OpenSanctions maritime ---
os_rows = list(csv.DictReader(open(W + "/data/t-ais-history/os/maritime.csv")))
def multi(v):
    return [x.strip() for x in re.split(r"[;,]", v or "") if x.strip()]
def os_imos(r):
    return {x[3:] for x in multi(r["imo"]) if x.upper().startswith("IMO") and x[3:].isdigit()}
def os_mmsis(r):
    return {x for x in multi(r["mmsi"]) if x.isdigit()}
os_mmsi = {m for r in os_rows for m in os_mmsis(r)}
os_imo = {i for r in os_rows for i in os_imos(r)}
print(f"OpenSanctions maritime.csv: {len(os_rows)} rows; type counts {C.Counter(r['type'] for r in os_rows).most_common(6)}")
print(f"  with MMSI {sum(1 for r in os_rows if os_mmsis(r))} ({100*sum(1 for r in os_rows if os_mmsis(r))/len(os_rows):.0f}%); "
      f"with IMO {sum(1 for r in os_rows if os_imos(r))} ({100*sum(1 for r in os_rows if os_imos(r))/len(os_rows):.0f}%); "
      f"both {sum(1 for r in os_rows if os_mmsis(r) and os_imos(r))}")
print(f"  distinct values: {len(os_mmsi)} MMSI, {len(os_imo)} IMO")
print(f"  rows with >1 MMSI: {sum(1 for r in os_rows if len(os_mmsis(r)) > 1)}; >1 IMO: {sum(1 for r in os_rows if len(os_imos(r)) > 1)}")
print(f"  dataset tags: {C.Counter(d for r in os_rows for d in multi(r['datasets'])).most_common(10)}")
bad_os_imo = sum(1 for i in os_imo if imo_ok(i) is False)
bad_os_mmsi = sum(1 for m in os_mmsi if len(m) != 9 or not (200 <= int(m[:3]) <= 799))
print(f"  IMO bad check digit: {bad_os_imo}/{len(os_imo)}; MMSI not 9 digits or MID 200-799: {bad_os_mmsi}/{len(os_mmsi)}")
# which datasets do the DK MMSI hits come from
os_by_mmsi = {}
for r in os_rows:
    for m in os_mmsis(r):
        os_by_mmsi.setdefault(m, []).append(r)
print(f"  DK hits by dataset: {C.Counter(d for m in (dk_mmsi & os_mmsi) for r in os_by_mmsi[m] for d in multi(r['datasets'])).most_common(8)}")
print(f"  DK hits where broadcast IMO differs from listed IMO:")
n_mis = 0
for m in sorted(dk_mmsi & os_mmsi):
    b = dk_by_mmsi[m]["imo"].strip()
    listed = {i for r in os_by_mmsi[m] for i in os_imos(r)}
    if b and b != "0" and listed and b not in listed:
        n_mis += 1
        if n_mis <= 5: print(f"    mmsi {m} dk_imo {b} listed {sorted(listed)} name_dk {dk_by_mmsi[m]['name']}")
print(f"    total {n_mis}")

# --- GFW identities ---
gfw = [json.loads(l) for l in open(W + "/data/identity/gfw-identities.jsonl")]
g_imo = {str(r["imo"]) for r in gfw if r.get("imo")}
g_mmsi = set()
for r in gfw:
    for e in r.get("entries") or []:
        for s in e.get("selfReportedInfo") or []:
            if s.get("ssvid"): g_mmsi.add(str(s["ssvid"]))
print(f"GFW identities: {len(gfw)} IMO records (still growing during wave); {len(g_mmsi)} distinct MMSI (ssvid)")
print(f"  groups {C.Counter(r['group'] for r in gfw).most_common()}; regions {C.Counter(r['region'] for r in gfw).most_common()}")

print("\n== JOIN RATES ==")
def pct(a, b): return f"{a}/{b} = {100*a/max(b,1):.1f}%"
# DK <-> Digitraffic (same live-ish universe, both Nordic)
i_joint_dt = dk_mmsi & dt_mmsi
print(f"DK(2026-11-01) ∩ Digitraffic(vessels, latest static): {pct(len(i_joint_dt), len(dk_mmsi))} of DK MMSIs")
print(f"  DK ships with IMO that appear in Digitraffic by IMO: {pct(len(dk_imo & dt_imo), len(dk_imo))}")
dk_mmsi_no_imo = dk_mmsi - {r['mmsi'] for r in dk if r['imo'].strip() not in ('','0')}
print(f"  DK ships without IMO that appear in Digitraffic by MMSI: {pct(len(dk_mmsi_no_imo & dt_mmsi), len(dk_mmsi_no_imo))}")
print(f"  DK ships with IMO, not in Digitraffic by MMSI but IMO found there: "
      f"{len({r['mmsi'] for r in dk if r['imo'].strip() not in ('','0')} - dt_mmsi & {r['mmsi'] for r in dk if r['imo'].strip() not in ('','0')} and set())}")
# DK <-> AISStream (different time, worldwide capture)
print(f"DK ∩ AISStream(capture) by MMSI: {pct(len(dk_mmsi & as_mmsi), len(dk_mmsi))}")
print(f"DK IMO ∩ AISStream IMO: {pct(len(dk_imo & as_imo), len(dk_imo))}")
# DK <-> OpenSanctions
print(f"DK ∩ OpenSanctions by MMSI: {pct(len(dk_mmsi & os_mmsi), len(dk_mmsi))}  (hits: {sorted(dk_mmsi & os_mmsi)[:10]})")
print(f"DK IMO ∩ OpenSanctions IMO: {pct(len(dk_imo & os_imo), len(dk_imo))}  (hits: {sorted(dk_imo & os_imo)[:10]})")
print(f"AISStream IMO ∩ OpenSanctions IMO: {pct(len(as_imo & os_imo), len(as_imo))} (hits: {sorted(as_imo & os_imo)[:10]})")
print(f"GFW sample IMO ∩ OpenSanctions IMO: {pct(len(g_imo & os_imo), len(g_imo))} (hits: {sorted(g_imo & os_imo)[:10]})")
print(f"AISStream ∩ OpenSanctions by MMSI: {pct(len(as_mmsi & os_mmsi), len(as_mmsi))}")
print(f"AISStream IMO ∩ OpenSanctions IMO: {pct(len(as_imo & os_imo), len(as_imo))}")
# GFW sample <- DK / AISStream
print(f"GFW IMO sample ∩ DK IMO: {pct(len(g_imo & dk_imo), len(g_imo))}  (hits {sorted(g_imo & dk_imo)[:8]})")
print(f"GFW IMO sample ∩ AISStream IMO: {pct(len(g_imo & as_imo), len(g_imo))}")
print(f"GFW ssvid set ∩ DK MMSI: {pct(len(g_mmsi & dk_mmsi), len(g_mmsi))}; ∩ Digitraffic MMSI: {pct(len(g_mmsi & dt_mmsi), len(g_mmsi))}")
# how many GFW IMO records also carry a registry record & MMSI list length
reg_n = sum(1 for r in gfw for e in (r.get('entries') or []) for ri in (e.get('registryInfo') or []))
print(f"GFW registryInfo records: {reg_n}; owners {sum(1 for r in gfw for e in (r.get('entries') or []) for x in (e.get('registryOwners') or []))}")

print("\n== FIELD CONFLICTS ON THE SAME MMSI ==")
conf = C.Counter(); ex = C.defaultdict(list)
def cmp(a, b, field, mm):
    if not a or not b: conf[field + "_one_missing"] += 1; return
    if norm(a) == norm(b): conf[field + "_match"] += 1
    else:
        conf[field + "_differ"] += 1
        if len(ex[field]) < 6: ex[field].append((mm, a, b))
for mm in sorted(dk_mmsi & dt_mmsi):
    r = dk_by_mmsi[mm]; d = next(v for v in dt if str(v["mmsi"]) == mm)
    cmp(r["name"], d.get("name"), "DKvsDT_name", mm)
    cmp(r["callsign"], d.get("callSign"), "DKvsDT_callsign", mm)
    if r["imo"].strip() not in ("", "0") and d.get("imo"):
        conf["DKvsDT_imo_match" if str(r["imo"]).strip() == str(d["imo"]) else "DKvsDT_imo_differ"] += 1
        if str(r["imo"]).strip() != str(d["imo"]) and len(ex["imo_dkdt"]) < 6: ex["imo_dkdt"].append((mm, r["imo"], d["imo"]))
    if num(r["length"]) and d.get("referencePointA") is not None:
        dtl = (d.get("referencePointA") or 0) + (d.get("referencePointB") or 0)
        if dtl:
            delta = abs(float(r["length"]) - dtl)
            conf["DKvsDT_length_within1m" if delta <= 1 else "DKvsDT_length_gt1m"] += 1
            if delta > 1 and len(ex["length"]) < 6: ex["length"].append((mm, r["length"], dtl))
for mm in sorted(dk_mmsi & set(stat)):
    r = dk_by_mmsi[mm]; e = stat[mm]
    cmp(r["name"], e["name"], "DKvsAS_name", mm)
    cmp(r["callsign"], e["callsign"], "DKvsAS_callsign", mm)
    if r["imo"].strip() not in ("", "0") and e["imo"]:
        conf["DKvsAS_imo_match" if str(r["imo"]).strip() == e["imo"] else "DKvsAS_imo_differ"] += 1
        if str(r["imo"]).strip() != e["imo"] and len(ex["imo_dkas"]) < 6: ex["imo_dkas"].append((mm, r["imo"], e["imo"]))
    if num(r["length"]) and e["len"]:
        delta = abs(float(r["length"]) - e["len"])
        conf["DKvsAS_length_within1m" if delta <= 1 else "DKvsAS_length_gt1m"] += 1
        if delta > 1 and len(ex["length_as"]) < 6: ex["length_as"].append((mm, r["length"], e["len"]))
for mm in sorted(set(stat) & dt_mmsi):
    e = stat[mm]; d = next(v for v in dt if str(v["mmsi"]) == mm)
    cmp(e["name"], d.get("name"), "ASvsDT_name", mm)
for k in sorted(conf): print(f"  {k}: {conf[k]}")
for k, v in ex.items(): print(f"  examples {k}: {v}")

# MMSI validity across sources
def mmsi_valid(m):
    s = str(m)
    if len(s) != 9 or not s.isdigit(): return False
    mid = int(s[:3])
    return 200 <= mid <= 799
for label, s in (("DK", dk_mmsi), ("Digitraffic", dt_mmsi), ("AISStream", as_mmsi), ("OpenSanctions", os_mmsi)):
    bad = [m for m in s if not mmsi_valid(m)]
    print(f"  MMSI not 9 digits or MID outside 200-799 [{label}]: {len(bad)}/{len(s)} = {100*len(bad)/max(len(s),1):.2f}%  e.g. {sorted(bad)[:5]}")

# IMO check digit across sources
for label, s in (("DK", dk_imo), ("AISStream", as_imo), ("GFW sample", g_imo), ("OpenSanctions", os_imo)):
    vals = [v for v in s if v]
    good = sum(1 for v in vals if imo_ok(v) is True)
    bad = sum(1 for v in vals if imo_ok(v) is False)
    print(f"  IMO check digit [{label}]: valid {good}/{len(vals)}, invalid {bad}, coverage {100*len(vals)/max(len(s),1):.0f}% of distinct values tested")
