import json, urllib.request, datetime as dt
from collections import Counter
base="https://earth-search.aws.element84.com/v1/search"
def post(body):
    req=urllib.request.Request(base, data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))
boxes={
 "mid-Atlantic 30W20N":[ -31,19,-29,21],
 "Gulf of Guinea":[2,0,4,2],
 "South China Sea open":[112,10,114,12],
 "Indian Ocean 70E10S":[69,-11,71,-9],
 "Hormuz":[56.0,26.2,57.0,27.0],
 "Natuna":[107.5,2.5,109.0,4.0],
 "Baltic Gotland":[18.5,57.0,19.5,58.0],
}
end=dt.datetime(2026,11,7,tzinfo=dt.timezone.utc); start=end-dt.timedelta(days=30)
for name,box in boxes.items():
    r=post({"collections":["sentinel-1-grd"],"bbox":box,
            "datetime":f"{start:%Y-%m-%dT%H:%M:%SZ}/{end:%Y-%m-%dT%H:%M:%SZ}","limit":1000})
    f=r["features"]
    ts=sorted(x["properties"]["datetime"][:16] for x in f)
    plat=Counter(x["properties"]["platform"] for x in f)
    mode=Counter(x["properties"].get("sar:instrument_mode") for x in f)
    gaps=""
    if len(ts)>1:
        dts=[dt.datetime.fromisoformat(t) for t in ts]
        gaps=max((b-a).total_seconds()/3600 for a,b in zip(dts,dts[1:]))
    print(f"{name:24s} scenes={len(f):3d} platforms={dict(plat)} modes={dict(mode)} first={ts[0] if ts else '-'} last={ts[-1] if ts else '-'} longest_gap_h={gaps}")
