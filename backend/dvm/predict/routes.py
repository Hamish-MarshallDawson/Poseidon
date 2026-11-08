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
from pathlib import Path
from typing import Callable, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import HTMLResponse

from dvm import gaps as gaps_mod
from dvm.predict import forecast as FC

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


SCORE_SET = ("SELECT id, mmsi, target, made_at, horizon_s, p, model_version, features, contrib, mode FROM scores "
             "WHERE target = $1 AND time = (SELECT max(time) FROM scores WHERE target = $1 "
             "AND time <= to_timestamp($2::bigint / 1000.0) AND time > to_timestamp($3::bigint / 1000.0)) "
             "ORDER BY p DESC, mmsi")
OUTCOMES = ("SELECT score_id, mmsi, made_at, resolved_at, label, censored, lead_s FROM outcomes WHERE target = $1 "
            "AND made_at + horizon_s::bigint * 1000 + $4::bigint BETWEEN $2 AND $3 ORDER BY made_at, score_id LIMIT $5")
TL_GAPS = ("SELECT * FROM (SELECT DISTINCT ON (id) id, mmsi, start_ts, end_ts FROM gaps "
           "WHERE start_ts <= $2 AND start_ts > $1 - 86400000::bigint AND ($3::int IS NULL OR mmsi = $3) "
           "ORDER BY id, version DESC) g WHERE end_ts IS NULL OR end_ts >= $1 ORDER BY start_ts DESC LIMIT $4")
TL_FREEZES = ("SELECT DISTINCT made_at FROM scores WHERE target = $3 AND time >= to_timestamp($1::bigint / 1000.0) "
              "AND time <= to_timestamp($2::bigint / 1000.0) ORDER BY made_at")
HISTORY_RANGE = ("SELECT (SELECT ts FROM positions ORDER BY time LIMIT 1) AS t0, "
                 "(SELECT ts FROM positions ORDER BY time DESC LIMIT 1) AS t1")
RESOLVE_LAG_MS = 30 * 60_000      # the frontend's RESOLVE_LAG_MS: an outcome is due made_at + horizon + 30 min
TIMELINE_MAX = 5000
CENSORED_TS = {"coverage_gap": "coverage_gap", "unknown": "coverage_gap", "own_stall": "own_stall",
               "no_truth": "data_end", "data_end": "data_end", "already_dark": "already_dark"}


def outcome_ts(o) -> dict:
    """An outcomes row as the frontend's Outcome. A censored row keeps label miss/hit and says why in `censored`
    (our `unknown`, open sea with no neighbours to compare, maps to coverage_gap: we can't tell it from a hole)."""
    return {"score_id": o["score_id"], "mmsi": o["mmsi"], "made_at": o["made_at"], "resolved_at": o["resolved_at"],
            "label": "hit" if o["label"] else "miss",
            "censored": CENSORED_TS.get(o["censored"], "coverage_gap") if o["censored"] else None,
            "lead_s": o["lead_s"] if o["label"] else None}


def coverage_spans(t0: Optional[int], t1: Optional[int], lo: int, hi: int,
                   stalls: list[tuple[int, int]]) -> list[dict]:
    """`coverage` timeline spans in [lo, hi]: stored history as `data`, our known outages inside it as `own_stall`."""
    if t0 is None or t1 is None:
        return []
    a, b = max(lo, t0), min(hi, t1)
    if a >= b:
        return []
    spans, edge = [], a
    for s0, s1 in sorted(stalls):
        s0, s1 = max(s0, a), min(s1, b)
        if s1 <= s0 or s1 <= edge:
            continue
        s0 = max(s0, edge)
        if s0 > edge:
            spans.append((edge, s0, "data"))
        spans.append((s0, s1, "own_stall"))
        edge = s1
    if edge < b:
        spans.append((edge, b, "data"))
    return [{"kind": "coverage", "id": f"cov-{x}-{y}", "start_ts": x, "end_ts": y, "state": st} for x, y, st in spans]


def _clean(r) -> dict:
    d = dict(r)
    for k in ("config", "metrics"):
        if isinstance(d.get(k), str):
            d[k] = json.loads(d[k])
    return {k: (float(v) if hasattr(v, "is_finite") else v) for k, v in d.items()}   # Decimal -> float


def make_router(pool_of: Callable[[], Optional[asyncpg.Pool]], running: Callable[[], Optional[dict]],
                require_login, clock: Callable[[], int] = lambda: int(time.time() * 1000),
                report_dir: Optional[Path] = None, stalls: Callable[[], list] = lambda: list(gaps_mod.KNOWN_STALLS)
                ) -> APIRouter:
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

    @r.get("/scores")
    async def scores(as_of: Optional[int] = None, target: str = Query(FC.PRIMARY, pattern=r"^dark_(1|6|24)h$")) -> list:
        """RiskScore[]: the newest frozen (hourly) score set at or before as_of (default now), ranked by p."""
        t = as_of if as_of is not None else clock()
        async with _pool().acquire() as con:
            rows = await _fetch(con, SCORE_SET, target, t, t - 2 * H_MS)
        out = []
        for i, x in enumerate(rows, 1):
            d = dict(x)
            for k in ("features", "contrib"):
                d[k] = json.loads(d[k]) if isinstance(d[k], str) else (d[k] or {})
            out.append(FC.risk_score(d, i))
        return out

    @r.get("/outcomes")
    async def outcomes(from_ts: int, to_ts: int, target: str = Query(FC.PRIMARY, pattern=r"^dark_(1|6|24)h$")) -> list:
        """Outcome[] of frozen scores whose window closed (made_at + horizon + 30 min) in [from_ts, to_ts]."""
        if to_ts < from_ts:
            raise HTTPException(422, "to_ts is before from_ts")
        async with _pool().acquire() as con:
            rows = await _fetch(con, OUTCOMES, target, from_ts, to_ts, RESOLVE_LAG_MS, 50_000)
        return [outcome_ts(o) for o in rows]

    @r.get("/timeline")
    async def timeline(from_ts: int, to_ts: int, mmsi: Optional[int] = None) -> list:
        """TimelineEvent[] in [from_ts, to_ts]: gaps (latest version, newest 5,000), dark_6h outcomes, hourly forecast
        freezes and coverage spans. No spoof or meeting events: there is no detector for them yet."""
        if to_ts < from_ts:
            raise HTTPException(422, "to_ts is before from_ts")
        async with _pool().acquire() as con:
            gap_rows = await _fetch(con, TL_GAPS, from_ts, to_ts, mmsi, TIMELINE_MAX)
            outs = await _fetch(con, OUTCOMES, FC.PRIMARY, from_ts, to_ts, RESOLVE_LAG_MS, TIMELINE_MAX)
            freezes = await _fetch(con, TL_FREEZES, from_ts, to_ts, FC.PRIMARY)
            span = await con.fetchrow(HISTORY_RANGE)
        ev = [{"kind": "gap", "id": g["id"], "mmsi": g["mmsi"], "start_ts": g["start_ts"], "end_ts": g["end_ts"]}
              for g in gap_rows]
        ev += [{"kind": "freeze", "id": f"freeze-{f['made_at']}", "ts": f["made_at"]} for f in freezes]
        ev += [{"kind": "outcome", "id": f"out-{o['score_id']}", "mmsi": o["mmsi"], "ts": o["resolved_at"],
                "label": "censored" if o["censored"] else ("hit" if o["label"] else "miss")}
               for o in outs if mmsi is None or o["mmsi"] == mmsi]
        ev += coverage_spans(span["t0"], span["t1"], from_ts, to_ts, stalls())
        return ev

    @r.get("/model/report", response_class=HTMLResponse)
    async def model_report() -> HTMLResponse:
        """The newest training report HTML (ml.core.report) in PREDICT_REPORT_DIR, or 404."""
        files = []
        if report_dir and report_dir.is_dir():
            files = [f for f in report_dir.rglob("*.html") if f.is_file()]
        if not files:
            raise HTTPException(404, "no training report yet")
        newest = max(files, key=lambda f: f.stat().st_mtime)
        return HTMLResponse(newest.read_text(encoding="utf-8", errors="replace"),
                            headers={"X-Report-File": newest.name})

    return r
