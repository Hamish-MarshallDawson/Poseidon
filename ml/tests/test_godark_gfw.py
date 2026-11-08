"""GFW go-dark target (#121): weekly unit, leakage clock, labels and censoring, fixed September held-out set,
the run through ml/core, the learning curve and its report section."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

import ml  # noqa: F401
from ml.core import evaluate as ev
from ml.core.registry import FileRegistry
from ml.core.report import build, render_html
from ml.core.run import run_one
from ml.godark_gfw import curve as C
from ml.godark_gfw import dataset as D
from ml.godark_gfw.target import SPEC, TEST_END, TEST_START

DAY = D.D
MON = int(pd.Timestamp("2026-06-01", tz="UTC").value // 1_000_000)   # a Monday


def write_cache(root, kinds: dict[str, list[dict]]):
    for kind, rows in kinds.items():
        (root / kind).mkdir(parents=True, exist_ok=True)
        pd.DataFrame(rows).to_parquet(root / kind / "2026-06.parquet", index=False)


def pres(mmsi, day_ts, region="gulf_of_oman", hours=10.0, flag="PAN", vt="CARGO"):
    return {"mmsi": mmsi, "ts": day_ts, "available_ts": day_ts + 5 * DAY, "recv_ts": day_ts + 5 * DAY,
            "hours": hours, "region": region, "flag": flag, "vessel_type": vt, "geartype": vt}


def ev_row(mmsi, ts, end, avail, hours=12.0, **kw):
    return {"mmsi": mmsi, "ts": ts, "end_ts": end, "available_ts": avail, "recv_ts": avail, "hours": hours, **kw}


def test_weekly_unit_leakage_clock_and_labels(tmp_path):
    a = 111
    as_of = MON + 2 * DAY + 5 * DAY     # newest presence day of the week is Wednesday, public 5 days later
    write_cache(tmp_path, {
        "ais_presence": [pres(a, MON), pres(a, MON + DAY), pres(a, MON + 2 * DAY, region="hormuz", hours=20),
                         pres(a, MON + 7 * DAY)],                                   # next week: a second row
        "port_visit": [ev_row(a, MON - 10 * DAY, MON - 8 * DAY, MON - 7 * DAY),    # known
                       ev_row(a, MON - 3 * DAY, MON - 2 * DAY, as_of + DAY)],       # published after as_of
        "loitering": [ev_row(a, MON - DAY, MON, MON + DAY, shore_km=80.0)],
        "encounter": [ev_row(a, MON + 3 * DAY, MON + 4 * DAY, as_of + 1)],          # not yet public
        "gap": [ev_row(a, MON - 400 * DAY, MON - 399 * DAY, MON - 395 * DAY, off_shore_km=120.0),  # old, known
                ev_row(a, MON + 4 * DAY, MON + 6 * DAY, as_of + 2 * DAY, off_shore_km=100.0),  # before as_of, unpublished
                ev_row(a, as_of + 3 * DAY, as_of + 4 * DAY, as_of + 5 * DAY, off_shore_km=90.0),  # label: 3 days on
                ev_row(999, as_of + 20 * DAY, as_of + 21 * DAY, as_of + 22 * DAY, off_shore_km=90.0)],  # frontier
    })
    w, info = D.build(tmp_path)
    assert len(w) == 2 and info["ships"] == 1
    r = w.iloc[0]
    assert r["as_of"] == as_of and r["days_present"] == 3 and r["hours_week"] == 40 and r["n_regions"] == 2
    assert r["region"] == "hormuz"                       # the region with the most hours that week
    assert r["port_visits_90d"] == 1 and np.isclose(r["days_since_port"], (as_of - (MON - 8 * DAY)) / DAY)
    assert r["loiter_90d"] == 1 and r["loiter_shore_km_90d"] == 80.0
    assert r["encounters_90d"] == 0                      # available_ts > as_of
    assert r["gaps_prev_all"] == 1 and r["gaps_prev_365d"] == 0   # the unpublished gap is invisible
    assert np.isclose(r["days_since_gap"], (as_of - (MON - 400 * DAY)) / DAY)
    # label: a gap starts 3 days after as_of; the frontier is as_of + 20 days, so 30 d is censored (null)
    assert r["y_7d"] == 1 and r["y_14d"] == 1 and np.isnan(r["y_30d"])
    assert r["case_id"] == "111:2026-06-01"
    second = w.iloc[1]
    assert second["weeks_since_prev"] == 1 and second["hours_prev4w"] == 40


def synthetic_examples(n_ships=3000, seed=0):
    """Ship-weeks from May to October 2026 with a real signal: ships with earlier gaps go dark more often."""
    rng = np.random.default_rng(seed)
    start = int(pd.Timestamp("2026-05-04", tz="UTC").value // 1_000_000)
    rows = []
    risky = rng.random(n_ships) < 0.1
    for m in range(n_ships):
        for wk in range(0, 22, 1 + int(rng.integers(0, 3))):
            week = start + wk * 7 * DAY
            p = 0.12 if risky[m] else 0.004
            r = {"mmsi": 200_000_000 + m, "week": week, "as_of": week + 7 * DAY,
                 "region": ["danish_straits", "gulf_of_oman", "hormuz", "gulf_of_finland"][m % 4],
                 "flag": ["PAN", "DNK", "LBR"][m % 3], "type_group": ["CARGO", "TANKER", "FISHING"][m % 3]}
            r |= {f: float(rng.random()) for f in D.NUMERIC}
            r["gaps_prev_365d"] = float(risky[m] * rng.integers(1, 4))
            y30 = float(rng.random() < p)
            r |= {"y_30d": y30, "y_14d": float(y30 and rng.random() < 0.6), "y_7d": float(y30 and rng.random() < 0.3)}
            rows.append(r)
    ex = pd.DataFrame(rows)
    ex.insert(0, "case_id", ex["mmsi"].astype(str) + ":" + pd.to_datetime(ex["week"], unit="ms").dt.strftime("%Y-%m-%d"))
    return ex.sort_values(["as_of", "case_id"]).reset_index(drop=True)


def test_run_through_core_curve_and_report(tmp_path, monkeypatch):
    ex = synthetic_examples()
    hold = ev.freeze_holdout(SPEC, ex, "v1", root=tmp_path)
    assert hold.start >= TEST_START and hold.end < TEST_END                   # September only
    train, test, _ = ev.split(SPEC, ex, hold)
    assert test["as_of"].between(TEST_START, TEST_END - 1).all()
    assert train["as_of"].max() < TEST_START - 30 * DAY                       # 30-day embargo

    reg = FileRegistry(tmp_path / "reg")
    row = run_one(SPEC, dict(SPEC.default_config), reg=reg, examples=ex, artifacts=tmp_path, log=lambda *a: None)
    m = row["metrics"]
    assert m["state"] == "done" and set(m["skill"]) >= {str(h) for h in SPEC.primary_horizons_s}
    assert m["skill"][str(30 * 86400)]["skill"] > 0                         # the planted signal is learnt
    meta = json.loads((tmp_path / "godark_gfw" / row["run_id"] / "model.json").read_text())
    assert meta["deployable"] is False and not list((tmp_path / "godark_gfw" / row["run_id"]).glob("*.pkl"))

    curve = C.run(ex, [1, 2, 4, 8, "all"], root=tmp_path, log=lambda *a: None)
    by = {p["months"]: p for p in curve["points"]}
    assert "skipped" in by[8]                                                # only about 3 months exist
    assert by[1]["n_train"] < by[2]["n_train"] < by["all"]["n_train"]
    n_test = {p["horizons"]["2592000"]["n_test"] for p in curve["points"] if "horizons" in p}
    assert len(n_test) == 1                                                  # same test set every time

    monkeypatch.setattr("ml.godark_gfw.target.DEFAULT_ARTIFACTS", tmp_path)
    (tmp_path / "reports").mkdir()
    (tmp_path / "reports" / "godark_gfw-learning_curve.json").write_text(json.dumps(curve, default=str))
    rep = build(SPEC, reg)
    assert rep["sections"] and rep["sections"][0]["title"].startswith("More history")
    page = render_html(rep)
    assert "months of history used for training" in page and "<svg" in page
