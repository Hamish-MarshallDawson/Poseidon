import time, json, os
import numpy as np, rasterio
from rasterio.windows import Window
from pystac_client import Client
import planetary_computer as pc

LON,LAT = 24.7, 59.9; d=0.03; bbox=[LON-d,LAT-d,LON+d,LAT+d]
c=Client.open('https://planetarycomputer.microsoft.com/api/stac/v1', timeout=60)
items=list(c.search(collections=['sentinel-1-grd'], bbox=bbox,
                    datetime='2026-10-08T00:00:00Z/2026-11-07T16:00:00Z', limit=50).items())
items.sort(key=lambda i:i.datetime)
it=items[-1]
a,b,lx,d_,e,ty = it.properties["proj:transform"]
def win(lon0,lat0,lon1,lat1):
    c0=int((lon0-lx)/a); c1=int((lon1-lx)/a); r0=int((ty-lat1)/abs(e)); r1=int((ty-lat0)/abs(e))
    return Window(c0, r0, max(1,c1-c0), max(1,r1-r0))
h=pc.sign(it.assets['vv'].href)
t0=time.time()
with rasterio.Env(GDAL_DISABLE_READDIR_ON_OPEN='EMPTY_DIR', CPL_VSIL_CURL_USE_HEAD='NO'):
    with rasterio.open(h) as ds:
        w=win(*bbox); print('window',w)
        a_=ds.read(1, window=w, out_shape=(512,512))
print('cold 512x512 read', round(time.time()-t0,2),'s', a_.shape, a_.dtype)
t0=time.time()
with rasterio.open(h) as ds:
    a2=ds.read(1, window=w, out_shape=(512,512))
print('warm read', round(time.time()-t0,2),'s')
db=20*np.log10(np.clip(a_.astype('float32'),1,None))-83.0
print('DN min/med/max',int(a_.min()),int(np.median(a_)),int(a_.max()),'dB p1/p50/p99',[round(float(np.percentile(db,p)),1) for p in (1,50,99)])
os.makedirs('/tmp/tsat',exist_ok=True); np.save('/tmp/tsat/arr.npy', a_)
json.dump({'id':it.id,'dt':it.datetime.isoformat(),'created':it.properties.get('created'),
  'transform':it.properties['proj:transform'],'shape':list(a_.shape),
  'asset_bytes':it.assets['vv'].to_dict().get('file:size')}, open('/tmp/tsat/read.json','w'), indent=1)
print(json.load(open('/tmp/tsat/read.json')))
