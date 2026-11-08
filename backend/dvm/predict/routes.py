"""Read-only prediction routes (#121), behind the same login as /coverage.

- `GET /predictions?mmsi=<n>&hours=24`: the ship's route prediction sets (newest first; one set = one as_of and model
  version, a point and 80/95% radii per horizon, with its grade once due), its gap reappearance grades, and its
  latest go-dark scores with their labels.
- `GET /model/leaderboard?hours=24`: the training registry (model_runs, newest status per run), what the backend is
  running now, and live skill from the graded ledger: per target, model version and horizon, n, median and p90
  error, the baseline's median error on the same cases, skill = 1 - median / baseline median, and 80/95% coverage;
  for go-dark, n, positives, Brier and the Brier of the observed base rate.
"""
from __future__ import annotations

import json
import time
from typing import Callable, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

H_MS = 3_600_000

SHIP_ROUTES = ("SELECT r.id, r.made_at, r.as_of, r.model_version, r.horizon_s, r.lat, r.lon, r.radius_m_80, "
               "r.radius_m_95, r.base_lat, r.base_lon, r.gap_id, o.error_m, o.baseline_error_m, o.in_r80, o.in_r95, "
               "o.truth_ts, o.truth_lat, o.truth_lon, o.censored, o.resolved_at FROM route_predictions r "
               "LEFT JOIN outcomes o ON o.score_id = r.id WHERE r.mmsi = $1 AND r.time > to_timestamp($2::bigint / 1000.0) "
               "ORDER BY r.as_of DESC, r.model_version, r.horizon_s LIMIT 400")
SHIP_REAPPEAR = ("SELECT score_id, event_id AS gap_id, model_version, lead_s, error_m, baseline_error_m, in_r80, in_r95, "
                 "truth_ts, truth_lat, truth_lon, censored FROM outcomes WHERE target = 'route_reappear' "
                 "AND mmsi = $1 AND made_at > $2 ORDER BY made_at DESC LIMIT 50")
SHIP_DARK = ("SELECT s.id, s.target, s.made_at, s.horizon_s, s.p, s.model_version, o.label, o.censored, o.event_id "
             "FROM scores s LEFT JOIN outcomes o ON o.score_id = s.id WHERE s.mmsi = $1 "
             "AND s.time > to_timestamp($2::bigint / 1000.0) AND s.target LIKE 'dark\\_%' "
             "ORDER BY s.made_at DESC, s.horizon_s LIMIT 60")
RUNS = ("SELECT DISTINCT ON (run_id) run_id, target, model, config, data_hash, train_from, train_to, metrics, artifact, "
        "proposer, parent_run, status, created_at, recorded_at FROM model_runs ORDER BY run_id, recorded_at DESC, (status = 'champion') DESC")
LIVE_ROUTE = ("SELECT target, model_version, CASE WHEN horizon_s <= 3600 THEN 3600 WHEN horizon_s <= 10800 THEN 10800 "
              "WHEN horizon_s <= 21600 THEN 21600 ELSE 86400 END AS horizon_s, count(*) AS n, "
              "percentile_cont(0.5) WITHIN GROUP (ORDER BY error_m) AS median_err_m, "
              "percentile_cont(0.9) WITHIN GROUP (ORDER BY error_m) AS p90_err_m, "
              "percentile_cont(0.5) WITHIN GROUP (ORDER BY baseline_error_m) AS baseline_median_err_m, "
              "avg(in_r80::int) AS coverage_80, avg(in_r95::int) AS coverage_95 FROM outcomes "
              "WHERE target IN ('route', 'route_reappear') AND error_m IS NOT NULL AND made_at > $1 "
              "GROUP BY 1, 2, 3 ORDER BY 1, 2, 3")
LIVE_DARK = ("SELECT o.target, o.model_version, o.horizon_s, count(*) AS n, count(*) FILTER (WHERE o.label) AS positives, "
             "avg((s.p - o.label::int) ^ 2) AS brier, avg(s.p) AS mean_p FROM outcomes o "
             "JOIN scores s ON s.id = o.score_id AND s.time > to_timestamp($1::bigint / 1000.0) "
             "WHERE o.target LIKE 'dark\\_%' AND o.label IS NOT NULL AND o.made_at > $1 "
             "GROUP BY 1, 2, 3 ORDER BY 3, 2")


def _clean(r) -> dict:
    d = dict(r)
    for k in ("config", "metrics"):
        if isinstance(d.get(k), str):
            d[k] = json.loads(d[k])
    return {k: (float(v) if hasattr(v, "is_finite") else v) for k, v in d.items()}   # Decimal -> float


def make_router(pool_of: Callable[[], Optional[asyncpg.Pool]], running: Callable[[], Optional[dict]],
                require_login, clock: Callable[[], int] = lambda: int(time.time() * 1000)) -> APIRouter:
    r = APIRouter(dependencies=[Depends(require_login)])

    def _pool() -> asyncpg.Pool:
        pool = pool_of()
        if pool is None:
            raise HTTPException(503, "Tiger Data is not connected")
        return pool

    async def _fetch(con, sql, *args):
        try:
            return await con.fetch(sql, *args)
        except (asyncpg.UndefinedTableError, asyncpg.UndefinedColumnError):
            raise HTTPException(503, "the prediction ledger is not set up (the backend runs it with PREDICT=1)")

    @r.get("/predictions")
    async def predictions(mmsi: int, hours: float = Query(24, gt=0, le=72)) -> dict:
        since = int(clock() - hours * H_MS)
        async with _pool().acquire() as con:
            routes = await _fetch(con, SHIP_ROUTES, mmsi, since)
            reappear = await _fetch(con, SHIP_REAPPEAR, mmsi, since)
            dark = await _fetch(con, SHIP_DARK, mmsi, since)
        sets: dict[tuple, dict] = {}
        for x in routes:
            key = (x["as_of"], x["model_version"])
            s = sets.setdefault(key, {"as_of": x["as_of"], "made_at": x["made_at"], "model_version": x["model_version"],
                                      "gap_id": x["gap_id"], "points": []})
            graded = x["resolved_at"] is not None
            s["points"].append({
                "horizon_s": x["horizon_s"], "lat": x["lat"], "lon": x["lon"], "radius_m_80": x["radius_m_80"],
                "radius_m_95": x["radius_m_95"], "base_lat": x["base_lat"], "base_lon": x["base_lon"],
                "grade": ({"error_m": x["error_m"], "baseline_error_m": x["baseline_error_m"], "in_r80": x["in_r80"],
                           "in_r95": x["in_r95"], "truth_ts": x["truth_ts"], "truth_lat": x["truth_lat"],
                           "truth_lon": x["truth_lon"], "censored": x["censored"]} if graded else None)})
        return {"mmsi": mmsi, "route": list(sets.values()), "reappear": [dict(x) for x in reappear],
                "godark": [dict(x) for x in dark]}

    @r.get("/model/leaderboard")
    async def leaderboard(hours: float = Query(24, gt=0, le=168)) -> dict:
        since = int(clock() - hours * H_MS)
        async with _pool().acquire() as con:
            runs = [_clean(x) for x in await _fetch(con, RUNS)]
            live_route = [_clean(x) for x in await _fetch(con, LIVE_ROUTE, since)]
            live_dark = [_clean(x) for x in await _fetch(con, LIVE_DARK, since)]
        for x in live_route:
            b = x["baseline_median_err_m"]
            x["skill"] = 1 - x["median_err_m"] / b if b else None
        for x in live_dark:
            rate = x["positives"] / x["n"] if x["n"] else 0
            x["base_rate"], x["base_rate_brier"] = rate, rate * (1 - rate)
            x["brier_skill"] = 1 - x["brier"] / x["base_rate_brier"] if x["base_rate_brier"] else None
        champions = {}
        for x in sorted(runs, key=lambda x: x["recorded_at"]):
            if x["status"] == "champion":
                champions[x["target"]] = x["run_id"]
        return {"hours": hours, "runs": sorted(runs, key=lambda x: -x["created_at"]), "champions": champions,
                "running": running(), "live_route": live_route, "live_godark": live_dark}

    return r
