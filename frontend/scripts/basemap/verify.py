"""Vertex error check for coast.pmtiles: tiled land vs the unsimplified source, in screen px at the tile's zoom.

For a tile (default: three tiles over the Helsinki skerries at z8, z11, z14) it rebuilds the source land from the
OpenFreeMap leaf tiles in the cache (no simplification), decodes the land layer from coast.pmtiles, and reports:
  tiled->source  max distance from any tiled boundary point to the source boundary (the vertex error; target <= 1 px),
                 raw and "as rendered" (after a 0.1 px closing that merges sub-pixel seams between child-tile pieces)
  source->tiled  the same the other way (includes islands under 1 px^2 that are dropped on purpose)
  islands        polygon count in source vs tile, and how many source islands >= 1 px^2 are missing from the tile
Tile-edge segments are excluded (clipping, not error).
Run: .venv/bin/python verify.py [z/x/y ...]     or  verify.py --stats   (tile count and size per zoom, largest tile)
"""
import gzip
import math
import sys

import mapbox_vector_tile as mvt
import shapely
from pmtiles.reader import MmapSource, Reader
from shapely.geometry import shape
from shapely.ops import unary_union

import build as B


def zxy_at(lon, lat, z):
    n = 2 ** z
    return z, int((lon + 180) / 360 * n), int((1 - math.asinh(math.tan(math.radians(lat))) / math.pi) / 2 * n)


def source_land(z, x, y):
    parts = []

    def rec(z, x, y):
        row = B.kind_of(z, x, y)
        if z < 10 or (z < B.ZMAX and B.kind_of(z + 1, 2 * x, 2 * y) is not None):   # the cache starts at z10
            for dx in (0, 1):
                for dy in (0, 1):
                    rec(z + 1, 2 * x + dx, 2 * y + dy)
            return
        if row is None:
            return
        if row[0] == "L":
            parts.append(B.tbox(z, x, y).intersection(B.R))
            return
        g = B.leaf_geom(z, x, y, row)
        if g == B.FULL:
            parts.append(B.tbox(z, x, y))
        elif g is not None and g[0] is not None:
            parts.append(g[0])

    rec(z, x, y)
    return shapely.make_valid(unary_union(parts)) if parts else None


def tiled_land(reader, z, x, y):
    blob = reader.get(z, x, y)
    if blob is None:
        return None
    d = mvt.decode(gzip.decompress(blob), default_options={"y_coord_down": True})
    feats = d.get("land", {}).get("features", [])
    if not feats:
        return None
    g = unary_union([shapely.make_valid(shape(f["geometry"])) for f in feats])
    return B.to_global(g, z, x, y)


def check(reader, z, x, y):
    tb = B.tbox(z, x, y)
    src, til = source_land(z, x, y), tiled_land(reader, z, x, y)
    src = src.intersection(tb) if src is not None else None
    edge = tb.exterior.buffer(B.px(z) * 0.25)          # clip edges, snapped to the 1/16 px MVT grid
    def bnd(g): return None if g is None else g.boundary.difference(edge)
    bs, bt = bnd(src), bnd(til)
    p = B.px(z)
    if bs is None or bt is None or bs.is_empty or bt.is_empty:
        print(f"{z}/{x}/{y}: source {'empty' if bs is None or bs.is_empty else 'has coast'}, tile {'empty' if bt is None or bt.is_empty else 'has coast'}")
        return
    dens = p * 0.25
    pts_t = shapely.points(shapely.get_coordinates(shapely.segmentize(bt, dens)))
    pts_s = shapely.points(shapely.get_coordinates(shapely.segmentize(bs, dens)))
    t2s = float(shapely.distance(pts_t, bs).max()) / p
    # As rendered: a 0.1 px closing merges sub-pixel seam cracks between pieces simplified in neighbouring child
    # tiles (they share an edge to ~0.06 px and draw as solid land), so only real coastline displacement remains.
    closed = til.buffer(0.1 * p, join_style="mitre").buffer(-0.1 * p, join_style="mitre")
    bc = bnd(closed)
    pts_c = shapely.points(shapely.get_coordinates(shapely.segmentize(bc, dens)))
    t2s_r = float(shapely.distance(pts_c, bs).max()) / p
    s2t = float(shapely.distance(pts_s, bt).max()) / p
    big = [q for q in B.polys(src) if q.area >= p * p]
    missing = sum(1 for q in big if not til.intersects(q.representative_point()))
    print(f"{z}/{x}/{y}: tiled->source max {t2s:.3f} px raw, {t2s_r:.3f} px as rendered; source->tiled max {s2t:.3f} px; "
          f"polygons source {len(B.polys(src))} (>=1 px^2: {len(big)}), tile {len(B.polys(til))}; "
          f">=1 px^2 islands missing from tile: {missing}; tile vertices {shapely.get_num_coordinates(til)}")


def stats(reader):
    """Tile count and bytes per zoom, the largest tile, and the distinct blobs (identical tiles are stored once)."""
    from pmtiles.reader import all_tiles
    per, big, blobs = {}, (0, None), set()
    with open(B.OUT, "rb") as f:
        for (z, x, y), data in all_tiles(MmapSource(f)):
            n, b = per.get(z, (0, 0))
            per[z] = (n + 1, b + len(data))
            blobs.add(hash(data))
            if len(data) > big[0]:
                big = (len(data), (z, x, y))
    for z in sorted(per):
        print(f"z{z}: {per[z][0]} tiles, {per[z][1] / 1e6:.1f} MB (before dedupe)")
    print(f"largest tile: {big[0]} bytes at {big[1][0]}/{big[1][1]}/{big[1][2]}; distinct tile blobs: {len(blobs)}")


def main():
    with open(B.OUT, "rb") as f:
        reader = Reader(MmapSource(f))
        if sys.argv[1:] == ["--stats"]:
            return stats(reader)
        tiles = [tuple(map(int, a.split("/"))) for a in sys.argv[1:]] or [zxy_at(24.95, 60.12, 8), zxy_at(24.95, 60.12, 11), zxy_at(25.03, 60.135, 14)]
        for t in tiles:
            check(reader, *t)


if __name__ == "__main__":
    main()
