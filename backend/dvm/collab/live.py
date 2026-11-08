"""Collaboration over the existing /ws: session join, live presence, broadcasts, and token expiry.

Presence lives in memory only. Fan-out runs in its own task (run()), never inside the 1 s ship tick; database
writes happen in the WebSocket handler or the REST routes, never in the tick either.
"""
from __future__ import annotations

import asyncio
import logging
import time
import uuid

import jwt

from dvm import auth
from dvm.collab.store import MemoryStore, PgStore
from dvm.collab import schema
from dvm.sources.routes import MMSI_MAX, MMSI_MIN

log = logging.getLogger(__name__)

WS_TYPES = {"auth", "session_join", "session_leave", "presence"}
FANOUT_S = 1.0          # presence goes out at most once a second per session
SILENT_AFTER_S = 30     # a user who sends no presence for this long drops off the list
MAX_FOLLOWING = 100
SEND_TIMEOUT_S = 5


def _mmsi(v) -> int | None:
    return v if isinstance(v, int) and not isinstance(v, bool) and MMSI_MIN <= v <= MMSI_MAX else None


def _bbox(v):
    if isinstance(v, list) and len(v) == 4 and all(isinstance(x, (int, float)) and not isinstance(x, bool) for x in v):
        return [float(x) for x in v]
    return None


class CollabHub:
    def __init__(self):
        self.reset()

    def reset(self) -> None:
        self.store: PgStore | MemoryStore | None = None   # None until Tiger's tables are set up (routes answer 503)
        self.status = "pending"                           # pending | ready | memory | failed: <error>
        self.joined: dict = {}       # client -> (session_id, user dict)
        self.presence: dict = {}     # client -> {viewing, following, bbox, private, ts}
        self.dirty: set[str] = set()  # sessions whose presence changed since the last fan-out
        self.expiry: dict = {}       # client -> task that closes the socket when its token expires
        self.subs: dict = {}         # client -> the identity (token sub; dev|name without Auth0) for pushes to one user
        self._tasks: set = set()

    # --- lifecycle --------------------------------------------------------------------------------------------
    async def run(self, dvm_store) -> None:
        """Started from lifespan: set up the tables (Tiger) or use memory (no database), then fan presence out."""
        self.reset()
        if dvm_store is None:
            self.store, self.status = MemoryStore(), "memory"
            log.warning("Collaboration: no Tiger Data, sessions are kept in memory and lost on restart")
        else:
            t = asyncio.create_task(self._setup(dvm_store))
            self._tasks.add(t)
            t.add_done_callback(self._tasks.discard)
        while True:
            await asyncio.sleep(FANOUT_S)
            try:
                await self.fanout()
            except Exception:  # noqa: BLE001 - a presence bug must not stop the loop
                log.exception("Presence fan-out failed")

    async def _setup(self, dvm_store) -> None:
        while dvm_store.pool is None:   # the dvm store sets its pool once its own tables (and dvm_append_only) exist
            await asyncio.sleep(1)
        try:
            async with dvm_store.pool.acquire() as con:
                await schema.setup(con)
            self.store, self.status = PgStore(dvm_store.pool), "ready"
        except Exception as e:  # noqa: BLE001 - ships keep flowing; collaboration routes answer 503
            self.status = f"failed: {type(e).__name__}: {e}"
            log.warning("Collaboration tables setup failed: %s", e)

    def attach(self, c) -> None:
        """A socket passed its auth check: close it when the token expires (unless it sends a fresher one)."""
        if sub := (getattr(c, "claims", None) or {}).get("sub"):
            self.subs[c] = sub
        exp = (getattr(c, "claims", None) or {}).get("exp")
        if exp:
            self._watch(c, exp)

    def detach(self, c) -> None:
        self.subs.pop(c, None)
        if t := self.expiry.pop(c, None):
            t.cancel()
        self._leave(c)

    def _watch(self, c, exp: float) -> None:
        if old := self.expiry.pop(c, None):
            old.cancel()
        self.expiry[c] = asyncio.create_task(self._close_at(c, exp))

    async def _close_at(self, c, exp: float) -> None:
        await asyncio.sleep(max(0.0, exp - time.time()))
        await self._close(c, "token expired")

    async def _close(self, c, reason: str) -> None:
        log.info("Closing a WebSocket: %s", reason)
        self._leave(c)
        try:
            async with asyncio.timeout(SEND_TIMEOUT_S):
                async with c.lock:
                    await c.ws.close(code=1008, reason=reason)
        except Exception:  # noqa: BLE001 - already closed
            pass

    def _leave(self, c) -> None:
        if (j := self.joined.pop(c, None)) is not None:
            self.presence.pop(c, None)
            self.dirty.add(j[0])

    # --- WebSocket messages -----------------------------------------------------------------------------------
    async def on_ws(self, c, msg: dict) -> None:
        try:
            await self._on_ws(c, msg)
        except Exception:  # noqa: BLE001 - a database hiccup must not drop the ship stream
            log.exception("Collaboration message failed: %s", msg.get("type"))
            await self._send(c, {"type": "error", "code": "unavailable", "for": msg.get("type")})

    async def _on_ws(self, c, msg: dict) -> None:
        kind = msg.get("type")
        if kind == "auth":
            await self._reauth(c, msg)
        elif kind == "session_join":
            await self._join(c, msg)
        elif kind == "session_leave":
            self._leave(c)
        elif kind == "presence":
            self._presence(c, msg)

    def _sub(self, c, msg: dict) -> str | None:
        if not auth.ENABLED:   # local dev: anyone, optionally as a named test user
            return f"dev|{msg.get('dev_user') or 'local'}"
        claims = getattr(c, "claims", None) or {}
        if claims.get("exp", 0) <= time.time():
            return None
        return claims.get("sub")

    async def _reauth(self, c, msg: dict) -> None:
        """A fresher access token on an open socket (the SPA renews it silently): extends the socket's life."""
        if not auth.ENABLED:   # local dev: the socket says who it is, like X-Dev-User on the routes
            if isinstance(msg.get("dev_user"), str):
                self.subs[c] = f"dev|{msg['dev_user']}"
            return
        try:
            claims = await auth.verify_async(msg.get("token") or "")
        except jwt.PyJWTError:
            await self._close(c, "login required")
            return
        if claims.get("sub") != (getattr(c, "claims", None) or {}).get("sub"):
            await self._close(c, "a different user")   # one socket, one identity
            return
        c.claims = claims
        self._watch(c, claims["exp"])

    async def _join(self, c, msg: dict) -> None:
        sid = msg.get("session_id")
        sub = self._sub(c, msg)
        if sub is None:
            await self._close(c, "token expired")
            return
        try:
            sid = str(uuid.UUID(sid))
        except (ValueError, TypeError, AttributeError):
            await self._send(c, {"type": "error", "code": "bad_request", "for": "session_join"})
            return
        if self.store is None:
            await self._send(c, {"type": "error", "code": "unavailable", "for": "session_join"})
            return
        user = await self.store.upsert_user(sub)
        role = await self.store.role(sid, user["id"])
        if role is None:   # not a member, or no such session: the same answer for both
            await self._send(c, {"type": "error", "code": "forbidden", "for": "session_join", "session_id": sid})
            return
        await self.store.touch(sid, user["id"])
        await self.store.add_activity(sid, user["id"], "joined")
        detail = await self.store.session_detail(sid)
        self._leave(c)   # one session per socket
        self.joined[c] = (sid, user)
        self.dirty.add(sid)   # the next fan-out sends the newcomer everyone, and everyone the newcomer
        await self._send(c, {"type": "session_joined", "session_id": sid, "role": role, "user_id": user["id"],
                             "session": detail})

    def _presence(self, c, msg: dict) -> None:
        j = self.joined.get(c)
        if j is None:
            return
        following = msg.get("following")
        following = [m for m in following if _mmsi(m)][:MAX_FOLLOWING] if isinstance(following, list) else []
        self.presence[c] = {"viewing": _mmsi(msg.get("viewing")), "following": following,
                            "bbox": _bbox(msg.get("bbox")), "private": msg.get("private") is True,
                            "ts": int(time.time() * 1000)}
        self.dirty.add(j[0])

    # --- fan-out ----------------------------------------------------------------------------------------------
    def users_in(self, sid: str) -> list[dict]:
        """Visible presence in a session: one entry per user (their freshest tab), private users left out."""
        best: dict[str, dict] = {}
        for c, (s, user) in self.joined.items():
            p = self.presence.get(c)
            if s != sid or p is None or p["private"]:
                continue
            if user["id"] not in best or p["ts"] > best[user["id"]]["ts"]:
                best[user["id"]] = {"id": user["id"], "name": user["name"], "picture": user["picture"],
                                    **{k: p[k] for k in ("viewing", "following", "bbox", "ts")}}
        return sorted(best.values(), key=lambda u: u["id"])

    async def fanout(self) -> None:
        cutoff = (time.time() - SILENT_AFTER_S) * 1000
        for c, p in list(self.presence.items()):
            if p["ts"] < cutoff:
                del self.presence[c]
                if c in self.joined:
                    self.dirty.add(self.joined[c][0])
        dirty, self.dirty = self.dirty, set()
        sends = []
        for sid in dirty:
            msg = {"type": "presence", "session_id": sid, "users": self.users_in(sid)}
            sends += [self._send(c, msg) for c, (s, _) in list(self.joined.items()) if s == sid]
        if sends:
            await asyncio.gather(*sends)

    def broadcast(self, sid: str, msg: dict) -> None:
        """Send to every socket joined to the session, without making the caller (a REST route) wait for them."""
        targets = [c for c, (s, _) in self.joined.items() if s == sid]
        if targets:
            t = asyncio.gather(*(self._send(c, msg) for c in targets))   # scheduled now; kept so it isn't collected
            self._tasks.add(t)
            t.add_done_callback(self._tasks.discard)

    def push_user(self, sub: str | None, msg: dict) -> None:
        """Send to every open socket of one identity (whether or not it has joined a session)."""
        targets = [c for c, s in self.subs.items() if s == sub]
        if targets:
            t = asyncio.gather(*(self._send(c, msg) for c in targets))
            self._tasks.add(t)
            t.add_done_callback(self._tasks.discard)

    def update_user(self, user: dict) -> None:
        """A profile changed: the joined sockets of that user show the new name and picture."""
        for c, (sid, u) in list(self.joined.items()):
            if u["id"] == user["id"]:
                self.joined[c] = (sid, user)
                self.dirty.add(sid)

    async def _send(self, c, msg: dict) -> None:
        try:
            async with c.lock:
                await c.send(msg)
        except Exception:  # noqa: BLE001 - closed or too slow: the ship tick drops it, so do we
            self._leave(c)


hub = CollabHub()
