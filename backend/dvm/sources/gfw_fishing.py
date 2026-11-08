"""GFW fishing events -> observations kind 'fishing', per region and week (#157).

Checked live on 8 Nov 2026 (week of 19 Oct 2026): the region polygons work for fishing events (the geometry filter tests
`position`, the event's centre), and a week is one page in every region: Danish straits 712, Gulf of Finland 115,
Hormuz 18, Gulf of Oman 19. Dates select by overlap, so about 5% of a week's answer started the week before: an event
is kept only in the week it starts in, which makes each row belong to exactly one ledger window.

Every event has `regions` (eez, eez12Nm, mpa, mpaNoTake, protectedseas, rfmo, highSeas) and a `fishing` block
(potentialRisk, vesselPublicAuthorizationStatus, average speed, distance), but no gear type: that comes from one batched
`/vessels` identity call per window (50 ids a call), best effort, so a failed lookup never loses the events.
Uses only /events and /vessels, never the 4Wings report lock. Data is CC BY-NC 4.0 (common.SOURCES["gfw"]).
"""
from __future__ import annotations

import asyncio
import logging
from datetime import date, timedelta
from typing import Any, Optional

from dvm.sources import gfw, jobs, schema
from dvm.sources.common import DAY_MS, REGIONS, Observation, day_ms, iso_ms, now_ms, poly, utc_today

log = logging.getLogger(__name__)

DATASET = "public-global-fishing-events:latest"
IDENTITY = "public-global-vessel-identity:latest"
STREAM = "fishing"
WINDOW_DAYS = 7
MAX_EVENTS = 20_000   # per region and week; a Danish week is about 700
VESSEL_BATCH = 50
SPEC = {"src": "gfw", "stream": STREAM, "settle_days": 7, "refetch_ms": 6 * 3_600_000, "lookback_windows": 3}


def window_start(d: date) -> date:
    """Windows are Monday-to-Sunday UTC weeks."""
    return d - timedelta(d.weekday())


def _f(v: Any) -> Optional[float]:
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def parse_fishing(body: dict, region: str, bbox, s_ms: int, e_ms: int, recv_ts: int,
                  gear: dict[str, str] | None = None) -> tuple[list[Observation], dict]:
    """Fishing events that start in [s_ms, e_ms) with their position in `bbox` -> observations. Returns (rows, counts)."""
    gear = gear or {}
    counts = {"events": 0, "earlier_week": 0, "outside": 0, "no_vessel": 0, "bad": 0}
    out: dict[str, Observation] = {}
    for e in body.get("entries", []):
        counts["events"] += 1
        v = e.get("vessel") or {}
        pos = e.get("position") or {}
        start, end = iso_ms(e.get("start")), iso_ms(e.get("end"))
        lat, lon = pos.get("lat"), pos.get("lon")
        if start is None or lat is None or lon is None or not e.get("id"):
            counts["bad"] += 1
            continue
        if not s_ms <= start < e_ms:
            counts["earlier_week" if start < s_ms else "bad"] += 1
            continue
        if not (bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]):
            counts["outside"] += 1
            continue
        mmsi = gfw._mmsi(v.get("ssvid"))
        if mmsi is None:
            counts["no_vessel"] += 1
            continue
        # Published once the event has ended: the leakage clock runs from the UTC day it ended.
        avail, q = gfw.available(((end if end is not None else start) // DAY_MS + 1) * DAY_MS, recv_ts)
        rg = e.get("regions") or {}
        f = e.get("fishing") or {}
        dist = e.get("distances") or {}
        bb = e.get("boundingBox")
        ebox = (min(bb[0], bb[2]), min(bb[1], bb[3]), max(bb[0], bb[2]), max(bb[1], bb[3])) \
            if bb and len(bb) == 4 else None
        attrs = {
            "event_id": e["id"], "vessel_id": v.get("id"), "name": v.get("name"), "flag": v.get("flag"),
            "gear_type": gear.get(v.get("id") or ""), "region": region,
            # Region tags are kept even when empty: [] means GFW checked and the event is outside every MPA.
            "eez": rg.get("eez") or [], "eez12nm": rg.get("eez12Nm") or [], "mpa": rg.get("mpa") or [],
            "mpa_no_take": rg.get("mpaNoTake") or [], "mpa_no_take_partial": rg.get("mpaNoTakePartial") or [],
            "protectedseas": rg.get("protectedseas") or [], "rfmo": rg.get("rfmo") or [],
            "high_seas": rg.get("highSeas") or [],
            "potential_risk": f.get("potentialRisk"),
            "authorization_status": f.get("vesselPublicAuthorizationStatus"),
            "avg_speed_kn": _f(f.get("averageSpeedKnots")), "distance_km": _f(f.get("totalDistanceKm")),
            "shore_km": _f(dist.get("startDistanceFromShoreKm")), "port_km": _f(dist.get("startDistanceFromPortKm")),
        }
        oid = f"gfw:fishing:{e['id']}"
        out[oid] = Observation(
            id=oid, src="gfw", kind="fishing", ts=start, end_ts=end, recv_ts=recv_ts, available_ts=avail,
            mmsi=mmsi, lat=float(lat), lon=float(lon), bbox=ebox,
            value=(end - start) / 3_600_000 if end is not None and end >= start else None,
            attrs={k: x for k, x in attrs.items() if x is not None}, q=list(q))
    return list(out.values()), counts


def parse_gear(body: dict) -> dict[str, str]:
    """/vessels identity entries -> {vessel id: gear type}, the most recent classification of the combined record.
    Every id GFW lists for the vessel (self-reported and combined) maps to it, since events carry either."""
    out = {}
    for ent in body.get("entries", []):
        info = ent.get("combinedSourcesInfo") or []
        gts = [g for c in info for g in (c.get("geartypes") or []) if g.get("name")]
        if not gts:
            continue
        name = max(gts, key=lambda g: g.get("yearTo") or 0)["name"]
        ids = [c.get("vesselId") for c in info] + [s.get("id") for s in ent.get("selfReportedInfo") or []]
        for i in ids:
            if i:
                out[i] = name
    return out


def fetch_window(client: gfw.Client, bbox, start: date, raw_sink=None) -> tuple[dict, dict[str, str]]:
    """Every fishing event overlapping the week in the region, all pages, plus the gear types of its vessels."""
    entries: list[dict] = []
    offset = 0
    body = {"datasets": [DATASET], "startDate": start.isoformat(),
            "endDate": (start + timedelta(WINDOW_DAYS)).isoformat(), "geometry": poly(bbox)}
    while True:
        d = client._post("/events", {"limit": gfw.PAGE, "offset": offset}, body)
        entries += d.get("entries", [])
        nxt = d.get("nextOffset")
        if not nxt or nxt <= offset or len(entries) >= MAX_EVENTS:
            out = {"entries": entries, "total": d.get("total")}
            break
        offset = nxt
    if out["total"] and len(entries) < out["total"]:
        log.warning("fishing %s: kept %d of %d events (page cap)", start, len(entries), out["total"])
    if raw_sink:
        raw_sink("events_fishing", out)
    gear: dict[str, str] = {}
    ids = sorted({(e.get("vessel") or {}).get("id") for e in entries} - {None, ""})
    for i in range(0, len(ids), VESSEL_BATCH):
        q = [("datasets[0]", IDENTITY)] + [(f"ids[{k}]", v) for k, v in enumerate(ids[i:i + VESSEL_BATCH])]
        try:
            vb = client._get("/vessels", q)
        except Exception as e:   # gear type is an extra: the events still land without it
            log.warning("fishing %s: vessel lookup failed (%s); gear type left out", start, e)
            break
        if raw_sink:
            raw_sink(f"vessels_{i // VESSEL_BATCH}", vb)
        gear |= parse_gear(vb)
    return out, gear


async def run_window(pool, start: date, regions: list[str], *, client, force=False, data_dir=None) -> dict:
    """Fetch one week for every requested region whose ledger row is not settled (one region at a time)."""
    s_ms = day_ms(start)
    e_ms = s_ms + WINDOW_DAYS * DAY_MS
    res: dict[str, Any] = {"src": "gfw", "stream": STREAM, "week": start.isoformat(), "regions": {}}
    total, events = 0, 0
    for region in regions:
        now = now_ms()
        async with pool.acquire() as con:
            row = await schema.get_window(con, SPEC["src"], STREAM, region, s_ms)
        if not jobs.needs_fetch(row, e_ms, now, SPEC, force):
            res["regions"][region] = "skipped"
            continue
        rec_end = min(e_ms, now)
        try:
            raw = jobs.RawDump(data_dir, "gfw", f"{STREAM}/{region}", start)
            body, gear = await asyncio.to_thread(fetch_window, client, REGIONS[region], start, raw)
            obs, counts = parse_fishing(body, region, REGIONS[region], s_ms, e_ms, now, gear)
        except Exception as e:   # recorded and retried on the next run; never stops the other regions
            async with pool.acquire() as con:
                await schema.record_window(con, SPEC["src"], STREAM, region, s_ms, rec_end, now, 0, "error",
                                           f"{type(e).__name__}: {e}"[:500])
            log.warning("fishing %s %s failed: %s", region, start, e)
            res["regions"][region] = {"error": str(e)[:200]}
            res["error"] = True
            continue
        async with pool.acquire() as con:
            async with con.transaction():
                n = await schema.write_observations(con, obs)
                await schema.record_window(con, SPEC["src"], STREAM, region, s_ms, rec_end, now, len(obs), "ok")
        res["regions"][region] = {"observations": n, "gear_known": sum("gear_type" in o.attrs for o in obs),
                                  "in_mpa": sum(bool(o.attrs.get("mpa")) for o in obs), **counts}
        total += n
        events += counts["events"]
    if total or events:
        res |= {"observations": total, "events": events}
    if all(x == "skipped" for x in res["regions"].values()):
        res["skipped"] = True
    log.info("%s", res)
    return res


async def backfill(url: str, regions: list[str], start: date, end: date, *, force=False, data_dir=None) -> list[dict]:
    """Every week whose Monday-to-Sunday span overlaps [start, end] (inclusive days)."""
    pool = await jobs.connect(url)
    client = gfw.Client()
    out = []
    try:
        w = window_start(start)
        while w <= end:
            out.append(await run_window(pool, w, regions, client=client, force=force, data_dir=data_dir))
            w += timedelta(WINDOW_DAYS)
    finally:
        client.close()
        await pool.close()
    return out


async def poll(url: str, regions: list[str], *, once=False, data_dir=None) -> list[dict]:
    """The current week and the ones before it that GFW may still be filling, then sleep; forever unless once."""
    pool = await jobs.connect(url)
    client = gfw.Client()
    out = []
    try:
        while True:
            newest = window_start(utc_today())
            for k in range(SPEC["lookback_windows"] - 1, -1, -1):
                out.append(await run_window(pool, newest - timedelta(WINDOW_DAYS * k), regions, client=client,
                                            data_dir=data_dir))
            if once:
                return out
            await asyncio.sleep(min(SPEC["refetch_ms"] / 1000, 1800))
    finally:
        client.close()
        await pool.close()


async def backfill_back(url: str, regions: list[str], *, until: date, max_db_gb: float = jobs.DEFAULT_MAX_DB_GB,
                        data_dir=None, newest: date | None = None, empty_stop: int = 4) -> dict:
    """From the current week backwards until `until`, `empty_stop` weeks in a row with no event in any region, or the
    size cap. Settled weeks are skipped, so a restart resumes; one transaction per region and week, so Ctrl+C is safe."""
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
            r = await run_window(pool, w, regions, client=client, data_dir=data_dir)
            totals["weeks"] += 1
            totals["observations"] += r.get("observations", 0)
            totals["errors"] += bool(r.get("error"))
            if not r.get("skipped") and not r.get("error"):
                empty = 0 if r.get("events") else empty + 1
            if empty >= empty_stop:
                stopped = f"{empty} consecutive weeks with no fishing events (history ends near {w})"
            w -= timedelta(WINDOW_DAYS)
            if not stopped and w + timedelta(WINDOW_DAYS - 1) < until:
                stopped = f"reached --until {until}"
    finally:
        client.close()
        await pool.close()
    return {"src": "gfw", "stream": STREAM, "oldest_week": (w + timedelta(WINDOW_DAYS)).isoformat(),
            "stopped": stopped, **totals}
