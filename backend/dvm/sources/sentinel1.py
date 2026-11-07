"""Sentinel-1 scene catalogue (radar coverage) from Element 84 Earth Search -> observations kind "radar_scene".

No pixels are read and no ships are detected: a scene says "radar looked at this footprint between start and end".
Earth Search `sentinel-1-grd` geometry matches the product (the Planetary Computer `sentinel-1-grd` location
metadata is wrong; don't swap the endpoint without switching to `sentinel-1-rtc`). `created` is when the item was
catalogued, so it is the real available time: 1 to 13 h after sensing in a live check on 7 Nov 2026.
"""
from __future__ import annotations

from typing import Optional

import httpx

from dvm.sources.common import USER_AGENT, Observation, iso_ms

SEARCH = "https://earth-search.aws.element84.com/v1/search"
COLLECTION = "sentinel-1-grd"
PAGE = 250
MAX_PAGES = 40


def parse_items(items: list[dict], recv_ts: int) -> list[Observation]:
    out = []
    for it in items:
        p = it.get("properties") or {}
        start = iso_ms(p.get("start_datetime")) or iso_ms(p.get("datetime"))
        if start is None or not it.get("id"):
            continue
        end = iso_ms(p.get("end_datetime"))
        created = iso_ms(p.get("created"))
        bb = it.get("bbox")
        bbox = (bb[0], bb[1], bb[2], bb[3]) if bb and len(bb) >= 4 else None
        c = p.get("proj:centroid") or {}
        lat: Optional[float] = c.get("lat")
        lon: Optional[float] = c.get("lon")
        if (lat is None or lon is None) and bbox:
            lat, lon = (bbox[1] + bbox[3]) / 2, (bbox[0] + bbox[2]) / 2
        attrs = {k.split(":")[-1]: p.get(k) for k in (
            "platform", "sar:instrument_mode", "sar:polarizations", "sat:orbit_state", "sat:relative_orbit",
            "sat:absolute_orbit", "s1:product_timeliness", "s1:product_identifier") if p.get(k) is not None}
        vv = (it.get("assets") or {}).get("vv") or {}
        if vv.get("href"):
            attrs["vv_href"] = vv["href"]
        out.append(Observation(
            id=f"sentinel1:{it['id']}", src="sentinel1", kind="radar_scene", ts=start, end_ts=end, recv_ts=recv_ts,
            available_ts=created if created is not None else recv_ts, lat=lat, lon=lon, bbox=bbox,
            geom=it.get("geometry"), attrs=attrs, q=[] if created is not None else ["available_est"]))
    return out


def search(bbox, start_iso: str, end_iso: str, http: httpx.Client | None = None, raw_sink=None) -> list[dict]:
    """All items in [start, end) intersecting bbox, following the STAC `next` link (POST with a body)."""
    own = http is None
    http = http or httpx.Client(headers={"User-Agent": USER_AGENT}, timeout=90)
    try:
        body = {"collections": [COLLECTION], "bbox": list(bbox), "datetime": f"{start_iso}/{end_iso}", "limit": PAGE}
        url, method, items = SEARCH, "POST", []
        for _ in range(MAX_PAGES):
            r = http.request(method, url, json=body if method == "POST" else None)
            r.raise_for_status()
            d = r.json()
            if raw_sink:
                raw_sink(f"page{len(items) // PAGE}", d)
            items += d.get("features", [])
            nxt = next((l for l in d.get("links", []) if l.get("rel") == "next"), None)
            if not nxt or not d.get("features"):
                return items
            url, method = nxt["href"], nxt.get("method", "GET").upper()
            if method == "POST":
                body = {**body, **(nxt.get("body") or {})} if nxt.get("merge") else (nxt.get("body") or body)
        return items
    finally:
        if own:
            http.close()
