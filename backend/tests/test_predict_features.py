"""dvm.predict.features: geometry, baseline, and that features never read past as_of."""
import math

import pytest

from dvm.predict import features as F

T0 = 1_794_100_000_000
MIN = 60_000


def _track(n=60, sog=10.0, cog=90.0, step_ms=MIN, nav=0, lat0=55.0, lon0=11.0):
    rows, lat, lon = [], lat0, lon0
    for k in range(n):
        rows.append({"mmsi": 1, "ts": T0 + k * step_ms, "lat": lat, "lon": lon, "sog_kn": sog, "cog_deg": cog,
                     "heading_deg": cog, "nav_status": nav, "cls": "A"})
        lat, lon = F.destination(lat, lon, cog, sog * F.KN_MS * step_ms / 1000)
    return F.Track.from_rows(rows)


def test_destination_and_offsets_round_trip():
    lat, lon = F.destination(55.0, 11.0, 45.0, 10_000)
    assert F.haversine_m(55.0, 11.0, lat, lon) == pytest.approx(10_000, rel=1e-6)
    e, n = F.enu_offset(55.0, 11.0, lat, lon)
    assert e == pytest.approx(n, rel=1e-3) and math.hypot(e, n) == pytest.approx(10_000, rel=1e-6)
    lat2, lon2 = F.apply_offset(55.0, 11.0, e, n)
    assert F.haversine_m(lat, lon, lat2, lon2) < 0.01
    assert F.destination(0, 179.99, 90, 5000)[1] < -179   # crosses the antimeridian
    # Rhumb line: constant course. Due east keeps the latitude; the distance is the distance asked for.
    rl = F.rhumb_destination(55.0, 11.0, 90.0, 100_000)
    assert rl[0] == pytest.approx(55.0, abs=1e-9) and rl[1] == pytest.approx(11 + 100 / (111.195 * math.cos(math.radians(55))), rel=1e-4)
    rl = F.rhumb_destination(55.0, 11.0, 30.0, 50_000)
    assert F.haversine_m(55.0, 11.0, *rl) == pytest.approx(50_000, rel=1e-3)
    assert F.rhumb_destination(0, 179.99, 90, 5000)[1] < -179


def test_baseline_dead_reckons_and_stays_put_when_stopped():
    fix = {"lat": 55.0, "lon": 11.0, "sog_kn": 10.0, "cog_deg": 0.0, "heading_deg": 511, "nav_status": 0}
    lat, lon = F.baseline_point(fix, 3600)
    assert F.haversine_m(55.0, 11.0, lat, lon) == pytest.approx(18_520, rel=1e-6) and lat > 55.0
    for stopped in ({"nav_status": 1}, {"nav_status": 5}, {"sog_kn": 0.2}, {"sog_kn": None},
                    {"cog_deg": 360.0, "heading_deg": 511}):
        assert F.baseline_point({**fix, **stopped}, 3600) == (55.0, 11.0)
    assert F.baseline_point({**fix, "cog_deg": None, "heading_deg": 90}, 3600)[1] > 11.0   # heading fallback


def test_features_straight_track():
    t = _track()
    as_of = T0 + 59 * MIN
    f = F.features_at(t, as_of, {"ship_type": 70, "length_m": 120})
    assert set(f) == set(F.FEATURE_NAMES)
    assert f["sog_kn"] == 10.0 and f["ve_kn"] == pytest.approx(10.0) and abs(f["vn_kn"]) < 1e-9
    assert f["age_s"] == 0 and f["is_class_a"] == 1.0 and f["anchored"] == 0.0
    assert f["w30m_disp_kn"] == pytest.approx(10.0, rel=1e-3)
    assert f["w30m_straightness"] == pytest.approx(1.0, abs=1e-6)
    assert f["w30m_turn_deg"] == 0 and f["w2h_n"] == 60
    assert f["ship_type"] == 70 and f["length_m"] == 120 and f["draught_m"] is None
    assert len(F.vector(f)) == len(F.FEATURE_NAMES) and math.isnan(F.vector(f)[F.FEATURE_NAMES.index("draught_m")])


def test_features_never_read_after_as_of():
    t = _track()
    as_of = T0 + 30 * MIN + 1
    f = F.features_at(t, as_of)
    # Change every fix after as_of wildly: the features must not move.
    rows = [{"mmsi": 1, "ts": ts, "lat": la if ts <= as_of else 0.0, "lon": lo if ts <= as_of else 0.0,
             "sog_kn": s if ts <= as_of else 99.0, "cog_deg": c if ts <= as_of else 200.0, "heading_deg": c if ts <= as_of else 7,
             "nav_status": 0, "cls": "A"} for ts, la, lo, s, c in zip(t.ts, t.lat, t.lon, t.sog, t.cog)]
    f2 = F.features_at(F.Track.from_rows(rows), as_of)
    assert f == f2
    assert f["age_s"] == pytest.approx(0.001)


def test_features_none_without_recent_history_and_unsorted_refused():
    t = _track(n=3)
    assert F.features_at(t, T0 - 1) is None
    assert F.features_at(t, T0 + 7 * 3600 * 1000) is None
    with pytest.raises(ValueError):
        F.Track(1, [2, 1], [0, 0], [0, 0], [None] * 2, [None] * 2, [None] * 2, [None] * 2, ["A"] * 2)


def test_turning_track_and_from_columns_nan():
    rows, lat, lon = [], 55.0, 11.0
    for k in range(31):
        cog = (k * 3) % 360   # 3 degrees a minute to starboard
        rows.append({"mmsi": 2, "ts": T0 + k * MIN, "lat": lat, "lon": lon, "sog_kn": 8.0, "cog_deg": cog,
                     "heading_deg": None, "nav_status": None, "cls": "B"})
        lat, lon = F.destination(lat, lon, cog, 8 * F.KN_MS * 60)
    t = F.Track.from_columns(2, [r["ts"] for r in rows], [r["lat"] for r in rows], [r["lon"] for r in rows],
                             [r["sog_kn"] for r in rows], [r["cog_deg"] for r in rows], [float("nan")] * 31,
                             [float("nan")] * 31, ["B"] * 31)
    f = F.features_at(t, T0 + 30 * MIN)
    assert f["w30m_turn_deg"] == pytest.approx(87, abs=0.01)   # 29 steps inside (as_of - 30 min, as_of]
    assert f["w30m_turn_abs_deg_per_h"] == pytest.approx(180, rel=0.01)
    assert f["w30m_straightness"] < 0.95 and f["nav_status"] is None and f["is_class_a"] == 0.0
