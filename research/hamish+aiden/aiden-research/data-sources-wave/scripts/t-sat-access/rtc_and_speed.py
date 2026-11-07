import time, numpy as np, rasterio, planetary_computer as pc
from rasterio.windows import Window
from pystac_client import Client
c=Client.open('https://planetarycomputer.microsoft.com/api/stac/v1', timeout=120)
# 1) sentinel-1-rtc: check georeferencing
try:
    it=list(c.search(collections=['sentinel-1-rtc'], bbox=[24.67,59.87,24.73,59.93],
        datetime='2026-10-08T00:00:00Z/2026-11-07T16:00:00Z', limit=3).items())[0]
    h=pc.sign(it.assets['vv'].href)
    with rasterio.open(h) as ds:
        print('RTC', it.id, ds.crs, ds.shape, ds.res, ds.dtypes[0], ds.transform)
        print('RTC props proj:code', it.properties.get('proj:code'), 'epsg', it.properties.get('proj:epsg'))
except Exception as e:
    print('RTC ERR', repr(e)[:300])
# 2) GRD window-size scaling
it=list(c.search(collections=['sentinel-1-grd'], bbox=[24.67,59.87,24.73,59.93],
    datetime='2026-10-08T00:00:00Z/2026-11-07T16:00:00Z', limit=3).items())[0]
h=pc.sign(it.assets['vv'].href)
print('GRD item', it.id, it.properties['proj:transform'])
with rasterio.open(h) as ds:
    for px in (256,512,1024,2048):
        t0=time.time()
        a=ds.read(1, window=Window(7522,10181,px,px))
        el=time.time()-t0
        print(f'  {px}x{px} read {el:.2f}s  {px*px*2/1e6:.1f} MB raw  {px*px*2/1e6/el:.2f} MB/s')
