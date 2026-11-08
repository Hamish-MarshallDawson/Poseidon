"""Predicted zone incursion (#157): how much of a route prediction's 80% circle lies in protected areas or in
another country's EEZ.

The shares are measured by sampling: N_SAMPLES points spread evenly over the disk (a sunflower pattern, equal
area per point) are looked up with the vectorised point query, so a share has a standard error of about 3 points and
a cycle's 2,600 rows take a few seconds on one core (exact polygon intersection took 36 ms a circle on big radii).
MPAs overlap (one sea area can carry several designations), so the MPA share counts a sample once if it is in any of
them. `mpa_ids` lists MPAs whose shape touches the circle, largest sampled overlap first, at most MAX_IDS (a 100 km
circle in Danish waters touches 150 sites; the share still counts all of them).

Returns {mpa_ids, mpa_share_80, foreign_eez, foreign_share_80}. All None when the zones are not loaded or the
circle centre is outside the area they were built for; foreign_* are None when the ship's own EEZ is unknown
(nothing to call foreign).
"""
from __future__ import annotations

import math
from typing import Optional

import numpy as np
import shapely
from shapely import geometry as G

from dvm.zones import lookup

N_SIDES = 48
N_SAMPLES = 256
MAX_IDS = 20
_UNIT = np.array([(math.cos(a), math.sin(a)) for a in np.linspace(0, 2 * math.pi, N_SIDES, endpoint=False)])
_k = np.arange(N_SAMPLES) + 0.5
_DISK = np.column_stack([np.sqrt(_k / N_SAMPLES) * np.cos(_k * math.pi * (3 - math.sqrt(5))),
                         np.sqrt(_k / N_SAMPLES) * np.sin(_k * math.pi * (3 - math.sqrt(5)))])
M_PER_DEG_LON_EQ = 111_320.0
FIELDS = ("mpa_ids", "mpa_share_80", "foreign_eez", "foreign_share_80")
NONE = {k: None for k in FIELDS}


def _scale(lat: float, radius_m: float) -> tuple[float, float]:
    return (radius_m / (M_PER_DEG_LON_EQ * max(0.05, math.cos(math.radians(lat)))), radius_m / lookup.M_PER_DEG_LAT)


def circle(lat: float, lon: float, radius_m: float):
    dx, dy = _scale(lat, radius_m)
    return G.Polygon(np.column_stack([lon + _UNIT[:, 0] * dx, lat + _UNIT[:, 1] * dy]))


def samples(lat: float, lon: float, radius_m: float) -> tuple[np.ndarray, np.ndarray]:
    dx, dy = _scale(lat, radius_m)
    return lat + _DISK[:, 1] * dy, lon + _DISK[:, 0] * dx


def incursion(lat: float, lon: float, radius_m_80: float, own_eez: Optional[int],
              zones: Optional[lookup.Zones] = None) -> dict:
    z = zones or lookup.get()
    if z is None or radius_m_80 is None or not z.covered(lat, lon):
        return dict(NONE)
    r = max(float(radius_m_80), 1.0)
    c = circle(lat, lon, r)
    lats, lons = samples(lat, lon, r)
    pts = shapely.points(lons, lats)
    n = len(pts)

    p_i, g_i = z.mpa.tree.query(pts, predicate="intersects")
    hits: dict[int, int] = {}
    for g in g_i:
        k = int(z.mpa.owner[g])
        hits[k] = hits.get(k, 0) + 1
    touching = {int(z.mpa.owner[g]) for g in z.mpa.tree.query(c, predicate="intersects")}
    order = sorted(touching, key=lambda k: (-hits.get(k, 0), z.mpa.ids[k]))
    out = {"mpa_ids": [z.mpa.ids[k] for k in order[:MAX_IDS]], "mpa_share_80": round(len(set(p_i.tolist())) / n, 4)}

    if own_eez is None:
        return {**out, "foreign_eez": None, "foreign_share_80": None}
    p_i, g_i = z.eez.tree.query(pts, predicate="intersects")
    own_pts, foreign_pts, f_hits = set(), set(), {}
    for p, g in zip(p_i.tolist(), g_i.tolist()):
        mid = z.eez.ids[int(z.eez.owner[g])]
        if mid == own_eez:
            own_pts.add(p)
        else:
            foreign_pts.add(p)
            f_hits[mid] = f_hits.get(mid, 0) + 1
    foreign_pts -= own_pts   # joint regimes overlap the 200 nm zones: water that is also ours is not foreign
    return {**out, "foreign_eez": sorted(f_hits, key=lambda m: -f_hits[m]),
            "foreign_share_80": round(len(foreign_pts) / n, 4)}


def for_route_rows(rows: list[dict], fix_lat: float, fix_lon: float) -> list[dict]:
    """Add the incursion fields to one ship's route rows (one per horizon), its own EEZ taken at its last fix.
    Never raises: zones are an extra on the ledger."""
    z = lookup.get()
    if z is None:
        return [{**r, **NONE} for r in rows]
    try:
        own = z.eez_of(fix_lat, fix_lon) if z.covered(fix_lat, fix_lon) else None
        return [{**r, **incursion(r["lat"], r["lon"], r["radius_m_80"], own, z)} for r in rows]
    except (shapely.errors.ShapelyError, ValueError, TypeError) as e:
        lookup.log.warning("Incursion failed at %.4f, %.4f: %s", fix_lat, fix_lon, e)
        return [{**r, **NONE} for r in rows]
