import json,urllib.request
def search(bbox, dt, limit=30):
    req=urllib.request.Request("https://stac.dataspace.copernicus.eu/v1/search",
        data=json.dumps({"collections":["sentinel-1-grd"],"bbox":bbox,"datetime":dt,"limit":limit}).encode(),
        headers={"Content-Type":"application/json"})
    return json.load(urllib.request.urlopen(req, timeout=60))
for day in ["2026-11-07","2026-11-06","2026-11-05"]:
    r=search([10.0,54.5,13.5,57.2], f"{day}T00:00:00Z/{day}T23:59:59Z")
    print(day, len(r["features"]))
    for f in r["features"]:
        print("   ", f["id"])
