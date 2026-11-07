#!/usr/bin/env python3
"""Longitudinal test: bright-target count in ONE fixed window per region, one value
per Sentinel-1 pass over 30 days. Compare with PortWatch daily transits (AIS-derived)
for the same dates. This is the "no live AIS" substitute the brief asks about."""
import json, sys, os, datetime as dt
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import detect

WAVE = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave"
INV = json.load(open(WAVE + "/data/t-regions/inventory.json"))
OUT = WAVE + "/data/t-regions"

WINDOWS = [  # region, box, label
    ("hormuz",  (56.30, 26.30, 56.70, 26.65), "Hormuz strait 56.30-56.70E 26.30-26.65N"),
    ("malacca", (100.75, 2.80, 101.15, 3.10), "Malacca, Port Klang approaches"),
    ("natuna",  (105.45, 3.10, 105.85, 3.50), "North Natuna Sea open water"),
]

if __name__ == "__main__":
    region = sys.argv[1]
    box = (56.30, 26.30, 56.70, 26.65) if region == "hormuz" else \
          (100.75, 2.80, 101.15, 3.10) if region == "malacca" else \
          (105.45, 3.10, 105.85, 3.50)
    W, S, E, N = box
    res = []
    for it in INV[region]["items"]:
        b = it["bbox"]
        if not (b[1] <= S and b[3] >= N and b[0] <= W and b[2] >= E):
            continue
        try:
            rows, a, db, aff = detect.run(it, box)
        except Exception as e:
            print(it["id"], "ERR", str(e)[:120], flush=True)
            continue
        rec = {"id": it["id"], "dt": it["dt"], "orbit": it["orbit"],
               "delay_h": it.get("delay_h"), "n_targets": len(rows),
               "n_ge50m": sum(1 for r in rows if r["len_m"] >= 50)}
        res.append(rec)
        print(f"{it['dt']} {it['orbit'][:4]} targets={len(rows):3d} >=50m={rec['n_ge50m']:2d} "
              f"publish_delay={it.get('delay_h')}h", flush=True)
        json.dump(res, open(f"{OUT}/longitudinal_{region}.json", "w"), indent=1)
    print("passes:", len(res), "-> ", f"{OUT}/longitudinal_{region}.json")
