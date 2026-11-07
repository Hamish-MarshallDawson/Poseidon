import datetime as dt, json, os, time
import numpy as np, rasterio, planetary_computer as pc
from rasterio.windows import Window
from pyproj import Transformer
from shapely.geometry import shape, Point
from pystac_client import Client
from scipy import ndimage
from PIL import Image
NOW=dt.datetime(2026,11,7,16,30,tzinfo=dt.timezone.utc); START=NOW-dt.timedelta(days=30)
OUT='/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave/data/t-sat-access'
os.makedirs(OUT,exist_ok=True)
c=Client.open('https://planetarycomputer.microsoft.com/api/stac/v1', timeout=120)
PTS={'Helsinki(land,control)':(24.94,60.17),'Danish straits':(12.60,55.40),'Hormuz':(56.40,26.60),
     'Gulf of Oman':(57.50,24.80),'Malacca':(100.00,3.50),'Natuna':(107.00,3.50)}
res={}
for name,(lon,lat) in PTS.items():
    try:
        items=[i for i in c.search(collections=['sentinel-1-rtc'], bbox=[lon-.06,lat-.06,lon+.06,lat+.06],
             datetime=f"{START:%Y-%m-%dT%H:%M:%SZ}/{NOW:%Y-%m-%dT%H:%M:%SZ}", limit=200).items()]
        pt=Point(lon,lat)
        items=[i for i in items if i.datetime and shape(i.geometry).contains(pt)]
        items.sort(key=lambda i:i.datetime)
        r={'rtc_items_30d':len(items),'last':items[-1].datetime.isoformat() if items else None}
        if not items: res[name]=r; print(name,r); continue
        it=items[-1]
        h=pc.sign(it.assets['vv'].href)
        t0=time.time()
        with rasterio.open(h) as ds:
            tr=Transformer.from_crs('EPSG:4326', ds.crs.to_string(), always_xy=True)
            x,y=tr.transform(lon,lat)
            cc=int((x-ds.transform.c)/ds.transform.a); rr=int((ds.transform.f-y)/abs(ds.transform.e))
            n=512
            arr=ds.read(1, window=Window(cc-n//2, rr-n//2, n, n), boundless=True, fill_value=0)
            crs=str(ds.crs); res_px=abs(ds.transform.a)
        el=time.time()-t0
        db=10*np.log10(np.clip(arr,1e-6,None))
        v=arr>0
        med=float(np.median(db[v])); std=float(db[v].std())
        m=(db>med+10)&v; lab,nl=ndimage.label(m); sizes=ndimage.sum(m,lab,range(1,nl+1)) if nl else np.array([])
        r.update({'id':it.id,'read_s':round(el,2),'crs':crs,'res_m':res_px,'db_med':round(med,1),
                  'db_std':round(std,1),'db_max':round(float(db[v].max()),1),'valid_frac':round(float(v.mean()),2),
                  'frac_gt_-20dB':round(float((db[v]>-20).mean()),3),
                  'blobs_ge6px_thr+10dB':int((sizes>=6).sum()) if nl else 0})
        lo,hi=np.percentile(db[v],[2,99.7]); img=np.clip((db-lo)/(hi-lo),0,1); img[~v]=0
        Image.fromarray((img*255).astype('uint8')).save(f"{OUT}/rtc_{name.split('(')[0].replace(' ','_')}.png")
        res[name]=r; print(name,r)
    except Exception as ex:
        res[name]={'error':repr(ex)[:200]}; print(name,'ERR',repr(ex)[:200])
json.dump(res, open('/tmp/tsat/rtc_probe.json','w'), indent=1)
