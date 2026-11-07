"""Simple documented ship detector for a Sentinel-1 GRD window: bright-point test vs local background."""
import sys, os, json, numpy as np, rasterio
from rasterio.windows import from_bounds
from rasterio.features import rasterize
from rasterio.transform import Affine
from scipy import ndimage

TIFF=os.environ["WAVE"]+"/data/t-match/s1c_vv.tiff"
LAND=os.environ["WAVE"]+"/data/t-match/ne_10m_land.geojson"

def load_window(bbox, band=1):
    with rasterio.open(TIFF) as ds:
        w=from_bounds(*bbox, transform=ds.transform)
        w=w.round_offsets().round_lengths()
        a=ds.read(band, window=w).astype("float32")
        tr=ds.window_transform(w)
        print("window", w, "shape", a.shape, "crs", ds.crs, "res", ds.res, file=sys.stderr)
        print("transform", tr, file=sys.stderr)
        print("value percentiles uncalibrated DN:", np.percentile(a[a>0],[1,50,90,99,99.9]).round(1), file=sys.stderr)
    return a, tr

def land_mask(shape, tr):
    gj=json.load(open(LAND))
    shapes=[(f["geometry"],1) for f in gj["features"]]
    m=rasterize(shapes, out_shape=shape, transform=tr, fill=0, default_value=1, all_touched=True)
    return m.astype(bool)

def detect(a, tr, block=32, thr_db=8.0, min_px=4, max_px=4000, max_extent_px=250, land=None, land_buffer_px=3):
    db=20*np.log10(np.maximum(a,1.0))
    # background: block mean of db with bright pixels clipped (robust-ish, cheap)
    H,W=db.shape
    hi=np.percentile(db[a>0], 97) if (a>0).any() else db.max()
    dbc=np.minimum(db,hi)
    pad=((H%block)//2, (W%block)//2)
    hb,wb=H//block, W//block
    blk=dbc[:hb*block,:wb*block].reshape(hb,block,wb,block).mean(axis=(1,3))
    bg=np.repeat(np.repeat(blk,block,axis=0),block,axis=1)
    bg=np.pad(bg,((0,H-bg.shape[0]),(0,W-bg.shape[1])),mode="edge")
    contrast=db-bg
    m=(contrast>thr_db)&(a>0)
    if land is not None:
        m &= ~ndimage.binary_dilation(land, iterations=land_buffer_px)
    lab,n=ndimage.label(m, structure=np.ones((3,3)))
    print("candidate px", int(m.sum()), "components", n, file=sys.stderr)
    objs=ndimage.find_objects(lab)
    rows=[]
    for i,sl in enumerate(objs, start=1):
        if sl is None: continue
        h=sl[0].stop-sl[0].start; w=sl[1].stop-sl[1].start
        mask=(lab[sl]==i)
        npx=int(mask.sum())
        if npx<min_px or npx>max_px or max(h,w)>max_extent_px: continue
        sub=db[sl]; subA=a[sl]
        ys,xs=np.nonzero(mask)
        cy=sl[0].start+ys.mean(); cx=sl[1].start+xs.mean()
        lon,lat=tr*(cx+0.5, cy+0.5)
        rows.append(dict(px=float(cx),py=float(cy),lon=lon,lat=lat,npx=npx,
            peak_db=float(sub[mask].max()), mean_db=float(sub[mask].mean()),
            peak_dn=float(subA[mask].max()), bg_db=float(bg[sl][mask].mean()),
            h=h,w=w, elong=max(h,w)/max(min(h,w),1),
            contrast=float(sub[mask].max()-bg[sl][mask].mean())))
    print("detections after size filter", len(rows), file=sys.stderr)
    return rows, db, bg

if __name__=="__main__":
    bbox=[float(x) for x in sys.argv[1:5]]
    tag=sys.argv[5] if len(sys.argv)>5 else "win"
    thr=float(sys.argv[6]) if len(sys.argv)>6 else 8.0
    a,tr=load_window(bbox)
    lm=land_mask(a.shape,tr)
    print("land fraction", lm.mean().round(3), file=sys.stderr)
    rows,db,bg=detect(a,tr,thr_db=thr,land=lm)
    import csv
    out=os.environ["WAVE"]+f"/data/t-match/det_{tag}.csv"
    with open(out,"w",newline="") as f:
        wcsv=csv.DictWriter(f, fieldnames=list(rows[0].keys())); wcsv.writeheader(); wcsv.writerows(rows)
    np.save(os.environ["WAVE"]+f"/data/t-match/db_{tag}.npy", db.astype("float32"))
    print("wrote", out)
