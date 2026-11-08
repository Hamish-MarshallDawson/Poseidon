"""VesselView.cls (#95): the AIS class of the ship's latest position, in live snapshots, deltas and replay."""
from __future__ import annotations

import asyncio

from dvm import replay
from dvm.live import Live
from dvm.models import PositionReport, VesselStatic, VesselView

T = 1_794_100_000_000


def fix(mmsi, cls, ts=T, lat=60.0):
    return PositionReport(mmsi=mmsi, ts=ts, recv_ts=ts, lat=lat, lon=25.0, cls=cls, ts_quality="rebuilt",
                          src="aisstream")


def test_class_a_and_b_ships_show_their_cls():
    live = Live()
    live.apply(fix(230000001, "A"))
    live.apply(fix(230000002, "B"))
    by = {v["mmsi"]: v for v in live.snapshot()}
    assert by[230000001]["cls"] == "A" and by[230000002]["cls"] == "B"
    vessels, _ = live.take_changes(T, 1800)   # deltas use the same view
    assert {v["mmsi"]: v["cls"] for v in vessels} == {230000001: "A", 230000002: "B"}
    assert live.detail(230000002)["vessel"]["cls"] == "B"


def test_cls_follows_the_latest_position():
    live = Live()
    live.apply(fix(230000001, "A"))
    live.apply(fix(230000001, "B", ts=T + 60_000, lat=60.1))
    assert live.view(230000001)["cls"] == "B"


def test_statics_only_ship_has_no_view_and_the_default_is_null():
    live = Live()
    live.apply(VesselStatic(mmsi=230000003, ts=T, recv_ts=T, mid=230, src="aisstream", name="ONLY STATICS"))
    assert live.snapshot() == []   # no position, so no dot and no cls to report
    assert VesselView(mmsi=1, lat=0, lon=0, last_ts=0).cls is None
    live.apply(fix(230000003, "A"))
    assert live.view(230000003)["cls"] == "A" and live.view(230000003)["name"] == "ONLY STATICS"


def test_replay_snapshot_carries_cls():
    rows = [fix(230000001, "A").model_dump(exclude={"kind"}), fix(230000002, "B").model_dump(exclude={"kind"})]

    class History:
        async def range(self):
            return T, T

        async def latest_positions(self, t, window_s):
            return rows

        async def identities(self, t, window_s):
            return {}

        async def between(self, a, b):
            return [], []

    sent = []

    async def send(m):
        sent.append(m)

    asyncio.run(replay.ReplaySession(History(), send).seek(T))
    snap = next(m for m in sent if m["type"] == "snapshot")
    assert {v["mmsi"]: v["cls"] for v in snap["vessels"]} == {230000001: "A", 230000002: "B"}
