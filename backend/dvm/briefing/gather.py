"""Facts for a briefing, built only from live state. Cross-ship numbers are computed here so Gemini never has to guess."""
from __future__ import annotations

import math
from itertools import combinations

from dvm.live import Live

MAX_SHIPS = 10
NEAR_KM = 50.0


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    p1, p2 = math.radians(lat1), math.radians(lat2)
    a = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(lon2 - lon1) / 2) ** 2
    return 6371.0 * 2 * math.asin(math.sqrt(a))


def _course_diff(a: float | None, b: float | None) -> float | None:
    if a is None or b is None:
        return None
    d = abs(a - b) % 360
    return min(d, 360 - d)


def _overlap_s(g1: dict, g2: dict, now_ms: int) -> float:
    s = max(g1.get("start_ts", 0), g2.get("start_ts", 0))
    e = min(g1.get("end_ts") or now_ms, g2.get("end_ts") or now_ms)
    return max(0.0, (e - s) / 1000)


def pair_facts(a: dict, b: dict, now_ms: int) -> dict:
    va, vb = a["vessel"], b["vessel"]
    sa, sb = (a["statics"] or [{}])[0], (b["statics"] or [{}])[0]
    dist = haversine_km(va["lat"], va["lon"], vb["lat"], vb["lon"])
    shared = {}
    for f in ("destination", "flag_iso2", "type_group"):
        x, y = sa.get(f) or va.get(f), sb.get(f) or vb.get(f)
        if f == "flag_iso2":
            x, y = sa.get(f) or va.get("flag"), sb.get(f) or vb.get("flag")
        if x and y and x != "unknown":
            shared[f] = {"same": str(x).strip().upper() == str(y).strip().upper(), "a": x, "b": y}
    overlap = max((_overlap_s(g1, g2, now_ms) for g1 in a["gaps"] for g2 in b["gaps"]), default=None)
    return {"mmsi_a": va["mmsi"], "mmsi_b": vb["mmsi"], "distance_km": round(dist, 1), "near": dist <= NEAR_KM,
            "course_diff_deg": _course_diff(va.get("cog_deg"), vb.get("cog_deg")),
            "speed_diff_kn": (round(abs(va["sog_kn"] - vb["sog_kn"]), 1)
                              if va.get("sog_kn") is not None and vb.get("sog_kn") is not None else None),
            "shared": shared, "gap_overlap_s": overlap}


def gather(live: Live, mmsis: list[int], now_ms: int) -> dict:
    """Raises KeyError(mmsi) for a ship not in live state. Missing data is listed, never filled in."""
    ships = []
    for m in dict.fromkeys(mmsis):   # drop duplicates, keep order
        if m not in live.pos:
            raise KeyError(m)
        d = live.detail(m)
        missing = [k for k, v in (("gaps", d["gaps"]), ("risk_score", d["score"])) if not v]
        if not d["statics"] or len(d["statics"][0]) <= 1:
            missing.append("statics")
        ships.append({"vessel": d["vessel"], "statics": d["statics"], "gaps": d["gaps"], "spoofs": d["spoofs"],
                      "sanction": d["sanction"], "score": d["score"], "data_not_available": missing,
                      "age_s": max(0, (now_ms - d["vessel"]["last_ts"]) // 1000)})
    pairs = [pair_facts(a, b, now_ms) for a, b in combinations(ships, 2)]
    return {"as_of_ts": now_ms, "ships": ships, "pairs": pairs}
