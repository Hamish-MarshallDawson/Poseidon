"""Zombie-style identity-chain statistics across ALL identity groups per IMO.

GFW returns one record per IMO with several entry groups; each group holds the
self-reported identity periods of one matched identity. A scrapped-IMO reuse
appears as a later group with a new name/flag/MMSI after the first group's last
transmission.

python3 -I gfw_chains.py <gfw.jsonl> <out.json>
"""
import json, sys, collections, datetime as dt

src, out = sys.argv[1], sys.argv[2]

def tp(s):
    return dt.datetime.fromisoformat(s.replace("Z", "+00:00")) if s else None

rows = [json.loads(l) for l in open(src)]
res = []
stats = collections.Counter()
for r in rows:
    ids = {}
    for g in r["entries"]:
        for s in g.get("selfReportedInfo") or []:
            ssvid = s.get("ssvid")
            if not ssvid:
                continue
            a, b = tp(s.get("transmissionDateFrom")), tp(s.get("transmissionDateTo"))
            if not a or not b:
                continue
            d = ids.setdefault((ssvid, (s.get("shipname") or "").strip(),
                                s.get("flag")), {"a": a, "b": b})
            d["a"] = min(d["a"], a); d["b"] = max(d["b"], b)
    if not ids:
        continue
    stats["ships"] += 1
    span = sorted(((v["a"], v["b"], k) for k, v in ids.items()))
    first, last = span[0], span[-1]
    names = {k[1] for k in ids}
    flags = {k[2] for k in ids}
    mmsis = {k[0] for k in ids}
    # later identities that start after the first identity's last transmission
    after = [x for x in span if x[0] > first[1]]
    if len(after) and len(after[-1][2][1]) and names:
        stats["identity_continued_after_first_end"] += 1
    # chain of non-overlapping identities with different name: zombie candidate
    chain = [span[0]]
    for x in span[1:]:
        if x[0] >= chain[-1][1]:
            chain.append(x)
    if len(chain) >= 3:
        stats["chain3"] += 1
    if len(chain) >= 4:
        stats["chain4"] += 1
    if len(chain) >= 3 and len({c[2][1] for c in chain}) >= 3:
        stats["chain3_distinct_names"] += 1
    res.append({"imo": r["imo"], "n_ids": len(ids), "n_chain": len(chain),
                "names": sorted(n for n in names if n), "flags": sorted(f for f in flags if f),
                "n_mmsi": len(mmsis),
                "span": [str(first[0])[:10], str(last[1])[:10]],
                "chain": [[c[2][0], c[2][1], c[2][2], str(c[0])[:10], str(c[1])[:10]] for c in chain]})

chains = [x for x in res if x["n_chain"] >= 3]
json.dump({"stats": dict(stats),
           "n_records": len(rows),
           "chains": sorted(chains, key=lambda x: -x["n_chain"])[:40],
           "examples": sorted(res, key=lambda x: -x["n_ids"])[:20]}, open(out, "w"), indent=1)
print("ok", dict(stats))
