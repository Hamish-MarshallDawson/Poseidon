"""id-fuzzy FINAL: one consistent snapshot of every figure quoted in the report."""
import json, re, collections, itertools
W = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave"
MID = json.load(open(f"{W}/data/id-fuzzy/mid_wikipedia.json"))
ROMAN = {'I': '1', 'II': '2', 'III': '3', 'IV': '4', 'V': '5', 'VI': '6'}
LEAD = {"MV", "MT", "M/V", "M/T", "MTS", "MS", "M/S", "SS", "SV", "MY", "FV", "TS"}
norm = lambda s: re.sub(r"\s+", " ", (s or "").upper()).strip()
sq = lambda s: re.sub(r"[^A-Z0-9]", "", norm(s))

def smart(s):
    t = norm(s)
    t = re.sub(r"\bNO[\.\s]*(\d)", r"\1", t)
    t = re.sub(r"\bNO\.?\b", "", t)
    t = re.sub(r"\b(III|II|IV|VI|V|I)\b", lambda m: ROMAN[m.group(1)], t)
    return re.sub(r"[^A-Z0-9]", "", t)

def lev(a, b, cap=99):
    if a == b: return 0
    if abs(len(a) - len(b)) > cap: return cap + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]; best = i
        for j, cb in enumerate(b, 1):
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)); cur.append(v); best = min(best, v)
        if best > cap: return cap + 1
        prev = cur
    return prev[-1]

ratio = lambda a, b: 1 - lev(sq(a), sq(b)) / max(len(sq(a)), len(sq(b)), 1)

def imo_check(imo):
    s = str(imo)
    if len(s) != 7 or not s.isdigit(): return None
    return str(sum(int(c) * w for c, w in zip(s[:6], (7, 6, 5, 4, 3, 2))) % 10) == s[6]

def classify(a, b):
    na, nb = norm(a), norm(b); sa, sb = sq(a), sq(b)
    if na == nb: return "spacing_case"
    if sa == sb: return "punctuation"
    if smart(a) == smart(b): return "roman_or_no"
    ta, tb = na.split(), nb.split()
    if (ta[1:] == tb or tb[1:] == ta or ta[:-1] == tb or tb[:-1] == ta) and ((ta and ta[0] in LEAD) or (tb and tb[0] in LEAD)):
        return "prefix_token"
    d = lev(sa, sb, cap=30); r = 1 - d / max(len(sa), len(sb), 1)
    if (d <= 2 and r >= 0.85) or (d <= 3 and r >= 0.9): return "typo"
    return "real_difference"

print("== AISStream capture ==")
msgs = 0; ms = set(); named = set(); stat = collections.defaultdict(collections.Counter)
meta = collections.defaultdict(collections.Counter); imos = collections.defaultdict(set)
nstr = l20 = zimo = ssm = 0
for l in open(f"{W}/data/identity/aisstream-capture.jsonl"):
    d = json.loads(l); m = d["msg"]; t = m.get("MessageType"); md = m.get("MetaData") or {}
    msgs += 1; mm = md.get("MMSI")
    if mm: ms.add(mm)
    b = (m.get("Message") or {}); nm = None
    if t == "ShipStaticData":
        b2 = b["ShipStaticData"]; ssm += 1; nm = b2.get("Name")
        if b2.get("ImoNumber"): imos[mm].add(str(b2["ImoNumber"]))
        else: zimo += 1
    elif t == "StaticDataReport":
        nm = ((b.get("StaticDataReport") or {}).get("ReportA") or {}).get("Name")
    if nm and nm.strip():
        stat[mm][nm.strip()] += 1; named.add(mm); nstr += 1; l20 += len(nm.strip()) == 20
    if (md.get("ShipName") or "").strip(): meta[mm][md["ShipName"].strip()] += 1
ship = [m for m in ms if len(str(m)) == 9 and str(m)[0] in "2345678"]
allim = [i for s in imos.values() for i in s]
both = [m for m in stat if meta.get(m)]
dis = [m for m in both if {x.upper().strip() for x in stat[m]} != {x.upper().strip() for x in meta[m]}]
print(f"messages {msgs} | mmsis {len(ms)} | named {len(named)} | name strings {nstr} | exactly 20 chars {l20} ({100*l20/nstr:.1f}%)")
print(f"ship-range mmsi {len(ship)} | unallocated MID {sum(1 for m in ship if str(m)[:3] not in MID)} | not 9 digits {len([m for m in ms if len(str(m)) != 9])}")
print(f"ShipStaticData {ssm} | IMO missing/0 {zimo} ({100*zimo/ssm:.0f}%) | distinct IMO values {len(set(allim))} | bad check {sum(1 for i in allim if imo_check(i) is False)} | not 7 digits {sum(1 for i in allim if imo_check(i) is None)}")
print(f"mmsi with >1 static name {sum(1 for v in stat.values() if len(v) > 1)} | meta-vs-static both {len(both)} disagree {len(dis)}")

print("\n== Global Fishing Watch ==")
rows = [json.loads(l) for l in open(f"{W}/data/identity/gfw-identities.jsonl")]
seen = set(); pairs = []
per = z = bad = 0
for r in rows:
    for e in r["entries"]:
        ri = e.get("registryInfo") or []
        for x in e.get("selfReportedInfo") or []:
            per += 1
            im = (x.get("imo") or "").strip()
            if not im or im in ("0", "0000000"): z += 1
            elif imo_check(im) is False: bad += 1
            for y in ri:
                if x.get("ssvid") and x.get("ssvid") == y.get("ssvid") and x.get("shipname") and y.get("shipname"):
                    k = (r["imo"], x["ssvid"], norm(x["shipname"]), norm(y["shipname"]))
                    if k in seen: continue
                    seen.add(k); pairs.append((x["shipname"], y["shipname"]))
c = collections.Counter(classify(a, b) for a, b in pairs)
print(f"records {len(rows)} | self-reported periods {per} | IMO zero {z} | bad check {bad}")
print(f"deduped AIS-vs-registry pairs {len(pairs)}: " + ", ".join(f"{k} {v} ({100*v/len(pairs):.0f}%)" for k, v in c.most_common()))
ch = []
for r in rows:
    for e in r["entries"]:
        dd = {(x.get("ssvid"), x.get("shipname"), x.get("flag"), x.get("callsign")): x for x in e.get("selfReportedInfo") or []}
        srt = sorted(dd.values(), key=lambda x: x.get("transmissionDateFrom") or "")
        for a, b in zip(srt, srt[1:]):
            if a.get("ssvid") and a.get("ssvid") != b.get("ssvid"): ch.append((r["imo"], a, b))
mid_ch = sum(1 for _, a, b in ch if a["ssvid"][:3] != b["ssvid"][:3])
sf = sum(1 for _, a, b in ch if a.get("flag") and a.get("flag") == b.get("flag"))
sn = sum(1 for _, a, b in ch if a.get("shipname") and norm(a["shipname"]) == norm(b["shipname"]))
sb = sum(1 for _, a, b in ch if a.get("shipname") and a.get("flag") and norm(a["shipname"]) == norm(b["shipname"]) and a["flag"] == b.get("flag"))
ed = collections.Counter(lev(a["ssvid"], b["ssvid"]) for _, a, b in ch)
print(f"deduped consecutive MMSI changes {len(ch)} | MID changed {mid_ch} ({100*mid_ch/len(ch):.0f}%) | same flag {sf} | same name {sn} | same name+flag {sb}")
print("MMSI edit distance:", sorted(ed.items()), "| <=2:", sum(v for k, v in ed.items() if k <= 2))

print("\n== Danish day 2026-11-01 ==")
V = json.load(open(f"{W}/data/id-fuzzy/dk_variants.json"))["vessels"]
d = collections.Counter(); imovals = 0; vimo = 0
for m, r in V.items():
    if r["imos"]: vimo += 1
    for im, _ in r["imos"]:
        imovals += 1
        d["zero" if im in ("0", "0000000") else ("valid" if imo_check(im) is True else ("bad_check" if imo_check(im) is False else "not_7"))] += 1
best = {m: max(r["names"], key=lambda x: x[1])[0] for m, r in V.items() if r["names"]}
byname = collections.defaultdict(list)
for m, n in best.items(): byname[sq(n)].append((m, n))
dups = {k: v for k, v in byname.items() if len(v) > 1}
print(f"vessels with static fields {len(V)} | with IMO {vimo} | IMO values {imovals} {dict(d)}")
print(f"named {len(best)} | distinct squashed names {len(byname)} | names on >1 MMSI {len(dups)} covering {sum(len(v) for v in dups.values())} MMSIs")
print("multi name", sum(1 for r in V.values() if len(r["names"]) > 1), "| multi imo", sum(1 for r in V.values() if len(r["imos"]) > 1),
      "| multi callsign", sum(1 for r in V.values() if len(r["callsigns"]) > 1), "| multi dims", sum(1 for r in V.values() if len(r["dims"]) > 1))
idx = collections.defaultdict(list)
for m, n in best.items(): idx[sq(n)[:4]].append((m, n))
checked = 0; merge = collections.Counter()
for b, items in idx.items():
    for (m1, n1), (m2, n2) in itertools.combinations(items, 2):
        if m1 == m2: continue
        checked += 1; r = ratio(n1, n2)
        for t in (0.80, 0.85, 0.90, 0.95):
            if r >= t: merge[t] += 1
print(f"distinct-ship pairs sharing a 4-char name prefix {checked} | pairs above threshold: {dict(merge)}")
