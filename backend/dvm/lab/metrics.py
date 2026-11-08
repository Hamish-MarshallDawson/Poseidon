"""Model Lab read routes for live track record, data collected and the overview (docs/handoffs/lab.md).

- `GET /lab/metrics?hours=24&bucket=3600`: graded outcomes per time bucket (by forecast time, `made_at`), mode
  (live or backtest) and model version. Route: per horizon, n, 80/95% coverage, median error and the dead-reckoning
  baseline's median error on the same cases, skill = 1 - median / baseline median. Go-dark: per target, n, positives,
  mean p, hit rate, Brier and Brier skill over the observed base rate. Plus the go-dark reliability diagram (fixed p
  bins) and the top-10% lift of one model per target (the running champion, else the most graded non-baseline one).
- `GET /lab/data?hours=168&bucket=3600`: graded outcomes per bucket and mode with a running total (counted from the
  start of the ledger), history depth per external source (`source_windows`) and our own AIS feed, training examples
  per run and the frozen held-out sets (`model_runs` metrics).
- `GET /lab/summary`: one card per model (route, godark, fishing): champion, offline skill from its run record, live
  skill and calibration over the last 24 h, whether the backend serves it, plus totals and the improvement cycle.

Everything is read-only, bounded by `made_at` (indexed) or the hypertables' `time`, and grouped in SQL. Route
outcomes join `route_predictions` and go-dark outcomes join `scores` on (id, time = made_at), which is one index
probe per outcome. Gap-reappearance grades have no prediction row of their own, so their mode is `unknown`.
"""
from __future__ import annotations

import json
import re
import time
from typing import Callable, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

H_MS = 3_600_000
LIVE_HOURS = 24
ROUTE_PRIMARY_H = 10800
GODARK_PRIMARY = "dark_6h"
PRIMARY_H = {"route": 10800, "godark": 21600, "fishing": 604800}
LABELS = {"route": "Route: where a silent ship is", "godark": "Go-dark: will it go silent",
          "fishing": "Fishing in protected areas"}
REG_TARGETS = {"route": ("route",), "godark": ("godark", "godark_gfw", "dark"), "fishing": ("fishing",)}
P_EDGES = [0.02, 0.05, 0.1, 0.15, 0.2, 0.3, 0.5]   # reliability bins: [0, .02), [.02, .05), ... [.5, 1]
TOP_SHARE = 0.1
COV_TOL = 0.05       # an 80% circle is calibrated when it holds the ship 75-85% of the time
SOURCE_LABELS = {("gfw", "gaps"): "GFW AIS gap events", ("gfw", "all"): "GFW presence and satellite detections",
                 ("gfw", "fishing"): "GFW fishing events", ("sentinel1", "scenes"): "Sentinel-1 radar scenes",
                 ("ais", "positions"): "Our AIS feed (AISStream)"}
MAX_ROWS = 2000

_HORIZON = ("CASE WHEN o.horizon_s <= 3600 THEN 3600 WHEN o.horizon_s <= 10800 THEN 10800 "
            "WHEN o.horizon_s <= 21600 THEN 21600 ELSE 86400 END")
ROUTE = (f"SELECT (o.made_at / $2::bigint) * $2::bigint AS t, r.mode, o.model_version, {_HORIZON} AS horizon_s, "
         "count(*) AS n, avg(o.in_r80::int) AS cov80, avg(o.in_r95::int) AS cov95, "
         "percentile_cont(0.5) WITHIN GROUP (ORDER BY o.error_m) AS median_err_m, "
         "percentile_cont(0.5) WITHIN GROUP (ORDER BY o.baseline_error_m) AS baseline_median_err_m "
         "FROM outcomes o JOIN route_predictions r ON r.id = o.score_id AND r.time = to_timestamp(o.made_at / 1000.0) "
         "AND r.time >= to_timestamp($1::bigint / 1000.0) "
         "WHERE o.target = 'route' AND o.error_m IS NOT NULL AND o.made_at >= $1 "
         f"GROUP BY 1, 2, 3, 4 ORDER BY 1, 3, 4, 2 LIMIT {MAX_ROWS}")
_DARK_FROM = ("FROM outcomes o JOIN scores s ON s.id = o.score_id AND s.time = to_timestamp(o.made_at / 1000.0) "
              "AND s.time >= to_timestamp($1::bigint / 1000.0) "
              "WHERE o.target LIKE 'dark\\_%' AND o.label IS NOT NULL AND o.made_at >= $1 ")
GODARK = ("SELECT (o.made_at / $2::bigint) * $2::bigint AS t, s.mode, o.target, s.model_version, count(*) AS n, "
          "count(*) FILTER (WHERE o.label) AS positives, avg(s.p) AS mean_p, avg(o.label::int) AS hit_rate, "
          f"avg((s.p - o.label::int) ^ 2) AS brier {_DARK_FROM}"
          f"GROUP BY 1, 2, 3, 4 ORDER BY 1, 3, 4, 2 LIMIT {MAX_ROWS}")
RELIABILITY = ("SELECT o.target, s.model_version, width_bucket(s.p, $2::float8[]) AS bin, count(*) AS n, "
               f"avg(s.p) AS p_mean, avg(o.label::int) AS hit_rate {_DARK_FROM}"
               f"GROUP BY 1, 2, 3 ORDER BY 1, 2, 3 LIMIT {MAX_ROWS}")
LIFT = ("SELECT target, model_version, count(*) AS n, avg(y) AS all_hit_rate, "
        "avg(y) FILTER (WHERE rk <= $2) AS top_hit_rate FROM (SELECT o.target, s.model_version, o.label::int AS y, "
        "percent_rank() OVER (PARTITION BY o.target, s.model_version ORDER BY s.p DESC) AS rk "
        f"{_DARK_FROM}) x GROUP BY 1, 2 ORDER BY 1, 2")
# One branch per ledger: each target joins only its own prediction table (a LEFT JOIN on both was 2.3 s on Tiger).
_T = "(o.made_at / $2::bigint) * $2::bigint"
OUTCOME_COUNT = (
    f"SELECT t, mode, sum(n)::bigint AS n FROM ("
    f"SELECT {_T} AS t, r.mode, count(*) AS n FROM outcomes o JOIN route_predictions r ON r.id = o.score_id "
    "AND r.time = to_timestamp(o.made_at / 1000.0) AND r.time >= to_timestamp($1::bigint / 1000.0) "
    "WHERE o.target = 'route' AND o.made_at >= $1 GROUP BY 1, 2 UNION ALL "
    f"SELECT {_T} AS t, s.mode, count(*) AS n FROM outcomes o JOIN scores s ON s.id = o.score_id "
    "AND s.time = to_timestamp(o.made_at / 1000.0) AND s.time >= to_timestamp($1::bigint / 1000.0) "
    "WHERE o.target LIKE 'dark\\_%' AND o.made_at >= $1 GROUP BY 1, 2 UNION ALL "
    f"SELECT {_T} AS t, 'unknown' AS mode, count(*) AS n FROM outcomes o "
    "WHERE o.target NOT IN ('route') AND o.target NOT LIKE 'dark\\_%' AND o.made_at >= $1 GROUP BY 1, 2"
    f") x GROUP BY 1, 2 ORDER BY 1, 2 LIMIT {MAX_ROWS}")
OUTCOMES_BEFORE = "SELECT count(*) FROM outcomes WHERE made_at < $1"
SOURCES = ("SELECT src, stream, min(start_ts) AS oldest, max(end_ts) AS newest, count(*) AS windows, "
           "sum(rows)::bigint AS rows FROM source_windows WHERE status = 'ok' GROUP BY 1, 2 ORDER BY 1, 2")
AIS_RANGE = ("SELECT (SELECT ts FROM positions ORDER BY time LIMIT 1) AS oldest, "
             "(SELECT ts FROM positions ORDER BY time DESC LIMIT 1) AS newest")
AIS_ROWS = "SELECT approximate_row_count('positions')"
RUNS = ("SELECT DISTINCT ON (run_id) run_id, target, status, proposer, created_at, recorded_at, artifact, metrics "
        "FROM model_runs ORDER BY run_id, recorded_at DESC, (status = 'champion') DESC")
TOTALS = ("SELECT (SELECT count(*) FROM outcomes) AS graded, "
          "(SELECT count(*) FROM outcomes WHERE made_at >= $1 - 26 * 3600000::bigint AND resolved_at >= $1 - 3600000)"
          " AS graded_last_hour")
OPTIONAL_COUNT = "SELECT count(*) FROM {}"
LIVE_ROUTE = ("SELECT o.model_version, count(*) AS n, avg(o.in_r80::int) AS cov80, "
              "percentile_cont(0.5) WITHIN GROUP (ORDER BY o.error_m) AS med, "
              "percentile_cont(0.5) WITHIN GROUP (ORDER BY o.baseline_error_m) AS base "
              "FROM outcomes o JOIN route_predictions r ON r.id = o.score_id "
              "AND r.time = to_timestamp(o.made_at / 1000.0) AND r.time >= to_timestamp($1::bigint / 1000.0) "
              f"WHERE o.target = 'route' AND o.error_m IS NOT NULL AND o.made_at >= $1 AND r.mode = 'live' "
              f"AND {_HORIZON} = $2 GROUP BY 1")
LIVE_DARK = ("SELECT s.model_version, count(*) AS n, avg(s.p) AS mean_p, avg(o.label::int) AS hit_rate, "
             f"avg((s.p - o.label::int) ^ 2) AS brier {_DARK_FROM}AND s.mode = 'live' AND o.target = $2 GROUP BY 1")


def _num(v):
    return float(v) if hasattr(v, "is_finite") else v   # Decimal -> float


def _row(r) -> dict:
    return {k: _num(v) for k, v in dict(r).items()}


def _json(v):
    return json.loads(v) if isinstance(v, str) else (v or {})


def route_row(r) -> dict:
    d = _row(r)
    b = d["baseline_median_err_m"]
    d["skill"] = 1 - d["median_err_m"] / b if b else None
    return d


def brier_skill(brier: float, hit_rate: float) -> Optional[float]:
    """1 - Brier / Brier of always forecasting the observed base rate; None when the base rate is 0 or 1."""
    ref = hit_rate * (1 - hit_rate)
    return 1 - brier / ref if ref > 0 else None


def godark_row(r) -> dict:
    d = _row(r)
    d["brier_skill"] = brier_skill(d["brier"], d["hit_rate"])
    return d


def pick_version(versions: dict[str, int], champion: Optional[str]) -> Optional[str]:
    """The model a per-target chart shows: the champion (or the version it was recalibrated from, `-calN` dropped),
    else the non-baseline version with the most graded rows, else whatever has the most."""
    if not versions:
        return None
    if champion:
        for v in (champion, re.sub(r"-cal\d+$", "", champion)):
            if v in versions:
                return v
    real = {v: n for v, n in versions.items() if not v.startswith("baseline")}
    pool = real or versions
    return max(pool, key=lambda v: (pool[v], v))


def reliability(rows: list[dict], champion: Optional[str]) -> list[dict]:
    by_target: dict[str, dict[str, list[dict]]] = {}
    for r in rows:
        by_target.setdefault(r["target"], {}).setdefault(r["model_version"], []).append(r)
    out = []
    for target, models in sorted(by_target.items()):
        v = pick_version({m: sum(b["n"] for b in bs) for m, bs in models.items()}, champion)
        out.append({"target": target, "model_version": v,
                    "bins": [{"p_mean": _num(b["p_mean"]), "hit_rate": _num(b["hit_rate"]), "n": b["n"]}
                             for b in sorted(models[v], key=lambda b: b["bin"])]})
    return out


def lift(rows: list[dict], champion: Optional[str]) -> list[dict]:
    by_target: dict[str, dict[str, dict]] = {}
    for r in rows:
        by_target.setdefault(r["target"], {})[r["model_version"]] = r
    out = []
    for target, models in sorted(by_target.items()):
        v = pick_version({m: r["n"] for m, r in models.items()}, champion)
        r = models[v]
        out.append({"target": target, "model_version": v, "n": r["n"], "top_share": TOP_SHARE,
                    "top_hit_rate": _num(r["top_hit_rate"]), "all_hit_rate": _num(r["all_hit_rate"])})
    return out


def cumulative(rows: list[dict], before: int) -> list[dict]:
    """Per-bucket counts per mode with the running total over all modes (rows ordered by t)."""
    total, out = before, []
    for r in rows:
        total += r["n"]
        out.append({"t": r["t"], "mode": r["mode"], "n": r["n"], "cumulative": total})
    return out


def holdout_text(h: dict) -> Optional[str]:
    if not h:
        return None
    n = h.get("n")
    return ", ".join(x for x in (h.get("label") or h.get("name"), f"{n:,} cases" if n is not None else None) if x)


def offline_skill(metrics: dict, primary_h: int) -> dict:
    skill = metrics.get("skill") or {}
    s = skill.get(str(primary_h)) or skill.get(primary_h)
    if s is None and skill:
        k = next(iter(skill))
        primary_h, s = int(k) if str(k).isdigit() else primary_h, skill[k]
    s = s or {}
    return {"primary_h": primary_h, "skill": s.get("skill"), "skill_lo": s.get("skill_lo"),
            "skill_hi": s.get("skill_hi"), "holdout": holdout_text(metrics.get("holdout") or {})}


def find_run(runs: list[dict], key: str, version: Optional[str]) -> Optional[dict]:
    """The registry run behind a served version (exact id, or the id a `-calN` version came from), else the newest
    champion row of the target."""
    targets = REG_TARGETS[key]
    mine = [r for r in runs if r["target"] in targets]
    if version:
        base = re.sub(r"-cal\d+$", "", version)
        for r in mine:
            if r["run_id"] in (version, base) or (r.get("artifact") or "").rstrip("/").endswith(("/" + version,
                                                                                                  "/" + base)):
                return r
    champs = [r for r in mine if r["status"] == "champion"]
    return max(champs, key=lambda r: r["recorded_at"]) if champs else None


def route_live(rows: list[dict], version: Optional[str]) -> Optional[dict]:
    v = pick_version({r["model_version"]: r["n"] for r in rows}, version)
    r = next((r for r in rows if r["model_version"] == v), None)
    if r is None:
        return None
    skill = 1 - r["med"] / r["base"] if r["base"] else None
    cov = _num(r["cov80"])
    return {"hours": LIVE_HOURS, "n": r["n"], "model_version": v,
            "primary": {"name": "skill over dead reckoning at 3 h", "value": skill, "ref_label": "dead reckoning"},
            "calibration": {"name": "80% circle coverage", "value": cov, "nominal": 0.8,
                            "ok": abs(cov - 0.8) <= COV_TOL + 1e-9}}


def dark_live(rows: list[dict], version: Optional[str], target: str = GODARK_PRIMARY) -> Optional[dict]:
    v = pick_version({r["model_version"]: r["n"] for r in rows}, version)
    r = next((r for r in rows if r["model_version"] == v), None)
    if r is None:
        return None
    mean_p, hit = _num(r["mean_p"]), _num(r["hit_rate"])
    h = target.removeprefix("dark_").replace("h", " h")
    return {"hours": LIVE_HOURS, "n": r["n"], "model_version": v, "target": target,
            "primary": {"name": f"Brier skill over the base rate, {h}", "value": brier_skill(_num(r["brier"]), hit),
                        "ref_label": "base rate"},
            "calibration": {"name": f"mean p vs hit rate, {h}", "value": mean_p, "nominal": hit,
                            "ok": abs(mean_p - hit) <= max(0.01, 0.25 * hit)}}


def note(offline: dict, live: Optional[dict], deployed: bool) -> str:
    if not deployed:
        return "not served live yet"
    if live is None:
        return "no live grades in the last 24 h yet"
    parts = []
    off, on = offline.get("skill"), live["primary"]["value"]
    if off is not None and on is not None:
        parts.append("live skill below offline" if on < off else "live skill at or above offline")
    if on is not None and on < 0:
        parts.append(f"live worse than {live['primary']['ref_label']}")
    c = live["calibration"]
    if not c["ok"]:
        parts.append(f"{c['name']} off target ({c['value']:.2f} vs {c['nominal']:.2f})")
    return "; ".join(parts) or "on target"


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
            return [_row(x) for x in await con.fetch(sql, *args)]
        except (asyncpg.UndefinedTableError, asyncpg.UndefinedColumnError):
            raise HTTPException(503, "the prediction ledger is not set up (the backend runs it with PREDICT=1)")

    async def _optional(con, sql, *args, default=None):
        """A query on a table that may not exist yet (ml_proposals, positions in a test database)."""
        try:
            async with con.transaction():
                return await con.fetchval(sql, *args)
        except (asyncpg.UndefinedTableError, asyncpg.UndefinedFunctionError, asyncpg.UndefinedColumnError):
            return default

    def _champions() -> dict:
        run = running() or {}
        return {"route": run.get("route_model"), "godark": run.get("godark_model")}

    @r.get("/lab/metrics")
    async def metrics(hours: float = Query(24, gt=0, le=168), bucket: int = Query(3600, ge=900, le=86400)) -> dict:
        now = clock()
        since, b = int(now - hours * H_MS), bucket * 1000
        since -= since % b
        dark_champion = _champions()["godark"]
        async with _pool().acquire() as con:
            route = [route_row(x) for x in await _fetch(con, ROUTE, since, b)]
            godark = [godark_row(x) for x in await _fetch(con, GODARK, since, b)]
            rel = await _fetch(con, RELIABILITY, since, P_EDGES)
            lf = await _fetch(con, LIFT, since, TOP_SHARE)
        return {"bucket": b, "hours": hours, "route": route, "godark": godark,
                "reliability": reliability(rel, dark_champion), "lift": lift(lf, dark_champion)}

    @r.get("/lab/data")
    async def data(hours: float = Query(168, gt=0, le=24 * 60), bucket: int = Query(3600, ge=900, le=86400)) -> dict:
        now = clock()
        since, b = int(now - hours * H_MS), bucket * 1000
        since -= since % b
        async with _pool().acquire() as con:
            counts = await _fetch(con, OUTCOME_COUNT, since, b)
            before = await con.fetchval(OUTCOMES_BEFORE, since)
            sources = await _fetch(con, SOURCES)
            ais = await con.fetchrow(AIS_RANGE)
            ais_rows = await _optional(con, AIS_ROWS)
            runs = await _fetch(con, RUNS)
        src = [{**s, "label": SOURCE_LABELS.get((s["src"], s["stream"]), f"{s['src']} {s['stream']}")}
               for s in sources]
        if ais and ais["oldest"] is not None:
            src.insert(0, {"src": "ais", "stream": "positions", "label": SOURCE_LABELS[("ais", "positions")],
                           "oldest": ais["oldest"], "newest": ais["newest"], "windows": None, "rows": ais_rows})
        training, holdouts, seen = [], [], set()
        for x in sorted(runs, key=lambda x: -x["created_at"]):
            m = _json(x["metrics"])
            n_train = (m.get("split") or {}).get("n_train")
            training.append({"target": x["target"], "run_id": x["run_id"], "created_at": x["created_at"],
                             "n_train": n_train})
            h = m.get("holdout") or {}
            key = (x["target"], h.get("name"), h.get("hash"))
            if h and key not in seen:
                seen.add(key)
                holdouts.append({"target": x["target"], "name": h.get("name"), "n": h.get("n"),
                                 "start": h.get("start"), "end": h.get("end"), "hash": h.get("hash")})
        return {"bucket": b, "outcomes": cumulative(counts, before or 0), "sources": src, "training": training,
                "holdouts": holdouts}

    @r.get("/lab/summary")
    async def summary() -> dict:
        now = clock()
        since = now - LIVE_HOURS * H_MS
        champs = _champions()
        async with _pool().acquire() as con:
            runs = await _fetch(con, RUNS)
            live_route = await _fetch(con, LIVE_ROUTE, since, ROUTE_PRIMARY_H)
            dark_target = GODARK_PRIMARY
            live_dark = await _fetch(con, LIVE_DARK, since, dark_target)
            if not live_dark:   # 6 h grades lag the feed by 6.5 h: show the 1 h ones until they arrive
                dark_target = "dark_1h"
                live_dark = await _fetch(con, LIVE_DARK, since, dark_target)
            totals = await con.fetchrow(TOTALS, now)
            proposals = await _optional(con, OPTIONAL_COUNT.format("ml_proposals"), default=0)
        for x in runs:
            x["metrics"] = _json(x["metrics"])
        models = []
        for key in ("route", "godark", "fishing"):
            version = champs.get(key)
            run = find_run(runs, key, version)
            deployed = version is not None
            if version is None and run is not None and key == "fishing":
                version = run["run_id"]
            champion = {"run_id": run["run_id"] if run else None, "version": version or (run or {}).get("run_id"),
                        "since": run["recorded_at"] if run and run["status"] == "champion" else None,
                        "proposer": run.get("proposer") if run else None,
                        "source": (run["metrics"].get("source") if run else None)}
            offline = offline_skill(run["metrics"] if run else {}, PRIMARY_H[key])
            live = None
            if deployed:
                live = route_live(live_route, version) if key == "route" else dark_live(live_dark, version, dark_target) \
                    if key == "godark" else None
            models.append({"target": key, "label": LABELS[key], "champion": champion, "offline": offline,
                           "live": live, "deployed": deployed, "note": note(offline, live, deployed)})
        last = max((x["created_at"] for x in runs), default=None)
        return {"generated_at": now, "models": models, "cycle": {"state": "manual", "last": last, "next": None},
                "totals": {"runs": len(runs), "proposals": proposals or 0, "graded_outcomes": totals["graded"],
                           "graded_last_hour": totals["graded_last_hour"]}}

    return r
