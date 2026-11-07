"""ReplaySession against an in-memory history: seek builds the state at t, play advances the replay clock."""
import asyncio

from dvm import config, replay

T0 = 1_794_070_000_000   # the first stored position, epoch ms


def pos(mmsi, t, lat, lon=20.0):
    return {"mmsi": mmsi, "ts": t, "recv_ts": t, "lat": lat, "lon": lon, "sog_kn": 10.0, "cog_deg": 90.0,
            "heading_deg": 90, "nav_status": 0, "cls": "A", "msg_type": 1, "ts_quality": "rebuilt",
            "src": "aisstream", "q": []}


class FakeHistory:
    def __init__(self, positions, identities=None):
        self.positions, self.ids = positions, identities or {}

    async def range(self):
        times = [p["ts"] for p in self.positions]
        return (min(times), max(times)) if times else (None, None)

    async def latest_positions(self, t, window_s):
        latest = {}
        for p in sorted(self.positions, key=lambda p: p["ts"]):
            if t - window_s * 1000 < p["ts"] <= t:
                latest[p["mmsi"]] = p
        return list(latest.values())

    async def identities(self, t, window_s):
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
