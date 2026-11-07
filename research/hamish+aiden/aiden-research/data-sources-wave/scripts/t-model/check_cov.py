"""Cheap nodata check for candidate AOIs inside the target slice VV COG."""
import json, sys
import numpy as np
import rasterio
from rasterio.transform import from_gcps

p = json.load(open("/tmp/s1picks.json"))["target"]
url = "https://sentinel-s1-l1c.s3.amazonaws.com/" + p["vv"][len("s3://sentinel-s1-l1c/"):]
cands = {
    "aoi1_kattegat": (12.25, 56.30, 12.85, 56.70),
    "aoi2_oresund": (12.45, 55.95, 12.95, 56.35),
    "aoi3_kattegat_e": (12.6, 56.3, 13.2, 56.7),
    "aoi4_baltic": (13.3, 55.2, 13.9, 55.6),
}
with rasterio.open(url) as src:
    gcps, _ = src.gcps
    tr = from_gcps(gcps)
    for name, (lon0, lat0, lon1, lat1) in cands.items():
        cols, rows = zip(*[~tr * (lon, lat) for lon in (lon0, lon1) for lat in (lat0, lat1)])
        c0, c1 = max(0, int(min(cols))), min(src.width, int(max(cols)))
        r0, r1 = max(0, int(min(rows))), min(src.height, int(max(rows)))
        if c1 - c0 < 50 or r1 - r0 < 50:
            print(name, "outside frame", (c0, c1, r0, r1))
            continue
        arr = src.read(1, window=rasterio.windows.Window(c0, r0, c1 - c0, r1 - r0), out_shape=(400, 400))
        zero = float((arr == 0).mean())
        db = 10 * np.log10(np.maximum(arr.astype("float32"), 1))
        med = float(np.median(db[arr > 0])) if (arr > 0).any() else float("nan")
        bright = int((db > med + 8).sum()) if arr.size else 0
        print(f"{name}: frame cols {c0}-{c1} rows {r0}-{r1} nodata_frac={zero:.3f} median_dB={med:.1f} px>+8dB={bright}")
