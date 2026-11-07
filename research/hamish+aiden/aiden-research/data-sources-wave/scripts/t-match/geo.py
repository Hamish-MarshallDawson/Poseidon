"""Georeference the S1 GRD COG from the product annotation geolocationGridPoint grid."""
import os, re, numpy as np, pandas as pd
from scipy.interpolate import RegularGridInterpolator
D=os.environ["WAVE"]+"/data/t-match"
TP=D+"/tiepoints.csv"
_df=pd.read_csv(TP)
_lines=np.unique(_df.line); _pxs=np.unique(_df.pixel)
LAT=np.zeros((len(_lines),len(_pxs))); LON=np.zeros_like(LAT)
for i,l in enumerate(_lines):
    for j,p in enumerate(_pxs):
        r=_df[(_df.line==l)&(_df.pixel==p)].iloc[0]
        LAT[i,j]=r.latitude; LON[i,j]=r.longitude
_lat=RegularGridInterpolator((_lines,_pxs), LAT, bounds_error=False, fill_value=None)
_lon=RegularGridInterpolator((_lines,_pxs), LON, bounds_error=False, fill_value=None)
LINES_T0=np.datetime64("2026-11-01T05:31:51.128286"); LINES_T1=np.datetime64("2026-11-01T05:32:16.127176")
N_LINES=16678; N_SAMPLES=26725

def latlon(line, pixel):
    pts=np.stack([np.atleast_1d(line).astype(float), np.atleast_1d(pixel).astype(float)], axis=-1)
    return _lat(pts), _lon(pts)

def line_time(line):
    """UTC time of a given line (linear between first and last line time)."""
    f=np.asarray(line,dtype=float)/ (N_LINES-1)
    t0=np.datetime64(LINES_T0,'ns').astype('int64'); t1=np.datetime64(LINES_T1,'ns').astype('int64')
    return (t0+f*(t1-t0))/1e9  # epoch seconds

def line_pixel_of(lat, lon, guess=None):
    """Invert the grid mapping for a lon/lat; returns (line, pixel) float, or None if outside."""
    ls=np.linspace(0,N_LINES-1,120); ps=np.linspace(0,N_SAMPLES-1,200)
    LL,PP=np.meshgrid(ls,ps,indexing="ij")
    la,lo=latlon(LL.ravel(),PP.ravel())
    d=(la-lat)**2*np.cos(np.radians(lat))**2+(lo-lon)**2
    k=int(np.argmin(d))
    if d[k] > (0.02)**2:   # more than ~2 km off the grid: outside the slice
        return None
    line, pix = LL.ravel()[k], PP.ravel()[k]
    # refine with local Newton using finite differences
    for _ in range(30):
        la0,lo0=latlon(line,pix); la0,lo0=float(la0[0]),float(lo0[0])
        if line<0 or line>N_LINES-1 or pix<0 or pix>N_SAMPLES-1: return None
        h=1.0
        la1,lo1=latlon(line+h,pix); la1,lo1=float(la1[0]),float(lo1[0])
        la2,lo2=latlon(line,pix+h); la2,lo2=float(la2[0]),float(lo2[0])
        J=np.array([[la1-la0,la2-la0],[lo1-lo0,lo2-lo0]])
        try: dq=np.linalg.solve(J, np.array([lat-la0, lon-lo0]))
        except np.linalg.LinAlgError: break
        line+=dq[0]; pix+=dq[1]
        if abs(dq).max()<1e-3: break
    if line<0 or line>N_LINES-1 or pix<0 or pix>N_SAMPLES-1: return None
    la0,lo0=latlon(line,pix)
    return line, pix

def window_for_bbox(west,south,east,north):
    """row/col window (half-open) covering the bbox, using the tie-point grid."""
    cs=[line_pixel_of(la,lo) for la in (north,south) for lo in (west,east)]
    cs=[c for c in cs if c is not None]
    if not cs: return None
    lines=[c[0] for c in cs]; pixs=[c[1] for c in cs]
    r0=max(int(np.floor(min(lines)))-1,0); r1=min(int(np.ceil(max(lines)))+1,N_LINES)
    c0=max(int(np.floor(min(pixs)))-1,0); c1=min(int(np.ceil(max(pixs)))+1,N_SAMPLES)
    return r0,c0,r1,c1

if __name__=="__main__":
    # sanity: corners and residual check
    for (la,lo) in [(56.0,11.0),(55.5,12.5),(55.2,11.0),(56.5,11.5)]:
        r=line_pixel_of(la,lo)
        print((la,lo),"->",None if r is None else (round(r[0],1),round(r[1],1)),
              "" if r is None else "back->%.5f,%.5f"%tuple(float(x[0]) for x in latlon(*r)))
    print("window for Great Belt/Grestrait 10.6-11.45E 55.05-55.75N:", window_for_bbox(10.6,55.05,11.45,55.75))
    print("window for Oresund 12.3-12.95E 55.6-56.1N:", window_for_bbox(12.3,55.6,12.95,56.1))
    print("line times", line_time(0), line_time(N_LINES//2), line_time(N_LINES-1))
