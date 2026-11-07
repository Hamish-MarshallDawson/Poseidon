#!/usr/bin/env python3
"""Run the simple bright-target detector on real Sentinel-1 windows in each region."""
import json, sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import detect

WAVE = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave"
INV = json.load(open(WAVE + "/data/t-regions/inventory.json"))
OUT = WAVE + "/data/t-regions"

JOBS = [
    ("hormuz_strait",   "hormuz",     (56.30, 26.30, 56.70, 26.65), "Strait of Hormuz, both lanes"),
    ("gulf_oman_lane",  "gulf_oman",  (57.55, 24.55, 57.95, 24.95), "Gulf of Oman, inbound lane"),
    ("natuna_open",     "natuna",     (105.45, 3.10, 105.85, 3.50), "North Natuna Sea open water"),
    ("malacca_klang",   "malacca",    (100.75, 2.80, 101.15, 3.10), "Malacca, Port Klang approaches"),
    ("malacca_north",   "malacca",    (99.95, 4.05, 100.35, 4.35), "Malacca, off One Fathom Bank"),
]

def pick(region, box):
    W, S, E, N = box
    c = [it for it in INV[region]["items"]
         if it["bbox"][1] <= S and it["bbox"][3] >= N and it["bbox"][0] <= W and it["bbox"][2] >= E]
    return c[-1] if c else None

if __name__ == "__main__":
    only = sys.argv[1] if len(sys.argv) > 1 else None
    try:
        summary = json.load(open(OUT + "/detections.json"))
    except Exception:
        summary = {}
    for name, region, box, label in JOBS:
        if only and only not in name:
            continue
        it = pick(region, box)
        if it is None:
            print(f"{name}: NO ITEM covers the window")
            continue
        print(f"\n## {name} ({label})\n   item={it['id']} sensed={it['dt']} "
              f"orbit={it['orbit']} publish_delay={it.get('delay_h')}h", flush=True)
        rows, a, db, aff = detect.run(it, box)
        rows.sort(key=lambda r: -r["area_px"])
        print(f"   window {a.shape[0]}x{a.shape[1]} px at {abs(aff['cx'][0]):.1f} m; "
              f"targets (land removed) = {len(rows)}", flush=True)
        for lo, hi in [(0, 25), (25, 50), (50, 100), (100, 200), (200, 10**6)]:
            n = sum(1 for r in rows if lo <= r["len_m"] < hi)
            print(f"     est length {lo:>4}-{hi if hi < 1000 else '+':>4} m: {n}", flush=True)
        for i, r in enumerate(rows[:6]):
            detect.save_crop(db, r, f"{OUT}/crop_{name}_{i:02d}.png")
        summary[name] = {"item": it["id"], "dt": it["dt"], "box": box, "label": label,
                         "region": region, "n_targets": len(rows),
                         "n_ge25m": sum(1 for r in rows if r["len_m"] >= 25),
                         "n_ge50m": sum(1 for r in rows if r["len_m"] >= 50),
                         "pixels": list(a.shape),
                         "targets": [{k: round(r[k], 5) for k in ("lon", "lat", "area_px", "len_m", "peak_db")} for r in rows]}
        json.dump(summary, open(OUT + "/detections.json", "w"), indent=1)
    print("\nwrote", OUT + "/detections.json")
