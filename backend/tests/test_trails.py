"""Live trails for the detail reply (06 section 4.3): 30 points, 60 s apart, last 60 minutes (#80 trails)."""
from __future__ import annotations

import json
from types import SimpleNamespace

import pytest
from fastapi.testclient import TestClient

from dvm import app as app_mod, auth, config
from dvm.app import TRAIL_POINTS, Trails
from dvm.live import Live
from dvm.models import PositionReport

T = 1_794_100_000_000
M = 230000001


def fix(ts, lon=25.0, lat=60.0, mmsi=M):
    return PositionReport(mmsi=mmsi, ts=ts, recv_ts=ts, lat=lat, lon=lon, sog_kn=10.0, cls="A",
                          ts_quality="rebuilt", src="aisstream")


def test_points_are_kept_60s_apart_in_order():
    tr = Trails()
    for i, dt in enumerate([0, 10_000, 59_999, 60_000, 90_000, 130_000]):
        tr.add(fix(T + dt, lon=25 + i / 100))
    assert [p[0] - T for p in tr.get(M, T + 130_000)] == [0, 60_000, 130_000]
    assert tr.get(M, T)[0] == [T, 25.0, 60.0]   # [ts, lon, lat]


def test_older_fix_never_goes_back_in():
    tr = Trails()
    tr.add(fix(T + 120_000))
    tr.add(fix(T))   # late, older fix
    assert [p[0] for p in tr.get(M, T + 120_000)] == [T + 120_000]


def test_at_most_30_points():
    tr = Trails()
    for i in range(50):
        tr.add(fix(T + i * 60_000))
    pts = tr.get(M, T + 49 * 60_000)
    assert len(pts) == TRAIL_POINTS and pts[-1][0] == T + 49 * 60_000


def test_points_older_than_60_min_are_dropped():
    tr = Trails()
    tr.add(fix(T))
    tr.add(fix(T + 30 * 60_000))
    now = T + 61 * 60_000
    assert [p[0] for p in tr.get(M, now)] == [T + 30 * 60_000]
    tr.prune(now, keep={M})
    assert len(tr.by_mmsi[M]) == 1
    tr.prune(T + 120 * 60_000, keep={M})
    assert M not in tr.by_mmsi   # empty trails are forgotten


def test_ships_off_the_map_are_dropped():
    tr = Trails()
    tr.add(fix(T))
    tr.add(fix(T, mmsi=244000002))
    tr.drop([M])
    tr.prune(T, keep=set())
    assert tr.by_mmsi == {}


@pytest.fixture
def client(tmp_path, monkeypatch):
    for k, v in (("DATA_DIR", tmp_path), ("TIGER_DATABASE_URL", ""), ("AISSTREAM_API_KEY", ""), ("DIGITRAFFIC", False)):
        monkeypatch.setattr(config, k, v)
    monkeypatch.setattr(auth, "ENABLED", False)
    with TestClient(app_mod.app) as c:
        yield c


def test_merged_positions_feed_the_trail(client):
    app_mod.hub._emit([fix(T), fix(T + 60_000, lon=25.1)])
    assert [p[1] for p in app_mod.hub.trails.get(M, T + 60_000)] == [25.0, 25.1]


def test_live_detail_has_the_trail(client, monkeypatch):
    now = app_mod.now_ms()
    app_mod.hub._emit([fix(now - 120_000), fix(now - 60_000, lon=25.1), fix(now, lon=25.2)])
    with client.websocket_connect("/ws") as ws:
        ws.receive_json(), ws.receive_json()   # hello, snapshot
        ws.send_text(json.dumps({"type": "detail", "mmsi": M}))
        d = ws.receive_json()
        while d["type"] != "detail":
            d = ws.receive_json()
        assert [p[1] for p in d["trail"]] == [25.0, 25.1, 25.2]
        ws.send_text(json.dumps({"type": "detail", "mmsi": [M]}))   # junk mmsi: ignored, socket stays open
        ws.send_text(json.dumps({"type": "detail", "mmsi": M}))
        d = ws.receive_json()
        while d["type"] != "detail":
            d = ws.receive_json()
        assert "trail" in d


def test_replay_detail_has_no_trail(client, monkeypatch):
    past = Live()
    past.apply(fix(T))

    async def fake_replay(c, msg):
        c.replay = SimpleNamespace(live=past, close=lambda: None)
    monkeypatch.setattr(app_mod, "handle_replay", fake_replay)
    app_mod.hub._emit([fix(app_mod.now_ms())])
    with client.websocket_connect("/ws") as ws:
        ws.receive_json(), ws.receive_json()
        ws.send_text(json.dumps({"type": "replay", "action": "seek", "t": T}))
        ws.send_text(json.dumps({"type": "detail", "mmsi": M}))
        d = ws.receive_json()
        while d["type"] != "detail":
            d = ws.receive_json()
        assert "trail" not in d and d["vessel"]["last_ts"] == T   # answered from the replay state
