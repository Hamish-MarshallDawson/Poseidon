"""Invites with an addressee (dvm/collab/invites.py): incoming and outgoing lists, accept, decline, revoke, and the
live push. REST through the app on the memory store."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dvm import app as app_mod, auth, collab, config
from tests.test_collab import _until, as_


@pytest.fixture
def api(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "TIGER_DATABASE_URL", "")
    monkeypatch.setattr(config, "AISSTREAM_API_KEY", "")
    monkeypatch.setattr(config, "DIGITRAFFIC", False)
    monkeypatch.setattr(auth, "ENABLED", False)
    monkeypatch.setattr(collab.live, "FANOUT_S", 0.05)
    with TestClient(app_mod.app) as c:
        yield c


def setup(api):
    ham, aid, mano = as_("hamish"), as_("aiden"), as_("mano")
    ids = {n: api.get("/me", headers=h).json()["user"]["id"] for n, h in (("ham", ham), ("aid", aid), ("mano", mano))}
    for n, h in (("Hamish", ham), ("Aiden", aid), ("Mano", mano)):
        api.post("/me", json={"name": n}, headers=h)
    sid = api.post("/sessions", json={"title": "Baltic dark ships"}, headers=ham).json()["id"]
    return ham, aid, mano, ids, sid


def test_addressed_invite_accept_and_lists(api):
    ham, aid, mano, ids, sid = setup(api)
    inv = api.post(f"/sessions/{sid}/invites", json={"to": ids["aid"]}, headers=ham).json()
    assert inv["id"] and inv["token"]
    got = api.get("/invites", headers=aid).json()
    assert [(i["session_title"], i["from"]["name"]) for i in got["incoming"]] == [("Baltic dark ships", "Hamish")]
    assert api.get("/invites", headers=mano).json() == {"incoming": [], "outgoing": []}   # not for Mano
    out = api.get("/invites", headers=ham).json()["outgoing"]
    assert out[0]["to"]["name"] == "Aiden" and out[0]["status"] == "pending"
    assert api.post(f"/invites/{inv['id']}/accept", headers=mano).status_code == 404       # not the addressee
    s = api.post(f"/invites/{inv['id']}/accept", headers=aid)
    assert s.status_code == 200 and len(s.json()["members"]) == 2
    assert api.get("/invites", headers=aid).json()["incoming"] == []
    assert api.get("/invites", headers=ham).json()["outgoing"][0]["status"] == "accepted"


def test_decline_and_revoke(api):
    ham, aid, mano, ids, sid = setup(api)
    a = api.post(f"/sessions/{sid}/invites", json={"to": ids["aid"]}, headers=ham).json()
    assert api.post(f"/invites/{a['id']}/decline", headers=mano).status_code == 404
    assert api.post(f"/invites/{a['id']}/decline", headers=aid).status_code == 204
    assert api.get("/invites", headers=aid).json()["incoming"] == []
    assert api.get("/invites", headers=ham).json()["outgoing"][0]["status"] == "declined"
    assert api.post(f"/invites/{a['id']}/accept", headers=aid).status_code == 404
    assert api.post(f"/invites/{a['token']}/accept", headers=aid).status_code == 404       # the link is dead too
    link = api.post(f"/sessions/{sid}/invites", headers=ham).json()                        # no addressee: a link
    assert api.delete(f"/invites/{link['id']}", headers=aid).status_code == 404            # only its creator
    assert api.delete(f"/invites/{link['id']}", headers=ham).status_code == 204
    assert api.post(f"/invites/{link['token']}/accept", headers=mano).status_code == 404   # revoked
    assert [o["status"] for o in api.get("/invites", headers=ham).json()["outgoing"]] == ["declined"]


def test_email_invite_matches_once_the_user_has_an_email(api):
    ham, aid, mano, ids, sid = setup(api)
    assert api.post(f"/sessions/{sid}/invites", json={"to": "not-an-email@"}, headers=ham).status_code == 422
    assert api.post(f"/sessions/{sid}/invites", json={"to": "nobody"}, headers=ham).status_code == 422
    assert api.post(f"/sessions/{sid}/invites", json={"to": ids["ham"]}, headers=ham).status_code == 409
    inv = api.post(f"/sessions/{sid}/invites", json={"to": " Aiden@Example.com "}, headers=ham).json()
    assert api.get("/invites", headers=aid).json()["incoming"] == []
    api.post("/me", json={"name": "Aiden", "email": "aiden@example.com"}, headers=aid)
    assert [i["id"] for i in api.get("/invites", headers=aid).json()["incoming"]] == [inv["id"]]
    assert api.get("/invites", headers=ham).json()["outgoing"][0]["to"] == {"email": "aiden@example.com"}
    assert api.post(f"/sessions/{sid}/invites", json={"to": "x@y.zz"}, headers=aid).status_code == 404   # not a member


def test_push_when_an_invite_arrives_and_when_it_changes(api):
    ham, aid, mano, ids, sid = setup(api)
    with api.websocket_connect("/ws") as w:
        w.send_json({"type": "auth", "dev_user": "aiden"})   # identifies the socket; no session needed
        w.send_json({"type": "presence"})                    # a no-op round trip so the auth is handled first
        inv = api.post(f"/sessions/{sid}/invites", json={"to": ids["aid"]}, headers=ham).json()
        m = _until(w, "invite")
        assert m["invite_id"] == inv["id"] and m["session_id"] == sid
        api.delete(f"/invites/{inv['id']}", headers=ham)
        _until(w, "invites_changed")


def test_no_invite_for_a_member_and_my_other_tabs_hear_of_accept_and_decline(api):
    ham, aid, mano, ids, sid = setup(api)
    inv = api.post(f"/sessions/{sid}/invites", json={"to": ids["aid"]}, headers=ham).json()
    with api.websocket_connect("/ws") as w:
        w.send_json({"type": "auth", "dev_user": "aiden"})
        w.send_json({"type": "presence"})
        assert api.post(f"/invites/{inv['id']}/accept", headers=aid).status_code == 200
        _until(w, "invites_changed")                                                      # Aiden's other tab clears its badge
    assert api.post(f"/sessions/{sid}/invites", json={"to": ids["aid"]}, headers=ham).status_code == 409   # already in
    b = api.post(f"/sessions/{sid}/invites", json={"to": ids["mano"]}, headers=ham).json()
    with api.websocket_connect("/ws") as w:
        w.send_json({"type": "auth", "dev_user": "mano"})
        w.send_json({"type": "presence"})
        assert api.post(f"/invites/{b['id']}/decline", headers=mano).status_code == 204
        _until(w, "invites_changed")


def test_a_dropped_connection_is_retried_once():
    import asyncio
    import asyncpg
    from dvm.collab.invites import retry_dropped

    @retry_dropped
    class Store:
        calls = 0

        def __init__(self, err):
            self.err = err

        async def get(self):
            Store.calls += 1
            if Store.calls == 1:
                raise self.err
            return "ok"

    for err in (asyncpg.exceptions.AdminShutdownError("terminating connection due to administrator command"),
                asyncpg.ConnectionDoesNotExistError(), asyncpg.InterfaceError("connection is closed"),
                ConnectionResetError()):
        Store.calls = 0
        assert asyncio.run(Store(err).get()) == "ok" and Store.calls == 2
    @retry_dropped
    class Dead(Store):
        async def get(self):
            Store.calls += 1
            raise self.err

    Store.calls = 0   # fails again on the retry: the error surfaces, no endless loop
    with pytest.raises(asyncpg.InterfaceError):
        asyncio.run(Dead(asyncpg.InterfaceError("closed")).get())
    assert Store.calls == 2
