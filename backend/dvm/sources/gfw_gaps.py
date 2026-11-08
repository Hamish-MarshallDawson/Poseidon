"""GFW AIS gap events (go-dark labels) -> observations, fetched worldwide by date and kept per area (#112).

Why not per region like the rest of gfw.py. Checked live on 8 Nov 2026:
- The public dataset holds only likely intentional disabling: every event has `intentionalDisabling = true`, lasts
  at least 12 h and starts at least 50 nm (93 km) from shore. Our four regions are narrow straits, almost all within
  50 nm of land, so a geometry query there is empty by definition (Baltic plus North Sea: 0 a week; Arabian Sea: 14).
- The `/events` geometry filter tests `position`, which for a gap is the midpoint of the off and on fixes (the centre
  of `boundingBox`), not where AIS went off. A ship that went dark near our waters and came back far away is missed.
- Dates select by overlap: a query for one day returns every gap open during it, some started years before.
So one window is one week worldwide (a week costs about 10 calls of 1000; seven single days cost about 4x more,
because long gaps repeat in every day). An event is kept when its off or on fix, or the straight segment between them,
falls in a requested area. Fishing-gear buoys (`vessel.type = gear`, about 90% of events) are dropped.
Data is CC BY-NC 4.0 (common.SOURCES["gfw"]).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any, Optional

from dvm.sources import gfw, jobs, schema
from dvm.sources.common import DAY_MS, Observation, day_ms, iso_ms, now_ms, utc_today

log = logging.getLogger(__name__)

DATASET = "public-global-gaps-events:latest"
STREAM = "gaps"
WINDOW_DAYS = 7
MAX_EVENTS = 60_000   # per window; a worldwide week is about 9k to 25k
# Waters around our regions where a gap can start (50 nm offshore). (min_lon, min_lat, max_lon, max_lat).
AREAS: dict[str, Optional[tuple[float, float, float, float]]] = {
    # Baltic, Danish straits, North Sea, Norwegian Sea: for danish_straits and gulf_of_finland
    "europe_north": (-12.0, 48.0, 32.0, 72.0),
    # Persian Gulf, Gulf of Oman, Arabian Sea, Gulf of Aden, Red Sea: for hormuz and gulf_of_oman
    "arabian_sea": (32.0, 0.0, 78.0, 31.0),
    "world": None,   # every vessel gap: about 60 to 80 a day, the most go-dark labels for training
}
NAMED = [a for a, b in AREAS.items() if b is not None]
# Polling: newest window worth asking for, and how long GFW may still add gaps that ended in it.
SPEC = {"src": "gfw", "stream": STREAM, "settle_days": 7, "refetch_ms": 6 * 3_600_000, "lookback_windows": 3}


def window_start(d: date) -> date:
    """Windows are Monday-to-Sunday UTC weeks."""
    return d - timedelta(d.weekday())


def _f(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def _in(lon: float, lat: float, b) -> bool:
    return b[0] <= lon <= b[2] and b[1] <= lat <= b[3]


def segment_hits(a: tuple[float, float], b: tuple[float, float], box) -> bool:
    """Does the straight lon/lat segment a-b cross the box (Liang-Barsky)? A segment across the antimeridian is not
    drawn the short way here, so it never counts."""
    (x0, y0), (x1, y1) = a, b
    if abs(x1 - x0) > 180:
        return False
    dx, dy = x1 - x0, y1 - y0
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, x0 - box[0]), (dx, box[2] - x0), (-dy, y0 - box[1]), (dy, box[3] - y0)):
        if p == 0:
            if q < 0:
                return False
            continue
        t = q / p
        if p < 0:
            t0 = max(t0, t)
        else:
            t1 = min(t1, t)
        if t0 > t1:
            return False
    return True


def areas_of(off: tuple[float, float], on: Optional[tuple[float, float]]) -> dict[str, str]:
    """Named areas the gap touches, with how: 'off' (AIS went off inside), 'on' or 'segment'."""
    out = {}
    for name in NAMED:
        box = AREAS[name]
        if _in(*off, box):
            out[name] = "off"
        elif on and _in(*on, box):
            out[name] = "on"
        elif on and segment_hits(off, on, box):
            out[name] = "segment"
    return out


def parse_gaps(body: dict, areas: list[str], recv_ts: int) -> tuple[list[Observation], dict]:
    """GFW gap events -> one observation each, for the events in any of `areas`. Returns (rows, counts)."""
    world = "world" in areas
    counts = {"events": 0, "gear": 0, "no_vessel": 0, "outside": 0, "bad": 0}
    out: dict[str, Observation] = {}
    for e in body.get("entries", []):
        counts["events"] += 1
        v = e.get("vessel") or {}
        g = e.get("gap") or {}
        if (v.get("type") or "").lower() == "gear":
            counts["gear"] += 1
            continue
        mmsi = gfw._mmsi(v.get("ssvid"))
        if mmsi is None:
            counts["no_vessel"] += 1
            continue
        offp, onp = g.get("offPosition") or {}, g.get("onPosition") or {}
        start, end = iso_ms(e.get("start")), iso_ms(e.get("end"))
        if offp.get("lat") is None or offp.get("lon") is None or start is None or not e.get("id"):
            counts["bad"] += 1
            continue
        off = (float(offp["lon"]), float(offp["lat"]))
        on = (float(onp["lon"]), float(onp["lat"])) if onp.get("lat") is not None and onp.get("lon") is not None \
            else None
        hit = areas_of(off, on)
        if not world and not any(a in hit for a in areas):
            counts["outside"] += 1
            continue
        # Published once the gap has closed: the leakage clock runs from the UTC day AIS came back on.
        known = end if end is not None else start
        avail, q = gfw.available((known // DAY_MS + 1) * DAY_MS, recv_ts)
        xs = [off[0]] + ([on[0]] if on else [])
        ys = [off[1]] + ([on[1]] if on else [])
        dist = e.get("distances") or {}
        attrs = {
            "event_id": e.get("id"), "vessel_id": v.get("id"), "name": v.get("name"), "flag": v.get("flag"),
            "vessel_type": v.get("type"),
            "on_lat": on[1] if on else None, "on_lon": on[0] if on else None,
            "distance_km": _f(g.get("distanceKm")), "implied_speed_knots": _f(g.get("impliedSpeedKnots")),
            "intentional_disabling": g.get("intentionalDisabling"),
            "positions_per_day_sat_reception": _f(g.get("positionsPerDaySatReception")),
            "positions_12h_before_sat": _f(g.get("positions12HoursBeforeSat")),
            "off_shore_km": _f(dist.get("startDistanceFromShoreKm")),
            "on_shore_km": _f(dist.get("endDistanceFromShoreKm")),
            "off_port_km": _f(dist.get("startDistanceFromPortKm")),
            "on_port_km": _f(dist.get("endDistanceFromPortKm")),
            "eez": ((e.get("regions") or {}).get("eez")) or None,
            "areas": hit or None,
        }
        hours = _f(g.get("durationHours"))
        out[f"gfw:gap:{e['id']}"] = Observation(
            id=f"gfw:gap:{e['id']}", src="gfw", kind="gap", ts=start, end_ts=end, recv_ts=recv_ts,
            available_ts=avail, mmsi=mmsi, lat=off[1], lon=off[0], bbox=(min(xs), min(ys), max(xs), max(ys)),
            value=hours if hours is not None else ((end - start) / 3_600_000 if end else None),
            attrs={k: x for k, x in attrs.items() if x not in (None, {}, [])}, q=list(q))
    return list(out.values()), counts


def fetch_window(client: gfw.Client, start: date, end: date, raw_sink=None) -> dict:
    """Every gap event open at some point in [start, end) worldwide, all pages."""
    entries: list[dict] = []
    offset = 0
    body = {"datasets": [DATASET], "startDate": start.isoformat(), "endDate": end.isoformat()}
    while True:
        d = client._post("/events", {"limit": gfw.PAGE, "offset": offset}, body)
        entries += d.get("entries", [])
        nxt = d.get("nextOffset")
        if not nxt or nxt <= offset or len(entries) >= MAX_EVENTS:
            out = {"entries": entries, "total": d.get("total")}
            break
        offset = nxt
    if out["total"] and len(entries) < out["total"]:
        log.warning("gaps %s: kept %d of %d events (page cap)", start, len(entries), out["total"])
    if raw_sink:
        raw_sink("events_gap", out)
    return out


async def run_window(pool, start: date, areas: list[str], *, client, force=False, data_dir=None) -> dict:
    """Fetch one week (once, worldwide) for every requested area whose ledger row is not settled."""
    s_ms = day_ms(start)
    e_ms = s_ms + WINDOW_DAYS * DAY_MS
    now = now_ms()
    async with pool.acquire() as con:
        rows = {a: await schema.get_window(con, SPEC["src"], STREAM, a, s_ms) for a in areas}
    todo = [a for a in areas if jobs.needs_fetch(rows[a], e_ms, now, SPEC, force)]
    res: dict[str, Any] = {"src": "gfw", "stream": STREAM, "week": start.isoformat()}
    if not todo:
        return res | {"skipped": True}
    raw = jobs.RawDump(data_dir, "gfw", STREAM, start)
    rec_end = min(e_ms, now)
    try:
        body = await asyncio.to_thread(fetch_window, client, start, start + timedelta(WINDOW_DAYS), raw)
        obs, counts = parse_gaps(body, todo, now)
    except Exception as e:   # recorded and retried on the next run; never stops the others
        async with pool.acquire() as con:
            for a in todo:
                await schema.record_window(con, SPEC["src"], STREAM, a, s_ms, rec_end, now, 0, "error",
                                           f"{type(e).__name__}: {e}"[:500])
        log.warning("gaps %s failed: %s", start, e)
        return res | {"error": str(e)[:200]}
    per_area = {a: sum(1 for o in obs if a == "world" or a in o.attrs.get("areas", {})) for a in todo}
    async with pool.acquire() as con:
        async with con.transaction():
            n = await schema.write_observations(con, obs)
            for a in todo:
                await schema.record_window(con, SPEC["src"], STREAM, a, s_ms, rec_end, now, per_area[a], "ok")
    res |= {"observations": n, "areas": per_area, **counts}
    log.info("%s", res)
    return res


async def backfill(url: str, areas: list[str], start: date, end: date, *, force=False, data_dir=None) -> list[dict]:
    """Every week that overlaps [start, end] (inclusive days)."""
    pool = await jobs.connect(url)
    client = gfw.Client()
    out = []
    try:
        w = window_start(start)
        while w <= end:
            out.append(await run_window(pool, w, areas, client=client, force=force, data_dir=data_dir))
            w += timedelta(WINDOW_DAYS)
    finally:
        client.close()
        await pool.close()
    return out


async def poll(url: str, areas: list[str], *, once=False, data_dir=None) -> list[dict]:
    """The current week and the ones before it that GFW may still be filling, then sleep; forever unless once."""
    pool = await jobs.connect(url)
    client = gfw.Client()
    out = []
    try:
        while True:
            newest = window_start(utc_today())
            for k in range(SPEC["lookback_windows"] - 1, -1, -1):
                out.append(await run_window(pool, newest - timedelta(WINDOW_DAYS * k), areas, client=client,
                                            data_dir=data_dir))
            if once:
                return out
            await asyncio.sleep(min(SPEC["refetch_ms"] / 1000, 1800))
    finally:
        client.close()
        await pool.close()


async def backfill_back(url: str, areas: list[str], *, until: date, max_db_gb: float = jobs.DEFAULT_MAX_DB_GB,
                        data_dir=None, newest: date | None = None, empty_stop: int = 3) -> dict:
    """From the current week backwards until `until`, `empty_stop` empty weeks in a row, or the size cap.
    Settled weeks are skipped, so a restart resumes; one transaction per week, so Ctrl+C is safe."""
    pool = await jobs.connect(url)
    client = gfw.Client()
    w = window_start(newest or utc_today())
    totals = {"weeks": 0, "observations": 0, "errors": 0}
    empty, stopped = 0, None
    try:
        while not stopped:
            async with pool.acquire() as con:
                size_gb = await schema.db_size_bytes(con) / 1e9
            if size_gb >= max_db_gb:
                stopped = f"database is {size_gb:.1f} GB, at the {max_db_gb:.0f} GB cap"
                break
            r = await run_window(pool, w, areas, client=client, data_dir=data_dir)
            totals["weeks"] += 1
            totals["observations"] += r.get("observations", 0)
            totals["errors"] += "error" in r
            if not r.get("skipped") and "error" not in r:
                empty = 0 if r.get("events") else empty + 1   # no event anywhere: GFW's history has ended
            if empty >= empty_stop:
                stopped = f"{empty} consecutive weeks with no gap events (history ends near {w})"
            w -= timedelta(WINDOW_DAYS)
            if not stopped and w + timedelta(WINDOW_DAYS - 1) < until:
                stopped = f"reached --until {until}"
    finally:
        client.close()
        await pool.close()
    return {"src": "gfw", "stream": STREAM, "oldest_week": (w + timedelta(WINDOW_DAYS)).isoformat(),
            "stopped": stopped, **totals}
