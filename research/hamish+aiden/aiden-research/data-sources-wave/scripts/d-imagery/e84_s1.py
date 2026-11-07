import json, urllib.request, urllib.error, time
base="https://earth-search.aws.element84.com/v1/search"
body={"collections":["sentinel-1-grd"],"bbox":[18.5,57.0,19.5,58.0],
      "datetime":"2026-11-01T00:00:00Z/2026-11-07T00:00:00Z","limit":3}
req=urllib.request.Request(base, data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
r=json.load(urllib.request.urlopen(req, timeout=90))
print("items", len(r["features"]))
it=r["features"][0]; p=it["properties"]
print(it["id"], p.get("datetime"), p.get("platform"), p.get("sar:instrument_mode"), p.get("gsd"))
print("assets:", list(it["assets"]))
for k,a in it["assets"].items():
    if k in ("vv","vh"):
        print(k, a["href"][:150])
href=it["assets"]["vv"]["href"]
t0=time.time()
try:
    rq=urllib.request.Request(href, headers={"Range":"bytes=0-200000"})
    rr=urllib.request.urlopen(rq, timeout=180); d=rr.read()
    print("GET", rr.status, len(d), "bytes", round(time.time()-t0,2),"s magic", d[:4])
except urllib.error.HTTPError as e:
    print("HTTPError", e.code, e.read()[:300])
