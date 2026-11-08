"""Route prediction tests on synthetic tracks: no real data, no database, no network.

    ml/.venv/bin/python -m pytest -q ml/route/tests
"""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

from ml.route import examples, features, geo
from ml.route.metrics import errors, report, skill_ci
from ml.route.model import RouteModel, conformal_q
from ml.route.train import time_split

T0 = 1_794_000_000_000          # 2026-11-08-ish, epoch ms


def ship_track(mmsi, lat0, lon0, course, sog_kn, hours, turn_deg_per_h=0.0, step_s=60, t0=T0, nav=0, cls="A"):
    n = int(hours * 3600 / step_s) + 1
    lat, lon, crs = [lat0], [lon0], [course]
    for _ in range(n - 1):
        c = crs[-1]
        la, lo = geo.destination(lat[-1], lon[-1], c, sog_kn * geo.KN_TO_MS * step_s)
        lat.append(float(la)); lon.append(float(lo)); crs.append((c + turn_deg_per_h * step_s / 3600) % 360)
    return pd.DataFrame({"mmsi": mmsi, "ts": t0 + np.arange(n) * step_s * 1000, "lat": lat, "lon": lon,
                         "sog_kn": np.float32(sog_kn), "cog_deg": np.array(crs, np.float32),
                         "heading_deg": np.array(crs, np.float32), "nav_status": np.float32(nav), "cls": cls,
                         "src": "test"})


def fleet(n_ships=60, hours=30, seed=0):
    """Ships that all turn to starboard at a steady rate: dead reckoning misses it, a learner can fix it."""
    rng = np.random.default_rng(seed)
    parts = []
    for k in range(n_ships):
        parts.append(ship_track(200_000_000 + k, 55 + rng.uniform(-1, 1), 10 + rng.uniform(-2, 2),
                                rng.uniform(0, 360), rng.uniform(6, 16), hours, turn_deg_per_h=20.0,
                                step_s=120, t0=T0 + int(rng.integers(0, 3600)) * 1000))
    tr = pd.concat(parts, ignore_index=True).sort_values(["mmsi", "ts"]).reset_index(drop=True)
    st = pd.DataFrame({"mmsi": tr["mmsi"].unique(), "ship_type": 70, "length": 150})
    return tr, st


def test_geo_roundtrip():
    la, lo = geo.destination(55.0, 10.0, 47.0, 12_345.0)
    assert geo.haversine_m(55.0, 10.0, la, lo) == pytest.approx(12_345.0, rel=1e-9)
    assert geo.bearing_deg(55.0, 10.0, la, lo) == pytest.approx(47.0, abs=1e-6)
    e, n = geo.enu_offset_m(55.0, 10.0, la, lo)
    la2, lo2 = geo.apply_enu_offset(55.0, 10.0, e, n)
    assert (float(la2), float(lo2)) == pytest.approx((float(la), float(lo)), abs=1e-9)
    assert geo.angle_diff_deg(10, 350) == pytest.approx(20)


def test_features_use_only_history():
    tr = ship_track(211_000_000, 55, 10, 90, 10, 6)
    as_of = int(tr["ts"].iloc[120])
    case = pd.DataFrame({"mmsi": [211_000_000], "as_of": [as_of]})
    full = features.track_features(tr, case)
    past = features.track_features(tr[tr["ts"] <= as_of], case)
    cols = features.feature_names()
    np.testing.assert_allclose(full[cols].to_numpy(float), past[cols].to_numpy(float), equal_nan=True)
    assert full["last_ts"].iat[0] == as_of and full["age_s"].iat[0] == 0


def test_features_vectorised_matches_single_ship():
    tr, st = fleet(5, 4)
    cases = tr.groupby("mmsi").nth([10, 50, 100])[["mmsi", "ts"]].rename(columns={"ts": "as_of"})
    allf = features.track_features(tr, cases, st).set_index(["mmsi", "as_of"]).sort_index()
    for m, g in cases.groupby("mmsi"):
        one = features.track_features(tr[tr["mmsi"] == m], g, st).set_index(["mmsi", "as_of"]).sort_index()
        cols = features.feature_names()
        np.testing.assert_allclose(allf.loc[one.index, cols].to_numpy(float), one[cols].to_numpy(float),
                                   rtol=1e-9, atol=1e-6, equal_nan=True)


def test_window_does_not_reach_previous_ship():
    a = ship_track(200_000_001, 55, 10, 0, 10, 2)
    b = ship_track(200_000_002, 56, 11, 90, 10, 2, t0=T0 + 5 * 3600_000)
    tr = pd.concat([a, b], ignore_index=True)
    f = features.track_features(tr, pd.DataFrame({"mmsi": [200_000_002], "as_of": [int(b["ts"].iloc[5])]}))
    assert f["n_fix_180"].iat[0] == 6           # only b's own six fixes, none of a's


def test_baseline_straight_and_stopped():
    tr = ship_track(212_000_000, 55, 10, 33, 12, 3)
    case = pd.DataFrame({"mmsi": [212_000_000], "as_of": [int(tr["ts"].iloc[0])]})
    f = features.track_features(tr, case)
    lat, lon = features.baseline_position(f, 3600)
    t_lat, t_lon = examples.truth_at(tr, np.array([212_000_000]), np.array([int(tr["ts"].iloc[0]) + 3_600_000]))
    # the test ship holds its compass course (a rhumb line); the baseline follows the great circle: 0.5% of 22 km
    assert geo.haversine_m(lat, lon, t_lat, t_lon)[0] < 0.005 * 12 * 1852
    moored = ship_track(213_000_000, 55, 10, 33, 3, 1, nav=5)
    f = features.track_features(moored, pd.DataFrame({"mmsi": [213_000_000], "as_of": [int(moored["ts"].iloc[0])]}))
    lat, lon = features.baseline_position(f, 3600)
    assert (float(lat[0]), float(lon[0])) == (55.0, 10.0)


def test_truth_at_interpolates_and_respects_tolerance():
    tr = pd.DataFrame({"mmsi": [1, 1, 2], "ts": [0, 240_000, 0], "lat": [0.0, 1.0, 5.0], "lon": [0.0, 2.0, 5.0]})
    lat, lon = examples.truth_at(tr, np.array([1, 1, 2, 2]), np.array([60_000, 1_000_000, 200_000, 400_000]))
    assert lat[0] == pytest.approx(0.25) and lon[0] == pytest.approx(0.5)
    assert np.isnan(lat[1])                   # 760 s after the last fix: beyond 5 min
    assert lat[2] == 5.0 and np.isnan(lat[3])


def test_conformal_quantile():
    s = np.arange(1, 101, dtype=float)
    assert conformal_q(s, 0.8) == 81.0        # ceil(101 * 0.8) = 81st smallest
    assert conformal_q(s[:3], 0.95) == 3.0


def test_time_split_embargo():
    tr, st = fleet(20, 20)
    ex = examples.build(tr, st, step_min=30, n_synthetic=50, horizons=(3600, 3 * 3600))
    train, test, start = time_split(ex, 0.3)
    assert (train["as_of"] + train["horizon_s"] * 1000 <= start).all()
    assert (test["as_of"] >= start).all()
    assert set(train["case_id"]).isdisjoint(set(test["case_id"]))


@pytest.fixture(scope="module")
def trained():
    tr, st = fleet(80, 30)
    ex = examples.build(tr, st, step_min=15, n_synthetic=300, horizons=(1800, 3600, 3 * 3600))
    train, test, _ = time_split(ex, 0.3)
    cfg = {"horizons_s": [1800, 3600, 10800], "n_estimators": 150, "num_leaves": 15, "min_child_samples": 20}
    model = RouteModel(cfg).fit(train)
    base = RouteModel({**cfg, "model": "baseline"}).fit(train)
    return model, base, test


def test_model_beats_baseline_on_turning_ships(trained):
    model, base, test = trained
    e = errors(test, model.predict(test), base.predict(test))
    rep = report(e, reps=100)
    for h in ("3600", "10800"):
        r = rep["by_horizon"][h]
        assert r["skill"] > 0.5 and r["skill_lo"] > 0, r
        assert 0.6 <= r["cover80"] <= 1.0 and r["cover95"] >= 0.85, r
    assert rep["reappear"]["synthetic_gap"]["all"]["skill"] > 0.3


def test_baseline_model_has_zero_skill_and_radii(trained):
    _, base, test = trained
    p = base.predict(test)
    e = errors(test, p, p)
    assert np.allclose(e["err_m"], e["base_err_m"])
    assert p["radius_m_80"].notna().all() and (p["radius_m_95"] >= p["radius_m_80"]).all()


def test_artifact_roundtrip_no_pickles(trained, tmp_path):
    model, _, test = trained
    model.save(tmp_path / "a")
    files = sorted(x.name for x in (tmp_path / "a").iterdir())
    assert "model.json" in files and not any(f.endswith((".pkl", ".pickle", ".joblib")) for f in files)
    spec = json.loads((tmp_path / "a" / "model.json").read_text())
    assert spec["target"] == "route" and spec["features"] == model.features and spec["horizons_s"] == model.horizons
    again = RouteModel.load(tmp_path / "a")
    pd.testing.assert_frame_equal(model.predict(test), again.predict(test))


def test_live_style_prediction_uses_age(trained):
    """A ship silent for 1 h asked for +1 h gets the same point as a fresh ship asked for +2 h from that fix."""
    model, _, test = trained
    row = test[test["truth"] == "fixed"].head(1).copy()
    a = model.predict(row.assign(age_s=3600.0, horizon_s=3600))
    b = model.predict(row.assign(age_s=0.0, horizon_s=7200))
    np.testing.assert_allclose(a.to_numpy(float), b.to_numpy(float))


def test_skill_ci_paired():
    rng = np.random.default_rng(0)
    base = rng.lognormal(8, 1, 2000)
    s, lo, hi = skill_ci(base * 0.7, base, reps=200)
    assert s == pytest.approx(0.3) and lo <= 0.3 <= hi and hi - lo < 1e-6   # paired: identical ratio every draw
