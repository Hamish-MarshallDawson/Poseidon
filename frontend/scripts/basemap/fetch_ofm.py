"""Download OSM ocean polygons for the Baltic box from OpenFreeMap vector tiles (water layer, class=ocean).

Why OpenFreeMap: osmdata.openstreetmap.de and Geofabrik time out from the build machine (7 Nov 2026). OpenFreeMap's
planet tiles carry the same OSM water polygons; at z14 they are unsimplified (extent 4096, ~0.06 px at z14).

Quadtree: every z10 tile in the box is fetched; land-only tiles stop at z10, ocean-only tiles at z11 (so open-sea islets
of >= 1 px at z11 are still found), mixed tiles descend to z14. Each tile is stored in .cache/ofm.sqlite as
kind L (no ocean), W (all ocean) or M (WKB of the ocean clipped to the tile, tile units 0..4096, y down).
Resumable: tiles already in the cache are not fetched again.
"""
import math
import os
import sqlite3
import sys
from concurrent.futures import ProcessPoolExecutor

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")
DB = os.path.join(CACHE, "ofm.sqlite")
TILEJSON = "https://tiles.openfreemap.org/planet"
UA = {"User-Agent": "dvm-coast-build/1.0 (hackathon basemap build)"}
# Baltic box lon 9-31, lat 53.5-66, plus the 0.5 degree data margin from the Figma build note.
FETCH_BOX = (8.5, 53.0, 31.5, 66.5)
EXT = 4096
Z_START, Z_LAND_STOP, Z_WATER_STOP, Z_MAX = 10, 10, 11, 14


def tile_range(box, z):
    n = 2 ** z
    def tx(lon): return int((lon + 180) / 360 * n)
    def ty(lat): return int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)
    return range(tx(box[0]), tx(box[2]) + 1), range(ty(box[3]), ty(box[1]) + 1)


_client = None
_url = None


def _init(url):
    global _client, _url
    import httpx
    _client = httpx.Client(headers=UA, timeout=60, http2=False)
    _url = url


def classify(pbf):
    """Ocean in one tile -> ('L'|'W'|'M', wkb or None)."""
    from mapbox_vector_tile.decoder import TileData
    from shapely.geometry import box, shape
    from shapely.ops import unary_union
    td = TileData(pbf, default_options={"y_coord_down": True})
    keep = [l for l in td.tile.layers if l.name == "water"]
    del td.tile.layers[:]
    td.tile.layers.extend(keep)
    feats = td.get_message().get("water", {}).get("features", [])
    geoms = [shape(f["geometry"]) for f in feats if f["properties"].get("class") == "ocean"]
    t = box(0, 0, EXT, EXT)
    ocean = unary_union([g.buffer(0) if not g.is_valid else g for g in geoms]).intersection(t) if geoms else None
    if ocean is None or ocean.area == 0:
        return "L", None
    if ocean.area >= EXT * EXT * (1 - 1e-9):
        return "W", None
    return "M", ocean.wkb


def work(zxy):
    z, x, y = zxy
    for attempt in range(5):
        try:
            r = _client.get(_url.format(z=z, x=x, y=y))
            if r.status_code == 204 or (r.status_code == 200 and not r.content):
                return zxy, "L", None, 0
            r.raise_for_status()
            kind, wkb = classify(r.content)
            return zxy, kind, wkb, len(r.content)
        except Exception as e:  # network blips: retry, then report
            err = e
    return zxy, "E", repr(err).encode(), 0


def main():
    import httpx
    os.makedirs(CACHE, exist_ok=True)
    url = httpx.get(TILEJSON, headers=UA, timeout=30).json()["tiles"][0]
    con = sqlite3.connect(DB)
    con.execute("create table if not exists tiles (z int, x int, y int, kind text, wkb blob, primary key (z,x,y))")
    con.execute("create table if not exists meta (k text primary key, v text)")
    con.execute("insert or replace into meta values ('source', ?)", (url,))
    con.commit()
    xs, ys = tile_range(FETCH_BOX, Z_START)
    level = [(Z_START, x, y) for x in xs for y in ys]
    with ProcessPoolExecutor(32, initializer=_init, initargs=(url,)) as pool:
        for z in range(Z_START, Z_MAX + 1):
            have = {(x, y): k for x, y, k in con.execute("select x,y,kind from tiles where z=? and kind!='E'", (z,))}
            todo = [t for t in level if (t[1], t[2]) not in have]
            print(f"z{z}: {len(level)} tiles, {len(todo)} to fetch", flush=True)
            got, nbytes = 0, 0
            for zxy, kind, wkb, nb in pool.map(work, todo, chunksize=8):
                con.execute("insert or replace into tiles values (?,?,?,?,?)", (*zxy, kind, wkb))
                have[(zxy[1], zxy[2])] = kind
                got += 1
                nbytes += nb
                if got % 2000 == 0:
                    con.commit()
                    print(f"  {got}/{len(todo)}  {nbytes / 1e6:.0f} MB", flush=True)
            con.commit()
            counts = {k: sum(1 for v in have.values() if v == k) for k in "LWME"}
            print(f"z{z} done: {counts}, {nbytes / 1e6:.0f} MB downloaded", flush=True)
            if counts["E"]:
                sys.exit(f"{counts['E']} tiles failed at z{z}; rerun to retry")
            if z == Z_MAX:
                break
            nxt = []
            for (x, y), k in have.items():
                if k == "M" or (k == "W" and z < Z_WATER_STOP) or (k == "L" and z < Z_LAND_STOP):
                    nxt += [(z + 1, 2 * x + dx, 2 * y + dy) for dx in (0, 1) for dy in (0, 1)]
            level = nxt


if __name__ == "__main__":
    main()
