import json, urllib.request, datetime as dt
base="https://planetarycomputer.microsoft.com/api/stac/v1/search"
def post(body):
    req=urllib.request.Request(base, data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
    return json.load(urllib.request.urlopen(req, timeout=90))
# Danish straits box
box=[11.0,54.5,13.5,56.5]
end=dt.datetime(2026,11,7,tzinfo=dt.timezone.utc)
start=end-dt.timedelta(days=7)
r=post({"collections":["sentinel-1-grd"],"bbox":box,"datetime":f"{start:%Y-%m-%dT%H:%M:%SZ}/{end:%Y-%m-%dT%H:%M:%SZ}","limit":1000})
feats=r["features"]
print("items:",len(feats), "matched:", r.get("context",{}).get("matched"))
from collections import Counter
c=Counter((f["properties"].get("platform"), f["properties"].get("sar:instrument_mode"), f["properties"].get("sar:product_type")) for f in feats)
for k,v in sorted(c.items()): print(k,v)
t=sorted(f["properties"]["datetime"] for f in feats)
print("first",t[0],"last",t[-1])
p=feats[0]["properties"]
print({k:p[k] for k in p if k.startswith("sar:") or k in ("datetime","platform","gsd")})
print("assets:", list(feats[0]["assets"].keys()))
