"""id-fuzzy part 4: truncation at 20 chars, typo cases, name behaviour across MMSI changes."""
import json, collections, re
WAVE = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave"

def norm(s):
    return re.sub(r"\s+", " ", (s or "").upper()).strip()

gfw = [json.loads(l) for l in open(f"{WAVE}/data/identity/gfw-identities.jsonl")]
print("gfw records", len(gfw))

# registry names longer than 20 chars: how often does the AIS name equal the 20-char prefix?
reg_names = {}
self_names = collections.defaultdict(set)
for r in gfw:
    for e in r["entries"]:
        for y in e.get("registryInfo") or []:
            if y.get("shipname"):
                reg_names.setdefault(r["imo"], set()).add(y["shipname"])
        for x in e.get("selfReportedInfo") or []:
            if x.get("shipname") and x.get("ssvid"):
                self_names[x["ssvid"]].add(x["shipname"])
long_reg = [(imo, n) for imo, ns in reg_names.items() for n in ns if len(norm(n)) > 20]
trunc_hits = 0; examples = []
for imo, n in long_reg:
    pre = norm(n)[:20]
    hit = any(norm(s) == pre or norm(s) == pre.strip() for ss, names in self_names.items() for s in names)
    trunc_hits += hit
    if hit and len(examples) < 5:
        examples.append((imo, n, pre))
print(f"registry names longer than 20 chars: {len(long_reg)}; an AIS name equal to the 20-char cut exists: {trunc_hits}")
print("truncation examples:", examples)

# typo-classified GFW pairs
R = json.load(open(f"{WAVE}/data/id-fuzzy/results.json"))
print("\n== GFW pairs classified as typo/abbreviation ==")
for p in R["gfw_pairs"]:
    if p["cat"] in ("typo", "abbreviation", "truncation20", "prefix_token"):
        print(f"  {p['cat']:14s} r={p['ratio']:<5} {p['kind']:18s} imo={p['imo']} {p['a']!r} -> {p['b']!r}")

# name behaviour across MMSI changes (deduped)
seen = set(); rows = []
for r in gfw:
    for e in r["entries"]:
        raw = e.get("selfReportedInfo") or []
        dedup = {}
        for x in raw:
            dedup[(x.get("ssvid"), x.get("shipname"), x.get("flag"), x.get("callsign"))] = x
        sr = sorted(dedup.values(), key=lambda x: x.get("transmissionDateFrom") or "")
        for a, b in zip(sr, sr[1:]):
            if not a.get("ssvid") or a.get("ssvid") == b.get("ssvid"):
                continue
            rows.append((r["imo"], a, b))
print("\nMMSI-change pairs:", len(rows))
same_name = sum(1 for _, a, b in rows if norm(a.get("shipname")) == norm(b.get("shipname")) and a.get("shipname"))
same_flag = sum(1 for _, a, b in rows if a.get("flag") and a.get("flag") == b.get("flag"))
same_cs = sum(1 for _, a, b in rows if a.get("callsign") and a.get("callsign") == b.get("callsign"))
same_name_flag = sum(1 for _, a, b in rows if a.get("shipname") and norm(a["shipname"]) == norm(b.get("shipname")) and a.get("flag") and a["flag"] == b.get("flag"))
print(f"same name across the MMSI change: {same_name}/{len(rows)}; same flag: {same_flag}; same callsign: {same_cs}; same name AND flag: {same_name_flag}")
print("\nexamples where name+flag identical but MMSI changed:")
for imo, a, b in rows:
    if a.get("shipname") and norm(a["shipname"]) == norm(b.get("shipname")) and a.get("flag") and a["flag"] == b.get("flag"):
        print(f"  imo={imo} {a['ssvid']}->{b['ssvid']} {a['shipname']!r} flag={a['flag']} "
              f"{a.get('transmissionDateTo')} -> {b.get('transmissionDateFrom')}")
