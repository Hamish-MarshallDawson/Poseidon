"""Route prediction tests on synthetic tracks: no real data, no database, no network.

    ml/.venv/bin/python -m pytest -q ml/route/tests
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[3]))   # repo root, so `import ml` works

from ml.core.registry import open_registry, save_artifact  # noqa: E402
from ml.route import examples, geo  # noqa: E402
from ml.route.metrics import paired, report, score, skill_ci  # noqa: E402
from ml.route.model import RouteBaseline, RouteLGBM, conformal_q  # noqa: E402
from ml.route.target import SPEC  # noqa: E402
from ml.route.train import time_split  # noqa: E402

from dvm.predict import artifact as backend_artifact  # noqa: E402
from dvm.predict import features as F  # noqa: E402

T0 = 1_794_000_000_000
HS = (1800, 3600, 10800)


def ship_track(mmsi, lat0, lon0, course, sog_kn, hours, turn_deg_per_h=0.0, step_s=60, t0=T0, nav=0, cls="A"):
    n = int(hours * 3600 / step_s) + 1
    lat, lon, crs = [lat0], [lon0], [course]
    for _ in range(n - 1):
        la, lo = geo.destination(lat[-1], lon[-1], crs[-1], sog_kn * geo.KN_TO_MS * step_s)
        lat.append(float(la)); lon.append(float(lo)); crs.append((crs[-1] + turn_deg_per_h * step_s / 3600) % 360)
    return pd.DataFrame({"mmsi": mmsi, "ts": t0 + np.arange(n) * step_s * 1000, "lat": lat, "lon": lon,
                         "sog_kn": np.float32(sog_kn), "cog_deg": np.array(crs, np.float32),
                         "heading_deg": np.array(crs, np.float32), "nav_status": np.float32(nav), "cls": cls,
                         "src": "test"})


def fleet(n_ships=60, hours=30, seed=0):
    """Ships that all turn to starboard at a steady rate: dead reckoning misses it, a learner can fix it."""
    rng = np.random.default_rng(seed)
    parts = [ship_track(200_000_000 + k, 55 + rng.uniform(-1, 1), 10 + rng.uniform(-2, 2), rng.uniform(0, 360),
                        rng.uniform(6, 16), hours, turn_deg_per_h=20.0, step_s=120,
                        t0=T0 + int(rng.integers(0, 3600)) * 1000) for k in range(n_ships)]
    tr = pd.concat(parts, ignore_index=True).sort_values(["mmsi", "ts"]).reset_index(drop=True)
    st = pd.DataFrame({"mmsi": tr["mmsi"].unique(), "ship_type": 70, "length": 150.0, "draught": 7.5})
    return tr, st


def test_geo_roundtrip():
    la, lo = geo.destination(55.0, 10.0, 47.0, 12_345.0)
    assert geo.haversine_m(55.0, 10.0, la, lo) == pytest.approx(12_345.0, rel=1e-9)
    e, n = geo.enu_offset_m(55.0, 10.0, la, lo)
    assert (float(e), float(n)) == pytest.approx(F.enu_offset(55.0, 10.0, float(la), float(lo)), abs=1e-6)
    la2, lo2 = geo.apply_enu_offset(55.0, 10.0, e, n)
    assert (float(la2), float(lo2)) == pytest.approx((float(la), float(lo)), abs=1e-9)


def test_features_are_the_backends():
    """compute_features (parallel, by ship) returns exactly features_at and baseline_point of dvm.predict."""
    tr, st = fleet(6, 8)
    cases = examples.grid_cases(tr, 30)
    par = examples.compute_features(tr, cases, st, HS, workers=3).set_index(["mmsi", "as_of"]).sort_index()
    ser = examples.compute_features(tr, cases, st, HS, workers=1).set_index(["mmsi", "as_of"]).sort_index()
    pd.testing.assert_frame_equal(par, ser)
    g = tr[tr["mmsi"] == 200_000_003]
    T = F.Track.from_rows(g.to_dict("records"))
    static = {"ship_type": 70.0, "length_m": 150.0, "draught_m": 7.5}
    for a in cases[cases["mmsi"] == 200_000_003]["as_of"].head(5):
        want = F.features_at(T, int(a), static)
        got = par.loc[(200_000_003, int(a))]
        for k in F.FEATURE_NAMES:
            assert (want[k] is None and pd.isna(got[k])) or got[k] == pytest.approx(want[k], abs=1e-9), k
        bl = F.baseline_point(T.last_fix(int(a)), 3600)
        assert (got["base_lat_3600"], got["base_lon_3600"]) == pytest.approx(bl, abs=1e-12)


def test_features_use_only_history():
    tr = ship_track(211_000_000, 55, 10, 90, 10, 6)
    a = int(tr["ts"].iloc[120])
    case = pd.DataFrame({"mmsi": [211_000_000], "as_of": [a]})
    full = examples.compute_features(tr, case, None, HS, workers=1)
    past = examples.compute_features(tr[tr["ts"] <= a], case, None, HS, workers=1)
    pd.testing.assert_frame_equal(full, past)


def test_dma_ship_types_map_to_ais_codes():
    st = examples.normalise_statics(pd.DataFrame({"mmsi": [1, 2, 3], "ship_type": ["Cargo", "Sailing", "Reserved"],
                                                  "length": [100.0, 0.0, 12.0], "draught": [5.0, 1.0, None]}))
    assert st["ship_type"].tolist()[:2] == [70, 36] and np.isnan(st["ship_type"].iloc[2])
    assert np.isnan(st["length_m"].iloc[1])
    assert [examples.type_group(x) for x in st["ship_type"]] == ["cargo", "pleasure", "unknown"]


def test_truth_at_interpolates_and_respects_tolerance():
    tr = pd.DataFrame({"mmsi": [1, 1, 2], "ts": [0, 240_000, 0], "lat": [0.0, 1.0, 5.0], "lon": [0.0, 2.0, 5.0]})
    lat, lon = examples.truth_at(tr, [1, 1, 2, 2], [60_000, 1_000_000, 200_000, 400_000])
    assert lat[0] == pytest.approx(0.25) and lon[0] == pytest.approx(0.5)
    assert np.isnan(lat[1])                   # 760 s after the last fix: beyond 5 min
    assert lat[2] == 5.0 and np.isnan(lat[3])


def test_conformal_quantile():
    s = np.arange(1, 101, dtype=float)
    assert conformal_q(s, 0.8) == 81.0        # ceil(101 * 0.8) = 81st smallest
    assert conformal_q(s[:3], 0.95) == 3.0


def test_real_gaps_hide_the_dark_stretch():
    a = ship_track(219_000_001, 55, 10, 90, 10, 6)
    tr = a[(a["ts"] < T0 + 3600_000) | (a["ts"] >= T0 + 3 * 3600_000)]     # dark 1 h to 3 h
    start = int(tr[tr["ts"] < T0 + 3600_000]["ts"].max())
    end = int(tr[tr["ts"] >= T0 + 3 * 3600_000]["ts"].min())
    last, nxt = tr[tr["ts"] == start].iloc[0], tr[tr["ts"] == end].iloc[0]
    gaps = pd.DataFrame([{"id": f"gap-219000001-{start}", "version": 2, "mmsi": 219000001, "state": "closed",
                          "start_ts": start, "end_ts": end, "next_lat": nxt["lat"], "next_lon": nxt["lon"],
                          "coverage_flag": "deliberate_candidate", "last_lat": last["lat"], "last_lon": last["lon"]}])
    rg = examples.real_gap_cases(gaps, tr, None, (1800, 3600, 3 * 3600), workers=1)
    assert len(rg) == 1 and rg["reap_kind"].iat[0] == "real" and rg["reap_s"].iat[0] == (end - start) // 1000
    assert np.isnan(rg["truth_lat_1800"].iat[0]) and np.isnan(rg["truth_lat_3600"].iat[0])
    assert not np.isnan(rg["truth_lat_10800"].iat[0])          # heard again by then


def test_time_split_embargo():
    tr, st = fleet(20, 20)
    ex = examples.build(tr, st, step_min=30, n_synthetic=50, horizons=HS, workers=2)
    train, test, start = time_split(ex, 0.3, HS)
    for h in HS:
        t = train[train[f"truth_lat_{h}"].notna()]
        assert (t["as_of"] + h * 1000 <= start).all()
    assert (test["as_of"] >= start).all() and set(train["case_id"]).isdisjoint(test["case_id"])


@pytest.fixture(scope="module")
def trained():
    tr, st = fleet(80, 30)
    ex = examples.build(tr, st, step_min=15, n_synthetic=300, horizons=HS, workers=4)
    train, test, _ = time_split(ex, 0.3, HS)
    cfg = {"horizons_s": list(HS), "n_estimators": 150, "num_leaves": 15, "min_child_samples": 20}
    return RouteLGBM().fit(train, cfg), RouteBaseline().fit(train, {**cfg, "model": "baseline"}), test, ex


def test_model_beats_baseline_on_turning_ships(trained):
    from ml.route.metrics import reappear_frame
    model, base, test, _ = trained
    rep = report(paired(score(test, model.predict(test)), score(test, base.predict(test))),
                 reappear_frame(model, base, test), reps=100)
    for h in ("3600", "10800"):
        r = rep["by_horizon"][h]
        assert r["skill"] > 0.5 and r["skill_lo"] > 0, r
        assert 0.65 <= r["cover80"] <= 1.0 and r["cover95"] >= 0.85, r
    assert rep["reappear"]["synthetic"]["all"]["skill"] > 0.3


def test_predict_at_matches_predict_at_trained_horizons(trained):
    model, _, test, _ = trained
    rows = test.head(20)
    p = model.predict(rows)
    q = model.predict_at(rows, np.full(len(rows), 3600.0))
    np.testing.assert_allclose(p[p["horizon_s"] == 3600][["pred_lat", "pred_lon", "radius_m_80"]].to_numpy(),
                               q[["pred_lat", "pred_lon", "radius_m_80"]].to_numpy(), rtol=0, atol=1e-9)


def test_backend_loads_the_artifact_and_predicts_the_same(trained, tmp_path):
    """The live predictor's own loader reads the artifact and gives the same point and radii as training."""
    model, base, test, _ = trained
    # 1800, 3600 and 10800 s are trained; the backend gets the contract's horizons among them
    d = save_artifact(model, tmp_path / "route-test", {"version": "route-test", "data_hash": "x", "config": model.cfg})
    files = sorted(p.name for p in d.iterdir())
    assert "model.json" in files and not any(f.endswith((".pkl", ".pickle", ".joblib")) for f in files)
    live = backend_artifact.load(d)
    assert live.kind == "lightgbm" and live.version == "route-test" and live.horizons_s == (3600, 10800)
    rows = test.head(25)
    mine = model.predict(rows).set_index(["case_id", "horizon_s"])
    tr, st = fleet(80, 30)
    for r in rows.itertuples(index=False):
        g = tr[(tr["mmsi"] == r.mmsi)]
        T = F.Track.from_rows(g.to_dict("records"))
        fix = T.last_fix(int(r.as_of))
        feats = F.features_at(T, int(r.as_of), {"ship_type": 70.0, "length_m": 150.0, "draught_m": 7.5})
        for p in live.predict(fix, feats):
            m = mine.loc[(r.case_id, p["horizon_s"])]
            assert (p["lat"], p["lon"]) == pytest.approx((m["pred_lat"], m["pred_lon"]), abs=1e-7)
            assert p["radius_m_80"] == pytest.approx(m["radius_m_80"], abs=0.1)
            assert p["radius_m_95"] == pytest.approx(m["radius_m_95"], abs=0.1)
    again = RouteLGBM.load(d)
    pd.testing.assert_frame_equal(model.predict(rows), again.predict(rows))
    b = save_artifact(base, tmp_path / "route-base", {"version": "route-base"})
    assert backend_artifact.load(b).kind == "baseline"


def test_loop_runs_route_end_to_end(trained, tmp_path):
    """ml.core.run with the route SPEC: held-out freeze, folds, baseline, decision, artifact."""
    from ml.core.run import run_one
    _, _, _, ex = trained
    cfg = {**SPEC.default_config, "n_estimators": 80, "num_leaves": 15, "min_child_samples": 20}
    spec = type(SPEC)()
    spec.horizons_s, spec.primary_horizons_s = list(HS), [3600, 10800]
    # the synthetic fleet has no GPS noise, so errors are tiny; the leakage check rightly flags that (below)
    assert spec.sanity({"1800": {"n": 500, "median_m": 13.0}})
    spec.sanity = lambda summary: []
    row = run_one(spec, cfg, reg=open_registry(str(tmp_path / "reg")), examples=ex, n_folds=2,
                  artifacts=tmp_path / "art", log=lambda *a: None)
    m = row["metrics"]
    assert set(m["summary"]) >= {"3600", "10800"} and m["skill"]["3600"]["skill"] > 0.3, m["skill"]
    spec_json = json.loads((Path(row["artifact"]) / "model.json").read_text())
    assert spec_json["target"] == "route" and spec_json["heads"]
    assert row["status"] == "champion", m["decision"]["reasons"]
    assert backend_artifact.load(Path(row["artifact"])).version == row["run_id"]


def test_skill_ci_paired():
    base = np.random.default_rng(0).lognormal(8, 1, 2000)
    s, lo, hi = skill_ci(base * 0.7, base, reps=200)
    assert s == pytest.approx(0.3) and lo <= 0.3 <= hi and hi - lo < 1e-6


def test_schema_accepts_default_and_dry_runs():
    import jsonschema
    jsonschema.validate(SPEC.default_config, SPEC.config_schema)
    for p in SPEC.dry_run_proposals:
        jsonschema.validate(p["config"], SPEC.config_schema)
