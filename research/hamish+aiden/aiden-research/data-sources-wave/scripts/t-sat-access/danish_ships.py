import numpy as np, rasterio, planetary_computer as pc, json
from rasterio.windows import Window
from pyproj import Transformer
from scipy import ndimage
from PIL import Image
from pystac_client import Client
c=Client.open('https://planetarycomputer.microsoft.com/api/stac/v1', timeout=120)
it=[i for i in c.search(collections=['sentinel-1-rtc'], ids=['S1C_IW_GRDH_1SDV_20261106T165210_20261106T165235_010219_014681_rtc']).items()][0]
lon,lat=12.60,55.40; n=2048
h=pc.sign(it.assets['vv'].href)
with rasterio.open(h) as ds:
    tr=Transformer.from_crs('EPSG:4326', ds.crs.to_string(), always_xy=True)
    x,y=tr.transform(lon,lat)
    cc=int((x-ds.transform.c)/ds.transform.a); rr=int((ds.transform.f-y)/abs(ds.transform.e))
    arr=ds.read(1, window=Window(cc-n//2, rr-n//2, n, n), boundless=True, fill_value=0)
db=10*np.log10(np.clip(arr,1e-6,None)); v=arr>0
med=float(np.median(db[v])); print('median dB',round(med,1),'std',round(float(db[v].std()),1),'p99',round(float(np.percentile(db[v],99)),1))
# simple local-background CFAR: 64x64 tile median, detect >tile+8 dB
ts=64; det=np.zeros_like(db,dtype=bool); ths=np.zeros_like(db)
for i in range(0,n,ts):
    for j in range(0,n,ts):
        t=db[i:i+ts,j:j+ts]; vv=v[i:i+ts,j:j+ts]
        if vv.sum()<ts*ts*0.5: continue
        m=np.median(t[vv]); ths[i:i+ts,j:j+ts]=m+8; det[i:i+ts,j:j+ts]=(t>m+8)&vv
lab,nl=ndimage.label(det)
sizes=ndimage.sum(det,lab,range(1,nl+1)) if nl else np.array([])
kept=[k+1 for k,s in enumerate(sizes) if 6<=s<=3000]
print('blobs total',nl,'kept 6..3000 px',len(kept),'largest',int(sizes.max()) if nl else 0)
peaks=sorted([(float(db[lab==k].max()),int(sizes[k-1])) for k in kept],reverse=True)[:10]
print('top peaks dB, px:',[(round(p,1),s) for p,s in peaks])
lo,hi=np.percentile(db[v],[2,99.8]); img=(np.clip((db-lo)/(hi-lo),0,1)*255).astype('uint8'); img[~v]=0
img=np.stack([img]*3,-1)
ys,xs=np.where(det)
img[ys,xs]=[255,0,0]
OUT='/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave/data/t-sat-access'
Image.fromarray(img).save(f'{OUT}/danish_rtc_2048_detections.png')
json.dump({'median_db':round(med,1),'det_blobs':len(kept),'px_area_km2':round((n*10/1000)**2,1),
           'top':[(round(p,1),s) for p,s in peaks]}, open('/tmp/tsat/danish_det.json','w'), indent=1)
print('window km:', n*10/1000,'x',n*10/1000)
