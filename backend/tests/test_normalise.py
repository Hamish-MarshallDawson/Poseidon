from dvm.models import Envelope, PositionReport, VesselStatic
from dvm.normalise import normalise, parse_time_utc, rebuild_ts


def test_time_rebuild():   # the self-check from 06 section 6.1
    t = parse_time_utc("2026-11-07 16:15:01.234567 +0000 UTC")
    assert rebuild_ts(t, 1)[0] == t - 234                                  # same minute
    assert rebuild_ts(t, 59)[0] == (t - t % 60_000) - 60_000 + 59_000      # previous minute
    assert rebuild_ts(t, 61) == (t, "recv_only")
    assert parse_time_utc("2026-11-07 16:15:01.234567891 +0000 UTC") == t   # Go nanoseconds
    assert parse_time_utc("2026-11-07 16:15:01 +0000 UTC") == t - 234


def env(mmsi, lat=60.05, lon=28.41, name="EXAMPLE @@@", sec=1):
    return Envelope(src="aisstream", recv_ts=0, raw={
        "MessageType": "PositionReport",
        "MetaData": {"MMSI": mmsi, "ShipName": name, "time_utc": "2026-11-07 16:15:01.234567 +0000 UTC"},
        "Message": {"PositionReport": {"MessageID": 1, "UserID": mmsi, "Sog": 102.3, "Cog": 120.3, "TrueHeading": 511,
                                       "Latitude": lat, "Longitude": lon, "Timestamp": sec, "NavigationalStatus": 15,
                                       "Valid": True}}})


def test_position_and_mmsi_filter():
    recs = normalise(env(538003705))
    pos, static = recs
    assert isinstance(pos, PositionReport) and isinstance(static, VesselStatic)
    assert pos.ts == parse_time_utc("2026-11-07 16:15:01.234567 +0000 UTC") - 234 and pos.ts_quality == "rebuilt"
    assert (pos.sog_kn, pos.heading_deg, pos.nav_status, pos.cog_deg) == (None, None, None, 120.3)
    assert pos.q == ["sog_na", "hdg_na"] and pos.cls == "A"
    assert static.name == "EXAMPLE" and static.mid == 538
    for not_a_ship in (2_300_1234, 992_351_000, 111_232_506, 970_123_456, 812_345_678, 12_345):
        assert normalise(env(not_a_ship)) == [], not_a_ship
    assert [type(r) for r in normalise(env(538003705, lat=91, lon=181))] == [VesselStatic]   # n/a position dropped
