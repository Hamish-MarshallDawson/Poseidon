"""id-fuzzy: name-difference classification, IMO check digits, MMSI validity, MMSI-change structure."""
import json, sys, re, random, collections, itertools, unicodedata

WAVE = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave"
MID = json.load(open(f"{WAVE}/data/id-fuzzy/mid_wikipedia.json"))
random.seed(7)

# ---------- basic validators ----------
def imo_check(imo):
    s = str(imo)
    if len(s) != 7 or not s.isdigit():
        return None
    total = sum(int(c) * w for c, w in zip(s[:6], (7, 6, 5, 4, 3, 2)))
    return str(total % 10) == s[6]

def mmsi_class(mmsi):
    s = str(mmsi)
    if len(s) != 9 or not s.isdigit():
        return "not_9_digits"
    if s[0] == "0":
        return "group"
    if s[0] == "1":
        return "sar_aircraft" if s[1] == "1" else "handheld"
    if s.startswith("98"):
        return "aux_craft"
    if s.startswith("99"):
        return "aid_to_navigation"
    if s.startswith("970"):
        return "aid_to_navigation"
    if s.startswith("972"):
        return "craft_assoc_parent"
    if s[0] in "2345678":
        return "ship" if s[:3] in MID else "ship_bad_mid"
    if s[0] == "8":
        return "handheld"
    return "other"

# ---------- name normalisation and difference classification ----------
def norm(s):
    s = unicodedata.normalize("NFKD", s or "")
    s = s.upper()
    s = re.sub(r"\s+", " ", s).strip()
    return s

def squash(s):
    return re.sub(r"[^A-Z0-9]", "", norm(s))

def lev(a, b, cap=99):
    if a == b:
        return 0
    if abs(len(a) - len(b)) > cap:
        return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        best = i
        for j, cb in enumerate(b, 1):
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            cur.append(v)
            if v < best:
                best = v
        if best > cap:
            return cap + 1
        prev = cur
    return prev[-1]

LEAD_TOKENS = {"MV", "MT", "M/V", "M/T", "MTS", "MS", "M/S", "SS", "S/S", "SV", "MY", "FV", "TS", "PSV", "AHTS"}
ABBREV_SKIP = {"NO", "OF", "THE", "AND"}

def classify(a, b):
    """Return (category, similarity dict) for two distinct raw name strings."""
    na, nb = norm(a), norm(b)
    sa, sb = squash(a), squash(b)
    levd = lev(sa, sb, cap=30)
    ratio = 1 - levd / max(len(sa), len(sb), 1)
    # 1 padding / case / space collapse
    if na == nb:
        return "spacing_case", ratio
    if sa == sb:
        return "punctuation", ratio
    # 2 pure truncation at 20 AIS characters
    la, lb = len(norm(a)), len(norm(b))
    if (la == 20 and nb.startswith(na) and len(nb) > la) or (lb == 20 and na.startswith(nb) and len(na) > lb):
        return "truncation20", ratio
    # 3 leading/trailing prefix token (MV, M/T ...)
    ta, tb = na.split(), nb.split()
    if len(ta) > 1 and ta[0] in LEAD_TOKENS and ta[1:] == tb:
        return "prefix_token", ratio
    if len(tb) > 1 and tb[0] in LEAD_TOKENS and tb[1:] == ta:
        return "prefix_token", ratio
    if len(ta) > 1 and ta[-1] in LEAD_TOKENS and ta[:-1] == tb:
        return "prefix_token", ratio
    if len(tb) > 1 and tb[-1] in LEAD_TOKENS and tb[:-1] == ta:
        return "prefix_token", ratio
    # 4 abbreviation: initials of the other
    for x, y in ((ta, tb), (tb, ta)):
        if len(x) > 1 and len(y) > 1 and "".join(w[0] for w in x) == "".join(y):
            return "abbreviation", ratio
        if len(x) > 1 and len(y) > 1 and "".join(w[0] for w in x if w not in ABBREV_SKIP) == "".join(y):
            return "abbreviation", ratio
    # 5 typo
    if levd <= 2 and ratio >= 0.85:
        return "typo", ratio
    if levd <= 3 and ratio >= 0.9:
        return "typo", ratio
    return "real_difference", ratio

# ---------- GFW ----------
gfw = [json.loads(l) for l in open(f"{WAVE}/data/identity/gfw-identities.jsonl")]
res = {}
res["gfw_records"] = len(gfw)
res["gfw_groups"] = {f"{k[0]}|{k[1]}": v for k, v in collections.Counter((r["group"], r["region"]) for r in gfw).items()}

gfw_pairs = []          # (imo, cat, ratio, a, b, kind)
gfw_mmsi_change = []    # (imo, flag_from, flag_to, mmsi_from, mmsi_to, mid_from, mid_to)
gfw_imo_defects = collections.Counter()
gfw_imo_entries = 0
for r in gfw:
    for e in r["entries"]:
        sr = e.get("selfReportedInfo") or []
        ri = e.get("registryInfo") or []
        # order self-reported periods by start date
        sr_sorted = sorted(sr, key=lambda x: x.get("transmissionDateFrom") or "")
        for x in sr:
            gfw_imo_entries += 1
            im = (x.get("imo") or "").strip()
            if not im or im in ("0", "0000000"):
                gfw_imo_defects["zero_or_blank"] += 1
            elif imo_check(im) is False:
                gfw_imo_defects["bad_check_digit"] += 1
            elif imo_check(im) is None:
                gfw_imo_defects["malformed"] += 1
            else:
                gfw_imo_defects["valid"] += 1
        for a, b in zip(sr_sorted, sr_sorted[1:]):
            if (a.get("ssvid") or "") != (b.get("ssvid") or "") and a.get("ssvid"):
                gfw_mmsi_change.append(dict(
                    imo=r["imo"], group=r["group"], region=r["region"],
                    flag_a=a.get("flag"), flag_b=b.get("flag"),
                    mmsi_a=a.get("ssvid"), mmsi_b=b.get("ssvid"),
                    mid_a=str(a.get("ssvid"))[:3], mid_b=str(b.get("ssvid"))[:3],
                    date_a=a.get("transmissionDateTo"), date_b=b.get("transmissionDateFrom")))
            na, nb = a.get("shipname") or "", b.get("shipname") or ""
            if na and nb and norm(na) != norm(nb):
                c, ratio = classify(na, nb)
                gfw_pairs.append(dict(imo=r["imo"], group=r["group"], region=r["region"],
                                      kind="self_report_rename", cat=c, ratio=round(ratio, 3), a=na, b=nb))
        # flagged names within one self-reported period (same ssvid, several shipname entries)
        for x in sr:
            if x.get("shipname") and norm(x["shipname"]) != norm(x.get("nShipname") or x["shipname"]):
                pass
        # AIS name vs registry name
        for x in sr:
            for y in ri:
                if x.get("ssvid") and x.get("ssvid") == y.get("ssvid"):
                    na, nb = x.get("shipname") or "", y.get("shipname") or ""
                    if na and nb and norm(na) != norm(nb):
                        c, ratio = classify(na, nb)
                        gfw_pairs.append(dict(imo=r["imo"], group=r["group"], region=r["region"],
                                              kind="ais_vs_registry", cat=c, ratio=round(ratio, 3), a=na, b=nb))

res["gfw_imo_defects"] = dict(gfw_imo_defects)
res["gfw_imo_entries"] = gfw_imo_entries
res["gfw_pairs_n"] = len(gfw_pairs)
res["gfw_pairs_by_kind"] = {f"{k[0]}|{k[1]}": v for k, v in collections.Counter((p["kind"], p["cat"]) for p in gfw_pairs).items()}
res["gfw_mmsi_changes"] = gfw_mmsi_change

# ---------- AISStream capture ----------
capt = {}
path = f"{WAVE}/data/identity/aisstream-capture.jsonl"
for line in open(path):
    try:
        d = json.loads(line)
    except Exception:
        continue
    m = d["msg"]
    t = m.get("MessageType")
    md = m.get("MetaData") or {}
    mmsi = md.get("MMSI")
    if not mmsi:
        continue
    rec = capt.setdefault(mmsi, {"names": collections.Counter(), "imos": collections.Counter(),
                                 "callsigns": collections.Counter(), "types": collections.Counter(),
                                 "dims": collections.Counter(), "src": set()})
    body = (m.get("Message") or {})
    if t == "ShipStaticData":
        b = body.get("ShipStaticData") or {}
        for k, tgt in (("Name", "names"), ("CallSign", "callsigns")):
            v = (b.get(k) or "").strip()
            if v:
                rec[tgt][v] += 1
        if b.get("ImoNumber"):
            rec["imos"][str(b["ImoNumber"])] += 1
        if b.get("Type"):
            rec["types"][str(b["Type"])] += 1
        dm = b.get("Dimension") or {}
        dim = (dm.get("A", 0) + dm.get("B", 0), dm.get("C", 0) + dm.get("D", 0))
        if any(dim):
            rec["dims"][str(dim)] += 1
        rec["src"].add("A")
    elif t == "StaticDataReport":
        b = body.get("StaticDataReport") or {}
        ra = b.get("ReportA") or {}
        rb = b.get("ReportB") or {}
        v = (ra.get("Name") or "").strip()
        if v:
            rec["names"][v] += 1
        v = (rb.get("CallSign") or "").strip()
        if v:
            rec["callsigns"][v] += 1
        if rb.get("ShipType"):
            rec["types"][str(rb["ShipType"])] += 1
        dm = rb.get("Dimension") or {}
        dim = (dm.get("A", 0) + dm.get("B", 0), dm.get("C", 0) + dm.get("D", 0))
        if any(dim):
            rec["dims"][str(dim)] += 1
        rec["src"].add("B")

res["capture_messages"] = sum(1 for _ in open(path))
res["capture_mmsi"] = len(capt)
res["capture_with_name"] = sum(1 for r in capt.values() if r["names"])
res["capture_multi_name"] = sum(1 for r in capt.values() if len(r["names"]) > 1)
res["capture_multi_imo"] = sum(1 for r in capt.values() if len(r["imos"]) > 1)
res["capture_multi_callsign"] = sum(1 for r in capt.values() if len(r["callsigns"]) > 1)
res["capture_multi_type"] = sum(1 for r in capt.values() if len(r["types"]) > 1)
res["capture_multi_dim"] = sum(1 for r in capt.values() if len(r["dims"]) > 1)

cap_imo = collections.Counter()
for r in capt.values():
    for im, c in r["imos"].items():
        cap_imo[im] += 1
res["capture_imo_defects"] = dict(collections.Counter(
    "zero" if im in ("0", "0000000") else ("bad_check_digit" if imo_check(im) is False else
     ("malformed" if imo_check(im) is None else "valid")) for im in
    [im for r in capt.values() for im in r["imos"]]))

cap_pairs = []
for mmsi, r in capt.items():
    ns = sorted(r["names"])
    for a, b in itertools.combinations(ns, 2):
        c, ratio = classify(a, b)
        cap_pairs.append(dict(mmsi=mmsi, cat=c, ratio=round(ratio, 3), a=a, b=b, kind="same_mmsi_20min"))
res["capture_pairs_n"] = len(cap_pairs)
res["capture_pairs_by_cat"] = dict(collections.Counter(p["cat"] for p in cap_pairs))

# MMSI classes in capture
res["capture_mmsi_class"] = dict(collections.Counter(mmsi_class(m) for m in capt))

# ---------- Danish day ----------
try:
    dk = json.load(open(f"{WAVE}/data/id-fuzzy/dk_variants.json"))
    dk_ok = True
except Exception:
    dk = {"rows": 0, "vessels": {}}
    dk_ok = False
res["dk_ready"] = dk_ok
if dk_ok:
    V = dk["vessels"]
    res["dk_rows"] = dk["rows"]
    res["dk_vessels_with_static"] = len(V)
    res["dk_multi_name"] = sum(1 for r in V.values() if len(r["names"]) > 1)
    res["dk_multi_imo"] = sum(1 for r in V.values() if len(r["imos"]) > 1)
    res["dk_multi_callsign"] = sum(1 for r in V.values() if len(r["callsigns"]) > 1)
    res["dk_multi_type"] = sum(1 for r in V.values() if len(r["shiptypes"]) > 1)
    res["dk_multi_dim"] = sum(1 for r in V.values() if len(r["dims"]) > 1)
    dk_pairs = []
    for m, r in V.items():
        for a, b in itertools.combinations(sorted(n for n, _ in r["names"]), 2):
            c, ratio = classify(a, b)
            dk_pairs.append(dict(mmsi=m, cat=c, ratio=round(ratio, 3), a=a, b=b, kind="same_mmsi_1day"))
    res["dk_pairs_n"] = len(dk_pairs)
    res["dk_pairs_by_cat"] = dict(collections.Counter(p["cat"] for p in dk_pairs))
    res["dk_imo_defects"] = dict(collections.Counter(
        "zero" if im in ("0", "0000000", "Unknown") else ("bad_check_digit" if imo_check(im) is False else
         ("malformed" if imo_check(im) is None else "valid"))
        for r in V.values() for im in r["imos"]))
    res["dk_imo_vessels_with_imo"] = sum(1 for r in V.values() if r["imos"])
    res["dk_mmsi_class"] = dict(collections.Counter(mmsi_class(m) for m in V))
    # bad-check IMO: nearest valid other IMO for the same vessel (typo hypothesis)
    fixable = 0; bad_imos = 0
    for m, r in V.items():
        ims = [im for im, _ in r["imos"]]
        bad = [im for im in ims if imo_check(im) is False and len(im) == 7]
        good = [im for im in ims if imo_check(im) is True]
        for b in bad:
            bad_imos += 1
            if any(lev(b, g, cap=1) == 1 for g in good):
                fixable += 1
    res["dk_bad_imo_values"] = bad_imos
    res["dk_bad_imo_with_1digit_valid_sibling"] = fixable
else:
    dk_pairs = []

# ---------- hand-check sample ----------
pool = gfw_pairs + cap_pairs + dk_pairs
by_cat = collections.defaultdict(list)
for p in pool:
    by_cat[p["cat"]].append(p)
sample = []
for cat in ("spacing_case", "punctuation", "truncation20", "prefix_token", "abbreviation", "typo", "real_difference"):
    lst = by_cat.get(cat, [])[:]
    random.shuffle(lst)
    sample.extend(lst[:10])

json.dump(dict(res=res, gfw_pairs=gfw_pairs, gfw_mmsi_changes=gfw_mmsi_change,
               cap_pairs=cap_pairs, dk_pairs=dk_pairs, sample=sample),
          open(f"{WAVE}/data/id-fuzzy/results.json", "w"), indent=1, default=str)

print(json.dumps(res, indent=1, default=str)[:6000])
print("\n=== SAMPLE (for hand check) ===")
for p in sample:
    print(f"{p['cat']:16s} r={p['ratio']:<5} | {p['a']!r:28s} -> {p['b']!r:28s} | {p.get('kind')}")
