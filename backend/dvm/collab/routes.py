"""REST routes for shared investigation sessions (issue #100). Shapes are in dvm/collab/README.md.

The caller is always the verified access token's `sub`; a name or picture posted to /me is display only.
"""
from __future__ import annotations

import hashlib
import secrets
import time
import uuid
from typing import Annotated, Literal

import jwt
from fastapi import APIRouter, Depends, Header, HTTPException, Query
from pydantic import BaseModel, Field

from dvm import auth
from dvm.briefing import gemini
from dvm.collab.live import hub
from dvm.sources.routes import MMSI_MAX, MMSI_MIN

INVITE_DAYS = 7
Status = Literal["open", "reviewed", "no_action"]


class Profile(BaseModel):
    name: str | None = Field(None, max_length=80)
    picture: str | None = Field(None, max_length=1000, pattern=r"^https://")


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
    kind: Literal["note", "briefing"] = "note"                  # "summary" is only made by POST .../summary
    mmsis: list[Annotated[int, Field(ge=MMSI_MIN, le=MMSI_MAX)]] = Field(default_factory=list, max_length=10)


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


def make_router() -> APIRouter:
    r = APIRouter(tags=["collaboration"])

    @r.get("/me")
    async def get_me(user: dict = Depends(current_user)) -> dict:
        return {"user": user, "last_session": await _store().last_session(user["id"])}

    @r.post("/me")
    async def post_me(body: Profile, user: dict = Depends(current_user)) -> dict:
        user = await _store().set_profile(user["id"], body.name, body.picture)
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
        return {"sessions": await _store().list_sessions(user["id"])}

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
    async def create_invite(session_id: uuid.UUID, user: dict = Depends(current_user)) -> dict:
        sid, role = await _member(session_id, user)
        if role != "owner":
            raise HTTPException(403, "only the session's owner can invite")
        token = secrets.token_urlsafe(24)
        expires = int((time.time() + INVITE_DAYS * 86400) * 1000)
        await _store().create_invite(sid, user["id"], hashlib.sha256(token.encode()).hexdigest(), expires)
        return {"token": token, "session_id": sid, "expires_at": expires}

    @r.post("/invites/{token}/accept")
    async def accept_invite(token: str, user: dict = Depends(current_user)) -> dict:
        store = _store()
        got = await store.accept_invite(hashlib.sha256(token.encode()).hexdigest(), user["id"])
        if got is None:
            raise HTTPException(404, "invite not found, used or expired")
        sid, joined = got
        await store.touch(sid, user["id"])
        if joined:
            await store.add_activity(sid, user["id"], "joined")
            hub.broadcast(sid, {"type": "member_joined", "session_id": sid,
                                "member": await store.member(sid, user["id"])})
        return await store.session_detail(sid)

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
        if body.kind == "briefing" and not body.mmsis:
            raise HTTPException(422, "a briefing names the ships it covers")
        store = _store()
        doc = await store.add_document(sid, user["id"], body.mmsi, text, body.kind, body.mmsis)
        await store.add_activity(sid, user["id"], "briefing_saved" if body.kind == "briefing" else "noted", body.mmsi)
        hub.broadcast(sid, {"type": "document", "session_id": sid, "document": doc})
        await store.touch(sid, user["id"])
        return {"document": doc}

    @r.post("/sessions/{session_id}/summary", status_code=201)
    async def summarise(session_id: uuid.UUID, user: dict = Depends(current_user)) -> dict:
        """End-of-session summary of the channel, the saved briefings and the tracked ships, stored as a document."""
        sid, _ = await _member(session_id, user)
        store = _store()
        detail = await store.session_detail(sid)
        names = {m["id"]: m["name"] or "A member" for m in detail["members"]}
        docs = [{"id": d["id"], "kind": d["kind"], "author": names.get(d["author_id"], "A member"), "ship": d["mmsi"],
                 "ships": d["mmsis"], "at": d["created_at"], "text": d["body"]}
                for d in detail["documents"] if d["kind"] != "summary"]
        facts = {"session": detail["title"], "members": list(names.values()), "documents": docs,
                 "tracked_ships": [{"mmsi": e["mmsi"], "status": e["status"],
                                    "added_by": names.get(e["added_by"], "A member")} for e in detail["list"]]}
        try:
            text = await gemini.summarise_session(facts)
        except gemini.BriefingError as e:
            raise HTTPException(e.status, str(e))
        ships = [e["mmsi"] for e in detail["list"]][:10]
        doc = await store.add_document(sid, user["id"], None, text[:4000], "summary", ships)
        await store.add_activity(sid, user["id"], "summarised")
        hub.broadcast(sid, {"type": "document", "session_id": sid, "document": doc})
        await store.touch(sid, user["id"])
        return {"document": doc}

    return r
