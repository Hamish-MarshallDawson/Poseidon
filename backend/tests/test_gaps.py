"""Gap detector (dvm/gaps.py) and the map state it drives (dvm/live.py): no network, no database."""
from dvm import store
from dvm.gaps import GapDetector, cell_id, haversine_km
from dvm.live import GAP_KEEP_MS, Live
from dvm.models import PositionReport

T0 = 1_794_000_000_000
MIN = 60_000
TARGET = 230_000_001


def fix(mmsi, t, lat, lon, sog=10.0, cls="A", nav=0, ts=None):
    return PositionReport(mmsi=mmsi, ts=t if ts is None else ts, recv_ts=t, lat=lat, lon=lon, sog_kn=sog, cog_deg=90.0,
                          cls=cls, ts_quality="source", src="aisstream", nav_status=nav)


def run(det, minutes, ships, silent=lambda m, t: False, step_s=30, tick_s=5, start=0):
    """ships: {mmsi: (lat, lon, sog)}; each reports every step_s unless silent(mmsi, t). Returns every gap version."""
    out = []
    t = T0 + start * MIN
    end = T0 + minutes * MIN
    next_tick = t
    while t <= end:
        while next_tick <= t:
            out += det.tick(next_tick)
            next_tick += tick_s * 1000
        for m, (lat, lon, sog) in ships.items():
            if not silent(m, t):
                lon_now = lon + (t - T0) / 3_600_000 * sog / 60   # a little eastward drift at sog
                out += det.observe(fix(m, t, lat, lon_now, sog))
        t += step_s * 1000
    return out


def latest(versions):
    best = {}
    for g in versions:
        if g["id"] not in best or g["version"] >= best[g["id"]]["version"]:
            best[g["id"]] = g
    return best


def fleet(n=6, lat=60.0, lon=25.0, sog=10.0):
    ships = {TARGET: (lat, lon, sog)}
    for i in range(1, n + 1):
        ships[TARGET + i] = (lat + 0.02 * i, lon + 0.01 * i, sog)   # within a few km of the target
    return ships


def off_between(a_min, b_min, who=TARGET):
    return lambda m, t: m == who and T0 + a_min * MIN <= t < T0 + b_min * MIN


def test_switch_off_among_neighbours_opens_then_closes_deliberate():
    gaps = latest(run(GapDetector(), 120, fleet(), off_between(30, 90)))
    mine = [g for g in gaps.values() if g["mmsi"] == TARGET]
    assert len(mine) == 1
    g = mine[0]
    assert g["coverage_flag"] == "deliberate_candidate"
    assert g["state"] == "closed" and g["end_ts"] >= T0 + 90 * MIN
    assert g["id"] == f"gap-{TARGET}-{g['start_ts']}"
    assert g["start_ts"] < T0 + 30 * MIN and g["neighbours_heard"] >= 3 and g["neighbours_baseline"] >= 3
    assert g["duration_s"] == (g["end_ts"] - g["start_ts"]) // 1000
    km = haversine_km(g["last_lat"], g["last_lon"], g["next_lat"], g["next_lon"])
    assert abs(g["implied_speed_kn"] - km / 1.852 / (g["duration_s"] / 3600)) < 1e-6
    assert g["cell_id"] == cell_id(g["last_lat"], g["last_lon"])
    assert set(store.APPEND_COLS["gaps"]) <= g.keys()   # every column the gaps table needs
    assert not [x for x in gaps.values() if x["mmsi"] != TARGET], "neighbours that kept reporting got gaps"


def test_gap_opens_after_the_30_minute_floor_not_before():
    versions = run(GapDetector(), 70, fleet(), off_between(10, 200))
    opened = [g for g in versions if g["mmsi"] == TARGET and g["version"] == 1]
    assert len(opened) == 1
    assert 30 * MIN < opened[0]["detected_at"] - opened[0]["start_ts"] <= 30 * MIN + 10_000


def test_ships_not_moving_get_no_gap():
    for sog, nav in ((0.2, 0), (10.0, 1), (10.0, 5), (None, 0)):   # stopped, at anchor, moored, speed unknown
        ships = fleet()
        ships[TARGET] = (60.0, 25.0, sog)
        det = GapDetector()
        versions = []
        for t in range(T0, T0 + 90 * MIN, 30_000):
            versions += det.tick(t)
            for m, (lat, lon, s) in ships.items():
                if m != TARGET or t < T0 + 10 * MIN:
                    versions += det.observe(fix(m, t, lat, lon, s, nav=nav if m == TARGET else 0))
        assert not [g for g in versions if g["mmsi"] == TARGET], (sog, nav)


def test_class_b_ships_are_never_tracked():
    det = GapDetector()
    det.observe(fix(TARGET, T0, 60.0, 25.0, cls="B"))
    assert det.tick(T0 + 120 * MIN) == [] and TARGET not in det.ships


def test_a_ship_that_ever_sent_class_a_is_class_a():
    det = GapDetector()
    det.observe(fix(TARGET, T0, 60.0, 25.0, cls="A"))
    det.observe(fix(TARGET, T0 + MIN, 60.0, 25.01, cls="B"))
    assert det.ships[TARGET].ts == T0 + MIN


def test_open_sea_without_neighbours_is_unknown():
    gaps = latest(run(GapDetector(), 90, {TARGET: (61.0, 20.0, 10.0)}, off_between(10, 80)))
    assert [g["coverage_flag"] for g in gaps.values()] == ["unknown"]


def test_too_few_neighbours_heard_is_coverage_gap():
    gaps = latest(run(GapDetector(), 90, fleet(n=2), off_between(10, 80)))
    assert [g["coverage_flag"] for g in gaps.values() if g["mmsi"] == TARGET] == ["coverage_gap"]


def test_whole_area_going_quiet_is_never_deliberate():
    gaps = latest(run(GapDetector(), 120, fleet(n=8), lambda m, t: T0 + 20 * MIN <= t < T0 + 80 * MIN))
    assert gaps and {g["coverage_flag"] for g in gaps.values()} <= {"coverage_gap", "unknown"}


def test_a_stall_noted_later_turns_an_open_gap_into_own_stall_only_if_it_explains_it():
    det = GapDetector()
    versions = run(det, 60, fleet(), off_between(10, 999))
    assert latest(versions)[next(iter(det.open.values()))["id"]]["coverage_flag"] == "deliberate_candidate"
    assert det.note_stall(T0 + 15 * MIN, T0 + 18 * MIN) == []   # 3 of the 50 silent minutes: not explained
    more = det.note_stall(T0 + 12 * MIN, T0 + 55 * MIN)           # now only 2 + 5 minutes are left outside
    assert [g["coverage_flag"] for g in more] == ["own_stall"] and more[0]["version"] == 2


def test_future_dated_fix_is_ignored():
    det = GapDetector()
    det.observe(fix(TARGET, T0, 60.0, 25.0))
    det.observe(fix(TARGET, T0 + MIN, 60.0, 25.01, ts=T0 + 10 * 3_600_000))
    assert det.ships[TARGET].ts == T0 and det.stats["ignored_future"] == 1


def test_resume_carries_versions_on_and_warm_closes_a_gap_whose_ship_came_back():
    det = GapDetector()
    stored = {"id": f"gap-{TARGET}-{T0}", "version": 3, "mmsi": TARGET, "state": "open", "start_ts": T0,
              "end_ts": None, "last_lat": 60.0, "last_lon": 25.0, "coverage_flag": "deliberate_candidate",
              "neighbours_heard": 4, "neighbours_baseline": 5, "duration_s": 0}
    assert len(det.resume([stored, {**stored, "id": "gap-1-1", "mmsi": 1, "state": "closed"}])) == 1
    closed = det.warm([fix(TARGET, T0 + 50 * MIN, 60.0, 25.2)])
    assert [(g["id"], g["version"], g["state"]) for g in closed] == [(stored["id"], 4, "closed")]


# ---- the map state (dvm/live.py) ----

def gap(mmsi, state="open", version=1, end=None):
    return {"id": f"gap-{mmsi}-{T0}", "version": version, "mmsi": mmsi, "state": state, "start_ts": T0, "end_ts": end}


def test_open_gap_keeps_the_ship_on_the_map_marked_gap_open():
    live = Live()
    live.apply(fix(TARGET, T0, 60.0, 25.0))
    live.take_changes(T0, 1800)
    live.apply_gaps([gap(TARGET)])
    changed, removed = live.take_changes(T0 + 2 * 3_600_000, 1800)   # well past the 30 min stale limit
    assert removed == [] and changed[0]["status"] == "gap_open" and changed[0]["open_gap_id"] == f"gap-{TARGET}-{T0}"
    assert live.detail(TARGET)["gaps"][0]["state"] == "open"
    assert live.snapshot_gaps(T0)[0]["id"] == f"gap-{TARGET}-{T0}"


def test_ship_leaves_the_map_after_24_h_or_once_the_gap_closes_and_it_goes_stale():
    live = Live()
    live.apply(fix(TARGET, T0, 60.0, 25.0))
    live.apply_gaps([gap(TARGET)])
    assert live.take_changes(T0 + GAP_KEEP_MS + 1, 1800)[1] == [TARGET]
    live = Live()
    live.apply(fix(TARGET, T0, 60.0, 25.0))
    live.apply_gaps([gap(TARGET), gap(TARGET, "closed", 2, T0 + MIN)])
    assert live.view(TARGET)["status"] == "active"
    assert live.take_changes(T0 + 31 * MIN, 1800)[1] == [TARGET]


def test_an_older_version_never_replaces_a_newer_one():
    live = Live()
    live.apply_gaps([gap(TARGET, "closed", 2, T0 + MIN), gap(TARGET, "open", 1)])
    assert live.gaps[f"gap-{TARGET}-{T0}"]["state"] == "closed" and TARGET not in live.open_gap


def test_gap_rows_fit_the_gaps_table_and_repeat_writes_are_skipped():
    g = latest(run(GapDetector(), 120, fleet(), off_between(30, 90)))
    row = store.append_args("gaps", next(iter(g.values())))
    assert len(row) == len(store.APPEND_COLS["gaps"])
    assert store.GAPS_INSERT.endswith("ON CONFLICT (id, version) DO NOTHING")


def test_a_short_restart_does_not_explain_a_long_silence():
    det = GapDetector()
    det.note_stall(T0 + 50 * MIN, T0 + 50 * MIN + 10_000)   # a 10 s deploy restart, 40 min into the silence
    gaps = latest(run(det, 120, fleet(), off_between(10, 100)))
    assert [g["coverage_flag"] for g in gaps.values() if g["mmsi"] == TARGET] == ["deliberate_candidate"]


def test_an_outage_covering_most_of_the_silence_is_own_stall():
    det = GapDetector()
    det.note_stall(T0 + 12 * MIN, T0 + 70 * MIN)   # only 2 + 10 min of the 70 min silence fall outside it
    gaps = latest(run(det, 120, fleet(), off_between(10, 80)))
    assert [g["coverage_flag"] for g in gaps.values() if g["mmsi"] == TARGET] == ["own_stall"]


def test_an_open_own_stall_gap_is_judged_normally_once_it_outgrows_the_outage():
    det = GapDetector()
    det.note_stall(T0 + 12 * MIN, T0 + 40 * MIN)
    versions = run(det, 110, fleet(), off_between(10, 999))
    flags = [g["coverage_flag"] for g in versions if g["mmsi"] == TARGET]
    assert flags[0] == "own_stall" and flags[-1] == "deliberate_candidate"


def test_a_ship_whose_speed_jitters_but_stays_put_gets_no_gap():
    """In port the reported speed can read over 1 kn while the position doesn't move."""
    det = GapDetector()
    versions = []
    for t in range(T0, T0 + 90 * MIN, 30_000):
        versions += det.tick(t)
        for m, (lat, lon, _) in fleet().items():
            if m == TARGET and t >= T0 + 15 * MIN:
                continue
            versions += det.observe(fix(m, t, lat, lon if m == TARGET else lon + (t - T0) / 3.6e6 / 6, 2.5))
    assert not [g for g in versions if g["mmsi"] == TARGET] and det.stats["not_moving"] >= 1
