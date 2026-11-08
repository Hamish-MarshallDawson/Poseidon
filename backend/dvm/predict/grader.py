"""Fast graders (#121): grade ledger rows against what our own AIS and gap detector saw since. Results go to `outcomes`
(one row per prediction, key `score_id`; append-only, so a row is written only once its truth is final).

- **route** (`target = 'route'`, score_id = the route_predictions id): truth is our own fix nearest `as_of + horizon`
  within 5 minutes (`truth_source = 'own_ais'`). Error and baseline error are great-circle metres; in_r80 / in_r95
  say whether the truth fell inside the stated radii. No fix within an hour of the target time: censored `no_truth`.
- **route_reappear** (score_id = `reappear-<gap id>-<model version>`): when a gap with predictions closes, the point
  where the ship came back, against the prediction interpolated to that lead time (linear in east/north metres from
  the last fix between the predicted horizons). `truth_source = 'gap_close'`. Past the longest horizon: censored
  `beyond_horizon`.
- **go-dark** (`target = 'dark_<h>h'`): once the window plus the detector's 30-minute delay has passed, label = a
  `deliberate_candidate` gap of ours started in (made_at, made_at + horizon]. A window with only other gaps is
  censored with that gap's flag (06 section 2.10); no gap is label false. `truth_source = 'own_detector'`: our own
  detector made the label, which GFW gap events (#112) can check independently later.

A later delayed grader (Danish archive, GFW) writes its own rows with a different score_id suffix (e.g. `<id>@dma`).
"""
from __future__ import annotations

import logging
from bisect import bisect_left
from typing import Optional

from dvm.predict import features as F, schema

log = logging.getLogger(__name__)

H_MS = 3_600_000
TRUTH_TOL_MS = 5 * 60_000
NO_TRUTH_AFTER_MS = H_MS            # route: give up on a fix this long after the target time
DETECT_DELAY_MS = 35 * 60_000       # go-dark: a gap is detected 30 min after the last fix; 5 min slack
LOOKBACK_MS = 50 * H_MS             # predictions older than this are never graded (24 h horizon + 24 h gap age)
LIMIT = 5000

DUE_ROUTE = ("SELECT r.id, r.mmsi, r.made_at, r.as_of, r.horizon_s, r.model_version, r.lat, r.lon, r.radius_m_80, "
             "r.radius_m_95, r.base_lat, r.base_lon, r.gap_id FROM route_predictions r "
             "LEFT JOIN outcomes o ON o.score_id = r.id WHERE r.time > to_timestamp($1::bigint / 1000.0) "
             "AND r.as_of + r.horizon_s::bigint * 1000 + $2::bigint <= $3::bigint AND o.score_id IS NULL "
             "ORDER BY r.as_of LIMIT $4")
TRUTH = ("SELECT p.id, x.ts, x.lat, x.lon FROM unnest($1::text[], $2::int[], $3::bigint[]) AS p(id, mmsi, t) "
         "CROSS JOIN LATERAL (SELECT ts, lat, lon FROM positions WHERE mmsi = p.mmsi "
         "AND time BETWEEN to_timestamp((p.t - $4::bigint) / 1000.0) AND to_timestamp((p.t + $4::bigint) / 1000.0) "
         "ORDER BY abs(ts - p.t) LIMIT 1) x")
DUE_REAPPEAR = ("WITH g AS (SELECT DISTINCT ON (id) id, mmsi, state, start_ts, end_ts, last_lat, last_lon, next_lat, "
                "next_lon FROM gaps WHERE start_ts > $1::bigint ORDER BY id, version DESC) "
                "SELECT g.id AS gap_id, g.mmsi, g.start_ts, g.end_ts, g.last_lat, g.last_lon, g.next_lat, g.next_lon, "
                "r.model_version, min(r.made_at) AS made_at, min(r.as_of) AS as_of, "
                "array_agg(r.horizon_s ORDER BY r.horizon_s) AS hs, array_agg(r.lat ORDER BY r.horizon_s) AS lats, "
                "array_agg(r.lon ORDER BY r.horizon_s) AS lons, array_agg(r.base_lat ORDER BY r.horizon_s) AS blats, "
                "array_agg(r.base_lon ORDER BY r.horizon_s) AS blons, "
                "array_agg(r.radius_m_80 ORDER BY r.horizon_s) AS r80s, "
                "array_agg(r.radius_m_95 ORDER BY r.horizon_s) AS r95s "
                "FROM g JOIN route_predictions r ON r.gap_id = g.id AND r.time > to_timestamp($1::bigint / 1000.0) "
                "LEFT JOIN outcomes o ON o.score_id = 'reappear-' || g.id || '-' || r.model_version "
                "WHERE g.state = 'closed' AND g.next_lat IS NOT NULL AND o.score_id IS NULL "
                "GROUP BY g.id, g.mmsi, g.start_ts, g.end_ts, g.last_lat, g.last_lon, g.next_lat, g.next_lon, "
                "r.model_version LIMIT $2")
DUE_DARK = ("SELECT s.id, s.mmsi, s.target, s.made_at, s.horizon_s, s.model_version FROM scores s "
            "LEFT JOIN outcomes o ON o.score_id = s.id WHERE s.time > to_timestamp($1::bigint / 1000.0) "
            "AND s.target LIKE 'dark\\_%' AND s.made_at + s.horizon_s::bigint * 1000 + $2::bigint <= $3::bigint "
            "AND o.score_id IS NULL ORDER BY s.time LIMIT $4")
SHIP_GAPS = ("SELECT DISTINCT ON (id) id, mmsi, start_ts, coverage_flag FROM gaps "
             "WHERE mmsi = ANY($1::int[]) AND start_ts > $2::bigint ORDER BY id, version DESC")


def _outcome(**kw) -> dict:
    return {c: kw.get(c) for c in schema.OUTCOME_COLS}


def grade_route(row, truth: Optional[tuple], now: int) -> Optional[dict]:
    """The outcome of one route prediction, or None while its truth may still arrive."""
    common = dict(score_id=row["id"], mmsi=row["mmsi"], target="route", made_at=row["made_at"],
                  horizon_s=row["horizon_s"], resolved_at=now, event_id=row["gap_id"], lead_s=row["horizon_s"],
                  model_version=row["model_version"])
    if truth is None:
        if row["as_of"] + row["horizon_s"] * 1000 + NO_TRUTH_AFTER_MS <= now:
            return _outcome(**common, censored="no_truth")
        return None
    ts, lat, lon = truth
    err = F.haversine_m(row["lat"], row["lon"], lat, lon)
    return _outcome(**common, truth_source="own_ais", truth_ts=ts, truth_lat=lat, truth_lon=lon, error_m=err,
                    baseline_error_m=F.haversine_m(row["base_lat"], row["base_lon"], lat, lon),
                    in_r80=err <= row["radius_m_80"], in_r95=err <= row["radius_m_95"])


def _interp(lead_s: float, hs: list[int], vals: list[float]) -> float:
    """Linear in lead time between the horizons, from 0 at lead 0 (the last fix)."""
    xs, ys = [0, *hs], [0.0, *vals]
    i = max(1, bisect_left(xs, lead_s))
    x0, x1, y0, y1 = xs[i - 1], xs[i], ys[i - 1], ys[i]
    return y0 + (y1 - y0) * (lead_s - x0) / (x1 - x0)


def grade_reappear(row, now: int) -> dict:
    lead_s = (row["end_ts"] - row["as_of"]) / 1000
    common = dict(score_id=f"reappear-{row['gap_id']}-{row['model_version']}", mmsi=row["mmsi"],
                  target="route_reappear", made_at=row["made_at"], horizon_s=int(lead_s), resolved_at=now,
                  event_id=row["gap_id"], lead_s=int(lead_s), model_version=row["model_version"],
                  truth_source="gap_close", truth_ts=row["end_ts"], truth_lat=row["next_lat"],
                  truth_lon=row["next_lon"])
    hs = list(row["hs"])
    if lead_s > hs[-1] or lead_s < 0:
        return _outcome(**common, censored="beyond_horizon")
    lat0, lon0 = row["last_lat"], row["last_lon"]

    def at(lats, lons) -> tuple[float, float]:
        offs = [F.enu_offset(lat0, lon0, a, b) for a, b in zip(lats, lons)]
        return F.apply_offset(lat0, lon0, _interp(lead_s, hs, [o[0] for o in offs]),
                              _interp(lead_s, hs, [o[1] for o in offs]))

    plat, plon = at(row["lats"], row["lons"])
    blat, blon = at(row["blats"], row["blons"])
    err = F.haversine_m(plat, plon, row["next_lat"], row["next_lon"])
    r80, r95 = _interp(lead_s, hs, list(row["r80s"])), _interp(lead_s, hs, list(row["r95s"]))
    return _outcome(**common, error_m=err, baseline_error_m=F.haversine_m(blat, blon, row["next_lat"], row["next_lon"]),
                    in_r80=err <= r80, in_r95=err <= r95)


def grade_dark(row, gaps: list, now: int) -> dict:
    """Label from our gaps that started in the window (gaps: the ship's latest gap versions)."""
    t0, t1 = row["made_at"], row["made_at"] + row["horizon_s"] * 1000
    inside = sorted((g for g in gaps if t0 < g["start_ts"] <= t1), key=lambda g: g["start_ts"])
    common = dict(score_id=row["id"], mmsi=row["mmsi"], target=row["target"], made_at=row["made_at"],
                  horizon_s=row["horizon_s"], resolved_at=now, model_version=row["model_version"],
                  truth_source="own_detector")
    hit = next((g for g in inside if g["coverage_flag"] == "deliberate_candidate"), None)
    if hit:
        return _outcome(**common, label=True, event_id=hit["id"], lead_s=(hit["start_ts"] - t0) // 1000)
    if inside:
        return _outcome(**common, censored=inside[0]["coverage_flag"], event_id=inside[0]["id"],
                        lead_s=(inside[0]["start_ts"] - t0) // 1000)
    return _outcome(**common, label=False)


async def _write(con, outs: list[dict]) -> int:
    if outs:
        await con.executemany(schema.OUTCOME_INSERT, [tuple(o[c] for c in schema.OUTCOME_COLS) for o in outs])
    return len(outs)


async def grade_all(con, now: int) -> dict:
    since = now - LOOKBACK_MS
    out = {}
    due = await con.fetch(DUE_ROUTE, since, TRUTH_TOL_MS, now, LIMIT)
    truths = {}
    if due:
        rows = await con.fetch(TRUTH, [r["id"] for r in due], [r["mmsi"] for r in due],
                               [r["as_of"] + r["horizon_s"] * 1000 for r in due], TRUTH_TOL_MS)
        truths = {r["id"]: (r["ts"], r["lat"], r["lon"]) for r in rows}
    out["route"] = await _write(con, [o for r in due if (o := grade_route(r, truths.get(r["id"]), now))])
    out["route_reappear"] = await _write(con, [grade_reappear(r, now)
                                               for r in await con.fetch(DUE_REAPPEAR, since, LIMIT)])
    due = await con.fetch(DUE_DARK, since, DETECT_DELAY_MS, now, LIMIT)
    by: dict[int, list] = {}
    if due:
        for g in await con.fetch(SHIP_GAPS, list({r["mmsi"] for r in due}), since):
            by.setdefault(g["mmsi"], []).append(g)
    out["dark"] = await _write(con, [grade_dark(r, by.get(r["mmsi"], []), now) for r in due])
    return out
