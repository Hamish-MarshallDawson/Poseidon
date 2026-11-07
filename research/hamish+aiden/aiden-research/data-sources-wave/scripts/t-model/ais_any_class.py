"""Extract ALL AIS classes (A, B, AtoN, SAR) for 16:40-16:50Z in the target slice bbox."""
import csv, io, zipfile
ZIP = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave/data/t-match/aisdk-2026-11-01.zip"
OUT = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave/data/t-model/ais_1640_1650_allclasses.csv"
n = 0
with zipfile.ZipFile(ZIP) as z, z.open("aisdk-2026-11-01.csv") as f, open(OUT, "w") as out:
    w = csv.writer(out)
    w.writerow(["ts", "mobile", "mmsi", "lat", "lon", "sog", "name", "ship_type", "length", "width", "dest"])
    for line in io.TextIOWrapper(f, encoding="utf-8", errors="replace"):
        if not line.startswith("01/11/2026 16:4"):
            continue
        p = line.rstrip("\r\n").split(",")
        if len(p) < 24:
            continue
        if not ("16:40:00" <= p[0][11:] <= "16:50:00"):
            continue
        try:
            lat, lon = float(p[3]), float(p[4])
        except ValueError:
            continue
        if not (55.5 <= lat <= 58.0 and 11.8 <= lon <= 17.0):
            continue
        w.writerow([p[0][11:], p[1], p[2], lat, lon, p[7], p[12], p[13], p[17], p[15], p[19]])
        n += 1
print("rows", n)
