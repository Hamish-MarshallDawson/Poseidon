import datetime as dt, json, time, os
import numpy as np, rasterio, planetary_computer as pc
from rasterio.windows import Window
from pystac_client import Client
from scipy import ndimage
from PIL import Image

NOW=dt.datetime(2026,11,7,16,30,tzinfo=dt.timezone.utc); START=NOW-dt.timedelta(days=30)
PTS={'Danish straits':(12.60,55.40),'Hormuz':(56.40,26.60),'Gulf of Oman':(57.50,24.80),
     'Malacca':(100.00,3.50),'Natuna':(107.00,3.50)}
OUT='/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave/data/t-sat-access'
os.makedirs(OUT,exist_ok=True)
c=Client.open('https://planetarycomputer.microsoft.com/api/stac/v1', timeout=120)
res={}
for name,(lon,lat) in PTS.items():
    try:
        items=[i for i in c.search(collections=['sentinel-1-grd'], bbox=[lon-.06,lat-.06,lon+.06,lat+.06],
               datetime=f"{START:%Y-%m-%dT%H:%M:%SZ}/{NOW:%Y-%m-%dT%H:%M:%SZ}", limit=100).items()]
        from shapely.geometry import shape, Point
        pt=Point(lon,lat)
        items=[i for i in items if i.datetime and shape(i.geometry).contains(pt)]
        items.sort(key=lambda i:i.datetime)
        it=items[-1]
        a,b,lx,d_,e,ty = it.properties['proj:transform']
        c0=int((lon-lx)/a)-512; r0=int((ty-lat)/abs(e))-512
        h=pc.sign(it.assets['vv'].href)
        t0=time.time()
        with rasterio.open(h) as ds:
            arr=ds.read(1, window=Window(c0,r0,1024,1024), boundless=True, fill_value=0)
        el=time.time()-t0
        db=20*np.log10(np.clip(arr.astype('float32'),1,None))-83.0
        sea=(arr>0)&(db>-60)
        if sea.sum()<1000: raise RuntimeError('window has little/no data: %d px'%int(sea.sum()))
        med=float(np.median(db[sea]))
        th=med+10
        m=(db>th)&sea
        lab,nl=ndimage.label(m)
        sizes=ndimage.sum(m,lab,range(1,nl+1))
        vessels=int(((sizes>=8)&(sizes<=4000)).sum())
        res[name]={'item':it.id,'dt':it.datetime.isoformat(),'proc':it.properties.get('s1:processing_datetime'),
          'read_s':round(el,2),'db_med':round(med,1),'db_p99':round(float(np.percentile(db[sea],99)),1),
          'db_max':round(float(db[sea].max()),1),'thr_dB_above_med':10,'blobs':int(nl),
          'blobs_8_to_4000px':vessels,'win_rows':1024,'win_cols':1024}
        # crop png (percentile stretch)
        lo,hi=np.percentile(db,[2,99.5]); img=np.clip((db-lo)/(hi-lo),0,1)
        Image.fromarray((img*255).astype('uint8')).save(f'{OUT}/{name.replace(" ","_")}_grd_vv_{it.id[:30]}.png')
        print(name, res[name])
    except Exception as ex:
        res[name]={'error':repr(ex)[:300]}; print(name,'ERR',repr(ex)[:200])
json.dump(res, open('/tmp/tsat/region_probe.json','w'), indent=1)
