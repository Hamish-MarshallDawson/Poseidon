"""Gap detector under switch-offs, coverage holes, outages, stalls, jamming, loss, skew and duplicates.

Targets Jake's dvm/gaps.py through adapter.py, and skips until it is merged. To check the tests themselves,
run with --detector reference (a small checker that follows 06 rules; not the product detector).
Thresholds assumed from 06: floor 1800 s, k 20, neighbours within 20 km, at least 3 heard.
"""
from __future__ import annotations

import random

import pytest

from tests.stress import harness, synth
from tests.stress.adapter import FLAGS, GAP_FIELDS
from tests.stress.synth import T0_MS, Faults, Window

pytestmark = pytest.mark.stress

MIN = 60_000
FLOOR_MS = 1800 * 1000


def scenario(scale, seed, faults, *, convoy_n=8, lone=False):
    """Background fleet + a convoy around a target (first convoy ship) + optionally a lone ship far out at sea."""
    rng = random.Random(seed)
    bg = synth.background(scale["ships"], rng, scale["interval_s"])
    cv = synth.convoy(convoy_n, 60.0, 25.5, rng, scale["interval_s"], start=10_000)
    ships = bg + cv
    lone_ship = None
    if lone:
        lone_ship = synth.Ship(synth.mmsi_for(20_000), 61.6, 21.0, 9, 45, scale["interval_s"], name="LONE", bounded=False)
        ships.append(lone_ship)
    return ships, cv, lone_ship


def run(scale, seed, ships, faults, detector):
    w = synth.World(ships, scale["hours"] * 3600, faults, seed=seed)
    stream, truth = w.emit()
    res = harness.run(stream, detector, stalls=faults.stalls, end_ms=T0_MS + int(scale["hours"] * 3_600_000))
    return res, truth


def check_shape(gaps):
    for g in gaps.values():
        missing = GAP_FIELDS - g.keys()
        assert not missing, f"GapEvent missing {missing}"
        assert g["coverage_flag"] in FLAGS and g["state"] in {"open", "closed"}
        assert g["id"] == f"gap-{g['mmsi']}-{g['start_ts']}"


def window(start_min, length_min):
    return Window(T0_MS + start_min * MIN, T0_MS + (start_min + length_min) * MIN)


# ---------- true positives ----------

def test_lone_switch_off_among_neighbours_is_deliberate(scale, seed, detector):
    ships, cv, _ = scenario(scale, seed, None)
    target = cv[0].mmsi
    off = window(40, 60)
    res, truth = run(scale, seed, ships, Faults(switch_off={target: off}), detector)
    gaps = res.gaps()
    check_shape(gaps)
    mine = [g for g in gaps.values() if g["mmsi"] == target]
    assert len(mine) == 1, f"expected one gap for the target, got {len(mine)}"
    g = mine[0]
    last_before = max(t for t, *_ in truth["fixes"][target] if t < off.start_ms) // 1000 * 1000
    first_after = min(t for t, *_ in truth["fixes"][target] if t >= off.end_ms) // 1000 * 1000
    assert g["coverage_flag"] == "deliberate_candidate", g
    assert g["neighbours_heard"] >= 3
    assert g["start_ts"] == last_before
    assert g["state"] == "closed" and g["end_ts"] == first_after
    assert FLOOR_MS <= g["detected_at"] - g["start_ts"] <= FLOOR_MS + 2 * MIN, "raised too early or too late"
    true_kn = synth.km_between(g["last_lat"], g["last_lon"], g["next_lat"], g["next_lon"]) / 1.852 / ((first_after - last_before) / 3.6e6)
    assert g["implied_speed_kn"] == pytest.approx(true_kn, rel=0.05)
    others = [x for x in gaps.values() if x["mmsi"] != target and x["coverage_flag"] == "deliberate_candidate"]
    assert not others, f"false deliberate gaps on {len(others)} other ships"


def test_open_sea_with_no_neighbours_is_unknown(scale, seed, detector):
    ships, _, lone = scenario(scale, seed, None, lone=True)
    res, _ = run(scale, seed, ships, Faults(switch_off={lone.mmsi: window(40, 60)}), detector)
    mine = [g for g in res.gaps().values() if g["mmsi"] == lone.mmsi]
    assert len(mine) == 1 and mine[0]["coverage_flag"] == "unknown", mine


# ---------- must NOT be called deliberate ----------

HOLE_KM, RADIUS_KM = 45.0, 20.0


def _hole_run(scale, seed, detector):
    ships, cv, _ = scenario(scale, seed, None)
    lat, lon = sum(s.lat for s in cv) / len(cv), sum(s.lon for s in cv) / len(cv)
    res, _ = run(scale, seed, ships, Faults(holes=[(lat, lon, HOLE_KM, window(40, 60))]), detector)
    gaps = res.gaps()
    check_shape(gaps)
    depth = {gid: HOLE_KM - synth.km_between(lat, lon, g["last_lat"], g["last_lon"]) for gid, g in gaps.items()}
    return gaps, depth, cv


def test_coverage_hole_is_coverage_gap(scale, seed, detector):
    """Ships deeper than the neighbour radius inside a receiver hole: no neighbour can be heard, never deliberate."""
    gaps, depth, cv = _hole_run(scale, seed, detector)
    deep = [g for gid, g in gaps.items() if depth[gid] > RADIUS_KM]
    assert any(g["mmsi"] in {s.mmsi for s in cv} for g in deep), "the hole should produce gaps for the convoy"
    bad = [g for g in deep if g["coverage_flag"] == "deliberate_candidate"]
    assert not bad, f"{len(bad)} ships deep inside a receiver hole were called deliberate"


@pytest.mark.xfail(strict=False, reason="Known limit of the 06 neighbour test: a ship within 20 km of the hole edge "
                   "still hears neighbours outside it. Passes only if the detector also uses the coverage cell state.")
def test_coverage_hole_edge_is_not_deliberate(scale, seed, detector):
    gaps, depth, _ = _hole_run(scale, seed, detector)
    edge = [g for gid, g in gaps.items() if 0 <= depth[gid] <= RADIUS_KM and g["coverage_flag"] == "deliberate_candidate"]
    assert not edge, f"{len(edge)} ships near the hole edge called deliberate"


def test_receiver_outage_of_whole_area_is_never_deliberate(scale, seed, detector):
    ships, _, _ = scenario(scale, seed, None)
    res, _ = run(scale, seed, ships, Faults(outages=[window(40, 45)]), detector)
    gaps = res.gaps()
    check_shape(gaps)
    deliberate = [g for g in gaps.values() if g["coverage_flag"] == "deliberate_candidate"]
    assert not deliberate, f"outage: {len(deliberate)} of {len(gaps)} gaps called deliberate"


def test_own_ingest_stall_is_own_stall(scale, seed, detector):
    ships, _, _ = scenario(scale, seed, None)
    res, _ = run(scale, seed, ships, Faults(stalls=[window(40, 45)]), detector)
    gaps = res.gaps()
    assert gaps, "a 45 min stall should open gaps"
    flags = {g["coverage_flag"] for g in gaps.values()}
    assert flags == {"own_stall"}, f"stall gaps flagged {flags}"


def test_jamming_moves_positions_but_opens_no_gaps(scale, seed, detector):
    ships, cv, _ = scenario(scale, seed, None)
    lat, lon = cv[0].lat, cv[0].lon
    res, _ = run(scale, seed, ships, Faults(jams=[(lat, lon, 40.0, window(30, 60))]), detector)
    assert not res.gaps(), "ships still transmitting must not get gaps"


def test_busy_lossy_traffic_opens_no_gaps(scale, seed, detector):
    """30% random loss, Class B ships reporting every 3 min, interval jitter: nobody actually went silent."""
    ships, _, _ = scenario(scale, seed, None)
    for s in ships[::3]:
        s.cls, s.interval_s = "B", 180
    res, _ = run(scale, seed, ships, Faults(loss_p=0.3, interval_jitter=0.3), detector)
    assert not res.gaps(), f"{len(res.gaps())} false gaps"


# ---------- delivery faults on top of a real switch-off ----------

@pytest.mark.parametrize("skew_s", [-120, 120])
def test_switch_off_found_despite_clock_skew(scale, seed, detector, skew_s):
    ships, cv, _ = scenario(scale, seed, None)
    target = cv[0].mmsi
    res, _ = run(scale, seed, ships, Faults(switch_off={target: window(40, 60)}, skew_s=skew_s), detector)
    gaps = res.gaps()
    assert [g["coverage_flag"] for g in gaps.values() if g["mmsi"] == target] == ["deliberate_candidate"]
    assert all(g["mmsi"] == target for g in gaps.values()), "skew produced false gaps"


def test_duplicates_and_reordering_give_one_gap(scale, seed, detector):
    ships, cv, _ = scenario(scale, seed, None)
    target = cv[0].mmsi
    res, _ = run(scale, seed, ships, Faults(switch_off={target: window(40, 60)}, dup_p=0.3, reorder_s=15), detector)
    mine = [g for g in res.gaps().values() if g["mmsi"] == target]
    assert len(mine) == 1 and mine[0]["coverage_flag"] == "deliberate_candidate", mine


def test_many_simultaneous_switch_offs_scale(scale, seed, detector):
    """A quarter of the background fleet switches off at staggered times: every one is found, and it keeps up."""
    ships, _, _ = scenario(scale, seed, None)
    rng = random.Random(seed)
    bg = ships[: scale["ships"]]
    chosen = rng.sample(bg, len(bg) // 4)
    faults = Faults(switch_off={s.mmsi: window(35 + rng.randint(0, 20), 50) for s in chosen})
    res, _ = run(scale, seed, ships, faults, detector)
    found = {g["mmsi"] for g in res.gaps().values()}
    missed = {s.mmsi for s in chosen} - found
    assert not missed, f"{len(missed)} of {len(chosen)} switch-offs not raised"
    sim_s = scale["hours"] * 3600
    assert res.seconds < sim_s / 50, f"detector + ingest ran at only {sim_s / res.seconds:.0f}x real time"
