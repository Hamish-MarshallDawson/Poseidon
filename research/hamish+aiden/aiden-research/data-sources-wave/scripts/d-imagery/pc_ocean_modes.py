import json, urllib.request, datetime as dt
from collections import Counter
base="https://planetarycomputer.microsoft.com/api/stac/v1/search"
end=dt.datetime(2026,11,7,tzinfo=dt.timezone.utc); start=end-dt.timedelta(days=7)
big=[20,-25,60,-5]   # Indian Ocean SW, 40x20 deg
body={"collections":["sentinel-1-grd"],"bbox":big,"datetime":f"{start:%Y-%m-%dT%H:%M:%SZ}/{end:%Y-%m-%dT%H:%M:%SZ}","limit":20}
req=urllib.request.Request(base, data=json.dumps(body).encode(), headers={"Content-Type":"application/json"})
r=json.load(urllib.request.urlopen(req, timeout=120))
print("items in 40x20deg Indian Ocean box, 7 days:", len(r["features"]))
print(Counter((f["properties"].get("sar:instrument_mode"), f["properties"].get("platform")) for f in r["features"]))
for f in r["features"][:3]:
    print(f["properties"]["datetime"], f["properties"]["sar:instrument_mode"], [round(x,1) for x in f["bbox"]])
