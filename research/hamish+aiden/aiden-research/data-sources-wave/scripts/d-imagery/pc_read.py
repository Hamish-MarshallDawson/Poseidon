import json, urllib.request, time, datetime as dt
base="https://planetarycomputer.microsoft.com/api/stac/v1/search"
body={"collections":["sentinel-1-grd"],"bbox":[18.5,57.0,19.5,58.0],
      "datetime":"2026-11-01T00:00:00Z/2026-11-07T00:00:00Z","limit":5}
req=urllib.request.Request(base, data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
it=json.load(urllib.request.urlopen(req, timeout=90))["features"][0]
print("item", it["id"], it["properties"]["datetime"])
for k in ("vv","vh"):
    print(k, it["assets"][k]["href"][:160])
t0=time.time()
u=it["assets"]["vv"]["href"]
rq=urllib.request.Request(u, headers={"Range":"bytes=0-200000"})
r=urllib.request.urlopen(rq, timeout=120)
d=r.read(); print("status",r.status,"bytes",len(d),"in",round(time.time()-t0,2),"s")
print("first bytes magic", d[:4])
