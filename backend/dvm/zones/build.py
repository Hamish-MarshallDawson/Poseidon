"""One-off: fetch EEZ and marine protected-area shapes for our regions, clip, simplify, write GeoJSON (#157).

    python -m dvm.zones.build [--out DIR] [--margin-deg 2] [--tolerance-deg 0.001]

Sources (both public, no key):
- EEZs: Marine Regions WFS `MarineRegions:eez` (CC BY 4.0, Flanders Marine Institute). `mrgid` matches the `eez`
  tags on GFW events (5674 Denmark, 5694 Sweden), so our live tags and GFW's labels share one id system.
- Marine protected areas: the World Database on Protected Areas map service (UNEP-WCMC and IUCN, non-commercial use
  with attribution), `realm <> 'Terrestrial'`. No-take status is not taken from here (its filter gives 0 sites).

Writes three layers to `dvm/zones/layers/` (or --out):
- `eez.geojson`: one feature per EEZ part touching our boxes, clipped to them, properties mrgid, name, sovereign, iso,
  pol_type.
- `mpa.geojson`: marine WDPA sites, clipped, properties site_id, name, desig, iucn, status, iso3.
- `eez_borders.geojson`: the maritime borders between EEZs (shared EEZ edges, not the coastline), properties a, b
  (the two mrgids). `lookup.distance_to_eez_border_m` measures to these.
Simplified with `tolerance_deg` (0.001 deg is about 110 m north-south, 55 m east-west at 60 N), coordinates rounded to
4 decimals (about 11 m). Holes under about 1 km2 (islands) are filled and marine sites under about
0.1 km2 dropped, which keeps the layers small enough to commit.
"""
from __future__ import annotations

import argparse
import json
import logging
import time
from pathlib import Path

import httpx
from shapely import geometry as G, ops, set_precision
from shapely.geometry import mapping, shape

from dvm.sources.common import REGIONS

log = logging.getLogger(__name__)

DATA_DIR = Path(__file__).parent / "layers"
EEZ_WFS = "https://geo.vliz.be/geoserver/MarineRegions/wfs"
WDPA = ("https://data-gis.unep-wcmc.org/server/rest/services/ProtectedSites/"
        "The_World_Database_of_Protected_Areas/MapServer/1/query")
WDPA_FIELDS = "site_id,name_eng,desig_eng,iucn_cat,status,iso3,realm"
PAGE = 1000
MIN_HOLE_DEG2 = 2e-4   # about 1 km2 at 60 N
MIN_MPA_DEG2 = 2e-5    # about 0.1 km2: smaller marine sites are dropped
PRECISION = 1e-4   # coordinate grid, about 11 m: well under the simplification tolerance
ATTRIBUTION = {
    "eez": "Flanders Marine Institute (2023). Maritime Boundaries Geodatabase, version 12. marineregions.org. CC BY 4.0",
    "mpa": "UNEP-WCMC and IUCN (2026). Protected Planet: The World Database on Protected Areas (WDPA). "
           "protectedplanet.net. Non-commercial use with attribution",
}


def boxes(margin: float) -> dict[str, tuple[float, float, float, float]]:
    return {n: (max(-180, a - margin), max(-90, b - margin), min(180, c + margin), min(90, d + margin))
            for n, (a, b, c, d) in REGIONS.items()}


def clip_area(margin: float):
    return ops.unary_union([G.box(*b) for b in boxes(margin).values()])


def _fill_small_holes(g, min_deg2: float):
    """Drop interior rings (islands, mostly) smaller than min_deg2: they are most of the vertices in the Finnish and
    Swedish archipelagos, and a ship is never inside a hole that small for long."""
    def one(p):
        return G.Polygon(p.exterior, [r for r in p.interiors if G.Polygon(r).area >= min_deg2])
    if g.geom_type == "Polygon":
        return one(g)
    if g.geom_type == "MultiPolygon":
        return G.MultiPolygon([one(p) for p in g.geoms])
    return g


def _clean(g, area, tol: float, min_hole_deg2: float = MIN_HOLE_DEG2):
    g = g.buffer(0) if not g.is_valid else g
    g = g.intersection(area)
    if g.is_empty:
        return None
    polys = [p for p in getattr(g, "geoms", [g]) if p.geom_type == "Polygon"]
    if not polys:
        return None
    g = _fill_small_holes(G.MultiPolygon(polys), min_hole_deg2)
    g = set_precision(g.simplify(tol, preserve_topology=True), PRECISION)
    g = g.buffer(0) if not g.is_valid else g
    polys = [p for p in getattr(g, "geoms", [g]) if p.geom_type == "Polygon" and p.area > 0]
    if not polys:
        return None
    return polys[0] if len(polys) == 1 else G.MultiPolygon(polys)


def fetch_eez(client: httpx.Client, box) -> list[dict]:
    r = client.get(EEZ_WFS, params={"service": "WFS", "version": "1.0.0", "request": "GetFeature",
                                    "typeName": "MarineRegions:eez", "outputFormat": "application/json",
                                    "bbox": ",".join(str(x) for x in box)})
    r.raise_for_status()
    return r.json()["features"]


def fetch_mpa(client: httpx.Client, box, tol: float) -> list[dict]:
    out, offset = [], 0
    while True:
        r = client.get(WDPA, params={
            "where": "realm <> 'Terrestrial'", "geometry": ",".join(str(x) for x in box),
            "geometryType": "esriGeometryEnvelope", "inSR": 4326, "outSR": 4326,
            "spatialRel": "esriSpatialRelIntersects", "outFields": WDPA_FIELDS, "returnGeometry": "true",
            "maxAllowableOffset": tol / 2, "geometryPrecision": 6, "resultOffset": offset,
            "resultRecordCount": PAGE, "orderByFields": "objectid", "f": "geojson"})
        r.raise_for_status()
        d = r.json()
        if "error" in d:
            raise RuntimeError(f"WDPA: {d['error']}")
        feats = d.get("features") or []
        out += feats
        if len(feats) < PAGE and not d.get("exceededTransferLimit"):
            return out
        offset += len(feats)


def _write(path: Path, feats: list[dict], attribution: str) -> int:
    path.write_text(json.dumps({"type": "FeatureCollection", "attribution": attribution, "features": feats},
                               separators=(",", ":")))
    return path.stat().st_size


def _cached(cache: Path | None, key: str, fetch):
    f = cache / f"{key}.json" if cache else None
    if f and f.exists():
        return json.loads(f.read_text())
    d = fetch()
    if f:
        f.parent.mkdir(parents=True, exist_ok=True)
        f.write_text(json.dumps(d))
    return d


def build(out: Path = DATA_DIR, margin: float = 2.0, tol: float = 0.001, cache: Path | None = None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    area = clip_area(margin)
    eez_raw: dict[int, dict] = {}
    mpa_raw: dict[int, dict] = {}
    with httpx.Client(timeout=180, headers={"User-Agent": "poseidon-zones/1"}) as client:
        for name, box in boxes(margin).items():
            t0 = time.monotonic()
            e = _cached(cache, f"eez-{name}-{margin}", lambda: fetch_eez(client, box))
            m = _cached(cache, f"mpa-{name}-{margin}-{tol}", lambda: fetch_mpa(client, box, tol))
            for f in e:
                eez_raw.setdefault(int(f["properties"]["mrgid"]), f)
            for f in m:
                if f.get("geometry"):
                    mpa_raw.setdefault(int(f["properties"]["site_id"]), f)
            log.info("%s: %d EEZs, %d marine protected areas (%.1f s)", name, len(e), len(m), time.monotonic() - t0)

    # EEZ shapes clipped (a small margin outside the area so the borders reach its edge) and lightly simplified
    # first: the pairwise border step on the full-resolution shapes takes about 10 minutes.
    wide = area.buffer(0.05)
    t0 = time.monotonic()
    eez_geom = {}
    for k, f in eez_raw.items():
        g = shape(f["geometry"])
        g = (g if g.is_valid else g.buffer(0)).intersection(wide)
        eez_geom[k] = g.simplify(tol / 4, preserve_topology=True)
    log.info("EEZs clipped in %.1f s", time.monotonic() - t0)
    eez_feats = []
    for k, f in sorted(eez_raw.items()):
        g = _clean(eez_geom[k], area, tol)
        if g is None:
            continue
        p = f["properties"]
        eez_feats.append({"type": "Feature", "geometry": mapping(g), "properties": {
            "mrgid": k, "name": p.get("geoname"), "sovereign": p.get("sovereign1"), "iso": p.get("iso_sov1"),
            "pol_type": p.get("pol_type")}})

    # Borders: the stretch of each EEZ's edge that touches another EEZ (shared edges; the coast is not a border)
    border_feats = []
    keys = sorted(k for k, g in eez_geom.items() if not g.is_empty)
    for i, a in enumerate(keys):
        for b in keys[i + 1:]:
            ga, gb = eez_geom[a], eez_geom[b]
            if not ga.intersects(gb.buffer(tol)):
                continue
            line = ga.boundary.intersection(gb.buffer(tol / 2)).intersection(area)
            lines = [x for x in getattr(line, "geoms", [line]) if x.geom_type in ("LineString", "MultiLineString")]
            if not lines:
                continue
            merged = ops.linemerge(ops.unary_union(lines)) if len(lines) > 1 else lines[0]
            merged = set_precision(merged.simplify(tol), PRECISION)
            if merged.is_empty or merged.length < tol:
                continue
            border_feats.append({"type": "Feature", "geometry": mapping(merged), "properties": {"a": a, "b": b}})

    mpa_feats = []
    for k, f in sorted(mpa_raw.items()):
        g = _clean(shape(f["geometry"]), area, tol)
        if g is None or g.area < MIN_MPA_DEG2:
            continue
        p = f["properties"]
        mpa_feats.append({"type": "Feature", "geometry": mapping(g), "properties": {
            "site_id": k, "name": p.get("name_eng"), "desig": p.get("desig_eng"), "iucn": p.get("iucn_cat"),
            "status": p.get("status"), "iso3": p.get("iso3"), "realm": p.get("realm")}})

    sizes = {"eez": _write(out / "eez.geojson", eez_feats, ATTRIBUTION["eez"]),
             "mpa": _write(out / "mpa.geojson", mpa_feats, ATTRIBUTION["mpa"]),
             "eez_borders": _write(out / "eez_borders.geojson", border_feats, ATTRIBUTION["eez"])}
    summary = {"eez": len(eez_feats), "mpa": len(mpa_feats), "eez_borders": len(border_feats),
               "bytes": sizes, "margin_deg": margin, "tolerance_deg": tol}
    (out / "build.json").write_text(json.dumps({**summary, "built_at": int(time.time() * 1000),
                                                "regions": boxes(margin)}, indent=1))
    return summary


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DATA_DIR)
    ap.add_argument("--margin-deg", type=float, default=2.0)
    ap.add_argument("--tolerance-deg", type=float, default=0.001)
    ap.add_argument("--cache", type=Path, default=None, help="keep the raw downloads here and reuse them")
    a = ap.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    print(json.dumps(build(a.out, a.margin_deg, a.tolerance_deg, a.cache), indent=1))


if __name__ == "__main__":
    main()
