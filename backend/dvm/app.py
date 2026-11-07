"""FastAPI: /health and /ws (hello, snapshot, then deltas at 1 Hz, per 06 section 4.3)."""
from __future__ import annotations

import asyncio
import json
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from dvm import config
from dvm.ingest import Feed, now_ms, run_aisstream
from dvm.live import Live
from dvm.models import Envelope
from dvm.normalise import normalise
from dvm.rawlog import RawLog
from dvm.store import Store

log = logging.getLogger("dvm")


class Client:
    def __init__(self, ws: WebSocket):
        self.ws, self.seq, self.lock = ws, 0, asyncio.Lock()

    async def send(self, msg: dict) -> None:   # call with self.lock held
        self.seq += 1
        await asyncio.wait_for(self.ws.send_text(json.dumps({**msg, "seq": self.seq}, separators=(",", ":"))), 10)


class Hub:
    def __init__(self):
        self.live, self.feed = Live(), Feed()
        self.queue: asyncio.Queue = asyncio.Queue(maxsize=100_000)
        self.rawlog = RawLog(config.DATA_DIR)
        self.store = Store(config.TIGER_DATABASE_URL) if config.TIGER_DATABASE_URL else None
        self.clients: set[Client] = set()
        self.msgs_per_s = 0.0
        self._count = 0

    def stats(self) -> dict:
        return {"tracked": len(self.live.pos), "msgs_per_s": round(self.msgs_per_s, 1), "queue_depth": self.queue.qsize()}

    def sources(self) -> list[dict]:
        return [{"src": "aisstream", "state": self.feed.state, "msgs_per_s": round(self.msgs_per_s, 1)}]

    async def consume(self) -> None:
        while True:
            recv_ts, msg = await self.queue.get()
            try:
                raw = json.loads(msg)
            except ValueError:
                raw = msg if isinstance(msg, str) else msg.decode("utf-8", "replace")
            self._count += 1
            self.rawlog.write("aisstream", recv_ts, raw)
            if isinstance(raw, dict) and "error" in raw:
                log.error("AISStream says: %s", raw["error"])   # e.g. a bad API key; the server then closes
                continue
            for rec in normalise(Envelope(src="aisstream", recv_ts=recv_ts, raw=raw)):
                if self.live.apply(rec) and self.store:
                    self.store.add(rec)

    async def tick(self) -> None:
        last_sent = now_ms()
        n = 0
        while True:
            await asyncio.sleep(1)
            self.rawlog.flush()
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
                await asyncio.gather(*(self._send(c, msg) for c in list(self.clients)))
            n += 1
            if n % 10 == 0:
                db = f"db rows {self.store.rows_written}, error {self.store.last_error}" if self.store else "db off"
                log.info("aisstream %s: %.1f msg/s, %d ships, queue %d, dropped %d, clients %d, %s", self.feed.state,
                         self.msgs_per_s, len(self.live.pos), self.queue.qsize(), self.feed.dropped, len(self.clients), db)

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
                                                       config.AIS_BBOX, hub.queue, hub.feed)))
    else:
        log.warning("AISSTREAM_API_KEY is not set in backend/.env: no live data")
    if hub.store:
        tasks.append(asyncio.create_task(hub.store.run()))
    else:
        log.warning("TIGER_DATABASE_URL is not set: positions go to the JSONL log only")
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
                                      "last_error": hub.feed.last_error},
            "stats": hub.stats(), "clients": len(hub.clients),
            "db": {"enabled": bool(store), "rows_written": store.rows_written if store else 0,
                   "last_error": store.last_error if store else None}}


@app.websocket("/ws")
async def ws(websocket: WebSocket) -> None:
    # Milestone 2: validate the Auth0 access token here before accept().
    await websocket.accept()
    c = Client(websocket)
    try:
        async with c.lock:
            hub.clients.add(c)
            now = now_ms()
            await c.send({"type": "hello", "schema": 1, "mode": "live", "speed": 1, "now_ts": now,
                          "sources": hub.sources(), "bbox": config.AIS_BBOX})
            await c.send({"type": "snapshot", "now_ts": now, "vessels": hub.live.snapshot(), "trails": {}, "gaps": [],
                          "spoofs": [], "watchlist": {"snapshot_ts": now, "entries": []}, "coverage": [],
                          "stats": hub.stats()})
        while True:
            await websocket.receive_text()   # shortcut: client messages (subscribe, replay, detail) are ignored until needed
    except (WebSocketDisconnect, asyncio.TimeoutError, RuntimeError):
        pass
    finally:
        hub.clients.discard(c)
