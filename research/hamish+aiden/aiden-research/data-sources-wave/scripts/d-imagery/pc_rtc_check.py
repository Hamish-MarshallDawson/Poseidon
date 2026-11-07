import json, urllib.request, datetime as dt
base="https://planetarycomputer.microsoft.com/api/stac/v1/search"
def post(b):
    req=urllib.request.Request(base, data=json.dumps(b).encode(), headers={"Content-Type":"application/json"})
    return json.load(urllib.request.urlopen(req, timeout=120))
end=dt.datetime(2026,11,7,tzinfo=dt.timezone.utc); start=end-dt.timedelta(days=30)
for coll in ("sentinel-1-rtc",):
  for name,box in {"Gotland":[18.5,57.0,19.5,58.0],"Hormuz":[56.0,26.2,57.0,27.0]}.items():
    r=post({"collections":[coll],"bbox":box,"datetime":f"{start:%Y-%m-%dT%H:%M:%SZ}/{end:%Y-%m-%dT%H:%M:%SZ}","limit":500})
    f=r["features"]
    print(coll,name,"scenes",len(f), sorted({x["properties"].get("platform") for x in f}))
    if f:
        p=f[0]["properties"]; print("  props:", {k:p[k] for k in p if k.startswith("sar:")})
        print("  assets:", list(f[0]["assets"])[:8])
