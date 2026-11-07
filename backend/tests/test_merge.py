"""FeedMerger over realistic AISStream and Digitraffic pairs (recorded Digitraffic payloads, AISStream shapes from
test_normalise.py)."""
import json
from datetime import datetime, timezone
from pathlib import Path

from dvm import merge
from dvm.merge import FeedMerger
from dvm.models import Envelope, PositionReport, VesselStatic
from dvm.normalise import normalise

FX = Path(__file__).parent / "sources" / "fixtures" / "digitraffic_mqtt.jsonl"
DT = {(j["topic"]): j for j in map(json.loads, FX.read_text().splitlines())}
LOC = DT["vessels-v2/230099950/location"]          # cog 124.1, heading 124, navStat 0, sog 14.0, time ...052
META = DT["vessels-v2/230938590/metadata"]         # UKKOPEKKA


def dt_env(j, recv_ts=None, **payload):
    return Envelope(src="digitraffic", recv_ts=recv_ts or j["recv_ts"],
                    raw={"topic": j["topic"], "payload": {**j["payload"], **payload}})


def utc(ms):
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%d %H:%M:%S.%f") + " +0000 UTC"


def ais_env(mmsi, lat, lon, fix_ms, lag_ms=1000, sog=102.3, cog=360, hdg=511, nav=15, ship="", mtype="PositionReport"):
    """AISStream position as the live feed sends it: second-of-minute Timestamp, MetaData.time_utc ~1 s later."""
    return Envelope(src="aisstream", recv_ts=fix_ms + lag_ms, raw={
        "MessageType": mtype,
        "MetaData": {"MMSI": mmsi, "ShipName": ship, "time_utc": utc(fix_ms + lag_ms)},
        "Message": {mtype: {"MessageID": 1, "UserID": mmsi, "Sog": sog, "Cog": cog, "TrueHeading": hdg,
                            "Latitude": lat, "Longitude": lon, "Timestamp": fix_ms // 1000 % 60,
                            "NavigationalStatus": nav, "Valid": True}}})


def recs(env):
    return normalise(env)


def pos(env) -> PositionReport:
    return next(r for r in normalise(env) if isinstance(r, PositionReport))


P = LOC["payload"]
FIX = P["time"] * 1000


def warm(m: FeedMerger, mmsi=230099950, t=FIX - 60_000):
    """Both feeds have heard this ship before, so its fixes are held for the other copy."""
    m.push(pos(ais_env(mmsi, 59.9, 24.0, t - 5000)), t - 4000)
    m.push(pos(dt_env(LOC, recv_ts=t - 3000, time=(t - 3000) // 1000, lat=59.91)), t - 3000)
    m.flush(t + 10_000)


def test_normalise_dispatches_digitraffic():
    [p] = normalise(dt_env(LOC))
    assert (p.src, p.mmsi, p.ts, p.ts_quality, p.heading_deg, p.nav_status) == (
        "digitraffic", 230099950, FIX, "source", 124, 0)
    [s] = normalise(dt_env(META))
    assert (s.src, s.name, s.callsign, s.imo) == ("digitraffic", "UKKOPEKKA", "OIOU", 6610132)
    assert normalise(dt_env(DT["vessels-v2/status"])) == []


def test_exact_duplicate_merges_and_fills_nulls():
    m = FeedMerger()
    warm(m)
    d = pos(dt_env(LOC))                                         # Digitraffic arrives first, ~0.5 s after the fix
    a = pos(ais_env(230099950, P["lat"], P["lon"], FIX))         # AISStream: sog/heading/nav n/a, cog 360 n/a
    assert (a.ts, a.ts_quality, a.sog_kn, a.heading_deg) == (FIX, "rebuilt", None, None)
    assert m.push(d, FIX + 500) == []                            # held for the other copy
    [out] = m.push(a, FIX + 1000)                                # emitted as soon as both have it
    assert out == d.model_copy(update={"msg_type": 1})          # only msg_type was missing, filled from AISStream
    assert m.flush(FIX + 10_000) == []
    assert m.stats["merged"] == 1 and m.stats["pos_in"] == {"aisstream": 2, "digitraffic": 2}


def test_aisstream_first_gets_digitraffic_detail_and_timestamp():
    m = FeedMerger()
    warm(m)
    a = pos(ais_env(230099950, P["lat"], P["lon"], FIX - 1000))  # rebuilt ts 1 s off from Digitraffic's time
    d = pos(dt_env(LOC))
    assert d.ts - a.ts == 1000
    assert m.push(a, FIX) == []
    [out] = m.push(d, FIX + 600)
    assert out.src == "aisstream"                                # first arrival keeps src
    assert (out.ts, out.ts_quality) == (FIX, "source")           # better timestamp
    assert (out.sog_kn, out.cog_deg, out.heading_deg, out.nav_status) == (14.0, 124.1, 124, 0)
    assert out.q == [] and out.msg_type == 1
    assert m.stats["filled_fields"] == 5


def test_two_fixes_one_second_apart_both_kept():
    """A ship at 14 kn moves ~7 m in 1 s: round(lat, 4) would often call that the same place, MATCH_DEG does not."""
    m = FeedMerger()
    warm(m)
    d = pos(dt_env(LOC))
    lat2 = P["lat"] - 0.00004                                    # 1 s later along cog 124 at 14 kn
    lon2 = P["lon"] + 0.00011
    a = pos(ais_env(230099950, lat2, lon2, FIX + 1000))
    assert m.push(d, FIX + 500) == []
    assert m.push(a, FIX + 2000) == []                           # different fix: held on its own
    out = m.flush(FIX + 10_000)
    assert [r.src for r in out] == ["digitraffic", "aisstream"] and m.stats["merged"] == 0


def test_same_source_repeat_dropped_and_late_copy_dropped():
    m = FeedMerger()
    warm(m)
    d = pos(dt_env(LOC))
    m.push(d, FIX + 500)
    assert m.push(d, FIX + 600) == []                            # QoS 0 redelivery
    assert m.stats["dup_dropped"] == 1
    [out] = m.flush(FIX + 500 + merge.HOLD_MS)
    assert out == d
    late = pos(ais_env(230099950, P["lat"], P["lon"], FIX, lag_ms=4000))
    assert m.push(late, FIX + 4000) == []                        # copy after the hold: not stored twice
    assert m.stats["late_dup_dropped"] == 1 and m.stats["pos_out"] == 3


def test_no_hold_without_overlap_and_class_b_never_merged():
    m = FeedMerger()
    [a] = m.push(pos(ais_env(230099950, P["lat"], P["lon"], FIX)), FIX + 1000)   # Digitraffic never heard it
    assert a.src == "aisstream"
    warm(m, mmsi=244123456)
    b = pos(ais_env(244123456, 59.5, 24.5, FIX, mtype="StandardClassBPositionReport"))
    assert b.cls == "B" and m.push(b, FIX + 1000) == [b]         # Class B: straight through


def test_hold_bounded_and_deterministic():
    def run():
        m, out = FeedMerger(), []
        warm(m)
        for i in range(50):                                       # one fix a second, Digitraffic only
            t = FIX + i * 1000
            out += m.push(pos(dt_env(LOC, recv_ts=t + 500, time=t // 1000, lat=P["lat"] + i * 1e-4)), t + 500)
            assert m.stats["held"] <= merge.HOLD_MS // 1000 + 1
            out += m.flush(t + 1000)
        return out, m.stats
    o1, s1 = run()
    o2, s2 = run()
    assert o1 == o2 and s1 == s2 and len(o1) >= 48


def test_statics_partials_merge_unchanged_suppressed_changed_emitted():
    m = FeedMerger()
    mmsi = 230938590
    name_only = [r for r in recs(ais_env(mmsi, 60.1, 24.9, FIX, ship="UKKOPEKKA")) if isinstance(r, VesselStatic)][0]
    assert name_only.callsign is None
    [first] = m.push(name_only, FIX + 1000)                      # first sighting always emits
    assert first.name == "UKKOPEKKA"
    assert m.push(name_only, FIX + 2000) == []                   # the name repeats with every position
    [full] = m.push(recs(dt_env(META))[0], FIX + 3000)           # Digitraffic adds callsign, imo, voyage
    assert (full.name, full.callsign, full.imo, full.destination, full.src) == (
        "UKKOPEKKA", "OIOU", 6610132, "FOR SALE", "digitraffic")
    assert m.push(recs(dt_env(META))[0], FIX + 360_000) == []    # 6-minute rebroadcast, unchanged
    assert m.push(name_only, FIX + 361_000) == []
    [moved] = m.push(recs(dt_env(META, destination="HELSINKI"))[0], FIX + 720_000)
    assert moved.destination == "HELSINKI" and moved.callsign == "OIOU"   # still the full identity
    assert m.stats["static_out"] == 3 and m.stats["static_unchanged"] == 3


def test_statics_no_flip_flop_between_sources():
    m = FeedMerger()
    mmsi = 230938590
    ais = [r for r in recs(ais_env(mmsi, 60.1, 24.9, FIX, ship="UKKOPEKK")) if isinstance(r, VesselStatic)][0]
    dt = recs(dt_env(META))[0]
    assert len(m.push(ais, 0)) == 1 and len(m.push(dt, 1)) == 1   # the newer source's spelling wins once
    for t in range(2, 10):
        assert m.push(ais if t % 2 else dt, t) == []


def test_two_digitraffic_fixes_in_one_second_each_merge_with_their_copy():
    """Seen live (mmsi 244995000, 9.5 kn): two Digitraffic fixes with the same `time`, 4 m apart, same 06 key."""
    m, mmsi, t = FeedMerger(), 244995000, 1794090362_000
    warm(m, mmsi=mmsi, t=t - 60_000)
    d1 = pos(Envelope(src="digitraffic", recv_ts=t + 177, raw={
        "topic": f"vessels-v2/{mmsi}/location", "payload": {**P, "lat": 63.919878, "lon": 21.63307, "time": t // 1000}}))
    d2 = pos(Envelope(src="digitraffic", recv_ts=t + 753, raw={
        "topic": f"vessels-v2/{mmsi}/location", "payload": {**P, "lat": 63.919913, "lon": 21.633127, "time": t // 1000}}))
    a2 = pos(ais_env(mmsi, 63.919913, 21.633127, t - 1000, lag_ms=2087))   # rebuilt 1 s early
    assert m.push(d1, t + 177) == [] and m.push(d2, t + 753) == []
    [out] = m.push(a2, t + 1087)
    assert (out.lat, out.src, out.ts) == (63.919913, "digitraffic", t) and m.stats["dup_dropped"] == 0
    assert [r.lat for r in m.flush(t + 10_000)] == [63.919878]
