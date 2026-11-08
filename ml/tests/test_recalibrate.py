import numpy as np
import pandas as pd

from ml.core import recalibrate as R


def test_route_factor_restores_coverage_and_keeps_only_real_changes():
    rng = np.random.default_rng(0)
    n = 4000
    r80 = np.full(n, 1000.0)
    err = np.abs(rng.normal(0, 1000, n))           # true 80% quantile ~1282 m: the circles are too small
    df = pd.DataFrame({"made_at": np.arange(n), "horizon_s": 3600, "radius_m_80": r80, "radius_m_95": r80 * 2,
                       "error_m": err})
    f = R.fit_route(df)[3600]
    assert f["keep"] and 1.2 < f["k80"] < 1.4 and abs(f["cov80_after"] - 0.8) < 0.03
    calibrated = df.assign(radius_m_80=r80 * f["k80"], radius_m_95=r80 * 2 * f["k95"])
    assert not R.fit_route(calibrated)[3600]["keep"]      # a second pass changes nothing


def test_godark_shift_only_when_the_newer_half_improves():
    rng = np.random.default_rng(1)
    n = 20000
    p = np.full(n, 0.04)
    y = rng.random(n) < 0.02                              # over-predicts 2x, steady over time
    f = R.fit_godark(pd.DataFrame({"made_at": np.arange(n), "target": "dark_6h", "p": p, "label": y}))["dark_6h"]
    assert f["keep"] and f["shift"] < -0.5 and f["logloss_after"] < f["logloss_before"]


def test_next_version():
    assert R.next_version("route-dma90-v2") == "route-dma90-v2-cal1"
    assert R.next_version("route-dma90-v2-cal1") == "route-dma90-v2-cal2"


def test_write_route_leaves_a_measured_refused_head_alone(tmp_path):
    """The review's case: the 1 h head measured 78.7% coverage, so its fit was refused; the 3 h head was kept at
    about 1.59. The 1 h radii must stay as they are, and only a head with no graded rows gets the kept median."""
    import json
    fit = {3600: {"k80": 0.999, "k95": 1.004, "n": 1200, "cov80_before": 0.787, "cov80_after": 0.786,
                  "cov95_before": 0.951, "cov95_after": 0.952, "keep": False},
           10800: {"k80": 1.59, "k95": 1.41, "n": 900, "cov80_before": 0.52, "cov80_after": 0.79,
                   "cov95_before": 0.80, "cov95_after": 0.94, "keep": True}}
    src = tmp_path / "route-x"
    src.mkdir()
    heads = {"3600": {"radius_m_80": 1000.0, "radius_m_95": 2000.0},
             "10800": {"radius_m_80": {"r": [1000.0, 2000.0]}, "radius_m_95": {"r": [2000.0, 4000.0]}},
             "21600": {"radius_m_80": 3000.0, "radius_m_95": 6000.0}}
    (src / "model.json").write_text(json.dumps({"version": "route-x", "heads": heads}))
    used = R.write_route(src, tmp_path / "route-x-cal1", fit, "test")
    m = json.loads((tmp_path / "route-x-cal1" / "model.json").read_text())
    k3 = fit[10800]["k80"]
    assert used["3600"] == {"k80": 1.0, "k95": 1.0, "measured": True, "kept": False}
    assert m["heads"]["3600"]["radius_m_80"] == 1000.0 and m["heads"]["3600"]["radius_m_95"] == 2000.0
    assert m["heads"]["10800"]["radius_m_80"]["r"] == [round(1000 * k3, 1), round(2000 * k3, 1)]
    assert used["21600"]["measured"] is False and used["21600"]["k80"] == k3    # unmeasured: the kept median
    assert m["version"] == "route-x-cal1" and m["recalibrations"][-1]["parent"] == "route-x"
