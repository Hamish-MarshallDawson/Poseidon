"""Read path shared by the model and the frontend: one query for every provider, filtered by kind, place and time.

Leakage rule (06 section 5.1): pass `as_of` and only rows the provider had published by then come back
(`available_ts <= as_of`). Every answer carries the attribution of each source in it.
"""
from __future__ import annotations

import json

from dvm.sources.common import SOURCES

MAX_ROWS = 20_000

COLS = ("id, src, kind, ts, end_ts, recv_ts, available_ts, mmsi, lat, lon, min_lon, min_lat, max_lon, max_lat, "
        "cell_deg, value, n, matched, geom, attrs, q")


def observations_sql(kinds=None, bbox=None, start_ts=None, end_ts=None, as_of=None, src=None, mmsi=None,
                     limit=5000) -> tuple[str, list]:
    """Rows whose interval [ts, end_ts] overlaps [start_ts, end_ts] and whose point or box touches bbox."""
    where, args = [], []

    def arg(v):
        args.append(v)
        return f"${len(args)}"

    if kinds:
        where.append(f"kind = ANY({arg(list(kinds))}::text[])")
    if src:
        where.append(f"src = {arg(src)}")
    if mmsi is not None:
        where.append(f"mmsi = {arg(int(mmsi))}")
    if end_ts is not None:
        where.append(f"time <= to_timestamp({arg(end_ts / 1000)})")
    if start_ts is not None:
        where.append(f"coalesce(end_ts, ts) >= {arg(int(start_ts))}")
    if as_of is not None:
        where.append(f"available_ts <= {arg(int(as_of))}")
    if bbox:
        x0, y0, x1, y1 = (arg(float(v)) for v in bbox)
        where.append(f"coalesce(max_lon, lon) >= {x0} AND coalesce(min_lon, lon) <= {x1} "
                     f"AND coalesce(max_lat, lat) >= {y0} AND coalesce(min_lat, lat) <= {y1}")
    sql = f"SELECT {COLS} FROM observations"
    if where:
        sql += " WHERE " + " AND ".join(where)
    sql += f" ORDER BY ts DESC LIMIT {max(1, min(int(limit), MAX_ROWS))}"
    return sql, args


def _row(r) -> dict:
    d = dict(r)
    for k in ("geom", "attrs"):
        if isinstance(d.get(k), str):
            d[k] = json.loads(d[k])
    if d.get("min_lon") is not None:
        d["bbox"] = [d.pop("min_lon"), d.pop("min_lat"), d.pop("max_lon"), d.pop("max_lat")]
    else:
        for k in ("min_lon", "min_lat", "max_lon", "max_lat"):
            d.pop(k, None)
    return d


async def observations(con, **kw) -> dict:
    sql, args = observations_sql(**kw)
    rows = [_row(r) for r in await con.fetch(sql, *args)]
    used = sorted({r["src"] for r in rows})
    return {"observations": rows, "attribution": {s: SOURCES[s]["attribution"] for s in used}}


async def freshness(con, now_ms: int) -> list[dict]:
    """Per source: newest data, newest fetch and age, from the ledger (delayed) or positions (live)."""
    out = []
    for r in await con.fetch(
            "SELECT src, max(end_ts) FILTER (WHERE status = 'ok' AND rows > 0) AS data_until, "
            "max(fetched_at) AS last_fetch, count(*) FILTER (WHERE status = 'error') AS errors "
            "FROM source_windows WHERE src IN ('gfw', 'sentinel1') GROUP BY src"):
        newest = await con.fetchval("SELECT max(ts) FROM observations WHERE src = $1", r["src"])
        out.append({"src": r["src"], "newest_event_ts": newest, "data_until_ts": r["data_until"],
                    "last_fetch_ts": r["last_fetch"], "window_errors": r["errors"],
                    "age_s": (now_ms - newest) // 1000 if newest else None, **SOURCES.get(r["src"], {})})
    for src in ("aisstream", "digitraffic"):
        last = await con.fetchval("SELECT max(recv_ts) FROM positions WHERE src = $1 AND time > now() - interval "
                                  "'1 hour'", src)
        out.append({"src": src, "newest_event_ts": last, "age_s": (now_ms - last) // 1000 if last else None,
                    **SOURCES[src]})
    return out
