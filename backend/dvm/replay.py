"""Per-client replay over /ws (06 section 4.3), built from the Tiger `positions` and `statics` hypertables.

Client: {"type": "replay", "action": "seek", "t": <ms>} · "play" · "pause" · {"action": "speed", "speed": n} · "live".
Server: a `status` message (mode, speed, paused, replay.from_ts / to_ts); after a seek, a `snapshot` whose `now_ts`
is the replay clock; while playing, a `delta` every wall-clock second whose `now_ts` advances by `speed` seconds.
A client in replay gets no live deltas. Playing pauses itself at the end of the stored data.
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone
from typing import Awaitable, Callable

from dvm import config
from dvm.live import STATIC_FIELDS, Live
from dvm.models import PositionReport, VesselStatic

log = logging.getLogger(__name__)

MAX_SPEED = 600          # replay seconds per wall-clock second
DEFAULT_SPEED = 60
POS_COLS = ("mmsi, ts, recv_ts, lat, lon, sog_kn, cog_deg, heading_deg, nav_status, cls, msg_type, ts_quality, "
            "src, q")
STATIC_COLS = ("mmsi, ts, recv_ts, imo, name, callsign, ship_type, type_group, dim_a_m, dim_b_m, dim_c_m, dim_d_m, "
               "length_m, beam_m, draught_m, destination, eta_utc, mid, flag_iso2, src, q")


def _dt(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, timezone.utc)


def _ms(dt: datetime | None) -> int | None:
    return None if dt is None else int(dt.timestamp() * 1000)


class TigerHistory:
    """The only SQL replay needs."""

    def __init__(self, pool):
        self.pool = pool

    async def range(self) -> tuple[int | None, int | None]:
        async with self.pool.acquire() as con:
            row = await con.fetchrow("SELECT (SELECT time FROM positions ORDER BY time LIMIT 1) AS t0, "
                                     "(SELECT time FROM positions ORDER BY time DESC LIMIT 1) AS t1")
        return _ms(row["t0"]), _ms(row["t1"])

    async def latest_positions(self, t: int, window_s: int) -> list[dict]:
        """The last position of every ship heard in (t - window, t]."""
        async with self.pool.acquire() as con:
            rows = await con.fetch(f"SELECT DISTINCT ON (mmsi) {POS_COLS} FROM positions WHERE time > $1 AND time <= $2 "
                                   "ORDER BY mmsi, time DESC", _dt(t - window_s * 1000), _dt(t))
        return [dict(r) for r in rows]

    async def identities(self, t: int, window_s: int) -> dict[int, dict]:
        """Latest known non-null identity fields at time t for every ship heard in (t - window, t] (the merge Live does).

        Joined in SQL: passing ~27k MMSIs as an ANY(array) ran Tiger out of memory, and TimescaleDB last() keeps one
        value per group where array_agg(...)[1] collected every row.
        """
        def pick(f: str) -> str:
            cond = f"s.{f} IS NOT NULL" + (" AND s.type_group <> 'unknown'" if f == "type_group" else "")
            return f"last(s.{f}, s.time) FILTER (WHERE {cond}) AS {f}"

        sql = ("WITH ships AS (SELECT DISTINCT mmsi FROM positions WHERE time > $1 AND time <= $2) "
               f"SELECT s.mmsi, {', '.join(pick(f) for f in STATIC_FIELDS)} FROM statics s JOIN ships USING (mmsi) "
               "WHERE s.time <= $2 AND s.time > $2 - interval '24 hours' GROUP BY s.mmsi")
        async with self.pool.acquire() as con:
            rows = await con.fetch(sql, _dt(t - window_s * 1000), _dt(t))
        return {r["mmsi"]: {f: r[f] for f in STATIC_FIELDS if r[f] is not None} for r in rows}

    async def between(self, a: int, b: int) -> tuple[list[dict], list[dict]]:
        """Positions and statics with time in (a, b], oldest first."""
        async with self.pool.acquire() as con:
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
        self._task: asyncio.Task | None = None

    def status(self, mode: str = "replay") -> dict:
        return {"type": "status", "now_ts": self.t, "mode": mode, "speed": self.speed if mode == "replay" else 1,
                "paused": not self.playing, "sources": self.sources(),
                "replay": {"from_ts": self.range[0], "to_ts": self.range[1]}}

    def _stats(self, rows: int = 0) -> dict:
        return {"tracked": len(self.live.pos), "msgs_per_s": round(rows / max(self.speed, 1), 1), "queue_depth": 0}

    async def seek(self, t: int | None) -> None:
        self._stop()
        self.range = await self.history.range()
        lo, hi = self.range
        if lo is None:
            await self.send(self.status())   # nothing stored yet
            return
        self.t = max(lo, min(int(t if t is not None else hi), hi))
        self.live = Live()
        for row in await self.history.latest_positions(self.t, config.STALE_AFTER_S):
            self.live.apply(PositionReport(**row))
        ids = await self.history.identities(self.t, config.STALE_AFTER_S)
        self.live.static.update({m: v for m, v in ids.items() if m in self.live.pos})
        self.live.changed.clear()
        await self.send(self.status())
        await self.send({"type": "snapshot", "now_ts": self.t, "vessels": self.live.snapshot(), "trails": {},
                         "gaps": [], "spoofs": [], "watchlist": {"snapshot_ts": self.t, "entries": []},
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

    async def step(self) -> bool:
        """Advance one tick. Returns True when playback reached the end of the stored data and paused."""
        hi = self.range[1] or self.t
        new_t = min(self.t + self.speed * 1000, hi)
        pos, sta = await self.history.between(self.t, new_t)
        for row in pos:
            self.live.apply(PositionReport(**row))
        for row in sta:
            self.live.apply(VesselStatic(**row))
        self.t = new_t
        vessels, removed = self.live.take_changes(new_t, config.STALE_AFTER_S)
        await self.send({"type": "delta", "now_ts": new_t, "vessels": vessels, "removed": removed, "gaps": [],
                         "spoofs": [], "watchlist": None, "stats": self._stats(len(pos))})
        if new_t >= hi:
            self.range = await self.history.range()   # the live backend keeps writing; maybe there is more now
            if self.t >= (self.range[1] or self.t):
                self.playing = False
                await self.send(self.status())
                return True
        return False
