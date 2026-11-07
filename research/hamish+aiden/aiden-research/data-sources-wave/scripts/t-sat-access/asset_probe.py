import json, time, requests
from pystac_client import Client
import planetary_computer as pc
res=json.load(open('/tmp/stac_probe.json'))
# get one item from each
for name,url in [('pc','https://planetarycomputer.microsoft.com/api/stac/v1'),
                 ('e84','https://earth-search.aws.element84.com/v1'),
                 ('cdse','https://stac.dataspace.copernicus.eu/v1')]:
    c=Client.open(url, timeout=60)
    # pick a Gulf of Finland item
    items=list(c.search(collections=['sentinel-1-grd'], bbox=[24.68,59.88,24.72,59.92],
                        datetime='2026-10-08T00:00:00Z/2026-11-07T16:31:00Z', limit=5).items())
    if not items: print(name,'no items'); continue
    it=items[0]
    print('==',name, it.id, it.datetime)
    for k in ('vv','VV','vh','local_incidence_angle','safe'):
        if k in it.assets:
            h=it.assets[k].href
            if name=='pc': h=pc.sign(h)
            t0=time.time()
            try:
                r=requests.get(h, headers={'Range':'bytes=0-1023'}, timeout=30, allow_redirects=True)
                print(' ',k,r.status_code, r.headers.get('content-range'), len(r.content),'bytes', round(time.time()-t0,2),'s',
                      h.split('?')[0][:110])
            except Exception as e:
                print(' ',k,'ERR',repr(e)[:200])
