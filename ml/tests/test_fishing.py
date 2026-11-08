"""Fishing-in-MPA target (#157): GFW event flattening, the weekly unit, the leakage clock, labels and censoring, the
fixed held-out weeks, and a run through ml/core that writes a go-dark-style artifact which loads back."""
from __future__ import annotations

import json

import numpy as np
import pandas as pd

import ml  # noqa: F401
from ml.core import evaluate as ev
from ml.core.registry import FileRegistry
from ml.core.run import run_one
from ml.fishing import dataset as D
from ml.fishing import fetch
from ml.fishing.target import SPEC, TEST_END, TEST_START, Lgbm

DAY = D.D
MON = int(pd.Timestamp("2026-06-01", tz="UTC").value // 1_000_000)   # a Monday
ISO = lambda ms: pd.Timestamp(ms, unit="ms", tz="UTC").strftime("%Y-%m-%dT%H:%M:%S.000Z")  # noqa: E731


def gfw_entry(eid, mmsi, start, end, mpa=(), no_take=(), eez=("5674",), risk=False, flag="DNK"):
    """The shape of one `public-global-fishing-events` entry (as returned on 8 Nov 2026)."""
    return {"id": eid, "type": "fishing", "start": ISO(start), "end": ISO(end),
            "position": {"lat": 57.4, "lon": 11.43},
            "regions": {"mpa": list(mpa), "mpaNoTake": list(no_take), "eez": list(eez), "eez12Nm": list(eez),
                        "rfmo": ["ICES"], "highSeas": [], "protectedseas": ["AIDNK1"], "mpaNoTakePartial": []},
            "distances": {"startDistanceFromShoreKm": 6, "startDistanceFromPortKm": 10.4},
            "vessel": {"id": "v" + str(mmsi), "name": "SLESVIG", "ssvid": str(mmsi), "flag": flag, "type": "fishing"},
            "fishing": {"totalDistanceKm": 119.8, "averageSpeedKnots": 2.6, "potentialRisk": risk,
                        "vesselPublicAuthorizationStatus": "not_matching_relevant_public_authorization"}}


def write_events(root, entries, recv_ts, region="danish_straits"):
    df = fetch.flatten(entries, region, recv_ts)
    (root / "events" / region).mkdir(parents=True, exist_ok=True)
    df.to_parquet(root / "events" / region / "2026-06.parquet", index=False)
    return df


def test_flatten_keeps_ids_regions_and_the_leakage_clock():
    recv = MON + 200 * DAY   # a backfill, long after the event
    df = fetch.flatten([gfw_entry("e1", 220323000, MON + 3600_000, MON + DAY + 7200_000, mpa=["555"],
                                  eez=["5694", "5674"]),
                        gfw_entry("e2", 12, MON, MON + 3600_000)],   # not a vessel MMSI: dropped
                       "danish_straits", recv)
    assert len(df) == 1
    r = df.iloc[0]
    assert r["event_id"] == "e1" and r["mmsi"] == 220323000 and r["mpa"] == "555" and r["eez"] == "5694|5674"
    assert np.isclose(r["hours"], 25.0) and r["authorization_status"].startswith("not_matching")
    assert r["available_ts"] == MON + 2 * DAY + 4 * DAY       # end of the event's last UTC day plus GFW's 4-day lag


def test_weekly_unit_leakage_clock_labels_and_frontier(tmp_path):
    a = 219000001
    h = 3600_000
    entries = [
        gfw_entry("old", a, MON - 20 * DAY, MON - 20 * DAY + 5 * h, mpa=["1"]),          # known, in MPA
        gfw_entry("out", a, MON - 10 * DAY, MON - 10 * DAY + 3 * h, eez=["5674", "5694"]),  # known, border, outside
        gfw_entry("late", a, MON - 2 * DAY, MON - 2 * DAY + 2 * h, mpa=["1"]),           # before as_of, public after
        gfw_entry("next", a, MON + 2 * DAY, MON + 2 * DAY + 4 * h, no_take=["9"]),        # label: in MPA next week
        gfw_entry("w2", a, MON + 9 * DAY, MON + 9 * DAY + 4 * h, risk=True),               # week 2: outside
        gfw_entry("front", a, MON + 40 * DAY, MON + 40 * DAY + h),                         # sets the frontier
    ]
    write_events(tmp_path, entries, recv_ts=MON + 400 * DAY)
    w, info = D.build(tmp_path, gfw_cache=tmp_path / "none")
    r = w.set_index("case_id").loc[f"{a}:2026-06-01"]
    assert r["as_of"] == MON
    assert r["events_ever"] == 2 and r["mpa_events_ever"] == 1      # "late" is not public yet at as_of
    assert r["hours_in_mpa_28d"] == 5 and r["hours_out_mpa_28d"] == 3
    assert r["share_mpa_90d"] == 0.5 and r["share_border_90d"] == 0.5
    assert np.isclose(r["days_since_event"], 10) and np.isclose(r["days_since_mpa"], 20)
    assert r["flag"] == "DNK" and r["gear"] == "UNKNOWN" and r["region"] == "danish_straits"
    assert r[D.LABEL] == 1 and r["y_fish_7d"] == 1 and r["y_risk_next"] == 0
    r2 = w.set_index("case_id").loc[f"{a}:2026-06-08"]
    assert r2[D.LABEL] == 0 and r2["y_fish_7d"] == 1 and r2["y_risk_next"] == 1
    assert r2["events_ever"] == 4          # "late" became public on 6 Jun, "next" exactly at 8 Jun 00:00 (<= as_of)
    # frontier: newest start minus 2 days; weeks ending after it are unlabelled, weeks starting after it are dropped
    frontier = MON + 38 * DAY
    assert w.loc[w["as_of"] + 7 * DAY > frontier, D.LABEL].isna().all()
    assert (w["as_of"] <= frontier).all()
    assert info["labels"][D.LABEL]["positives"] == 2              # also the week before: "late" was in an MPA


def synthetic_examples(n=1500, seed=0):
    """Vessel-weeks Mar to Nov 2026 with a real signal: vessels that fished in MPAs recently do so again."""
    rng = np.random.default_rng(seed)
    start = int(pd.Timestamp("2026-03-02", tz="UTC").value // 1_000_000)
    rows = []
    habit = rng.random(n)
    for m in range(n):
        for wk in range(0, 36, 1 + int(rng.integers(0, 2))):
            as_of = start + wk * 7 * DAY
            r = {"mmsi": 219_000_000 + m, "as_of": as_of,
                 "region": ["danish_straits", "gulf_of_oman", "hormuz", "gulf_of_finland"][m % 4],
                 "flag": ["DNK", "SWE", "IRN"][m % 3], "gear": ["TRAWLERS", "FISHING", "FIXED_GEAR"][m % 3],
                 "auth_status": "pending_info"}
            r |= {f: float(rng.random()) for f in D.NUMERIC}
            r["share_mpa_90d"] = float(np.clip(habit[m] + rng.normal(0, 0.1), 0, 1))
            r[D.LABEL] = float(rng.random() < 0.05 + 0.6 * habit[m] ** 2)
            r["y_fish_7d"], r["y_risk_next"] = 1.0, 0.0
            rows.append(r)
    ex = pd.DataFrame(rows)
    ex.insert(0, "case_id", ex["mmsi"].astype(str) + ":" + pd.to_datetime(ex["as_of"], unit="ms").dt.strftime("%Y-%m-%d"))
    return ex.sort_values(["as_of", "case_id"]).reset_index(drop=True)


def test_run_through_core_and_artifact(tmp_path):
    ex = synthetic_examples()
    hold = ev.freeze_holdout(SPEC, ex, "v1", root=tmp_path)
    assert hold.start >= TEST_START and hold.end < TEST_END
    train, test, _ = ev.split(SPEC, ex, hold)
    assert train["as_of"].max() < TEST_START - 7 * DAY                       # one-week embargo

    reg = FileRegistry(tmp_path / "reg")
    row = run_one(SPEC, dict(SPEC.default_config), reg=reg, examples=ex, artifacts=tmp_path, log=lambda *a: None)
    m = row["metrics"]
    assert m["state"] == "done" and m["skill"][str(7 * 86400)]["skill"] > 0.1   # the planted signal is learnt
    d = tmp_path / "fishing" / row["run_id"]
    meta = json.loads((d / "model.json").read_text())
    head = meta["heads"][str(7 * 86400)]
    assert set(head) >= {"model", "calibration"} and (d / head["model"]).exists()
    x = head["calibration"]["x"]
    assert x == sorted(x) and len(x) == len(head["calibration"]["y"])
    assert not list(d.glob("*.pkl"))
    p = Lgbm.load(d).predict(test)["p"].to_numpy()
    assert len(p) == len(test) and ((p >= 0) & (p <= 1)).all() and p.std() > 0
