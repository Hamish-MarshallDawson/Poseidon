import sys, numpy as np, pandas as pd, rasterio, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from rasterio.windows import Window
sys.path.insert(0,'.'); import geo2
D=__import__("os").environ["WAVE"]+"/data/t-match"
TIFF=D+"/s1c_vv.tiff"
def grab(lat,lon,half_km=3.0):
    dlat=half_km/111.32; dlon=half_km/(111.32*np.cos(np.radians(lat)))
    w=geo2.window_for_bbox(lon-dlon,lat-dlat,lon+dlon,lat+dlat)
    r0,c0,r1,c1=w
    with rasterio.open(TIFF) as ds:
        a=ds.read(1,window=Window(c0,r0,c1-c0,r1-r0)).astype("float32")
    db=20*np.log10(np.maximum(a,1))
    rr=np.arange(r1-r0)+r0; cc=np.arange(c1-c0)+c0
    CC,RR=np.meshgrid(cc,rr); la,lo=geo2.latlon(RR,CC)
    return db,la,lo,r0,c0
def png(lat,lon,out,half_km=3.0,dets=None,ais=None,title=""):
    db,la,lo,r0,c0=grab(lat,lon,half_km)
    fig,ax=plt.subplots(figsize=(7,7),dpi=120)
    ax.pcolormesh(lo,la,db,cmap="gray",vmin=np.percentile(db,10),vmax=np.percentile(db,99.5),shading="auto")
    if dets is not None:
        m=(dets.lat>la.min())&(dets.lat<la.max())&(dets.lon>lo.min())&(dets.lon<lo.max())
        ax.plot(dets.lon[m],dets.lat[m],"o",ms=8,mfc="none",mec="red",mew=1.0)
    if ais is not None:
        m=(ais.lat>la.min())&(ais.lat<la.max())&(ais.lon>lo.min())&(ais.lon<lo.max())
        ax.plot(ais.lon[m],ais.lat[m],"+",ms=9,color="cyan",mew=1.2)
        for _,r in ais[m].iterrows():
            ax.annotate(str(r.get("name",""))[:14],(r.lon,r.lat),fontsize=5,color="cyan")
    ax.set_title(title,fontsize=7); ax.tick_params(labelsize=6)
    ax.set_xlabel("lon",fontsize=7); ax.set_ylabel("lat",fontsize=7)
    fig.tight_layout(); fig.savefig(D+"/"+out); plt.close(fig)
    print("wrote",out,"px",db.shape)
