"""Quick look at the AOI inside the target VV COG via anonymous https range reads."""
import json, time
import numpy as np
import rasterio
from rasterio.transform import from_gcps
import rasterio.warp

p = json.load(open("/tmp/s1picks.json"))["target"]
url = "https://sentinel-s1-l1c.s3.amazonaws.com/" + p["vv"][len("s3://sentinel-s1-l1c/"):]
t0 = time.time()
ds = rasterio.open(url)
print("open", round(time.time()-t0, 2), "s; size", ds.width, ds.height, ds.count, ds.dtypes, "crs", ds.crs)
gcps, gcp_crs = ds.gcps
print("np gcps", len(gcps), "crs", gcp_crs)
tr = from_gcps(gcps)

lon0, lat0, lon1, lat1 = 12.25, 56.30, 12.85, 56.70
c0, r0 = ~tr * (lon0, lat1)
c1, r1 = ~tr * (lon1, lat0)
r0, r1 = sorted((r0, r1)); c0, c1 = sorted((c0, c1))
c0, r0, c1, r1 = max(0,int(c0)), max(0,int(r0)), min(ds.width,int(c1)), min(ds.height,int(r1))
print("window rows", r0, r1, "cols", c0, c1)
t0 = time.time()
win = rasterio.windows.Window(c0, r0, c1-c0, r1-r0)
arr = ds.read(1, window=win)
print("read", round(time.time()-t0, 2), "s shape", arr.shape, arr.dtype, "min/max", arr.min(), arr.max())
np.save(f"{__file__.rsplit('/',1)[0]}/../../data/t-model/aoi_vv.npy", arr)
# bright target count with a crude median + 8 dB test in 64x64 tiles
arrf = arr.astype("float32")
db = 10*np.log10(np.maximum(arrf, 1))
med = np.median(db)
print("scene median dB", round(float(med), 2), "p99.9", round(float(np.percentile(db, 99.9)), 2))
mask = db > med + 8
print("pixels > median+8dB:", int(mask.sum()))
