import json

import numpy as np
import pandas as pd
import pytest

from ml.core import evaluate as ev
from ml.core.toy import ToyTarget, make_examples


@pytest.fixture
def spec():
    return ToyTarget(n_ships=12, days=5)


@pytest.fixture
def examples(spec):
    return spec.load_examples(spec.default_config, None)


def test_holdout_is_latest_block_and_frozen(spec, examples, tmp_path):
    h = ev.freeze_holdout(spec, examples, "v1", root=tmp_path)
    test = examples[examples["case_id"].isin(h.case_ids)]
    assert h.n == len(test) > 0
    assert test["as_of"].min() >= h.start
    assert (examples[~examples["case_id"].isin(h.case_ids)]["as_of"] < h.start).all()
    # Re-freezing with other data returns the frozen set unchanged.
    h2 = ev.freeze_holdout(spec, examples.iloc[:100], "v1", root=tmp_path)
    assert h2.hash == h.hash and h2.case_ids == h.case_ids


def test_edited_holdout_is_refused(spec, examples, tmp_path):
    ev.freeze_holdout(spec, examples, "v1", root=tmp_path)
    p = tmp_path / "holdout" / "toy-v1.json"
    d = json.loads(p.read_text())
    d["case_ids"] = d["case_ids"][1:]
    p.write_text(json.dumps(d))
    with pytest.raises(ValueError, match="hash"):
        ev.load_holdout("toy", "v1", tmp_path)


def test_split_embargo_and_no_leak(spec, examples, tmp_path):
    h = ev.freeze_holdout(spec, examples, "v1", root=tmp_path)
    train, test, info = ev.split(spec, examples, h)
    assert not set(train["case_id"]) & set(h.case_ids)
    assert (train["as_of"] + max(spec.horizons_s) * 1000 < h.start).all()   # no training label reaches the block
    assert info["n_holdout_missing"] == 0 and len(test) == h.n


def test_group_by_ship_keeps_heldout_ships_out(examples, tmp_path):
    spec = ToyTarget(n_ships=12, days=5)
    spec.group_by_ship = True
    h = ev.freeze_holdout(spec, examples, "g", root=tmp_path)
    train, test, _ = ev.split(spec, examples, h)
    assert 0 < len(h.ships) < examples["mmsi"].nunique()
    assert not set(train["mmsi"]) & set(h.ships)
    assert set(test["mmsi"]) <= set(h.ships)


def test_rolling_folds_are_ordered_with_embargo(spec, examples):
    folds = ev.rolling_folds(spec, examples, 3)
    assert len(folds) == 3
    for fit, val in folds:
        assert fit["as_of"].max() + ev.embargo_ms(spec) < val["as_of"].min()
    assert len(folds[0][0]) < len(folds[1][0]) < len(folds[2][0])   # expanding window


def _scored(loss, horizons=(3600, 10800), cov=(0.8, 0.95), strata=None):
    n = len(loss)
    rows = []
    for h in horizons:
        rows.append(pd.DataFrame({"case_id": [f"c{i}" for i in range(n)], "mmsi": 1, "as_of": 0, "horizon_s": h,
                                  "loss": loss, "in80": np.arange(n) < cov[0] * n, "in95": np.arange(n) < cov[1] * n,
                                  "ship_type": strata if strata is not None else "cargo", "speed_class": "fast"}))
    return pd.concat(rows, ignore_index=True)


def test_tie_keeps_champion(spec):
    loss = np.random.default_rng(0).gamma(2, 100, 400)
    d = ev.decide(spec, _scored(loss), _scored(loss.copy()))
    assert not d["promote"]


def test_clear_win_promotes(spec):
    rng = np.random.default_rng(0)
    ref = rng.gamma(2, 100, 400)
    d = ev.decide(spec, _scored(ref * 0.7), _scored(ref))
    assert d["promote"], d["reasons"]
    assert all(v["hi"] < 0 for v in d["horizons"].values())


def test_small_win_fails_after_bonferroni(spec):
    rng = np.random.default_rng(1)
    ref = rng.gamma(2, 100, 400)
    cand = ref * rng.normal(0.965, 0.08, 400)   # a marginal win: passes at 95%, not at 95% / 20
    alone = ev.decide(spec, _scored(cand), _scored(ref), n_comparisons=1)
    many = ev.decide(spec, _scored(cand), _scored(ref), n_comparisons=20)
    assert alone["promote"] and not many["promote"]
    assert many["alpha"] == pytest.approx(0.0025)


def test_bad_calibration_blocks(spec):
    rng = np.random.default_rng(0)
    ref = rng.gamma(2, 100, 400)
    d = ev.decide(spec, _scored(ref * 0.7, cov=(0.6, 0.95)), _scored(ref))
    assert not d["promote"] and any("80% radius" in r for r in d["reasons"])


def test_worse_stratum_blocks(spec):
    rng = np.random.default_rng(0)
    ref = rng.gamma(2, 100, 400)
    strata = np.where(np.arange(400) < 60, "fishing", "cargo")
    cand = np.where(strata == "fishing", ref * 1.5, ref * 0.6)   # much better overall, fishing 50% worse
    d = ev.decide(spec, _scored(cand, strata=strata), _scored(ref, strata=strata))
    assert not d["promote"]
    assert {w["value"] for w in d["strata_worse"]} == {"fishing"}


def test_skill_table_baseline_is_zero(spec):
    loss = np.random.default_rng(0).gamma(2, 100, 300)
    t = ev.skill_table(spec, _scored(loss), _scored(loss))
    assert t["3600"]["skill"] == 0 and t["3600"]["skill_lo"] == 0


def test_examples_deterministic():
    a, b = make_examples(n_ships=3, days=1), make_examples(n_ships=3, days=1)
    pd.testing.assert_frame_equal(a, b)


def test_holdout_is_not_frozen_without_enough_history(spec, examples, tmp_path):
    """A set frozen too early would leave nothing to train on forever (the server's first cycle on a young feed)."""
    span = int(examples["as_of"].max() - examples["as_of"].min())
    short = examples[examples["as_of"] >= examples["as_of"].max() - min(span, ev.embargo_ms(spec))]
    with pytest.raises(ValueError, match="not enough history"):
        ev.freeze_holdout(spec, short, root=tmp_path)
    assert not list((tmp_path / "holdout").glob("*.json")) if (tmp_path / "holdout").exists() else True
