"""Backtest (#121): fill the prediction ledger for stored history, as the live predictor would have, then grade it.

    python -m dvm.predict.backtest --from 2026-11-07T17:00Z --to 2026-11-08T06:00Z --step-min 10 [--db URL]

Walks the history in steps of `--step-min` minutes. At each step t it reads only what was known at t from the source
database (Tiger by default, always in a read-only session): positions and statics with `recv_ts <= t`, gaps with
`detected_at <= t` that had not closed by t (`end_ts > t`; a close is known when the ship's next fix arrives). It then
runs the live predictor's code on that view (dvm/predict/predictor.py `route_rows` and `godark_rows`, the champions
from `--model-dir` or the built-in baselines, and forecast.Forecast's hourly frozen sets):

- route: once per gap and model version for ships in an open gap (`as_of` = the gap's last fix), and a sample of
  `--sample` moving Class A ships per step (`as_of` = t), chosen with a generator seeded by t.
- go-dark: every moving Class A ship heard in the last 10 min is scored once an hour, at a step fixed by its mmsi
  (the live predictor rotates through the ships the same way), and every full hour whose hour before the walk fully
  covered commits a frozen set to `scores` with `mode = 'backtest'`. Hours that already hold a live set are skipped.
- the base rate of the baseline go-dark model is measured as live (deliberate-candidate gaps per moving Class A
  ship-hour in the 6 h before t - 30 min), at the half hour on or before t.

Grading runs the graders' own functions (dvm/predict/grader.py) once the walk is done, on everything the stored
history can already decide: truth from the source, predictions and outcomes in the target, `resolved_at` = the time
the live grader would have decided it. Ids are the live ids (stable), every insert is ON CONFLICT DO NOTHING and
the sampling is seeded by time, so a re-run of the same range writes nothing new.

The target (`--db`, default BACKTEST_DATABASE_URL or the local test database) must not be Tiger unless
`--allow-tiger` is given; only the Vultr server uses that.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import random
import sys
import time
import zlib
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import asyncpg

from dvm.predict import artifact, features as F, forecast as FC, grader, predictor as P, schema

log = logging.getLogger("dvm.predict.backtest")

H_MS, MIN_MS = 3_600_000, 60_000
LOCAL_DEFAULT = "postgresql://postgres:local@127.0.0.1:55542/postgres"
GRADE_BATCH = 2000
READ_ONLY = {"default_transaction_read_only": "on"}

# Source reads: the live predictor's queries plus the availability filter (recv_ts <= t).
ACTIVE = ("SELECT DISTINCT ON (mmsi) mmsi, ts, sog_kn, nav_status FROM positions "
          "WHERE time > to_timestamp($1::bigint / 1000.0) AND time <= to_timestamp($2::bigint / 1000.0) "
          "AND recv_ts <= $2 AND cls = 'A' ORDER BY mmsi, time DESC")
TRACKS = ("SELECT p.mmsi, x.ts, x.lat, x.lon, x.sog_kn, x.cog_deg, x.heading_deg, x.nav_status, x.cls "
          "FROM unnest($1::int[], $2::bigint[]) AS p(mmsi, as_of) CROSS JOIN LATERAL ("
          "  SELECT ts, lat, lon, sog_kn, cog_deg, heading_deg, nav_status, cls FROM positions"
          "  WHERE mmsi = p.mmsi AND time > to_timestamp((p.as_of - $3::bigint) / 1000.0)"
          "  AND time <= to_timestamp(p.as_of / 1000.0) AND ts <= p.as_of AND recv_ts <= $4) x ORDER BY p.mmsi, x.ts")
STATICS = ("SELECT p.mmsi, x.ship_type, x.length_m, x.draught_m FROM unnest($1::int[]) AS p(mmsi) CROSS JOIN LATERAL ("
           "  SELECT ship_type, length_m, draught_m FROM statics WHERE mmsi = p.mmsi"
           "  AND time > to_timestamp($2::bigint / 1000.0) AND time <= to_timestamp($3::bigint / 1000.0)"
           "  AND recv_ts <= $3 ORDER BY time DESC LIMIT 1) x")
MOVING_SHIPS = ("SELECT count(DISTINCT mmsi) FROM positions WHERE time > to_timestamp($1::bigint / 1000.0) "
                "AND time <= to_timestamp($2::bigint / 1000.0) AND cls = 'A' AND sog_kn >= 1")
GAPS = ("SELECT id, version, mmsi, state, start_ts, end_ts, detected_at, expected_interval_s, last_lat, last_lon, next_lat, next_lon, "
        "coverage_flag FROM gaps WHERE start_ts > $1 AND start_ts <= $2 ORDER BY id, version")
DATA_END = "SELECT recv_ts FROM positions ORDER BY time DESC LIMIT 1"
GAPS_START = "SELECT min(start_ts) FROM gaps"
# The detector's opening rule (dvm/gaps.py GapDetector defaults): silent for max(floor_s, k * report interval).
DETECT_FLOOR_S, DETECT_K = 1800, 20

# Target reads.
LIVE_HOURS = ("SELECT DISTINCT made_at FROM scores WHERE mode = 'live' AND time >= to_timestamp($1::bigint / 1000.0) "
              "AND time <= to_timestamp($2::bigint / 1000.0)")
DONE_GAPS = ("SELECT DISTINCT gap_id, model_version FROM route_predictions WHERE gap_id IS NOT NULL "
             "AND time > to_timestamp($1::bigint / 1000.0) AND time <= to_timestamp($2::bigint / 1000.0)")
COUNT_ROUTES = ("SELECT count(*) FROM route_predictions WHERE mode = 'backtest' "
                "AND time >= to_timestamp($1::bigint / 1000.0) AND time <= to_timestamp($2::bigint / 1000.0)")
COUNT_SCORES = ("SELECT count(*) FROM scores WHERE mode = 'backtest' "
                "AND time >= to_timestamp($1::bigint / 1000.0) AND time <= to_timestamp($2::bigint / 1000.0)")
COUNT_OUTCOMES = ("SELECT count(*) FROM outcomes WHERE made_at >= $1 AND made_at <= $2 AND (score_id LIKE 'route-%' "
                  "OR score_id LIKE 'reappear-%' OR score_id LIKE 'score-%')")
DUE_ROUTE = ("SELECT r.id, r.mmsi, r.made_at, r.as_of, r.horizon_s, r.model_version, r.lat, r.lon, r.radius_m_80, "
             "r.radius_m_95, r.base_lat, r.base_lon, r.gap_id FROM route_predictions r "
             "LEFT JOIN outcomes o ON o.score_id = r.id WHERE r.mode = 'backtest' "
             "AND r.time >= to_timestamp($1::bigint / 1000.0) AND r.time <= to_timestamp($2::bigint / 1000.0) "
             "AND r.as_of + r.horizon_s::bigint * 1000 + $3::bigint <= $4::bigint AND o.score_id IS NULL "
             "AND r.id > $6 ORDER BY r.id LIMIT $5")
DUE_REAPPEAR = ("SELECT r.gap_id, r.mmsi, r.model_version, min(r.made_at) AS made_at, min(r.as_of) AS as_of, "
                "array_agg(r.horizon_s ORDER BY r.horizon_s) AS hs, array_agg(r.lat ORDER BY r.horizon_s) AS lats, "
                "array_agg(r.lon ORDER BY r.horizon_s) AS lons, array_agg(r.base_lat ORDER BY r.horizon_s) AS blats, "
                "array_agg(r.base_lon ORDER BY r.horizon_s) AS blons, "
                "array_agg(r.radius_m_80 ORDER BY r.horizon_s) AS r80s, "
                "array_agg(r.radius_m_95 ORDER BY r.horizon_s) AS r95s FROM route_predictions r "
                "LEFT JOIN outcomes o ON o.score_id = 'reappear-' || r.gap_id || '-' || r.model_version "
                "WHERE r.mode = 'backtest' AND r.gap_id IS NOT NULL AND o.score_id IS NULL "
                "AND r.time >= to_timestamp($1::bigint / 1000.0) AND r.time <= to_timestamp($2::bigint / 1000.0) "
                "GROUP BY r.gap_id, r.mmsi, r.model_version")
DUE_DARK = ("SELECT s.id, s.mmsi, s.target, s.made_at, s.horizon_s, s.model_version FROM scores s "
            "LEFT JOIN outcomes o ON o.score_id = s.id WHERE s.mode = 'backtest' AND s.target LIKE 'dark\\_%' "
            "AND s.time >= to_timestamp($1::bigint / 1000.0) AND s.time <= to_timestamp($2::bigint / 1000.0) "
            "AND s.made_at + s.horizon_s::bigint * 1000 + $3::bigint <= $4::bigint AND o.score_id IS NULL "
            "ORDER BY s.id LIMIT $5")


def parse_ts(s: str) -> int:
    """ISO 8601 (a trailing Z is fine; naive means UTC) or epoch ms."""
    if s.isdigit():
        return int(s)
    d = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if d.tzinfo is None:
        d = d.replace(tzinfo=timezone.utc)
    return int(d.timestamp() * 1000)


def iso(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def is_tiger(url: str) -> bool:
    tiger = os.getenv("TIGER_DATABASE_URL", "")
    return bool(url) and ((tiger and url == tiger) or "tsdb.cloud" in url or "timescale.com" in url)


def score_slot(mmsi: int, k: int) -> int:
    """The step of the hour (0..k-1) at which this ship is scored: stable across runs and machines."""
    return zlib.crc32(str(mmsi).encode()) % k


def opened_at(g: dict, detected_at: int) -> int:
    """When the live detector opened (or would have opened) this gap: start + max(floor, k x interval), or the stored
    detected_at if that is earlier. A warm start re-detects older gaps with detected_at = the restart time, which
    would hide every gap before a restart; the rule needs only the silence itself, so nothing after t is used."""
    limit_ms = max(DETECT_FLOOR_S, DETECT_K * (g.get("expected_interval_s") or 0)) * 1000
    return int(min(detected_at, g["start_ts"] + limit_ms))


class Gaps:
    """Every gap version in the range, in memory (tens of thousands of rows a day): what the detector knew at t.
    `history_start` is the earliest gap start the table holds: before it there are no labels and no base rate."""

    def __init__(self, rows, history_start: Optional[int] = None):
        self.history_start = history_start
        self.latest: dict[str, dict] = {}
        self.first_seen: dict[str, int] = {}
        self.by_mmsi: dict[int, list[dict]] = {}
        for r in rows:   # ordered by id, version
            d = dict(r)
            self.latest[d["id"]] = d
            self.first_seen[d["id"]] = min(self.first_seen.get(d["id"], d["detected_at"]), d["detected_at"])
        for gid, g in self.latest.items():
            self.first_seen[gid] = opened_at(g, self.first_seen[gid])
        for g in self.latest.values():
            self.by_mmsi.setdefault(g["mmsi"], []).append(g)

    def open_at(self, t: int) -> list[dict]:
        """Gaps detected by t, opened in the 24 h before it, and not closed by t (the predictor's OPEN_GAPS at t)."""
        return [g for gid, g in self.latest.items()
                if self.first_seen[gid] <= t and t - P.GAP_WINDOW_MS < g["start_ts"] <= t
                and (g["end_ts"] is None or g["end_ts"] > t)]

    def deliberate_between(self, t0: int, t1: int, known_at: int) -> int:
        return sum(1 for gid, g in self.latest.items() if t0 < g["start_ts"] <= t1
                   and self.first_seen[gid] <= known_at and g["coverage_flag"] == "deliberate_candidate")


RETRY_ERRORS = (asyncpg.ConnectionDoesNotExistError, asyncpg.InterfaceError, asyncpg.AdminShutdownError,
                asyncpg.CannotConnectNowError, ConnectionError, OSError, asyncio.TimeoutError)


class Source:
    """The read-only history pool, retrying a read when Tiger drops the connection ("terminating connection due to
    administrator command" happens under load). Reads are pure, so a retry is safe."""

    def __init__(self, pool: asyncpg.Pool, tries: int = 5):
        self.pool, self.tries = pool, tries

    async def _call(self, name: str, *args):
        for i in range(self.tries):
            try:
                return await getattr(self.pool, name)(*args)
            except RETRY_ERRORS as e:
                if i == self.tries - 1:
                    raise
                wait = 2 ** i * 3
                log.warning("Source read failed (%s: %s), retry in %s s", type(e).__name__, e, wait)
                await asyncio.sleep(wait)

    async def fetch(self, *args):
        return await self._call("fetch", *args)

    async def fetchval(self, *args):
        return await self._call("fetchval", *args)


class Backtest:
    def __init__(self, source: asyncpg.Pool, target: asyncpg.Pool, model_dir: Optional[Path], step_ms: int,
                 sample_n: int = 150):
        if H_MS % step_ms:
            raise ValueError("--step-min must divide 60")
        self.src = source if isinstance(source, Source) else Source(source)
        self.dst, self.step_ms, self.sample_n = target, step_ms, sample_n
        self.k = H_MS // step_ms
        self.champions = artifact.Champions(model_dir)
        self.champions.refresh()   # load champions.json now: Champions starts as the baselines until refreshed
        self.forecast = FC.Forecast()
        self.done_gaps: set[tuple[str, str]] = set()
        self._rate: dict[int, float] = {}
        self.stats = {"steps": 0, "route_rows": 0, "score_rows": 0, "skipped_live_hours": 0}

    async def _rate_at(self, t: int) -> float:
        """The baseline's rate as the live predictor measures it, at the half hour on or before t."""
        at = t // P.RATE_EVERY_MS * P.RATE_EVERY_MS
        if at not in self._rate:
            t0, t1 = at - P.RATE_DELAY_MS - P.RATE_WINDOW_MS, at - P.RATE_DELAY_MS
            t0 = max(t0, self.gaps.history_start or t0)   # count ship-hours only where gaps could be seen
            if t1 <= t0:
                self._rate[at] = 0.0
                return 0.0
            ships = await self.src.fetchval(MOVING_SHIPS, t0, t1)
            n = self.gaps.deliberate_between(t0, t1, at)
            self._rate[at] = (n or 0) / max(1, ships or 0) / ((t1 - t0) / H_MS)
        return self._rate[at]

    async def _tracks(self, mmsis: list[int], as_ofs: list[int], t: int) -> dict[int, F.Track]:
        out: dict[int, F.Track] = {}
        for i in range(0, len(mmsis), P.BATCH):
            rows = await self.src.fetch(TRACKS, mmsis[i:i + P.BATCH], as_ofs[i:i + P.BATCH], F.MAX_HISTORY_MS, t)
            out.update(P.tracks_from_rows(rows))
        return out

    async def _statics(self, mmsis: list[int], t: int) -> dict[int, dict]:
        rows = await self.src.fetch(STATICS, mmsis, t - P.GAP_WINDOW_MS, t) if mmsis else []
        return {r["mmsi"]: dict(r) for r in rows}

    async def step(self, t: int, emit_from: int, live_hours: set[int]) -> tuple[list[dict], list[dict]]:
        """Predict at t from what was known at t. Returns (route rows, frozen score rows) to write."""
        route, godark = self.champions.route, self.champions.godark
        open_gaps = self.gaps.open_at(t)
        in_gap = {g["mmsi"] for g in open_gaps}
        todo = sorted((g for g in open_gaps if (g["id"], route.version) not in self.done_gaps), key=lambda g: g["id"])
        hour = t // H_MS * H_MS
        live = hour in live_hours or hour + H_MS in live_hours
        active = sorted((r for r in await self.src.fetch(ACTIVE, t - P.ACTIVE_WINDOW_MS, t)
                         if r["mmsi"] not in in_gap and P._moving(r)), key=lambda r: r["mmsi"])
        slot = (t // self.step_ms) % self.k
        to_score = [] if live else [r for r in active if score_slot(r["mmsi"], self.k) == slot]
        sample = [] if live else random.Random(t).sample(active, min(self.sample_n, len(active)))
        if isinstance(godark, artifact.GodarkBaseline) and to_score:
            godark.rate_per_h = await self._rate_at(t)
        mmsis = sorted({g["mmsi"] for g in todo} | {r["mmsi"] for r in to_score} | {r["mmsi"] for r in sample})
        statics = await self._statics(mmsis, t)
        gap_tracks = await self._tracks([g["mmsi"] for g in todo], [g["start_ts"] for g in todo], t)
        act = sorted({r["mmsi"] for r in to_score} | {r["mmsi"] for r in sample})
        act_tracks = await self._tracks(act, [t] * len(act), t)

        routes, scores = [], []
        for g in todo:
            tr = gap_tracks.get(g["mmsi"])
            if tr is not None:
                routes += P.route_rows(route, g["mmsi"], tr, g["start_ts"], t, statics.get(g["mmsi"]), g["id"],
                                       "backtest")
            self.done_gaps.add((g["id"], route.version))
        for r in sample:
            tr = act_tracks.get(r["mmsi"])
            if tr is not None:
                routes += P.route_rows(route, r["mmsi"], tr, t, t, statics.get(r["mmsi"]), None, "backtest")
        for r in to_score:
            tr = act_tracks.get(r["mmsi"])
            if tr is not None:
                scores += P.godark_rows(godark, r["mmsi"], tr, t, statics.get(r["mmsi"]), "backtest")
        self.forecast.update(scores, routes, {g["id"] for g in open_gaps}, t)
        frozen = []
        if t == hour and hour - H_MS >= emit_from:   # the walk scored every slot of the hour before
            if hour in live_hours:
                self.stats["skipped_live_hours"] += 1
            else:
                frozen = self.forecast.frozen_set(hour)
        return routes, frozen

    async def _write(self, routes: list[dict], frozen: list[dict]) -> None:
        async with self.dst.acquire() as con, con.transaction():
            if routes:
                await con.executemany(schema.ROUTE_INSERT, [tuple(x[c] for c in schema.ROUTE_COLS) for x in routes])
            if frozen:
                await con.executemany(schema.SCORE_INSERT, [
                    tuple(json.dumps(x[c]) if c in ("features", "contrib") and x[c] is not None else x[c]
                          for c in schema.SCORE_COLS) for x in frozen])

    async def walk(self, t_from: int, t_to: int, progress=None) -> dict:
        t0 = -(-t_from // self.step_ms) * self.step_ms     # first step on the grid
        self.gaps = Gaps(await self.src.fetch(GAPS, t0 - P.GAP_WINDOW_MS, t_to + 2 * P.GAP_WINDOW_MS),
                         await self.src.fetchval(GAPS_START))
        # Gaps already predicted (by live or an earlier backtest) are skipped, as the live predictor does at start.
        self.done_gaps |= {(r["gap_id"], r["model_version"])
                           for r in await self.dst.fetch(DONE_GAPS, t0 - 2 * P.GAP_WINDOW_MS, t_to + P.GAP_WINDOW_MS)}
        live_hours = {r["made_at"] for r in await self.dst.fetch(LIVE_HOURS, t0 - H_MS, t_to + H_MS)}
        # Hours on the grid whose whole previous hour is scored: (H - 1h, H] needs every slot from H - 1h + step.
        emit_from = t0 - self.step_ms
        buf_r, buf_s, t = [], [], t0
        while t <= t_to:
            routes, frozen = await self.step(t, emit_from, live_hours)
            buf_r += routes
            buf_s += frozen
            self.stats["steps"] += 1
            self.stats["route_rows"] += len(routes)
            self.stats["score_rows"] += len(frozen)
            if len(buf_r) + len(buf_s) > 5000 or t % H_MS == 0:
                await self._write(buf_r, buf_s)
                buf_r, buf_s = [], []
                if progress:
                    progress(t, self.stats)
            t += self.step_ms
        await self._write(buf_r, buf_s)
        return self.stats

    async def grade(self, t_from: int, t_to: int, data_end: int) -> dict:
        """Grade the backtest rows made in [t_from, t_to] that the stored history (up to data_end) can decide."""
        out = {"route": 0, "route_reappear": 0, "dark": 0}
        after = ""   # keyset: rows still waiting for truth (near data_end) are passed over, not fetched again
        while True:
            due = await self.dst.fetch(DUE_ROUTE, t_from, t_to, grader.TRUTH_TOL_MS, data_end, GRADE_BATCH, after)
            if not due:
                break
            after = due[-1]["id"]
            rows = await self.src.fetch(grader.TRUTH, [r["id"] for r in due], [r["mmsi"] for r in due],
                                        [r["as_of"] + r["horizon_s"] * 1000 for r in due], grader.TRUTH_TOL_MS)
            truths = {r["id"]: (r["ts"], r["lat"], r["lon"]) for r in rows}
            outs = []
            for r in due:
                o = grader.grade_route(r, truths.get(r["id"]), data_end)
                if o:
                    target_ts = r["as_of"] + r["horizon_s"] * 1000
                    o["resolved_at"] = target_ts + (grader.TRUTH_TOL_MS if o["censored"] is None
                                                    else grader.NO_TRUTH_AFTER_MS)
                    outs.append(o)
            out["route"] += await self._outcomes(outs)
            if len(due) < GRADE_BATCH:
                break
        outs = []
        for r in await self.dst.fetch(DUE_REAPPEAR, t_from, t_to):
            g = self.gaps.latest.get(r["gap_id"])
            if g and g["state"] == "closed" and g["next_lat"] is not None and g["end_ts"] <= data_end:
                outs.append(grader.grade_reappear({**dict(r), "start_ts": g["start_ts"], "end_ts": g["end_ts"],
                                                   "last_lat": g["last_lat"], "last_lon": g["last_lon"],
                                                   "next_lat": g["next_lat"], "next_lon": g["next_lon"]}, g["end_ts"]))
        out["route_reappear"] = await self._outcomes(outs)
        # Windows that start before the gap history are left ungraded: no gap there means no data, not no gap.
        dark_from = max(t_from, self.gaps.history_start) if self.gaps.history_start is not None else t_to + 1
        while dark_from <= t_to:
            due = await self.dst.fetch(DUE_DARK, dark_from, t_to, grader.DETECT_DELAY_MS, data_end, GRADE_BATCH)
            outs = [grader.grade_dark(r, self.gaps.by_mmsi.get(r["mmsi"], []),
                                      r["made_at"] + r["horizon_s"] * 1000 + grader.DETECT_DELAY_MS) for r in due]
            out["dark"] += await self._outcomes(outs)
            if len(due) < GRADE_BATCH:
                break
        return out

    async def _outcomes(self, outs: list[dict]) -> int:
        if outs:
            async with self.dst.acquire() as con:
                await con.executemany(schema.OUTCOME_INSERT, [tuple(o[c] for c in schema.OUTCOME_COLS) for o in outs])
        return len(outs)


SKILL_ROUTE = ("SELECT o.target, o.model_version, CASE WHEN o.horizon_s <= 3600 THEN 3600 WHEN o.horizon_s <= 10800 "
               "THEN 10800 WHEN o.horizon_s <= 21600 THEN 21600 ELSE 86400 END AS h, count(*) AS n, "
               "percentile_cont(0.5) WITHIN GROUP (ORDER BY o.error_m) AS med, "
               "percentile_cont(0.5) WITHIN GROUP (ORDER BY o.baseline_error_m) AS base_med, "
               "avg(o.in_r80::int) AS cov80, avg(o.in_r95::int) AS cov95 FROM outcomes o "
               "WHERE o.target IN ('route', 'route_reappear') AND o.error_m IS NOT NULL AND o.made_at >= $1 "
               "AND o.made_at <= $2 AND EXISTS (SELECT 1 FROM route_predictions r WHERE r.mode = 'backtest' "
               "AND r.time >= to_timestamp(($1 - 86400000)::bigint / 1000.0) AND r.time <= to_timestamp($2::bigint / 1000.0) "
               "AND (r.id = o.score_id OR (o.target = 'route_reappear' AND r.gap_id = o.event_id "
               "AND r.model_version = o.model_version))) GROUP BY 1, 2, 3 ORDER BY 1, 3, 2")
SKILL_DARK = ("SELECT o.target, o.model_version, count(*) AS n, count(*) FILTER (WHERE o.label) AS pos, "
              "avg((s.p - o.label::int) ^ 2) AS brier, avg(s.p) AS mean_p FROM outcomes o JOIN scores s "
              "ON s.id = o.score_id AND s.mode = 'backtest' WHERE o.target LIKE 'dark\\_%' AND o.label IS NOT NULL "
              "AND o.made_at >= $1 AND o.made_at <= $2 GROUP BY 1, 2 ORDER BY 1, 2")
CENSORED = ("SELECT o.target, coalesce(o.censored, 'graded') AS c, count(*) AS n FROM outcomes o "
            "WHERE o.made_at >= $1 AND o.made_at <= $2 GROUP BY 1, 2 ORDER BY 1, 2")


async def skill_report(con, t_from: int, t_to: int) -> dict:
    """Skill over the baseline from the graded backtest rows. Route: 1 - median error / baseline median error (the
    baseline is graded on the same cases). Go-dark: Brier skill against the hit rate of the same rows."""
    route = [{"target": r["target"], "model_version": r["model_version"], "horizon_s": r["h"], "n": r["n"],
              "median_err_m": round(r["med"]), "baseline_median_err_m": round(r["base_med"]),
              "skill": round(1 - r["med"] / r["base_med"], 3) if r["base_med"] else None,
              "coverage_80": round(float(r["cov80"]), 3), "coverage_95": round(float(r["cov95"]), 3)}
             for r in await con.fetch(SKILL_ROUTE, t_from, t_to)]
    dark = []
    for r in await con.fetch(SKILL_DARK, t_from, t_to):
        rate = r["pos"] / r["n"]
        ref = rate * (1 - rate)
        dark.append({"target": r["target"], "model_version": r["model_version"], "n": r["n"], "positives": r["pos"],
                     "brier": round(r["brier"], 5), "mean_p": round(r["mean_p"], 5), "hit_rate": round(rate, 5),
                     "brier_skill_vs_hit_rate": round(1 - r["brier"] / ref, 3) if ref else None})
    graded = [dict(r) for r in await con.fetch(CENSORED, t_from, t_to)]
    return {"route": route, "godark": dark, "outcomes_by_status": graded}


async def counts(con, t_from: int, t_to: int) -> dict:
    return {"route_predictions": await con.fetchval(COUNT_ROUTES, t_from, t_to + H_MS),
            "scores": await con.fetchval(COUNT_SCORES, t_from, t_to + H_MS),
            "outcomes": await con.fetchval(COUNT_OUTCOMES, t_from, t_to + H_MS)}


async def run(args) -> dict:
    from dvm import store as store_sql

    t_from, t_to = parse_ts(args.from_), parse_ts(args.to)
    if t_to <= t_from:
        sys.exit("--to must be after --from")
    src = await asyncpg.create_pool(args.source, min_size=1, max_size=2, command_timeout=600,
                                    server_settings=READ_ONLY)
    dst = await asyncpg.create_pool(args.db, min_size=1, max_size=2, command_timeout=600)
    try:
        async with dst.acquire() as con:
            await con.execute(store_sql.SCHEMA)
            await schema.setup(con)
            before = await counts(con, t_from, t_to)
        bt = Backtest(src, dst, Path(args.model_dir) if args.model_dir else None, args.step_min * MIN_MS, args.sample)
        log.info("Models: route %s, godark %s%s", bt.champions.route.version, bt.champions.godark.version,
                 f" (champion errors: {bt.champions.errors})" if bt.champions.errors else "")
        w0 = time.monotonic()
        stats = await bt.walk(t_from, t_to, lambda t, s: log.info("%s: %s", iso(t), s))
        walk_s = time.monotonic() - w0
        data_end = args.data_end and parse_ts(args.data_end) or await bt.src.fetchval(DATA_END)
        g0 = time.monotonic()
        graded = await bt.grade(t_from, t_to + H_MS, data_end)
        grade_s = time.monotonic() - g0
        async with dst.acquire() as con:
            after = await counts(con, t_from, t_to)
            skill = await skill_report(con, t_from, t_to + H_MS)
    finally:
        await src.close()
        await dst.close()
    hours = (t_to - t_from) / H_MS
    new = {k: after[k] - before[k] for k in after}
    return {"from": iso(t_from), "to": iso(t_to), "hours": round(hours, 2), "step_min": args.step_min,
            "data_end": iso(data_end), "models": {"route": bt.champions.route.version,
                                                  "godark": bt.champions.godark.version},
            "walk": stats, "graded": graded, "new_rows": new, "total_rows": after,
            "new_rows_per_hour": {k: round(v / hours, 1) for k, v in new.items()},
            "walk_s": round(walk_s, 1), "grade_s": round(grade_s, 1),
            "seconds_per_hour_of_history": round((walk_s + grade_s) / hours, 1), "skill": skill}


def main(argv=None) -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    except ImportError:
        pass
    ap = argparse.ArgumentParser(prog="python -m dvm.predict.backtest", description=__doc__.split("\n\n")[0])
    ap.add_argument("--from", dest="from_", required=True, help="ISO 8601 or epoch ms")
    ap.add_argument("--to", required=True, help="ISO 8601 or epoch ms")
    ap.add_argument("--step-min", type=int, default=10)
    ap.add_argument("--db", default=os.getenv("BACKTEST_DATABASE_URL") or LOCAL_DEFAULT,
                    help="target database for the ledger (default BACKTEST_DATABASE_URL or the local test database)")
    ap.add_argument("--source", default=os.getenv("TIGER_DATABASE_URL", ""),
                    help="history to read (positions, statics, gaps), read-only; default TIGER_DATABASE_URL")
    ap.add_argument("--allow-tiger", action="store_true", help="allow writing to Tiger (the Vultr server only)")
    ap.add_argument("--model-dir", default=os.getenv("PREDICT_MODEL_DIR") or str(Path(__file__).resolve().parents[2]
                                                                                 / "data" / "models"))
    ap.add_argument("--sample", type=int, default=150, help="moving ships with an active route prediction per step")
    ap.add_argument("--data-end", help="grade only what was decidable by this time (default: the newest position)")
    ap.add_argument("--json", help="also write the summary to this file")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
    if not args.source:
        sys.exit("No source: set TIGER_DATABASE_URL or pass --source")
    if is_tiger(args.db) and not args.allow_tiger:
        sys.exit("Refusing to write the backtest ledger to Tiger without --allow-tiger (the Vultr server only).")
    summary = asyncio.run(run(args))
    text = json.dumps(summary, indent=2, default=str)
    print(text)
    if args.json:
        Path(args.json).write_text(text)


if __name__ == "__main__":
    main()
