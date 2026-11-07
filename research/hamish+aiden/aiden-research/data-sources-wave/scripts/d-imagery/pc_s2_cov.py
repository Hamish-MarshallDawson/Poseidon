import json, urllib.request, datetime as dt
base="https://planetarycomputer.microsoft.com/api/stac/v1/search"
def post(b):
    req=urllib.request.Request(base, data=json.dumps(b).encode(), headers={"Content-Type":"application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))
boxes={"mid-Atlantic 30W20N":[-31,19,-29,21],"Gulf of Guinea":[2,0,4,2],
 "South China Sea open":[112,10,114,12],"Indian Ocean 70E10S":[69,-11,71,-9],
 "Hormuz":[56.0,26.2,57.0,27.0],"Natuna":[107.5,2.5,109.0,4.0],"Baltic Gotland":[18.5,57.0,19.5,58.0]}
end=dt.datetime(2026,11,7,tzinfo=dt.timezone.utc); start=end-dt.timedelta(days=30)
for name,box in boxes.items():
    r=post({"collections":["sentinel-2-l2a"],"bbox":box,"datetime":f"{start:%Y-%m-%dT%H:%M:%SZ}/{end:%Y-%m-%dT%H:%M:%SZ}","limit":500})
    f=r["features"]
    clear=[x for x in f if (x["properties"].get("eo:cloud_cover") or 100) < 20]
    print(f"{name:24s} s2_scenes={len(f):3d} clear<20%={len(clear):3d} platforms={sorted({x['properties']['platform'] for x in f})}")
