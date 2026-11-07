#!/usr/bin/env python3
"""Inventory of Sentinel-1 GRD passes over three regions + publication delay.

Route: Element84 Earth Search STAC (no account) -> rewrite s3://sentinel-s1-l1c/... to
https://sentinel-s1-l1c.s3.amazonaws.com/... then HTTP HEAD for Last-Modified (= when the
COG we would read appeared in the catalogue we can reach).
"""
import json, sys, datetime as dt, urllib.request, concurrent.futures as cf

STAC = "https://earth-search.aws.element84.com/v1/search"

REGIONS = {
    # name: (bbox W,S,E,N, representative sea point lon,lat, note)
    "hormuz":      (56.00, 26.20, 57.30, 27.20, 56.45, 26.55, "Strait of Hormuz, inbound/outbound lanes"),
    "gulf_oman":   (57.30, 24.30, 58.60, 25.40, 58.20, 24.90, "Gulf of Oman, outside the strait"),
    "malacca":     (99.00,  3.00, 100.60, 4.60, 99.70,  3.90, "Malacca Strait, off Port Klang/One Fathom Bank"),
    "natuna":      (105.00, 2.50, 106.50, 4.00, 105.80, 3.30, "North Natuna Sea (Indonesian EEZ / South China Sea edge)"),
    "red_sea":     (41.00, 13.00, 42.50, 15.00, 41.70, 13.90, "Bab el-Mandeb approaches"),
}

def post(url, body):
    req = urllib.request.Request(url, data=json.dumps(body).encode(),
                                 headers={"Content-Type": "application/json"})
    return json.load(urllib.request.urlopen(req, timeout=90))

def s3_to_https(href):
    if href.startswith("s3://sentinel-s1-l1c/"):
        return "https://sentinel-s1-l1c.s3.amazonaws.com/" + href[len("s3://sentinel-s1-l1c/"):]
    return href

def head_lastmod(url):
    try:
        req = urllib.request.Request(url, method="HEAD")
        with urllib.request.urlopen(req, timeout=60) as r:
            lm = r.headers.get("Last-Modified")
            cl = r.headers.get("Content-Length")
        if not lm:
            return None, cl
        when = dt.datetime.strptime(lm, "%a, %d %b %Y %H:%M:%S %Z").replace(tzinfo=dt.timezone.utc)
        return when, cl
    except Exception as e:
        return ("ERR:" + str(e)[:80]), None

def point_in_geom(lon, lat, geom):
    # ray casting against the item footprint (lon/lat polygon or multipolygon)
    def in_ring(pt, ring):
        x, y = pt; inside = False
        for i in range(len(ring) - 1):
            x1, y1 = ring[i][0], ring[i][1]
            x2, y2 = ring[i + 1][0], ring[i + 1][1]
            if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1 + 0.0) + x1:
                inside = not inside
        return inside
    g = geom or {}
    polys = g.get("coordinates", [])
    if g.get("type") == "Polygon":
        polys = [polys]
    for poly in polys:
        if poly and in_ring((lon, lat), poly[0]):
            return True
    return False

def do_region(name, start, end):
    w, s, e, n, plon, plat, note = REGIONS[name]
    body = {"collections": ["sentinel-1-grd"], "bbox": [w, s, e, n],
            "datetime": f"{start}T00:00:00Z/{end}T23:59:59Z", "limit": 400}
    r = post(STAC, body)
    feats = r["features"]
    items = []
    for f in feats:
        p = f["properties"]
        items.append({
            "id": f["id"],
            "dt": p["datetime"],
            "platform": p.get("platform"),
            "orbit": p.get("sat:orbit_state"),
            "rel_orbit": p.get("sat:relative_orbit"),
            "mode": p.get("sar:instrument_mode"),
            "point_inside": point_in_geom(plon, plat, f.get("geometry")),
            "vv": s3_to_https(f["assets"]["vv"]["href"]),
            "bbox": f["bbox"],
        })
    items.sort(key=lambda x: x["dt"])
    print(f"## {name}: {len(feats)} GRD items intersect bbox, "
          f"{sum(1 for i in items if i['point_inside'])} contain the sea point", flush=True)
    with cf.ThreadPoolExecutor(8) as ex:
        for it, (lm, cl) in zip(items, ex.map(lambda x: head_lastmod(x["vv"]), items)):
            it["published"] = lm.isoformat() if isinstance(lm, dt.datetime) else lm
            it["bytes"] = cl
            if isinstance(lm, dt.datetime):
                t = dt.datetime.fromisoformat(it["dt"].replace("Z", "+00:00"))
                it["delay_h"] = round((lm - t).total_seconds() / 3600.0, 2)
    return {"region": name, "note": note, "bbox": [w, s, e, n], "point": [plon, plat],
            "window": [start, end], "count": len(feats), "items": items}

if __name__ == "__main__":
    start = sys.argv[2] if len(sys.argv) > 2 else "2026-10-09"
    end = sys.argv[3] if len(sys.argv) > 3 else "2026-11-07"
    only = sys.argv[4].split(",") if len(sys.argv) > 4 else list(REGIONS)
    out = {}
    for name in only:
        out[name] = do_region(name, start, end)
    p = sys.argv[1]
    json.dump(out, open(p, "w"), indent=1)
    print("wrote", p)
