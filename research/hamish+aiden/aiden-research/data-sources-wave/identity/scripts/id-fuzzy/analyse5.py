"""id-fuzzy part 5: fixed Danish IMO defects, split threshold sweeps, 60-pair hand-check sample."""
import json, collections, itertools, random, re
WAVE = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave"
random.seed(23)

def imo_check(imo):
    s = str(imo)
    if len(s) != 7 or not s.isdigit():
        return None
    return str(sum(int(c) * w for c, w in zip(s[:6], (7, 6, 5, 4, 3, 2))) % 10) == s[6]

def norm(s):
    return re.sub(r"\s+", " ", (s or "").upper()).strip()

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
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        prev = cur
    return prev[-1]

def ratio(a, b):
    sa, sb = squash(a), squash(b)
    return 1 - lev(sa, sb) / max(len(sa), len(sb), 1)

du = json.load(open(f"{WAVE}/data/id-fuzzy/dk_variants.json"))
V = du["vessels"]
# --- Danish IMO defects (imos stored as [value, count] pairs) ---
defect = collections.Counter()
vals = 0
for m, r in V.items():
    for im, c in r["imos"]:
        vals += 1
        if im in ("0", "0000000"):
            defect["zero"] += 1
        elif imo_check(im) is True:
            defect["valid_check_digit"] += 1
        elif imo_check(im) is False:
            defect["bad_check_digit"] += 1
        else:
            defect["not_7_digits"] += 1
print("Danish day: vessels with IMO", sum(1 for r in V.values() if r["imos"]),
      "| distinct IMO values", vals, "|", dict(defect))
bad = [(m, im) for m, r in V.items() for im, _ in r["imos"] if imo_check(im) is False]
print("bad-check IMO values (vessel, imo):", bad)
# IMO typo test: a bad-check IMO within 1 digit of a valid IMO in the *same day's* fleet
valid_imos = {im for r in V.values() for im, _ in r["imos"] if imo_check(im) is True}
for m, im in bad:
    near = [v for v in valid_imos if lev(im, v, cap=1) <= 1]
    print("   ", m, im, "-> 1-digit valid IMO in the fleet:", near[:3])
# length distribution of names
lens = collections.Counter()
for m, r in V.items():
    for nm, c in r["names"]:
        lens[len(nm)] += 1
print("name length distribution (Danish day), top:", lens.most_common(6), "| exactly 20 chars:", lens[20], "of", sum(lens.values()))

# --- threshold sweeps, split ---
R = json.load(open(f"{WAVE}/data/id-fuzzy/results.json"))
COSMETIC = {"spacing_case", "punctuation", "truncation20", "prefix_token", "abbreviation"}
TYPO = {"typo"}
def sweep(pairs, label):
    out = {}
    for t in (0.80, 0.85, 0.90, 0.95):
        tp = sum(1 for p in pairs if p["ratio"] >= t and p["cat"] in COSMETIC | TYPO)
        fp = sum(1 for p in pairs if p["ratio"] >= t and p["cat"] not in COSMETIC | TYPO)
        out[t] = (tp, fp)
    print(f"{label}: n={len(pairs)} (tp,fp) by threshold {out}")
sweep(R["gfw_pairs"], "GFW pairs (rename/registry)")
sweep(R["dk_pairs"], "Danish-day same-MMSI pairs")

# --- 60-pair hand-check sample ---
pool = [p for p in R["gfw_pairs"] + R["dk_pairs"]]
by_cat = collections.defaultdict(list)
for p in pool:
    by_cat[p["cat"]].append(p)
want = {"punctuation": 16, "real_difference": 16, "typo": 16, "prefix_token": 4, "spacing_case": 4, "truncation20": 0, "abbreviation": 0}
sample = []
for cat, k in want.items():
    lst = by_cat.get(cat, [])[:]
    random.shuffle(lst)
    sample.extend(lst[:k])
random.shuffle(sample)
out = []
for i, p in enumerate(sample):
    out.append(dict(i=i, cat=p["cat"], kind=p.get("kind"), ratio=p["ratio"], a=p["a"], b=p["b"],
                    squash_equal=squash(p["a"]) == squash(p["b"]),
                    r85=p["ratio"] >= 0.85, r90=p["ratio"] >= 0.90))
json.dump(out, open(f"{WAVE}/data/id-fuzzy/handcheck60.json", "w"), indent=0)
for o in out:
    print(f"{o['i']:2d} {o['cat']:15s} r={o['ratio']:<5} {o['a']!r} | {o['b']!r}")
