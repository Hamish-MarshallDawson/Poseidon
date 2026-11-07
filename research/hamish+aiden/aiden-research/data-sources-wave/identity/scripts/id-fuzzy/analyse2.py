"""id-fuzzy part 2: anomaly examples, metadata-vs-static name agreement, GFW MMSI-change structure."""
import json, collections, itertools, re
WAVE = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave"
MID = json.load(open(f"{WAVE}/data/id-fuzzy/mid_wikipedia.json"))
import importlib.util
spec = importlib.util.spec_from_file_location("a1", f"{WAVE}/scripts/id-fuzzy/analyse.py")

def imo_check(imo):
    s = str(imo)
    if len(s) != 7 or not s.isdigit():
        return None
    total = sum(int(c) * w for c, w in zip(s[:6], (7, 6, 5, 4, 3, 2)))
    return str(total % 10) == s[6]

def norm(s):
    return re.sub(r"\s+", " ", (s or "").upper()).strip()

def lev(a, b):
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]

path = f"{WAVE}/data/identity/aisstream-capture.jsonl"
static_name = collections.defaultdict(collections.Counter)
meta_name = collections.defaultdict(collections.Counter)
imos = collections.defaultdict(collections.Counter)
bad_mid = []
nondigit = []
for line in open(path):
    d = json.loads(line)
    m = d["msg"]; t = m.get("MessageType"); md = m.get("MetaData") or {}
    mmsi = md.get("MMSI")
    if mmsi is None:
        continue
    b = (m.get("Message") or {})
    nm = None
    if t == "ShipStaticData":
        nm = (b.get("ShipStaticData") or {}).get("Name")
        im = (b.get("ShipStaticData") or {}).get("ImoNumber")
        if im:
            imos[mmsi][str(im)] += 1
    elif t == "StaticDataReport":
        nm = ((b.get("StaticDataReport") or {}).get("ReportA") or {}).get("Name")
    if nm and nm.strip():
        static_name[mmsi][nm.strip()] += 1
    if (md.get("ShipName") or "").strip():
        meta_name[mmsi][md["ShipName"].strip()] += 1
    if mmsi:
        s = str(mmsi)
        if len(s) != 9:
            nondigit.append((mmsi, t))
        elif s[0] in "2345678" and s[:3] not in MID:
            bad_mid.append((mmsi, t, sorted(static_name[mmsi].elements()) if static_name[mmsi] else None))

print("== non 9-digit MMSI ==", len(nondigit), collections.Counter(x[1] for x in nondigit))
print(sorted(nondigit)[:15])
print("== ship-range MMSI with MID not in list ==", len(bad_mid))
print(collections.Counter(str(x[0])[:3] for x in bad_mid).most_common(20))

both = [m for m in static_name if meta_name.get(m)]
dis = [m for m in both if norm(next(iter(static_name[m]))) != norm(next(iter(meta_name[m])))] if all(static_name[m] for m in both) else [m for m in both if static_name[m] and norm(next(iter(static_name[m]))) != norm(next(iter(meta_name[m])))]
print("== metadata vs static name: mmsi with both:", len(both), "disagree:", len(dis))
for m in dis[:15]:
    print("  ", m, "static=", list(static_name[m]), "meta=", list(meta_name[m]))

print("== IMO values in capture ==")
tot = sum(sum(c.values()) for c in imos.values())
vals = [(im, c) for m in imos for im, c in imos[m].items()]
z = sum(v for im, v in vals if im in ("0", "0000000"))
badc = [(im, v) for im, v in vals if imo_check(im) is False]
mal = [(im, v) for im, v in vals if imo_check(im) is None and im not in ("0", "0000000")]
print("imo values", len(vals), "messages with imo", tot, "zero", z, "bad check", len(badc), "malformed", len(mal))
print("bad check sample:", sorted(badc, key=lambda x: -x[1])[:12])
print("malformed sample:", sorted(mal, key=lambda x: -x[1])[:12])

# ---------- GFW MMSI change structure ----------
gfw = [json.loads(l) for l in open(f"{WAVE}/data/identity/gfw-identities.jsonl")]
rows = []
import datetime as dt
for r in gfw:
    for e in r["entries"]:
        raw = e.get("selfReportedInfo") or []
        seen = set()
        sr = []
        for x in raw:
            k = (x.get("ssvid"), x.get("shipname"), x.get("flag"), x.get("callsign"))
            if k in seen:
                continue
            seen.add(k); sr.append(x)
        sr.sort(key=lambda x: x.get("transmissionDateFrom") or "")
        for a, b in zip(sr, sr[1:]):
            if not a.get("ssvid") or a.get("ssvid") == b.get("ssvid"):
                continue
            rows.append(dict(imo=r["imo"], group=r["group"], region=r["region"],
                             mmsi_a=a["ssvid"], mmsi_b=b["ssvid"],
                             mid_a=a["ssvid"][:3], mid_b=b["ssvid"][:3],
                             flag_a=a.get("flag"), flag_b=b.get("flag"),
                             name_a=a.get("shipname"), name_b=b.get("shipname"),
                             t_a=a.get("transmissionDateTo"), t_b=b.get("transmissionDateFrom")))
print("== GFW consecutive self-reported periods with MMSI change ==", len(rows))
same_mid = [x for x in rows if x["mid_a"] == x["mid_b"]]
print("same MID:", len(same_mid), "different MID:", len(rows) - len(same_mid))
print("flag unchanged overall:", sum(1 for x in rows if x["flag_a"] == x["flag_b"]))
print("flag unchanged & MID changed:", sum(1 for x in rows if x["flag_a"] == x["flag_b"] and x["mid_a"] != x["mid_b"]))
print("flag changed & MID same:", sum(1 for x in rows if x["flag_a"] != x["flag_b"] and x["mid_a"] == x["mid_b"]))
ed = collections.Counter(lev(x["mmsi_a"], x["mmsi_b"]) for x in rows)
print("MMSI edit distance histogram:", sorted(ed.items()))
small = [x for x in rows if lev(x["mmsi_a"], x["mmsi_b"]) <= 2]
print("== near-identical MMSI pairs (edit<=2) ==", len(small))
for x in small:
    print("  ", x["imo"], x["mmsi_a"], "->", x["mmsi_b"], "| flags", x["flag_a"], x["flag_b"],
          "| names", x["name_a"], "->", x["name_b"], "|", x["t_a"], "->", x["t_b"])
# gaps
def gap(a, b):
    try:
        ta = dt.datetime.fromisoformat(a.replace("Z", "+00:00"))
        tb = dt.datetime.fromisoformat(b.replace("Z", "+00:00"))
    except Exception:
        return None
    return (tb - ta).total_seconds()
gs = [g for g in (gap(x["t_a"], x["t_b"]) for x in rows) if g is not None]
gs.sort()
print("gap seconds: min", gs[0], "p10", gs[len(gs)//10], "median", gs[len(gs)//2], "p90", gs[9*len(gs)//10], "max", gs[-1])
print("negative (overlapping) gaps:", sum(1 for g in gs if g < 0), "of", len(gs))
print("under 1 hour:", sum(1 for g in gs if 0 <= g < 3600), "under 1 day:", sum(1 for g in gs if 0 <= g < 86400))
json.dump(rows, open(f"{WAVE}/data/id-fuzzy/gfw_mmsi_change_rows.json", "w"), indent=0)
