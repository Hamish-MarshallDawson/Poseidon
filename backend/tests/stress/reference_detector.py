"""A deliberately small gap detector that follows 06 sections 2.4 and 5, used ONLY to check that the stress tests
themselves are right (run with --detector reference). It is not the product's detector; dvm/gaps.py is Jake's.

Rules (06, table in section 5): open when now - last_recv > max(floor_s, k * report_interval_s), floor 1800 s, k 20.
neighbours_heard: other vessels within 20 km of the last fix in the last 10 minutes; baseline: the 30 minutes before.
Flag: own_stall if it overlaps a stall; unknown if baseline is 0; deliberate_candidate if heard >= 3; else coverage_gap.
Closes on the next position with a later ts.
"""
from __future__ import annotations

import math
from collections import defaultdict, deque

from tests.stress.synth import km_between

CELL = 0.2   # index grid, degrees


def _key(lat, lon):
    return (math.floor(lat / CELL), math.floor(lon / CELL))


class ReferenceGapDetector:
    def __init__(self, floor_s=1800, k=20, radius_km=20.0, min_neighbours=3, recent_s=600, baseline_s=1800):
        self.floor_s, self.k, self.radius_km, self.min_n = floor_s, k, radius_km, min_neighbours
        self.recent_ms, self.baseline_ms = recent_s * 1000, baseline_s * 1000
        self.last = {}                      # mmsi -> (recv_ts, ts, lat, lon, sog, cog, nav)
        self.intervals = defaultdict(lambda: deque(maxlen=10))
        self.heard = defaultdict(deque)     # grid key -> deque[(recv_ts, mmsi)]
        self.open = {}                      # mmsi -> gap dict
        self.stalls = []

    def _near(self, lat, lon, t0, t1, exclude):
        dlat = self.radius_km / 111.32
        dlon = dlat / max(0.1, math.cos(math.radians(lat)))
        seen = set()
        for i in range(math.floor((lat - dlat) / CELL), math.floor((lat + dlat) / CELL) + 1):
            for j in range(math.floor((lon - dlon) / CELL), math.floor((lon + dlon) / CELL) + 1):
                for recv, mmsi, la, lo in self.heard.get((i, j), ()):
                    if t0 <= recv <= t1 and mmsi != exclude and mmsi not in seen and km_between(lat, lon, la, lo) <= self.radius_km:
                        seen.add(mmsi)
        return len(seen)

    def _flag(self, g, now):
        if any(s < now and e > g["start_recv"] for s, e in self.stalls):
            return "own_stall"
        if g["neighbours_baseline"] == 0:
            return "unknown"
        return "deliberate_candidate" if g["neighbours_heard"] >= self.min_n else "coverage_gap"

    def note_stall(self, start_ms, end_ms):
        self.stalls.append((start_ms, end_ms))

    def observe(self, rec):
        out = []
        prev = self.last.get(rec.mmsi)
        if prev and rec.recv_ts > prev[0]:
            self.intervals[rec.mmsi].append((rec.recv_ts - prev[0]) / 1000)
        g = self.open.get(rec.mmsi)
        if g and rec.ts > g["start_ts"]:
            dist = km_between(g["last_lat"], g["last_lon"], rec.lat, rec.lon)
            hours = max(1e-9, (rec.ts - g["start_ts"]) / 3_600_000)
            g = {**g, "version": g["version"] + 1, "state": "closed", "end_ts": rec.ts, "next_lat": rec.lat,
                 "next_lon": rec.lon, "implied_speed_kn": dist / 1.852 / hours, "duration_s": (rec.ts - g["start_ts"]) // 1000}
            g["coverage_flag"] = self._flag(g, rec.recv_ts)
            del self.open[rec.mmsi]
            out.append(self._public(g))
        if not prev or rec.ts >= prev[1]:
            self.last[rec.mmsi] = (rec.recv_ts, rec.ts, rec.lat, rec.lon, rec.sog_kn, rec.cog_deg, rec.nav_status)
        dq = self.heard[_key(rec.lat, rec.lon)]
        dq.append((rec.recv_ts, rec.mmsi, rec.lat, rec.lon))
        return out

    def tick(self, now):
        out = []
        horizon = now - self.baseline_ms - 3_600_000 * 3
        for dq in self.heard.values():
            while dq and dq[0][0] < horizon:
                dq.popleft()
        for mmsi, (recv, ts, lat, lon, sog, cog, nav) in self.last.items():
            iv = sorted(self.intervals[mmsi])
            interval = iv[len(iv) // 2] if iv else None
            limit_ms = max(self.floor_s, self.k * (interval or 0)) * 1000
            if mmsi in self.open or now - recv <= limit_ms:
                continue
            g = {"id": f"gap-{mmsi}-{ts}", "version": 1, "mmsi": mmsi, "state": "open", "start_ts": ts, "start_recv": recv,
                 "end_ts": None, "detected_at": now, "duration_s": (now - ts) // 1000, "expected_interval_s": interval,
                 "last_lat": lat, "last_lon": lon, "last_sog_kn": sog, "last_cog_deg": cog, "last_nav_status": nav,
                 "next_lat": None, "next_lon": None, "implied_speed_kn": None,
                 "neighbours_heard": self._near(lat, lon, now - self.recent_ms, now, mmsi),
                 "neighbours_baseline": self._near(lat, lon, recv - self.baseline_ms, recv, mmsi),
                 "cell_id": f"{math.floor(lat * 10)}_{math.floor(lon * 10)}", "src": "derived", "q": []}
            g["coverage_flag"] = self._flag(g, now)
            self.open[mmsi] = g
            out.append(self._public(g))
        return out

    @staticmethod
    def _public(g):
        return {k: v for k, v in g.items() if k != "start_recv"}
