import sys, numpy as np, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
sys.path.insert(0,'.')
import common

def crop_png(lat, lon, half_m=900, out="crop.png", dets=None, ais=None, title="", band_label="VV (relative dB, uncalibrated)"):
    dlat=half_m/111320.0; dlon=half_m/(111320.0*np.cos(np.radians(lat)))
    bbox=[lon-dlon, lat-dlat, lon+dlon, lat+dlat]
    a,(r0,c0)=common.read_window(bbox)
    db=20*np.log10(np.maximum(a,1.0))
    vmin,vmax=np.percentile(db[db>-30],[5,99.5]) if (db>-30).any() else (0,40)
    fig,ax=plt.subplots(figsize=(7,7),dpi=110)
    tr=common.transform_for(bbox)[0]  # actually transform_for returns (t,offset)
    from rasterio.transform import Affine
    tr=Affine(common.A,0,common.C+c0*common.A,0,common.E,common.F+r0*common.E)
    ext=[common.C+c0*common.A, common.C+(c0+db.shape[1])*common.A, common.F+(r0+db.shape[0])*common.E, common.F+r0*common.E]
    ax.imshow(db, cmap="gray", vmin=vmin, vmax=vmax, extent=ext, origin="upper")
    if dets is not None:
        for _,d in dets.iterrows():
            ax.plot(d.lon, d.lat, "o", ms=6, mfc="none", mec="red", mew=0.8)
    if ais is not None:
        for _,d in ais.iterrows():
            ax.plot(d.lon, d.lat, "+", ms=7, color="cyan", mew=1.0)
    ax.set_title(title, fontsize=7)
    ax.set_xlabel("lon", fontsize=7); ax.set_ylabel("lat", fontsize=7)
    ax.tick_params(labelsize=6)
    fig.tight_layout(); fig.savefig(out); plt.close(fig)
    print("wrote", out, "shape", db.shape, "extent", [round(x,4) for x in ext])
