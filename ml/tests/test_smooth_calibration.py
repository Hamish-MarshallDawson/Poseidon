import json

import numpy as np
import pandas as pd

from ml.core import smooth_calibration as S


def _data(n=20000, seed=0):
    rng = np.random.default_rng(seed)
    z = rng.normal(-2, 1.2, n)
    raw = S._expit(z)                                   # an over-confident raw score (class weights)
    y = (rng.random(n) < S._expit(-3.5 + 0.5 * z)).astype(int)
    made_at = np.repeat(np.arange(10), n // 10)
    return pd.DataFrame({"made_at": made_at, "raw": raw, "label": y})


def _staircase(raw, y):
    m = S.iso_mid_map(raw, y)                              # the block values ...
    xs, ys = [], []
    for i, (a, b) in enumerate(zip(m["x"], m["y"])):       # ... as flat runs joined by near-vertical steps
        lo = m["x"][i - 1] + 1e-6 if i else 0.0
        xs += [lo, a]
        ys += [b, b]
    return {"x": xs, "y": ys}


def test_platt_is_strictly_increasing_and_beats_a_staircase():
    d = _data()
    cur = _staircase(d.raw.to_numpy(), d.label.to_numpy())
    ev = S.evaluate_head(d, cur, None)
    r = ev["newer_half"]
    assert r["platt"]["strictly_increasing"] and not r["current"]["strictly_increasing"]
    assert r["platt"]["distinct"] == r["platt"]["n"] > 20 * r["current"]["distinct"]
    assert r["platt"]["log_loss"] < r["current"]["log_loss"]
    assert r["platt"]["auc"] >= r["current"]["auc"]
    assert ev["winner"] in S.SMOOTH and ev["winner_beats_current"]
    a, b = r["platt"]["params"]["a"], r["platt"]["params"]["b"]
    assert abs(b - 0.5) < 0.1 and abs(a + 3.5) < 0.4      # recovers the true link


def test_split_never_cuts_a_snapshot():
    d = pd.DataFrame({"made_at": [1] * 5 + [2] * 3 + [3] * 4, "raw": 0.1, "label": 0})
    old, new = S.snapshot_halves(d)
    assert set(old.made_at) == {1} and set(new.made_at) == {2, 3}


def test_top_hit_rate_counts_a_straddling_tie_pro_rata():
    p = np.array([0.9, 0.5, 0.5, 0.5, 0.5, 0.1, 0.1, 0.1, 0.1, 0.1] * 10)
    y = np.array([1, 1, 0, 0, 0, 0, 0, 0, 0, 0] * 10)
    # top 10 rows: the 10 rows at 0.9 (all hits)
    assert S.top_hit_rate(p, y) == 1.0
    # top 20%: 10 at 0.9 and 10 of the 40 tied at 0.5 (a quarter of them hits)
    assert abs(S.top_hit_rate(p, y, 0.2) - (10 + 10 * 10 / 40) / 20) < 1e-12


def test_step_midpoints_and_shift_stay_increasing():
    cur = {"x": [0.0, 0.1, 0.1001, 0.5, 0.5001, 1.0], "y": [0.0, 0.0, 0.05, 0.05, 0.2, 0.2]}
    mid = S.step_midpoints(cur)
    assert list(mid["y"]) == [0.0, 0.05, 0.2] and np.allclose(mid["x"], [0.05, 0.30005, 0.75005])
    sh = S.shifted(mid, -0.7)
    assert S.strictly_increasing(sh) and sh["y"][0] == S.Y_FLOOR


def test_written_artifact_loads_and_scores_through_the_backend(tmp_path):
    import lightgbm as lgb
    from dvm.predict import artifact as A
    from dvm.predict import features as F
    feats = ["sog_kn", "w2h_n"]
    rng = np.random.default_rng(2)
    X = rng.random((400, 2))
    y = (X[:, 0] + rng.normal(0, 0.3, 400) > 0.8).astype(int)
    b = lgb.train({"objective": "binary", "verbose": -1, "num_leaves": 4}, lgb.Dataset(X, y), 5)
    src = tmp_path / "godark-x"
    src.mkdir()
    b.save_model(str(src / "h3600.txt"))
    (src / "model.json").write_text(json.dumps({
        "target": "godark", "kind": "lightgbm", "version": "godark-x", "feature_version": F.FEATURE_VERSION,
        "features": feats, "horizons_s": [3600],
        "heads": {"3600": {"model": "h3600.txt", "calibration": {"x": [0, 0.5, 1], "y": [0, 0.1, 0.1]}}}}))
    a, bb = S.fit_platt(b.predict(X), y)
    cal = S.platt_map(a, bb) | {"method": "platt", "params": {"a": a, "b": bb}, "fit_rows": "400"}
    dst = tmp_path / "godark-x-smooth1"
    S.write_artifact(src, dst, {"3600": cal}, {"check": 1}, None)
    m = A.load(dst)
    assert m.version == "godark-x-smooth1"
    ps = [m.predict({"sog_kn": float(s), "w2h_n": 0.5})[3600] for s in np.linspace(0, 1, 50)]
    assert all(0 < p < 1 for p in ps) and np.all(np.diff(ps) >= 0)
    meta = json.loads((dst / "model.json").read_text())
    assert meta["recalibration"]["parent"] == "godark-x" and meta["recalibration"]["heads"]["3600"]["method"] == "platt"
