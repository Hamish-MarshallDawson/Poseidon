import json, urllib.request, datetime as dt
base="https://planetarycomputer.microsoft.com/api/stac/v1/search"
def post(b):
    req=urllib.request.Request(base, data=json.dumps(b).encode(), headers={"Content-Type":"application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))
end=dt.datetime(2026,11,7,tzinfo=dt.timezone.utc); start=end-dt.timedelta(days=14)
box=[18.5,57.0,19.5,58.0]
for coll in ("sentinel-1-grd","sentinel-1-rtc"):
    f=post({"collections":[coll],"bbox":box,"datetime":f"{start:%Y-%m-%dT%H:%M:%SZ}/{end:%Y-%m-%dT%H:%M:%SZ}","limit":500})["features"]
    ts=sorted(x["properties"]["datetime"][:16] for x in f)
    print(coll, "n=",len(f), "newest=",ts[-1] if ts else None, "oldest=",ts[0] if ts else None)
