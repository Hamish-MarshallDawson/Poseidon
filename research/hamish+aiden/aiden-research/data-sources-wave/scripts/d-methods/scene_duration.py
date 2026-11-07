"""How long does one Sentinel-1 GRD acquisition take, and how far does the
image time vary across a scene? Earth Search STAC, no account."""

import json
import urllib.request
from datetime import datetime

BODY = {
    "collections": ["sentinel-1-grd"],
    "bbox": [16.0, 59.0, 22.0, 61.0],       # Gulf of Finland
    "datetime": "2026-10-25T00:00:00Z/2026-11-07T23:59:59Z",
    "limit": 5,
    "query": {"sar:instrument_mode": {"eq": "IW"}},
}

req = urllib.request.Request(
    "https://earth-search.aws.element84.com/v1/search",
    data=json.dumps(BODY).encode(),
    headers={"Content-Type": "application/json"},
)
with urllib.request.urlopen(req, timeout=60) as r:
    j = json.load(r)

print("items:", len(j["features"]))
for f in j["features"]:
    p = f["properties"]
    def parse(x):
        return datetime.strptime(x.replace("Z", "")[:19], "%Y-%m-%dT%H:%M:%S")
    s = parse(p["start_datetime"])
    e = parse(p["end_datetime"])
    print(f["id"])
    print("   mode %s  platform %s  start %s  stop %s  duration %.0f s"
          % (p.get("sar:instrument_mode"), p.get("platform"),
             p["start_datetime"], p["end_datetime"], (e - s).total_seconds()))
    print("   assets:", ", ".join(sorted(f["assets"])))
