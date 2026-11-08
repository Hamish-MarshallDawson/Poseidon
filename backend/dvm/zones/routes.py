"""GET /zones (#157): EEZ, protected-area and border shapes for the map, as GeoJSON.

    GET /zones?bbox=[[lon1,lat1],[lon2,lat2]]&layers=eez,mpa,borders

`bbox` is optional (same format as /coverage); features touching it are clipped to it (all of them are already
clipped to our regions plus a 2-degree margin). `layers` defaults to eez,mpa. Each feature gets
`properties.layer`. Same login as /coverage.
"""
from __future__ import annotations

import asyncio

import shapely
from fastapi import APIRouter, Depends, HTTPException
from shapely import geometry as G
from shapely.geometry import mapping

from dvm import coverage
from dvm.zones import lookup

LAYERS = ("eez", "mpa", "borders")


def features(z: lookup.Zones, layers: list[str], box) -> list[dict]:
    q = G.box(*box) if box else None
    out = []
    for name in layers:
        if name == "borders":
            continue
        layer = getattr(z, name)
        idx = (sorted({int(layer.owner[i]) for i in layer.tree.query(q, predicate="intersects")})
               if q is not None else range(len(layer)))
        for k in idx:
            g = layer.geoms[k] if q is None or q.contains(layer.geoms[k]) else layer.geoms[k].intersection(q)
            if not g.is_empty:
                out.append({"type": "Feature", "geometry": mapping(g), "properties": {**layer.props[k], "layer": name}})
    if "borders" in layers and z.border_tree is not None:
        segs = z.borders if q is None else z.borders[z.border_tree.query(q, predicate="intersects")]
        if len(segs):
            out.append({"type": "Feature", "geometry": mapping(shapely.multilinestrings(list(segs))),
                        "properties": {"layer": "borders"}})
    return out


def make_router(require_login) -> APIRouter:
    r = APIRouter()

    @r.get("/zones", dependencies=[Depends(require_login)])
    async def get_zones(bbox: str | None = None, layers: str = "eez,mpa") -> dict:
        try:
            box = coverage.parse_bbox(bbox)
        except ValueError as e:
            raise HTTPException(422, str(e))
        names = [x.strip() for x in layers.split(",") if x.strip()]
        bad = [x for x in names if x not in LAYERS]
        if bad or not names:
            raise HTTPException(422, f"layers must be a comma list of {', '.join(LAYERS)}")
        z = await asyncio.to_thread(lookup.get)
        if z is None:
            raise HTTPException(503, f"zones not loaded: {lookup.health().get('error')}")
        feats = await asyncio.to_thread(features, z, names, box)
        return {"type": "FeatureCollection", "features": feats,
                "attribution": [z.attribution[k] for k in ("eez", "mpa") if k in names or k == "eez"]}

    return r
