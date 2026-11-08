"""#101 yachts: IMO check digits, OpenSanctions filter, IMO-only matching, live status and the /yachts shape."""
from __future__ import annotations

import io

from fastapi import FastAPI
from fastapi.testclient import TestClient

from dvm.live import Live
from dvm.models import PositionReport
from dvm.yachts import ref
from dvm.yachts.routes import make_router

DILBAR, AMADEA, TANKER = 9661792, 1012531, 9292058


def test_imo_check_digit():
    assert ref.valid_imo(DILBAR) and ref.valid_imo("1012531") and ref.valid_imo(9074729)
    assert not ref.valid_imo(9661793)                       # wrong check digit
    for bad in (0, 1234567, 999999999, 9999999, 123456, None, "", "IMO"):
        assert not ref.valid_imo(bad)                        # placeholders, wrong length, junk
    assert ref.imo_of("IMO9661792;ZGFO") == DILBAR
    assert ref.imo_of("IMO1234567;IMO9661792") == DILBAR    # skips the placeholder
    assert ref.imo_of("572465210;T2EQ4") is None


CSV = (
    "id,schema,name,identifiers,sanctions,program_ids\n"
    "a,Vessel,Dilbar,IMO9661792;ZGFO,EO14024,US-RUSHAR\n"
    "b,Vessel,DILBAR,IMO9661792,\"EU, Russia\",EU-RUS\n"     # same ship, another list: programmes merge
    "c,Vessel,Ghost,IMO1234567,x,US-X\n"                    # placeholder IMO
    "d,Vessel,No IMO,572465210,x,US-X\n"
    "e,Person,Someone,IMO9661792,x,US-X\n"                  # not a vessel
    "f,Vessel,Tango,IMO9292058,x,EU-RUS\n"
)


def test_sanctioned_vessels_filter():
    got = ref.sanctioned_vessels(io.StringIO(CSV))
    assert set(got) == {DILBAR, TANKER}
    assert got[DILBAR] == {"name": "Dilbar", "programs": ["EU-RUS", "US-RUSHAR"], "entity_id": "a"}


NOTABLE = {DILBAR: {"imo": DILBAR, "name": "Dilbar", "length_m": 156.0, "owner": "Owner A", "url": "https://w/Dilbar"},
           AMADEA: {"imo": AMADEA, "name": "Amadea", "length_m": 106.0, "owner": "Owner B", "url": "https://w/Amadea"}}


def test_matching_is_by_imo_and_keeps_only_yachts():
    sanctioned = ref.sanctioned_vessels(io.StringIO(CSV))
    statics = {DILBAR: {"mmsi": 319094900, "ship_type": 37, "length_m": 156, "name": "DILBAR"},
               TANKER: {"mmsi": 273000001, "ship_type": 80, "length_m": 180, "name": "TANGO"}}
    rows = {r["imo"]: r for r in ref.build_rows(NOTABLE, sanctioned, statics)}
    assert set(rows) == {DILBAR, AMADEA}                    # the sanctioned tanker is not a yacht
    d = rows[DILBAR]
    assert d["sanctioned"] and d["programs"] == ["EU-RUS", "US-RUSHAR"] and d["mmsi"] == 319094900
    assert d["owner_reported"] == "Owner A" and d["owner_source_url"] == "https://w/Dilbar"
    assert d["sanctions_source"] == "https://www.opensanctions.org/entities/a"
    assert rows[AMADEA]["mmsi"] is None and not rows[AMADEA]["sanctioned"]   # no statics row with that IMO
    # a sanctioned pleasure craft that is not on the notable list still counts
    statics[TANKER]["ship_type"] = 37
    assert TANKER in {r["imo"] for r in ref.build_rows(NOTABLE, sanctioned, statics)}


def test_name_never_matches():
    # A 20 m "DILBAR" with another IMO must not become the famous yacht.
    rows = ref.build_rows(NOTABLE, {}, {9074729: {"mmsi": 211000001, "ship_type": 37, "length_m": 20, "name": "DILBAR"}})
    assert {r["imo"]: r["mmsi"] for r in rows} == {DILBAR: None, AMADEA: None}


def test_notable_json_is_valid():
    notable = ref.load_notable()
    assert len(notable) > 50 and all(ref.valid_imo(i) for i in notable)
    assert all(y["url"].startswith("https://en.wikipedia.org/wiki/") for y in notable.values())


def _pos(mmsi, ts):
    return PositionReport(mmsi=mmsi, ts=ts, recv_ts=ts, lat=55.0, lon=20.0, cls="A", ts_quality="rebuilt", src="aisstream")


def test_endpoint_shape_and_status():
    live = Live()
    live.apply(_pos(319094900, 2_000))
    router = make_router(lambda: None, lambda: live, _no_login)
    app = FastAPI()
    app.include_router(router)
    with TestClient(app) as c:
        assert c.get("/yachts").status_code == 503             # no match yet (no Tiger)
        router.yachts.rows = ref.build_rows(NOTABLE, {}, {DILBAR: {"mmsi": 319094900, "ship_type": 37},
                                                          AMADEA: {"mmsi": 538000001, "ship_type": 37}})
        router.yachts.last_seen = {319094900: 1_000, 538000001: 5_000}
        rows = {r["imo"]: r for r in c.get("/yachts").json()}
        assert set(rows[DILBAR]) == {"imo", "name", "length_m", "owner_reported", "owner_source_url", "sanctioned",
                                     "programs", "sanctions_source", "mmsi", "last_seen_ts", "status"}
        assert rows[DILBAR]["status"] == "ais" and rows[DILBAR]["last_seen_ts"] == 2_000
        assert rows[AMADEA]["status"] == "no_ais" and rows[AMADEA]["last_seen_ts"] == 5_000
        live.open_gap[319094900] = "g1"                         # an open gap: No AIS, even while still on the map
        assert {r["imo"]: r["status"] for r in c.get("/yachts").json()}[DILBAR] == "no_ais"
        router.yachts.last_seen = {}
        assert {r["imo"]: r["status"] for r in c.get("/yachts").json()}[AMADEA] == "not_seen"


async def _no_login() -> None:
    return None
