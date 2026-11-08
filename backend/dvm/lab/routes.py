"""Model Lab read routes (docs/handoffs/lab.md), behind the same login as /model/leaderboard. Times are epoch ms.

- `GET /lab/runs?target=`: run records (model_runs, newest status per run), newest first, without metrics.strata*.
- `GET /lab/runs/{run_id}`: the full record plus parent, config_diff, rationale (its proposal's text), rule (the
  promotion rule as pass/fail checks) and confirm (the second-seed re-run).
- `GET /lab/proposals?target=`: every logged proposal, newest first, with its outcome from its run's status now.
- `GET /lab/events?hours=`: the Lab timeline, oldest first; no `hours` = all.

Mount with: app.include_router(make_router(get_pool, require_login)). /lab/metrics, /lab/data and /lab/summary
are dvm/lab/metrics.py's router.
"""
from __future__ import annotations

import time
from typing import Callable, Optional

import asyncpg
from fastapi import APIRouter, Depends, HTTPException, Query

from dvm.lab import records as R

H_MS = 3_600_000
TARGET = r"^[a-z0-9_]{1,40}$"
_COLS = ("run_id, target, model, config, data_hash, train_from, train_to, {metrics}, artifact, proposer, parent_run, "
         "status, created_at, recorded_at, loop_id, round, git_sha, source")
LIGHT = _COLS.format(metrics="metrics - 'strata' - 'strata_baseline' AS metrics")
FULL = _COLS.format(metrics="metrics")
RUNS = f"SELECT {LIGHT} FROM model_runs WHERE ($1::text IS NULL OR target = $1)"
RUN_FULL = f"SELECT {FULL} FROM model_runs WHERE run_id = $1"
STATUS = ("SELECT DISTINCT ON (run_id) run_id, status FROM model_runs WHERE ($1::text IS NULL OR target = $1) "
          "ORDER BY run_id, recorded_at DESC, (status = 'champion') DESC")
PROPOSALS = ("SELECT * FROM ml_proposals WHERE ($1::text IS NULL OR target = $1) "
             "ORDER BY created_at DESC NULLS LAST, id LIMIT 2000")
EVENTS = ("SELECT * FROM ml_events WHERE ($1::bigint IS NULL OR ts >= $1) ORDER BY ts, kind, id LIMIT 5000")


def make_router(pool_of: Callable[[], Optional[asyncpg.Pool]], require_login,
                clock: Callable[[], int] = lambda: int(time.time() * 1000)) -> APIRouter:
    r = APIRouter(prefix="/lab", dependencies=[Depends(require_login)])

    def _pool() -> asyncpg.Pool:
        pool = pool_of()
        if pool is None:
            raise HTTPException(503, "Tiger Data is not connected")
        return pool

    async def _fetch(con, sql, *args) -> list[dict]:
        try:
            return [dict(x) for x in await con.fetch(sql, *args)]
        except (asyncpg.UndefinedTableError, asyncpg.UndefinedColumnError):
            raise HTTPException(503, "the Model Lab tables are not set up (dvm.lab.schema runs with PREDICT=1)")

    async def _proposals(con, target: Optional[str]) -> list[dict]:
        status = {x["run_id"]: x["status"] for x in await _fetch(con, STATUS, target)}
        return [R.proposal_record(p, status.get(p["run_id"])) for p in await _fetch(con, PROPOSALS, target)]

    @r.get("/runs")
    async def runs(target: Optional[str] = Query(None, pattern=TARGET)) -> list:
        async with _pool().acquire() as con:
            return R.runs_from_rows(await _fetch(con, RUNS, target))

    @r.get("/runs/{run_id}")
    async def run(run_id: str) -> dict:
        async with _pool().acquire() as con:
            own = R.runs_from_rows(await _fetch(con, RUN_FULL, run_id))
            if not own:
                raise HTTPException(404, f"no run {run_id}")
            rec = own[0]
            peers = R.runs_from_rows(await _fetch(con, RUNS, rec["target"]))
            props = await _proposals(con, rec["target"])
        return R.run_detail(rec, peers, props)

    @r.get("/proposals")
    async def proposals(target: Optional[str] = Query(None, pattern=TARGET)) -> list:
        async with _pool().acquire() as con:
            return await _proposals(con, target)

    @r.get("/events")
    async def events(hours: Optional[float] = Query(None, gt=0, le=24 * 365)) -> list:
        since = int(clock() - hours * H_MS) if hours else None
        async with _pool().acquire() as con:
            return [R.event_record(e) for e in await _fetch(con, EVENTS, since)]

    return r
