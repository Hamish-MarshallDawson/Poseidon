"""Invites with an addressee (issue #117): the owner invites an existing user (by id) or an email; the addressee sees it
in GET /invites and accepts or declines; the owner sees outgoing ones and can revoke. Link invites (no addressee)
still work through POST /invites/{token}/accept. Only a token's SHA-256 is stored, so an older link can't be copied
again from the server: the UI keeps the links it created.

shortcut: an addressee email comes from the client's Auth0 profile unverified (like the name), so anyone can claim an
address and see invites sent to it; upgrade by reading the verified email from Auth0's /userinfo with the same token.
"""
from __future__ import annotations

import re
import time
import uuid

EMAIL = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def norm_email(v: str | None) -> str | None:
    v = (v or "").strip().lower()
    return v if len(v) <= 254 and EMAIL.match(v) else None


def _pub(u: dict) -> dict:
    return {k: u[k] for k in ("id", "name", "picture")}


class MemInvites:
    """In memory, on the MemoryStore's own dicts (store.invites holds the rows by token hash)."""

    def __init__(self, store):
        self.s = store
        self.emails: dict[str, str] = {}   # user id -> email

    def _row(self, inv_id: str):
        for h, i in self.s.invites.items():
            if i.get("id") == inv_id:
                return h, i
        return None, None

    async def set_email(self, user_id: str, email: str | None) -> None:
        if email:
            self.emails[user_id] = email

    async def sub_of(self, user_id: str) -> str | None:
        return next((sub for sub, u in self.s.users.items() if u["id"] == user_id), None)

    async def user_by_email(self, email: str) -> str | None:
        return next((uid for uid, e in self.emails.items() if e == email), None)

    async def exists(self, user_id: str) -> bool:
        return any(u["id"] == user_id for u in self.s.users.values())

    async def create(self, sid: str, by: str, token_hash: str, expires_ms: int, to_user: str | None,
                     to_email: str | None) -> dict:
        inv = {"id": str(uuid.uuid4()), "session_id": sid, "expires_at": expires_ms, "used_by": None, "created_by": by,
               "created_at": self.s._now(), "to_user": to_user, "to_email": to_email, "revoked": False,
               "declined": False}
        self.s.invites[token_hash] = inv
        return dict(inv)

    def _mine(self, inv: dict, uid: str) -> bool:
        return inv["to_user"] == uid or (inv["to_email"] is not None and inv["to_email"] == self.emails.get(uid))

    async def listing(self, uid: str) -> dict:
        now = time.time() * 1000
        incoming, outgoing = [], []
        for i in sorted(self.s.invites.values(), key=lambda i: i.get("created_at", 0)):
            if i.get("id") is None or i["revoked"] or i["expires_at"] <= now:
                continue
            title = self.s.sessions[i["session_id"]]["title"]
            if i["created_by"] == uid:
                status = "declined" if i["declined"] else "accepted" if i["used_by"] else "pending"
                to = (_pub(self.s._by_id(i["to_user"])) if i["to_user"]
                      else {"email": i["to_email"]} if i["to_email"] else None)
                outgoing.append({"id": i["id"], "session_id": i["session_id"], "session_title": title, "to": to,
                                 "created_at": i["created_at"], "expires_at": i["expires_at"], "status": status})
            elif (self._mine(i, uid) and not i["used_by"] and not i["declined"]
                  and (i["session_id"], uid) not in self.s.members):
                incoming.append({"id": i["id"], "session_id": i["session_id"], "session_title": title,
                                 "from": _pub(self.s._by_id(i["created_by"])), "created_at": i["created_at"],
                                 "expires_at": i["expires_at"]})
        return {"incoming": incoming, "outgoing": outgoing}

    async def accept(self, inv_id: str, uid: str):
        h, i = self._row(inv_id)
        if (i is None or i["revoked"] or i["declined"] or i["used_by"] or i["expires_at"] <= time.time() * 1000
                or not self._mine(i, uid)):
            return None
        return await self.s.accept_invite(h, uid)

    async def decline(self, inv_id: str, uid: str) -> dict | None:
        _, i = self._row(inv_id)
        if i is None or i["revoked"] or i["used_by"] or not self._mine(i, uid):
            return None
        i["declined"] = True
        return {"created_by": i["created_by"]}

    async def revoke(self, inv_id: str, uid: str) -> dict | None:
        _, i = self._row(inv_id)
        if i is None or i["created_by"] != uid or i["revoked"]:
            return None
        i["revoked"] = True
        return {"to_user": i["to_user"], "to_email": i["to_email"]}


class PgInvites:
    def __init__(self, pool):
        self.pool = pool

    async def set_email(self, user_id: str, email: str | None) -> None:
        if email:
            await self.pool.execute("UPDATE users SET email = $2 WHERE id = $1", uuid.UUID(user_id), email)

    async def sub_of(self, user_id: str) -> str | None:
        return await self.pool.fetchval("SELECT auth0_sub FROM users WHERE id = $1", uuid.UUID(user_id))

    async def user_by_email(self, email: str) -> str | None:
        v = await self.pool.fetchval("SELECT id FROM users WHERE email = $1 ORDER BY seen_at DESC LIMIT 1", email)
        return v and str(v)

    async def exists(self, user_id: str) -> bool:
        return bool(await self.pool.fetchval("SELECT 1 FROM users WHERE id = $1", uuid.UUID(user_id)))

    async def create(self, sid: str, by: str, token_hash: str, expires_ms: int, to_user: str | None,
                     to_email: str | None) -> dict:
        r = await self.pool.fetchrow(
            "INSERT INTO collab_invites (token_hash, session_id, created_by, expires_at, to_user, to_email) "
            "VALUES ($1, $2, $3, to_timestamp($4 / 1000.0), $5, $6) RETURNING id, created_at",
            token_hash, uuid.UUID(sid), uuid.UUID(by), expires_ms, to_user and uuid.UUID(to_user), to_email)
        return {"id": str(r["id"]), "session_id": sid, "created_by": by,
                "created_at": int(r["created_at"].timestamp() * 1000), "expires_at": expires_ms,
                "to_user": to_user, "to_email": to_email}

    async def listing(self, uid: str) -> dict:
        u = uuid.UUID(uid)
        inc = await self.pool.fetch(
            "SELECT i.id, i.session_id, s.title, i.created_at, i.expires_at, f.id AS fid, f.display_name AS fname, "
            "f.picture_url AS fpic FROM collab_invites i JOIN collab_sessions s ON s.id = i.session_id "
            "JOIN users f ON f.id = i.created_by JOIN users me ON me.id = $1 "
            "WHERE (i.to_user = me.id OR (i.to_email IS NOT NULL AND i.to_email = me.email)) "
            "AND i.created_by <> me.id AND i.used_at IS NULL AND i.declined_at IS NULL AND i.revoked_at IS NULL "
            "AND i.expires_at > now() AND NOT EXISTS (SELECT 1 FROM collab_members m "
            "WHERE m.session_id = i.session_id AND m.user_id = me.id) ORDER BY i.created_at", u)
        out = await self.pool.fetch(
            "SELECT i.id, i.session_id, s.title, i.created_at, i.expires_at, i.used_at, i.declined_at, i.to_email, "
            "t.id AS tid, t.display_name AS tname, t.picture_url AS tpic "
            "FROM collab_invites i JOIN collab_sessions s ON s.id = i.session_id LEFT JOIN users t ON t.id = i.to_user "
            "WHERE i.created_by = $1 AND i.revoked_at IS NULL AND i.expires_at > now() ORDER BY i.created_at", u)

        def ms(d):
            return int(d.timestamp() * 1000)

        return {
            "incoming": [{"id": str(r["id"]), "session_id": str(r["session_id"]), "session_title": r["title"],
                          "from": {"id": str(r["fid"]), "name": r["fname"], "picture": r["fpic"]},
                          "created_at": ms(r["created_at"]), "expires_at": ms(r["expires_at"])} for r in inc],
            "outgoing": [{"id": str(r["id"]), "session_id": str(r["session_id"]), "session_title": r["title"],
                          "to": ({"id": str(r["tid"]), "name": r["tname"], "picture": r["tpic"]} if r["tid"]
                                 else {"email": r["to_email"]} if r["to_email"] else None),
                          "created_at": ms(r["created_at"]), "expires_at": ms(r["expires_at"]),
                          "status": "declined" if r["declined_at"] else "accepted" if r["used_at"] else "pending"}
                         for r in out],
        }

    async def accept(self, inv_id: str, uid: str):
        """(session id, newly joined) if this invite is addressed to the user and still open, else None."""
        u, iid = uuid.UUID(uid), uuid.UUID(inv_id)
        async with self.pool.acquire() as con, con.transaction():
            r = await con.fetchrow(
                "SELECT i.session_id FROM collab_invites i JOIN users me ON me.id = $2 WHERE i.id = $1 "
                "AND (i.to_user = me.id OR (i.to_email IS NOT NULL AND i.to_email = me.email)) AND i.used_at IS NULL "
                "AND i.declined_at IS NULL AND i.revoked_at IS NULL AND i.expires_at > now() FOR UPDATE OF i", iid, u)
            if r is None:
                return None
            sid = r["session_id"]
            await con.execute("UPDATE collab_invites SET used_at = now(), used_by = $2 WHERE id = $1", iid, u)
            had = await con.fetchval("SELECT 1 FROM collab_members WHERE session_id = $1 AND user_id = $2", sid, u)
            if not had:
                await con.execute("INSERT INTO collab_members (session_id, user_id, role) VALUES ($1, $2, 'member')",
                                  sid, u)
        return str(sid), not had

    async def decline(self, inv_id: str, uid: str) -> dict | None:
        r = await self.pool.fetchrow(
            "UPDATE collab_invites i SET declined_at = now() FROM users me WHERE me.id = $2 AND i.id = $1 "
            "AND (i.to_user = me.id OR (i.to_email IS NOT NULL AND i.to_email = me.email)) AND i.used_at IS NULL "
            "AND i.revoked_at IS NULL RETURNING i.created_by", uuid.UUID(inv_id), uuid.UUID(uid))
        return r and {"created_by": str(r["created_by"])}

    async def revoke(self, inv_id: str, uid: str) -> dict | None:
        r = await self.pool.fetchrow(
            "UPDATE collab_invites SET revoked_at = now() WHERE id = $1 AND created_by = $2 AND revoked_at IS NULL "
            "RETURNING to_user, to_email", uuid.UUID(inv_id), uuid.UUID(uid))
        return r and {"to_user": r["to_user"] and str(r["to_user"]), "to_email": r["to_email"]}
