"""ReplaySession against an in-memory history: seek builds the state at t, play advances the replay clock."""
import asyncio

from dvm import config, replay

T0 = 1_794_070_000_000   # the first stored position, epoch ms


def pos(mmsi, t, lat, lon=20.0):
    return {"mmsi": mmsi, "ts": t, "recv_ts": t, "lat": lat, "lon": lon, "sog_kn": 10.0, "cog_deg": 90.0,
            "heading_deg": 90, "nav_status": 0, "cls": "A", "msg_type": 1, "ts_quality": "rebuilt",
            "src": "aisstream", "q": []}


class FakeHistory:
    """The SQL in replay.TigerHistory, in Python."""

    def __init__(self, positions, identities=None, gaps=(), scores=(), routes=()):
        self.positions, self.ids = positions, identities or {}
        self.gaps, self.score_rows, self.route_rows = list(gaps), list(scores), list(routes)

    async def last_positions_of(self, mmsis, t, since):
        return [p for p in await self.latest_positions(t, (t - since) // 1000) if p["mmsi"] in mmsis]

    async def gap_versions(self, a, b):
        known = lambda g: max(g["detected_at"], g["start_ts"] + g["duration_s"] * 1000)   # noqa: E731
        newest = {}
        for g in sorted(self.gaps, key=lambda g: g["version"]):
            if b - replay.GAP_LOOKBACK_MS < g["detected_at"] <= b and (a is None or a < known(g)) and known(g) <= b:
                newest[g["id"]] = g
        return list(newest.values())

    async def scores(self, a, b):
        newest = {}
        for r in sorted(self.score_rows, key=lambda r: r["made_at"]):
            if a < r["made_at"] <= b:
                newest[(r["mmsi"], r["target"])] = r
        return list(newest.values())

    async def routes(self, a, b, gap_ids=None):
        return [r for r in self.route_rows if a < r["made_at"] <= b and r["gap_id"]
                and (gap_ids is None or r["gap_id"] in gap_ids)]

    async def range(self):
        times = [p["ts"] for p in self.positions]
        return (min(times), max(times)) if times else (None, None)

    async def latest_positions(self, t, window_s):
        latest = {}
        for p in sorted(self.positions, key=lambda p: p["ts"]):
            if t - window_s * 1000 < p["ts"] <= t:
                latest[p["mmsi"]] = p
        return list(latest.values())

    async def identities(self, t, window_s, extra=()):
        return dict(self.ids)

    async def between(self, a, b):
        return sorted((p for p in self.positions if a < p["ts"] <= b), key=lambda p: p["ts"]), []


def session(history):
    sent = []

    async def send(m):
        sent.append(m)

    async def no_sleep(_):
        return None

    return replay.ReplaySession(history, send, sleep=no_sleep), sent


DATA = [pos(230000001, T0, 60.0), pos(230000001, T0 + 60_000, 60.1), pos(230000001, T0 + 120_000, 60.2),
        pos(244000002, T0 + 30_000, 59.5)]


def test_seek_builds_the_state_at_t():
    async def main():
        s, sent = session(FakeHistory(DATA, {230000001: {"name": "ALPHA", "type_group": "tanker"}}))
        await s.seek(T0 + 60_000)
        status, snap = sent
        assert status["type"] == "status" and status["mode"] == "replay" and status["paused"] is True
        assert status["replay"] == {"from_ts": T0, "to_ts": T0 + 120_000}
        assert snap["type"] == "snapshot" and snap["now_ts"] == T0 + 60_000
        ships = {v["mmsi"]: v for v in snap["vessels"]}
        assert ships[230000001]["lat"] == 60.1 and ships[230000001]["name"] == "ALPHA"   # latest at or before t
        assert ships[244000002]["lat"] == 59.5
    asyncio.run(main())


def test_seek_is_clamped_to_the_stored_range():
    async def main():
        s, sent = session(FakeHistory(DATA))
        await s.seek(T0 - 10**9)
        assert sent[-1]["now_ts"] == T0
        await s.seek(None)   # no t: the newest stored time
        assert sent[-1]["now_ts"] == T0 + 120_000
    asyncio.run(main())


def test_step_advances_by_speed_and_pauses_at_the_end():
    async def main():
        s, sent = session(FakeHistory(DATA))
        await s.seek(T0)
        await s.set_speed(60)
        s.playing = True
        assert await s.step() is False
        delta = sent[-1]
        assert delta["type"] == "delta" and delta["now_ts"] == T0 + 60_000
        assert [v["lat"] for v in delta["vessels"] if v["mmsi"] == 230000001] == [60.1]
        assert await s.step() is True   # reached the newest stored time
        assert sent[-1]["type"] == "status" and sent[-1]["paused"] is True and s.playing is False
    asyncio.run(main())


def test_speed_is_clamped_and_bad_values_ignored():
    async def main():
        s, sent = session(FakeHistory(DATA))
        await s.set_speed(10_000)
        assert s.speed == replay.MAX_SPEED
        await s.set_speed(0)
        assert s.speed == 1
        await s.set_speed("fast")
        assert s.speed == 1 and sent[-1]["type"] == "status"
    asyncio.run(main())


def test_ships_silent_too_long_drop_out_of_replay():
    async def main():
        late = DATA + [pos(230000001, T0 + config.STALE_AFTER_S * 1000 + 120_000, 60.5)]
        s, sent = session(FakeHistory(late))
        await s.seek(T0 + 120_000)
        await s.set_speed(replay.MAX_SPEED)   # 10 min per step; the stale window is longer, so step until past it
        for _ in range(10):
            if await s.step():
                break
        removed = {m for msg in sent if msg["type"] == "delta" for m in msg["removed"]}
        assert 244000002 in removed            # last heard at T0 + 30 s, then silent past the stale window
        assert 230000001 not in removed        # heard again before the window ran out
    asyncio.run(main())


class FakePool:
    def __init__(self):
        self.out = self.peak = 0

    async def acquire(self):
        self.out += 1
        self.peak = max(self.peak, self.out)
        await asyncio.sleep(0.01)
        return object()

    async def release(self, con):
        self.out -= 1


def test_replay_queries_take_turns_on_one_connection():
    """The store's writer needs the pool's other connection: replay must never hold both."""
    async def main():
        pool = FakePool()

        async def query():
            async with replay.TigerHistory(pool)._con():
                await asyncio.sleep(0.01)
        await asyncio.gather(*(query() for _ in range(5)))
        return pool.peak
    assert asyncio.run(main()) == 1


class BrokenHistory(FakeHistory):
    async def between(self, a, b):
        raise ConnectionError("Tiger went away")


def test_playback_error_pauses_and_tells_the_client():
    async def main():
        s, sent = session(BrokenHistory(DATA))
        await s.seek(T0)
        await s.play()
        await asyncio.sleep(0.05)
        assert s.playing is False
        assert sent[-1]["type"] == "status" and sent[-1]["paused"] is True
    asyncio.run(main())


def test_failed_first_seek_leaves_the_client_live(monkeypatch):
    from dvm import app as app_mod

    class NoRange(FakeHistory):
        async def range(self):
            raise ConnectionError("Tiger went away")

    class FakeHub:
        store = type("S", (), {"pool": object()})()

        def sources(self):
            return []

    class C:
        replay, lock = None, asyncio.Lock()

        async def send(self, m):
            pass

    monkeypatch.setattr(app_mod, "hub", FakeHub(), raising=False)
    monkeypatch.setattr(replay, "TigerHistory", lambda pool: NoRange(DATA))
    c = C()
    try:
        asyncio.run(app_mod.handle_replay(c, {"type": "replay", "action": "seek", "t": T0}))
    except ConnectionError:
        pass
    assert c.replay is None   # still gets live deltas instead of a frozen map


# ---- gaps, go-dark risk and route predictions as known at the replay time (#121) ----

M = 60_000
SHIP, OTHER = 230000001, 244000002


def gap(version, state, detected_at, known_at, end_ts=None, flag="deliberate_candidate", start=T0 + 2 * M):
    return {"id": f"gap-{SHIP}-{start}", "version": version, "mmsi": SHIP, "state": state, "start_ts": start,
            "end_ts": end_ts, "detected_at": detected_at, "duration_s": (known_at - start) // 1000,
            "expected_interval_s": 10.0, "last_lat": 60.2, "last_lon": 20.0, "last_sog_kn": 10.0,
            "last_cog_deg": 90.0, "last_nav_status": 0, "next_lat": None, "next_lon": None, "implied_speed_kn": None,
            "draught_before_m": None, "draught_after_m": None, "neighbours_heard": 5, "neighbours_baseline": 5,
            "cell_id": "c", "coverage_flag": flag, "src": "derived", "gfw_intentional": None, "q": []}


def score(mmsi, made_at, p, mode="backtest"):
    return {"id": f"s-{mmsi}-{made_at}", "mmsi": mmsi, "target": "dark_6h", "made_at": made_at, "horizon_s": 21600,
            "p": p, "model_version": "godark-test", "feature_version": "f1", "features": {"sog": 10.0},
            "contrib": {}, "mode": mode}


def route(made_at, horizon_s, lat):
    return {"id": f"r-{made_at}-{horizon_s}", "mmsi": SHIP, "made_at": made_at, "as_of": T0 + 2 * M,
            "model_version": "route-test", "horizon_s": horizon_s, "lat": lat, "lon": 20.5, "radius_m_80": 5000.0,
            "radius_m_95": 9000.0, "base_lat": lat, "base_lon": 20.4, "gap_id": f"gap-{SHIP}-{T0 + 2 * M}",
            "feature_version": "f1", "mode": "backtest"}


# SHIP reports until T0 + 2 min, a gap is detected at +35 min and closes when it reappears at +90 min. OTHER keeps
# reporting. Scores at +10 and +50 min, route predictions at +40 and +100 min (the second after the close).
TRACK = ([pos(SHIP, T0 + i * M, 60.0 + i / 100) for i in range(3)] + [pos(SHIP, T0 + 90 * M, 60.9)]
         + [pos(OTHER, T0 + i * 5 * M, 59.5) for i in range(40)])
GAPS = [gap(1, "open", T0 + 35 * M, T0 + 35 * M, flag="unknown"),
        gap(2, "open", T0 + 35 * M, T0 + 45 * M),                          # re-check: now deliberate
        gap(3, "closed", T0 + 35 * M, T0 + 90 * M, end_ts=T0 + 90 * M)]
SCORES = [score(SHIP, T0 + 10 * M, 0.3), score(OTHER, T0 + 10 * M, 0.1, mode="live"),
          score(OTHER, T0 + 50 * M, 0.6)]
ROUTES = [route(T0 + 40 * M, 3600, 60.4), route(T0 + 40 * M, 10800, 60.7), route(T0 + 100 * M, 3600, 61.0)]
GID = f"gap-{SHIP}-{T0 + 2 * M}"


def history():
    return FakeHistory(TRACK, {SHIP: {"name": "ALPHA"}}, GAPS, SCORES, ROUTES)


def ships(msg):
    return {v["mmsi"]: v for v in msg["vessels"]}


def test_seek_shows_gaps_risk_and_predictions_known_at_t():
    async def main():
        s, sent = session(history())
        await s.seek(T0 + 60 * M)
        snap = sent[-1]
        [g] = snap["gaps"]
        assert g["id"] == GID and g["state"] == "open" and g["version"] == 2   # the close at +90 min is not known yet
        assert (g["pred_lat"], g["pred_horizon_s"], g["pred_model"]) == (60.4, 3600, "route-test")
        v = ships(snap)
        assert v[SHIP]["status"] == "gap_open" and v[SHIP]["open_gap_id"] == GID   # silent 58 min, kept by its gap
        assert (v[SHIP]["risk_p"], v[SHIP]["risk_rank"]) == (0.3, 2)
        assert (v[OTHER]["risk_p"], v[OTHER]["risk_rank"]) == (0.6, 1)             # newest score by t, any mode
        wl = snap["watchlist"]["entries"]
        assert [e["mmsi"] for e in wl] == [OTHER, SHIP]
        assert "OPEN_GAP" in wl[1]["reason_codes"] and wl[1]["decision"] in ("watch", "inspect")
    asyncio.run(main())


def test_seek_before_anything_was_known_has_none_of_it():
    async def main():
        s, sent = session(history())
        await s.seek(T0 + 5 * M)
        snap = sent[-1]
        assert snap["gaps"] == [] and snap["watchlist"]["entries"] == []
        assert all(v["risk_p"] is None and v["status"] == "active" for v in snap["vessels"])
    asyncio.run(main())


def test_seek_after_the_close_shows_the_closed_gap_for_an_hour():
    async def main():
        s, sent = session(history())
        await s.seek(T0 + 100 * M)
        [g] = sent[-1]["gaps"]
        assert g["state"] == "closed" and "pred_lat" not in g
        assert ships(sent[-1])[SHIP]["status"] == "active"
        await s.seek(T0 + 151 * M)
        assert sent[-1]["gaps"] == []
    asyncio.run(main())


def test_play_carries_gap_risk_and_prediction_changes_in_deltas():
    async def main():
        s, sent = session(history())
        await s.seek(T0 + 30 * M)
        assert sent[-1]["gaps"] == []
        await s.set_speed(300)   # 5 min a step
        deltas = []
        for _ in range(14):     # to +100 min
            n = len(sent)
            await s.step()
            deltas += [m for m in sent[n:] if m["type"] == "delta"]
        at = {d["now_ts"]: d for d in deltas}
        opened = at[T0 + 35 * M]
        assert [(g["id"], g["version"], g["state"]) for g in opened["gaps"]] == [(GID, 1, "open")]
        assert ships(opened)[SHIP]["status"] == "silent"           # coverage flag unknown at first
        assert ships(at[T0 + 45 * M])[SHIP]["status"] == "gap_open"
        [p] = at[T0 + 40 * M]["gaps"]
        assert p["pred_lat"] == 60.4                                # the prediction arrives on the open gap
        risk = at[T0 + 50 * M]
        assert ships(risk)[OTHER]["risk_p"] == 0.6 and risk["watchlist"]["entries"][0]["mmsi"] == OTHER
        closed = at[T0 + 90 * M]
        assert closed["gaps"][0]["state"] == "closed" and ships(closed)[SHIP]["status"] == "active"
        assert at[T0 + 70 * M]["watchlist"] is not None             # SHIP's +10 min score aged out after an hour
        assert all(not d["gaps"] for d in deltas if d["now_ts"] == T0 + 100 * M)   # post-close prediction: no gap
    asyncio.run(main())
