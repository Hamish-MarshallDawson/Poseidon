"""Read path shared by the model and the frontend: one query for every provider, filtered by kind, place and time.

Leakage rule (06 section 5.1): pass `as_of` and only rows the provider had published by then come back
(`available_ts <= as_of`). Every answer carries the attribution of each source in it.
"""
from __future__ import annotations

import json

from dvm.sources.common import SOURCES
from dvm.sources.schema import _dt

MAX_ROWS = 20_000
MAX_SPAN_MS = 31 * 86_400_000   # longest event a windowed query still finds by overlap

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
        # Chunk pruning: without a lower bound on `time` every chunk back to 2012 is opened. An event that started
        # more than MAX_SPAN_MS before the window is skipped even if it overlaps (rare: multi-month port visits).
        where.append(f"time >= to_timestamp({arg((int(start_ts) - MAX_SPAN_MS) / 1000)})")
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


# ---- Read helpers for the HTTP routes (dvm/sources/routes.py). The functions above keep their behaviour. ----

MAP_COLS = ("id, src, kind, ts, end_ts, available_ts, mmsi, lat, lon, min_lon, min_lat, max_lon, max_lat, "
            "cell_deg, value, n, matched, attrs, q, CASE WHEN kind = 'radar_scene' THEN geom END AS geom")
MAP_ATTRS = ("name", "shipName", "flag", "vessel_type", "vesselType", "event_id", "region", "platform",
             "instrument_mode", "orbit_state", "product_timeliness")

POS_COLS = ("mmsi, ts, recv_ts, lat, lon, sog_kn, cog_deg, heading_deg, nav_status, cls, msg_type, ts_quality, src, q")
POS_KEY = ("ts", "mmsi", "recv_ts", "src", "msg_type")   # unique enough for keyset paging; see positions_page
STATIC_FIELDS = ("imo", "name", "callsign", "ship_type", "type_group", "dim_a_m", "dim_b_m", "dim_c_m", "dim_d_m",
                 "length_m", "beam_m", "draught_m", "destination", "eta_utc", "mid", "flag_iso2")


def attribution_for(srcs) -> dict:
    return {s: SOURCES[s]["attribution"] for s in sorted(set(srcs)) if s in SOURCES}


def _ms_time(n: int) -> str:
    return f"to_timestamp({n}::bigint / 1000.0)"   # n is an int we validated; time = ts as timestamptz


async def map_observations(con, kinds, bbox, start_ts, end_ts, limit) -> dict:
    sql, args = observations_sql(kinds=kinds, bbox=bbox, start_ts=start_ts, end_ts=end_ts, limit=limit)
    sql = sql.replace(f"SELECT {COLS} FROM", f"SELECT {MAP_COLS} FROM", 1)
    rows = []
    for r in await con.fetch(sql, *args, timeout=30):
        d = _row(r)
        d["attrs"] = {k: v for k, v in d["attrs"].items() if k in MAP_ATTRS}
        if d.get("geom") is None:
            d.pop("geom", None)
        rows.append(d)
    return {"observations": rows, "attribution": attribution_for(r["src"] for r in rows)}


async def model_observations_page(con, as_of, kinds, bbox, start_ts, end_ts, after, limit) -> tuple[list[dict], bool]:
    """Keyset page ordered by (ts, id). `after` is the last (ts, id) of the previous page. Returns (rows, more)."""
    where, args = [], []

    def arg(v):
        args.append(v)
        return f"${len(args)}"

    where.append(f"available_ts <= {arg(int(as_of))}")
    if kinds:
        where.append(f"kind = ANY({arg(list(kinds))}::text[])")
    if end_ts is not None:
        where.append(f"time <= to_timestamp({arg(end_ts)}::bigint / 1000.0)")
    if start_ts is not None:
        where.append(f"coalesce(end_ts, ts) >= {arg(int(start_ts))}")
        where.append(f"time >= to_timestamp({arg(int(start_ts) - MAX_SPAN_MS)}::bigint / 1000.0)")   # chunk pruning
    if bbox:
        x0, y0, x1, y1 = (arg(float(v)) for v in bbox)
        where.append(f"coalesce(max_lon, lon) >= {x0} AND coalesce(min_lon, lon) <= {x1} "
                     f"AND coalesce(max_lat, lat) >= {y0} AND coalesce(min_lat, lat) <= {y1}")
    if after:
        where.append(f"(ts, id) > ({arg(int(after[0]))}::bigint, {arg(str(after[1]))}::text)")
    sql = (f"SELECT {COLS} FROM observations WHERE {' AND '.join(where)} ORDER BY ts, id LIMIT {int(limit) + 1}")
    rows = [_row(r) for r in await con.fetch(sql, *args, timeout=120)]
    return rows[:limit], len(rows) > limit


async def positions_page(con, as_of, start_ts, end_ts, bbox, mmsis, after, limit) -> tuple[list[dict], bool]:
    """Keyset page over positions ordered by (ts, mmsi, recv_ts, src, msg_type), with recv_ts <= as_of."""
    where, args = [], []

    def arg(v):
        args.append(v)
        return f"${len(args)}"

    where.append(f"recv_ts <= {arg(int(as_of))}")
    if start_ts is not None:
        where += [f"ts >= {arg(int(start_ts))}", f"time >= to_timestamp({arg(int(start_ts))}::bigint / 1000.0)"]
    if end_ts is not None:
        where += [f"ts <= {arg(int(end_ts))}", f"time <= to_timestamp({arg(int(end_ts))}::bigint / 1000.0)"]
    if mmsis:
        where.append(f"mmsi = ANY({arg(list(mmsis))}::int[])")
    if bbox:
        x0, y0, x1, y1 = (arg(float(v)) for v in bbox)
        where.append(f"lon >= {x0} AND lon <= {x1} AND lat >= {y0} AND lat <= {y1}")
    if after:
        types = ("bigint", "int", "bigint", "text", "smallint")
        ph = ", ".join(f"{arg(v)}::{t}" for v, t in zip(after, types))
        where.append(f"({', '.join(POS_KEY)}) > ({ph})")
    sql = (f"SELECT {POS_COLS} FROM positions WHERE {' AND '.join(where)} "
           f"ORDER BY {', '.join(POS_KEY)} LIMIT {int(limit) + 1}")
    rows = [dict(r) for r in await con.fetch(sql, *args, timeout=120)]
    return rows[:limit], len(rows) > limit


async def statics_as_of(con, as_of, mmsis, after_mmsi, limit) -> tuple[list[dict], bool]:
    """Per mmsi, each field's newest non-null value with recv_ts <= as_of, and the source it came from."""
    args: list = [int(as_of)]
    where = ["recv_ts <= $1"]
    if mmsis:
        args.append(list(mmsis))
        where.append(f"mmsi = ANY(${len(args)}::int[])")
    if after_mmsi is not None:
        args.append(int(after_mmsi))
        where.append(f"mmsi > ${len(args)}")
    cols = ",\n  ".join(
        f"(array_agg({f} ORDER BY ts DESC, recv_ts DESC) FILTER (WHERE {f} IS NOT NULL))[1] AS {f}, "
        f"(array_agg(src ORDER BY ts DESC, recv_ts DESC) FILTER (WHERE {f} IS NOT NULL))[1] AS {f}__src"
        for f in STATIC_FIELDS)
    sql = (f"SELECT mmsi, max(ts) AS ts, max(recv_ts) AS recv_ts,\n  {cols}\nFROM statics WHERE {' AND '.join(where)} "
           f"GROUP BY mmsi ORDER BY mmsi LIMIT {int(limit) + 1}")
    out = []
    for r in await con.fetch(sql, *args, timeout=120):
        d = {"mmsi": r["mmsi"], "ts": r["ts"], "recv_ts": r["recv_ts"], "sources": {}}
        for f in STATIC_FIELDS:
            d[f] = r[f]
            if r[f] is not None:
                d["sources"][f] = r[f + "__src"]
        out.append(d)
    return out[:limit], len(out) > limit


# One ship's past track for Track history (GET /track): the latest fix in each minute, oldest first. The mmsi filter and
# time window use positions_mmsi_time (mmsi, time DESC), so it reads only that ship's rows (a few ms for 24 h).
TRACK_SQL = ("SELECT DISTINCT ON (bucket) time_bucket('1 minute', time) AS bucket, ts, lon, lat, src FROM positions "
             "WHERE mmsi = $1 AND time >= $2 AND time <= $3 ORDER BY bucket, time DESC")


async def track(con, mmsi: int, start_ms: int, end_ms: int) -> tuple[list[list], set[str]]:
    """[[ts, lon, lat], ...] with at most one point per minute in [start_ms, end_ms], oldest first; and the sources."""
    rows = await con.fetch(TRACK_SQL, mmsi, _dt(start_ms), _dt(end_ms))
    return [[r["ts"], r["lon"], r["lat"]] for r in rows], {r["src"] for r in rows}
