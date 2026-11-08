"""Per-client replay over /ws (06 section 4.3), built from the Tiger `positions` and `statics` hypertables.

Client: {"type": "replay", "action": "seek", "t": <ms>} · "play" · "pause" · {"action": "speed", "speed": n} · "live".
Server: a `status` message (mode, speed, paused, replay.from_ts / to_ts); after a seek, a `snapshot` whose `now_ts`
is the replay clock; while playing, a `delta` every wall-clock second whose `now_ts` advances by `speed` seconds.
A client in replay gets no live deltas. Playing pauses itself at the end of the stored data.

Frames carry what was known at the replay time t (#121), through the same Live and Forecast code as live frames:
- gaps: the newest version of every gap known by t, open at t or closed in the last hour. Versions carry no write
  time, so a version counts as known at greatest(detected_at, start_ts + duration_s): the detector sets duration_s to
  its clock at every re-check and to the close at the close, so a later close never shows early.
- risk_p / risk_rank and the watchlist: the newest scores of the hour before t (any mode, live or backtest).
- pred_* on open gaps: the newest route prediction for the gap made by t.
Deltas carry what changed as the clock moves; seek rebuilds everything as of t.
"""
from __future__ import annotations

import asyncio
import json
import logging
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable

from dvm import config
from dvm.live import CLOSED_SHOWN_MS, GAP_KEEP_MS, STATIC_FIELDS, Live
from dvm.models import PositionReport, VesselStatic
from dvm.predict import forecast as FC
from dvm.predict.schema import ROUTE_COLS
from dvm.store import APPEND_COLS

log = logging.getLogger(__name__)

MAX_SPEED = 600          # replay seconds per wall-clock second
DEFAULT_SPEED = 60
POS_COLS = ("mmsi, ts, recv_ts, lat, lon, sog_kn, cog_deg, heading_deg, nav_status, cls, msg_type, ts_quality, "
            "src, q")
STATIC_COLS = ("mmsi, ts, recv_ts, imo, name, callsign, ship_type, type_group, dim_a_m, dim_b_m, dim_c_m, dim_d_m, "
               "length_m, beam_m, draught_m, destination, eta_utc, mid, flag_iso2, src, q")
GAP_COLS = ", ".join(APPEND_COLS["gaps"])
GAP_LOOKBACK_MS = GAP_KEEP_MS + CLOSED_SHOWN_MS   # older gaps are off the map (live forgets them after a day)
KNOWN_AT = "greatest(detected_at, start_ts + duration_s::bigint * 1000)"
SCORE_COLS = "id, mmsi, target, made_at, horizon_s, p, model_version, feature_version, features, contrib, mode"


def _dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, timezone.utc)


def _ms(dt: datetime | None) -> int | None:
    return None if dt is None else int(dt.timestamp() * 1000)


# The store's pool has two connections and its writer needs one every second. A world seek takes seconds, so replay
# queries from every client share one connection per pool, one at a time, and never starve live writes.
_DB_TURNS: dict = {}   # pool -> semaphore; one pool per process (asyncpg pools take no weak references)


def _db_turn(pool) -> asyncio.Semaphore:
    if pool not in _DB_TURNS:
        _DB_TURNS[pool] = asyncio.Semaphore(1)
    return _DB_TURNS[pool]


class _Turn:
    """`async with self.pool.acquire()` for replay: waits for the replay turn first, then a connection."""

    def __init__(self, pool):
        self.pool, self.con = pool, None

    async def __aenter__(self):
        await _db_turn(self.pool).acquire()
        try:
            self.con = await self.pool.acquire()
        except BaseException:
            _db_turn(self.pool).release()
            raise
        return self.con

    async def __aexit__(self, *exc):
        try:
            await self.pool.release(self.con)
        finally:
            _db_turn(self.pool).release()


class TigerHistory:
    """The only SQL replay needs."""

    def __init__(self, pool):
        self.pool = pool

    def _con(self) -> _Turn:
        return _Turn(self.pool)

    async def range(self) -> tuple[int | None, int | None]:
        async with self._con() as con:
            row = await con.fetchrow("SELECT (SELECT time FROM positions ORDER BY time LIMIT 1) AS t0, "
                                     "(SELECT time FROM positions ORDER BY time DESC LIMIT 1) AS t1")
        return _ms(row["t0"]), _ms(row["t1"])

    async def latest_positions(self, t: int, window_s: int) -> list[dict]:
        """The last position of every ship heard in (t - window, t]."""
        async with self._con() as con:
            rows = await con.fetch(f"SELECT DISTINCT ON (mmsi) {POS_COLS} FROM positions WHERE time > $1 AND time <= $2 "
                                   "ORDER BY mmsi, time DESC", _dt(t - window_s * 1000), _dt(t))
        return [dict(r) for r in rows]

    async def identities(self, t: int, window_s: int, extra: list[int] = ()) -> dict[int, dict]:
        """Latest known non-null identity fields at time t for every ship heard in (t - window, t] (the merge Live does).

        Joined in SQL: passing ~27k MMSIs as an ANY(array) ran Tiger out of memory, and TimescaleDB last() keeps one
        value per group where array_agg(...)[1] collected every row.
        """
        def pick(f: str) -> str:
            cond = f"s.{f} IS NOT NULL" + (" AND s.type_group <> 'unknown'" if f == "type_group" else "")
            return f"last(s.{f}, s.time) FILTER (WHERE {cond}) AS {f}"

        sql = ("WITH ships AS (SELECT mmsi FROM positions WHERE time > $1 AND time <= $2 "
               "UNION SELECT unnest($3::int[])) "
               f"SELECT s.mmsi, {', '.join(pick(f) for f in STATIC_FIELDS)} FROM statics s JOIN ships USING (mmsi) "
               "WHERE s.time <= $2 AND s.time > $2 - interval '24 hours' GROUP BY s.mmsi")
        async with self._con() as con:
            rows = await con.fetch(sql, _dt(t - window_s * 1000), _dt(t), list(extra))
        return {r["mmsi"]: {f: r[f] for f in STATIC_FIELDS if r[f] is not None} for r in rows}

    async def last_positions_of(self, mmsis: list[int], t: int, since: int) -> list[dict]:
        """The last position at or before t (and after `since`) of each given ship: ships in an open gap at t."""
        if not mmsis:
            return []
        async with self._con() as con:
            rows = await con.fetch(f"SELECT DISTINCT ON (mmsi) {POS_COLS} FROM positions WHERE mmsi = ANY($1::int[]) "
                                   "AND time > $2 AND time <= $3 ORDER BY mmsi, time DESC", list(mmsis), _dt(since),
                                   _dt(t))
        return [dict(r) for r in rows]

    async def gap_versions(self, a: int | None, b: int) -> list[dict]:
        """The newest version of each gap among the versions known in (a, b] (a None: known by b)."""
        async with self._con() as con:
            rows = await con.fetch(f"SELECT DISTINCT ON (id) {GAP_COLS} FROM gaps WHERE detected_at > $1 AND "
                                   f"detected_at <= $2 AND {KNOWN_AT} <= $2 AND {KNOWN_AT} > $3 "
                                   "ORDER BY id, version DESC", b - GAP_LOOKBACK_MS, b, -1 if a is None else a)
        return [dict(r) for r in rows]

    async def scores(self, a: int, b: int) -> list[dict]:
        """The newest go-dark score per ship and target made in (a, b], any mode."""
        async with self._con() as con:
            rows = await con.fetch(f"SELECT DISTINCT ON (mmsi, target) {SCORE_COLS} FROM scores WHERE time > $1 "
                                   "AND time <= $2 AND made_at <= $3 AND target LIKE 'dark\\_%' "
                                   "ORDER BY mmsi, target, made_at DESC", _dt(a), _dt(b), b)
        out = []
        for r in rows:
            d = dict(r)
            for k in ("features", "contrib"):
                if isinstance(d[k], str):
                    d[k] = json.loads(d[k])
            out.append(d)
        return out

    async def routes(self, a: int, b: int, gap_ids: list[str] | None = None) -> list[dict]:
        """Route predictions of gaps made in (a, b]: of the given gaps only, if gap_ids is not None."""
        if gap_ids is not None and not gap_ids:
            return []
        sql = (f"SELECT {', '.join(ROUTE_COLS)} FROM route_predictions WHERE time > $1 AND time <= $2 "
               "AND made_at <= $3 AND gap_id IS NOT NULL")
        args = [_dt(a), _dt(b), b]
        if gap_ids is not None:
            sql += " AND gap_id = ANY($4::text[])"
            args.append(list(gap_ids))
        async with self._con() as con:
            rows = await con.fetch(sql, *args)
        return [dict(r) for r in rows]

    async def between(self, a: int, b: int) -> tuple[list[dict], list[dict]]:
        """Positions and statics with time in (a, b], oldest first."""
        async with self._con() as con:
            pos = await con.fetch(f"SELECT {POS_COLS} FROM positions WHERE time > $1 AND time <= $2 ORDER BY time",
                                  _dt(a), _dt(b))
            sta = await con.fetch(f"SELECT {STATIC_COLS} FROM statics WHERE time > $1 AND time <= $2 ORDER BY time",
                                  _dt(a), _dt(b))
        return [dict(r) for r in pos], [dict(r) for r in sta]


class ReplaySession:
    def __init__(self, history, send: Callable[[dict], Awaitable[None]], sources: Callable[[], list] = list,
                 sleep=asyncio.sleep, clock=time.monotonic):
        self.history, self.send, self.sources, self._sleep, self._clock = history, send, sources, sleep, clock
        self.live = Live()
        self.t = 0
        self.speed = DEFAULT_SPEED
        self.playing = False
        self.range: tuple[int | None, int | None] = (None, None)
        self.watchlist: dict | None = None
        self._risk_sent: dict = {}    # mmsi -> (risk_p, risk_rank) last sent, as the Hub's on_forecast keeps
        self._pred_sent: dict = {}    # open gap id -> pred_* fields last sent
        self._task: asyncio.Task | None = None

    def status(self, mode: str = "replay") -> dict:
        return {"type": "status", "now_ts": self.t, "mode": mode, "speed": self.speed if mode == "replay" else 1,
                "paused": not self.playing, "sources": self.sources(),
                "replay": {"from_ts": self.range[0], "to_ts": self.range[1]}}

    def _stats(self, rows: int = 0) -> dict:
        return {"tracked": len(self.live.pos), "msgs_per_s": round(rows / max(self.speed, 1), 1), "queue_depth": 0}

    def _forecast_changes(self, now: int) -> tuple[list[str], dict | None]:
        """What the forecast changed, as the Hub's on_forecast works it out: ships whose risk changed are marked
        changed, and it returns the open gaps whose pred_* fields changed and the watchlist if it changed."""
        fc = self.live.forecast
        risk = {m: fc.risk_of(m) for m in fc.risk}
        for m in set(self._risk_sent) | set(risk):
            if m in self.live.pos and self._risk_sent.get(m) != risk.get(m):
                self.live.changed.add(m)
        self._risk_sent = risk
        sent, pending = {}, []
        for gid, g in self.live.gaps.items():
            if g["state"] == "open" and (fields := fc.gap_fields(gid, now)):
                sent[gid] = fields
                if self._pred_sent.get(gid) != fields:
                    pending.append(gid)
        self._pred_sent = sent
        prev = {e["mmsi"]: e["rank"] for e in (self.watchlist or {}).get("entries", [])}
        wl = fc.watchlist(self.live, now, prev)
        key = lambda w: [(e["mmsi"], e["rank"], e["decision"], e["reason_codes"]) for e in w["entries"]]   # noqa: E731
        changed = wl if self.watchlist is None or key(wl) != key(self.watchlist) else None
        self.watchlist = wl
        return pending, changed

    async def seek(self, t: int | None) -> None:
        self._stop()
        self.range = await self.history.range()
        lo, hi = self.range
        if lo is None:
            await self.send(self.status())   # nothing stored yet
            return
        self.t = max(lo, min(int(t if t is not None else hi), hi))
        t = self.t
        self.live = Live()
        self.live.forecast = FC.Forecast(config.PREDICT_P_ALERT)
        self._risk_sent, self._pred_sent, self.watchlist = {}, {}, None
        for row in await self.history.latest_positions(t, config.STALE_AFTER_S):
            self.live.apply(PositionReport(**row))
        gaps = [g for g in await self.history.gap_versions(None, t)
                if g["state"] == "open" or (g["end_ts"] or 0) >= t - CLOSED_SHOWN_MS]
        open_ships = sorted({g["mmsi"] for g in gaps if g["state"] == "open"} - set(self.live.pos))
        for row in await self.history.last_positions_of(open_ships, t, t - GAP_KEEP_MS):   # kept on the map in a gap
            self.live.apply(PositionReport(**row))
        ids = await self.history.identities(t, config.STALE_AFTER_S, open_ships)
        self.live.static.update({m: v for m, v in ids.items() if m in self.live.pos})
        self.live.apply_gaps([g for g in gaps if g["state"] == "closed" or g["mmsi"] in self.live.pos])
        open_ids = sorted(gid for gid, g in self.live.gaps.items() if g["state"] == "open")
        self.live.forecast.update(await self.history.scores(t - FC.RISK_TTL_MS, t),
                                  await self.history.routes(t - GAP_LOOKBACK_MS, t, open_ids), set(open_ids), t)
        self._forecast_changes(t)
        self.live.take_changes(t, config.STALE_AFTER_S)   # drops what is past its window, clears `changed`
        await self.send(self.status())
        await self.send({"type": "snapshot", "now_ts": t, "vessels": self.live.snapshot(), "trails": {},
                         "gaps": self.live.snapshot_gaps(t), "spoofs": [],
                         "watchlist": self.watchlist or {"snapshot_ts": t, "entries": []},
                         "coverage": [], "stats": self._stats()})
        if self.playing:
            self._start()

    async def play(self) -> None:
        self.playing = True
        self._start()
        await self.send(self.status())

    async def pause(self) -> None:
        self.playing = False
        self._stop()
        await self.send(self.status())

    async def set_speed(self, speed) -> None:
        try:
            self.speed = max(1, min(int(speed), MAX_SPEED))
        except (TypeError, ValueError):
            pass
        await self.send(self.status())

    def close(self) -> None:
        self.playing = False
        self._stop()

    def _start(self) -> None:
        if self._task is None or self._task.done():
            self._task = asyncio.create_task(self._run())

    def _stop(self) -> None:
        if self._task and not self._task.done():
            self._task.cancel()
        self._task = None

    async def _run(self) -> None:
        try:
            while self.playing:
                started = self._clock()
                if await self.step():
                    break
                await self._sleep(max(0.0, 1.0 - (self._clock() - started)))
        except asyncio.CancelledError:
            raise
        except Exception:  # a closed socket or a database error ends playback, never the connection handler
            log.exception("Replay playback stopped")
            self.playing = False
            try:   # tell the client it is paused now, or its play button stays on
                await self.send(self.status())
            except Exception:
                pass

    async def step(self) -> bool:
        """Advance one tick. Returns True when playback reached the end of the stored data and paused."""
        hi = self.range[1] or self.t
        new_t = min(self.t + self.speed * 1000, hi)
        old_t = self.t
        pos, sta = await self.history.between(old_t, new_t)
        for row in pos:
            self.live.apply(PositionReport(**row))
        for row in sta:
            self.live.apply(VesselStatic(**row))
        gaps = sorted(await self.history.gap_versions(old_t, new_t), key=lambda g: g["version"])
        self.live.apply_gaps(gaps)
        open_ids = {gid for gid, g in self.live.gaps.items() if g["state"] == "open"}
        self.live.forecast.update(await self.history.scores(old_t, new_t),
                                  await self.history.routes(old_t, new_t), open_ids, new_t)
        self.t = new_t
        pending, wl = self._forecast_changes(new_t)
        vessels, removed = self.live.take_changes(new_t, config.STALE_AFTER_S)
        sent_gaps = {g["id"]: g for g in gaps}
        sent_gaps.update({gid: self.live.gaps[gid] for gid in pending if gid in self.live.gaps})
        await self.send({"type": "delta", "now_ts": new_t, "vessels": vessels, "removed": removed,
                         "gaps": [self.live.gap_out(g, new_t) for g in sent_gaps.values()],
                         "spoofs": [], "watchlist": wl, "stats": self._stats(len(pos))})
        if new_t >= hi:
            self.range = await self.history.range()   # the live backend keeps writing; maybe there is more now
            if self.t >= (self.range[1] or self.t):
                self.playing = False
                await self.send(self.status())
                return True
        return False
