"""Read path for the per-cell coverage baseline: the `coverage_1m` continuous aggregate (see store.SETUP).

Cells are 0.1-degree boxes, `lat_bin = floor(lat*10)`, `lon_bin = floor(lon*10)`, as in 06 section 7 decision 10,
and `cell_id` is `"<lat_bin>_<lon_bin>"` (e.g. "600_284"). Rows are per AIS class; the default is Class A, which is
what the gap detector and forecast use.
"""
from __future__ import annotations

import json
import math

VIEW = "coverage_1m"
DEFAULT_MINUTES = 10
MAX_MINUTES = 120   # the aggregate's refresh policy keeps the last 2 h materialised; a cap keeps the query cheap
CLASSES = ("A", "B")


def cell_bin(deg: float) -> int:
    return math.floor(deg * 10)


def cell_id(lat_bin: int, lon_bin: int) -> str:
    return f"{lat_bin}_{lon_bin}"


def parse_bbox(text: str | None) -> tuple[float, float, float, float] | None:
    """'[[lon1,lat1],[lon2,lat2]]' -> (min_lon, min_lat, max_lon, max_lat), or None when empty."""
    if not text:
        return None
    try:
        (lon1, lat1), (lon2, lat2) = json.loads(text)
        lon1, lat1, lon2, lat2 = float(lon1), float(lat1), float(lon2), float(lat2)
    except (ValueError, TypeError) as e:
        raise ValueError("bbox must be [[lon1,lat1],[lon2,lat2]]") from e
    if not (-180 <= lon1 <= 180 and -180 <= lon2 <= 180 and -90 <= lat1 <= 90 and -90 <= lat2 <= 90):
        raise ValueError("bbox out of range (lon -180..180, lat -90..90)")
    return min(lon1, lon2), min(lat1, lat2), max(lon1, lon2), max(lat1, lat2)


def coverage_sql(minutes: int, bbox: tuple[float, float, float, float] | None, cls: str = "A") -> tuple[str, list]:
    if cls not in CLASSES:
        raise ValueError(f"cls must be one of {', '.join(CLASSES)}")
    minutes = max(1, min(int(minutes), MAX_MINUTES))
    sql = (f"SELECT bucket, lat_bin, lon_bin, ships, msgs FROM {VIEW} "
           "WHERE cls = $1 AND bucket >= now() - make_interval(mins => $2)")
    args: list = [cls, minutes]
    if bbox:
        min_lon, min_lat, max_lon, max_lat = bbox
        sql += " AND lon_bin BETWEEN $3 AND $4 AND lat_bin BETWEEN $5 AND $6"
        args += [cell_bin(min_lon), cell_bin(max_lon), cell_bin(min_lat), cell_bin(max_lat)]
    return sql + " ORDER BY bucket", args


async def coverage(pool, minutes: int = DEFAULT_MINUTES, bbox=None, cls: str = "A") -> list[dict]:
    sql, args = coverage_sql(minutes, bbox, cls)
    async with pool.acquire() as con:
        rows = await con.fetch(sql, *args)
    return [{"cell_id": cell_id(r["lat_bin"], r["lon_bin"]), "bucket_ts": int(r["bucket"].timestamp() * 1000),
             "ships": r["ships"], "msgs": r["msgs"]} for r in rows]
