"""Shared investigation sessions (dvm/collab): presence with fake WebSocket clients, and the REST routes on the
in-memory store. No database."""
from __future__ import annotations

import asyncio
import json
import time

import pytest
from fastapi.testclient import TestClient

from dvm import app as app_mod, auth, collab, config
from dvm.app import Client
from dvm.collab.live import CollabHub
from dvm.collab.store import MemoryStore

SHIP, OTHER = 230000001, 244660000


class FakeWs:
    def __init__(self):
        self.sent: list[dict] = []
        self.closed = None

    async def send_text(self, text: str) -> None:
        if self.closed:
            raise RuntimeError("closed")
        self.sent.append(json.loads(text))

    async def close(self, code: int, reason: str) -> None:
        self.closed = (code, reason)

    def of(self, kind: str) -> list[dict]:
        return [m for m in self.sent if m["type"] == kind]


def client(sub: str, exp: float | None = None) -> Client:
    c = Client(FakeWs())
    c.claims = {"sub": sub, "exp": exp or time.time() + 3600}
    return c


async def hub_with_session(monkeypatch):
    """A hub on a memory store with a session owned by Hamish, joined by Aiden, and Mano who is not a member."""
    monkeypatch.setattr(auth, "ENABLED", True)
    h = CollabHub()
    h.store = MemoryStore()
    ham = await h.store.upsert_user("auth0|hamish")
    await h.store.set_profile(ham["id"], "Hamish", "https://example.com/h.png")
    aid = await h.store.upsert_user("auth0|aiden")
    await h.store.set_profile(aid["id"], "Aiden", None)
    sid = await h.store.create_session(ham["id"], "Baltic gaps")
    await h.store.create_invite(sid, ham["id"], "hash", int(time.time() * 1000) + 60_000)
    assert await h.store.accept_invite("hash", aid["id"]) == (sid, True)
    return h, sid


def test_two_members_see_each_other_and_a_non_member_sees_nothing(monkeypatch):
    async def go():
        h, sid = await hub_with_session(monkeypatch)
        a, b, outsider = client("auth0|hamish"), client("auth0|aiden"), client("auth0|mano")
        for c in (a, b, outsider):
            await h.on_ws(c, {"type": "session_join", "session_id": sid})
        assert a.ws.of("session_joined")[0]["role"] == "owner"
        assert b.ws.of("session_joined")[0]["role"] == "member"
        assert outsider.ws.of("error") == [{"type": "error", "code": "forbidden", "for": "session_join",
                                            "session_id": sid, "seq": 1}]
        await h.on_ws(a, {"type": "presence", "viewing": SHIP, "following": [OTHER, "junk"], "bbox": [10, 54, 20, 60]})
        await h.on_ws(b, {"type": "presence", "viewing": None, "following": [], "bbox": None})
        await h.on_ws(outsider, {"type": "presence", "viewing": OTHER})   # ignored: never joined
        await h.fanout()
        for c in (a, b):
            users = c.ws.of("presence")[-1]["users"]
            assert {u["name"] for u in users} == {"Hamish", "Aiden"}
            ham = next(u for u in users if u["name"] == "Hamish")
            assert ham["viewing"] == SHIP and ham["following"] == [OTHER] and ham["bbox"] == [10, 54, 20, 60]
            assert ham["picture"] == "https://example.com/h.png"
        assert outsider.ws.of("presence") == []
    asyncio.run(go())


def test_private_user_is_left_out_and_disconnect_or_silence_drops_users(monkeypatch):
    async def go():
        h, sid = await hub_with_session(monkeypatch)
        a, b = client("auth0|hamish"), client("auth0|aiden")
        for c in (a, b):
            await h.on_ws(c, {"type": "session_join", "session_id": sid})
        await h.on_ws(a, {"type": "presence", "viewing": SHIP, "private": True})
        await h.on_ws(b, {"type": "presence", "viewing": OTHER})
        await h.fanout()
        assert [u["name"] for u in b.ws.of("presence")[-1]["users"]] == ["Aiden"]
        await h.on_ws(a, {"type": "presence", "viewing": SHIP})
        await h.fanout()
        assert len(b.ws.of("presence")[-1]["users"]) == 2
        h.detach(a)   # the socket closed
        await h.fanout()
        assert [u["name"] for u in b.ws.of("presence")[-1]["users"]] == ["Aiden"]
        h.presence[b]["ts"] -= 31_000   # 31 s without a presence message
        await h.fanout()
        assert b.ws.of("presence")[-1]["users"] == []
    asyncio.run(go())


def test_expired_token_closes_the_socket(monkeypatch):
    async def go():
        h, sid = await hub_with_session(monkeypatch)
        late = client("auth0|aiden", exp=time.time() - 1)
        await h.on_ws(late, {"type": "session_join", "session_id": sid})   # re-checked on join
        assert late.ws.closed == (1008, "token expired") and late not in h.joined
        soon = client("auth0|aiden", exp=time.time() + 0.05)
        h.attach(soon)
        await h.on_ws(soon, {"type": "session_join", "session_id": sid})
        assert soon in h.joined
        await asyncio.sleep(0.2)   # the expiry watchdog closes it when exp passes
        assert soon.ws.closed == (1008, "token expired") and soon not in h.joined
    asyncio.run(go())


def test_fresher_token_extends_the_socket_and_another_user_is_refused(monkeypatch):
    async def go():
        h, sid = await hub_with_session(monkeypatch)
        tokens = {"fresh": {"sub": "auth0|aiden", "exp": time.time() + 3600},
                  "mano": {"sub": "auth0|mano", "exp": time.time() + 3600}}

        async def verify(token):
            return tokens[token]
        monkeypatch.setattr(auth, "verify_async", verify)
        c = client("auth0|aiden", exp=time.time() + 0.05)
        h.attach(c)
        await h.on_ws(c, {"type": "auth", "token": "fresh"})
        await asyncio.sleep(0.2)
        assert c.ws.closed is None
        await h.on_ws(c, {"type": "auth", "token": "mano"})
        assert c.ws.closed == (1008, "a different user")
        h.detach(c)
    asyncio.run(go())


# --- REST routes, through the app, on the memory store -------------------------------------------------------------
@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "TIGER_DATABASE_URL", "")   # no database: the collab store is in memory
    monkeypatch.setattr(config, "AISSTREAM_API_KEY", "")
    monkeypatch.setattr(config, "DIGITRAFFIC", False)
    monkeypatch.setattr(auth, "ENABLED", False)
    monkeypatch.setattr(collab.live, "FANOUT_S", 0.05)
    with TestClient(app_mod.app) as c:
        yield c


def as_(user: str) -> dict:
    return {"X-Dev-User": user}


def test_identity_sessions_invites_list_and_documents(api):
    ham, aid, mano = as_("hamish"), as_("aiden"), as_("mano")
    me = api.post("/me", json={"name": "Hamish", "picture": "https://example.com/h.png"}, headers=ham).json()["user"]
    assert me["name"] == "Hamish"
    assert api.post("/me", json={"picture": "javascript:alert(1)"}, headers=ham).status_code == 422
    assert api.get("/me", headers=ham).json() == {"user": me, "last_session": None}

    s = api.post("/sessions", json={"title": "Baltic gaps"}, headers=ham)
    assert s.status_code == 201
    sid = s.json()["id"]
    assert api.get("/me", headers=ham).json()["last_session"]["id"] == sid   # "resume your last session?"
    assert api.get(f"/sessions/{sid}", headers=aid).status_code == 404       # not a member yet

    inv = api.post(f"/sessions/{sid}/invites", headers=ham).json()
    assert inv["expires_at"] > time.time() * 1000 + 6 * 86_400_000
    joined = api.post(f"/invites/{inv['token']}/accept", headers=aid)
    assert joined.status_code == 200 and len(joined.json()["members"]) == 2
    assert api.post(f"/invites/{inv['token']}/accept", headers=mano).status_code == 404   # one-time
    assert api.post(f"/invites/{inv['token']}/accept", headers=aid).status_code == 200    # its user can reopen it
    assert api.post(f"/sessions/{sid}/invites", headers=aid).status_code == 403          # owner only
    assert api.get("/sessions", headers=aid).json()["sessions"][0]["role"] == "member"
    assert api.get("/sessions", headers=aid).json()["sessions"][0]["online"] == []

    e = api.post(f"/sessions/{sid}/list", json={"mmsi": SHIP}, headers=aid).json()["entry"]
    assert e["status"] == "open" and e["added_by"] == joined.json()["members"][1]["id"]
    assert api.post(f"/sessions/{sid}/list", json={"mmsi": 123}, headers=aid).status_code == 422
    assert api.patch(f"/sessions/{sid}/list/{SHIP}", json={"status": "guilty"}, headers=ham).status_code == 422
    assert api.patch(f"/sessions/{sid}/list/{SHIP}", json={"status": "reviewed"},
                     headers=ham).json()["entry"]["status"] == "reviewed"
    assert api.post(f"/sessions/{sid}/list", json={"mmsi": SHIP}, headers=mano).status_code == 404

    d = api.post(f"/sessions/{sid}/documents", json={"mmsi": SHIP, "body": " Went quiet near Gdansk. "},
                 headers=ham).json()["document"]
    assert d["body"] == "Went quiet near Gdansk." and d["author_id"] == me["id"]
    assert api.post(f"/sessions/{sid}/documents", json={"body": "x" * 4001}, headers=ham).status_code == 422
    detail = api.get(f"/sessions/{sid}", headers=aid).json()
    assert [x["mmsi"] for x in detail["list"]] == [SHIP] and detail["documents"][0]["id"] == d["id"]
    assert api.delete(f"/sessions/{sid}/list/{SHIP}", headers=aid).status_code == 204
    kinds = [a["kind"] for a in api.get(f"/sessions/{sid}/activity", headers=ham).json()["activity"]]
    assert kinds == ["removed", "noted", "status_reviewed", "added", "joined", "created"]   # newest first


def test_collab_routes_need_login_when_auth_is_on(api, monkeypatch):
    monkeypatch.setattr(auth, "ENABLED", True)
    assert api.get("/me").status_code == 401
    assert api.post("/sessions", json={"title": "x"}).status_code == 401


def _until(ws, kind: str, limit: int = 50) -> dict:
    for _ in range(limit):
        m = ws.receive_json()
        if m["type"] == kind:
            return m
    raise AssertionError(f"no {kind} message")


def test_live_over_the_real_socket(api):
    ham, aid = as_("hamish"), as_("aiden")
    sid = api.post("/sessions", json={"title": "Live"}, headers=ham).json()["id"]
    token = api.post(f"/sessions/{sid}/invites", headers=ham).json()["token"]
    api.post(f"/invites/{token}/accept", headers=aid)
    with api.websocket_connect("/ws") as w1, api.websocket_connect("/ws") as w2:
        w1.send_json({"type": "session_join", "session_id": sid, "dev_user": "hamish"})
        w2.send_json({"type": "session_join", "session_id": sid, "dev_user": "aiden"})
        assert _until(w1, "session_joined")["role"] == "owner"
        _until(w2, "session_joined")
        w2.send_json({"type": "presence", "viewing": SHIP, "following": []})
        while not (users := _until(w1, "presence")["users"]):
            pass
        assert users[0]["viewing"] == SHIP
        api.post(f"/sessions/{sid}/list", json={"mmsi": SHIP}, headers=ham)
        assert _until(w2, "list_delta")["entry"]["mmsi"] == SHIP


def test_briefing_documents_and_session_summary(api, monkeypatch):
    from dvm.briefing import gemini
    ham, aid = as_("hamish"), as_("aiden")
    sid = api.post("/sessions", json={"title": "Baltic gaps"}, headers=ham).json()["id"]
    tok = api.post(f"/sessions/{sid}/invites", headers=ham).json()["token"]
    api.post(f"/invites/{tok}/accept", headers=aid)

    saved = api.post(f"/sessions/{sid}/documents", headers=aid,
                     json={"kind": "briefing", "mmsis": [SHIP, OTHER], "body": "Two ships went quiet."})
    assert saved.status_code == 201 and saved.json()["document"]["kind"] == "briefing"
    assert saved.json()["document"]["mmsis"] == [SHIP, OTHER]
    note = api.post(f"/sessions/{sid}/documents", json={"mmsi": SHIP, "body": "this is sus"}, headers=ham).json()["document"]
    assert note["kind"] == "note" and note["mmsis"] == []
    # a briefing must name its ships, and the summary kind can't be posted by hand
    assert api.post(f"/sessions/{sid}/documents", json={"kind": "briefing", "body": "x"}, headers=ham).status_code == 422
    assert api.post(f"/sessions/{sid}/documents", json={"kind": "summary", "body": "x"}, headers=ham).status_code == 422

    seen = {}

    async def fake(facts, key=None):
        seen.update(facts)
        return "The team looked at two ships."
    monkeypatch.setattr(gemini, "summarise_session", fake)
    api.post(f"/sessions/{sid}/list", json={"mmsi": SHIP}, headers=aid)
    r = api.post(f"/sessions/{sid}/summary", headers=ham)
    assert r.status_code == 201 and r.json()["document"]["kind"] == "summary"
    assert r.json()["document"]["body"] == "The team looked at two ships." and r.json()["document"]["mmsis"] == [SHIP]
    assert seen["session"] == "Baltic gaps" and {d["author"] for d in seen["documents"]} == {"A member"}
    assert seen["tracked_ships"][0]["mmsi"] == SHIP and len(seen["documents"]) == 2
    assert api.get(f"/sessions/{sid}", headers=aid).json()["documents"][-1]["kind"] == "summary"
    assert api.post(f"/sessions/{sid}/summary", headers=as_("mano")).status_code == 404   # not a member


def test_session_summary_without_a_gemini_key_is_503(api, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    sid = api.post("/sessions", json={"title": "x"}, headers=as_("hamish")).json()["id"]
    assert api.post(f"/sessions/{sid}/summary", headers=as_("hamish")).status_code == 503


def test_summarise_session_parses_the_model_answer_and_retries_once(monkeypatch):
    from dvm.briefing import gemini
    good = {"steps": [{"type": "model_output", "content": [{"type": "text", "text": '{"summary": " Fine. "}'}]}]}
    bad = {"steps": [{"type": "model_output", "content": [{"type": "text", "text": "not json"}]}]}
    answers = [bad, good]
    monkeypatch.setattr(gemini, "_post", lambda payload, key: answers.pop(0))
    assert asyncio.run(gemini.summarise_session({"session": "x"}, key="k")) == "Fine."
    monkeypatch.setattr(gemini, "_post", lambda payload, key: bad)
    with pytest.raises(gemini.BriefingError):
        asyncio.run(gemini.summarise_session({}, key="k"))
