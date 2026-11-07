"""Build public/basemap/coast.pmtiles: land, coast and border layers for the DVM basemap.

Sources (see README.md):
  - Baltic box R (lon 9-31, lat 53.5-66), z4-14: OSM ocean polygons from OpenFreeMap tiles (fetch_ofm.py), land = tile - ocean.
  - Everywhere at z0-3, and outside R at z4-6: Natural Earth 10m land + minor islands, NE 10m lakes cut out (z0-6).
  - Borders: NE 10m admin-0 boundary lines (land), z0-6; MapLibre overzooms z6 beyond.
  - z6 tiles also carry `mask` (the box R) so the style can paint water over OpenFreeMap's ocean inside R at z7+,
    where this file's land is the authority; outside R, OpenFreeMap's own coast carries on above z6.

Accuracy: geometry is never smoothed. Each pyramid level simplifies (Douglas-Peucker, topology kept) by TOL_PX of its own
pixel, so the total drift at any zoom stays below 2 * TOL_PX px; islands and holes under 1 px^2 at that zoom are dropped.
Coordinates: Web Mercator in z14 pixels (256 px tiles), y down. Tiles: MVT extent 4096, gzip, Hilbert-ordered PMTiles v3.
"""
import gzip
import json
import math
import os
import sqlite3
import sys
from concurrent.futures import ProcessPoolExecutor

import mapbox_vector_tile as mvt
import shapely
from pmtiles.tile import Compression, TileType, zxy_to_tileid
from pmtiles.writer import write
from shapely import affinity
from shapely.geometry import LineString, MultiLineString, MultiPolygon, Polygon, box, shape
from shapely.ops import linemerge, unary_union

HERE = os.path.dirname(os.path.abspath(__file__))
CACHE = os.path.join(HERE, ".cache")
DB = os.path.join(CACHE, "ofm.sqlite")
OUT = os.path.normpath(os.path.join(HERE, "..", "..", "public", "basemap", "coast.pmtiles"))
NE_URL = "https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/{}.geojson"
NE_FILES = ["ne_10m_land", "ne_10m_minor_islands", "ne_10m_lakes", "ne_10m_admin_0_boundary_lines_land"]

ZMAX = 14
S = 256 * 2 ** ZMAX  # world size in z14 px
EXT = 4096
TOL_PX = 0.125  # per-level simplification; cumulative < 0.25 px
R_LL = (9.0, 53.5, 31.0, 66.0)
MAXLAT = 85.0511287798


def mx(lon): return (lon + 180) / 360 * S
def my(lat):
    lat = max(-MAXLAT, min(MAXLAT, lat))
    return (1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * S


R = box(mx(R_LL[0]), my(R_LL[3]), mx(R_LL[2]), my(R_LL[1]))


def tbox(z, x, y):
    s = S / 2 ** z
    return box(x * s, y * s, (x + 1) * s, (y + 1) * s)


def px(z):
    """One screen px at zoom z, in z14 px units."""
    return 2 ** (ZMAX - z)


# ---------- geometry helpers ----------

def polys(g):
    if g is None or g.is_empty:
        return []
    if isinstance(g, Polygon):
        return [g]
    if isinstance(g, MultiPolygon):
        return list(g.geoms)
    return [p for part in getattr(g, "geoms", []) for p in polys(part)]


def lines(g):
    if g is None or g.is_empty:
        return []
    if isinstance(g, LineString):
        return [g]
    if isinstance(g, MultiLineString):
        return list(g.geoms)
    return [l for part in getattr(g, "geoms", []) for l in lines(part)]


def prune(g, min_area):
    """Drop islands and holes smaller than min_area (1 px^2 at the tile's zoom)."""
    out = []
    for p in polys(g):
        if p.area < min_area:
            continue
        holes = [r for r in p.interiors if Polygon(r).area >= min_area]
        out.append(Polygon(p.exterior, holes))
    return MultiPolygon(out) if out else None


def ring_area(l):
    c = shapely.get_coordinates(l)
    return abs(float((c[:-1, 0] * c[1:, 1] - c[1:, 0] * c[:-1, 1]).sum())) / 2


def prune_lines(ls, min_area):
    """Drop closed coast rings (islands) under min_area and empty pieces."""
    return [l for l in ls if l.length > 0 and not (l.is_closed and ring_area(l) < min_area)]


def simplify_land(g, z):
    if g is None:
        return None
    # Prune by area before simplifying, so an island of >= 1 px^2 that simplification shrinks is still kept;
    # afterwards drop only slivers that collapsed (< 0.05 px^2).
    g = prune(g, px(z) ** 2)
    if g is None:
        return None
    g = shapely.make_valid(g.simplify(TOL_PX * px(z), preserve_topology=True))
    return prune(g, 0.05 * px(z) ** 2)


def simplify_lines(ls, z):
    if not ls:
        return []
    merged = linemerge(MultiLineString(ls)) if len(ls) > 1 else ls[0]
    out = [l.simplify(TOL_PX * px(z), preserve_topology=False) for l in lines(merged)]
    return prune_lines(out, px(z) ** 2)


def clip(g, b):
    if g is None or g.is_empty:
        return None
    c = shapely.clip_by_rect(g, *b.bounds)
    return None if c.is_empty else c


def clip_lines(ls, b):
    out = []
    for l in ls:
        c = shapely.clip_by_rect(l, *b.bounds)
        out += lines(c)
    return out


# ---------- MVT encoding ----------

def to_tile(g, z, x, y):
    s = S / 2 ** z
    k = EXT / s
    return affinity.affine_transform(g, [k, 0, 0, k, -x * s * k, -y * s * k])


def encode(z, x, y, layers):
    """layers: {name: list of shapely geoms in z14 px}. Returns gzipped MVT or None."""
    out = []
    for name, geoms in layers.items():
        geoms = [g for g in geoms if g is not None and not g.is_empty]
        if geoms and all(isinstance(g, LineString) for g in geoms):
            geoms = [MultiLineString(geoms)]  # one feature per tile keeps the tile small
        feats = []
        for g in geoms:
            t = to_tile(g, z, x, y)
            if name in ("land", "mask"):
                # Snap to the MVT integer grid here, keeping the result valid. (Letting the encoder quantise and then
                # make_valid dropped whole land features when snapping created a self-touch: land vanished at z7-9.)
                t = shapely.set_precision(t, 1.0)
                t = MultiPolygon(polys(t)) if not t.is_empty else None
            if t is not None and not t.is_empty:
                feats.append({"geometry": t, "properties": {}})
        if feats:
            out.append({"name": name, "features": feats})
    if not out:
        return None
    raw = mvt.encode(out, default_options={"y_coord_down": True, "extents": EXT})
    return gzip.compress(raw, mtime=0)


FULL = "FULL"


def full_tile_blob():
    # One square of land per tile, shared by every all-land tile (PMTiles dedupes it).
    return encode(0, 0, 0, {"land": [box(0, 0, S, S)]})


# ---------- Baltic pyramid from OFM leaves ----------

_db = None


def kind_of(z, x, y):
    global _db
    if _db is None:
        _db = sqlite3.connect(DB)
    r = _db.execute("select kind, wkb from tiles where z=? and x=? and y=?", (z, x, y)).fetchone()
    return r


def leaf_geom(z, x, y, row):
    """Land and coast lines of one OFM leaf tile, clipped to R. Returns (land, lines) or FULL or None."""
    b = tbox(z, x, y)
    inR = R.contains(b)
    kind, wkb = row
    if kind == "W":
        return None
    if kind == "L":
        if inR:
            return FULL
        land = clip(R, b)
        return (MultiPolygon(polys(land)), []) if land is not None else None
    ocean = MultiPolygon(polys(to_global(shapely.from_wkb(wkb), z, x, y)))
    land = b.difference(ocean)
    coast = lines(ocean.boundary.difference(b.exterior.buffer(1e-3)))
    if not inR:
        land = land.intersection(R)
        coast = lines(MultiLineString(coast).intersection(R)) if coast else []
    land = prune(shapely.make_valid(land), 1e-6)
    return (land, coast) if land is not None or coast else None


def to_global(g, z, x, y):
    s = S / 2 ** z
    k = s / EXT
    return affinity.affine_transform(g, [k, 0, 0, k, x * s, y * s])


def subtree(z, x, y, tiles):
    """Recursively build node (z,x,y) from the OFM cache. Appends (z,x,y,blob|FULL) to tiles; returns node geom."""
    b = tbox(z, x, y)
    if not R.intersects(b) or R.touches(b):
        return None
    row = kind_of(z, x, y)
    children = None
    if z < ZMAX and kind_of(z + 1, 2 * x, 2 * y) is not None:
        children = [subtree(z + 1, 2 * x + dx, 2 * y + dy, tiles) for dx in (0, 1) for dy in (0, 1)]
    elif row is None:
        raise RuntimeError(f"no OFM data for {z}/{x}/{y}; rerun fetch_ofm.py")
    elif row[0] == "L" and z < ZMAX:
        # land leaf above z14: every descendant is all land (or land clipped to R)
        children = [subtree_land(z + 1, 2 * x + dx, 2 * y + dy, tiles) for dx in (0, 1) for dy in (0, 1)]
    if children is None:
        node = leaf_geom(z, x, y, row)
    elif all(c == FULL for c in children):
        node = FULL
    elif all(c is None for c in children):
        node = None
    else:
        land, coast = [], []
        for i, c in enumerate(children):
            if c == FULL:
                land.append(tbox(z + 1, 2 * x + i // 2, 2 * y + i % 2))
            elif c is not None:
                if c[0] is not None:
                    land.append(c[0])
                coast += c[1]
        node = (simplify_land(unary_union(land) if land else None, z), simplify_lines(coast, z))
    emit(z, x, y, node, tiles)
    return node


def subtree_land(z, x, y, tiles):
    b = tbox(z, x, y)
    if not R.intersects(b) or R.touches(b):
        return None
    if R.contains(b):
        node = FULL
        # descendants are all FULL too; record them without geometry work
        emit_full_tree(z, x, y, tiles)
        return node
    children = [subtree_land(z + 1, 2 * x + dx, 2 * y + dy, tiles) for dx in (0, 1) for dy in (0, 1)] if z < ZMAX else None
    land = clip(R, b)
    node = (MultiPolygon(polys(land)), []) if land is not None else None
    emit(z, x, y, node, tiles)
    return node


def emit_full_tree(z, x, y, tiles):
    tiles.append((z, x, y, FULL))
    if z < ZMAX:
        for dx in (0, 1):
            for dy in (0, 1):
                emit_full_tree(z + 1, 2 * x + dx, 2 * y + dy, tiles)


def emit(z, x, y, node, tiles):
    if node is None:
        return
    if node == FULL:
        tiles.append((z, x, y, FULL))
        return
    land, coast = node
    blob = encode(z, x, y, {"land": [land] if land is not None else [], "coast": coast})
    if blob:
        tiles.append((z, x, y, blob))


def node_wkb(node):
    if node is None or node == FULL:
        return node
    land, coast = node
    return (land.wkb if land is not None else None, [l.wkb for l in coast])


def node_from_wkb(n):
    if n is None or n == FULL:
        return n
    return (shapely.from_wkb(n[0]) if n[0] is not None else None, [shapely.from_wkb(w) for w in n[1]])


def job_z10(zxy):
    tiles = []
    node = subtree(*zxy, tiles)
    return zxy, node_wkb(node), tiles


def combine(z, x, y, kids, tiles):
    """Build node (z,x,y) from its four child nodes (already simplified at z+1)."""
    if all(c == FULL for c in kids):
        node = FULL
    elif all(c is None for c in kids):
        node = None
    else:
        land, coast = [], []
        for i, c in enumerate(kids):
            if c == FULL:
                land.append(tbox(z + 1, 2 * x + i // 2, 2 * y + i % 2))
            elif c is not None:
                if c[0] is not None:
                    land.append(c[0])
                coast += c[1]
        node = (simplify_land(unary_union(land) if land else None, z), simplify_lines(coast, z))
    return node


def job_up(args):
    """From z10 nodes under a z7 tile, build z9..z7. Returns z7 node and tiles."""
    (z0, x0, y0), z10nodes = args
    nodes = {k: node_from_wkb(v) for k, v in z10nodes.items()}
    tiles = []

    def get(z, x, y):
        if z == 10:
            return nodes.get((x, y))
        kids = [get(z + 1, 2 * x + dx, 2 * y + dy) for dx in (0, 1) for dy in (0, 1)]
        node = combine(z, x, y, kids, tiles)
        emit(z, x, y, node, tiles)
        return node

    return (x0, y0), node_wkb(get(z0, x0, y0)), tiles


def tile_range(b, z):
    s = S / 2 ** z
    x0, y0, x1, y1 = b.bounds
    return range(int(x0 // s), int(math.ceil(x1 / s))), range(int(y0 // s), int(math.ceil(y1 / s)))


# ---------- Natural Earth world ----------

def load_ne():
    import httpx
    d = os.path.join(CACHE, "ne")
    os.makedirs(d, exist_ok=True)
    out = {}
    for name in NE_FILES:
        p = os.path.join(d, name + ".geojson")
        if not os.path.exists(p):
            print("downloading", name, flush=True)
            r = httpx.get(NE_URL.format(name), timeout=120, follow_redirects=True)
            r.raise_for_status()
            open(p, "wb").write(r.content)
        out[name] = [shape(f["geometry"]) for f in json.load(open(p, encoding="utf-8"))["features"] if f["geometry"]]
    return out


def project(g):
    return shapely.transform(g, lambda c: [[mx(lon), my(lat)] for lon, lat in c])


def world(osm_low):
    """z0-6 tiles. osm_low: {(z,x,y): node} for z4..6 inside R."""
    ne = load_ne()
    land = unary_union([shapely.make_valid(project(g)) for g in ne["ne_10m_land"] + ne["ne_10m_minor_islands"]])
    lakes = unary_union([shapely.make_valid(project(g)) for g in ne["ne_10m_lakes"]])
    land = shapely.make_valid(land.difference(lakes))
    coast = lines(land.boundary)
    lake_shore = lines(lakes.boundary)
    border = [project(g) for g in ne["ne_10m_admin_0_boundary_lines_land"]]
    land_out = shapely.make_valid(land.difference(R))
    coast_out = lines(MultiLineString(coast).difference(R))
    lake_shore_in = lines(MultiLineString(lake_shore).intersection(R))
    print(f"NE: land {shapely.get_num_coordinates(land)} vertices, borders {len(border)} lines", flush=True)
    tiles = []

    def rec(z, x, y, g_land, g_coast, g_border, g_lout, g_cout):
        b = tbox(z, x, y)
        g_land, g_lout = clip(g_land, b), clip(g_lout, b)
        g_coast, g_border, g_cout = clip_lines(g_coast, b), clip_lines(g_border, b), clip_lines(g_cout, b)
        osm = osm_low.get((z, x, y)) if z >= 4 else None
        if g_land is None and not g_coast and not g_border and osm is None:
            return
        if z < 4:
            l, c = simplify_land(g_land, z), simplify_lines(g_coast, z)
        else:
            l = simplify_land(g_lout, z)
            c = simplify_lines(g_cout + clip_lines(lake_shore_in, b), z)
            if osm == FULL:
                osm = (clip(R, b), [])
            if osm is not None:
                ol = osm[0].difference(lakes) if osm[0] is not None else None
                l = unary_union([g for g in (l, ol) if g is not None]) if (l is not None or ol is not None) else None
                c = c + osm[1]
        layers = {"land": [l] if l is not None else [], "coast": c,
                  "border": g_border if z == 6 else simplify_lines(g_border, z)}
        if z == 6:  # overzoomed by the style at z7+
            m = clip(R, b)
            layers["mask"] = [m] if m is not None else []
        blob = encode(z, x, y, layers)
        if blob:
            tiles.append((z, x, y, blob))
        if z < 6:
            for dx in (0, 1):
                for dy in (0, 1):
                    rec(z + 1, 2 * x + dx, 2 * y + dy, g_land, g_coast, g_border, g_lout, g_cout)

    rec(0, 0, 0, land, coast, border, land_out, coast_out)
    return tiles


# ---------- main ----------

def main():
    if not os.path.exists(DB):
        sys.exit("no OFM cache; run fetch_ofm.py first")
    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    xs, ys = tile_range(R, 10)
    roots = [(10, x, y) for x in xs for y in ys if R.intersects(tbox(10, x, y)) and not R.touches(tbox(10, x, y))]
    all_tiles = []
    z10 = {}
    with ProcessPoolExecutor(int(os.environ.get("BASEMAP_WORKERS", "14"))) as pool:
        for i, (zxy, node, tiles) in enumerate(pool.map(job_z10, roots, chunksize=4)):
            z10[(zxy[1], zxy[2])] = node
            all_tiles += tiles
            if i % 500 == 0:
                print(f"z10-14: {i}/{len(roots)} roots, {len(all_tiles)} tiles", flush=True)
        xs7, ys7 = tile_range(R, 7)
        jobs = []
        for x7 in xs7:
            for y7 in ys7:
                sub = {(x, y): v for (x, y), v in z10.items() if x >> 3 == x7 and y >> 3 == y7}
                if sub:
                    jobs.append(((7, x7, y7), sub))
        z7 = {}
        for (x7, y7), node, tiles in pool.map(job_up, jobs):
            z7[(x7, y7)] = node_from_wkb(node)
            all_tiles += tiles
    print(f"z7-9 done, {len(all_tiles)} tiles", flush=True)
    # z6..z4 inside R, combined from z7 nodes (kept as geometry for world())
    osm_low = {}
    level = z7
    for z in (6, 5, 4):
        nxt = {}
        for x, y in {(x >> 1, y >> 1) for x, y in level}:
            kids = [level.get((2 * x + dx, 2 * y + dy)) for dx in (0, 1) for dy in (0, 1)]
            nxt[(x, y)] = combine(z, x, y, kids, [])
            osm_low[(z, x, y)] = nxt[(x, y)]
        level = nxt
    all_tiles += world(osm_low)
    print(f"world done, {len(all_tiles)} tiles; writing", flush=True)

    full = full_tile_blob()
    entries = sorted(((zxy_to_tileid(z, x, y), full if b == FULL else b, z) for z, x, y, b in all_tiles), key=lambda e: e[0])
    with write(OUT) as w:
        for tid, blob, _ in entries:
            w.write_tile(tid, blob)
        header = {
            "tile_type": TileType.MVT, "tile_compression": Compression.GZIP,
            "min_zoom": 0, "max_zoom": ZMAX,
            "min_lon_e7": -1800000000, "min_lat_e7": -850511287, "max_lon_e7": 1800000000, "max_lat_e7": 850511287,
            "center_zoom": 5, "center_lon_e7": 200000000, "center_lat_e7": 597000000,
        }
        meta = {
            "name": "dvm-coast",
            "attribution": "© OpenStreetMap contributors (via OpenFreeMap), Natural Earth",
            "vector_layers": [
                {"id": n, "fields": {}, "minzoom": 0, "maxzoom": ZMAX if n in ("land", "coast") else 6}
                for n in ("land", "coast", "border", "mask")
            ],
        }
        w.finalize(header, meta)
    print(f"wrote {OUT}: {os.path.getsize(OUT) / 1e6:.1f} MB, {len(entries)} tiles", flush=True)


if __name__ == "__main__":
    main()
