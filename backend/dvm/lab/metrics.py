"""Model Lab read routes for live track record, data collected and the overview (docs/handoffs/lab.md).

- `GET /lab/metrics?hours=24&bucket=3600`: graded outcomes per time bucket (by forecast time, `made_at`), mode
  (live or backtest) and model version. Route: per horizon, n, 80/95% coverage, median error and the dead-reckoning
  baseline's median error on the same cases, skill = 1 - median / baseline median. Go-dark: per target, n, positives,
  mean p, hit rate, Brier and Brier skill over the observed base rate. Plus the go-dark reliability diagram (fixed p
  bins) and the top-10% lift of one model per target (the running champion, else the most graded non-baseline one).
- `GET /lab/data?hours=168&bucket=3600`: graded outcomes per bucket, one row per mode, each with its own mode's
  running total (counted from `counted_from`, BEFORE_DAYS before the window, so the count stays bounded), history
  depth per external source (`source_windows`) and our own AIS feed, training examples per run and the frozen
  held-out sets (`model_runs` metrics). Bucket rows past MAX_ROWS drop the oldest buckets (`truncated`).
- `GET /lab/summary`: one card per model (route, godark, fishing): champion, offline skill from its run record
  (`offline.statistic` names it: 'log-loss skill', 'median-error skill'), live skill and calibration over the last
  24 h of the served version's own grades (`live` is null with a note when that version has none yet, e.g. a fresh
  `-calN`), whether the backend serves it, plus totals and the improvement cycle. `live.statistic` and
  `live.horizon_s` name the live number; `live.offline` is the held-out number with that same statistic at that
  horizon (go-dark: summary[h].brier_skill), or null, and only then does the note compare offline with live.
  `champion.since` is the newest `deployed` event of the version (or its run). `totals.graded_outcomes` is exact up
  to EXACT_COUNT_MAX rows, then the planner's estimate (`graded_outcomes_estimated`).

Everything is read-only, bounded by `made_at` (indexed) or the hypertables' `time`, and grouped in SQL. Route
outcomes join `route_predictions` and go-dark outcomes join `scores` on (id, time = made_at), which is one index
probe per outcome. A gap-reappearance grade takes the mode of its gap's first route prediction (`unknown` when
there is none).
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
         f"GROUP BY 1, 2, 3, 4 ORDER BY 1 DESC, 3, 4, 2 LIMIT {MAX_ROWS}")
_DARK_FROM = ("FROM outcomes o JOIN scores s ON s.id = o.score_id AND s.time = to_timestamp(o.made_at / 1000.0) "
              "AND s.time >= to_timestamp($1::bigint / 1000.0) "
              "WHERE o.target LIKE 'dark\\_%' AND o.label IS NOT NULL AND o.made_at >= $1 ")
GODARK = ("SELECT (o.made_at / $2::bigint) * $2::bigint AS t, s.mode, o.target, s.model_version, count(*) AS n, "
          "count(*) FILTER (WHERE o.label) AS positives, avg(s.p) AS mean_p, avg(o.label::int) AS hit_rate, "
          f"avg((s.p - o.label::int) ^ 2) AS brier {_DARK_FROM}"
          f"GROUP BY 1, 2, 3, 4 ORDER BY 1 DESC, 3, 4, 2 LIMIT {MAX_ROWS}")
RELIABILITY = ("SELECT o.target, s.model_version, width_bucket(s.p, $2::float8[]) AS bin, count(*) AS n, "
               f"avg(s.p) AS p_mean, avg(o.label::int) AS hit_rate {_DARK_FROM}"
               f"GROUP BY 1, 2, 3 ORDER BY 1, 2, 3 LIMIT {MAX_ROWS}")
LIFT = ("SELECT target, model_version, count(*) AS n, avg(y) AS all_hit_rate, "
        "avg(y) FILTER (WHERE rk <= $2) AS top_hit_rate FROM (SELECT o.target, s.model_version, o.label::int AS y, "
        "percent_rank() OVER (PARTITION BY o.target, s.model_version ORDER BY s.p DESC) AS rk "
        f"{_DARK_FROM}) x GROUP BY 1, 2 ORDER BY 1, 2")
# Graded outcomes per bucket and mode. One branch per ledger: each target joins only its own prediction table (a LEFT
# JOIN on both was 2.3 s on Tiger). A reappearance grade has no prediction row of its own: the grader stamps it with
# the earliest made_at of the gap's route predictions for that model, so it takes that row's mode (`unknown` if none).
# Every branch is bounded below by $1 and, with `upper`, above by $3, so the count never scans the whole ledger.
def _by_mode(upper: bool) -> str:
    """(t, mode, n) of the outcomes with $1 <= made_at (< $3 with `upper`), bucketed by $2 ms."""
    t = "(o.made_at / $2::bigint) * $2::bigint"
    at = "to_timestamp(o.made_at / 1000.0)"
    lo = "to_timestamp($1::bigint / 1000.0)"
    made = "o.made_at >= $1" + (" AND o.made_at < $3" if upper else "")
    rng = f">= {lo}" + (" AND {c} < to_timestamp($3::bigint / 1000.0)" if upper else "")
    r_time = f"r.time {rng.format(c='r.time')}"
    s_time = f"s.time {rng.format(c='s.time')}"
    return (
        f"SELECT {t} AS t, r.mode, count(*) AS n FROM outcomes o JOIN route_predictions r ON r.id = o.score_id "
        f"AND r.time = {at} AND {r_time} WHERE o.target = 'route' AND {made} "
        "GROUP BY 1, 2 UNION ALL "
        f"SELECT {t} AS t, s.mode, count(*) AS n FROM outcomes o JOIN scores s ON s.id = o.score_id "
        f"AND s.time = {at} AND {s_time} WHERE (o.target LIKE 'dark\\_%' OR o.target = 'fishing_mpa_7d') AND {made} "
        "GROUP BY 1, 2 UNION ALL "
        f"SELECT {t} AS t, coalesce((SELECT r.mode FROM route_predictions r WHERE r.gap_id = o.event_id "
        f"AND r.model_version = o.model_version AND r.time = {at} AND {r_time} LIMIT 1), 'unknown') "
        f"AS mode, count(*) AS n FROM outcomes o WHERE o.target = 'route_reappear' AND {made} "
        "GROUP BY 1, 2 UNION ALL "
        f"SELECT {t} AS t, 'unknown' AS mode, count(*) AS n FROM outcomes o WHERE o.target NOT IN "
        f"('route', 'route_reappear', 'fishing_mpa_7d') AND o.target NOT LIKE 'dark\\_%' AND {made} GROUP BY 1, 2")


BEFORE_DAYS = 30     # /lab/data's running totals start this long before the window (bounded as the ledger grows)
OUTCOME_COUNT = (f"SELECT t, mode, sum(n)::bigint AS n FROM ({_by_mode(False)}) x "
                 f"GROUP BY 1, 2 ORDER BY 1 DESC, 2 LIMIT {MAX_ROWS}")
OUTCOMES_BEFORE = f"SELECT mode, sum(n)::bigint AS n FROM ({_by_mode(True)}) x GROUP BY 1"
SOURCES = ("SELECT src, stream, min(start_ts) AS oldest, max(end_ts) AS newest, count(*) AS windows, "
           "sum(rows)::bigint AS rows FROM source_windows WHERE status = 'ok' GROUP BY 1, 2 ORDER BY 1, 2")
AIS_RANGE = ("SELECT (SELECT ts FROM positions ORDER BY time LIMIT 1) AS oldest, "
             "(SELECT ts FROM positions ORDER BY time DESC LIMIT 1) AS newest")
AIS_ROWS = "SELECT approximate_row_count('positions')"
RUNS = ("SELECT DISTINCT ON (run_id) run_id, target, status, proposer, created_at, recorded_at, artifact, metrics "
        "FROM model_runs ORDER BY run_id, recorded_at DESC, (status = 'champion') DESC")
EXACT_COUNT_MAX = 1_000_000   # above this, graded_outcomes is the planner's row estimate (pg_class.reltuples)
TOTALS = ("SELECT CASE WHEN c.reltuples > $2 THEN c.reltuples::bigint ELSE (SELECT count(*) FROM outcomes) END "
          "AS graded, c.reltuples > $2 AS estimated, "
          "(SELECT count(*) FROM outcomes WHERE made_at >= $1 - 26 * 3600000::bigint AND resolved_at >= $1 - 3600000)"
          " AS graded_last_hour FROM pg_class c WHERE c.oid = 'outcomes'::regclass")
OPTIONAL_COUNT = "SELECT count(*) FROM {}"
# lab-store's additions (dvm/lab/schema.py): model_runs.source and ml_events; both optional here.
RUN_SOURCES = "SELECT run_id, max(source) AS source FROM model_runs WHERE source IS NOT NULL GROUP BY 1"
EVENTS = ("SELECT ts, target, kind, run_id, version FROM ml_events "
          "WHERE kind IN ('trained', 'promoted', 'deployed', 'recalibrated') ORDER BY ts")
LIVE_ROUTE = ("SELECT o.model_version, count(*) AS n, avg(o.in_r80::int) AS cov80, "
              "percentile_cont(0.5) WITHIN GROUP (ORDER BY o.error_m) AS med, "
              "percentile_cont(0.5) WITHIN GROUP (ORDER BY o.baseline_error_m) AS base "
              "FROM outcomes o JOIN route_predictions r ON r.id = o.score_id "
              "AND r.time = to_timestamp(o.made_at / 1000.0) AND r.time >= to_timestamp($1::bigint / 1000.0) "
              f"WHERE o.target = 'route' AND o.error_m IS NOT NULL AND o.made_at >= $1 AND r.mode = 'live' "
              f"AND {_HORIZON} = $2 GROUP BY 1")
LIVE_DARK = ("SELECT s.model_version, count(*) AS n, avg(s.p) AS mean_p, avg(o.label::int) AS hit_rate, "
             f"avg((s.p - o.label::int) ^ 2) AS brier {_DARK_FROM}AND s.mode = 'live' AND o.target = $2 GROUP BY 1")

# Fishing in protected areas is scored weekly by `ml.fishing.score` (made_at = the week's Monday) and graded once the
# week has passed, so it gets its own all-weeks (bounded) counts instead of the 24 h live window.
FISHING_TARGET = "fishing_mpa_7d"
FISHING_DAYS = 120
FISHING = ("SELECT s.made_at AS week, s.model_version, count(*) AS scored, count(o.score_id) AS graded, "
           "count(*) FILTER (WHERE o.label) AS positives, avg(s.p) AS mean_p, avg(o.label::int) AS hit_rate "
           "FROM scores s LEFT JOIN outcomes o ON o.score_id = s.id WHERE s.target = 'fishing_mpa_7d' "
           "AND s.mode = 'live' AND s.time >= to_timestamp($1::bigint / 1000.0) GROUP BY 1, 2 ORDER BY 1, 2")


def fishing_live(rows: list[dict]) -> Optional[dict]:
    """Totals of the weekly live fishing scores: vessels scored (latest week and all), graded, flagged in an MPA."""
    if not rows:
        return None
    last = max(r["week"] for r in rows)
    graded = sum(r["graded"] for r in rows)
    pos = sum(r["positives"] for r in rows)
    return {"latest_week": last, "scored_latest_week": sum(r["scored"] for r in rows if r["week"] == last),
            "scored": sum(r["scored"] for r in rows), "graded": graded, "positives": pos,
            "hit_rate": pos / graded if graded else None,
            "model_version": max((r for r in rows if r["week"] == last), key=lambda r: r["scored"])["model_version"]}


def _num(v):
    return float(v) if hasattr(v, "is_finite") else v   # Decimal -> float


def _row(r) -> dict:
    return {k: _num(v) for k, v in dict(r).items()}


def _json(v):
    return json.loads(v) if isinstance(v, str) else (v or {})


def _oldest_first(rows: list[dict], key: str) -> list[dict]:
    """The bucket queries return newest first (so MAX_ROWS drops the oldest buckets); the API is oldest first."""
    return sorted(rows, key=lambda x: (x["t"], x["model_version"], x[key], x["mode"]))


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


def cumulative(rows: list[dict], before: dict[str, int]) -> list[dict]:
    """Per-bucket counts, one row per mode, each with its own mode's running total since the start of the ledger
    (`before`: per mode, what was graded before the window). Rows ordered by t."""
    total, out = dict(before), []
    for r in rows:
        total[r["mode"]] = total.get(r["mode"], 0) + r["n"]
        out.append({"t": r["t"], "mode": r["mode"], "n": r["n"], "cumulative": total[r["mode"]]})
    return out


def holdout_text(h: dict) -> Optional[str]:
    if not h:
        return None
    n = h.get("n")
    return ", ".join(x for x in (h.get("label") or h.get("name"), f"{n:,} cases" if n is not None else None) if x)


STATISTICS = {"log_loss": "log-loss skill", "error_m": "median-error skill", "brier": "Brier skill"}


def statistic_label(metrics: dict) -> Optional[str]:
    """What a run's `skill` block measures, in words: 'log-loss skill' (go-dark, fishing), 'median-error skill'
    (route, over dead reckoning)."""
    loss = metrics.get("loss_name")
    return STATISTICS.get(loss) or (f"{loss.replace('_', '-')} skill" if loss else None)


def offline_skill(metrics: dict, primary_h: int) -> dict:
    skill = metrics.get("skill") or {}
    s = skill.get(str(primary_h)) or skill.get(primary_h)
    if s is None and skill:
        k = next(iter(skill))
        primary_h, s = int(k) if str(k).isdigit() else primary_h, skill[k]
    s = s or {}
    return {"primary_h": primary_h, "statistic": statistic_label(metrics), "skill": s.get("skill"),
            "skill_lo": s.get("skill_lo"), "skill_hi": s.get("skill_hi"),
            "holdout": holdout_text(metrics.get("holdout") or {})}


def offline_match(metrics: dict, statistic: str, horizon_s: int) -> Optional[dict]:
    """The held-out number with the live card's statistic at the live card's horizon, or None when the run has none
    (then the card makes no offline-vs-live comparison). Brier skill comes from summary[h].brier_skill (go-dark runs
    store it beside their log-loss skill); median-error skill from the run's own skill block."""
    h = str(horizon_s)
    if statistic == "Brier skill":
        x = (metrics.get("summary") or {}).get(h) or {}
        if x.get("brier_skill") is None:
            return None
        ci = x.get("brier_skill_ci") or [None, None]
        return {"statistic": statistic, "horizon_s": horizon_s, "skill": x["brier_skill"], "skill_lo": ci[0],
                "skill_hi": ci[1]}
    if statistic_label(metrics) == statistic:
        x = (metrics.get("skill") or {}).get(h) or {}
        if x.get("skill") is not None:
            return {"statistic": statistic, "horizon_s": horizon_s, "skill": x["skill"], "skill_lo": x.get("skill_lo"),
                    "skill_hi": x.get("skill_hi")}
    return None


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


def champion_since(events: list[dict], key: str, version: Optional[str], run: Optional[dict]) -> Optional[int]:
    """When the served champion went live: the newest deployed event of exactly this version, else of its run (or the
    version it was recalibrated from), else the run's champion row. Promoted and recalibrated events don't count: a
    promotion or a `-calN` build is not the moment it was installed."""
    targets = REG_TARGETS[key]
    mine = [e for e in events if e["target"] in targets and e["kind"] == "deployed"]
    base = re.sub(r"-cal\d+$", "", version) if version else None
    for match in (lambda e: version and e["version"] == version,
                  lambda e: run and e["run_id"] == run["run_id"] or base and e["version"] == base):
        hits = [e["ts"] for e in mine if match(e)]
        if hits:
            return max(hits)
    return run["recorded_at"] if run and run["status"] == "champion" else None


def route_live(rows: list[dict], version: Optional[str], metrics: Optional[dict] = None) -> Optional[dict]:
    """The served version's own live grades at 3 h, or None when it has none yet (an earlier version's grades are
    never shown under its name)."""
    r = next((r for r in rows if version and r["model_version"] == version), None)
    if r is None:
        return None
    skill = 1 - r["med"] / r["base"] if r["base"] else None
    cov = _num(r["cov80"])
    return {"hours": LIVE_HOURS, "n": r["n"], "model_version": version, "statistic": "median-error skill",
            "horizon_s": ROUTE_PRIMARY_H, "offline": offline_match(metrics or {}, "median-error skill", ROUTE_PRIMARY_H),
            "primary": {"name": "skill over dead reckoning at 3 h", "value": skill, "ref_label": "dead reckoning"},
            "calibration": {"name": "80% circle coverage", "value": cov, "nominal": 0.8,
                            "ok": abs(cov - 0.8) <= COV_TOL + 1e-9}}


def dark_live(rows: list[dict], version: Optional[str], target: str = GODARK_PRIMARY,
              metrics: Optional[dict] = None) -> Optional[dict]:
    r = next((r for r in rows if version and r["model_version"] == version), None)
    if r is None:
        return None
    mean_p, hit = _num(r["mean_p"]), _num(r["hit_rate"])
    h = target.removeprefix("dark_").replace("h", " h")
    hs = int(target.removeprefix("dark_").removesuffix("h")) * 3600
    return {"hours": LIVE_HOURS, "n": r["n"], "model_version": version, "target": target, "statistic": "Brier skill",
            "horizon_s": hs, "offline": offline_match(metrics or {}, "Brier skill", hs),
            "primary": {"name": f"Brier skill over the base rate, {h}", "value": brier_skill(_num(r["brier"]), hit),
                        "ref_label": "base rate"},
            "calibration": {"name": f"mean p vs hit rate, {h}", "value": mean_p, "nominal": hit,
                            "ok": abs(mean_p - hit) <= max(0.01, 0.25 * hit)}}


def note(live: Optional[dict], deployed: bool, graded_other: Optional[str] = None) -> str:
    """The card's one-line verdict. Offline and live are compared only through live.offline, the held-out number
    with the same statistic at the same horizon; without it there is no comparison."""
    if not deployed:
        return "not served live yet"
    if live is None:
        if graded_other:
            return f"no live grades for this version yet (the last 24 h graded {graded_other})"
        return "no live grades in the last 24 h yet"
    parts = []
    off, on = (live.get("offline") or {}).get("skill"), live["primary"]["value"]
    if off is not None and on is not None:
        parts.append("live skill below offline" if on < off else "live skill at or above offline")
    if on is not None and on < 0:
        parts.append(f"live worse than {live['primary']['ref_label']}")
    c = live["calibration"]
    if not c["ok"]:
        parts.append(f"{c['name']} off target ({c['value']:.1%} vs {c['nominal']:.1%})")
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

    async def _optional(con, sql, *args, default=None, rows=False):
        """A query on a table or column that may not exist yet (lab-store's ml_* tables and model_runs.source,
        positions' row estimate in a test database)."""
        try:
            async with con.transaction():
                if rows:
                    return [_row(x) for x in await con.fetch(sql, *args)]
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
            route = _oldest_first([route_row(x) for x in await _fetch(con, ROUTE, since, b)], "horizon_s")
            godark = _oldest_first([godark_row(x) for x in await _fetch(con, GODARK, since, b)], "target")
            rel = await _fetch(con, RELIABILITY, since, P_EDGES)
            lf = await _fetch(con, LIFT, since, TOP_SHARE)
            fishing = [_row(x) for x in await _fetch(con, FISHING, int(now - FISHING_DAYS * 24 * H_MS))]
        return {"fishing": fishing, "bucket": b, "hours": hours, "route": route, "godark": godark,
                "truncated": len(route) >= MAX_ROWS or len(godark) >= MAX_ROWS,
                "reliability": reliability(rel, dark_champion), "lift": lift(lf, dark_champion)}

    @r.get("/lab/data")
    async def data(hours: float = Query(168, gt=0, le=24 * 60), bucket: int = Query(3600, ge=900, le=86400)) -> dict:
        now = clock()
        since, b = int(now - hours * H_MS), bucket * 1000
        since -= since % b
        async with _pool().acquire() as con:
            counts = sorted(await _fetch(con, OUTCOME_COUNT, since, b), key=lambda x: (x["t"], x["mode"]))
            counted_from = since - BEFORE_DAYS * 24 * H_MS
            before = {x["mode"]: x["n"] for x in await _fetch(con, OUTCOMES_BEFORE, counted_from, b, since)}
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
        return {"bucket": b, "outcomes": cumulative(counts, before), "counted_from": counted_from,
                "truncated": len(counts) >= MAX_ROWS, "sources": src, "training": training, "holdouts": holdouts}

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
            dark_v = champs.get("godark")
            if not any(x["model_version"] == dark_v for x in live_dark):
                # 6 h grades lag the feed by 6.5 h: show the champion's 1 h ones until they arrive
                one = await _fetch(con, LIVE_DARK, since, "dark_1h")
                if any(x["model_version"] == dark_v for x in one) or not live_dark:
                    dark_target, live_dark = "dark_1h", one
            totals = await con.fetchrow(TOTALS, now, EXACT_COUNT_MAX)
            proposals = await _optional(con, OPTIONAL_COUNT.format("ml_proposals"), default=0)
            sources = {x["run_id"]: x["source"] for x in await _optional(con, RUN_SOURCES, default=[], rows=True)}
            events = await _optional(con, EVENTS, default=[], rows=True)
            fish = fishing_live([_row(x) for x in await _fetch(con, FISHING, int(now - FISHING_DAYS * 24 * H_MS))])
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
                        "since": champion_since(events, key, version, run),
                        "proposer": run.get("proposer") if run else None,
                        "source": (sources.get(run["run_id"]) or run["metrics"].get("source")) if run else None}
            m = run["metrics"] if run else {}
            offline = offline_skill(m, PRIMARY_H[key])
            live, other = None, None
            if deployed and key in ("route", "godark"):
                rows = live_route if key == "route" else live_dark
                live = route_live(rows, version, m) if key == "route" else dark_live(rows, version, dark_target, m)
                if live is None and rows:
                    other = pick_version({x["model_version"]: x["n"] for x in rows}, version)
            card = {"target": key, "label": LABELS[key], "champion": champion, "offline": offline,
                    "live": live, "deployed": deployed, "note": note(live, deployed, other)}
            if key == "fishing":
                card["fishing_live"] = fish
                if fish:
                    card["note"] = (f"scored {fish['scored_latest_week']} vessels this week; "
                                    f"{fish['graded']} weekly predictions graded so far")
            models.append(card)
        last = max([x["created_at"] for x in runs] + [e["ts"] for e in events
                                                       if e["kind"] in ("trained", "recalibrated")], default=None)
        return {"generated_at": now, "models": models, "cycle": {"state": "manual", "last": last, "next": None},
                "totals": {"runs": len(runs), "proposals": proposals or 0, "graded_outcomes": totals["graded"],
                           "graded_outcomes_estimated": bool(totals["estimated"]),
                           "graded_last_hour": totals["graded_last_hour"]}}

    return r
