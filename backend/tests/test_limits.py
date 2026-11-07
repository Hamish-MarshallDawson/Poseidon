"""Each AISStream rate rule in dvm/limits.py is enforced, not just written down."""
import asyncio

import pytest

from dvm import limits
from dvm.ingest import Feed, enqueue
from dvm.limits import AisLimiter, RateRuleBreach


class Clock:
    def __init__(self):
        self.t = 1_000_000.0

    def __call__(self):
        return self.t


@pytest.fixture
def clock():
    return Clock()


def lim(clock, path=None):
    return AisLimiter(path, clock=clock, rand=lambda: 1.0)   # rand 1.0: the longest jitter


def test_one_connection_at_a_time(clock):
    l = lim(clock)
    l.open_connection("deflate")
    with pytest.raises(RateRuleBreach):
        l.open_connection("deflate")


def test_compression_is_mandatory(clock):
    with pytest.raises(RateRuleBreach):
        lim(clock).open_connection(None)


def test_one_machine_one_connection(clock, monkeypatch):
    monkeypatch.setattr(limits, "HOST_LOCK_PORT", 47822)   # not the live backend's port
    a, b = lim(clock), lim(clock)
    a.acquire_host_lock()
    with pytest.raises(RateRuleBreach):
        b.acquire_host_lock()
    a._lock_sock.close()


def test_subscription_updates_spaced(clock):
    l = lim(clock)
    l.open_connection("deflate")
    l.subscribe()
    clock.t += limits.MIN_SUBSCRIPTION_INTERVAL_S - 0.1
    with pytest.raises(RateRuleBreach):
        l.subscribe()
    clock.t += 0.2
    l.subscribe()


def test_backoff_doubles_with_jitter_and_caps(clock):
    l = lim(clock)
    waits = []
    for _ in range(12):
        clock.t += l.delay()
        l.open_connection("deflate")
        l.closed()
        waits.append(l.delay())
    assert waits[0] >= limits.BACKOFF_MIN_S and waits[1] > waits[0]
    assert max(waits) <= limits.BACKOFF_MAX_S * 1.5
    with pytest.raises(RateRuleBreach):   # connecting early is refused, not attempted
        l.open_connection("deflate")


def test_hourly_ceiling(clock):
    l = lim(clock)
    for _ in range(limits.MAX_CONNECTS_PER_HOUR):
        l.open_connection("deflate")
        clock.t += limits.HEALTHY_AFTER_S / 100
        l.not_before, l.open = 0, 0       # pretend every connection ended without backoff
    assert l.delay() > 0
    with pytest.raises(RateRuleBreach):
        l.open_connection("deflate")


def test_penalty_after_429_survives_restart(clock, tmp_path):
    path = tmp_path / "limits.json"
    l = lim(clock, path)
    l.open_connection("deflate")
    l.closed(penalty="HTTP 429 at handshake")
    restarted = lim(clock, path)
    assert restarted.delay() >= limits.PENALTY_S - 1
    assert restarted.status()["penalty_reason"] == "HTTP 429 at handshake"


def test_reader_never_blocks_on_a_full_queue():
    q, feed = asyncio.Queue(maxsize=1), Feed()
    enqueue(q, b"a", feed)
    enqueue(q, b"b", feed)   # would block with put(); must drop and count instead
    assert (feed.received, feed.dropped) == (1, 1)
