"""THE feature code for route and go-dark models (#121), shared by training (`ml/`) and live inference (`dvm.predict`).

Everything here is a pure function of one ship's track up to `as_of` (and its static fields): no I/O, no clock, no
numpy, nothing read after `as_of`. Training and the live predictor call the same functions, so a model sees the same
numbers in both. `ml/` imports this module by adding `backend/` to `sys.path`:

    from dvm.predict.features import Track, features_at, baseline_point, FEATURE_NAMES, FEATURE_VERSION

Track input follows the contract in docs/handoffs/ml-architecture.md: columns `mmsi, ts (epoch ms), lat, lon, sog_kn,
cog_deg, heading_deg, nav_status, cls, src`, sorted by ts. A Track holds one ship.

Also here, because the backend must compute them without importing `ml/`: the route baseline (dead reckoning on the
sphere from the last course and speed; "stay put" for anchored, moored or stopped ships) and the local east/north
offsets that route models predict on top of that baseline.

Change FEATURE_VERSION whenever a feature's meaning or FEATURE_NAMES changes: artifacts record the version they were
trained on, and the backend refuses an artifact whose version differs.
"""
from __future__ import annotations

import math
from bisect import bisect_right
from typing import Iterable, Mapping, Optional, Sequence

FEATURE_VERSION = "f1"
EARTH_R_M = 6_371_008.8
KN_MS = 1852 / 3600                     # knots to metres per second
AT_ANCHOR_OR_MOORED = {1, 5}            # AIS navigational status, same rule as dvm/gaps.py
STOPPED_KN = 0.5                        # below this the baseline stays put
MAX_HISTORY_MS = 6 * 3600 * 1000        # nothing older than 6 h before as_of is ever read
WINDOWS = (("30m", 30 * 60 * 1000), ("2h", 2 * 3600 * 1000), ("6h", 6 * 3600 * 1000))

_WINDOW_FEATURES = ("n", "rate_per_min", "sog_mean", "sog_std", "sog_trend", "disp_kn", "straightness",
                    "turn_deg", "turn_abs_deg_per_h", "disp_bearing_sin", "disp_bearing_cos")
FEATURE_NAMES: list[str] = [
    # last fix
    "lat", "lon", "sog_kn", "cog_sin", "cog_cos", "ve_kn", "vn_kn", "heading_cog_diff_deg", "nav_status",
    "anchored", "is_class_a", "age_s",
    # history windows before as_of
    *[f"w{w}_{f}" for w, _ in WINDOWS for f in _WINDOW_FEATURES],
    # static
    "ship_type", "length_m", "draught_m",
    # context
    "hour_sin", "hour_cos",
]


# ---------------------------------------------------------------- geometry

def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dp, dl = p2 - p1, math.radians(lon2 - lon1)
    a = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * EARTH_R_M * math.asin(min(1.0, math.sqrt(a)))


def bearing_deg(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2, dl = math.radians(lat1), math.radians(lat2), math.radians(lon2 - lon1)
    y = math.sin(dl) * math.cos(p2)
    x = math.cos(p1) * math.sin(p2) - math.sin(p1) * math.cos(p2) * math.cos(dl)
    return math.degrees(math.atan2(y, x)) % 360


def destination(lat: float, lon: float, bearing: float, dist_m: float) -> tuple[float, float]:
    """The point dist_m along the great circle from (lat, lon) at an initial bearing (degrees)."""
    d, b = dist_m / EARTH_R_M, math.radians(bearing)
    p1, l1 = math.radians(lat), math.radians(lon)
    p2 = math.asin(max(-1.0, min(1.0, math.sin(p1) * math.cos(d) + math.cos(p1) * math.sin(d) * math.cos(b))))
    l2 = l1 + math.atan2(math.sin(b) * math.sin(d) * math.cos(p1), math.cos(d) - math.sin(p1) * math.sin(p2))
    return math.degrees(p2), (math.degrees(l2) + 540) % 360 - 180


def enu_offset(lat0: float, lon0: float, lat: float, lon: float) -> tuple[float, float]:
    """East and north metres from (lat0, lon0) to (lat, lon): the target route models learn on top of the baseline."""
    dist, b = haversine_m(lat0, lon0, lat, lon), math.radians(bearing_deg(lat0, lon0, lat, lon))
    return dist * math.sin(b), dist * math.cos(b)


def apply_offset(lat0: float, lon0: float, east_m: float, north_m: float) -> tuple[float, float]:
    """Inverse of enu_offset: the point east_m and north_m from (lat0, lon0)."""
    dist = math.hypot(east_m, north_m)
    if dist == 0:
        return lat0, lon0
    return destination(lat0, lon0, math.degrees(math.atan2(east_m, north_m)) % 360, dist)


def _angdiff(a: float, b: float) -> float:
    """Signed smallest difference b - a in degrees, in (-180, 180]."""
    d = (b - a) % 360
    return d - 360 if d > 180 else d


def _course(cog: Optional[float], heading: Optional[float]) -> Optional[float]:
    if cog is not None and 0 <= cog < 360:
        return float(cog)
    if heading is not None and 0 <= heading < 360:   # 511 = not available
        return float(heading)
    return None


# ---------------------------------------------------------------- track

class Track:
    """One ship's fixes as parallel lists, sorted by ts. Build with from_rows or from_columns."""

    __slots__ = ("mmsi", "ts", "lat", "lon", "sog", "cog", "heading", "nav", "cls")

    def __init__(self, mmsi, ts, lat, lon, sog, cog, heading, nav, cls):
        self.mmsi = mmsi
        self.ts, self.lat, self.lon = list(ts), list(lat), list(lon)
        self.sog, self.cog, self.heading, self.nav, self.cls = list(sog), list(cog), list(heading), list(nav), list(cls)
        if any(self.ts[i] > self.ts[i + 1] for i in range(len(self.ts) - 1)):
            raise ValueError("Track must be sorted by ts")

    @classmethod
    def from_rows(cls, rows: Iterable[Mapping]) -> "Track":
        rows = list(rows)
        g = lambda k: [_num(r.get(k)) for r in rows]   # noqa: E731
        return cls(rows[0]["mmsi"] if rows else None, [int(r["ts"]) for r in rows], [float(r["lat"]) for r in rows],
                   [float(r["lon"]) for r in rows], g("sog_kn"), g("cog_deg"), g("heading_deg"),
                   [None if (v := _num(r.get("nav_status"))) is None else int(v) for r in rows],
                   [r.get("cls") for r in rows])

    @classmethod
    def from_columns(cls, mmsi, ts, lat, lon, sog_kn, cog_deg, heading_deg, nav_status, cls_) -> "Track":
        """Columns as lists or arrays (NaN counts as missing), e.g. from one pandas group."""
        f = lambda xs: [_num(x) for x in xs]   # noqa: E731
        return cls(mmsi, [int(t) for t in ts], [float(x) for x in lat], [float(x) for x in lon], f(sog_kn),
                   f(cog_deg), f(heading_deg), [None if (v := _num(x)) is None else int(v) for x in nav_status],
                   list(cls_))

    def __len__(self) -> int:
        return len(self.ts)

    def last_index(self, as_of: int) -> int:
        """Index of the last fix with ts <= as_of, or -1."""
        return bisect_right(self.ts, as_of) - 1

    def last_fix(self, as_of: int) -> Optional[dict]:
        i = self.last_index(as_of)
        if i < 0:
            return None
        return {"ts": self.ts[i], "lat": self.lat[i], "lon": self.lon[i], "sog_kn": self.sog[i],
                "cog_deg": self.cog[i], "heading_deg": self.heading[i], "nav_status": self.nav[i], "cls": self.cls[i]}


def _num(x) -> Optional[float]:
    if x is None:
        return None
    try:
        v = float(x)
    except (TypeError, ValueError):
        return None
    return None if math.isnan(v) else v


# ---------------------------------------------------------------- baseline

def is_stopped(fix: Mapping) -> bool:
    sog = fix.get("sog_kn")
    return fix.get("nav_status") in AT_ANCHOR_OR_MOORED or sog is None or sog < STOPPED_KN \
        or _course(fix.get("cog_deg"), fix.get("heading_deg")) is None


def baseline_point(fix: Mapping, horizon_s: float) -> tuple[float, float]:
    """Where the route baseline puts the ship horizon_s after `fix`: dead reckoning along the great circle from the
    last course and speed, or the fix itself for an anchored, moored, stopped or course-less ship."""
    if is_stopped(fix):
        return fix["lat"], fix["lon"]
    course = _course(fix.get("cog_deg"), fix.get("heading_deg"))
    return destination(fix["lat"], fix["lon"], course, fix["sog_kn"] * KN_MS * horizon_s)


# ---------------------------------------------------------------- features

def _window(t: Track, i: int, as_of: int, span_ms: int) -> dict:
    j = bisect_right(t.ts, as_of - span_ms, 0, i + 1)   # first fix inside (as_of - span, as_of]
    n = i - j + 1
    out = dict.fromkeys(_WINDOW_FEATURES)
    out["n"] = float(n)
    out["rate_per_min"] = n / (span_ms / 60000)
    sogs = [s for s in t.sog[j:i + 1] if s is not None]
    if sogs:
        m = sum(sogs) / len(sogs)
        out["sog_mean"] = m
        out["sog_std"] = math.sqrt(sum((s - m) ** 2 for s in sogs) / len(sogs))
        if t.sog[i] is not None:
            out["sog_trend"] = t.sog[i] - m
    if n >= 2:
        dt_h = (t.ts[i] - t.ts[j]) / 3_600_000
        disp = haversine_m(t.lat[j], t.lon[j], t.lat[i], t.lon[i])
        path = sum(haversine_m(t.lat[k], t.lon[k], t.lat[k + 1], t.lon[k + 1]) for k in range(j, i))
        if dt_h > 0:
            out["disp_kn"] = disp / 1852 / dt_h
        out["straightness"] = disp / path if path > 0 else None
        if disp > 50:   # below ~50 m the bearing is GPS noise
            b = math.radians(bearing_deg(t.lat[j], t.lon[j], t.lat[i], t.lon[i]))
            out["disp_bearing_sin"], out["disp_bearing_cos"] = math.sin(b), math.cos(b)
        courses = [c for c in (_course(t.cog[k], t.heading[k]) for k in range(j, i + 1)) if c is not None]
        if len(courses) >= 2:
            steps = [_angdiff(a, b) for a, b in zip(courses, courses[1:])]
            out["turn_deg"] = sum(steps)
            if dt_h > 0:
                out["turn_abs_deg_per_h"] = sum(abs(s) for s in steps) / dt_h
    return out


def features_at(track: Track, as_of: int, static: Optional[Mapping] = None) -> Optional[dict]:
    """Feature dict (FEATURE_NAMES -> float or None) from the fixes with ts <= as_of only, or None if the ship has no
    fix in the 6 h before as_of. `static` may carry ship_type, length_m, draught_m (the latest known at as_of)."""
    i = track.last_index(as_of)
    if i < 0 or as_of - track.ts[i] > MAX_HISTORY_MS:
        return None
    sog, cog, hdg, nav = track.sog[i], track.cog[i], track.heading[i], track.nav[i]
    course = _course(cog, hdg)
    f: dict = dict.fromkeys(FEATURE_NAMES)
    f["lat"], f["lon"], f["sog_kn"] = track.lat[i], track.lon[i], sog
    if course is not None:
        c = math.radians(course)
        f["cog_sin"], f["cog_cos"] = math.sin(c), math.cos(c)
        if sog is not None:
            f["ve_kn"], f["vn_kn"] = sog * math.sin(c), sog * math.cos(c)
    if cog is not None and 0 <= cog < 360 and hdg is not None and 0 <= hdg < 360:
        f["heading_cog_diff_deg"] = _angdiff(cog, hdg)
    f["nav_status"] = None if nav is None else float(nav)
    f["anchored"] = 1.0 if nav in AT_ANCHOR_OR_MOORED else 0.0
    f["is_class_a"] = 1.0 if track.cls[i] == "A" else 0.0
    f["age_s"] = (as_of - track.ts[i]) / 1000
    for w, span in WINDOWS:
        for k, v in _window(track, i, as_of, span).items():
            f[f"w{w}_{k}"] = v
    s = static or {}
    for k in ("ship_type", "length_m", "draught_m"):
        f[k] = _num(s.get(k))
    hour = (as_of / 3_600_000) % 24
    f["hour_sin"], f["hour_cos"] = math.sin(2 * math.pi * hour / 24), math.cos(2 * math.pi * hour / 24)
    return f


def features_many(track: Track, as_ofs: Sequence[int], static: Optional[Mapping] = None) -> list[Optional[dict]]:
    """features_at for several as_of times of one ship (training: one call per ship and grid)."""
    return [features_at(track, a, static) for a in as_ofs]


def vector(f: Mapping, names: Sequence[str] = FEATURE_NAMES) -> list[float]:
    """Feature dict to a row in the artifact's feature order, None as NaN (what LightGBM reads as missing)."""
    return [math.nan if (v := f.get(n)) is None else float(v) for n in names]
