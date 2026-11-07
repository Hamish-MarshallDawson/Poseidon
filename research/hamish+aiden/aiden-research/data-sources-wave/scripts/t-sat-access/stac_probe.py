import datetime as dt, json, time, sys
from pystac_client import Client
import planetary_computer as pc

now = dt.datetime.now(dt.timezone.utc)
start = (now - dt.timedelta(days=30)).strftime('%Y-%m-%dT%H:%M:%SZ')
end = now.strftime('%Y-%m-%dT%H:%M:%SZ')
print("window UTC:", start, "->", end)
pt = (24.7, 59.9)  # Gulf of Finland test point
bbox = [pt[0]-0.02, pt[1]-0.02, pt[0]+0.02, pt[1]+0.02]

cats = {
 'pc': 'https://planetarycomputer.microsoft.com/api/stac/v1',
 'e84': 'https://earth-search.aws.element84.com/v1',
 'cdse': 'https://stac.dataspace.copernicus.eu/v1',
}
out={}
for name,url in cats.items():
    t0=time.time()
    try:
        c = Client.open(url, timeout=60)
        col = 'sentinel-1-grd' if name!='cdse' else 'sentinel-1-grd'
        s = c.search(collections=[col], bbox=bbox, datetime=f"{start}/{end}", limit=1000)
        items = list(s.items())
        out[name]={'n':len(items),'secs':round(time.time()-t0,2),
                   'ids':[i.id for i in items][:5],
                   'datetime':[i.datetime.isoformat() if i.datetime else None for i in items][:5],
                   'assets':sorted(items[0].assets.keys()) if items else []}
        print(name, out[name]['n'], 'items', out[name]['secs'],'s')
    except Exception as e:
        out[name]={'error':repr(e)[:300]}
        print(name,'ERR',repr(e)[:300])
json.dump(out, open('/tmp/stac_probe.json','w'), indent=1)
