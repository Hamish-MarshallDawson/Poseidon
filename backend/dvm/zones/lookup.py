"""Zone lookups (#157): which EEZ and protected areas a point is in, and how far it is to an EEZ border.

The layers come from `python -m dvm.zones.build` (GeoJSON in dvm/zones/layers/, or ZONES_DIR). They are loaded once
(`get()`), cut into 1-degree tiles so every indexed piece is small, and put in shapely STRtrees. A point query then
tests a handful of small polygons; `zone_of_many` does a whole array at once.

Points outside the area the layers were built for (our four regions plus the build margin) get `covered: False` and
no zones: "no EEZ" there means "not loaded", not "high seas".
"""
from __future__ import annotations

import json
import logging
import math
import os
import threading
import time
from pathlib import Path
from typing import Optional

import numpy as np
import shapely
from shapely import STRtree, geometry as G, ops
from shapely.geometry import shape

log = logging.getLogger(__name__)

DATA_DIR = Path(os.environ.get("ZONES_DIR") or Path(__file__).parent / "layers")
TILE_DEG = 1.0
NEAR_EEZ_DEG = 0.05      # a fix just outside every EEZ polygon (a quay, a filled-in coast): take the nearest within this
M_PER_DEG_LAT = 110_574.0
EARTH_R = 6_371_008.8


def _tiles(geom, size: float = TILE_DEG) -> list:
    """The parts of geom in each size x size degree cell (only the cells its bounds touch)."""
    x0, y0, x1, y1 = geom.bounds
    if x1 - x0 <= size and y1 - y0 <= size:
        return [geom]
    out = []
    for i in range(math.floor(x0 / size), math.ceil(x1 / size)):
        for j in range(math.floor(y0 / size), math.ceil(y1 / size)):
            part = geom.intersection(G.box(i * size, j * size, (i + 1) * size, (j + 1) * size))
            if not part.is_empty and part.area > 0:
                out.append(part)
    return out


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 2 * EARTH_R * math.asin(min(1.0, math.sqrt(a)))


class Layer:
    """One polygon layer: features (properties), their tiled pieces and an STRtree over the pieces."""

    def __init__(self, features: list[dict], id_key: str):
        self.props = [f["properties"] for f in features]
        self.ids = [p[id_key] for p in self.props]
        self.geoms = [shape(f["geometry"]) for f in features]
        pieces, owner = [], []
        for k, g in enumerate(self.geoms):
            for part in _tiles(g):
                pieces.append(part)
                owner.append(k)
        self.pieces = np.array(pieces, dtype=object)
        self.owner = np.array(owner, dtype=np.int64)
        shapely.prepare(self.pieces)
        self.tree = STRtree(self.pieces)

    def __len__(self) -> int:
        return len(self.ids)

    def at(self, pt) -> list[int]:
        """Feature indexes containing the point, in feature order."""
        return sorted({int(self.owner[i]) for i in self.tree.query(pt, predicate="intersects")})


class Zones:
    def __init__(self, data_dir: Path = DATA_DIR):
        t0 = time.monotonic()
        self.dir = Path(data_dir)
        meta = json.loads((self.dir / "build.json").read_text()) if (self.dir / "build.json").exists() else {}
        boxes = (meta.get("regions") or {}).values()
        self.area = ops.unary_union([G.box(*b) for b in boxes]) if boxes else None
        if self.area is not None:
            shapely.prepare(self.area)
        self.eez = Layer(self._read("eez"), "mrgid")
        self.mpa = Layer(self._read("mpa"), "site_id")
        # the Marine Regions layer has joint regimes and overlapping claims beside each country's 200 nm zone
        self._eez_rank = [0 if (p.get("pol_type") or "200NM") == "200NM" else 1 for p in self.eez.props]
        borders = self._read("eez_borders")
        lines = []
        for f in borders:
            g = shape(f["geometry"])
            for seg in getattr(g, "geoms", [g]):
                coords = list(seg.coords)
                lines += [G.LineString(coords[i:i + 2]) for i in range(len(coords) - 1)]
        self.borders = np.array(lines, dtype=object)
        self.border_tree = STRtree(self.borders) if lines else None
        self.attribution = {k: self._attribution(k) for k in ("eez", "mpa")}
        self.load_s = round(time.monotonic() - t0, 2)
        log.info("Zones loaded from %s: %d EEZs, %d protected areas, %d border segments (%.1f s)", self.dir,
                 len(self.eez), len(self.mpa), len(lines), self.load_s)

    def _read(self, name: str) -> list[dict]:
        return json.loads((self.dir / f"{name}.geojson").read_text())["features"]

    def _attribution(self, name: str) -> Optional[str]:
        try:
            return json.loads((self.dir / f"{name}.geojson").read_text()).get("attribution")
        except OSError:
            return None

    # ---- points ----

    def covered(self, lat: float, lon: float) -> bool:
        return self.area is None or self.area.intersects(G.Point(lon, lat))

    def eez_index(self, lat: float, lon: float, near: bool = True) -> Optional[int]:
        pt = G.Point(lon, lat)
        hits = self.eez.at(pt)
        if hits:
            return min(hits, key=lambda k: self._eez_rank[k])
        if near:
            i = self.eez.tree.query_nearest(pt, max_distance=NEAR_EEZ_DEG)
            if len(i):
                return int(self.eez.owner[i[0]])
        return None

    def eez_of(self, lat: float, lon: float, near: bool = True) -> Optional[int]:
        """The mrgid of the EEZ at the point (its 200 nm zone first; the nearest within ~5 km when on a quay)."""
        k = self.eez_index(lat, lon, near)
        return self.eez.ids[k] if k is not None else None

    def zone_of(self, lat: float, lon: float) -> dict:
        if not self.covered(lat, lon):
            return {"covered": False, "eez": None, "eez_name": None, "mpa": [], "mpa_names": []}
        k = self.eez_index(lat, lon, near=False)
        mpas = self.mpa.at(G.Point(lon, lat))
        return {"covered": True, "eez": self.eez.ids[k] if k is not None else None,
                "eez_name": self.eez.props[k]["name"] if k is not None else None,
                "mpa": [self.mpa.ids[i] for i in mpas], "mpa_names": [self.mpa.props[i]["name"] for i in mpas]}

    def zone_of_many(self, lats, lons) -> tuple[list[Optional[int]], list[list[int]]]:
        """Vectorised: (EEZ mrgid or None, list of MPA site ids) per point. No nearest-EEZ fallback."""
        pts = shapely.points(np.asarray(lons, dtype=float), np.asarray(lats, dtype=float))
        eez: list[Optional[int]] = [None] * len(pts)
        rank = [9] * len(pts)
        p_i, g_i = self.eez.tree.query(pts, predicate="intersects")
        for p, g in zip(p_i, g_i):
            k = int(self.eez.owner[g])
            if self._eez_rank[k] < rank[p]:
                eez[p], rank[p] = self.eez.ids[k], self._eez_rank[k]
        mpa: list[list[int]] = [[] for _ in pts]
        p_i, g_i = self.mpa.tree.query(pts, predicate="intersects")
        for p, g in zip(p_i, g_i):
            sid = self.mpa.ids[int(self.mpa.owner[g])]
            if sid not in mpa[p]:
                mpa[p].append(sid)
        return eez, mpa

    def distance_to_eez_border_m(self, lat: float, lon: float) -> Optional[float]:
        """Metres to the nearest maritime border between two EEZs (not the coast). None if no border is loaded."""
        if self.border_tree is None:
            return None
        pt = G.Point(lon, lat)
        # nearest in degrees with longitude scaled is close enough to pick the segment; the metres come from
        # the nearest point on it by haversine.
        i = self.border_tree.query_nearest(pt)
        best = None
        for j in np.atleast_1d(i):
            q = ops.nearest_points(pt, self.borders[j])[1]
            d = haversine_m(lat, lon, q.y, q.x)
            best = d if best is None or d < best else best
        # the degree metric can pick the wrong segment at high latitude: check the others within that distance
        r_deg = best / (M_PER_DEG_LAT * max(0.2, math.cos(math.radians(lat))))
        for j in self.border_tree.query(pt.buffer(r_deg)):
            q = ops.nearest_points(pt, self.borders[j])[1]
            best = min(best, haversine_m(lat, lon, q.y, q.x))
        return best

    def health(self) -> dict:
        return {"loaded": True, "dir": str(self.dir), "layers": {"eez": len(self.eez), "mpa": len(self.mpa),
                                                                 "eez_border_segments": len(self.borders)},
                "load_s": self.load_s}


_zones: Optional[Zones] = None
_error: Optional[str] = None
_lock = threading.Lock()


def get() -> Optional[Zones]:
    """The loaded zones, or None when the layers are missing or broken (logged once; see health())."""
    global _zones, _error
    if _zones is not None or _error is not None:
        return _zones
    with _lock:
        if _zones is None and _error is None:
            try:
                _zones = Zones()
            except Exception as e:  # noqa: BLE001 - zones are an extra: the predictor and map run without them
                _error = f"{type(e).__name__}: {e}"
                log.warning("Zones not loaded from %s: %s", DATA_DIR, _error)
    return _zones


def health() -> dict:
    z = _zones
    if z is not None:
        return z.health()
    return {"loaded": False, "dir": str(DATA_DIR), "error": _error}


def zone_of(lat: float, lon: float) -> dict:
    z = get()
    return z.zone_of(lat, lon) if z else {"covered": False, "eez": None, "eez_name": None, "mpa": [], "mpa_names": []}


def distance_to_eez_border_m(lat: float, lon: float) -> Optional[float]:
    z = get()
    return z.distance_to_eez_border_m(lat, lon) if z else None
