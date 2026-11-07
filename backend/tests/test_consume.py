"""Hub.consume must survive a message that raises (stress-suite bug 1): skip it, count it, keep going."""
from __future__ import annotations

import asyncio
import json
import logging

import pytest

from dvm import app as app_mod, config

T0 = 1_762_500_000_000


def position(mmsi: int, sog=10.0) -> str:
    return json.dumps({
        "MessageType": "PositionReport",
        "MetaData": {"MMSI": mmsi, "time_utc": "2025-11-07 07:20:00.000000000 +0000 UTC"},
        "Message": {"PositionReport": {"UserID": mmsi, "Latitude": 60.0, "Longitude": 25.0, "Sog": sog, "Cog": 90.0,
                                       "TrueHeading": 90, "Timestamp": 0, "NavigationalStatus": 0, "Valid": True,
                                       "MessageID": 1}},
    })


@pytest.fixture
def hub(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "TIGER_DATABASE_URL", "")
    h = app_mod.Hub()
    yield h
    h.rawlog.close()


def drain(hub, msgs):
    async def go():
        task = asyncio.create_task(hub.consume())
        for m in msgs:
            hub.queue.put_nowait((T0, m))
        while not hub.queue.empty():
            await asyncio.sleep(0)
        await asyncio.sleep(0)
        task.cancel()
        await asyncio.gather(task, return_exceptions=True)
        return task
    return asyncio.run(go())


def test_bad_message_is_skipped_and_counted(hub, caplog):
    msgs = [position(538003705), position(538003706, sog="abc"), b"\xff\xfe not json", position(538003707)]
    with caplog.at_level(logging.WARNING, logger="dvm"):
        task = drain(hub, msgs)
    assert task.cancelled(), "consume stopped by itself"
    assert {538003705, 538003707} <= set(hub.live.pos), "messages after the bad one were not handled"
    assert hub.bad_messages == 1 and hub.last_bad.startswith(("TypeError", "ValueError"))
    assert sum("Skipped a bad message" in r.message for r in caplog.records) == 1


def test_bad_message_log_is_rate_limited(hub, caplog):
    with caplog.at_level(logging.WARNING, logger="dvm"):
        drain(hub, [position(538003706, sog="abc")] * 50)
    assert hub.bad_messages == 50
    assert sum("Skipped a bad message" in r.message for r in caplog.records) == 1


def test_health_reports_bad_messages(hub, monkeypatch):
    monkeypatch.setattr(app_mod, "hub", hub, raising=False)
    hub.bad_messages, hub.last_bad = 3, "TypeError: x"
    body = app_mod.health()
    assert body["aisstream"]["bad_messages"] == 3 and body["aisstream"]["last_bad"] == "TypeError: x"
