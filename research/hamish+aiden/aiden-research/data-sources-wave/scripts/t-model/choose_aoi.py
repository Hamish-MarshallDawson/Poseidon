"""Pick a big AOI: AIS vessels at image time x valid (non-nodata) Sentinel-1 data."""
import json, math
import numpy as np
import pandas as pd
import rasterio
from rasterio.transform import from_gcps

W = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave"
p = json.load(open("/tmp/s1picks.json"))["target"]
url = "https://sentinel-s1-l1c.s3.amazonaws.com/" + p["vv"][len("s3://sentinel-s1-l1c/"):]

df = pd.read_csv(f"{W}/data/t-ais-history/day_2026-11-01/classa_1630_1700Z.csv", parse_dates=["ts_utc"])
t = pd.Timestamp("2026-11-01T16:44:39Z")
pos = []
for mmsi, g in df.sort_values("ts_utc").groupby("mmsi"):
    if len(g) < 2:
        continue
    ts = g["ts_utc"].values.astype("datetime64[s]").astype(np.int64)
    tt = t.value // 10**9
    if ts[0] > tt or ts[-1] < tt:
        continue
    pos.append((mmsi, np.interp(tt, ts, g["lon"].values), np.interp(tt, ts, g["lat"].values),
                np.interp(tt, ts, g["sog"].values), g["length"].iloc[-1], g["name"].iloc[-1]))
ais = pd.DataFrame(pos, columns=["mmsi", "lon", "lat", "sog", "length", "name"])
print("vessels with bracketing fix:", len(ais),
      "| moving >=3kn:", int((ais.sog >= 3).sum()))

with rasterio.open(url) as src:
    gcps, _ = src.gcps
    tr = from_gcps(gcps)
    dec = 8
    arr = src.read(1, out_shape=(src.height // dec, src.width // dec),
                   resampling=rasterio.enums.Resampling.nearest)
    # pixel(col,row) of decimated grid ~ (c0/dec, r0/dec) via the affine
print("decimated valid frac", float((arr > 0).mean()), "shape", arr.shape)

# AIS pixel coords in the COG frame
cols, rows = zip(*[~tr * (lon, lat) for lon, lat in zip(ais.lon, ais.lat)])
ais["col"] = np.array(cols)
ais["row"] = np.array(rows)
v = (ais.col >= 0) & (ais.col < src.width) & (ais.row >= 0) & (ais.row < src.height)
print("in COG frame:", int(v.sum()))
ais = ais[v]
# valid-data test at decimated resolution
sub = arr[(ais.row // dec).astype(int).clip(0, arr.shape[0] - 1),
          (ais.col // dec).astype(int).clip(0, arr.shape[1] - 1)]
ais["valid"] = sub > 0
print("in valid data:", int(ais.valid.sum()), "| moving>=3kn in valid:",
      int(((ais.sog >= 3) & ais.valid).sum()))

# candidate boxes: 60x60, 80x60, 90x70 km sliding, scored by vessels+valid area
best = []
for wkm, hkm in [(60, 60), (80, 60), (90, 70), (60, 90)]:
    for c0 in range(0, src.width - wkm * 100, 1500):
        for r0 in range(0, src.height - hkm * 100, 1000):
            dc0, dc1 = c0 // dec, (c0 + wkm * 100) // dec
            dr0, dr1 = r0 // dec, (r0 + hkm * 100) // dec
            vf = float((arr[dr0:dr1, dc0:dc1] > 0).mean())
            if vf < 0.5:
                continue
            inb = ais[(ais.col >= c0) & (ais.col < c0 + wkm * 100)
                      & (ais.row >= r0) & (ais.row < r0 + hkm * 100)]
            nv = len(inb)
            nm = int((inb.sog >= 3).sum())
            if nv == 0:
                continue
            best.append((nv, nm, vf, wkm, hkm, c0, r0,
                         [(r.mmsi, round(r.length) if pd.notna(r.length) else None,
                           round(float(r.sog), 1)) for r in inb.itertuples()]))
best.sort(key=lambda x: (-x[0], -x[1]))
for b in best[:8]:
    print(f"box {b[3]}x{b[4]} km at col {b[5]} row {b[6]}: vessels {b[0]} moving {b[1]} "
          f"valid {b[2]:.2f} : {b[7]}")
