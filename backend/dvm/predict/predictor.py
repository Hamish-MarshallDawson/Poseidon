"""Live predictor (#121): every PREDICT_INTERVAL_S, predict routes and go-dark risk from Tiger, write the ledger.

Each cycle:
1. Reload the champions (artifact.Champions; the baselines when there are none).
2. Ships in an open gap (gaps table, opened in the last 24 h): one route prediction per gap and model version, with
   `as_of` = the gap's last fix, so the cone is "where it is h after it went silent". Never re-predicted: no new data
   arrives while a ship is dark.
3. A random sample of moving Class A ships (at least 1 kn, not anchored or moored) heard in the last 10 minutes and not
   in a gap: a route prediction with `as_of` = now, and a go-dark score per horizon (target `dark_<h>h`, the 06
   naming) into `scores`. Moving only, because gaps open only for moving ships: moored ships would make both
   targets trivially easy and swamp the live metrics.
4. The graders (dvm/predict/grader.py) then grade whatever has come due.

Reads and writes go through its own small pool; the queries are bounded by mmsi lists and time ranges.
"""
from __future__ import annotations

import asyncio
import json
import logging
import random
import time
from pathlib import Path
from typing import Iterable, Optional

import asyncpg

from dvm.predict import artifact, features as F, grader, schema

log = logging.getLogger(__name__)

H_MS = 3_600_000
ACTIVE_WINDOW_MS = 10 * 60_000
GAP_WINDOW_MS = 24 * H_MS
RATE_WINDOW_MS = 6 * H_MS
RATE_DELAY_MS = 30 * 60_000      # gaps open 30 min after the last fix: the newest half hour is not counted yet
RATE_EVERY_MS = 30 * 60_000      # the base rate is re-measured this often (the ship count takes ~2.5 s on Tiger)
BATCH = 200
RUN_REQUIRED = ("run_id", "target", "model", "status", "created_at")

OPEN_GAPS = ("SELECT DISTINCT ON (id) id, mmsi, state, start_ts, last_lat, last_lon, last_sog_kn, last_cog_deg, "
             "last_nav_status, coverage_flag FROM gaps WHERE start_ts > $1 ORDER BY id, version DESC")
PREDICTED_GAPS = ("SELECT DISTINCT gap_id, model_version FROM route_predictions "
                  "WHERE time > to_timestamp($1::bigint / 1000.0) AND gap_id IS NOT NULL")
ACTIVE = ("SELECT DISTINCT ON (mmsi) mmsi, ts, sog_kn, nav_status FROM positions WHERE time > to_timestamp($1::bigint / 1000.0) "
          "AND time <= to_timestamp($2::bigint / 1000.0) AND cls = 'A' ORDER BY mmsi, time DESC")
TRACKS = ("SELECT p.mmsi, x.ts, x.lat, x.lon, x.sog_kn, x.cog_deg, x.heading_deg, x.nav_status, x.cls "
          "FROM unnest($1::int[], $2::bigint[]) AS p(mmsi, as_of) CROSS JOIN LATERAL ("
          "  SELECT ts, lat, lon, sog_kn, cog_deg, heading_deg, nav_status, cls FROM positions"
          "  WHERE mmsi = p.mmsi AND time > to_timestamp((p.as_of - $3::bigint) / 1000.0)"
          "  AND time <= to_timestamp(p.as_of / 1000.0) AND ts <= p.as_of) x ORDER BY p.mmsi, x.ts")
# Per ship on statics_mmsi_time, newest first: a DISTINCT ON over the whole statics hypertable ran out of memory on Tiger.
STATICS = ("SELECT p.mmsi, x.ship_type, x.length_m, x.draught_m FROM unnest($1::int[]) AS p(mmsi) CROSS JOIN LATERAL ("
           "  SELECT ship_type, length_m, draught_m FROM statics WHERE mmsi = p.mmsi"
           "  AND time > to_timestamp($2::bigint / 1000.0) ORDER BY time DESC LIMIT 1) x")
MOVING_SHIPS = ("SELECT count(DISTINCT mmsi) FROM positions WHERE time > to_timestamp($1::bigint / 1000.0) "
                "AND time <= to_timestamp($2::bigint / 1000.0) AND cls = 'A' AND sog_kn >= 1")
DELIBERATE_SINCE = ("SELECT count(DISTINCT id) FROM gaps WHERE start_ts > $1 AND start_ts <= $2 "
                    "AND coverage_flag = 'deliberate_candidate'")


def now_ms() -> int:
    return int(time.time() * 1000)


def route_rows(model, mmsi: int, track: F.Track, as_of: int, made_at: int, static: Optional[dict],
               gap_id: Optional[str], mode: str) -> list[dict]:
    """Ledger rows for one ship (one per horizon), or [] if it has no usable fix in the 6 h before as_of."""
    fix = track.last_fix(as_of)
    feats = F.features_at(track, as_of, static)
    if fix is None or feats is None:
        return []
    out = []
    for p in model.predict(fix, feats):
        out.append({"id": f"route-{mmsi}-{as_of}-{p['horizon_s']}-{model.version}", "mmsi": mmsi, "made_at": made_at,
                    "as_of": as_of, "model_version": model.version, "horizon_s": p["horizon_s"],
                    "lat": p["lat"], "lon": p["lon"], "radius_m_80": p["radius_m_80"], "radius_m_95": p["radius_m_95"],
                    "base_lat": p["base_lat"], "base_lon": p["base_lon"], "gap_id": gap_id,
                    "feature_version": model.feature_version, "mode": mode})
    return out


def godark_rows(model, mmsi: int, track: F.Track, made_at: int, static: Optional[dict], mode: str) -> list[dict]:
    """`scores` rows, one per horizon. The full feature snapshot goes on the shortest horizon's row only (the others
    point at it), which keeps the table small: the features are the same for every horizon."""
    feats = F.features_at(track, made_at, static)
    if feats is None:
        return []
    ps = model.predict(feats)
    first = min(ps)
    ids = {h: f"score-{mmsi}-dark_{h // 3600}h-{made_at}" for h in ps}
    snap = {k: (round(v, 6) if isinstance(v, float) else v) for k, v in feats.items()}
    return [{"id": ids[h], "mmsi": mmsi, "target": f"dark_{h // 3600}h", "made_at": made_at, "horizon_s": h,
             "p": float(p), "model_version": model.version, "feature_version": model.feature_version,
             "features": snap if h == first else {"same_as": ids[first]}, "contrib": None, "mode": mode}
            for h, p in sorted(ps.items())]


def _moving(r) -> bool:
    """The gap detector's first test (dvm/gaps.py): at least 1 kn and not at anchor or moored at the last fix."""
    return (r["sog_kn"] or 0) >= 1 and r["nav_status"] not in F.AT_ANCHOR_OR_MOORED


def tracks_from_rows(rows: Iterable) -> dict[int, F.Track]:
    by: dict[int, list] = {}
    for r in rows:
        by.setdefault(r["mmsi"], []).append(r)
    return {m: F.Track.from_rows(rs) for m, rs in by.items()}


class Predictor:
    def __init__(self, url: str, model_dir: Optional[Path], interval_s: float = 300, sample_n: int = 150,
                 max_gaps: int = 500, mode: str = "live", clock=now_ms, rng: Optional[random.Random] = None):
        self.url, self.interval_s, self.sample_n, self.max_gaps, self.mode = url, interval_s, sample_n, max_gaps, mode
        self.champions = artifact.Champions(model_dir)
        self.clock, self.rng = clock, rng or random.Random()
        self.pool: Optional[asyncpg.Pool] = None
        self._done_gaps: set[tuple[str, str]] = set()
        self._runs_mtime: Optional[float] = None
        self._rate_at: Optional[int] = None
        self.status = {"state": "starting", "cycles": 0, "route_rows": 0, "score_rows": 0, "graded": 0,
                       "last_cycle_ms": None, "last_cycle_s": None, "last_error": None, "rate_per_h": None}

    def health(self) -> dict:
        return {**self.status, "route_model": self.champions.route.version, "godark_model": self.champions.godark.version,
                "champion_errors": self.champions.errors}

    async def connect(self) -> None:
        self.pool = await asyncpg.create_pool(self.url, min_size=1, max_size=2, command_timeout=120)
        async with self.pool.acquire() as con:
            await schema.setup(con)
            since = self.clock() - GAP_WINDOW_MS
            self._done_gaps = {(r["gap_id"], r["model_version"]) for r in await con.fetch(PREDICTED_GAPS, since)}

    async def close(self) -> None:
        if self.pool:
            await self.pool.close()

    async def mirror_runs(self, con, now: int) -> int:
        """Copy <model dir>/runs.jsonl (ml-loop's registry export, one model_runs row per line) into model_runs, when
        the file changes. Rows already there are skipped (key run_id, status), so it is safe to repeat."""
        f = self.champions.dir / "runs.jsonl" if self.champions.dir else None
        try:
            mtime = f.stat().st_mtime if f else None
        except OSError:
            mtime = None
        if mtime is None or mtime == self._runs_mtime:
            return 0
        rows = []
        for n, line in enumerate(f.read_text().splitlines(), 1):
            if not line.strip():
                continue
            try:
                d = json.loads(line)
                if any(d.get(c) is None for c in RUN_REQUIRED):
                    raise ValueError(f"{', '.join(RUN_REQUIRED)} are required")
            except (ValueError, AttributeError) as e:
                log.warning("runs.jsonl line %d skipped: %s", n, e)
                continue
            d.setdefault("recorded_at", d["created_at"])
            d["config"], d["metrics"] = json.dumps(d.get("config") or {}), json.dumps(d.get("metrics") or {})
            rows.append(tuple(d.get(c) for c in schema.RUN_COLS))
        if rows:
            await con.executemany(schema.RUN_INSERT, rows)
        self._runs_mtime = mtime
        return len(rows)

    async def _base_rate(self, con, model: artifact.GodarkBaseline, now: int) -> None:
        """Deliberate-candidate gaps per moving Class A ship-hour over the 6 h before the detector's delay."""
        if self._rate_at is None or now - self._rate_at >= RATE_EVERY_MS:
            t0, t1 = now - RATE_DELAY_MS - RATE_WINDOW_MS, now - RATE_DELAY_MS
            ships = await con.fetchval(MOVING_SHIPS, t0, t1)
            n = await con.fetchval(DELIBERATE_SINCE, t0, t1)
            self.status["rate_per_h"] = (n or 0) / max(1, ships or 0) / (RATE_WINDOW_MS / H_MS)
            self._rate_at = now
        model.rate_per_h = self.status["rate_per_h"]

    async def _tracks(self, con, mmsis: list[int], as_ofs: list[int]) -> dict[int, F.Track]:
        out: dict[int, F.Track] = {}
        for i in range(0, len(mmsis), BATCH):
            rows = await con.fetch(TRACKS, mmsis[i:i + BATCH], as_ofs[i:i + BATCH], F.MAX_HISTORY_MS)
            out.update(tracks_from_rows(rows))
        return out

    async def _statics(self, con, mmsis: list[int], now: int) -> dict[int, dict]:
        rows = await con.fetch(STATICS, mmsis, now - GAP_WINDOW_MS) if mmsis else []
        return {r["mmsi"]: dict(r) for r in rows}

    async def cycle(self) -> dict:
        """One predict-and-grade pass. Returns counts (also kept in status)."""
        t0, now = time.monotonic(), self.clock()
        self.champions.refresh()
        route, godark = self.champions.route, self.champions.godark
        async with self.pool.acquire() as con:
            await self.mirror_runs(con, now)
            gap_rows = [g for g in await con.fetch(OPEN_GAPS, now - GAP_WINDOW_MS) if g["state"] == "open"]
            in_gap = {g["mmsi"] for g in gap_rows}
            todo = sorted((g for g in gap_rows if (g["id"], route.version) not in self._done_gaps),
                          key=lambda g: -g["start_ts"])[: self.max_gaps]
            active = [r for r in await con.fetch(ACTIVE, now - ACTIVE_WINDOW_MS, now)
                      if r["mmsi"] not in in_gap and _moving(r)]
            if isinstance(godark, artifact.GodarkBaseline):
                await self._base_rate(con, godark, now)
            sample = self.rng.sample(active, min(self.sample_n, len(active)))
            mmsis = [g["mmsi"] for g in todo] + [r["mmsi"] for r in sample]
            statics = await self._statics(con, mmsis, now)
            gap_tracks = await self._tracks(con, [g["mmsi"] for g in todo], [g["start_ts"] for g in todo])
            act_tracks = await self._tracks(con, [r["mmsi"] for r in sample], [now] * len(sample))

            routes, scores = [], []
            for g in todo:
                t = gap_tracks.get(g["mmsi"])
                if t is not None:   # no stored track (e.g. older than our data): nothing to predict from
                    routes += route_rows(route, g["mmsi"], t, g["start_ts"], now, statics.get(g["mmsi"]), g["id"],
                                         self.mode)
            for r in sample:
                t = act_tracks.get(r["mmsi"])
                if t is None:
                    continue
                routes += route_rows(route, r["mmsi"], t, now, now, statics.get(r["mmsi"]), None, self.mode)
                scores += godark_rows(godark, r["mmsi"], t, now, statics.get(r["mmsi"]), self.mode)
            async with con.transaction():
                if routes:
                    await con.executemany(schema.ROUTE_INSERT, [tuple(x[c] for c in schema.ROUTE_COLS) for x in routes])
                if scores:
                    await con.executemany(schema.SCORE_INSERT, [
                        tuple(json.dumps(x[c]) if c in ("features", "contrib") and x[c] is not None else x[c]
                              for c in schema.SCORE_COLS) for x in scores])
            self._done_gaps |= {(g["id"], route.version) for g in todo}
            graded = await grader.grade_all(con, now)
        counts = {"gaps": len(todo), "active": len(sample), "route_rows": len(routes), "score_rows": len(scores),
                  "graded": graded}
        s = self.status
        s.update(state="running", last_cycle_ms=now, last_cycle_s=round(time.monotonic() - t0, 2), last_error=None,
                 cycles=s["cycles"] + 1, route_rows=s["route_rows"] + len(routes),
                 score_rows=s["score_rows"] + len(scores), graded=s["graded"] + sum(graded.values()))
        return counts

    async def run(self) -> None:
        backoff = 5
        while self.pool is None:
            try:
                await self.connect()
            except Exception as e:  # noqa: BLE001 - keep retrying; the rest of the backend never waits on this
                self.status.update(state="connecting", last_error=f"{type(e).__name__}: {e}")
                log.warning("Predictor connect failed (retry in %ss): %s", backoff, self.status["last_error"])
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 300)
        while True:
            try:
                counts = await self.cycle()
                log.info("Predictor cycle: %s (%.1f s)", counts, self.status["last_cycle_s"])
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 - a bad cycle is logged and the next one tries again
                self.status.update(state="error", last_error=f"{type(e).__name__}: {e}")
                log.warning("Predictor cycle failed: %s", self.status["last_error"])
            await asyncio.sleep(self.interval_s)
