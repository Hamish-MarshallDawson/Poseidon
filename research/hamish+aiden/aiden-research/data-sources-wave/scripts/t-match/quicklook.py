import sys, numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, rasterio
sys.path.insert(0,'.'); import common
from rasterio.enums import Resampling
from rasterio.windows import Window
from rasterio.transform import Affine
bbox=[8.9,54.8,13.5,56.7]
r0,c0,r1,c1=common.window_for(bbox)
with rasterio.open(common.TIFF) as ds:
    w=Window(c0,r0,c1-c0,r1-r0)
    a=ds.read(1,window=w,out_shape=(800, int(800*(c1-c0)/(r1-r0))),resampling=Resampling.average).astype("float32")
db=20*np.log10(np.maximum(a,1))
print("shape",db.shape,"pct",np.percentile(db,[1,50,90,99]).round(1))
fig,ax=plt.subplots(figsize=(8,8),dpi=100)
ax.imshow(db,cmap="gray",vmin=np.percentile(db,5),vmax=np.percentile(db,99))
ax.set_title("S1C 2026-11-01T05:31:51Z VV overview (uncalibrated dB), lon 8.9-13.5, lat 54.8-56.7")
ax.set_xlabel("col"); ax.set_ylabel("row")
fig.tight_layout(); fig.savefig(common.D+"/overview_0532.png")
# also crop the Great Belt test box at full res
b=[10.6,55.05,11.45,55.75]
a2,(rr,cc)=common.read_window(b)
db2=20*np.log10(np.maximum(a2,1))
print("greatbelt shape",db2.shape)
fig,ax=plt.subplots(figsize=(8,10),dpi=100)
ax.imshow(db2[:, ::3],cmap="gray",vmin=np.percentile(db2,5),vmax=np.percentile(db2,99.5))
ax.set_title("Great Belt box 10.6-11.45E 55.05-55.75N (cols decimated x3)")
fig.tight_layout(); fig.savefig(common.D+"/greatbelt_raw.png")
