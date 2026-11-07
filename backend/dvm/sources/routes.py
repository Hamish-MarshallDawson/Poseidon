"""Read-only data routes over Tiger for the map (/observations, /sources) and the model (/model/*).

Mount with: app.include_router(make_router(get_pool, require_login)), where get_pool() returns the asyncpg pool or
None (answered 503). Times are epoch ms UTC (06 units). Every answer carries the attribution of the sources in it.
"""
from __future__ import annotations

import base64
import hmac
import json
import os
import time
from typing import Awaitable, Callable

from fastapi import APIRouter, Depends, Header, HTTPException, Query

from dvm import coverage
from dvm.sources import query
from dvm.sources.common import SOURCES

MAP_MAX_WINDOW_MS = 7 * 86_400_000
MAP_DEFAULT_WINDOW_MS = 86_400_000
MAP_DEFAULT_LIMIT, MAP_MAX_LIMIT = 2000, 5000
MODEL_DEFAULT_LIMIT, MODEL_MAX_LIMIT = 10_000, 50_000
MAX_MMSIS = 1000
KINDS = {"ais_presence", "sar_detection", "gap", "encounter", "loitering", "port_visit", "radar_scene"}
MAX_MS = 4_102_444_800_000   # year 2100: anything above is a seconds/ms mix-up or junk


def _bad(msg: str):
    raise HTTPException(422, msg)


def parse_bbox(text: str | None, required: bool):
    """'minLon,minLat,maxLon,maxLat' or coverage's '[[lon1,lat1],[lon2,lat2]]' -> (min_lon, min_lat, max_lon, max_lat)."""
    if not text:
        if required:
            _bad("bbox is required")
        return None
    try:
        if text.lstrip().startswith("["):
            box = coverage.parse_bbox(text)
        else:
            x0, y0, x1, y1 = (float(p) for p in text.split(","))
            box = coverage.parse_bbox(json.dumps([[x0, y0], [x1, y1]]))
    except (ValueError, TypeError) as e:
        _bad(f"bad bbox: {e}; use minLon,minLat,maxLon,maxLat")
    if box[0] == box[2] or box[1] == box[3]:
        _bad("bbox has no area")
    return box


def parse_kinds(text: str | None):
    if not text:
        return None
    kinds = [k for k in (p.strip() for p in text.split(",")) if k]
    unknown = sorted(set(kinds) - KINDS)
    if unknown:
        _bad(f"unknown kinds {unknown}; known: {sorted(KINDS)}")
    return kinds


def check_ms(name: str, v: int | None) -> int | None:
    if v is not None and not 0 <= v <= MAX_MS:
        _bad(f"{name} must be epoch milliseconds")
    return v


def check_range(start, end):
    if start is not None and end is not None and start > end:
        _bad("start must not be after end")


def encode_cursor(key: list) -> str:
    return base64.urlsafe_b64encode(json.dumps(key, separators=(",", ":")).encode()).decode().rstrip("=")


def decode_cursor(text: str | None, n: int):
    if not text:
        return None
    try:
        key = json.loads(base64.urlsafe_b64decode(text + "=" * (-len(text) % 4)))
        if not isinstance(key, list) or len(key) != n:
            raise ValueError
        return key
    except (ValueError, TypeError):
        _bad("bad cursor")


def make_router(get_pool: Callable[[], object], require_login: Callable[..., Awaitable[None]]) -> APIRouter:
    async def model_login(authorization: str | None = Header(None)) -> None:
        """A static MODEL_API_TOKEN (Bearer) for training scripts, else the normal login. Read per request, never logged."""
        want = os.getenv("MODEL_API_TOKEN", "")
        scheme, _, token = (authorization or "").partition(" ")
        if want and scheme == "Bearer" and hmac.compare_digest(token.encode(), want.encode()):
            return
        await require_login(authorization)

    def pool():
        p = get_pool()
        if p is None:
            raise HTTPException(503, "Tiger Data is not connected")
        return p

    front = APIRouter(dependencies=[Depends(require_login)])
    model = APIRouter(prefix="/model", dependencies=[Depends(model_login)])

    @front.get("/observations")
    async def observations(kinds: str | None = None, bbox: str | None = None, start: int | None = None,
                           end: int | None = None, limit: int = Query(MAP_DEFAULT_LIMIT, ge=1, le=MAP_MAX_LIMIT)) -> dict:
        box = parse_bbox(bbox, required=True)
        kinds_ = parse_kinds(kinds)
        check_ms("start", start), check_ms("end", end)
        end = end if end is not None else int(time.time() * 1000)
        start = start if start is not None else end - MAP_DEFAULT_WINDOW_MS
        check_range(start, end)
        if end - start > MAP_MAX_WINDOW_MS:
            _bad("time window is capped at 7 days")
        async with pool().acquire() as con:
            return await query.map_observations(con, kinds_, box, start, end, limit)

    @front.get("/sources")
    async def sources() -> dict:
        now = int(time.time() * 1000)
        async with pool().acquire() as con:
            return {"now": now, "sources": await query.freshness(con, now)}

    def window(as_of, start, end):
        check_ms("as_of", as_of), check_ms("start", start), check_ms("end", end)
        check_range(start, end)

    @model.get("/observations")
    async def model_observations(as_of: int, kinds: str | None = None, bbox: str | None = None,
                                 start: int | None = None, end: int | None = None, cursor: str | None = None,
                                 limit: int = Query(MODEL_DEFAULT_LIMIT, ge=1, le=MODEL_MAX_LIMIT)) -> dict:
        window(as_of, start, end)
        box, kinds_, after = parse_bbox(bbox, False), parse_kinds(kinds), decode_cursor(cursor, 2)
        async with pool().acquire() as con:
            rows, more = await query.model_observations_page(con, as_of, kinds_, box, start, end, after, limit)
        return {"as_of": as_of, "observations": rows, "attribution": query.attribution_for(r["src"] for r in rows),
                "next_cursor": encode_cursor([rows[-1]["ts"], rows[-1]["id"]]) if more else None}

    @model.get("/positions")
    async def model_positions(as_of: int, start: int | None = None, end: int | None = None, bbox: str | None = None,
                              mmsi: list[int] = Query([], max_length=MAX_MMSIS), cursor: str | None = None,
                              limit: int = Query(MODEL_DEFAULT_LIMIT, ge=1, le=MODEL_MAX_LIMIT)) -> dict:
        window(as_of, start, end)
        box, after = parse_bbox(bbox, False), decode_cursor(cursor, 5)
        async with pool().acquire() as con:
            rows, more = await query.positions_page(con, as_of, start, end, box, mmsi, after, limit)
        last = rows[-1] if rows else None
        return {"as_of": as_of, "positions": rows, "attribution": query.attribution_for(r["src"] for r in rows),
                "next_cursor": encode_cursor([last[k] for k in query.POS_KEY]) if more else None}

    @model.get("/statics")
    async def model_statics(as_of: int, mmsi: list[int] = Query([], max_length=MAX_MMSIS), cursor: str | None = None,
                            limit: int = Query(MAX_MMSIS, ge=1, le=MODEL_MAX_LIMIT)) -> dict:
        check_ms("as_of", as_of)
        after = decode_cursor(cursor, 1)
        async with pool().acquire() as con:
            rows, more = await query.statics_as_of(con, as_of, mmsi, after[0] if after else None, limit)
        srcs = {s for r in rows for s in r["sources"].values()}
        return {"as_of": as_of, "statics": rows, "attribution": query.attribution_for(srcs),
                "next_cursor": encode_cursor([rows[-1]["mmsi"]]) if more else None}

    root = APIRouter()
    root.include_router(front)
    root.include_router(model)
    return root
