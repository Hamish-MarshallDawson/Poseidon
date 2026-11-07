"""FastAPI: /health and /ws (hello, snapshot, then deltas at 1 Hz, per 06 section 4.3)."""
from __future__ import annotations

import asyncio
import json
import logging
import time
from contextlib import asynccontextmanager

import jwt
from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from dvm import auth, config, coverage, limits, replay
from dvm.briefing.routes import make_router as briefing_router
from dvm.ingest import Feed, now_ms, run_aisstream
from dvm.live import Live
from dvm.merge import FeedMerger
from dvm.models import Envelope
from dvm.normalise import normalise
from dvm.rawlog import RawLog
from dvm.sources import digitraffic, schema as sources_schema
from dvm.sources.routes import make_router as sources_router
from dvm.store import Store

log = logging.getLogger("dvm")
BAD_LOG_EVERY_S = 10


class Client:
    def __init__(self, ws: WebSocket):
        self.ws, self.seq, self.lock = ws, 0, asyncio.Lock()
        self.replay: replay.ReplaySession | None = None   # set while this client watches the past

    async def send(self, msg: dict) -> None:   # call with self.lock held
        self.seq += 1
        await asyncio.wait_for(self.ws.send_text(json.dumps({**msg, "seq": self.seq}, separators=(",", ":"))), 10)


class Hub:
    def __init__(self):
        self.live, self.feed = Live(), Feed()
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=limits.QUEUE_MAX)
        self.limiter = limits.AisLimiter(config.DATA_DIR / "aisstream_limits.json")
        self.rawlog = RawLog(config.DATA_DIR)
        self.store = Store(config.TIGER_DATABASE_URL) if config.TIGER_DATABASE_URL else None
        self.clients: set[Client] = set()
        self.msgs_per_s = 0.0
        self._count = 0
        self.bad_messages = 0          # messages that raised while being handled, then skipped
        self.last_bad: str | None = None
        self._bad_logged_at = float("-inf")
        self.merger = FeedMerger()     # every feed's records pass through here before the map and the store
        self.digitraffic = digitraffic.Stats() if config.DIGITRAFFIC else None
        self.sources_schema: str = "pending"   # observations tables: pending | ready | failed: <error>

    def ingest(self, rec, now: int) -> None:
        """One normalised record from any feed: merge it across feeds, then map and store what the merger emits."""
        self._emit(self.merger.push(rec, now))

    def _emit(self, recs) -> None:
        for rec in recs:   # the merger has already dropped cross-feed copies and repeats, so store everything it emits
            self.live.apply(rec)
            if self.store:
                self.store.add(rec)

    def digitraffic_sink(self, rec) -> None:
        try:
            self.ingest(rec, now_ms())
        except Exception as e:  # one bad record must never stop the Digitraffic stream
            self._bad(e)

    def stats(self) -> dict:
        return {"tracked": len(self.live.pos), "msgs_per_s": round(self.msgs_per_s, 1), "queue_depth": self.queue.qsize()}

    def snapshot_msg(self, now: int) -> dict:
        return {"type": "snapshot", "now_ts": now, "vessels": self.live.snapshot(), "trails": {}, "gaps": [],
                "spoofs": [], "watchlist": {"snapshot_ts": now, "entries": []}, "coverage": [], "stats": self.stats()}

    def sources(self) -> list[dict]:
        out = [{"src": "aisstream", "state": self.feed.state, "msgs_per_s": round(self.msgs_per_s, 1)}]
        if self.digitraffic:
            out.append({"src": "digitraffic", "state": "up" if self.digitraffic.connected else "down"})
        return out

    async def consume(self) -> None:
        while True:
            recv_ts, msg = await self.queue.get()
            try:
                self.handle(recv_ts, msg)
            except Exception as e:  # one bad message must never stop ingest
                self._bad(e)

    def _bad(self, e: Exception) -> None:
        self.bad_messages += 1
        self.last_bad = f"{type(e).__name__}: {str(e)[:200]}"
        now = time.monotonic()
        if now - self._bad_logged_at >= BAD_LOG_EVERY_S:   # rate-limited: a stream of junk can't flood the log
            log.warning("Skipped a bad message (%d so far): %s", self.bad_messages, self.last_bad,
                        exc_info=self._bad_logged_at == float("-inf"))   # full traceback the first time only
            self._bad_logged_at = now

    def handle(self, recv_ts: int, msg) -> None:
        try:
            raw = json.loads(msg)
        except ValueError:
            raw = msg if isinstance(msg, str) else msg.decode("utf-8", "replace")
        self._count += 1
        self.rawlog.write("aisstream", recv_ts, raw)
        if isinstance(raw, dict) and "error" in raw:
            log.error("AISStream says: %s", raw["error"])   # e.g. a bad API key; the server then closes
            return
        if isinstance(raw, dict) and raw.get("MessageType") == "SubscriptionConfirmation":
            self.feed.state = "up"   # an invalid subscription gets no confirmation
            if (raw.get("Message") or {}).get("CompressionEnabled"):
                log.info("AISStream subscription confirmed, compression on")
            else:   # uncompressed connections are bandwidth-limited and drop messages, which look like dark ships
                log.warning("AISStream subscription confirmed WITHOUT compression: expect dropped messages")
            return
        for rec in normalise(Envelope(src="aisstream", recv_ts=recv_ts, raw=raw)):
            self.ingest(rec, now_ms())

    async def tick(self) -> None:
        last_sent = now_ms()
        n = 0
        while True:
            await asyncio.sleep(1)
            self.rawlog.flush()
            try:
                self._emit(self.merger.flush(now_ms()))   # fixes held for the other feed's copy, now due
            except Exception as e:  # never let a merger bug stop the 1 Hz loop
                self._bad(e)
            self.msgs_per_s = 0.7 * self.msgs_per_s + 0.3 * self._count   # smoothed per-second rate
            self._count = 0
            now = now_ms()
            vessels, removed = self.live.take_changes(now, config.STALE_AFTER_S)
            if vessels or removed:
                msg = {"type": "delta", "now_ts": now, "vessels": vessels, "removed": removed, "gaps": [], "spoofs": [],
                       "watchlist": None, "stats": self.stats()}
            elif now - last_sent >= 10_000:
                msg = {"type": "ping", "now_ts": now}
            else:
                msg = None
            if msg:
                last_sent = now
                await asyncio.gather(*(self._send(c, msg) for c in list(self.clients) if c.replay is None))
            n += 1
            if n % 10 == 0:
                db = f"db rows {self.store.rows_written}, error {self.store.last_error}" if self.store else "db off"
                dt = self.digitraffic
                db += (f", digitraffic {'up' if dt.connected else 'down'} {dt.positions} pos, merged "
                       f"{self.merger.stats['merged']}" if dt else ", digitraffic off")
                log.info("aisstream %s: %.1f msg/s, %d ships, queue %d, dropped %d, bad %d, clients %d, %s", self.feed.state,
                         self.msgs_per_s, len(self.live.pos), self.queue.qsize(), self.feed.dropped, self.bad_messages,
                         len(self.clients), db)

    async def run_digitraffic(self) -> None:
        """paho reconnects by itself; this only restarts the stream if it ever ends with an error."""
        while True:
            try:
                await digitraffic.run(self.digitraffic_sink, self.rawlog, stats=self.digitraffic)
            except asyncio.CancelledError:
                raise
            except Exception as e:  # noqa: BLE001 - log and restart, the live map keeps AISStream meanwhile
                self.digitraffic.connected, self.digitraffic.last_error = False, f"{type(e).__name__}: {e}"
                log.warning("Digitraffic stream stopped (%s); restarting in 30 s", self.digitraffic.last_error)
            await asyncio.sleep(30)

    async def setup_sources_schema(self) -> None:
        """observations and source_windows (dvm/sources/schema.py), once the store has connected and set up its own
        tables. Idempotent and best-effort: a failure is logged and shown in /health, positions keep flowing."""
        while self.store.pool is None:
            await asyncio.sleep(1)
        try:
            async with self.store.pool.acquire() as con:
                await sources_schema.setup(con)
            self.sources_schema = "ready"
        except Exception as e:  # noqa: BLE001
            self.sources_schema = f"failed: {type(e).__name__}: {e}"
            log.warning("observations tables setup failed, data routes may 500: %s", e)

    async def _send(self, c: Client, msg: dict) -> None:
        try:
            async with c.lock:
                await c.send(msg)
        except Exception:  # closed or too slow: the client reconnects and gets a fresh snapshot
            self.clients.discard(c)


hub: Hub


@asynccontextmanager
async def lifespan(app: FastAPI):
    global hub
    hub = Hub()
    tasks = [asyncio.create_task(hub.consume()), asyncio.create_task(hub.tick())]
    if config.AISSTREAM_API_KEY:
        tasks.append(asyncio.create_task(run_aisstream(config.AISSTREAM_URL, config.AISSTREAM_API_KEY,
                                                       config.AIS_BBOX, hub.queue, hub.feed, hub.limiter)))
    else:
        log.warning("AISSTREAM_API_KEY is not set in .env: no live data")
    if hub.digitraffic:
        tasks.append(asyncio.create_task(hub.run_digitraffic()))
    else:
        log.info("DIGITRAFFIC=0: Digitraffic stream off")
    if hub.store:
        tasks.append(asyncio.create_task(hub.store.run()))
        tasks.append(asyncio.create_task(hub.setup_sources_schema()))
    else:
        log.warning("TIGER_DATABASE_URL is not set: positions go to the JSONL log only")
    if not auth.ENABLED:
        log.warning("AUTH0_DOMAIN / AUTH0_AUDIENCE not set: /ws is open to anyone (local dev only)")
    yield
    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    hub.rawlog.close()
    if hub.store:
        await hub.store.close()


app = FastAPI(title="Dark Vessel Monitor", lifespan=lifespan)
app.add_middleware(CORSMiddleware, allow_origins=config.FRONTEND_ORIGINS, allow_methods=["*"], allow_headers=["*"])


@app.get("/health")
def health() -> dict:
    store = hub.store
    return {"ok": True, "aisstream": {"state": hub.feed.state, "received": hub.feed.received, "dropped": hub.feed.dropped,
                                      "last_error": hub.feed.last_error, "bad_messages": hub.bad_messages,
                                      "last_bad": hub.last_bad, "limits": hub.limiter.status()},
            "digitraffic": ({"enabled": True, "connected": dt.connected, "received": dt.received,
                             "positions": dt.positions, "statics": dt.statics, "last_error": dt.last_error}
                            if (dt := hub.digitraffic) else {"enabled": False}),
            "merger": hub.merger.stats, "sources_schema": hub.sources_schema,
            "stats": hub.stats(), "clients": len(hub.clients),
            "db": {"enabled": bool(store), "rows_written": store.rows_written if store else 0,
                   "last_error": store.last_error if store else None}}


async def require_login(authorization: str | None = Header(None)) -> None:
    """Bearer access token, checked like the WebSocket's. Open when Auth0 is not configured (local dev)."""
    if not auth.ENABLED:
        return
    scheme, _, token = (authorization or "").partition(" ")
    if scheme != "Bearer" or not token:
        raise HTTPException(401, "login required", headers={"WWW-Authenticate": "Bearer"})
    try:
        await auth.verify_async(token)
    except jwt.PyJWTError:
        raise HTTPException(401, "invalid token", headers={"WWW-Authenticate": "Bearer"})


@app.get("/coverage", dependencies=[Depends(require_login)])
async def get_coverage(minutes: int = coverage.DEFAULT_MINUTES, bbox: str | None = None) -> dict:
    """Per-cell message and ship counts per minute for the last `minutes` (capped), optionally in a bbox."""
    try:
        box = coverage.parse_bbox(bbox)
    except ValueError as e:
        raise HTTPException(422, str(e))
    pool = hub.store.pool if hub.store else None
    if pool is None:
        raise HTTPException(503, "Tiger Data is not connected")
    return {"cells": await coverage.coverage(pool, minutes, box)}


@app.get("/history/range", dependencies=[Depends(require_login)])
async def history_range() -> dict:
    """The time span replay can show: first and last stored position, epoch ms (null when nothing is stored)."""
    pool = hub.store.pool if hub.store else None
    if pool is None:
        raise HTTPException(503, "Tiger Data is not connected")
    lo, hi = await replay.TigerHistory(pool).range()
    return {"from_ts": lo, "to_ts": hi}


async def handle_replay(c: Client, msg: dict) -> None:
    """06 section 4.3 replay actions, plus "live" to go back. A client in replay gets no live broadcasts."""
    async def send(m: dict) -> None:
        async with c.lock:
            await c.send(m)

    action = msg.get("action")
    if action == "live":
        session, c.replay = c.replay, None
        if session:
            session.close()
            now = now_ms()
            await send({**session.status("live"), "now_ts": now, "paused": False})
            await send(hub.snapshot_msg(now))
        return
    pool = hub.store.pool if hub.store else None
    if pool is None:
        log.warning("Replay asked for, but Tiger Data is not connected")
        return
    if c.replay is None:
        c.replay = replay.ReplaySession(replay.TigerHistory(pool), send, hub.sources)
        try:   # play, pause or speed from live starts at the newest stored time, paused
            await c.replay.seek(msg.get("t") if action == "seek" else None)
        except BaseException:   # no replay snapshot was sent: stay live rather than freeze the client's map
            c.replay.close()
            c.replay = None
            raise
        if action == "seek":
            return
    if action == "seek":
        await c.replay.seek(msg.get("t"))
    elif action == "play":
        await c.replay.play()
    elif action == "pause":
        await c.replay.pause()
    elif action == "speed":
        await c.replay.set_speed(msg.get("speed"))


class _CurrentHub:
    """The hub is built in lifespan, after routers are mounted: routers get this and read the live one per request."""

    @property
    def live(self) -> Live:
        return hub.live


app.include_router(briefing_router(_CurrentHub(), require_login))   # POST /briefing, POST /briefing/speech
# GET /observations, /sources, /model/observations, /model/positions, /model/statics (dvm/sources/routes.py)
app.include_router(sources_router(lambda: hub.store.pool if hub.store else None, require_login))


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    # Browsers can't set headers on a WebSocket, and a token in the URL lands in access logs, so the client's
    # first message is {"type": "auth", "token": "<Auth0 access token>"}; nothing is sent until it checks out.
    # shortcut: the token is checked once at connect, not again when it expires; recheck if sessions get long.
    await websocket.accept()
    c = Client(websocket)
    try:
        if auth.ENABLED:
            try:
                first = json.loads(await asyncio.wait_for(websocket.receive_text(), 10))
                await auth.verify_async(first["token"] if first.get("type") == "auth" else "")
            except (ValueError, KeyError, TypeError, AttributeError, asyncio.TimeoutError, jwt.PyJWTError) as e:
                log.info("WebSocket refused: %s", type(e).__name__)
                await websocket.close(code=1008, reason="login required")
                return
        async with c.lock:
            hub.clients.add(c)
            now = now_ms()
            await c.send({"type": "hello", "schema": 1, "mode": "live", "speed": 1, "now_ts": now,
                          "sources": hub.sources(), "bbox": config.AIS_BBOX})
            await c.send(hub.snapshot_msg(now))
        while True:
            # shortcut: `subscribe` is ignored until needed.
            try:
                msg = json.loads(await websocket.receive_text())
                kind = msg.get("type")
            except (ValueError, AttributeError):
                continue
            if kind == "replay":
                try:
                    await handle_replay(c, msg)
                except (WebSocketDisconnect, asyncio.TimeoutError, RuntimeError):
                    raise
                except Exception:  # a database hiccup must not drop the connection
                    log.exception("Replay request failed: %s", msg.get("action"))
            elif kind == "detail":
                state = c.replay.live if c.replay else hub.live   # in replay, details are as of the replay time
                if msg.get("mmsi") in state.pos:
                    async with c.lock:
                        await c.send(state.detail(msg["mmsi"]))
    except (WebSocketDisconnect, asyncio.TimeoutError, RuntimeError):
        pass
    finally:
        hub.clients.discard(c)
        if c.replay:
            c.replay.close()
