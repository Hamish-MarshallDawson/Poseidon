"""The gap warm start waits for the store's setup (its tables) before reading Tiger (#82)."""
from __future__ import annotations

import asyncio

import pytest

from dvm import app as app_mod, config


class SlowStore:
    """Like Store: `pool` is set only once setup has created the tables."""
    url = "postgresql://unused"

    def __init__(self):
        self.pool = None


@pytest.fixture
def hub(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "DATA_DIR", tmp_path)
    monkeypatch.setattr(config, "TIGER_DATABASE_URL", "")
    monkeypatch.setattr(config, "DIGITRAFFIC", False)
    monkeypatch.setattr(app_mod, "WARM_POLL_S", 0.01)
    h = app_mod.Hub()
    h.store, h.gaps_warm = SlowStore(), "pending"
    yield h
    h.rawlog.close()


def test_warm_start_reads_only_after_store_setup(hub, monkeypatch):
    seen = []

    async def connect(*a, **k):
        seen.append(hub.store.pool)   # what the store had done when the warm start connected
        raise ConnectionError("stop here")
    monkeypatch.setattr(app_mod.asyncpg, "connect", connect)

    async def main():
        warm = asyncio.create_task(hub.warm_gaps())
        await asyncio.sleep(0.1)
        assert not seen and hub.gaps_warm == "pending"   # still waiting: no tables yet
        hub.store.pool = object()                        # setup done
        await asyncio.wait_for(warm, 2)
    asyncio.run(main())
    assert seen and seen[0] is not None


def test_warm_start_gives_up_if_the_store_never_sets_up(hub, monkeypatch):
    monkeypatch.setattr(app_mod, "WARM_WAIT_S", 0.05)

    async def connect(*a, **k):
        raise AssertionError("must not connect before setup")
    monkeypatch.setattr(app_mod.asyncpg, "connect", connect)
    asyncio.run(asyncio.wait_for(hub.warm_gaps(), 2))
    assert hub.gaps_warm.startswith("failed: Tiger Data not set up")   # the detector ticks again
