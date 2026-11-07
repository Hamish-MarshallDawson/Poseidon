"""id-fuzzy part 3: threshold sweep, false-merge measurement, stratified hand-check sample."""
import json, collections, itertools, random, re, sys
WAVE = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave"
random.seed(11)

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
        cur = [i]; best = i
        for j, cb in enumerate(b, 1):
            v = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            cur.append(v); best = min(best, v)
        if best > cap:
            return cap + 1
        prev = cur
    return prev[-1]

def ratio(a, b):
    sa, sb = squash(a), squash(b)
    return 1 - lev(sa, sb) / max(len(sa), len(sb), 1)

def token_jaccard(a, b):
    ta, tb = set(norm(a).split()), set(norm(b).split())
    return len(ta & tb) / len(ta | tb) if ta | tb else 0.0

R = json.load(open(f"{WAVE}/data/id-fuzzy/results.json"))
dk_pairs = R["dk_pairs"]; cap_pairs = R["cap_pairs"]; gfw_pairs = R["gfw_pairs"]
print("pair counts: dk", len(dk_pairs), "capture", len(cap_pairs), "gfw", len(gfw_pairs))

# ---- duplicate-name test on the Danish day: names are not unique ----
dk = json.load(open(f"{WAVE}/data/id-fuzzy/dk_variants.json"))["vessels"]
best_name = {m: max(r["names"], key=lambda x: x[1])[0] for m, r in dk.items() if r["names"]}
by_name = collections.defaultdict(list)
for m, n in best_name.items():
    by_name[squash(n)].append((m, n))
dups = {k: v for k, v in by_name.items() if len(v) > 1}
print("vessels with a name:", len(best_name), "| distinct names after squash:", len(by_name),
      "| names shared by >1 MMSI:", len(dups), "| MMSIs involved:", sum(len(v) for v in dups.values()))
for k, v in sorted(dups.items(), key=lambda x: -len(x[1]))[:12]:
    print("   ", len(v), "x", v[0][1], "->", [m for m, _ in v][:6])

# ---- false-merge rate: distinct MMSIs, name-only matching ----
names = list(best_name.values())
idx = collections.defaultdict(list)
for m, n in best_name.items():
    s = squash(n)
    idx[s[:4]].append((m, n))
pairs_checked = 0; merge = {0.80: 0, 0.85: 0, 0.90: 0, 0.95: 0}
worst = []
for bucket, items in idx.items():
    for (m1, n1), (m2, n2) in itertools.combinations(items, 2):
        if m1 == m2:
            continue
        pairs_checked += 1
        r = ratio(n1, n2)
        for t in merge:
            if r >= t:
                merge[t] += 1
        worst.append((round(r, 3), n1, n2))
worst.sort(reverse=True)
print("distinct-ship pairs with same 4-char name prefix:", pairs_checked)
print("pairs scoring above threshold:", merge)
print("top near-collisions (different MMSIs, same day):")
for r, a, b in worst[:10]:
    print("   ", r, repr(a), repr(b))

# ---- threshold sweep on same-MMSI pairs (cosmetic vs substantive) ----
COSMETIC = {"spacing_case", "punctuation", "truncation20", "prefix_token", "abbreviation", "typo"}
pool = dk_pairs + cap_pairs
sweep = {}
for t in (0.70, 0.75, 0.80, 0.85, 0.90, 0.95, 0.99):
    tp = sum(1 for p in pool if p["ratio"] >= t and p["cat"] in COSMETIC)
    fp = sum(1 for p in pool if p["ratio"] >= t and p["cat"] not in COSMETIC)
    fn = sum(1 for p in pool if p["ratio"] < t and p["cat"] in COSMETIC)
    sweep[t] = (tp, fp, fn)
print("same-MMSI pair threshold sweep (tp, fp, fn) on n=", len(pool), sweep)

# ---- stratified hand-check sample ----
by_cat = collections.defaultdict(list)
for p in dk_pairs + gfw_pairs:
    by_cat[p["cat"]].append(p)
sample = []
for cat in ("spacing_case", "punctuation", "truncation20", "prefix_token", "abbreviation", "typo", "real_difference"):
    lst = [p for p in by_cat.get(cat, []) if p.get("kind") != "ais_vs_registry"]
    random.shuffle(lst)
    sample.extend(lst[:8])
out = f"{WAVE}/data/id-fuzzy/handcheck.json"
json.dump(sample, open(out, "w"), indent=0)
print("\nHANDCHECK SAMPLE", len(sample), "pairs ->", out)
for i, p in enumerate(sample):
    print(f"{i:2d} {p['cat']:16s} r={p['ratio']:<5} kind={p.get('kind'):18s} {p['a']!r} | {p['b']!r}")
