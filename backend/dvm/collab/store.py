"""Collaboration storage: PgStore over the Tiger pool, and MemoryStore, the same interface in memory (tests and local
dev without a database). Every time is epoch ms UTC; ids are uuid strings (documents and activity: integers)."""
from __future__ import annotations

import itertools
import time
import uuid
from datetime import datetime

from dvm.collab.invites import MemInvites, PgInvites

DOCS_IN_DETAIL = 200          # newest documents returned with a session


def _ms(dt: datetime | None) -> int | None:
    return None if dt is None else int(dt.timestamp() * 1000)


def _user(r) -> dict:
    return {"id": str(r["id"]), "name": r["display_name"], "picture": r["picture_url"]}


def _entry(r) -> dict:
    return {"mmsi": r["mmsi"], "status": r["status"], "added_by": str(r["added_by"]), "added_at": _ms(r["added_at"]),
            "updated_by": str(r["updated_by"]), "updated_at": _ms(r["updated_at"])}


def _doc(r) -> dict:
    return {"id": r["id"], "mmsi": r["mmsi"], "author_id": str(r["author_id"]), "body": r["body"],
            "created_at": _ms(r["created_at"]), "kind": r["kind"], "mmsis": list(r["mmsis"])}


class PgStore:
    def __init__(self, pool):
        self.pool = pool
        self.inv = PgInvites(pool)       # invites with an addressee (invites.py)

    async def upsert_user(self, sub: str) -> dict:
        r = await self.pool.fetchrow(
            "INSERT INTO users (auth0_sub) VALUES ($1) ON CONFLICT (auth0_sub) DO UPDATE SET seen_at = now() "
            "RETURNING id, display_name, picture_url", sub)
        return _user(r)

    async def set_profile(self, user_id: str, name: str | None, picture: str | None) -> dict:
        r = await self.pool.fetchrow("UPDATE users SET display_name = $2, picture_url = $3 WHERE id = $1 "
                                     "RETURNING id, display_name, picture_url", uuid.UUID(user_id), name, picture)
        return _user(r)

    async def last_session(self, user_id: str) -> dict | None:
        r = await self.pool.fetchrow(
            "SELECT s.id, s.title, m.role, m.last_active_at FROM collab_members m JOIN collab_sessions s "
            "ON s.id = m.session_id WHERE m.user_id = $1 ORDER BY m.last_active_at DESC LIMIT 1", uuid.UUID(user_id))
        return r and {"id": str(r["id"]), "title": r["title"], "role": r["role"],
                      "last_active_at": _ms(r["last_active_at"])}

    async def create_session(self, user_id: str, title: str) -> str:
        async with self.pool.acquire() as con, con.transaction():
            sid = await con.fetchval("INSERT INTO collab_sessions (title, created_by) VALUES ($1, $2) RETURNING id",
                                     title, uuid.UUID(user_id))
            await con.execute("INSERT INTO collab_members (session_id, user_id, role) VALUES ($1, $2, 'owner')",
                              sid, uuid.UUID(user_id))
        return str(sid)

    async def list_sessions(self, user_id: str) -> list[dict]:
        rows = await self.pool.fetch(
            "SELECT s.id, s.title, s.created_at, m.role, m.last_active_at, "
            "(SELECT count(*) FROM collab_members x WHERE x.session_id = s.id) AS members "
            "FROM collab_members m JOIN collab_sessions s ON s.id = m.session_id WHERE m.user_id = $1 "
            "ORDER BY m.last_active_at DESC", uuid.UUID(user_id))
        return [{"id": str(r["id"]), "title": r["title"], "role": r["role"], "created_at": _ms(r["created_at"]),
                 "last_active_at": _ms(r["last_active_at"]), "members": r["members"]} for r in rows]

    async def role(self, session_id: str, user_id: str) -> str | None:
        return await self.pool.fetchval("SELECT role FROM collab_members WHERE session_id = $1 AND user_id = $2",
                                        uuid.UUID(session_id), uuid.UUID(user_id))

    async def touch(self, session_id: str, user_id: str) -> None:
        await self.pool.execute("UPDATE collab_members SET last_active_at = now() WHERE session_id = $1 AND user_id = $2",
                                uuid.UUID(session_id), uuid.UUID(user_id))

    async def member(self, session_id: str, user_id: str) -> dict | None:
        r = await self.pool.fetchrow(
            "SELECT u.id, u.display_name, u.picture_url, m.role, m.joined_at, m.last_active_at FROM collab_members m "
            "JOIN users u ON u.id = m.user_id WHERE m.session_id = $1 AND m.user_id = $2",
            uuid.UUID(session_id), uuid.UUID(user_id))
        return r and {**_user(r), "role": r["role"], "joined_at": _ms(r["joined_at"]),
                      "last_active_at": _ms(r["last_active_at"])}

    async def session_detail(self, session_id: str) -> dict | None:
        sid = uuid.UUID(session_id)
        async with self.pool.acquire() as con:
            s = await con.fetchrow("SELECT id, title, created_by, created_at FROM collab_sessions WHERE id = $1", sid)
            if s is None:
                return None
            members = await con.fetch(
                "SELECT u.id, u.display_name, u.picture_url, m.role, m.joined_at, m.last_active_at FROM collab_members m "
                "JOIN users u ON u.id = m.user_id WHERE m.session_id = $1 ORDER BY m.joined_at", sid)
            entries = await con.fetch("SELECT * FROM collab_list WHERE session_id = $1 ORDER BY added_at", sid)
            docs = await con.fetch("SELECT * FROM (SELECT * FROM collab_documents WHERE session_id = $1 "
                                   "ORDER BY created_at DESC LIMIT $2) d ORDER BY created_at", sid, DOCS_IN_DETAIL)
        return {"id": str(s["id"]), "title": s["title"], "created_by": str(s["created_by"]),
                "created_at": _ms(s["created_at"]),
                "members": [{**_user(r), "role": r["role"], "joined_at": _ms(r["joined_at"]),
                             "last_active_at": _ms(r["last_active_at"])} for r in members],
                "list": [_entry(r) for r in entries], "documents": [_doc(r) for r in docs]}

    async def create_invite(self, session_id: str, user_id: str, token_hash: str, expires_ms: int) -> None:
        await self.pool.execute("INSERT INTO collab_invites (token_hash, session_id, created_by, expires_at) "
                                "VALUES ($1, $2, $3, to_timestamp($4 / 1000.0))",
                                token_hash, uuid.UUID(session_id), uuid.UUID(user_id), expires_ms)

    async def accept_invite(self, token_hash: str, user_id: str) -> tuple[str, bool] | None:
        """(session id, newly joined) for a valid unused invite, or None. A current member doesn't use it up, and the
        person who used it can open it again."""
        uid = uuid.UUID(user_id)
        async with self.pool.acquire() as con, con.transaction():
            r = await con.fetchrow("SELECT session_id, used_by FROM collab_invites WHERE token_hash = $1 "
                                   "AND expires_at > now() AND revoked_at IS NULL AND declined_at IS NULL FOR UPDATE", token_hash)
            if r is None or r["used_by"] not in (None, uid):
                return None
            sid = r["session_id"]
            if await con.fetchval("SELECT 1 FROM collab_members WHERE session_id = $1 AND user_id = $2", sid, uid):
                return str(sid), False
            await con.execute("UPDATE collab_invites SET used_at = now(), used_by = $2 WHERE token_hash = $1",
                              token_hash, uid)
            await con.execute("INSERT INTO collab_members (session_id, user_id, role) VALUES ($1, $2, 'member')", sid, uid)
        return str(sid), True

    async def list_add(self, session_id: str, user_id: str, mmsi: int, status: str) -> tuple[dict, bool]:
        """(entry, added). A ship already on the list is returned as it is."""
        sid, uid = uuid.UUID(session_id), uuid.UUID(user_id)
        r = await self.pool.fetchrow(
            "INSERT INTO collab_list (session_id, mmsi, status, added_by, updated_by) VALUES ($1, $2, $3, $4, $4) "
            "ON CONFLICT DO NOTHING RETURNING *", sid, mmsi, status, uid)
        if r:
            return _entry(r), True
        r = await self.pool.fetchrow("SELECT * FROM collab_list WHERE session_id = $1 AND mmsi = $2", sid, mmsi)
        return _entry(r), False

    async def list_set(self, session_id: str, user_id: str, mmsi: int, status: str) -> dict | None:
        r = await self.pool.fetchrow(
            "UPDATE collab_list SET status = $3, updated_by = $4, updated_at = now() WHERE session_id = $1 AND mmsi = $2 "
            "RETURNING *", uuid.UUID(session_id), mmsi, status, uuid.UUID(user_id))
        return r and _entry(r)

    async def list_remove(self, session_id: str, mmsi: int) -> bool:
        return await self.pool.fetchval("DELETE FROM collab_list WHERE session_id = $1 AND mmsi = $2 RETURNING true",
                                        uuid.UUID(session_id), mmsi) is not None

    async def add_document(self, session_id: str, user_id: str, mmsi: int | None, body: str,
                           kind: str = "note", mmsis: list[int] = ()) -> dict:
        r = await self.pool.fetchrow("INSERT INTO collab_documents (session_id, mmsi, author_id, body, kind, mmsis) "
                                     "VALUES ($1, $2, $3, $4, $5, $6) RETURNING *",
                                     uuid.UUID(session_id), mmsi, uuid.UUID(user_id), body, kind, list(mmsis))
        return _doc(r)

    async def add_activity(self, session_id: str, user_id: str, kind: str, mmsi: int | None = None) -> None:
        await self.pool.execute("INSERT INTO collab_activity (session_id, actor_id, kind, mmsi) VALUES ($1, $2, $3, $4)",
                                uuid.UUID(session_id), uuid.UUID(user_id), kind, mmsi)

    async def activity(self, session_id: str, limit: int) -> list[dict]:
        rows = await self.pool.fetch("SELECT * FROM collab_activity WHERE session_id = $1 ORDER BY at DESC LIMIT $2",
                                     uuid.UUID(session_id), limit)
        return [{"id": r["id"], "actor_id": str(r["actor_id"]), "kind": r["kind"], "mmsi": r["mmsi"],
                 "at": _ms(r["at"])} for r in rows]


class MemoryStore:
    """The PgStore interface in memory. Lost on restart: for tests and local dev only."""

    def __init__(self):
        self.users: dict[str, dict] = {}            # sub -> {id, name, picture}
        self.sessions: dict[str, dict] = {}         # id -> {id, title, created_by, created_at}
        self.members: dict[tuple, dict] = {}        # (sid, uid) -> {role, joined_at, last_active_at}
        self.invites: dict[str, dict] = {}          # hash -> {session_id, expires_at, used_by}
        self.lists: dict[tuple, dict] = {}          # (sid, mmsi) -> entry
        self.docs: list[dict] = []
        self.acts: list[dict] = []
        self.inv = MemInvites(self)
        self._ids = itertools.count(1)
        self._clock = 0

    def _now(self) -> int:   # strictly increasing, so "most recent first" is stable within one millisecond
        self._clock = max(self._clock + 1, int(time.time() * 1000))
        return self._clock

    def _by_id(self, user_id: str) -> dict:
        return next(u for u in self.users.values() if u["id"] == user_id)

    async def upsert_user(self, sub: str) -> dict:
        u = self.users.setdefault(sub, {"id": str(uuid.uuid4()), "name": None, "picture": None})
        return dict(u)

    async def set_profile(self, user_id: str, name, picture) -> dict:
        u = self._by_id(user_id)
        u.update(name=name, picture=picture)
        return dict(u)

    async def last_session(self, user_id: str) -> dict | None:
        mine = await self.list_sessions(user_id)
        return mine and {k: mine[0][k] for k in ("id", "title", "role", "last_active_at")} or None

    async def create_session(self, user_id: str, title: str) -> str:
        sid, now = str(uuid.uuid4()), self._now()
        self.sessions[sid] = {"id": sid, "title": title, "created_by": user_id, "created_at": now}
        self.members[(sid, user_id)] = {"role": "owner", "joined_at": now, "last_active_at": now}
        return sid

    async def list_sessions(self, user_id: str) -> list[dict]:
        out = [{**{k: self.sessions[sid][k] for k in ("id", "title", "created_at")}, "role": m["role"],
                "last_active_at": m["last_active_at"], "members": sum(1 for s, _ in self.members if s == sid)}
               for (sid, uid), m in self.members.items() if uid == user_id]
        return sorted(out, key=lambda s: -s["last_active_at"])

    async def role(self, session_id: str, user_id: str) -> str | None:
        m = self.members.get((session_id, user_id))
        return m and m["role"]

    async def touch(self, session_id: str, user_id: str) -> None:
        if m := self.members.get((session_id, user_id)):
            m["last_active_at"] = self._now()

    async def member(self, session_id: str, user_id: str) -> dict | None:
        m = self.members.get((session_id, user_id))
        return m and {**self._by_id(user_id), **m}

    async def session_detail(self, session_id: str) -> dict | None:
        s = self.sessions.get(session_id)
        if s is None:
            return None
        members = sorted(({**self._by_id(uid), **m} for (sid, uid), m in self.members.items() if sid == session_id),
                         key=lambda m: m["joined_at"])
        return {**s, "members": members,
                "list": sorted((dict(e) for (sid, _), e in self.lists.items() if sid == session_id),
                               key=lambda e: e["added_at"]),
                "documents": [{k: v for k, v in d.items() if k != "session_id"}
                              for d in self.docs if d["session_id"] == session_id][-DOCS_IN_DETAIL:]}

    async def create_invite(self, session_id: str, user_id: str, token_hash: str, expires_ms: int) -> None:
        self.invites[token_hash] = {"session_id": session_id, "expires_at": expires_ms, "used_by": None}

    async def accept_invite(self, token_hash: str, user_id: str):
        inv = self.invites.get(token_hash)
        if inv is None or inv.get("revoked") or inv.get("declined") or inv["used_by"] not in (None, user_id) or inv["expires_at"] <= time.time() * 1000:
            return None
        sid = inv["session_id"]
        if (sid, user_id) in self.members:
            return sid, False
        inv["used_by"] = user_id
        now = self._now()
        self.members[(sid, user_id)] = {"role": "member", "joined_at": now, "last_active_at": now}
        return sid, True

    async def list_add(self, session_id: str, user_id: str, mmsi: int, status: str):
        if (e := self.lists.get((session_id, mmsi))) is not None:
            return dict(e), False
        now = self._now()
        e = self.lists[(session_id, mmsi)] = {"mmsi": mmsi, "status": status, "added_by": user_id, "added_at": now,
                                              "updated_by": user_id, "updated_at": now}
        return dict(e), True

    async def list_set(self, session_id: str, user_id: str, mmsi: int, status: str) -> dict | None:
        e = self.lists.get((session_id, mmsi))
        if e is None:
            return None
        e.update(status=status, updated_by=user_id, updated_at=self._now())
        return dict(e)

    async def list_remove(self, session_id: str, mmsi: int) -> bool:
        return self.lists.pop((session_id, mmsi), None) is not None

    async def add_document(self, session_id: str, user_id: str, mmsi, body: str, kind: str = "note",
                           mmsis: list[int] = ()) -> dict:
        d = {"id": next(self._ids), "session_id": session_id, "mmsi": mmsi, "author_id": user_id, "body": body,
             "created_at": self._now(), "kind": kind, "mmsis": list(mmsis)}
        self.docs.append(d)
        return {k: v for k, v in d.items() if k != "session_id"}

    async def add_activity(self, session_id: str, user_id: str, kind: str, mmsi=None) -> None:
        self.acts.append({"id": next(self._ids), "session_id": session_id, "actor_id": user_id, "kind": kind,
                          "mmsi": mmsi, "at": self._now()})

    async def activity(self, session_id: str, limit: int) -> list[dict]:
        rows = [{k: v for k, v in a.items() if k != "session_id"} for a in self.acts if a["session_id"] == session_id]
        return rows[::-1][:limit]
