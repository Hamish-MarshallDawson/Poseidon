#!/usr/bin/env python3
"""Raw relationship between PortWatch Hormuz daily transits and free Brent (FRED).

No account: FRED graph CSV endpoint (fredgraph.csv?id=DCOILBRENTEU).
Reports only the co-movement (correlations, lag profile, event windows).
No trading claim.
"""
import csv
import os
import statistics as st

HERE = os.path.dirname(os.path.abspath(__file__))
D = os.path.join(HERE, "..", "..", "data", "t-ais-history")


def load_series(fn):
    with open(os.path.join(D, fn)) as f:
        r = csv.DictReader(f)
        out = {}
        for row in r:
            k = row["observation_date"]
            v = row[list(row)[1]]
            try:
                out[k] = float(v)
            except ValueError:
                pass
        return out


def load_pw(fn, col="n_total"):
    with open(os.path.join(D, "portwatch", fn)) as f:
        return {row["date"]: float(row[col]) for row in csv.DictReader(f)
                if row[col] not in ("", None)}


def corr(a, b):
    n = len(a)
    ma, mb = st.mean(a), st.mean(b)
    sa = (sum((x - ma) ** 2 for x in a) / n) ** 0.5
    sb = (sum((x - mb) ** 2 for x in b) / n) ** 0.5
    if sa == 0 or sb == 0:
        return float("nan")
    return sum((x - ma) * (y - mb) for x, y in zip(a, b)) / (n * sa * sb)


def join(pw, oil, start=None, end=None):
    keys = sorted(set(pw) & set(oil))
    if start:
        keys = [k for k in keys if k >= start]
    if end:
        keys = [k for k in keys if k <= end]
    return keys


def report(name, pw, oil, start=None, end=None):
    keys = join(pw, oil, start, end)
    a = [pw[k] for k in keys]
    b = [oil[k] for k in keys]
    print(f"\n--- {name} n={len(keys)} {keys[0]}..{keys[-1]} ---")
    print(f"transits mean {st.mean(a):.1f}  oil mean ${st.mean(b):.1f}")
    print(f"same-day Pearson r = {corr(a, b):+.3f}")
    for lag in (-20, -10, -5, -2, -1, 0, 1, 2, 5, 10, 20, 40):
        # correlation of transits(t) with oil(t+lag)
        xs, ys = [], []
        for i, k in enumerate(keys):
            j = i + lag
            if 0 <= j < len(keys):
                xs.append(a[i])
                ys.append(b[j])
        print(f"  r(transits, oil+{lag:>3d}d) = {corr(xs, ys):+.3f}  n={len(xs)}")


if __name__ == "__main__":
    oil = load_series("fred_DCOILBRENTEU.csv")
    print("Brent observations:", len(oil), min(oil), max(oil))
    pw = load_pw("Strait_of_Hormuz.csv")
    mal = load_pw("Malacca_Strait.csv")
    report("Hormuz transits vs Brent, all overlap", pw, oil)
    report("Hormuz transits vs Brent, 2026 only", pw, oil, "2026-01-01")
    report("Hormuz transits vs Brent, Feb 2026 onward",
           pw, oil, "2026-02-01")
    report("Hormuz transits vs Brent, 2024-2025", pw, oil, "2024-01-01", "2025-12-31")
    report("Malacca transits vs Brent, 2026", mal, oil, "2026-01-01")

    # event window table around the 28 Feb 2026 war start
    print("\n=== daily table around the war start (28 Feb 2026) ===")
    keys = sorted(set(pw) & set(oil))
    sel = [k for k in keys if "2026-02-10" <= k <= "2026-03-25"]
    print(f"{'date':12s} {'transits':>8s} {'tankers':>7s} {'brent':>7s}")
    tk = load_pw("Strait_of_Hormuz.csv", "n_tanker")
    for k in sel:
        print(f"{k:12s} {pw[k]:8.0f} {tk.get(k, float('nan')):7.0f} {oil[k]:7.2f}")
