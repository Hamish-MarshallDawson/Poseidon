"""Adapters against recorded responses (7 Nov 2026, trimmed). No network.

Fixtures: Digitraffic (Fintraffic, CC BY 4.0), Global Fishing Watch (CC BY-NC 4.0), Element 84 Earth Search
Sentinel-1 catalogue (Copernicus Sentinel data).
"""
import copy
import json
from datetime import date
from pathlib import Path

from dvm.models import Envelope
from dvm.sources import gfw, jobs, query, sentinel1
from dvm.sources.common import DAY_MS, REGIONS, day_ms, iso_ms
from dvm.sources.digitraffic import Dedup, normalise_digitraffic, unpack_eta

FX = Path(__file__).parent / "fixtures"
DAY = date(2026, 11, 3)
BOX = REGIONS["danish_straits"]
RECV = day_ms(DAY) + 4 * DAY_MS   # fetched four days after the day: counts as live


def dt_envs():
    for line in (FX / "digitraffic_mqtt.jsonl").read_text().splitlines():
        m = json.loads(line)
        yield Envelope(src="digitraffic", recv_ts=m["recv_ts"], raw={"topic": m["topic"], "payload": m["payload"]})


def gfw_fx():
    return json.loads((FX / "gfw_danish_2026-11-03.json").read_text())


# Digitraffic

def test_digitraffic_location_maps_to_position():
    recs = [r for e in dt_envs() for r in normalise_digitraffic(e)]
    pos = [r for r in recs if r.kind == "pos"]
    assert len(pos) == 6
    p = pos[0]
    assert p.mmsi == 230099950 and p.src == "digitraffic" and p.cls == "A" and p.ts_quality == "source"
    assert p.ts == 1794087052 * 1000 and p.recv_ts == 1794087052992
    assert (p.lat, p.lon, p.sog_kn, p.cog_deg, p.heading_deg, p.nav_status) == (59.943855, 24.13649, 14.0, 124.1, 124, 0)


def test_digitraffic_metadata_maps_to_static():
    st = [r for e in dt_envs() for r in normalise_digitraffic(e) if r.kind == "static"]
    assert len(st) == 3
    s = next(x for x in st if x.mmsi == 230938590)
    assert s.name == "UKKOPEKKA" and s.callsign == "OIOU" and s.imo == 6610132 and s.ship_type == 60
    assert s.type_group == "passenger" and s.draught_m == 3.0 and s.length_m == 33 and s.beam_m == 7
    assert s.destination == "FOR SALE" and s.mid == 230 and s.eta_utc is not None


def test_digitraffic_status_and_junk_are_ignored():
    assert normalise_digitraffic(Envelope(src="digitraffic", recv_ts=1, raw={"topic": "vessels-v2/status",
                                                                              "payload": {"updated": 1}})) == []
    bad = Envelope(src="digitraffic", recv_ts=1, raw={"topic": "vessels-v2/002300000/location",
                                                      "payload": {"lat": 60, "lon": 25, "time": 1}})
    assert normalise_digitraffic(bad) == []           # base station MMSI
    na = Envelope(src="digitraffic", recv_ts=10**12, raw={"topic": "vessels-v2/230099950/location",
                                                          "payload": {"lat": 91, "lon": 181, "time": 10**9}})
    assert normalise_digitraffic(na) == []


def test_digitraffic_na_values_and_late_flag():
    env = Envelope(src="digitraffic", recv_ts=1_000_000_000_000, raw={
        "topic": "vessels-v2/230099950/location",
        "payload": {"lat": 60, "lon": 25, "time": 999_999_000, "sog": 102.3, "cog": 360, "heading": 511, "navStat": 15}})
    (p,) = normalise_digitraffic(env)
    assert p.sog_kn is None and p.cog_deg is None and p.heading_deg is None and p.nav_status is None
    assert set(p.q) == {"sog_na", "cog_na", "hdg_na", "late"}


def test_eta_unpack_matches_06_example():
    assert unpack_eta(740352) == {"Month": 11, "Day": 9, "Hour": 16, "Minute": 0}
    assert unpack_eta(0) is None


def test_dedup_drops_exact_repeat_only():
    d = Dedup()
    pos = [r for e in dt_envs() for r in normalise_digitraffic(e) if r.kind == "pos"]
    assert all(d.keep(p) for p in pos)
    assert not d.keep(pos[0]) and d.dropped == 1


# Global Fishing Watch

def test_gfw_cells_are_anonymous_and_deterministic():
    body = gfw_fx()["presence_cells"]
    a = gfw.parse_cells(body, "ais_presence", None, DAY, RECV)
    b = gfw.parse_cells(body, "ais_presence", None, DAY, RECV + 999)
    assert len(a) == 4 and [o.id for o in a] == [o.id for o in b]
    o = a[0]
    assert o.mmsi is None and o.cell_deg == 0.01 and o.ts == day_ms(DAY) and o.end_ts == day_ms(DAY) + DAY_MS
    assert o.value == body["entries"][0]["public-global-presence:v5.0"][0]["hours"] and o.available_ts == RECV
    assert "cell_level" in o.q


def test_gfw_sar_cells_keep_match_state():
    fx = gfw_fx()
    m = gfw.parse_cells(fx["sar_cells_matched"], "sar_detection", True, DAY, RECV)
    u = gfw.parse_cells(fx["sar_cells_unmatched"], "sar_detection", False, DAY, RECV)
    assert all(o.matched is True for o in m) and all(o.matched is False for o in u)
    assert not {o.id for o in m} & {o.id for o in u}


def test_gfw_vessels_give_region_rows_and_identity():
    obs, statics = gfw.parse_vessels(gfw_fx()["presence_vessels"], "ais_presence", "danish_straits", BOX, DAY, RECV)
    assert len(obs) == 4 and all(o.bbox == BOX and o.lat is None and "region_level" in o.q for o in obs)
    assert statics and all(s.src == "gfw" and s.ts == day_ms(DAY) and s.recv_ts == RECV for s in statics)
    s = statics[0]
    assert s.flag_iso2 is None or len(s.flag_iso2) == 2
    assert s.mid == s.mmsi // 1_000_000


def test_gfw_backfilled_day_gets_estimated_available_time():
    late = day_ms(DAY) + 30 * DAY_MS
    (o, *_) = gfw.parse_cells(gfw_fx()["presence_cells"], "ais_presence", None, DAY, late)
    assert o.available_ts == day_ms(DAY) + DAY_MS + gfw.LAG_MS and "available_est" in o.q


def test_gfw_events_map_and_filter():
    fx = gfw_fx()
    obs, dropped = gfw.parse_events(fx["events_loitering"], "loitering", BOX, RECV, DAY)
    assert len(obs) + dropped == len(fx["events_loitering"]["entries"]) and obs
    e = fx["events_loitering"]["entries"][0]
    o = next(x for x in obs if x.id == f"gfw:loitering:{e['id']}")
    assert o.ts == iso_ms(e["start"]) and o.end_ts == iso_ms(e["end"]) and o.mmsi == int(e["vessel"]["ssvid"])
    assert o.value == e["loitering"]["totalTimeHours"]
    # An event far outside the region, and one from a buoy MMSI, are both dropped.
    far = copy.deepcopy(e)
    far["position"], far["boundingBox"] = {"lat": -30, "lon": 100}, [100, -30, 101, -29]
    buoy = copy.deepcopy(e)
    buoy["vessel"]["ssvid"] = "994046045"
    obs2, dropped2 = gfw.parse_events({"entries": [far, buoy]}, "loitering", BOX, RECV, DAY)
    assert obs2 == [] and dropped2 == 2


def test_gfw_gap_event_duration():
    e = copy.deepcopy(gfw_fx()["events_loitering"]["entries"][0])
    e["type"] = "gap"
    e["gap"] = {"durationHours": 13.5, "intentionalDisabling": True}
    (o,), _ = gfw.parse_events({"entries": [e]}, "gap", BOX, RECV, DAY)
    assert o.kind == "gap" and o.value == 13.5 and o.attrs["detail"]["intentionalDisabling"] is True


def test_gfw_fetch_day_with_fake_client():
    fx = gfw_fx()

    class Fake:
        def report(self, ds, bbox, day, *, vessels, matched=None):
            if ds == gfw.PRESENCE:
                return fx["presence_vessels" if vessels else "presence_cells"]
            if vessels:
                return fx["sar_vessels"]
            return fx["sar_cells_matched" if matched else "sar_cells_unmatched"]

        def events(self, ds, bbox, day):
            kind = next(k for k, v in gfw.EVENT_DATASETS.items() if v == ds)
            return fx[f"events_{kind}"]

    saved = {}
    obs, statics, info = gfw.fetch_day(Fake(), "danish_straits", BOX, DAY, RECV, lambda n, b: saved.setdefault(n, b))
    assert len(saved) == 8 and len({o.id for o in obs}) == len(obs)   # gaps come from gfw_gaps.py (#112)
    assert len({s.mmsi for s in statics}) == len(statics)
    assert {o.kind for o in obs} >= {"ais_presence", "sar_detection", "loitering", "port_visit"}


# Sentinel-1

def test_s1_items_map_to_scenes():
    items = json.loads((FX / "s1_search.json").read_text())["features"]
    obs = sentinel1.parse_items(items, recv_ts=1)
    assert len(obs) == 2
    o = obs[0]
    p = items[0]["properties"]
    assert o.kind == "radar_scene" and o.src == "sentinel1" and o.id == f"sentinel1:{items[0]['id']}"
    assert o.ts == iso_ms(p["start_datetime"]) and o.end_ts == iso_ms(p["end_datetime"])
    assert o.available_ts == iso_ms(p["created"]) and o.available_ts > o.ts
    assert o.geom["type"] == "Polygon" and o.bbox == tuple(items[0]["bbox"])
    assert o.attrs["platform"] == "sentinel-1d" and o.attrs["instrument_mode"] == "IW"


# Windows and the query

def test_needs_fetch_rules():
    spec = jobs.SPEC["gfw"]
    end = day_ms(DAY) + DAY_MS
    assert jobs.needs_fetch(None, end, end, spec)
    assert jobs.needs_fetch({"status": "error", "fetched_at": end}, end, end + 1, spec)
    recent = {"status": "ok", "fetched_at": end + DAY_MS}
    assert not jobs.needs_fetch(recent, end, end + DAY_MS + 60_000, spec)          # polled a minute ago
    assert jobs.needs_fetch(recent, end, end + DAY_MS + spec["refetch_ms"], spec)  # may have changed
    settled = {"status": "ok", "fetched_at": end + 8 * DAY_MS}
    assert not jobs.needs_fetch(settled, end, end + 100 * DAY_MS, spec)
    assert jobs.needs_fetch(settled, end, end + 100 * DAY_MS, spec, force=True)


def test_query_sql_filters():
    sql, args = query.observations_sql(kinds=["radar_scene"], bbox=(9, 54, 14, 58), start_ts=1, end_ts=2000,
                                       as_of=1500, limit=10)
    assert "available_ts <= $5" in sql and "kind = ANY($1::text[])" in sql and sql.endswith("LIMIT 10")
    assert "time >= to_timestamp($4)" in sql   # chunk pruning below the window
    assert args[:5] == [["radar_scene"], 2.0, 1, (1 - query.MAX_SPAN_MS) / 1000, 1500]
    sql, args = query.observations_sql()
    assert "WHERE" not in sql and args == []


def test_back_state_stops():
    st = jobs.BackState(date(2026, 11, 3), until=date(2026, 1, 1), empty_stop=3)
    for rows in (10, 0, 0):
        st.record(rows, False)
    assert st.stopped is None and st.day == date(2026, 10, 31)
    st.record(0, True)                        # settled earlier: not counted as empty
    assert st.stopped is None
    st.record(0, False)
    assert st.stopped and "3 consecutive empty days" in st.stopped
    st2 = jobs.BackState(date(2026, 1, 2), until=date(2026, 1, 1))
    st2.record(5, False)
    assert st2.stopped is None
    st2.record(5, False)
    assert st2.stopped == "reached --until 2026-01-01"
