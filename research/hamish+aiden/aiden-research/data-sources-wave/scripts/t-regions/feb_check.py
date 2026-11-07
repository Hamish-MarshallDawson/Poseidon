#!/usr/bin/env python3
"""Before/after test for Hormuz: same window, passes in Feb 2026 (PortWatch AIS
transits ~78/day) vs Oct-Nov 2026 (PortWatch ~3.8/day). If the radar target count
moved with the AIS count, the collapse is real; if radar targets stayed high, the
AIS series is the thing that broke."""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import detect

WAVE = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave"
BOX = {"hormuz": (56.30, 26.30, 56.70, 26.65), "malacca": (100.75, 2.80, 101.15, 3.10)}

if __name__ == "__main__":
    region = sys.argv[1]
    inv = json.load(open(WAVE + "/data/t-regions/inventory_feb.json"))
    W, S, E, N = BOX[region]
    res = []
    for it in inv[region]["items"]:
        b = it["bbox"]
        if not (b[1] <= S and b[3] >= N and b[0] <= W and b[2] >= E):
            continue
        try:
            rows, a, db, aff = detect.run(it, BOX[region])
        except Exception as e:
            print(it["id"], "ERR", str(e)[:100], flush=True); continue
        res.append({"id": it["id"], "dt": it["dt"], "orbit": it["orbit"],
                    "n_targets": len(rows),
                    "n_ge50m": sum(1 for r in rows if r["len_m"] >= 50)})
        print(f"{it['dt']} {it['orbit'][:4]} targets={len(rows):3d} "
              f">=50m={res[-1]['n_ge50m']:2d}", flush=True)
        json.dump(res, open(f"{WAVE}/data/t-regions/feb_{region}.json", "w"), indent=1)
    print("passes:", len(res))
