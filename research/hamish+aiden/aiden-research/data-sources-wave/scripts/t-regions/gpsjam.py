#!/usr/bin/env python3
"""GPSJam daily H3 files (no account, no key) as free GPS-interference evidence.

Endpoints measured working: https://gpsjam.org/data/manifest.csv (latest date per day)
and https://gpsjam.org/data/<date>-h3_4.csv . Both arrive as gzip bytes WITHOUT a
Content-Encoding header, so they must be gunzipped by hand.
Columns: hex (H3 res 4), count_good_aircraft, count_bad_aircraft.
Percent bad = bad / (bad + good) among aircraft passing through the hex that day.
"""
import gzip, io, csv, sys, urllib.request, collections
import h3

BASE = "https://gpsjam.org/data/"
REGIONS = {
    "Hormuz+approach (55.5-58E, 24-27.5N)": (24.0, 55.5, 27.5, 58.0),
    "Malacca (98.5-101E, 2.5-5N)": (2.5, 98.5, 5.0, 101.0),
    "Natuna/South China Sea (104-107E, 2-5N)": (2.0, 104.0, 5.0, 107.0),
    "Denmark straits (9-14E, 54-58N)": (54.0, 9.0, 58.0, 14.0),
    "English Channel (0-3E, 49-51.5N)": (49.0, 0.0, 51.5, 3.0),
}

def get(url):
    raw = urllib.request.urlopen(url, timeout=120).read()
    try:
        txt = gzip.decompress(raw).decode("utf-8", "ignore")
    except OSError:
        txt = raw.decode("utf-8", "ignore")
    return txt

if __name__ == "__main__":
    man = list(csv.reader(io.StringIO(get(BASE + "manifest.csv"))))
    dates = [r[0] for r in man[1:] if r and r[0].startswith("20")][-int(sys.argv[1] if len(sys.argv) > 1 else 14):]
    print("dates:", dates[0], "..", dates[-1], f"({len(dates)} days)")
    agg = collections.defaultdict(lambda: [0, 0])
    per_day = collections.defaultdict(dict)
    for d in dates:
        try:
            rows = list(csv.DictReader(io.StringIO(get(f"{BASE}{d}-h3_4.csv"))))
        except Exception as e:
            print(d, "ERR", str(e)[:80]); continue
        for r in rows:
            try:
                la, lo = h3.cell_to_latlng(r["hex"])
            except Exception:
                continue
            try:
                g = int(r["count_good_aircraft"] or 0); b = int(r["count_bad_aircraft"] or 0)
            except ValueError:
                continue
            for k, (s, w, n, e) in REGIONS.items():
                if s <= la <= n and w <= lo <= e:
                    agg[k][0] += g; agg[k][1] += b
                    pd = per_day[d]
                    pd.setdefault(k, {"g": 0, "b": 0})
                    pd[k]["g"] += g; pd[k]["b"] += b
    print(f"\n{len(dates)}-day totals, GPSJam bad-aircraft share by region:")
    for k, (g, b) in agg.items():
        print(f"  {k:42s} good={g:8d} bad={b:6d} bad%={100*b/max(g+b,1):5.2f}")
    for k in REGIONS:
        line = []
        for d in dates:
            pd = per_day.get(d, {}).get(k, {})
            g, b = pd.get("g", 0), pd.get("b", 0)
            line.append(f"{d[5:]}:{100*b/max(g+b,1):.1f}%({g+b})")
        print(f"{k}\n   " + "  ".join(line))
