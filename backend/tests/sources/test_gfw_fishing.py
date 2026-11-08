"""GFW fishing events (#157): parsing a recorded response, the week and region filter, gear types, and idempotent
fetches into a local TimescaleDB.

The fixture is seven real events from the 19 Oct 2026 week (`/events` with the region polygons): five Danish (one
started the week before, two inside an MPA) and two in the Gulf of Oman, plus the recorded `/vessels` identity answer
for their vessels, cut to the fields parse_gear reads.
"""
import asyncio
import copy
import json
import os
from datetime import date
from pathlib import Path

import asyncpg
import pytest

from dvm.sources import gfw_fishing as F
from dvm.sources.common import DAY_MS, REGIONS, day_ms, iso_ms

URL = os.getenv("SOURCES_TEST_DATABASE_URL", "")
needs_db = pytest.mark.skipif(not URL or "tsdb.cloud" in URL or "timescale.com" in URL,
                              reason="set SOURCES_TEST_DATABASE_URL to a local TimescaleDB")

FX = json.loads((Path(__file__).parent / "fixtures" / "gfw_fishing_sample.json").read_text())
EV, VS = FX["events"], FX["vessels"]
WEEK = date(2026, 10, 19)
S, E = day_ms(WEEK), day_ms(WEEK) + 7 * DAY_MS
RECV = iso_ms("2026-11-08T04:00:00Z")
DK, OM = REGIONS["danish_straits"], REGIONS["gulf_of_oman"]


def test_week_and_region_filter():
    obs, c = F.parse_fishing(EV, "danish_straits", DK, S, E, RECV)
    assert c == {"events": 7, "earlier_week": 1, "outside": 2, "no_vessel": 0, "bad": 0}
    assert len(obs) == 4 and all(S <= o.ts < E for o in obs)
    assert sum(bool(o.attrs["mpa"]) for o in obs) == 2
    om, c2 = F.parse_fishing(EV, "gulf_of_oman", OM, S, E, RECV)
    assert len(om) == 2 and c2["outside"] == 4 and {o.attrs["flag"] for o in om} == {"IRN"}
    # The week before gets only the one that started then.
    prev, _ = F.parse_fishing(EV, "danish_straits", DK, S - 7 * DAY_MS, S, RECV)
    assert [o.attrs["event_id"] for o in prev] == [EV["entries"][0]["id"]]


def test_fields_from_recorded_event():
    gear = F.parse_gear(VS)
    e = next(x for x in EV["entries"] if x["regions"]["mpa"])
    (o,), _ = F.parse_fishing({"entries": [e]}, "danish_straits", DK, S, E, RECV, gear)
    assert o.id == f"gfw:fishing:{e['id']}" and o.kind == "fishing" and o.src == "gfw"
    assert o.ts == iso_ms(e["start"]) and o.end_ts == iso_ms(e["end"]) and o.mmsi == int(e["vessel"]["ssvid"])
    assert (o.lat, o.lon) == (e["position"]["lat"], e["position"]["lon"])
    assert o.value == pytest.approx((o.end_ts - o.ts) / 3_600_000)
    a = o.attrs
    assert a["mpa"] == e["regions"]["mpa"] and a["mpa_no_take"] == [] and a["eez"] == e["regions"]["eez"]
    assert a["eez12nm"] == e["regions"]["eez12Nm"] and a["rfmo"] and a["high_seas"] == []
    assert a["protectedseas"] == e["regions"]["protectedseas"]
    assert a["potential_risk"] is e["fishing"]["potentialRisk"]
    assert a["authorization_status"] == e["fishing"]["vesselPublicAuthorizationStatus"]
    assert a["avg_speed_kn"] == pytest.approx(e["fishing"]["averageSpeedKnots"])
    assert a["distance_km"] == pytest.approx(e["fishing"]["totalDistanceKm"])
    assert a["name"] == e["vessel"]["name"] and a["flag"] == e["vessel"]["flag"] and a["region"] == "danish_straits"
    assert a["gear_type"] and a["gear_type"] == gear[e["vessel"]["id"]]
    # Backfilled long after it ended: end's UTC day plus GFW's 4-day lag, flagged.
    end_day = iso_ms(e["end"]) // DAY_MS * DAY_MS
    assert o.available_ts == end_day + DAY_MS + 4 * DAY_MS and o.q == ["available_est"]
    recent = iso_ms(e["end"]) + 2 * DAY_MS
    (o2,), _ = F.parse_fishing({"entries": [e]}, "danish_straits", DK, S, E, recent)
    assert o2.available_ts == recent and o2.q == []


def test_gear_for_every_vessel_and_bad_rows():
    gear = F.parse_gear(VS)
    assert all(x["vessel"]["id"] in gear for x in EV["entries"])
    bad = copy.deepcopy(EV["entries"][1:3])
    bad[0]["vessel"]["ssvid"] = "123"
    del bad[1]["position"]
    obs, c = F.parse_fishing({"entries": bad}, "danish_straits", DK, S, E, RECV)
    assert obs == [] and c["no_vessel"] == 1 and c["bad"] == 1
    assert F.window_start(date(2026, 10, 25)) == WEEK


class FakeClient:
    """/events from the fixture in pages of 2 (geometry required), /vessels from the recorded identity answer."""

    def __init__(self, vessels_fail=False):
        self.calls, self.vcalls, self.vessels_fail = 0, 0, vessels_fail

    def _post(self, path, params, body):
        assert path == "/events" and body["datasets"] == [F.DATASET] and body["geometry"]["type"] == "Polygon"
        self.calls += 1
        off = params["offset"]
        page = EV["entries"][off:off + 2]
        return {"entries": page, "total": len(EV["entries"]), "nextOffset": off + 2 if off + 2 < 7 else None}

    def _get(self, path, params):
        assert path == "/vessels" and params[0] == ("datasets[0]", F.IDENTITY)
        self.vcalls += 1
        if self.vessels_fail:
            raise RuntimeError("GFW /vessels HTTP 503")
        return VS

    def close(self):
        pass


async def _db_run(monkeypatch):
    con = await asyncpg.connect(URL)
    pool = None
    try:
        from dvm.sources import jobs
        pool = await jobs.connect(URL)
        await con.execute("DELETE FROM observations WHERE id LIKE 'gfw:fishing:%'")
        await con.execute("DELETE FROM source_windows WHERE src = 'gfw' AND stream = 'fishing'")
        regions = ["danish_straits", "gulf_of_oman"]

        # Gear lookup down: the events still land, without gear types.
        r0 = await F.run_window(pool, WEEK, regions, client=FakeClient(vessels_fail=True))
        assert r0["observations"] == 6
        assert await con.fetchval("SELECT count(*) FROM observations WHERE kind = 'fishing' "
                                  "AND attrs ? 'gear_type'") == 0

        fake = FakeClient()
        r1 = await F.run_window(pool, WEEK, regions, client=fake, force=True)
        assert r1["observations"] == 6 and r1["regions"]["danish_straits"]["observations"] == 4
        assert r1["regions"]["danish_straits"]["in_mpa"] == 2 and r1["regions"]["gulf_of_oman"]["observations"] == 2
        assert fake.calls == 8 and fake.vcalls == 2                    # 4 pages and 1 vessel call per region
        assert await con.fetchval("SELECT count(*) FROM observations WHERE kind = 'fishing'") == 6
        assert await con.fetchval("SELECT count(*) FROM observations WHERE kind = 'fishing' "
                                  "AND attrs ? 'gear_type'") == 6       # re-fetch upserts the same ids
        led = await con.fetch("SELECT region, rows, status FROM source_windows WHERE stream = 'fishing' ORDER BY 1")
        assert [tuple(x) for x in led] == [("danish_straits", 4, "ok"), ("gulf_of_oman", 2, "ok")]

        # Settled long ago: skipped without a call.
        assert (await F.run_window(pool, WEEK, regions, client=fake)).get("skipped") and fake.calls == 8
        e = next(x for x in EV["entries"] if x["regions"]["mpa"])
        row = await con.fetchrow("SELECT * FROM observations WHERE id = $1", f"gfw:fishing:{e['id']}")
        assert row["kind"] == "fishing" and row["ts"] == iso_ms(e["start"]) and row["mmsi"] == int(e["vessel"]["ssvid"])
        assert json.loads(row["attrs"])["mpa"] == e["regions"]["mpa"]

        # backfill(): the week before gets the one early event; the fixture week is skipped.
        monkeypatch.setattr(F.gfw, "Client", FakeClient)
        out = await F.backfill(URL, regions, date(2026, 10, 12), date(2026, 10, 25))
        assert [x["week"] for x in out] == ["2026-10-12", "2026-10-19"] and out[1].get("skipped")
        assert out[0]["observations"] == 1
        assert await con.fetchval("SELECT count(*) FROM observations WHERE kind = 'fishing'") == 7
    finally:
        await con.execute("DELETE FROM observations WHERE id LIKE 'gfw:fishing:%'")
        await con.execute("DELETE FROM source_windows WHERE src = 'gfw' AND stream = 'fishing'")
        await con.close()
        if pool:
            await pool.close()


@needs_db
def test_window_idempotent_in_db(monkeypatch):
    asyncio.run(_db_run(monkeypatch))
