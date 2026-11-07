"""app.py mounts the briefing router against the hub built in lifespan."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dvm import app as app_mod, auth, config
from dvm.models import PositionReport


@pytest.fixture
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "TIGER_DATABASE_URL", "")
    monkeypatch.setattr(config, "AISSTREAM_API_KEY", "")
    monkeypatch.setattr(auth, "ENABLED", False)
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    with TestClient(app_mod.app) as c:
        yield c


def test_briefing_routes_are_mounted(client):
    paths = set(client.get("/openapi.json").json()["paths"])
    assert {"/briefing", "/briefing/speech"} <= paths


def test_briefing_reads_the_live_hub(client):
    assert client.post("/briefing", json={"mmsis": [230000001]}).status_code == 404   # not in the live picture
    app_mod.hub.live.apply(PositionReport(mmsi=230000001, ts=1, recv_ts=1, lat=60.0, lon=25.0, cls="A",
                                          ts_quality="rebuilt", src="aisstream"))
    r = client.post("/briefing", json={"mmsis": [230000001]})
    assert r.status_code == 503 and "GEMINI_API_KEY" in r.json()["detail"]   # found the ship; no key here


def test_briefing_needs_login_when_auth_is_on(client, monkeypatch):
    monkeypatch.setattr(auth, "ENABLED", True)
    assert client.post("/briefing", json={"mmsis": [230000001]}).status_code == 401
