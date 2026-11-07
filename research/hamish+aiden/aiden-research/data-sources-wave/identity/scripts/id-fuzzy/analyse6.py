"""id-fuzzy part 6: precision/recall of candidate matching rules on 52 hand-labelled pairs."""
import json, re, collections
WAVE = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave"

# Hand labels by id-fuzzy, read off the pair list (52 pairs). C = cosmetic (same name written
# differently, should match), S = substantive (name content changed, must not match), A = ambiguous.
LABELS = {
    0: "C", 1: "C", 2: "S", 3: "S", 4: "S", 5: "C", 6: "C", 7: "S", 8: "S", 9: "C",
    10: "A", 11: "C", 12: "C", 13: "C", 14: "C", 15: "C", 16: "S", 17: "C", 18: "S",
    19: "C", 20: "S", 21: "C", 22: "C", 23: "C", 24: "C", 25: "C", 26: "C", 27: "S",
    28: "S", 29: "S", 30: "C", 31: "C", 32: "S", 33: "C", 34: "S", 35: "C", 36: "C",
    37: "C", 38: "S", 39: "S", 40: "S", 41: "C", 42: "C", 43: "S", 44: "S", 45: "C",
    46: "S", 47: "S", 48: "S", 49: "C", 50: "C", 51: "S",
}
ROMAN = {"I": "1", "II": "2", "III": "3", "IV": "4", "V": "5", "VI": "6"}

def norm(s):
    return re.sub(r"\s+", " ", (s or "").upper()).strip()

def squash(s):
    return re.sub(r"[^A-Z0-9]", "", norm(s))

def smart(s):
    t = norm(s)
    t = re.sub(r"\bNO[\.\s]*(\d)", r"\1", t)
    t = re.sub(r"\bNO\.?\b", "", t)
    t = re.sub(r"\b(III|II|IV|VI|V|I)\b", lambda m: ROMAN[m.group(1)], t)
    t = re.sub(r"(?<=[A-Z])(\d)\b", lambda m: "0" + m.group(1), t) if False else t
    return re.sub(r"[^A-Z0-9]", "", t)

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

H = json.load(open(f"{WAVE}/data/id-fuzzy/handcheck60.json"))
rules = {
    "squash equality": lambda a, b: squash(a) == squash(b),
    "squash+roman/NO equality": lambda a, b: smart(a) == smart(b),
    "ratio >= 0.85": lambda a, b: ratio(a, b) >= 0.85,
    "ratio >= 0.90": lambda a, b: ratio(a, b) >= 0.90,
    "ratio >= 0.85 or squash eq": lambda a, b: ratio(a, b) >= 0.85 or squash(a) == squash(b),
}
N = len(LABELS)
cos = [k for k, v in LABELS.items() if v == "C"]
sub = [k for k, v in LABELS.items() if v == "S"]
amb = [k for k, v in LABELS.items() if v == "A"]
print(f"hand-labelled pairs: {N} (cosmetic {len(cos)}, substantive {len(sub)}, ambiguous {len(amb)})")
print(f"\n{'rule':30s} {'predict':>7s} {'TP':>3s} {'FP':>3s} {'FN':>3s} {'precision':>9s} {'recall':>7s}")
for name, fn in rules.items():
    pred = [o["i"] for o in H if fn(o["a"], o["b"])]
    tp = sum(1 for i in pred if LABELS[i] == "C")
    fp = sum(1 for i in pred if LABELS[i] == "S")
    fpn = sum(1 for i in pred if LABELS[i] == "A")
    fn_ = sum(1 for i in cos if i not in pred)
    print(f"{name:30s} {len(pred):7d} {tp:3d} {fp:3d} {fn_:3d} {tp/(tp+fp) if tp+fp else 0:9.2f} {tp/len(cos):7.2f}   amb-merged={fpn}")
print("\nclassifier category vs hand label:")
ct = collections.Counter((o["cat"], LABELS[o["i"]]) for o in H)
for k, v in sorted(ct.items()):
    print("  ", k, v)
print("\nmismatches (classifier says typo/real but hand says otherwise):")
for o in H:
    lab = LABELS[o["i"]]
    bad = (o["cat"] == "typo" and lab == "S") or (o["cat"] == "real_difference" and lab == "C") or (o["cat"] in ("punctuation", "prefix_token") and lab != "C")
    if bad:
        print(f"  {o['i']:2d} classifier={o['cat']:15s} hand={lab} r={o['ratio']:<5} {o['a']!r} | {o['b']!r}")
