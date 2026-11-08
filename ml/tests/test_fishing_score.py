"""Live fishing scorer (ml.fishing.score): this week's cases respect the leakage clock, rows have the ledger shape,
grading labels a past week from MPA events and leaves the current week alone, and the ml.auto step is opt-in."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

import ml  # noqa: F401
from ml.fishing import dataset as D
from ml.fishing import fetch
from ml.fishing import score as S
from ml.tests.test_fishing import MON, gfw_entry, synthetic_examples, write_events
from ml.fishing.target import Lgbm

DAY = D.D


def _events(tmp_path):
    recv = MON + 60 * DAY
    write_events(tmp_path, [
        gfw_entry("a1", 220000001, MON + DAY, MON + DAY + 3600_000, mpa=["555"]),       # known by week 2
        gfw_entry("a2", 220000001, MON + 15 * DAY, MON + 15 * DAY + 3600_000, mpa=["555"]),  # week 3, in an MPA
        gfw_entry("b1", 220000002, MON + 8 * DAY, MON + 8 * DAY + 3600_000),            # outside
        gfw_entry("c1", 220000003, MON + 13 * DAY, MON + 13 * DAY + 3600_000),          # not yet known at week 3
    ], recv)
    return D.prepare(fetch.load(tmp_path))


def test_week_start_and_live_cases_respect_the_clock(tmp_path):
    ev = _events(tmp_path)
    assert S.week_start(MON + 3 * DAY + 5) == MON
    wk3 = MON + 14 * DAY
    c = S.live_cases(ev, wk3)
    # a1 ended day 1 -> available ~day 6; b1 day 8 -> ~day 13; c1 day 13 -> ~day 18 > as_of: not a case
    assert set(c["mmsi"]) == {220000001, 220000002} and (c["as_of"] == wk3).all()


def test_score_rows_and_grading(tmp_path):
    ev = _events(tmp_path)
    m = Lgbm().fit(synthetic_examples(), {"model": "lgbm", "n_estimators": 20, "min_child_samples": 20})
    wk3 = MON + 14 * DAY
    f = S.score_week(ev, wk3, m, gfw_cache=tmp_path / "none")
    assert len(f) == 2 and f["p"].between(0, 1).all()
    rows = S.score_rows(f, "fishing-x")
    r = rows[0]
    assert r[1] == S.score_id(r[2], wk3) and r[3] == "fishing_mpa_7d" and r[4] == wk3 and r[5] == 7 * 86400
    assert r[7] == "fishing-x" and r[11] == "live" and set(json.loads(r[9])) == set(D.FEATURES)
    pending = [{"id": S.score_id(220000001, wk3), "mmsi": 220000001, "made_at": wk3},
               {"id": S.score_id(220000002, wk3), "mmsi": 220000002, "made_at": wk3},
               {"id": S.score_id(220000002, wk3 + 7 * DAY), "mmsi": 220000002, "made_at": wk3 + 7 * DAY}]
    out = S.grade(pending, ev, frontier=wk3 + 7 * DAY, now_ms=1)
    assert [(o[0], o[6]) for o in out] == [(pending[0]["id"], True), (pending[1]["id"], False)]
    assert out[0][8] == "a2" and out[0][9] == 86400   # the event and its lead from the week start


def test_distribution():
    d = S.distribution(np.array([0.01, 0.2, 0.6, 0.9]))
    assert d["n"] == 4 and sum(d["bins"].values()) == 4
    assert S.distribution(np.array([])) == {"n": 0}


def test_auto_step_is_opt_in(monkeypatch):
    from ml import auto
    calls = []

    class P:
        returncode, stderr = 0, ""
        stdout = '{"region": "x"}\n' + json.dumps({"vessels_scored": 3, "mode": "dry-run"}, indent=1)

    monkeypatch.setattr(auto.subprocess, "run", lambda cmd, **k: calls.append(cmd) or P())
    monkeypatch.delenv("ML_FISHING_SCORE_WRITE", raising=False)
    out = auto.fishing_score(lambda m: None)
    assert out["vessels_scored"] == 3 and "--write" not in calls[0]
    monkeypatch.setenv("ML_FISHING_SCORE_WRITE", "1")
    auto.fishing_score(lambda m: None)
    assert calls[1][-2:] == ["--write", "--allow-tiger"]
