import json, urllib.request, time
base="https://planetarycomputer.microsoft.com/api/stac/v1/search"
body={"collections":["sentinel-1-grd"],"bbox":[18.5,57.0,19.5,58.0],
      "datetime":"2026-11-01T00:00:00Z/2026-11-07T00:00:00Z","limit":3}
req=urllib.request.Request(base, data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
it=json.load(urllib.request.urlopen(req, timeout=90))["features"][0]
print("item", it["id"], it["properties"]["datetime"], it["properties"]["platform"])
href=it["assets"]["vv"]["href"]
print("href", href[:200])
tok=json.load(urllib.request.urlopen("https://planetarycomputer.microsoft.com/api/sas/v1/token/sentinel1euwest?collection=sentinel-1-grd", timeout=60))
print("sas keys", list(tok)[:5], "token len", len(tok.get("token","")))
signed = href.split("?")[0] + "?" + tok["token"]
t0=time.time()
rq=urllib.request.Request(signed, headers={"Range":"bytes=0-300000"})
r=urllib.request.urlopen(rq, timeout=180)
d=r.read()
print("GET ok", r.status, len(d), "bytes in", round(time.time()-t0,2), "s; magic", d[:4])
open("/tmp/d-imagery_s1_tile_head.tif","wb").write(d)
