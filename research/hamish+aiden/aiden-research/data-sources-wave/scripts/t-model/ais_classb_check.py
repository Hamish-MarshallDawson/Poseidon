"""Check whether the radar-only target had any AIS (any class) nearby, from the raw DMA day."""
import csv, io, math, zipfile

ZIP = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave/data/t-match/aisdk-2026-11-01.zip"
TX, TY = 12.6444, 56.4543
rows = 0
near = {}
types = {}
with zipfile.ZipFile(ZIP) as z:
    with z.open("aisdk-2026-11-01.csv") as f:
        for line in io.TextIOWrapper(f, encoding="utf-8", errors="replace"):
            if "16:4" not in line[11:14] and not line.startswith("01/11/2026 16:"):
                continue
            if not line.startswith("01/11/2026 16:4"):
                continue
            p = line.rstrip("\r\n").split(",")
            ts = p[0][11:]
            if not ("16:40:00" <= ts <= "16:50:00"):
                continue
            try:
                lat, lon = float(p[3]), float(p[4])
            except ValueError:
                continue
            rows += 1
            d = math.hypot((lon - TX) * 111320 * math.cos(math.radians(TY)),
                           (lat - TY) * 110540)
            types[p[1]] = types.get(p[1], 0) + 1
            if d < 3000:
                key = p[2]
                if key not in near or d < near[key][0]:
                    near[key] = (d, p[1], p[2], p[12], p[13], p[7], p[17], lon, lat)
print("rows 16:40-16:50", rows, "by type", types)
for v in sorted(near.values()):
    print(f"{v[0]:6.0f} m {v[1]:12s} mmsi {v[2]} {v[3]!r} type {v[4]!r} sog {v[5]} len {v[6]} at {v[7]:.4f},{v[8]:.4f}")
if not near:
    print("no AIS of any class within 3 km of the radar-only target in that 10-minute window")
