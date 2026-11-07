#!/usr/bin/env python3
"""List Sentinel-1 GRD acquisitions over Danish waters (2026-10-20 .. 2026-11-07).

No account: Microsoft Planetary Computer STAC search endpoint is public.
Purpose: tell t-match which date/time has both a Sentinel-1 pass and Danish AIS.
"""
import json
import urllib.request
from datetime import datetime, timezone

STAC = "https://planetarycomputer.microsoft.com/api/stac/v1/search"

# Danish straits / Kattegat / western Baltic: lon 9..14, lat 54..58
AOI = {"type": "Polygon", "coordinates": [[
    [9.0, 54.0], [14.0, 54.0], [14.0, 58.0], [9.0, 58.0], [9.0, 54.0]]]}

body = {
    "collections": ["sentinel-1-grd"],
    "intersects": AOI,
    "datetime": "2026-10-20T00:00:00Z/2026-11-08T00:00:00Z",
    "limit": 300,
}
req = urllib.request.Request(
    STAC, data=json.dumps(body).encode(), method="POST",
    headers={"Content-Type": "application/json", "Accept": "application/geo+json"})
with urllib.request.urlopen(req, timeout=120) as r:
    d = json.load(r)

print("matched items:", len(d.get("features", [])))
rows = []
for f in d["features"]:
    p = f["properties"]
    rows.append((p["datetime"], f["id"], p.get("sar:instrument_mode"),
                 p.get("sar:polarizations"), p.get("sat:orbit_state")))
rows.sort()
for dt, i, mode, pol, orb in rows:
    print(dt, i, mode, pol, orb)
