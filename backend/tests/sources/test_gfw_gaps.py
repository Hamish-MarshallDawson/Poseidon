"""GFW gap events (#112): parsing recorded responses, the area filter, and idempotent fetches into a local TimescaleDB.

The fixture is eight real events from worldwide day queries (Jan 2024, Jun 2025, Oct 2026): one with the off fix in
each area, one with the on fix, one whose segment crosses the Arabian Sea, one elsewhere, a gear buoy and a bad MMSI.
"""
import asyncio
import json
import os
from datetime import date
from pathlib import Path

import asyncpg
import pytest

from dvm.sources import gfw_gaps as G
from dvm.sources.common import DAY_MS, iso_ms

URL = os.getenv("SOURCES_TEST_DATABASE_URL", "")
needs_db = pytest.mark.skipif(not URL or "tsdb.cloud" in URL or "timescale.com" in URL,
                              reason="set SOURCES_TEST_DATABASE_URL to a local TimescaleDB")

FX = json.loads((Path(__file__).parent / "fixtures" / "gfw_gaps_sample.json").read_text())
IDS = {"off_ar": "98c4895693ec3c061979c4b10718bf72", "on_ar": "0759c60d9a630efeb102bb7c4a78f876",
       "seg_ar": "541f9dffd121130f0d93c9463dadcc0c", "off_eu": "78b68389906111da6e2006cd9bb9a2c8",
       "on_eu": "c4794d32e38208dd8a6b1875f5a03e89", "elsewhere": "514d7a089cfba4fe822067bc65bd3a38"}
RECV = iso_ms("2026-11-08T04:00:00Z")


def ev(key):
    return next(e for e in FX["entries"] if e["id"] == IDS[key])


def test_area_filter():
    obs, counts = G.parse_gaps(FX, ["arabian_sea"], RECV)
    assert {o.id for o in obs} == {f"gfw:gap:{IDS[k]}" for k in ("off_ar", "on_ar", "seg_ar")}
    assert counts == {"events": 8, "gear": 1, "no_vessel": 1, "outside": 3, "bad": 0}
    by = {o.attrs["event_id"]: o.attrs["areas"] for o in obs}
    assert by[IDS["off_ar"]]["arabian_sea"] == "off" and by[IDS["on_ar"]]["arabian_sea"] == "on"
    assert by[IDS["seg_ar"]]["arabian_sea"] == "segment"
    eu, _ = G.parse_gaps(FX, ["europe_north"], RECV)
    assert {o.attrs["event_id"] for o in eu} == {IDS["off_eu"], IDS["on_eu"]}
    world, c = G.parse_gaps(FX, ["world"], RECV)
    assert len(world) == 6 and c["outside"] == 0 and c["gear"] == 1
    assert "areas" not in next(o for o in world if o.attrs["event_id"] == IDS["elsewhere"]).attrs


def test_fields_from_recorded_event():
    e = ev("off_eu")
    (o,), _ = G.parse_gaps({"entries": [e]}, ["europe_north"], RECV)
    g = e["gap"]
    assert o.id == f"gfw:gap:{e['id']}" and o.kind == "gap" and o.src == "gfw"
    assert o.ts == iso_ms(e["start"]) and o.end_ts == iso_ms(e["end"]) and o.mmsi == int(e["vessel"]["ssvid"])
    assert (o.lat, o.lon) == (g["offPosition"]["lat"], g["offPosition"]["lon"])        # AIS off, not the midpoint
    assert (o.attrs["on_lat"], o.attrs["on_lon"]) == (g["onPosition"]["lat"], g["onPosition"]["lon"])
    assert o.value == pytest.approx(g["durationHours"])
    assert o.attrs["distance_km"] == pytest.approx(float(g["distanceKm"]))             # GFW sends it as a string
    assert o.attrs["intentional_disabling"] is True and o.attrs["off_shore_km"] >= 93
    assert o.bbox[0] <= o.lon <= o.bbox[2] and o.bbox[1] <= o.lat <= o.bbox[3]
    # Backfilled long after it closed: the end's UTC day plus GFW's 4-day lag, flagged as an estimate.
    end_day = iso_ms(e["end"]) // DAY_MS * DAY_MS
    assert o.available_ts == end_day + DAY_MS + 4 * DAY_MS and o.q == ["available_est"]
    # Fetched within days of closing: our fetch is the publication time.
    recent = iso_ms(e["end"]) + 3 * DAY_MS
    (o2,), _ = G.parse_gaps({"entries": [e]}, ["europe_north"], recent)
    assert o2.available_ts == recent and o2.q == []


def test_segment_and_week():
    box = (0, 0, 10, 10)
    assert G.segment_hits((-5, 5), (15, 5), box)          # passes straight through
    assert not G.segment_hits((-5, 20), (15, 20), box)    # passes above
    assert not G.segment_hits((-5, 15), (5, 25), box)     # diagonal that misses the corner
    assert not G.segment_hits((-170, 5), (170, 5), box)   # across the antimeridian: never drawn the long way
    assert G.window_start(date(2026, 11, 8)) == date(2026, 11, 2)   # Sunday -> its Monday
    assert G.window_start(date(2026, 11, 2)) == date(2026, 11, 2)


class FakeClient:
    """Answers /events from the fixture, in pages of 3, and counts calls."""

    def __init__(self):
        self.calls = 0

    def _post(self, path, params, body):
        assert path == "/events" and "geometry" not in body and body["datasets"] == [G.DATASET]
        self.calls += 1
        off = params["offset"]
        page = FX["entries"][off:off + 3]
        nxt = off + 3 if off + 3 < len(FX["entries"]) else None
        return {"entries": page, "total": len(FX["entries"]), "nextOffset": nxt}

    def close(self):
        pass


async def _db_run(monkeypatch):
    con = await asyncpg.connect(URL)
    pool = None
    try:
        from dvm.sources import jobs
        pool = await jobs.connect(URL)
        ids = [f"gfw:gap:{i}" for i in IDS.values()]
        await con.execute("DELETE FROM observations WHERE id = ANY($1)", ids)
        await con.execute("DELETE FROM source_windows WHERE src = 'gfw' AND stream = 'gaps'")
        fake = FakeClient()
        wk = date(2024, 1, 8)
        areas = ["europe_north", "arabian_sea"]

        r1 = await G.run_window(pool, wk, areas, client=fake)
        assert r1["observations"] == 5 and r1["areas"] == {"europe_north": 2, "arabian_sea": 3}
        assert fake.calls == 3                                         # 8 events, pages of 3: one fetch for both areas
        assert await con.fetchval("SELECT count(*) FROM observations WHERE id = ANY($1)", ids) == 5
        led = await con.fetch("SELECT region, rows, status FROM source_windows WHERE stream = 'gaps' ORDER BY 1")
        assert [tuple(x) for x in led] == [("arabian_sea", 3, "ok"), ("europe_north", 2, "ok")]

        # Settled long ago: the ledger skips it without a call.
        assert (await G.run_window(pool, wk, areas, client=fake)).get("skipped") and fake.calls == 3
        # Forced, and with world added: same rows upserted, the one extra event lands once.
        r3 = await G.run_window(pool, wk, areas + ["world"], client=fake, force=True)
        assert r3["observations"] == 6
        assert await con.fetchval("SELECT count(*) FROM observations WHERE id = ANY($1)", ids) == 6
        row = await con.fetchrow("SELECT * FROM observations WHERE id = $1", f"gfw:gap:{IDS['off_eu']}")
        assert row["kind"] == "gap" and row["ts"] == iso_ms(ev("off_eu")["start"])
        assert json.loads(row["attrs"])["areas"] == {"europe_north": "off"}

        # backfill(): a short range resumes from the ledger (all three weeks already settled or fetched once).
        monkeypatch.setattr(G.gfw, "Client", FakeClient)
        out = await G.backfill(URL, areas, date(2024, 1, 1), date(2024, 1, 21))
        assert [x["week"] for x in out] == ["2024-01-01", "2024-01-08", "2024-01-15"]
        assert out[1].get("skipped") and not out[0].get("skipped")
        assert await con.fetchval("SELECT count(*) FROM observations WHERE id = ANY($1)", ids) == 6
        assert await con.fetchval("SELECT count(*) FROM source_windows WHERE stream = 'gaps'") == 7
    finally:
        await con.execute("DELETE FROM observations WHERE id LIKE 'gfw:gap:%'")
        await con.execute("DELETE FROM source_windows WHERE src = 'gfw' AND stream = 'gaps'")
        await con.close()
        if pool:
            await pool.close()


@needs_db
def test_window_idempotent_in_db(monkeypatch):
    asyncio.run(_db_run(monkeypatch))
