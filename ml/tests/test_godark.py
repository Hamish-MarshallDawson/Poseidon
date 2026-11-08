"""Go-dark target (#121): labels, population, censoring, no look-ahead, detector replay, models and artifact."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd
import pytest

import ml  # noqa: F401
from ml.godark import dataset as D
from ml.godark import replay as R
from ml.godark.target import SPEC, Baseline, GlobalRate, Lgbm, label_col

MIN = 60_000
T0 = 1_794_000_000_000 // (10 * MIN) * (10 * MIN)


def track(mmsi, t_from, t_to, lat0, lon0, sog=10.0, cog=90.0, nav=0, step=MIN, cls="A", src="aisstream", drift=True):
    rows = []
    for k, t in enumerate(range(t_from, t_to, step)):
        rows.append({"mmsi": mmsi, "ts": t, "recv_ts": t + 1000, "lat": lat0, "lon": lon0 + drift * k * 0.003 * step / MIN,   # about 10 kn
                     "sog_kn": sog, "cog_deg": cog, "heading_deg": cog, "nav_status": nav, "cls": cls, "src": src})
    return rows


def gap(mmsi, start_ts, flag, detected_at=None, version=1, lat=55.0, lon=11.0):
    return {"id": f"gap-{mmsi}-{start_ts}", "version": version, "mmsi": mmsi, "start_ts": start_ts,
            "detected_at": detected_at or start_ts + 31 * MIN, "coverage_flag": flag, "last_lat": lat, "last_lon": lon}


def statics(mmsis):
    return pd.DataFrame([{"mmsi": m, "ts": T0 - 3600_000, "recv_ts": T0, "imo": None, "ship_type": 70,
                          "type_group": "cargo", "length_m": 120, "draught_m": 7.0, "flag_iso2": "DK", "src": "x"}
                         for m in mmsis])


# ---------------------------------------------------------------- labels and population

def test_labels_window_censoring_and_population():
    end = T0 + 6 * 3600_000
    pos = pd.DataFrame(
        track(1, T0, T0 + 4 * 3600_000, 55.0, 11.0)                        # silent from T0+4h
        + track(2, T0, end, 55.01, 11.0)                                   # always heard
        + track(3, T0, end, 55.02, 11.0, sog=0.0, nav=5))                  # moored: never in the population
    last1 = T0 + 4 * 3600_000 - MIN
    versions = pd.DataFrame([gap(1, last1, "deliberate_candidate")])
    rows = D.base_rows(D.prepare_positions(pos), D.grid_times(T0, end, []))
    assert set(rows["mmsi"]) == {1, 2}
    rows = D.add_labels(rows, versions, end)
    r1 = rows[rows.mmsi == 1].set_index("made_at")
    col1 = "y_deliberate_candidate_1h"
    # made_at 3h10: the gap starts 49 min later, inside 1 h
    assert r1.loc[T0 + 190 * MIN, col1] == 1.0
    # made_at 2h50: starts 69 min later, outside 1 h but inside 6 h
    assert r1.loc[T0 + 170 * MIN, col1] == 0.0
    # 6 h labels need made_at + 6 h + DETECT_MS <= end: nothing is labelled here, and censored is NaN, not 0
    assert rows["y_deliberate_candidate_6h"].isna().all()
    assert rows["y_unknown_1h"].fillna(0).eq(0).all()
    assert rows.loc[rows.mmsi == 1, "y_any_1h"].max() == 1.0
    # censoring for 1 h: made_at > end - 1 h - DETECT_MS is NaN
    late = rows[rows.made_at > end - 3600_000 - D.DETECT_MS]
    assert len(late) and late[col1].isna().all()
    # ship 1 after its last fix is no longer in the population (not heard within ACTIVE_MS)
    assert r1.index.max() <= last1 + D.ACTIVE_MS


def test_grid_skips_warmup_and_after_stalls():
    g = D.grid_times(T0, T0 + 8 * 3600_000, [(T0 + 4 * 3600_000, T0 + 5 * 3600_000)])
    assert g.min() >= T0 + D.WARMUP_MS
    assert not ((g >= T0 + 4 * 3600_000) & (g < T0 + 5 * 3600_000 + D.POST_STALL_MS)).any()


def test_features_do_not_read_the_future():
    end = T0 + 5 * 3600_000
    base = track(1, T0, end, 55.0, 11.0) + track(2, T0, end, 55.01, 11.0)
    later = track(1, end, end + 3600_000, 55.0, 12.5, sog=20, cog=10)  # different future behaviour
    st = statics([1, 2])
    a = D.build(pd.DataFrame(base), pd.DataFrame([gap(2, end, "unknown")]), st, [], T0, end, workers=1)
    b = D.build(pd.DataFrame(base + later), pd.DataFrame([gap(2, end, "unknown")]), st, [], T0, end + 3600_000,
                workers=1)
    feats = [c for c in a.columns if not c.startswith("y_")]
    m = a.merge(b, on="case_id", suffixes=("", "_b"))
    assert len(m) == len(a)
    for c in feats:
        if c in ("case_id",):
            continue
        x, y = m[c], m[f"{c}_b"]
        same = (x == y) | (x.isna() & y.isna())
        assert same.all(), c


def test_past_gap_features_use_only_detected_gaps():
    end = T0 + 6 * 3600_000
    pos = pd.DataFrame(track(1, T0, end, 55.0, 11.0) + track(2, T0, end, 55.0, 11.2))
    # ship 2 had a deliberate gap detected at T0+3h (a short one; positions continue)
    v = pd.DataFrame([gap(2, T0 + 150 * MIN, "deliberate_candidate", detected_at=T0 + 180 * MIN, lat=55.0,
                          lon=11.2)])
    ex = D.build(pos, v, statics([1, 2]), [], T0, end, workers=1)
    s2 = ex[ex.mmsi == 2].set_index("as_of")
    assert s2.loc[T0 + 170 * MIN, "ship_gaps_delib"] == 0
    assert s2.loc[T0 + 180 * MIN, "ship_gaps_delib"] == 1
    s1 = ex[ex.mmsi == 1].set_index("as_of")
    assert s1.loc[T0 + 170 * MIN, "area_gaps_6h_delib"] == 0
    assert s1.loc[T0 + 190 * MIN, "area_gaps_6h_delib"] == 1
    assert (ex["type_group"] == "cargo").all()


# ---------------------------------------------------------------- replay

def test_replay_finds_a_deliberate_gap_and_notes_outages():
    end = T0 + 3 * 3600_000
    rows = track(9, T0, T0 + 3600_000, 55.0, 11.0, step=10_000)
    for m in range(10, 15):   # neighbours within 20 km keep reporting (holding position, so they stay near)
        rows += track(m, T0, end, 55.0 + (m - 10) * 0.01, 11.0, step=10_000, drift=False)
    df, stats = R.replay(pd.DataFrame(rows), known_stalls=[])
    lat = R.latest(df)
    g = lat[lat.mmsi == 9]
    assert len(g) == 1 and g.iloc[0]["coverage_flag"] == "deliberate_candidate"
    assert g.iloc[0]["start_ts"] == T0 + 3600_000 - 10_000
    assert R.find_stalls(np.array([0, 10_000, 100_000, 110_000])) == [(10_000, 100_000)]


def test_replay_marks_silence_inside_our_outage_as_own_stall():
    rows = []
    for m in range(20, 26):
        rows += track(m, T0, T0 + 3600_000, 55.0 + (m - 20) * 0.01, 11.0, step=10_000)
        rows += track(m, T0 + 3 * 3600_000, T0 + 4 * 3600_000, 55.0 + (m - 20) * 0.01, 11.5, step=10_000)
    df, stats = R.replay(pd.DataFrame(rows), known_stalls=[])
    assert len(stats["stalls"]) == 1
    # every ship went quiet only because nothing at all came in: no gap opens during the outage (no ticks), and
    # when data resumes the stall is noted before the ships are ticked, so nothing is deliberate
    lat = R.latest(df) if len(df) else pd.DataFrame(columns=["coverage_flag"])
    assert not (lat["coverage_flag"] == "deliberate_candidate").any()


# ---------------------------------------------------------------- models and artifact

def synthetic_examples(n_ships=300, steps=40, seed=1):
    rng = np.random.default_rng(seed)
    rows = []
    for s in range(n_ships):
        risky = s % 5 == 0
        for k in range(steps):
            t = T0 + k * 10 * MIN
            age = rng.uniform(0, 600)
            p1 = 0.25 if risky else 0.02
            row = {"case_id": f"{s}-{t}", "mmsi": 1000 + s, "as_of": t, "area": 5501 if risky else 5502,
                   "type_group": "fishing" if risky else "cargo", "flag_iso2": "DK", "src_digitraffic": 0.0,
                   "sog_kn": rng.uniform(1, 15), "age_s": age, "w2h_rate_per_min": 0.2 if risky else 1.0}
            for f in D.CONTEXT_FEATURES:
                row.setdefault(f, 0.0)
            y1 = float(rng.random() < p1)
            row[label_col(3600)] = y1
            row[label_col(21600)] = float(y1 or rng.random() < p1 * 2)
            row[label_col(86400)] = np.nan
            rows.append(row)
    return pd.DataFrame(rows)


def test_models_learn_and_baseline_backs_off():
    ex = synthetic_examples()
    tr, te = ex[ex.as_of < T0 + 30 * 10 * MIN], ex[ex.as_of >= T0 + 30 * 10 * MIN]
    b = Baseline().fit(tr, {})
    g = GlobalRate().fit(tr, {})
    m = Lgbm().fit(tr, {**SPEC.default_config, "n_estimators": 50, "min_child_samples": 20})
    assert "86400" not in b.table and 86400 not in m.boosters   # no labels, no head
    sc = {name: SPEC.score(te, mod.predict(te)) for name, mod in (("b", b), ("g", g), ("m", m))}
    s = {k: SPEC.summarise(v) for k, v in sc.items()}
    assert s["m"]["3600"]["log_loss"] < s["g"]["3600"]["log_loss"]
    assert s["b"]["3600"]["log_loss"] < s["g"]["3600"]["log_loss"]
    assert set(sc["m"]["horizon_s"]) == {3600, 21600}
    cal = SPEC.calibration(sc["m"])
    assert all(c["value"] < 0.05 for c in cal), cal
    # unseen area and type fall back to the global rate
    odd = te.head(1).assign(area=9999, type_group="other")
    assert abs(b.predict(odd).query("horizon_s == 3600")["p"].iloc[0] - b.table["3600"]["global"]) < 1e-12


def test_artifact_round_trip_and_backend_format(tmp_path):
    from ml.core.registry import save_artifact
    ex = synthetic_examples()
    # the deployable model uses shared track features only; give it two of them with signal
    from dvm.predict import features as F
    for f in F.FEATURE_NAMES:
        if f not in ex:
            ex[f] = np.nan
    m = Lgbm().fit(ex, {**SPEC.default_config, "n_estimators": 30, "min_child_samples": 20})
    save_artifact(m, tmp_path / "a", {"version": "godark-test"})
    meta = json.loads((tmp_path / "a" / "model.json").read_text())
    assert meta["target"] == "godark" and meta["kind"] == "lightgbm" and meta["deployable"] is True
    assert meta["horizons_s"] == [3600, 21600] and set(meta["heads"]) == {"3600", "21600"}
    assert meta["primary_target"] == "dark_6h" and meta["targets"] == {"3600": "dark_1h", "21600": "dark_6h"}
    assert meta["heads"]["21600"]["target_name"] == "dark_6h"
    assert all(i["calibration_slice"] in ("time", "ships") for i in meta["fit_info"].values() if "n_fit" in i)
    for spec in meta["heads"].values():
        xs = spec["calibration"]["x"]
        assert all(a <= b for a, b in zip(xs, xs[1:]))
    assert not any(p.suffix in (".pkl", ".joblib") for p in (tmp_path / "a").iterdir())
    m2 = Lgbm.load(tmp_path / "a")
    a, b = m.predict(ex.head(50)), m2.predict(ex.head(50))
    assert np.allclose(a["p"], b["p"])
    # The backend's loader, when it is on this branch (be-predict's dvm/predict/artifact.py), reads it too.
    art = pytest.importorskip("dvm.predict.artifact")
    if not hasattr(art, "GodarkModel"):
        pytest.skip("backend artifact loader not here yet")
    live = art.load(tmp_path / "a")
    row = ex.iloc[0]
    feats = {f: (None if pd.isna(row.get(f)) else float(row[f])) for f in F.FEATURE_NAMES}
    got = live.predict(feats)
    want = m.predict(ex.head(1)).set_index("horizon_s")["p"]
    for h, p in got.items():
        assert abs(p - want[h]) < 1e-9


def test_context_model_is_marked_not_deployable(tmp_path):
    from ml.core.registry import save_artifact
    ex = synthetic_examples(n_ships=100, steps=20)
    m = Lgbm().fit(ex, {**SPEC.default_config, "features": "track+context", "n_estimators": 20,
                        "min_child_samples": 20, "min_category_rows": 10})
    save_artifact(m, tmp_path / "c", {"version": "godark-ctx"})
    meta = json.loads((tmp_path / "c" / "model.json").read_text())
    assert meta["deployable"] is False and "type_group" in meta["vocab"]


def test_threads_are_capped():
    import os
    from ml.godark import MAX_THREADS
    assert MAX_THREADS == 6 and int(os.environ["OMP_NUM_THREADS"]) <= 6
    assert SPEC.primary_horizons_s[0] == 21600


def test_config_schema_rejects_unknown_keys():
    jsonschema = pytest.importorskip("jsonschema")
    jsonschema.validate(SPEC.default_config, SPEC.config_schema)
    with pytest.raises(jsonschema.ValidationError):
        jsonschema.validate({**SPEC.default_config, "label": "unknown"}, SPEC.config_schema)
