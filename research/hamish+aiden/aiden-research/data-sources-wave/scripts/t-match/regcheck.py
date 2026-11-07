"""Independent check of georeferencing: FFT cross-correlation of the Natural Earth land mask with the image's land/sea contrast."""
import sys, numpy as np, rasterio, json
from rasterio.windows import Window
from scipy import ndimage, signal
sys.path.insert(0,'.'); import geo2, detect2
D=__import__("os").environ["WAVE"]+"/data/t-match"
r0,c0,r1,c1=geo2.window_for_bbox(10.95,55.15,11.35,55.55)
with rasterio.open(D+"/s1c_vv.tiff") as ds:
    a=ds.read(1,window=Window(c0,r0,c1-c0,r1-r0)).astype("float32")
db=20*np.log10(np.maximum(a,1))
st=3
sm=ndimage.uniform_filter(db,9)[::st,::st]
land=detect2.landmask(r0,c0,a.shape,step=3).astype(float)
land=ndimage.uniform_filter(land[::st,::st],3)
img=sm-sm.mean(); L=land-land.mean()
C=signal.fftconvolve(img, L[::-1,::-1], mode="same")
k=np.unravel_index(np.argmax(C), C.shape)
dr=(k[0]-C.shape[0]//2)*st; dc=(k[1]-C.shape[1]//2)*st
print("best shift row %+d col %+d pixels x 10 m  => row %.0f m, col %.0f m"%(dr,dc,dr*10,dc*10))
print("corr at best %.4f, at zero %.4f"%(C[k]/np.sqrt((img**2).sum()*(L**2).sum()), C[C.shape[0]//2,C.shape[1]//2]/np.sqrt((img**2).sum()*(L**2).sum())))
# what direction is +row in metres?
la1,lo1=geo2.latlon(r0+4000,c0+4000); la2,lo2=geo2.latlon(r0+4050,c0+4000)
la3,lo3=geo2.latlon(r0+4000,c0+4050)
coslat=np.cos(np.radians(56))
print("+50 rows = dn %.0f m, de %.0f m | +50 cols = dn %.0f m, de %.0f m"%((la2-la1)*111320,(lo2-lo1)*111320*coslat,(la3-la1)*111320,(lo3-lo1)*111320*coslat))
