"""Digitraffic (Fintraffic) live AIS over MQTT-over-WebSocket -> positions and statics, like AISStream.

wss://meri.digitraffic.fi:443/mqtt, topics vessels-v2/<mmsi>/location and vessels-v2/<mmsi>/metadata, header
Digitraffic-User. Class A only, fishing boats removed by Fintraffic, no history: we can only accumulate from now.
Payload fields were checked live on 7 Nov 2026 (734 messages in 20 s): location `time` is the fix time in whole
seconds, median 0.5 s before our receive clock, so ts = time * 1000 with ts_quality "source".
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from typing import Any, Optional

from dvm.models import Envelope, PositionReport, Record, VesselStatic
from dvm.normalise import _num, clean, eta_ms, imo_ok, is_vessel_mmsi, type_group

log = logging.getLogger(__name__)

HOST, PORT, PATH = "meri.digitraffic.fi", 443, "/mqtt"
USER_HEADER = {"Digitraffic-User": "hacktheburgh/poseidon"}
TOPICS = [("vessels-v2/+/location", 0), ("vessels-v2/+/metadata", 0)]
LATE_MS = 120_000


def unpack_eta(eta: Any) -> Optional[dict]:
    """Bit-packed AIS ETA: month bits 19-16, day 15-11, hour 10-6, minute 5-0 (06 section 3.2)."""
    if not isinstance(eta, int) or eta <= 0:
        return None
    return {"Month": (eta >> 16) & 15, "Day": (eta >> 11) & 31, "Hour": (eta >> 6) & 31, "Minute": eta & 63}


def _location(mmsi: int, p: dict, recv_ts: int) -> list[Record]:
    lat, lon, t = p.get("lat"), p.get("lon"), p.get("time")
    if not (isinstance(lat, (int, float)) and isinstance(lon, (int, float)) and -90 <= lat <= 90
            and -180 <= lon <= 180 and isinstance(t, int)):
        return []
    ts = t * 1000
    sog, cog = _num(p.get("sog"), 102.3), _num(p.get("cog"), 360)
    hdg = p.get("heading")
    hdg = None if hdg is None or hdg >= 360 else int(hdg)
    nav = p.get("navStat")
    q = [f for f, v in (("sog_na", sog), ("cog_na", cog), ("hdg_na", hdg)) if v is None]
    if recv_ts - ts > LATE_MS:
        q.append("late")
    return [PositionReport(mmsi=mmsi, ts=ts, recv_ts=max(recv_ts, ts - 5000), lat=float(lat), lon=float(lon),
                           sog_kn=sog, cog_deg=cog, heading_deg=hdg,
                           nav_status=None if nav is None or nav == 15 else nav,
                           cls="A", msg_type=0, ts_quality="source", src="digitraffic", q=q)]


def _metadata(mmsi: int, p: dict, recv_ts: int) -> list[Record]:
    ts = p.get("timestamp") if isinstance(p.get("timestamp"), int) else recv_ts
    imo = p.get("imo") or None
    ship_type = p.get("type") or None
    da, db, dc, dd = (p.get(k) for k in ("refA", "refB", "refC", "refD"))
    draught = p.get("draught")
    dest = p.get("destination")
    return [VesselStatic(
        mmsi=mmsi, ts=ts, recv_ts=max(recv_ts, ts), imo=imo, name=clean(p.get("name")),
        callsign=clean(p.get("callSign")), ship_type=ship_type, type_group=type_group(ship_type),
        dim_a_m=da, dim_b_m=db, dim_c_m=dc, dim_d_m=dd,
        length_m=(da + db) if da is not None and db is not None and da + db > 0 else None,
        beam_m=(dc + dd) if dc is not None and dd is not None and dc + dd > 0 else None,
        draught_m=draught / 10 if isinstance(draught, (int, float)) and draught > 0 else None,
        destination=None if dest in (None, "0") else clean(dest), eta_utc=eta_ms(unpack_eta(p.get("eta")), ts),
        mid=mmsi // 1_000_000, src="digitraffic", q=["imo_bad_checksum"] if imo and not imo_ok(imo) else [])]


def normalise_digitraffic(env: Envelope) -> list[Record]:
    """Envelope raw = {"topic": "vessels-v2/<mmsi>/<kind>", "payload": {...}}. Proposed dispatch for normalise.py."""
    raw = env.raw if isinstance(env.raw, dict) else {}
    parts = str(raw.get("topic", "")).split("/")
    p = raw.get("payload")
    if len(parts) != 3 or not parts[1].isdigit() or not isinstance(p, dict):
        return []
    mmsi = int(parts[1])
    if not is_vessel_mmsi(mmsi):
        return []
    try:
        if parts[2] == "location":
            return _location(mmsi, p, env.recv_ts)
        if parts[2] == "metadata":
            return _metadata(mmsi, p, env.recv_ts)
    except (ValueError, TypeError) as e:   # a malformed field must not stop the stream
        log.debug("digitraffic: skipped %s: %s", raw.get("topic"), e)
    return []


class Dedup:
    """Drops an exact repeat of the last fix per MMSI (QoS 0 redelivery after a reconnect)."""

    def __init__(self):
        self.last: dict[tuple[int, str], int] = {}
        self.dropped = 0

    def keep(self, rec: Record) -> bool:
        key = (rec.mmsi, rec.kind)
        if self.last.get(key) == rec.ts:
            self.dropped += 1
            return False
        self.last[key] = rec.ts
        return True


class Stats:
    def __init__(self):
        self.received = self.positions = self.statics = 0
        self.connected = False
        self.last_error: str | None = None


async def run(sink, rawlog=None, seconds: float | None = None, stats: Stats | None = None) -> Stats:
    """Stream until cancelled (or for `seconds`). `sink(rec)` gets each canonical record; raw goes to rawlog first.

    paho runs its own network thread and reconnects with backoff; messages cross into asyncio via a queue.
    """
    import paho.mqtt.client as mqtt

    stats = stats or Stats()
    loop = asyncio.get_running_loop()
    queue: asyncio.Queue = asyncio.Queue(maxsize=100_000)

    def on_connect(c, _u, _f, rc, _p=None):
        stats.connected = not rc.is_failure
        if stats.connected:
            c.subscribe(TOPICS)
            log.info("Digitraffic connected, subscribed to %s", [t for t, _ in TOPICS])
        else:
            stats.last_error = f"connect refused: {rc}"

    def on_disconnect(_c, _u, _f, rc, _p=None):
        stats.connected = False
        stats.last_error = f"disconnected: {rc}"
        log.warning("Digitraffic disconnected (%s); paho reconnects with backoff", rc)

    def on_message(_c, _u, msg):
        recv = time.time_ns() // 1_000_000   # our clock first, before any parsing
        try:
            loop.call_soon_threadsafe(queue.put_nowait, (recv, msg.topic, msg.payload))
        except (asyncio.QueueFull, RuntimeError):
            pass

    c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"poseidon-{int(time.time())}", transport="websockets")
    c.ws_set_options(path=PATH, headers=USER_HEADER)
    c.tls_set()
    c.reconnect_delay_set(min_delay=2, max_delay=120)
    c.on_connect, c.on_disconnect, c.on_message = on_connect, on_disconnect, on_message
    c.connect_async(HOST, PORT, keepalive=60)
    c.loop_start()
    dedup = Dedup()
    deadline = None if seconds is None else loop.time() + seconds
    try:
        while deadline is None or loop.time() < deadline:
            try:
                recv, topic, payload = await asyncio.wait_for(queue.get(), timeout=1.0)
            except asyncio.TimeoutError:
                continue
            stats.received += 1
            try:
                body = json.loads(payload)
            except ValueError:
                continue
            raw = {"topic": topic, "payload": body}
            if rawlog is not None:
                rawlog.write("digitraffic", recv, raw)
            for rec in normalise_digitraffic(Envelope(src="digitraffic", recv_ts=recv, raw=raw)):
                if dedup.keep(rec):
                    if rec.kind == "pos":
                        stats.positions += 1
                    else:
                        stats.statics += 1
                    sink(rec)
    finally:
        c.disconnect()   # clean close frame first, then stop the network thread
        c.loop_stop()
    return stats
