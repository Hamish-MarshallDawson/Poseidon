"""GFW fishing events for our four regions, straight from the GFW API, cached as Parquet per region and month (#157).

    ml/.venv/bin/python -m ml.fishing.fetch [--out DIR] [--minutes 15] [--until 2026-11] [--months 36]

Polite: one request at a time through the backend's `gfw.Client` (0.3 s pause, backoff on 429 and 5xx), because the
live server shares the token. Months are fetched newest first until the time budget runs out; a month already cached
is skipped unless it is the newest two (GFW still adds events to them). `/events` selects by overlap, so an event
spanning a month boundary appears in both files; `load` dedups by event id.

`available_ts` (the leakage clock) follows `gfw.available`: an event is published once it has ended, so the clock
runs from the end of its last UTC day plus GFW's 4-day lag (or our fetch time, if we fetched it within 8 days).
Token: `GFW_API_TOKEN` from the repo `.env`, never printed. GFW data is CC BY-NC 4.0.
"""
from __future__ import annotations

import argparse
import json
import os
import time
from datetime import date
from pathlib import Path

import pandas as pd

import ml  # noqa: F401  (backend on sys.path)

DEFAULT_OUT = Path(os.getenv("FISHING_DATA", "/home/aiden/data/poseidon/fishing"))
DATASET = "public-global-fishing-events:latest"
LIST_COLS = {"eez": "eez", "eez12Nm": "eez12nm", "mpa": "mpa", "mpaNoTake": "mpa_no_take",
             "mpaNoTakePartial": "mpa_no_take_partial", "protectedseas": "protectedseas", "rfmo": "rfmo",
             "highSeas": "high_seas"}


def _f(v):
    try:
        return float(v)
    except (TypeError, ValueError):
        return None


def flatten(entries: list[dict], region: str, recv_ts: int) -> pd.DataFrame:
    """GFW fishing events -> one row each. List-valued regions are '|'-joined strings ('' when empty)."""
    from dvm.sources import gfw
    from dvm.sources.common import DAY_MS, iso_ms
    rows = []
    for e in entries:
        v = e.get("vessel") or {}
        mmsi = gfw._mmsi(v.get("ssvid"))
        start, end = iso_ms(e.get("start")), iso_ms(e.get("end"))
        pos = e.get("position") or {}
        if mmsi is None or start is None or not e.get("id"):
            continue
        known = end if end is not None else start
        avail, _ = gfw.available((known // DAY_MS + 1) * DAY_MS, recv_ts)
        reg = e.get("regions") or {}
        fi = e.get("fishing") or {}
        dist = e.get("distances") or {}
        r = {"event_id": e["id"], "mmsi": mmsi, "vessel_id": v.get("id"), "name": v.get("name"),
             "flag": v.get("flag") or "UNK", "vessel_type": v.get("type"), "region": region,
             "ts": start, "end_ts": end, "available_ts": avail, "recv_ts": recv_ts,
             "lat": _f(pos.get("lat")), "lon": _f(pos.get("lon")),
             "hours": (end - start) / 3_600_000 if end else None,
             "potential_risk": fi.get("potentialRisk"),
             "authorization_status": fi.get("vesselPublicAuthorizationStatus") or "unknown",
             "avg_speed_kn": _f(fi.get("averageSpeedKnots")), "distance_km": _f(fi.get("totalDistanceKm")),
             "shore_km": _f(dist.get("startDistanceFromShoreKm")), "port_km": _f(dist.get("startDistanceFromPortKm"))}
        for k, c in LIST_COLS.items():
            r[c] = "|".join(str(x) for x in (reg.get(k) or []))
        rows.append(r)
    df = pd.DataFrame(rows)
    if not df.empty:
        df["potential_risk"] = df["potential_risk"].astype("boolean")
    return df


def fetch_month(client, region: str, bbox, month: date) -> tuple[pd.DataFrame, dict]:
    from dvm.sources.common import now_ms, poly
    nxt = (pd.Timestamp(month) + pd.offsets.MonthBegin(1)).date()
    body = {"datasets": [DATASET], "startDate": month.isoformat(), "endDate": nxt.isoformat(), "geometry": poly(bbox)}
    entries, offset, total = [], 0, None
    while True:
        d = client._post("/events", {"limit": 1000, "offset": offset}, body)
        entries += d.get("entries", [])
        total = d.get("total")
        n = d.get("nextOffset")
        if not n or n <= offset or len(entries) >= 50_000:
            break
        offset = n
    return flatten(entries, region, now_ms()), {"events": len(entries), "total": total}


def load(data: Path = DEFAULT_OUT) -> pd.DataFrame:
    """Every cached event, one row per event id (the newest fetch wins), sorted by mmsi and ts."""
    files = sorted((data / "events").glob("*/*.parquet"))
    if not files:
        raise FileNotFoundError(f"no fishing events cached under {data}/events; run python -m ml.fishing.fetch")
    df = pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)
    df = df.sort_values("recv_ts").drop_duplicates("event_id", keep="last")
    return df.sort_values(["mmsi", "ts"], kind="stable").reset_index(drop=True)


def main() -> None:
    from dotenv import load_dotenv
    load_dotenv(ml.REPO / ".env")
    from dvm.sources import gfw
    from dvm.sources.common import REGIONS
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--minutes", type=float, default=15)
    ap.add_argument("--until", default=date.today().strftime("%Y-%m"), help="newest month, YYYY-MM")
    ap.add_argument("--months", type=int, default=36, help="how far back at most")
    ap.add_argument("--regions", default=",".join(REGIONS))
    a = ap.parse_args()
    deadline = time.time() + a.minutes * 60
    months = list(pd.period_range(end=pd.Period(a.until, "M"), periods=a.months, freq="M"))[::-1]
    manifest_p = a.out / "manifest.json"
    manifest = json.loads(manifest_p.read_text()) if manifest_p.exists() else {}
    client = gfw.Client()
    try:
        for i, m in enumerate(months):
            for region in a.regions.split(","):
                f = a.out / "events" / region / f"{m}.parquet"
                if f.exists() and i >= 2:
                    continue
                if time.time() > deadline:
                    print(json.dumps({"stopped": "time budget", "next_month": str(m), "calls": client.calls}))
                    return
                t = time.time()
                df, info = fetch_month(client, region, REGIONS[region], m.start_time.date())
                f.parent.mkdir(parents=True, exist_ok=True)
                df.to_parquet(f, index=False)
                manifest.setdefault(region, {})[str(m)] = info | {"rows": len(df), "fetched": date.today().isoformat()}
                manifest_p.write_text(json.dumps(manifest, indent=1, sort_keys=True))
                print(json.dumps({"region": region, "month": str(m), **info, "s": round(time.time() - t, 1)}),
                      flush=True)
    finally:
        client.close()
    print(json.dumps({"done": True, "calls": client.calls}))


if __name__ == "__main__":
    main()
