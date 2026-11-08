"""Global Fishing Watch v3 -> observations (presence, radar detections, events) and statics (identity).

One window = one region and one UTC day. `fetch_day` asks GFW for one day; `fetch_range` asks for a block of days at
once and splits the answers back into the same per-day windows, with the same rows. Checked live on 7 Nov 2026:
- 4Wings `group-by=VESSEL_ID` with `spatial-aggregation=false` returns 404 "temporarily unavailable", so per-vessel
  positions are out. What works: anonymous 0.01-degree cells (presence hours, radar detections matched or not) and
  per-vessel daily totals over the whole region (identity, hours, and for radar the detection times).
- /events takes one dataset per request; with two it ignored the geometry. Rows are still bbox-checked here.
Data is CC BY-NC 4.0: the attribution is in common.SOURCES and goes out with every API answer.
"""
from __future__ import annotations

import logging
import time
from collections import defaultdict
from datetime import date, timedelta
from typing import Any, Iterator, Optional

import httpx

from dvm.models import VesselStatic
from dvm.normalise import clean, imo_ok, is_vessel_mmsi
from dvm.sources.common import (DAY_MS, ISO3_TO_2, USER_AGENT, Observation, bbox_intersects, day_ms, days,
                                gfw_token, iso_ms, poly)

log = logging.getLogger(__name__)

BASE = "https://gateway.api.globalfishingwatch.org/v3"
PRESENCE = "public-global-presence:latest"
SAR = "public-global-sar-presence:latest"
EVENT_DATASETS = {
    "encounter": "public-global-encounters-events:latest",
    "loitering": "public-global-loitering-events:latest",
    "port_visit": "public-global-port-visits-events:latest",
}
CELL_DEG = 0.01           # HIGH spatial resolution
LAG_MS = 4 * DAY_MS       # nominal publication delay, used only to estimate available_ts for backfilled days
LIVE_WINDOW_MS = 8 * DAY_MS   # a day fetched within this long of its end counts as fetched "live"
PAGE = 1000
EVENT_CAP = 20_000   # per request and day: a runaway paging loop stops here (a busy Danish day has ~6,000 port visits)
PAUSE_S = 0.3   # between calls: one backfill must never look like a burst to GFW

TYPE_GROUP = {"CARGO": "cargo", "CARRIER": "cargo", "TANKER": "tanker", "BUNKER": "tanker", "PASSENGER": "passenger",
              "FISHING": "fishing", "OTHER_NON_FISHING": "other", "SEISMIC_VESSEL": "other", "SUPPORT": "other",
              "GEAR": "other", "DISCREPANCY": "unknown", "INACTIVE": "unknown", "INSUFFICIENT_DATA": "unknown"}


def available(day_end: int, recv_ts: int) -> tuple[int, list[str]]:
    """When the provider published a day. Polled live: our first fetch. Backfilled: the end of the day plus the lag."""
    if recv_ts - day_end <= LIVE_WINDOW_MS:
        return recv_ts, []
    return day_end + LAG_MS, ["available_est"]


def _rows(body: dict) -> list[dict]:
    return [x for e in body.get("entries", []) for v in e.values() for x in (v or [])]


def _mmsi(v: Any) -> Optional[int]:
    try:
        m = int(str(v).strip())
    except (TypeError, ValueError):
        return None
    return m if is_vessel_mmsi(m) else None


def _imo(v: Any) -> Optional[int]:
    try:
        i = int(str(v).strip())
    except (TypeError, ValueError):
        return None
    return i if 1_000_000 <= i <= 9_999_999 else None


def parse_cells(body: dict, kind: str, matched: Optional[bool], day: date, recv_ts: int) -> list[Observation]:
    """Anonymous 0.01-degree cells: presence hours or radar detections, with the distinct-vessel count."""
    start = day_ms(day)
    avail, q = available(start + DAY_MS, recv_ts)
    tag = "pres" if kind == "ais_presence" else ("sar-m" if matched else "sar-u" if matched is False else "sar")
    out = []
    for r in _rows(body):
        lat, lon = r.get("lat"), r.get("lon")
        if lat is None or lon is None:
            continue
        val = r.get("hours") if kind == "ais_presence" else r.get("detections")
        out.append(Observation(
            id=f"gfw:{tag}:{r.get('date', day.isoformat())}:{lat:.2f}:{lon:.2f}", src="gfw", kind=kind,
            ts=start, end_ts=start + DAY_MS, recv_ts=recv_ts, available_ts=avail, lat=float(lat), lon=float(lon),
            bbox=(lon, lat, round(lon + CELL_DEG, 6), round(lat + CELL_DEG, 6)), cell_deg=CELL_DEG,
            value=float(val) if val is not None else None, n=r.get("vesselIDs"), matched=matched,
            q=[*q, "cell_level"]))
    return out


def parse_vessels(body: dict, kind: str, region: str, bbox, day: date, recv_ts: int
                  ) -> tuple[list[Observation], list[VesselStatic]]:
    """Per-vessel totals over the region for the day, plus one identity row per vessel."""
    start = day_ms(day)
    avail, q = available(start + DAY_MS, recv_ts)
    obs, statics = [], []
    for r in _rows(body):
        vid = r.get("vesselId") or ""
        mmsi = _mmsi(r.get("mmsi"))
        val = r.get("hours") if kind == "ais_presence" else r.get("detections")
        attrs = {k: r.get(k) for k in ("vesselId", "mmsi", "shipName", "flag", "imo", "vesselType", "geartype",
                                       "speed", "entryTimestamp", "exitTimestamp") if r.get(k) not in (None, "")}
        attrs["region"] = region
        obs.append(Observation(
            id=f"gfw:{'presv' if kind == 'ais_presence' else 'sarv'}:{day.isoformat()}:{region}:{vid or r.get('mmsi')}",
            # ts is the day, not entry: entry can be revised as late data lands, and ts is part of the key.
            src="gfw", kind=kind, ts=start, end_ts=start + DAY_MS, recv_ts=recv_ts,
            available_ts=avail, mmsi=mmsi, bbox=tuple(bbox), value=float(val) if val is not None else None,
            matched=True if kind == "sar_detection" else None, attrs=attrs, q=[*q, "region_level"]))
        if mmsi is None:
            continue
        imo = _imo(r.get("imo"))
        flag3 = (r.get("flag") or "").upper()
        statics.append(VesselStatic(
            mmsi=mmsi, ts=start, recv_ts=avail, imo=imo, name=clean(r.get("shipName")),
            callsign=clean(r.get("callsign")), type_group=TYPE_GROUP.get((r.get("vesselType") or "").upper(), "unknown"),
            mid=mmsi // 1_000_000, flag_iso2=ISO3_TO_2.get(flag3), src="gfw",
            q=["imo_bad_checksum"] if imo and not imo_ok(imo) else []))
    return obs, statics


def parse_events(body: dict, kind: str, bbox, recv_ts: int, day: date) -> tuple[list[Observation], int]:
    """GFW events -> one observation each. Returns (rows, dropped) where dropped = outside bbox or not a vessel."""
    avail, q = available(day_ms(day) + DAY_MS, recv_ts)
    out, dropped = [], 0
    for e in body.get("entries", []):
        v = e.get("vessel") or {}
        mmsi = _mmsi(v.get("ssvid"))
        pos = e.get("position") or {}
        bb = e.get("boundingBox")
        ebox = (min(bb[0], bb[2]), min(bb[1], bb[3]), max(bb[0], bb[2]), max(bb[1], bb[3])) if bb and len(bb) == 4 \
            else None
        lat, lon = pos.get("lat"), pos.get("lon")
        inside = (lat is not None and bbox[0] <= lon <= bbox[2] and bbox[1] <= lat <= bbox[3]) or \
                 (ebox is not None and bbox_intersects(ebox, bbox))
        start = iso_ms(e.get("start"))
        if mmsi is None or not inside or start is None:
            dropped += 1
            continue
        end = iso_ms(e.get("end"))
        detail = e.get(e.get("type") or "") or {}
        if kind == "port_visit":   # the three anchorage objects are most of the bytes; keep what identifies the port
            detail = {k: detail.get(k) for k in ("visitId", "confidence", "durationHrs")} | {
                f"{p}_port": (detail.get(f"{p}Anchorage") or {}).get("name") for p in ("start", "end")} | {
                "port_id": (detail.get("startAnchorage") or {}).get("id"),
                "at_dock": (detail.get("startAnchorage") or {}).get("atDock")}
        hours = detail.get("durationHours") or detail.get("totalTimeHours") or \
            ((end - start) / 3_600_000 if end else None)
        attrs = {"event_id": e.get("id"), "vessel_id": v.get("id"), "name": v.get("name"), "flag": v.get("flag"),
                 "vessel_type": v.get("type"), "distances": e.get("distances"), "detail": detail}
        if kind == "encounter":
            attrs["other_vessel"] = (detail.get("vessel") or {})
        out.append(Observation(
            id=f"gfw:{kind}:{e.get('id')}", src="gfw", kind=kind, ts=start, end_ts=end, recv_ts=recv_ts,
            available_ts=avail, mmsi=mmsi, lat=lat, lon=lon, bbox=ebox,
            value=float(hours) if hours is not None else None,
            attrs={k: x for k, x in attrs.items() if x not in (None, {}, [])}, q=list(q)))
    return out, dropped


class Client:
    def __init__(self, token: str | None = None, timeout: float = 170):
        self.http = httpx.Client(headers={"Authorization": "Bearer " + (token or gfw_token()),
                                          "User-Agent": USER_AGENT}, timeout=timeout)
        self.calls = 0

    def close(self):
        self.http.close()

    def _post(self, path: str, params: dict, body: dict) -> dict:
        """POST with a polite pause, and backoff on 429 and 5xx. Errors carry GFW's text, never the request."""
        for attempt in range(4):
            time.sleep(PAUSE_S)
            self.calls += 1
            try:
                r = self.http.post(BASE + path, params=params, json=body)
            except httpx.TransportError as e:
                if attempt == 3:
                    raise RuntimeError(f"GFW {path}: {type(e).__name__}") from None
                time.sleep(10 * 3 ** attempt)
                continue
            if r.status_code == 429 or r.status_code >= 500:
                if attempt < 3:
                    time.sleep(10 * 3 ** attempt)   # 10, 30, 90 s
                    continue
            if r.status_code >= 400:
                raise RuntimeError(f"GFW {path} HTTP {r.status_code}: {r.text[:200]}")
            return r.json()
        raise RuntimeError(f"GFW {path}: retries exhausted")

    def report(self, dataset: str, bbox, day: date, *, vessels: bool, matched: Optional[bool] = None,
               last: Optional[date] = None) -> dict:
        """4Wings report for `day`, or for `day` to `last` inclusive (one entry per row and day, with `date`)."""
        q = {"datasets[0]": dataset, "date-range": f"{day.isoformat()},{((last or day) + timedelta(1)).isoformat()}",
             "format": "JSON", "temporal-resolution": "DAILY"}
        if vessels:
            q.update({"spatial-resolution": "LOW", "spatial-aggregation": "true", "group-by": "VESSEL_ID"})
        else:
            q.update({"spatial-resolution": "HIGH", "spatial-aggregation": "false"})
        if matched is not None:
            q["filters[0]"] = f"matched='{str(matched).lower()}'"
        return self._post("/4wings/report", q, {"geojson": poly(bbox)})

    def event_pages(self, dataset: str, bbox, day: date, last: Optional[date] = None) -> Iterator[dict]:
        """Pages of the events overlapping `day` (to `last` inclusive), at most EVENT_CAP per day of range."""
        cap = EVENT_CAP * (((last or day) - day).days + 1)
        body = {"datasets": [dataset], "startDate": day.isoformat(),
                "endDate": ((last or day) + timedelta(1)).isoformat(), "geometry": poly(bbox)}
        offset, n = 0, 0
        while True:
            d = self._post("/events", {"limit": PAGE, "offset": offset}, body)
            n += len(d.get("entries", []))
            yield d
            nxt = d.get("nextOffset")
            if not nxt or nxt <= offset or n >= cap:
                return
            offset = nxt

    def events(self, dataset: str, bbox, day: date) -> dict:
        entries, total = [], None
        for d in self.event_pages(dataset, bbox, day):
            entries += d.get("entries", [])
            total = d.get("total")
        return {"entries": entries, "total": total}


def fetch_day(client: Client, region: str, bbox, day: date, recv_ts: int, raw_sink=None
              ) -> tuple[list[Observation], list[VesselStatic], dict]:
    """Every GFW stream for one region and day. raw_sink(name, body) keeps the original responses."""
    obs: list[Observation] = []
    statics: list[VesselStatic] = []
    info: dict[str, Any] = {"dropped_events": 0}

    def keep(name, body):
        if raw_sink:
            raw_sink(name, body)
        return body

    obs += parse_cells(keep("presence_cells", client.report(PRESENCE, bbox, day, vessels=False)),
                       "ais_presence", None, day, recv_ts)
    o, s = parse_vessels(keep("presence_vessels", client.report(PRESENCE, bbox, day, vessels=True)),
                         "ais_presence", region, bbox, day, recv_ts)
    obs += o
    statics += s
    for m in (True, False):
        obs += parse_cells(keep(f"sar_cells_{'matched' if m else 'unmatched'}",
                                client.report(SAR, bbox, day, vessels=False, matched=m)),
                           "sar_detection", m, day, recv_ts)
    o, s = parse_vessels(keep("sar_vessels", client.report(SAR, bbox, day, vessels=True, matched=True)),
                         "sar_detection", region, bbox, day, recv_ts)
    obs += o
    statics += s
    for kind, ds in EVENT_DATASETS.items():
        o, dropped = parse_events(keep(f"events_{kind}", client.events(ds, bbox, day)), kind, bbox, recv_ts, day)
        obs += o
        info["dropped_events"] += dropped
    return _dedup(obs, statics, info)


def _dedup(obs: list[Observation], statics: list[VesselStatic], info: dict):
    # One identity row per vessel and day (presence and radar can both name it): keep the first.
    seen, uniq = set(), []
    for s in statics:
        if s.mmsi not in seen:
            seen.add(s.mmsi)
            uniq.append(s)
    # The same event can be listed by overlapping requests: keep one per id.
    by_id = {o.id: o for o in obs}
    return list(by_id.values()), uniq, info


def event_days(e: dict, first: date, last: date) -> list[date]:
    """The days of first..last whose one-day /events request lists `e`: those its [start, end) interval overlaps
    (checked live against single-day requests). An instant (no end, or end == start) belongs to the day it is in."""
    start = iso_ms(e.get("start"))
    if start is None:
        return []
    end = iso_ms(e.get("end"))
    out = []
    for d in days(first, last):
        lo = day_ms(d)
        hi = lo + DAY_MS
        if (end is None or end <= start) and lo <= start < hi or start < hi and end is not None and end > lo:
            out.append(d)
    return out


def fetch_range(client: Client, region: str, bbox, start_day: date, end_day: date, recv_ts: int, raw_sink=None
                ) -> dict[date, tuple[list[Observation], list[VesselStatic], dict]]:
    """fetch_day for every day of start_day..end_day (inclusive), with far fewer calls: the cell reports and the
    events are asked once for the whole block and split back into days. Each day gets exactly the rows, ids and
    fields fetch_day gives it. The vessel reports stay one call per day, because over a block GFW gives each
    vessel's entry and exit for the whole block instead of for the day.

    raw_sink(name, body) gets each block response once (`presence_cells`, `events_port_visit_p0`, ...), plus the
    per-day vessel responses as `<day>_presence_vessels` and `<day>_sar_vessels`."""
    if end_day < start_day:
        raise ValueError("end_day before start_day")
    span = days(start_day, end_day)
    obs: dict[date, list[Observation]] = {d: [] for d in span}
    statics: dict[date, list[VesselStatic]] = {d: [] for d in span}
    info: dict[date, dict[str, Any]] = {d: {"dropped_events": 0} for d in span}

    def keep(name, body):
        if raw_sink:
            raw_sink(name, body)
        return body

    def cells(name, dataset, kind, matched):
        body = keep(name, client.report(dataset, bbox, start_day, vessels=False, matched=matched, last=end_day))
        by_day: dict[date, list] = defaultdict(list)
        for r in _rows(body):
            d = date.fromisoformat(r["date"]) if r.get("date") else (start_day if start_day == end_day else None)
            if d is None or d not in obs:
                raise RuntimeError(f"GFW {name}: row outside {start_day}..{end_day}: {r.get('date')}")
            by_day[d].append(r)
        for d, rows in by_day.items():
            obs[d] += parse_cells({"entries": [{"rows": rows}]}, kind, matched, d, recv_ts)

    def vessels(name, dataset, kind, matched, d):
        o, s = parse_vessels(keep(f"{d.isoformat()}_{name}", client.report(dataset, bbox, d, vessels=True,
                                                                          matched=matched)),
                             kind, region, bbox, d, recv_ts)
        obs[d] += o
        statics[d] += s

    # Same order as fetch_day, so each day's lists come out in the same order too.
    cells("presence_cells", PRESENCE, "ais_presence", None)
    for d in span:
        vessels("presence_vessels", PRESENCE, "ais_presence", None, d)
    for m in (True, False):
        cells(f"sar_cells_{'matched' if m else 'unmatched'}", SAR, "sar_detection", m)
    for d in span:
        vessels("sar_vessels", SAR, "sar_detection", True, d)
    unplaced = 0
    for kind, ds in EVENT_DATASETS.items():
        # Page by page, so a block's ~50,000 Danish port visits are never all in memory as raw JSON at once.
        for i, page in enumerate(client.event_pages(ds, bbox, start_day, end_day)):
            keep(f"events_{kind}_p{i}", page)
            by_day = defaultdict(list)
            for e in page.get("entries", []):
                ds_ = event_days(e, start_day, end_day)
                if not ds_:
                    if iso_ms(e.get("start")) is None:
                        ds_ = span   # unplaceable; fetch_day would count it as dropped wherever it was listed
                    else:
                        unplaced += 1
                for d in ds_:
                    by_day[d].append(e)
            for d, entries in by_day.items():
                o, dropped = parse_events({"entries": entries}, kind, bbox, recv_ts, d)
                obs[d] += o
                info[d]["dropped_events"] += dropped
    if unplaced:
        log.warning("GFW %s %s..%s: %d events overlap no day of the block", region, start_day, end_day, unplaced)
    return {d: _dedup(obs[d], statics[d], info[d]) for d in span}
