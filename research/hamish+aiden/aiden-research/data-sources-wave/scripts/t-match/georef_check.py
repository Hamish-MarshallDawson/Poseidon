import sys, json, numpy as np, matplotlib; matplotlib.use("Agg")
import matplotlib.pyplot as plt, rasterio
from rasterio.features import rasterize
from rasterio.transform import Affine
sys.path.insert(0,'.'); import common
from scipy import ndimage
bbox=[10.3,54.95,12.2,55.95]
a,(r0,c0)=common.read_window(bbox)
tr=Affine(common.A,0,common.C+c0*common.A,0,common.E,common.F+r0*common.E)
gj=json.load(open(common.D+"/ne_10m_land.geojson"))
land=rasterize([(f["geometry"],1) for f in gj["features"]],out_shape=a.shape,transform=tr,fill=0,default_value=1,all_touched=True).astype(bool)
db=20*np.log10(np.maximum(a,1))
edge=land^ndimage.binary_erosion(land,iterations=2)
print("shape",db.shape,"land frac",land.mean().round(3))
step=6
fig,ax=plt.subplots(figsize=(9,9),dpi=110)
ax.imshow(db[::step,::step],cmap="gray",vmin=np.percentile(db,5),vmax=np.percentile(db,99))
ys,xs=np.nonzero(edge[::step,::step]); ax.plot(xs,ys,",",color="red",alpha=0.5)
ax.set_title("land mask (Natural Earth 10m) edges in red over S1 VV; uncorrected proj:transform")
fig.tight_layout(); fig.savefig(common.D+"/georef_check.png")
