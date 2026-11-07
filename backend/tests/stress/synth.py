"""Synthetic AIS world with known ground truth, emitted in AISStream's live JSON format.

Nothing here touches the network. Every scenario says exactly which ships went silent, when and why,
so the tests can compare the pipeline's output with the truth.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Optional

T0_MS = 1_794_067_200_000          # 2026-11-07 16:00:00 UTC
BOX = (59.6, 60.4, 24.0, 27.0)     # lat_min, lat_max, lon_min, lon_max (Gulf of Finland)
KM_PER_DEG_LAT = 111.32


def time_utc(ms: int) -> str:
    """AISStream MetaData.time_utc, e.g. '2026-11-07 16:15:01.234567 +0000 UTC'."""
    dt = datetime.fromtimestamp(ms / 1000, timezone.utc)
    return dt.strftime("%Y-%m-%d %H:%M:%S.%f") + " +0000 UTC"


def km_between(lat1, lon1, lat2, lon2) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0088 * math.asin(math.sqrt(a))


def offset(lat, lon, north_km, east_km):
    return lat + north_km / KM_PER_DEG_LAT, lon + east_km / (KM_PER_DEG_LAT * math.cos(math.radians(lat)))


@dataclass
class Ship:
    mmsi: int
    lat: float
    lon: float
    sog_kn: float
    cog_deg: float
    interval_s: float
    cls: str = "A"
    imo: Optional[int] = None
    name: str = "SYNTH"
    ship_type: int = 70
    nav_status: int = 0
    bounded: bool = True           # bounce off the box edges; open-sea ships are not bounded

    def step(self, dt_s: float) -> None:
        d_nm = self.sog_kn * dt_s / 3600
        self.lat, self.lon = offset(self.lat, self.lon, d_nm * 1.852 * math.cos(math.radians(self.cog_deg)),
                                    d_nm * 1.852 * math.sin(math.radians(self.cog_deg)))
        if self.bounded:
            lat0, lat1, lon0, lon1 = BOX
            if not lat0 <= self.lat <= lat1:
                self.cog_deg = (180 - self.cog_deg) % 360
                self.lat = min(max(self.lat, lat0), lat1)
            if not lon0 <= self.lon <= lon1:
                self.cog_deg = (360 - self.cog_deg) % 360
                self.lon = min(max(self.lon, lon0), lon1)


@dataclass
class Window:
    start_ms: int
    end_ms: int

    def has(self, t: int) -> bool:
        return self.start_ms <= t < self.end_ms


@dataclass
class Faults:
    """What goes wrong between the ship and our consumer. All optional."""
    switch_off: dict[int, Window] = field(default_factory=dict)            # mmsi -> silent window (the ship)
    holes: list[tuple[float, float, float, Window]] = field(default_factory=list)  # lat, lon, radius_km, window
    outages: list[Window] = field(default_factory=list)                      # receiver network down: nobody heard
    stalls: list[Window] = field(default_factory=list)                       # our own consumer dropped everything
    jams: list[tuple[float, float, float, Window]] = field(default_factory=list)   # GNSS jamming: positions jump
    loss_p: float = 0.0               # random message loss (collisions in busy cells)
    dup_p: float = 0.0                # message delivered more than once
    delay_max_s: float = 0.0          # AISStream relays the message late: time_utc is the late receipt time
    reorder_s: float = 0.0            # delivery order shuffled within this window
    skew_s: float = 0.0               # AISStream clock offset: time_utc = true time + skew
    interval_jitter: float = 0.1      # +/- fraction of the report interval


@dataclass
class World:
    ships: list[Ship]
    duration_s: float
    faults: Faults = field(default_factory=Faults)
    seed: int = 0
    static_every_s: float = 360

    def emit(self) -> tuple[list[tuple[int, dict]], dict]:
        """Returns (stream sorted by our receive time, truth). Each stream item is (recv_ms, raw AISStream dict)."""
        rng = random.Random(self.seed)
        f = self.faults
        end_ms = T0_MS + int(self.duration_s * 1000)
        out: list[tuple[int, dict]] = []
        truth = {"sent": {}, "silent": {}, "fixes": {}}   # fixes: mmsi -> [(ts, lat, lon)] of what was transmitted

        for ship in self.ships:
            t = T0_MS + int(rng.uniform(0, ship.interval_s) * 1000)
            last_static = T0_MS - int(rng.uniform(0, self.static_every_s) * 1000)
            prev = t
            fixes = truth["fixes"].setdefault(ship.mmsi, [])
            while t < end_ms:
                ship.step((t - prev) / 1000)
                prev = t
                lat, lon = ship.lat, ship.lon
                for jlat, jlon, r, w in f.jams:
                    if w.has(t) and km_between(lat, lon, jlat, jlon) <= r:
                        lat, lon = offset(lat, lon, rng.uniform(20, 80), rng.uniform(-80, 80))
                silent = (ship.mmsi in f.switch_off and f.switch_off[ship.mmsi].has(t))
                if not silent:
                    fixes.append((t, lat, lon))
                heard = not silent and not any(w.has(t) for w in f.outages) and not any(
                    w.has(t) and km_between(ship.lat, ship.lon, hl, ho) <= r for hl, ho, r, w in f.holes)
                if heard and rng.random() >= f.loss_p:
                    delay = rng.uniform(0, f.delay_max_s) if f.delay_max_s else 0.0
                    recv = t + int(delay * 1000)
                    raw = position_msg(ship, t, recv + int(f.skew_s * 1000), lat, lon)
                    for _ in range(1 + (rng.random() < f.dup_p) * rng.randint(1, 2)):
                        out.append((recv, raw))
                    if t - last_static >= self.static_every_s * 1000:
                        last_static = t
                        out.append((recv, static_msg(ship, recv + int(f.skew_s * 1000))))
                truth["sent"][ship.mmsi] = truth["sent"].get(ship.mmsi, 0) + 1
                jit = 1 + rng.uniform(-f.interval_jitter, f.interval_jitter)
                t += max(1000, int(ship.interval_s * jit * 1000))

        # Our own stalls drop whatever arrives in the window, after everything else.
        if f.stalls:
            out = [m for m in out if not any(w.has(m[0]) for w in f.stalls)]
        out.sort(key=lambda m: m[0])
        if f.reorder_s:
            out = _reorder(out, f.reorder_s, rng)
        truth["silent"] = {m: (w.start_ms, w.end_ms) for m, w in f.switch_off.items()}
        return out, truth


def _reorder(stream, window_s, rng):
    """Shuffle delivery inside a sliding window while keeping each item's own recv time."""
    keyed = [(recv + rng.uniform(0, window_s * 1000), recv, raw) for recv, raw in stream]
    keyed.sort(key=lambda k: k[0])
    return [(int(k[0]), k[2]) for k in keyed]


def position_msg(ship: Ship, ts_ms: int, time_utc_ms: int, lat: float, lon: float) -> dict:
    mtype = "PositionReport" if ship.cls == "A" else "StandardClassBPositionReport"
    body = {"MessageID": 1 if ship.cls == "A" else 18, "UserID": ship.mmsi, "Sog": round(ship.sog_kn, 1),
            "Cog": round(ship.cog_deg, 1), "TrueHeading": int(ship.cog_deg) % 360, "Latitude": round(lat, 6),
            "Longitude": round(lon, 6), "Timestamp": (ts_ms // 1000) % 60, "Valid": True}
    if ship.cls == "A":
        body["NavigationalStatus"] = ship.nav_status
    return {"MessageType": mtype,
            "MetaData": {"MMSI": ship.mmsi, "MMSI_String": str(ship.mmsi), "ShipName": ship.name,
                         "latitude": round(lat, 6), "longitude": round(lon, 6), "time_utc": time_utc(time_utc_ms)},
            "Message": {mtype: body}}


def static_msg(ship: Ship, time_utc_ms: int) -> dict:
    return {"MessageType": "ShipStaticData",
            "MetaData": {"MMSI": ship.mmsi, "ShipName": ship.name, "time_utc": time_utc(time_utc_ms)},
            "Message": {"ShipStaticData": {
                "MessageID": 5, "UserID": ship.mmsi, "ImoNumber": ship.imo or 0, "Name": ship.name, "CallSign": "SYN",
                "Type": ship.ship_type, "Dimension": {"A": 100, "B": 20, "C": 10, "D": 10},
                "MaximumStaticDraught": 8.5, "Destination": "HELSINKI",
                "Eta": {"Month": 11, "Day": 8, "Hour": 6, "Minute": 0}, "Valid": True}}}


# ---------- fleets ----------

def mmsi_for(i: int, mid: int = 230) -> int:
    return mid * 1_000_000 + 100_000 + i


def background(n: int, rng: random.Random, interval_s: float, start: int = 0) -> list[Ship]:
    lat0, lat1, lon0, lon1 = BOX
    return [Ship(mmsi_for(start + i), rng.uniform(lat0, lat1), rng.uniform(lon0, lon1), rng.uniform(6, 15),
                 rng.uniform(0, 360), interval_s, name=f"BG{start + i}") for i in range(n)]


def convoy(n: int, lat: float, lon: float, rng: random.Random, interval_s: float, start: int,
           spread_km: float = 8.0) -> list[Ship]:
    """n ships within spread_km of a point, same course and speed, so they stay neighbours for hours."""
    cog, sog = rng.uniform(0, 360), rng.uniform(8, 12)
    ships = []
    for i in range(n):
        la, lo = offset(lat, lon, rng.uniform(-spread_km, spread_km) / 1.5, rng.uniform(-spread_km, spread_km) / 1.5)
        ships.append(Ship(mmsi_for(start + i), la, lo, sog, cog, interval_s, name=f"CV{start + i}", bounded=False))
    return ships
