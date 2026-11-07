"""Georeference the S1 GRD product from annotation tie points (bilinear on the 10x21 grid) + fast bbox windowing."""
import os, sys, numpy as np, pandas as pd
from scipy.interpolate import RegularGridInterpolator
D=os.environ["WAVE"]+"/data/t-match"
df=pd.read_csv(os.environ.get("GEO_TP", D+"/tiepoints.csv"))
N_LINES=int(os.environ.get("GEO_LINES","16678")); N_SAMPLES=int(os.environ.get("GEO_SAMPLES","26725"))
lines=np.unique(df.line); pxs=np.unique(df.pixel)
LAT=np.zeros((len(lines),len(pxs))); LON=np.zeros_like(LAT)
li={l:i for i,l in enumerate(lines)}; pi={p:j for j,p in enumerate(pxs)}
for _,r in df.iterrows():
    LAT[li[r.line],pi[r.pixel]]=r.latitude; LON[li[r.line],pi[r.pixel]]=r.longitude
_lat=RegularGridInterpolator((lines,pxs),LAT,bounds_error=False,fill_value=None)
_lon=RegularGridInterpolator((lines,pxs),LON,bounds_error=False,fill_value=None)

def latlon(line,pixel):
    pts=np.stack([np.ravel(np.asarray(line,float)), np.ravel(np.asarray(pixel,float))],axis=-1)
    la=_lat(pts).reshape(np.shape(line)); lo=_lon(pts).reshape(np.shape(line))
    return la,lo

T0=pd.Timestamp(os.environ.get("GEO_T0","2026-11-01T05:31:51.128286Z")).timestamp()
T1=pd.Timestamp(os.environ.get("GEO_T1","2026-11-01T05:32:16.127176Z")).timestamp()
def line_time(line):
    return T0+np.asarray(line,float)/(N_LINES-1)*(T1-T0)

def window_for_bbox(west,south,east,north):
    lg,pg=np.meshgrid(np.arange(0,N_LINES,6), np.arange(0,N_SAMPLES,6), indexing="ij")
    la,lo=latlon(lg,pg)
    m=(la>=south)&(la<=north)&(lo>=west)&(lo<=east)
    if not m.any(): return None
    r,c=np.nonzero(m)
    return max(int(lg[r.min(),c.min()])-12,0), max(int(pg[r.min(),c.min()])-12,0), min(int(lg[r.max(),c.max()])+13,N_LINES), min(int(pg[r.max(),c.max()])+13,N_SAMPLES)

def line_pixel_of(lat,lon):
    lg,pg=np.meshgrid(np.arange(0,N_LINES,6), np.arange(0,N_SAMPLES,6), indexing="ij")
    la,lo=latlon(lg,pg)
    d=(la-lat)**2*np.cos(np.radians(lat))**2+(lo-lon)**2
    k=np.unravel_index(np.argmin(d), d.shape)
    if d[k]>(0.01)**2: return None
    line=float(lg[k]); pix=float(pg[k])
    for _ in range(20):
        a,b=latlon(line,pix); a=float(a); b=float(b); h=2.0
        a1,b1=latlon(line+h,pix); a2,b2=latlon(line,pix+h)
        J=np.array([[float(a1)-a,float(a2)-a],[float(b1)-b,float(b2)-b]])
        try: dq=np.linalg.solve(J,np.array([lat-a,lon-b]))
        except np.linalg.LinAlgError: break
        line+=dq[0]; pix+=dq[1]
        if np.abs(dq).max()<1e-3: break
    return line,pix
