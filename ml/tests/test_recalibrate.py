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
