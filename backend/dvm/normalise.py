"""normalise(envelope) -> canonical records. The only code that knows source formats (06 section 3.1)."""
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Optional

from dvm.models import Envelope, PositionReport, Record, VesselStatic

POSITION_TYPES = {"PositionReport": "A", "StandardClassBPositionReport": "B", "ExtendedClassBPositionReport": "B"}
STATIC_TYPES = ("ShipStaticData", "StaticDataReport")
SUBSCRIBED_TYPES = [*POSITION_TYPES, *STATIC_TYPES]


def rebuild_ts(recv_ts: int, sec: Optional[int]) -> tuple[int, str]:
    """Full UTC ms from second-of-minute and receive time. shortcut: assumes delay < ~55 s (06 section 1.3)."""
    if sec is None or not 0 <= sec <= 59:
        return recv_ts, "recv_only"
    cand = recv_ts - recv_ts % 60_000 + sec * 1000
    if cand > recv_ts + 5_000:
        cand -= 60_000
    return cand, "rebuilt"


def parse_time_utc(s: str) -> int:
    """AISStream "2026-11-07 16:15:01.234567 +0000 UTC" (Go format, up to 9 fraction digits) -> epoch ms."""
    head = s.split(" +")[0]
    if "." in head:
        whole, frac = head.split(".", 1)
        head = f"{whole}.{frac[:6].ljust(6, '0')}"   # Python parses exactly microseconds
    return int(datetime.fromisoformat(head).replace(tzinfo=timezone.utc).timestamp() * 1000)


def is_vessel_mmsi(mmsi: int) -> bool:
    """9 digits with a ship MID (200-799): drops base stations, AtoN, SAR aircraft, handhelds, SART/MOB/EPIRB."""
    return 100_000_000 <= mmsi <= 999_999_999 and 200 <= mmsi // 1_000_000 <= 799


def type_group(ship_type: Optional[int]) -> str:
    if not ship_type:
        return "unknown"
    if 80 <= ship_type <= 89: return "tanker"
    if 70 <= ship_type <= 79: return "cargo"
    if 60 <= ship_type <= 69: return "passenger"
    if ship_type == 30: return "fishing"
    if ship_type == 35: return "military"
    if ship_type in (36, 37): return "pleasure"
    if ship_type in (31, 32) or 50 <= ship_type <= 59: return "tug_special"
    return "other"


def clean(s: Any) -> Optional[str]:
    """AIS text: trim padding '@' and spaces, upper case; empty becomes None."""
    if not isinstance(s, str):
        return None
    s = s.replace("@", " ").strip().upper()
    return s or None


def imo_ok(imo: int) -> bool:
    d = [int(c) for c in f"{imo:07d}"]
    return len(d) == 7 and sum(x * (7 - i) for i, x in enumerate(d[:6])) % 10 == d[6]


def eta_ms(eta: Any, ts: int) -> Optional[int]:
    """AIS ETA has no year: take the first matching date at or after ts - 1 day."""
    if not isinstance(eta, dict):
        return None
    mo, d, h, mi = (eta.get(k) for k in ("Month", "Day", "Hour", "Minute"))
    if not mo or not d or h is None or mi is None or h >= 24 or mi >= 60:
        return None
    floor = ts - 86_400_000
    year = datetime.fromtimestamp(floor / 1000, timezone.utc).year
    for y in (year, year + 1):
        try:
            t = int(datetime(y, mo, d, h, mi, tzinfo=timezone.utc).timestamp() * 1000)
        except ValueError:
            return None   # e.g. 30 February
        if t >= floor:
            return t
    return None


def _num(v: Any, na: float) -> Optional[float]:
    return None if v is None or v >= na else float(v)


def _aisstream(env: Envelope) -> list[Record]:
    raw = env.raw if isinstance(env.raw, dict) else {}
    mtype = raw.get("MessageType")
    body = (raw.get("Message") or {}).get(mtype)
    meta = raw.get("MetaData") or {}
    if not isinstance(body, dict):
        return []
    mmsi = body.get("UserID") or meta.get("MMSI")
    if not isinstance(mmsi, int) or not is_vessel_mmsi(mmsi):
        return []
    t = meta.get("time_utc") or meta.get("TimeUtc")
    try:
        recv_ts = parse_time_utc(t) if isinstance(t, str) else env.recv_ts
    except ValueError:
        recv_ts = env.recv_ts
    out: list[Record] = []
    common = {"mmsi": mmsi, "src": "aisstream"}

    if mtype in POSITION_TYPES:
        lat, lon = body.get("Latitude"), body.get("Longitude")
        if (body.get("Valid") is not False and isinstance(lat, (int, float)) and isinstance(lon, (int, float))
                and -90 <= lat <= 90 and -180 <= lon <= 180):
            ts, quality = rebuild_ts(recv_ts, body.get("Timestamp"))
            sog, cog = _num(body.get("Sog"), 102.3), _num(body.get("Cog"), 360)
            hdg = body.get("TrueHeading")
            hdg = None if hdg is None or hdg >= 360 else int(hdg)
            nav = body.get("NavigationalStatus")
            q = [f for f, v in (("sog_na", sog), ("cog_na", cog), ("hdg_na", hdg)) if v is None]
            if quality == "recv_only":
                q.append("ts_recv_only")
            out.append(PositionReport(
                **common, ts=ts, recv_ts=recv_ts, lat=float(lat), lon=float(lon), sog_kn=sog, cog_deg=cog,
                heading_deg=hdg, nav_status=None if nav is None or nav == 15 else nav,
                cls=POSITION_TYPES[mtype], msg_type=body.get("MessageID") or 0, ts_quality=quality, q=q))

    static: dict[str, Any] = {}
    if mtype == "ShipStaticData":
        imo = body.get("ImoNumber") or None
        static = dict(imo=imo, name=clean(body.get("Name")), callsign=clean(body.get("CallSign")),
                      ship_type=body.get("Type") or None, dim=body.get("Dimension"),
                      draught_m=body.get("MaximumStaticDraught") or None,   # assumed metres (06: verify live)
                      destination=clean(body.get("Destination")), eta_utc=eta_ms(body.get("Eta"), recv_ts))
    elif mtype == "StaticDataReport":
        a, b = body.get("ReportA") or {}, body.get("ReportB") or {}
        if a.get("Valid"):
            static["name"] = clean(a.get("Name"))
        if b.get("Valid"):
            static.update(callsign=clean(b.get("CallSign")), ship_type=b.get("ShipType") or None, dim=b.get("Dimension"))
    elif mtype == "ExtendedClassBPositionReport":
        static = dict(name=clean(body.get("Name")), ship_type=body.get("Type") or None, dim=body.get("Dimension"))
    elif mtype in POSITION_TYPES and clean(meta.get("ShipName")):
        static = {"name": clean(meta.get("ShipName"))}   # partial: the pipeline keeps it only if the name changed

    if any(v is not None for v in static.values()):
        dim = static.pop("dim", None) or {}
        da, db, dc, dd = (dim.get(k) for k in "ABCD")
        imo = static.pop("imo", None)
        q = ["imo_bad_checksum"] if imo and not imo_ok(imo) else []
        out.append(VesselStatic(
            **common, ts=recv_ts, recv_ts=recv_ts, imo=imo, **static,
            type_group=type_group(static.get("ship_type")),
            dim_a_m=da, dim_b_m=db, dim_c_m=dc, dim_d_m=dd,
            length_m=(da + db) if da is not None and db is not None and da + db > 0 else None,
            beam_m=(dc + dd) if dc is not None and dd is not None and dc + dd > 0 else None,
            mid=mmsi // 1_000_000, q=q))
    return out


def normalise(env: Envelope) -> list[Record]:
    """Dispatch on source. Unknown sources and message types yield nothing."""
    if env.src == "aisstream":
        return _aisstream(env)
    return []
