"""Forecasts in the live frames and route shapes, checked against the frontend's TypeScript types (#121 addendum)."""
from __future__ import annotations

import re
from pathlib import Path

import pytest

from dvm import app as app_mod, config
from dvm.models import PositionReport
from dvm.predict import forecast as FC
from dvm.predict.routes import coverage_spans, outcome_ts

TYPES = Path(__file__).resolve().parents[2] / "frontend" / "src" / "types.ts"
H, MIN = 3_600_000, 60_000
T = 1_699_999_200_000   # on the hour


def ts_fields(name: str) -> tuple[set[str], set[str]]:
    """(all fields, optional fields) of `export interface <name> { ... }` in types.ts."""
    src = re.sub(r"//[^\n]*", "", TYPES.read_text())
    i = src.index("{", src.index(f"export interface {name} "))
    depth, j = 0, i
    while True:
        depth += {"{": 1, "}": -1}.get(src[j], 0)
        if depth == 0:
            break
        j += 1
    text = re.sub(r"\{[^{}]*\}", "", src[i + 1:j])   # nested object types are one field
    fields = re.findall(r"(\w+)(\??):", text)
    return {f for f, _ in fields}, {f for f, q in fields if q}


def ts_union(name: str) -> dict[str, set[str]]:
    """kind -> fields of each `{ kind: "x"; ... }` alternative of `export type <name> =`."""
    src = re.sub(r"//[^\n]*", "", TYPES.read_text())
    block = re.search(r"export type " + name + r" =(.*?);\s*\n(?:export|\n)", src, re.S).group(1)
    out = {}
    for alt in re.findall(r"\{([^{}]*)\}", block):
        kind = re.search(r'kind:\s*"(\w+)"', alt).group(1)
        out[kind] = set(re.findall(r"(\w+)\??:", alt))
    return out


def assert_shape(obj: dict, name: str) -> None:
    fields, optional = ts_fields(name)
    assert set(obj) <= fields, f"{name}: extra {set(obj) - fields}"
    assert fields - optional <= set(obj), f"{name}: missing {fields - optional - set(obj)}"


def score_row(mmsi, p, made_at=T - 10 * MIN, target="dark_6h", h=21600, contrib=None):
    return {"id": f"score-{mmsi}-{target}-{made_at}", "mmsi": mmsi, "target": target, "made_at": made_at,
            "horizon_s": h, "p": p, "model_version": "m1", "feature_version": "f1",
            "features": {"sog_kn": 10.0, "draught_m": None} if target == "dark_6h" else {"same_as": "x"},
            "contrib": contrib or {}, "mode": "live"}


def route_set(mmsi, as_of, made_at, gap_id=None, model="baseline-dr-v1"):
    return [{"id": f"r-{mmsi}-{h}", "mmsi": mmsi, "made_at": made_at, "as_of": as_of, "model_version": model,
             "horizon_s": h, "lat": 55 + h / 1e6, "lon": 11.0, "radius_m_80": h / 10, "radius_m_95": h / 5,
             "base_lat": 55.0, "base_lon": 11.0, "gap_id": gap_id, "feature_version": "f1", "mode": "live"}
            for h in (3600, 10800, 21600, 86400)]


def test_forecast_ranks_prunes_and_freezes():
    fc = FC.Forecast(p_alert=0.2)
    fc.update([score_row(1, 0.1), score_row(2, 0.5), score_row(3, 0.3, made_at=T - 2 * H),
               score_row(2, 0.4, target="dark_1h", h=3600)], [], set(), T)
    assert fc.risk_of(2) == (0.5, 1) and fc.risk_of(1) == (0.1, 2) and fc.risk_of(3) == (None, None)  # 3 too old
    assert_shape(fc.score_of(2), "RiskScore")
    assert fc.score_of(2)["features"] == {"sog_kn": 10.0}   # nulls dropped: Record<string, number>
    frozen = {r["id"]: r for r in fc.frozen_set(T)}
    assert set(frozen) == {f"score-1-dark_6h-{T}", f"score-2-dark_6h-{T}", f"score-2-dark_1h-{T}"}
    six = frozen[f"score-2-dark_6h-{T}"]
    assert six["made_at"] == T and six["features"]["scored_age_s"] == 600
    assert frozen[f"score-2-dark_1h-{T}"]["features"] == {"same_as": f"score-2-dark_6h-{T}"}
    assert fc.frozen_set(T - H) == []   # nothing was made in the hour before T - 1 h


def test_gap_fields_follow_the_gap_age_and_route_block():
    fc = FC.Forecast()
    fc.update([], route_set(7, T, T + 30 * MIN, gap_id="g7") + route_set(8, T, T), {"g7"}, T + 30 * MIN)
    f = fc.gap_fields("g7", T + 30 * MIN)
    assert f["pred_horizon_s"] == 3600 and f["pred_r80_m"] == 360 and f["pred_model"] == "baseline-dr-v1"
    assert set(f) == {"pred_lat", "pred_lon", "pred_r80_m", "pred_r95_m", "pred_horizon_s", "pred_made_at", "pred_model",
                      "pred_mpa_ids", "pred_mpa_share_80", "pred_foreign_eez", "pred_foreign_share_80"}   # zones, #157
    assert fc.gap_fields("g7", T + 2 * H)["pred_horizon_s"] == 10800
    assert fc.gap_fields("g7", T + 30 * H)["pred_horizon_s"] == 86400   # past the last horizon: the last one
    assert fc.gap_fields("nope", T) == {}
    b = fc.route_block(7)
    assert b["gap_id"] == "g7" and [p["horizon_s"] for p in b["points"]] == [3600, 10800, 21600, 86400]
    fc.update([], [], set(), T + H)   # gap g7 closed: its prediction leaves the gaps, the ship keeps its block
    assert fc.gap_fields("g7", T + H) == {} and fc.route_block(7) is not None
    fc.update([], [], set(), T + 7 * H)
    assert fc.route_block(8) is None   # an active ship's set expires after 6 h


@pytest.fixture
def hub(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "TIGER_DATABASE_URL", "")
    h = app_mod.Hub()
    yield h
    h.rawlog.close()


def _fix(mmsi, ts):
    return PositionReport(mmsi=mmsi, ts=ts, recv_ts=ts, lat=55.0, lon=11.0, sog_kn=10, cog_deg=90, cls="A",
                          msg_type=1, ts_quality="source", src="aisstream")


def test_hub_frames_carry_risk_watchlist_and_gap_predictions(hub):
    now = app_mod.now_ms()
    for m in (1, 2, 3):
        hub.live.apply(_fix(m, now - MIN))
    hub.live.static[1] = {"name": "ONE", "destination": "RIGA"}
    gap = {"id": "gap-3-1", "version": 1, "mmsi": 3, "state": "open", "start_ts": now - H, "end_ts": None,
           "duration_s": 3600, "last_lat": 55.0, "last_lon": 11.0, "last_sog_kn": 10.0, "last_cog_deg": 90.0,
           "next_lat": None, "next_lon": None, "neighbours_heard": 5, "neighbours_baseline": 5, "cell_id": "x",
           "coverage_flag": "deliberate_candidate", "draught_before_m": None, "draught_after_m": None}
    hub.live.apply_gaps([gap])
    hub.live.take_changes(now, 1800)
    hub.pending_gaps = []

    fc = FC.Forecast(p_alert=0.2)
    fc.update([score_row(1, 0.6, made_at=now - MIN), score_row(2, 0.05, made_at=now - MIN),
               score_row(3, 0.1, made_at=now - 2 * H + MIN)],
              route_set(3, now - 50 * MIN, now - 30 * MIN, gap_id="gap-3-1"), {"gap-3-1"}, now)
    hub.on_forecast(fc)

    vessels, _ = hub.live.take_changes(now, 1800)
    by = {v["mmsi"]: v for v in vessels}
    assert (by[1]["risk_p"], by[1]["risk_rank"]) == (0.6, 1) and by[2]["risk_rank"] == 2
    assert [g["id"] for g in hub.pending_gaps] == ["gap-3-1"]
    out = hub.live.gap_out(hub.pending_gaps[0], now)
    assert out["pred_horizon_s"] == 3600 and "pred_lat" not in gap   # the detector's dict is not touched
    wl = hub.pending_watchlist
    assert_shape(wl, "Watchlist")
    for e in wl["entries"]:
        assert_shape(e, "WatchlistRow")
        for ev in e["evidence"]:
            assert_shape(ev, "Evidence")
    e1, e2 = wl["entries"]
    assert e1["decision"] == "inspect" and e1["reason_codes"] == ["HIGH_FORECAST"] and e1["name"] == "ONE"
    assert e2["decision"] == "none" and e2["reason_codes"] == ["BLANK_DESTINATION"] and e2["prev_rank"] is None

    snap = hub.snapshot_msg(now)
    assert snap["watchlist"] is wl and snap["gaps"][0]["pred_model"] == "baseline-dr-v1"
    d = hub.live.detail(3)
    assert d["route_prediction"]["gap_id"] == "gap-3-1" and d["gaps"][0]["pred_r95_m"] == 720
    assert d["score"] is None   # its score is over an hour old
    assert_shape(hub.live.detail(1)["score"], "RiskScore")
    assert "route_prediction" not in hub.live.detail(1)

    hub.pending_watchlist = None
    hub.on_forecast(fc)   # same forecast again: nothing new to send
    assert hub.pending_watchlist is None and [g["id"] for g in hub.pending_gaps] == ["gap-3-1"]
    assert hub.live.take_changes(now, 1800)[0] == []
    # The predictor updates the same Forecast object in place: a changed risk must still reach the next delta.
    fc.update([score_row(2, 0.9, made_at=now)], [], {"gap-3-1"}, now)
    hub.on_forecast(fc)
    by = {v["mmsi"]: v for v in hub.live.take_changes(now, 1800)[0]}
    assert set(by) == {1, 2} and by[2]["risk_rank"] == 1 and by[1]["risk_rank"] == 2
    assert hub.pending_watchlist["entries"][0]["mmsi"] == 2 and hub.pending_watchlist["entries"][0]["prev_rank"] == 2
    hub.live.forecast = None
    assert "risk_p" in hub.live.view(1) and hub.live.view(1)["risk_p"] is None   # PREDICT off: as before


def test_outcome_and_coverage_shapes():
    o = outcome_ts({"score_id": "s", "mmsi": 1, "made_at": T, "resolved_at": T + 7 * H, "label": None,
                    "censored": "unknown", "lead_s": None})
    assert_shape(o, "Outcome")
    assert o["label"] == "miss" and o["censored"] == "coverage_gap"
    hit = outcome_ts({"score_id": "s", "mmsi": 1, "made_at": T, "resolved_at": T, "label": True, "censored": None,
                      "lead_s": 60})
    assert hit["label"] == "hit" and hit["lead_s"] == 60
    spans = coverage_spans(T, T + 10 * H, T - H, T + 5 * H, [(T + H, T + 2 * H), (T + 20 * H, T + 21 * H)])
    assert [(s["start_ts"] - T, s["end_ts"] - T, s["state"]) for s in spans] == [
        (0, H, "data"), (H, 2 * H, "own_stall"), (2 * H, 5 * H, "data")]
    kinds = ts_union("TimelineEvent")
    for s in spans:
        assert set(s) == kinds["coverage"]
    assert coverage_spans(None, None, T, T + H, []) == []
