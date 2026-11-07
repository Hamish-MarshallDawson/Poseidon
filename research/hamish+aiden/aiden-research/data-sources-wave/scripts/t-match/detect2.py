"""Ship detection on a georeferenced S1 GRD window: bright-point test against a local block background."""
import sys, os, json, time, numpy as np, rasterio, matplotlib
matplotlib.use("Agg"); import matplotlib.pyplot as plt
from rasterio.windows import Window
from rasterio.features import rasterize
from rasterio.transform import Affine
from scipy import ndimage
sys.path.insert(0,'.')
import geo2

TIFF=os.environ.get("S1_TIFF", os.environ["WAVE"]+"/data/t-match/s1c_vv.tiff")
LAND=os.environ["WAVE"]+"/data/t-match/ne_10m_land.geojson"
LANDG=[(f["geometry"],1) for f in json.load(open(LAND))["features"]]

def read(r0,c0,r1,c1):
    with rasterio.open(TIFF) as ds:
        return ds.read(1, window=Window(c0,r0,c1-c0,r1-r0)).astype("float32")

def landmask(r0,c0,shape,step=4,deg=0.0002):
    H,W=shape
    rr=np.arange(0,H,step); cc=np.arange(0,W,step)
    CC,RR=np.meshgrid(cc,rr)
    la,lo=geo2.latlon(RR+r0,CC+c0)
    wc,ec=lo.min(),lo.max(); sc,nc=la.min(),la.max()
    gw=int((ec-wc)/deg)+2; gh=int((nc-sc)/deg)+2
    tr=Affine(deg,0,wc,0,-deg,nc+deg)
    g=rasterize(LANDG,out_shape=(gh,gw),transform=tr,fill=0,default_value=1,all_touched=True).astype(bool)
    ci=np.clip(((lo-wc)/deg).astype(int),0,gw-1); ri=np.clip(((nc-la)/deg).astype(int),0,gh-1)
    m=g[ri,ci]
    return np.repeat(np.repeat(m,step,axis=0),step,axis=1)[:H,:W]

def detect(a, thr_db=8.0, min_px=4, max_px=5000, max_extent=200, land=None, land_buf=3, block=32):
    db=20*np.log10(np.maximum(a,1.0))
    H,W=db.shape; hb,wb=H//block,W//block
    hi=np.percentile(db[a>0],97)
    blk=np.minimum(db[:hb*block,:wb*block],hi).reshape(hb,block,wb,block).mean(axis=(1,3))
    bg=np.pad(np.repeat(np.repeat(blk,block,axis=0),block,axis=1),((0,H-hb*block),(0,W-wb*block)),mode="edge")
    m=(db-bg>thr_db)&(a>0)
    if land is not None: m&=~ndimage.binary_dilation(land,iterations=land_buf)
    lab,n=ndimage.label(m,structure=np.ones((3,3)))
    objs=ndimage.find_objects(lab); rows=[]
    for i,sl in enumerate(objs,1):
        if sl is None: continue
        h,w=sl[0].stop-sl[0].start, sl[1].stop-sl[1].start
        mk=(lab[sl]==i); npx=int(mk.sum())
        if npx<min_px or npx>max_px or max(h,w)>max_extent: continue
        ys,xs=np.nonzero(mk)
        rows.append(dict(row=float(sl[0].start+ys.mean()),col=float(sl[1].start+xs.mean()),npx=npx,h=h,w=w,
            peak_db=float(db[sl][mk].max()),bg_db=float(bg[sl][mk].mean()),peak_dn=float(a[sl][mk].max()),
            elong=float(max(h,w)/max(min(h,w),1))))
    return rows,db,bg,m

def run(bbox,tag,thr_db=8.0,png=True):
    t0=time.time()
    w=geo2.window_for_bbox(*bbox); r0,c0,r1,c1=w
    a=read(r0,c0,r1,c1); H,W=a.shape
    print(f"[{tag}] rows {r0}..{r1} cols {c0}..{c1} = {H}x{W} = {H*W/1e6:.1f} Mpx, read {time.time()-t0:.1f}s", file=sys.stderr)
    lm=landmask(r0,c0,a.shape); print(f"[{tag}] land frac {lm.mean():.3f} ({time.time()-t0:.1f}s)", file=sys.stderr)
    rows,db,bg,m=detect(a,thr_db=thr_db,land=lm,land_buf=int(os.environ.get('DET_LAND_BUF','3')),min_px=int(os.environ.get('DET_MIN_PX','4')),max_extent=int(os.environ.get('DET_MAX_EXTENT','200')))
    del a,m
    import pandas as pd
    df=pd.DataFrame(rows)
    if len(df):
        la,lo=geo2.latlon(df.row.values+r0,df.col.values+c0); df["lat"]=la; df["lon"]=lo
    out=f"{os.environ['WAVE']}/data/t-match/det_{tag}.csv"; df.to_csv(out,index=False)
    open(f"{os.environ['WAVE']}/data/t-match/meta_{tag}.json","w").write(__import__("json").dumps(dict(r0=r0,c0=c0,r1=r1,c1=c1,bbox=bbox,thr_db=thr_db)))
    print(f"[{tag}] detections {len(df)} in {time.time()-t0:.1f}s -> {out}", file=sys.stderr)
    np.save(f"{os.environ['WAVE']}/data/t-match/db_{tag}.npy", db[::2,::2].astype('float32'))
    if png:
        st=5; rr=np.arange(0,H,st); cc=np.arange(0,W,st); CC,RR=np.meshgrid(cc,rr)
        la,lo=geo2.latlon(RR+r0,CC+c0)
        fig,ax=plt.subplots(figsize=(10,11),dpi=100)
        ax.pcolormesh(lo,la,db[::st,::st],cmap="gray",vmin=np.percentile(db,5),vmax=np.percentile(db,99),shading="auto")
        if len(df): ax.plot(df.lon,df.lat,"o",ms=5,mfc="none",mec="red",mew=0.7)
        ax.set_title(f"S1C 2026-11-01 ~05:32Z VV; {len(df)} radar detections (red)",fontsize=9)
        ax.set_xlabel("lon"); ax.set_ylabel("lat"); ax.tick_params(labelsize=8)
        fig.tight_layout(); fig.savefig(f"{os.environ['WAVE']}/data/t-match/det_{tag}.png"); plt.close(fig)
    return df

if __name__=="__main__":
    run([float(x) for x in sys.argv[1:5]], sys.argv[5], float(sys.argv[6]) if len(sys.argv)>6 else 8.0)
