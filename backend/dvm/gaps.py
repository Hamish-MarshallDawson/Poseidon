"""Gap detector: Class A ships that stop reporting, and whether the silence looks like the ship or like reception (#76).

Follows 06 sections 2.4, 2.9 and 5 with the first-version numbers Jake settled (7-8 Nov):
- Only Class A ships. A ship is Class A once it has sent any Class A fix; Class B ships are never tracked.
- Only moving ships: no gap opens when the last fix was at anchor or moored (nav status 1 or 5), slower than
  min_sog_kn, or when the ship's real displacement over its last 5 to 60 minutes works out below min_sog_kn (in port
  the reported speed jitters above 1 kn while the ship stays put). In the recorded 7 Nov log stopped ships were ~95%
  of all silences, mostly in port, where AISStream drops their slow reports, so they looked deliberate.
- A gap opens when `now - last_recv_ts > max(floor_s, k * report_interval_s)`, checked by `tick` on the recv_ts clock.
  `report_interval_s` is an exponentially weighted mean (alpha 0.2) of the time between consecutive fixes while
  moving, so the 30-minute floor decides for almost every ship.
- `coverage_flag`, in order:
  own_stall            our own ingest outages (`note_stall`) explain the silence: what is left of it outside them
                       is shorter than the ship's limit. A ten-second restart does not explain two hours of silence,
                       so that gap is judged on the rules below instead
  unknown              no other Class A ship was heard within radius_km in the baseline window (e.g. open sea)
  coverage_gap         fewer than min_neighbours heard within radius_km in the last recent_s, or most of the ships
                       that were near it before the silence have gone silent too (a receiver hole, not the ship).
                       This stands in for 06's "cell not dead": it follows the neighbours themselves, so a convoy
                       sailing out of a 0.1 degree cell does not make the cell look dead.
  deliberate_candidate otherwise: the area can still hear ships, this one went quiet
- The flag is re-checked every recheck_s while the gap is open, and kept as it was at the close (neighbours reappear
  at the same moment as the ship after an outage, so a count taken at the close would mislead).
- A gap closes on the next fix with a later `ts`. Every change is a new version of the same id (`gap-{mmsi}-{start_ts}`).

The detector is plain Python with no I/O: the Hub feeds it, stores what it returns and sends it to the browser.
Events are dicts with the `gaps` table's columns (store.APPEND_COLS["gaps"]).
"""
from __future__ import annotations

import math
from collections import deque
from dataclasses import dataclass, field
from typing import Callable, Iterable, Optional

from dvm.models import PositionReport

MIN_MS = 60_000
GRID_DEG = 0.2          # neighbour index buckets; a 0.1 degree coverage cell always sits inside one bucket
SAMPLE_MS = MIN_MS      # at most one index sample per ship, bucket and minute
AT_ANCHOR_OR_MOORED = {1, 5}   # AIS navigational status: 1 at anchor, 5 moored
FUTURE_SLACK_MS = 5 * MIN_MS   # a fix stamped further ahead of its receive time than this is ignored
TRACK_MS = 60 * MIN_MS         # recent track kept per ship (one point a minute) for the "really moving" test
TRACK_MIN_SPAN_MS = 5 * MIN_MS # the track must span this long before its displacement counts

# Our own ingest outages that are over and known (UTC): the team backend was down or restarting.
KNOWN_STALLS: list[tuple[int, int]] = [
    (1794080384000, 1794081008000),             # 7 Nov 19:39:44 to 19:50:08
    (1794088633000, 1794094560000),             # 7 Nov 21:57:13 to 23:36:00
]


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * 6371.0088 * math.asin(min(1.0, math.sqrt(a)))


def cell_id(lat: float, lon: float) -> str:
    return f"{math.floor(lat * 10)}_{math.floor(lon * 10)}"


def _bucket(lat: float, lon: float) -> tuple[int, int]:
    return math.floor(lat / GRID_DEG), math.floor(lon / GRID_DEG)


@dataclass
class _Ship:
    recv_ts: int
    ts: int
    lat: float
    lon: float
    sog: Optional[float]
    cog: Optional[float]
    nav: Optional[int]
    interval_s: Optional[float] = None
    quiet: bool = False      # silent past its limit while not moving: no gap was opened for this silence
    track: deque = field(default_factory=deque)   # (ts, lat, lon), one a minute, last TRACK_MS


class _Index:
    """Where Class A ships were heard recently: bucket -> mmsi -> deque[(recv_ts, lat, lon)], one sample a minute."""

    def __init__(self):
        self.b: dict[tuple[int, int], dict[int, deque]] = {}

    def add(self, mmsi: int, recv_ts: int, lat: float, lon: float) -> None:
        dq = self.b.setdefault(_bucket(lat, lon), {}).setdefault(mmsi, deque())
        if not dq or recv_ts - dq[-1][0] >= SAMPLE_MS or recv_ts < dq[-1][0]:
            dq.append((recv_ts, lat, lon))

    def prune(self, before: int) -> None:
        for key in list(self.b):
            ships = self.b[key]
            for m in list(ships):
                dq = ships[m]
                while dq and dq[0][0] < before:
                    dq.popleft()
                if not dq:
                    del ships[m]
            if not ships:
                del self.b[key]

    def near(self, lat: float, lon: float, radius_km: float, t0: int, t1: int, exclude: int) -> set[int]:
        """Other ships with a sample in [t0, t1] within radius_km of (lat, lon)."""
        dlat = radius_km / 111.32
        dlon = dlat / max(0.05, math.cos(math.radians(lat)))
        seen: set[int] = set()
        for i in range(math.floor((lat - dlat) / GRID_DEG), math.floor((lat + dlat) / GRID_DEG) + 1):
            for j in range(math.floor((lon - dlon) / GRID_DEG), math.floor((lon + dlon) / GRID_DEG) + 1):
                for m, dq in self.b.get((i, j), {}).items():
                    if m == exclude or m in seen:
                        continue
                    for recv, la, lo in reversed(dq):
                        if recv < t0:
                            break
                        if recv <= t1 and haversine_km(lat, lon, la, lo) <= radius_km:
                            seen.add(m)
                            break
        return seen


class GapDetector:
    def __init__(self, floor_s: float = 1800, k: float = 20, radius_km: float = 20.0, min_neighbours: int = 3,
                 recent_s: float = 600, baseline_s: float = 1800, peers_min: int = 3,
                 peers_silent_share: float = 0.5, recheck_s: float = 60,
                 max_open_s: float = 86_400, history_s: float = 3 * 3600, min_sog_kn: float = 1.0,
                 draught_of: Optional[Callable[[int], Optional[float]]] = None):
        self.floor_s, self.k, self.radius_km, self.min_n = floor_s, k, radius_km, min_neighbours
        self.recent_ms, self.baseline_ms = int(recent_s * 1000), int(baseline_s * 1000)
        self.peers_min, self.peers_silent_share = peers_min, peers_silent_share
        self.recheck_ms, self.max_open_ms, self.history_ms = int(recheck_s * 1000), int(max_open_s * 1000), int(history_s * 1000)
        self.min_sog_kn = min_sog_kn
        self.draught_of = draught_of or (lambda mmsi: None)
        self.ships: dict[int, _Ship] = {}
        self.class_a: set[int] = set()
        self.index = _Index()
        self.open: dict[int, dict] = {}          # mmsi -> latest version of its open gap
        self._meta: dict[str, dict] = {}         # gap id -> private fields (start_recv, last check, peers before)
        self.stalls: list[tuple[int, int]] = []
        self._last_prune = 0
        self._clock = 0                           # newest receive or tick time seen
        self.stats = {"opened": 0, "closed": 0, "versions": 0, "expired": 0, "ignored_future": 0, "not_moving": 0}

    # ---- inputs ----

    def note_stall(self, start_ms: int, end_ms: int) -> list[dict]:
        """One of our own ingest outages, known once it is over. Open gaps it explains become own_stall."""
        if end_ms <= start_ms:
            return []
        self.stalls.append((start_ms, end_ms))
        out = []
        for mmsi, g in list(self.open.items()):
            meta = self._meta[g["id"]]
            now = max(end_ms, self._clock)   # the silence so far, not just up to the outage's end
            if g["coverage_flag"] != "own_stall" and self._stalled(meta["start_recv"], now, meta["limit"]):
                out.append(self._version(mmsi, {"coverage_flag": "own_stall"}))
        return out

    def observe(self, rec: PositionReport) -> list[dict]:
        """Every position after it has been merged across feeds. Returns the closed version of a gap it ends."""
        if rec.cls == "A":
            self.class_a.add(rec.mmsi)
        elif rec.mmsi not in self.class_a:
            return []
        self._clock = max(self._clock, rec.recv_ts)
        if rec.ts > rec.recv_ts + FUTURE_SLACK_MS:   # a future-dated fix would freeze the ship's clock
            self.stats["ignored_future"] += 1
            return []
        out = []
        g = self.open.get(rec.mmsi)
        if g and rec.ts > g["start_ts"]:
            out.append(self._close(rec, g))
        prev = self.ships.get(rec.mmsi)
        if prev is None or rec.ts > prev.ts:
            interval = prev.interval_s if prev else None
            if prev:
                dt = (rec.ts - prev.ts) / 1000
                moving = (rec.sog_kn or 0) >= 1 and (prev.sog or 0) >= 1
                if moving and 0 < dt < self.floor_s:
                    interval = dt if interval is None else 0.8 * interval + 0.2 * dt
            track = prev.track if prev else deque()
            if not track or rec.ts - track[-1][0] >= MIN_MS:
                track.append((rec.ts, rec.lat, rec.lon))
            while track and rec.ts - track[0][0] > TRACK_MS:
                track.popleft()
            self.ships[rec.mmsi] = _Ship(rec.recv_ts, rec.ts, rec.lat, rec.lon, rec.sog_kn, rec.cog_deg,
                                         rec.nav_status, interval, track=track)
        elif rec.recv_ts > prev.recv_ts and rec.ts == prev.ts:
            prev.recv_ts, prev.quiet = rec.recv_ts, False   # the same fix heard again later: still heard
        self.index.add(rec.mmsi, rec.recv_ts, rec.lat, rec.lon)
        return out

    def warm(self, recs: Iterable[PositionReport]) -> list[dict]:
        """Seed state from stored fixes (oldest first) without opening anything; the next tick opens what is due.
        Returns the closed versions of resumed gaps whose ship came back while the backend was down."""
        out: list[dict] = []
        for rec in recs:
            out.extend(self.observe(rec))
        return out

    def resume(self, gap_rows: Iterable[dict]) -> list[dict]:
        """Latest stored versions of gaps that were open when the backend stopped, so versions carry on, not repeat.

        Call before `warm`, so a ship that came back while the backend was down closes its gap as the fixes replay.
        Returns the open gaps taken over."""
        out = []
        for g in gap_rows:
            if g["state"] != "open":
                continue
            g = dict(g)
            self.open[g["mmsi"]] = g
            self._meta[g["id"]] = {"start_recv": g["start_ts"], "checked": 0, "peers": None,   # peers: at first check
                                   "limit": self.floor_s * 1000}
            out.append(dict(g))
        return out

    # ---- the clock ----

    def tick(self, now_ms: int) -> list[dict]:
        """Every few seconds on the recv_ts clock: open gaps that are due, re-check open ones, drop old state."""
        out: list[dict] = []
        self._clock = max(self._clock, now_ms)
        if now_ms - self._last_prune >= MIN_MS:
            self.index.prune(now_ms - self.history_ms)
            self._last_prune = now_ms
        for mmsi, s in list(self.ships.items()):
            g = self.open.get(mmsi)
            if g is not None:
                if now_ms - self._meta[g["id"]]["start_recv"] > self.max_open_ms:
                    self._forget(mmsi)   # stays open in the table; the map lets the ship go
                    continue
                meta = self._meta[g["id"]]
                if now_ms - meta["checked"] >= self.recheck_ms:   # own_stall too: a silence can outgrow the outage
                    meta["checked"] = now_ms
                    if meta["peers"] is None:   # a resumed gap: its ship's neighbours from before, if still indexed
                        meta["peers"] = self.index.near(g["last_lat"], g["last_lon"], self.radius_km,
                                                        meta["start_recv"] - self.baseline_ms, meta["start_recv"], mmsi)
                    heard, flag = self._assess(mmsi, s, meta["start_recv"], meta["peers"], now_ms)
                    if flag != g["coverage_flag"]:
                        out.append(self._version(mmsi, {"coverage_flag": flag, "neighbours_heard": heard,
                                                         "duration_s": (now_ms - g["start_ts"]) // 1000}))
                    else:
                        g["neighbours_heard"] = heard
                continue
            silent_ms = now_ms - s.recv_ts
            if silent_ms > self.max_open_ms:
                del self.ships[mmsi]
            elif silent_ms > self._limit_ms(s) and not s.quiet:
                if self._moving(s):
                    out.append(self._open(mmsi, s, now_ms))
                else:
                    s.quiet = True   # stopped or moored when last heard: no gap, and not counted again
                    self.stats["not_moving"] += 1
        return out

    def open_gaps(self) -> list[dict]:
        return list(self.open.values())

    # ---- internals ----

    def _moving(self, s: _Ship) -> bool:
        if s.nav in AT_ANCHOR_OR_MOORED or s.sog is None or s.sog < self.min_sog_kn:
            return False
        t0, lat0, lon0 = s.track[0] if s.track else (s.ts, s.lat, s.lon)
        span_ms = s.ts - t0
        if span_ms < TRACK_MIN_SPAN_MS:
            return True   # too little track to check; the reported speed decides
        kn = haversine_km(lat0, lon0, s.lat, s.lon) / 1.852 / (span_ms / 3_600_000)
        return kn >= self.min_sog_kn

    def _limit_ms(self, s: _Ship) -> float:
        return max(self.floor_s, self.k * (s.interval_s or 0)) * 1000

    def _stalled(self, start_recv: int, end_ms: int, limit_ms: float) -> bool:
        """Our outages explain the silence [start_recv, end_ms]: what is left of it outside them is under limit_ms."""
        covered, edge = 0, start_recv
        for a, b in sorted(self.stalls):   # merged as we go, so overlapping outages are not counted twice
            a, b = max(a, edge), min(b, end_ms)
            if b > a:
                covered += b - a
                edge = b
        return covered > 0 and (end_ms - start_recv) - covered < limit_ms

    def _assess(self, mmsi: int, s: _Ship, start_recv: int, peers: set[int], now_ms: int) -> tuple[int, str]:
        heard = len(self.index.near(s.lat, s.lon, self.radius_km, now_ms - self.recent_ms, now_ms, mmsi))
        if self._stalled(start_recv, now_ms, self._limit_ms(s)):
            return heard, "own_stall"
        if not peers:
            return heard, "unknown"
        if heard < self.min_n or self._peers_silent(peers, now_ms):
            return heard, "coverage_gap"
        return heard, "deliberate_candidate"

    def _peers_silent(self, peers: set[int], now_ms: int) -> bool:
        """Most of the ships heard near this one before its silence are silent now too, wherever they went."""
        if len(peers) < self.peers_min:
            return False   # too few to judge; the neighbour count decides
        silent = sum(1 for m in peers if (p := self.ships.get(m)) is None or now_ms - p.recv_ts > self.recent_ms)
        return silent >= self.peers_silent_share * len(peers)

    def _open(self, mmsi: int, s: _Ship, now_ms: int) -> dict:
        peers = self.index.near(s.lat, s.lon, self.radius_km, s.recv_ts - self.baseline_ms, s.recv_ts, mmsi)
        heard, flag = self._assess(mmsi, s, s.recv_ts, peers, now_ms)
        gid = f"gap-{mmsi}-{s.ts}"
        draught = self.draught_of(mmsi)
        g = {"id": gid, "version": 1, "mmsi": mmsi, "state": "open", "start_ts": s.ts, "end_ts": None,
             "detected_at": now_ms, "duration_s": (now_ms - s.ts) // 1000, "expected_interval_s": s.interval_s,
             "last_lat": s.lat, "last_lon": s.lon, "last_sog_kn": s.sog, "last_cog_deg": s.cog, "last_nav_status": s.nav,
             "next_lat": None, "next_lon": None, "implied_speed_kn": None,
             "draught_before_m": draught, "draught_after_m": None,
             "neighbours_heard": heard, "neighbours_baseline": len(peers), "cell_id": cell_id(s.lat, s.lon),
             "coverage_flag": flag, "src": "derived", "gfw_intentional": None, "q": []}
        self.open[mmsi] = g
        self._meta[gid] = {"start_recv": s.recv_ts, "checked": now_ms, "peers": peers, "limit": self._limit_ms(s)}
        self.stats["opened"] += 1
        self.stats["versions"] += 1
        return dict(g)

    def _version(self, mmsi: int, changes: dict) -> dict:
        g = {**self.open[mmsi], **changes, "version": self.open[mmsi]["version"] + 1}
        self.open[mmsi] = g
        self.stats["versions"] += 1
        return dict(g)

    def _close(self, rec: PositionReport, g: dict) -> dict:
        meta = self._meta.pop(g["id"], {"start_recv": g["start_ts"], "limit": self.floor_s * 1000})
        hours = max(1e-9, (rec.ts - g["start_ts"]) / 3_600_000)
        flag = "own_stall" if self._stalled(meta["start_recv"], rec.recv_ts, meta["limit"]) else g["coverage_flag"]
        closed = {**g, "version": g["version"] + 1, "state": "closed", "end_ts": rec.ts,
                  "duration_s": (rec.ts - g["start_ts"]) // 1000, "next_lat": rec.lat, "next_lon": rec.lon,
                  "implied_speed_kn": haversine_km(g["last_lat"], g["last_lon"], rec.lat, rec.lon) / 1.852 / hours,
                  "draught_after_m": self.draught_of(rec.mmsi), "coverage_flag": flag}
        del self.open[rec.mmsi]
        self.stats["closed"] += 1
        self.stats["versions"] += 1
        return closed

    def _forget(self, mmsi: int) -> None:
        g = self.open.pop(mmsi, None)
        if g:
            self._meta.pop(g["id"], None)
            self.stats["expired"] += 1
        self.ships.pop(mmsi, None)
