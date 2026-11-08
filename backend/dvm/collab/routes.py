"""REST routes for shared investigation sessions (issue #100). Shapes are in dvm/collab/README.md.

The caller is always the verified access token's `sub`; a name or picture posted to /me is display only.
"""
from __future__ import annotations

import hashlib
import secrets
import time
import uuid
from typing import Literal

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from dvm import auth
from dvm.collab.invites import norm_email
from dvm.collab.live import hub
from dvm.sources.routes import MMSI_MAX, MMSI_MIN

INVITE_DAYS = 7
Status = Literal["open", "reviewed", "no_action"]


class Profile(BaseModel):
    name: str | None = Field(None, max_length=80)
    picture: str | None = Field(None, max_length=1000, pattern=r"^https://")
    email: str | None = Field(None, max_length=254)   # only used to match invites sent to this address


class InviteIn(BaseModel):
    to: str | None = Field(None, max_length=254)   # an existing user's id, or an email; none = a link anyone can use once


class NewSession(BaseModel):
    title: str = Field(min_length=1, max_length=120)


class ListAdd(BaseModel):
    mmsi: int = Field(ge=MMSI_MIN, le=MMSI_MAX)
    status: Status = "open"


class ListSet(BaseModel):
    status: Status


class NewDocument(BaseModel):
    mmsi: int | None = Field(None, ge=MMSI_MIN, le=MMSI_MAX)   # null: a note on the whole session
    body: str = Field(min_length=1, max_length=4000)


def _store():
    if hub.store is None:
        raise HTTPException(503, f"collaboration store not ready ({hub.status})")
    return hub.store


async def current_user(authorization: str | None = Header(None), x_dev_user: str | None = Header(None)) -> dict:
    """Bearer access token, checked as everywhere else; the user row is upserted from its sub.
    Without Auth0 (local dev) the caller is dev|<X-Dev-User header>, so two browsers can be two users."""
    if auth.ENABLED:
        scheme, _, token = (authorization or "").partition(" ")
        if scheme != "Bearer" or not token:
            raise HTTPException(401, "login required", headers={"WWW-Authenticate": "Bearer"})
        try:
            sub = (await auth.verify_async(token))["sub"]
        except jwt.PyJWTError:
            raise HTTPException(401, "invalid token", headers={"WWW-Authenticate": "Bearer"})
    else:
        sub = f"dev|{x_dev_user or 'local'}"
    return await _store().upsert_user(sub)


async def _member(session_id: uuid.UUID, user: dict) -> tuple[str, str]:
    """(session id, role) for a member; 404 otherwise, so a non-member can't tell which sessions exist."""
    sid = str(session_id)
    role = await _store().role(sid, user["id"])
    if role is None:
        raise HTTPException(404, "no such session")
    return sid, role


async def _poke(user_id: str | None, msg: dict) -> None:
    """Tell one user's open sockets that their invites changed (the UI re-reads GET /invites)."""
    if user_id:
        hub.push_user(await _store().inv.sub_of(user_id), msg)


def make_router() -> APIRouter:
    r = APIRouter(tags=["collaboration"])

    @r.get("/me")
    async def get_me(user: dict = Depends(current_user)) -> dict:
        return {"user": user, "last_session": await _store().last_session(user["id"])}

    @r.post("/me")
    async def post_me(body: Profile, user: dict = Depends(current_user)) -> dict:
        user = await _store().set_profile(user["id"], body.name, body.picture)
        await _store().inv.set_email(user["id"], norm_email(body.email))
        await _poke(user["id"], {"type": "invites_changed"})   # an invite sent to this address may now match
        hub.update_user(user)
        return {"user": user}

    @r.post("/sessions", status_code=201)
    async def create_session(body: NewSession, user: dict = Depends(current_user)) -> dict:
        store = _store()
        sid = await store.create_session(user["id"], body.title.strip() or "Untitled session")
        await store.add_activity(sid, user["id"], "created")
        return await store.session_detail(sid)

    @r.get("/sessions")
    async def list_sessions(user: dict = Depends(current_user)) -> dict:
        rows = await _store().list_sessions(user["id"])
        # `online`: the others who are in each session right now (private users are left out), for the entry pop-up.
        return {"sessions": [{**s, "online": [{"id": u["id"], "name": u["name"], "picture": u["picture"]}
                                              for u in hub.users_in(s["id"]) if u["id"] != user["id"]]} for s in rows]}

    @r.get("/sessions/{session_id}")
    async def get_session(session_id: uuid.UUID, user: dict = Depends(current_user)) -> dict:
        sid, _ = await _member(session_id, user)
        return await _store().session_detail(sid)

    @r.get("/sessions/{session_id}/activity")
    async def get_activity(session_id: uuid.UUID, limit: int = Query(50, ge=1, le=500),
                           user: dict = Depends(current_user)) -> dict:
        sid, _ = await _member(session_id, user)
        return {"activity": await _store().activity(sid, limit)}

    @r.post("/sessions/{session_id}/invites", status_code=201)
    async def create_invite(session_id: uuid.UUID, body: InviteIn | None = None,
                            user: dict = Depends(current_user)) -> dict:
        """A link anyone can use once, or (with `to`) an invite addressed to an existing user id or an email."""
        sid, role = await _member(session_id, user)
        if role != "owner":
            raise HTTPException(403, "only the session's owner can invite")
        store, to = _store(), ((body and body.to) or "").strip() or None
        to_user = to_email = None
        if to and "@" in to:
            if (to_email := norm_email(to)) is None:
                raise HTTPException(422, "not an email address")
            to_user = await store.inv.user_by_email(to_email)
        elif to:
            try:
                to_user = str(uuid.UUID(to))
            except ValueError:
                raise HTTPException(422, "to must be a user id or an email address")
            if not await store.inv.exists(to_user):
                raise HTTPException(404, "no such user")
        if to_user == user["id"]:
            raise HTTPException(422, "you are already in this session")
        token = secrets.token_urlsafe(24)
        expires = int((time.time() + INVITE_DAYS * 86400) * 1000)
        inv = await store.inv.create(sid, user["id"], hashlib.sha256(token.encode()).hexdigest(), expires,
                                     to_user, to_email)
        await _poke(to_user, {"type": "invite", "invite_id": inv["id"], "session_id": sid})
        return {"id": inv["id"], "token": token, "session_id": sid, "expires_at": expires}

    @r.get("/invites")
    async def get_invites(user: dict = Depends(current_user)) -> dict:
        return await _store().inv.listing(user["id"])

    async def _joined(store, sid: str, joined: bool, user: dict) -> dict:
        await store.touch(sid, user["id"])
        if joined:
            await store.add_activity(sid, user["id"], "joined")
            hub.broadcast(sid, {"type": "member_joined", "session_id": sid,
                                "member": await store.member(sid, user["id"])})
        return await store.session_detail(sid)

    @r.post("/invites/{ref}/accept")
    async def accept_invite(ref: str, user: dict = Depends(current_user)) -> dict:
        """`ref` is the secret link token, or the id of an invite addressed to you (from GET /invites)."""
        store = _store()
        try:
            got = await store.inv.accept(str(uuid.UUID(ref)), user["id"])
        except ValueError:
            got = await store.accept_invite(hashlib.sha256(ref.encode()).hexdigest(), user["id"])
        if got is None:
            raise HTTPException(404, "invite not found, used or expired")
        sid, joined = got
        detail = await _joined(store, sid, joined, user)
        await _poke(detail["created_by"], {"type": "invites_changed"})
        return detail

    @r.post("/invites/{invite_id}/decline", status_code=204)
    async def decline_invite(invite_id: uuid.UUID, user: dict = Depends(current_user)) -> None:
        got = await _store().inv.decline(str(invite_id), user["id"])
        if got is None:
            raise HTTPException(404, "invite not found")
        await _poke(got["created_by"], {"type": "invites_changed"})

    @r.delete("/invites/{invite_id}", status_code=204)
    async def revoke_invite(invite_id: uuid.UUID, user: dict = Depends(current_user)) -> None:
        got = await _store().inv.revoke(str(invite_id), user["id"])
        if got is None:
            raise HTTPException(404, "invite not found")
        to = got["to_user"] or (got["to_email"] and await _store().inv.user_by_email(got["to_email"]))
        await _poke(to, {"type": "invites_changed"})

    @r.post("/sessions/{session_id}/list", status_code=201)
    async def list_add(session_id: uuid.UUID, body: ListAdd, user: dict = Depends(current_user)) -> dict:
        sid, _ = await _member(session_id, user)
        store = _store()
        entry, added = await store.list_add(sid, user["id"], body.mmsi, body.status)
        if added:
            await store.add_activity(sid, user["id"], "added", body.mmsi)
            hub.broadcast(sid, {"type": "list_delta", "session_id": sid, "op": "put", "entry": entry})
        await store.touch(sid, user["id"])
        return {"entry": entry}

    @r.patch("/sessions/{session_id}/list/{mmsi}")
    async def list_set(session_id: uuid.UUID, body: ListSet, mmsi: int, user: dict = Depends(current_user)) -> dict:
        sid, _ = await _member(session_id, user)
        store = _store()
        entry = await store.list_set(sid, user["id"], mmsi, body.status)
        if entry is None:
            raise HTTPException(404, "ship not on this session's list")
        await store.add_activity(sid, user["id"], f"status_{body.status}", mmsi)
        hub.broadcast(sid, {"type": "list_delta", "session_id": sid, "op": "put", "entry": entry})
        await store.touch(sid, user["id"])
        return {"entry": entry}

    @r.delete("/sessions/{session_id}/list/{mmsi}", status_code=204)
    async def list_remove(session_id: uuid.UUID, mmsi: int, user: dict = Depends(current_user)) -> None:
        sid, _ = await _member(session_id, user)
        store = _store()
        if not await store.list_remove(sid, mmsi):
            raise HTTPException(404, "ship not on this session's list")
        await store.add_activity(sid, user["id"], "removed", mmsi)
        hub.broadcast(sid, {"type": "list_delta", "session_id": sid, "op": "remove",
                            "entry": {"mmsi": mmsi, "updated_by": user["id"], "updated_at": int(time.time() * 1000)}})
        await store.touch(sid, user["id"])

    @r.post("/sessions/{session_id}/documents", status_code=201)
    async def add_document(session_id: uuid.UUID, body: NewDocument, user: dict = Depends(current_user)) -> dict:
        sid, _ = await _member(session_id, user)
        text = body.body.strip()
        if not text:
            raise HTTPException(422, "body is empty")
        store = _store()
        doc = await store.add_document(sid, user["id"], body.mmsi, text)
        await store.add_activity(sid, user["id"], "noted", body.mmsi)
        hub.broadcast(sid, {"type": "document", "session_id": sid, "document": doc})
        await store.touch(sid, user["id"])
        return {"document": doc}

    return r
