"""app.py sends AISStream and Digitraffic records through one FeedMerger before the map and the store (#59 item 5)."""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from dvm import app as app_mod, auth, config, merge
from dvm.models import PositionReport

T = 1_794_090_000_000


def fix(src, ts=T, recv=T + 500, sog=10.0, quality="source"):
    return PositionReport(mmsi=230000001, ts=ts, recv_ts=recv, lat=60.123456, lon=24.654321, sog_kn=sog, cls="A",
                          ts_quality=quality, src=src)


class FakeStore:
    pool = None
    rows_written, last_error = 0, None

    def __init__(self):
        self.rows = []

    def add(self, rec):
        self.rows.append(rec)


@pytest.fixture
def hub(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "TIGER_DATABASE_URL", "")
    monkeypatch.setattr(config, "DIGITRAFFIC", True)
    h = app_mod.Hub()
    h.store = FakeStore()
    yield h
    h.rawlog.close()


def test_same_fix_from_both_feeds_is_stored_once(hub):
    hub.digitraffic_sink(fix("digitraffic"))                    # first sighting while... no other feed yet: emitted
    hub.ingest(fix("aisstream", ts=T, quality="rebuilt", sog=None), T + 1000)   # the AISStream copy of that fix
    assert len(hub.store.rows) == 1 and hub.merger.stats["late_dup_dropped"] + hub.merger.stats["merged"] == 1
    assert 230000001 in hub.live.pos


def test_held_fix_is_released_by_the_tick_flush(hub):
    hub.ingest(fix("digitraffic", ts=T - 60_000, recv=T - 59_500), T - 59_500)   # Digitraffic hears the ship
    hub.ingest(fix("aisstream", ts=T, quality="rebuilt"), T)    # overlap ship: held for Digitraffic's copy
    assert len(hub.store.rows) == 1 and hub.merger.stats["held"] == 1
    hub._emit(hub.merger.flush(T + merge.HOLD_MS))              # what tick() does every second
    assert len(hub.store.rows) == 2 and hub.live.pos[230000001].ts == T


def test_a_record_that_breaks_the_pipeline_is_counted_not_raised(hub, monkeypatch):
    monkeypatch.setattr(hub.merger, "push", lambda rec, now: 1 / 0)
    hub.digitraffic_sink(fix("digitraffic"))
    assert hub.bad_messages == 1


def test_health_shows_digitraffic_and_merger(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "TIGER_DATABASE_URL", "")
    monkeypatch.setattr(config, "AISSTREAM_API_KEY", "")
    monkeypatch.setattr(config, "DIGITRAFFIC", False)   # no network in unit tests
    monkeypatch.setattr(auth, "ENABLED", False)
    with TestClient(app_mod.app) as c:
        h = c.get("/health").json()
        assert h["digitraffic"] == {"enabled": False} and "pos_in" in h["merger"]
        assert c.get("/observations", params={"bbox": "[[19,54],[31,61]]"}).status_code == 503   # mounted, no DB
        assert c.get("/model/positions", params={"as_of": T}).status_code == 503
