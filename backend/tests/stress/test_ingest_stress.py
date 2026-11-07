"""Ingest and normalise under bad input. Runs today: needs only dvm/normalise.py, dvm/live.py and dvm/ingest.py.

Tests marked xfail(strict=True) are KNOWN gaps found by this suite. They pass while the gap exists, and turn
into a failure the moment someone fixes it, so the marker can be removed. Each reason says what is missing.
"""
from __future__ import annotations

import asyncio
import copy
import json
import random

import pytest

from dvm import ingest, limits
from dvm.live import Live
from dvm.models import Envelope, PositionReport, VesselStatic
from dvm.normalise import normalise
from tests.stress import harness, synth

pytestmark = pytest.mark.stress


def world(scale, seed, faults=None, ships=None):
    rng = synth.random.Random(seed)
    fleet = ships if ships is not None else synth.background(scale["ships"], rng, scale["interval_s"])
    return synth.World(fleet, scale["hours"] * 3600, faults or synth.Faults(), seed=seed)


def env(raw, recv=synth.T0_MS):
    return Envelope(src="aisstream", recv_ts=recv, raw=raw)


def one_position(**body):
    ship = synth.Ship(538003705, 60.0, 25.0, 10, 90, 10)
    raw = synth.position_msg(ship, synth.T0_MS, synth.T0_MS, 60.0, 25.0)
    raw["Message"]["PositionReport"].update(body)
    return raw


# ---------- malformed input ----------

JUNK_SAME_TYPE = {   # JSON types AISStream really sends, with out-of-range or sentinel values
    "Latitude": [91, -91, 90.0000001, 0, 1e9], "Longitude": [181, -181, 0, 1e9], "Sog": [102.3, 102.2, 0, -1, 1e9],
    "Cog": [360, 3600, -1], "TrueHeading": [511, 360, -1], "Timestamp": [60, 61, 62, 63, -1, 999],
    "NavigationalStatus": [15, 99, -1], "UserID": [0, 1, 999_999_999, 2**40, -538003705], "Valid": [False, True],
    "MessageID": [0, 99],
}
JUNK_WRONG_TYPE = [None, "", "12", "abc", [], {}, True]


def _mutations(rng, n, values_for):
    for _ in range(n):
        raw = one_position()
        body = raw["Message"]["PositionReport"]
        for key in rng.sample(sorted(body), rng.randint(1, 4)):
            body[key] = rng.choice(values_for(key))
        if rng.random() < 0.1:
            raw["MetaData"]["time_utc"] = rng.choice(["", "garbage", "2026-13-45 99:99:99 +0000 UTC", None])
        yield raw


def _crashes(raws):
    bad = []
    for raw in raws:
        try:
            for rec in normalise(env(json.loads(json.dumps(raw)))):
                Live().apply(rec)
        except Exception as e:   # noqa: BLE001 - collecting every crash is the point
            bad.append((type(e).__name__, str(e)[:80], raw["Message"]["PositionReport"]))
    return bad


def test_fuzz_out_of_range_values_never_crash(scale, seed):
    """Sentinels and out-of-range numbers of the right JSON type: must be dropped or flagged, never raise."""
    rng = random.Random(seed)
    raws = _mutations(rng, scale["fuzz"], lambda k: JUNK_SAME_TYPE.get(k, [0]))
    bad = _crashes(raws)
    assert not bad, f"{len(bad)} crashes, first: {bad[0]}"


@pytest.mark.xfail(strict=True, reason="A field of the wrong JSON type (e.g. Sog as a string) raises inside normalise. "
                   "Hub.consume now skips and counts such a message (tests/test_consume.py), so ingest survives; "
                   "normalise itself still raises rather than dropping the field.")
def test_fuzz_wrong_types_never_crash(scale, seed):
    rng = random.Random(seed)
    raws = _mutations(rng, scale["fuzz"], lambda k: JUNK_WRONG_TYPE)
    bad = _crashes(raws)
    assert not bad, f"{len(bad)} of {scale['fuzz']} crash, first: {bad[0]}"


def test_out_of_range_positions_are_dropped():
    for lat, lon in ((91, 25.0), (60.0, 181), (-91, 25.0)):
        assert not [r for r in normalise(env(one_position(Latitude=lat, Longitude=lon))) if isinstance(r, PositionReport)]


@pytest.mark.xfail(strict=True, reason="0/0 ('null island') positions are accepted; DATA-MODEL-IMPLICATIONS.md proposes "
                   "filtering them before gap, speed or spoof logic.")
def test_null_island_is_dropped():
    assert not [r for r in normalise(env(one_position(Latitude=0, Longitude=0))) if isinstance(r, PositionReport)]


# ---------- placeholder IMOs ----------

def _static_with_imo(imo):
    ship = synth.Ship(538003705, 60.0, 25.0, 10, 90, 10, imo=imo)
    recs = [r for r in normalise(env(synth.static_msg(ship, synth.T0_MS))) if isinstance(r, VesselStatic)]
    return recs[0]


@pytest.mark.parametrize("imo", [1, 100000000, 999999999, 9999999])
def test_placeholder_imo_is_flagged(imo):
    """Placeholders must never pass as a clean IMO: dropped, or kept with imo_bad_checksum."""
    s = _static_with_imo(imo)
    assert s.imo is None or "imo_bad_checksum" in s.q, (imo, s.imo, s.q)


def test_imo_zero_means_none():
    assert _static_with_imo(0).imo is None


@pytest.mark.xfail(strict=True, reason="1234567 has a valid check digit, so it passes as a clean IMO; "
                   "DATA-MODEL-IMPLICATIONS.md lists it as a placeholder to reject before sanctions joins.")
def test_imo_1234567_is_rejected():
    s = _static_with_imo(1234567)
    assert s.imo is None or "imo_bad_checksum" in s.q


# ---------- duplicates, late and out-of-order delivery ----------

def test_duplicates_are_not_stored_twice(scale, seed):
    clean, _ = world(scale, seed).emit()
    dup, _ = world(scale, seed, synth.Faults(dup_p=0.5)).emit()
    a, b = harness.run(clean), harness.run(dup)
    assert b.msgs > a.msgs * 1.2
    assert b.stored == a.stored, f"duplicates changed what is stored: {a.stored} vs {b.stored}"


def test_reordered_delivery_never_moves_a_dot_back(scale, seed):
    stream, truth = world(scale, seed, synth.Faults(reorder_s=20)).emit()
    res = harness.run(stream, track_views=True)
    for mmsi, seq in res.view_ts.items():
        assert seq == sorted(seq), f"{mmsi}: shown fix went back in time"
    for mmsi, fixes in truth["fixes"].items():
        if mmsi in res.live.pos:
            assert res.live.pos[mmsi].ts == max(t for t, *_ in fixes) // 1000 * 1000


def test_delay_under_50s_rebuilds_exact_time(scale, seed):
    stream, truth = world(scale, seed, synth.Faults(delay_max_s=50)).emit()
    sent = {m: {t // 1000 * 1000 for t, *_ in f} for m, f in truth["fixes"].items()}
    for recv, raw in stream:
        for rec in normalise(env(raw, recv)):
            if isinstance(rec, PositionReport):
                assert rec.ts in sent[rec.mmsi] and rec.ts_quality == "rebuilt"


@pytest.mark.xfail(strict=True, reason="rebuild_ts assumes the message is under ~55 s late (06 section 1.3). Later "
                   "messages get an event time exactly 60 s wrong and are not flagged `late`, so the detectors cannot skip them.")
def test_late_over_55s_is_flagged_or_exact(scale, seed):
    stream, truth = world(scale, seed, synth.Faults(delay_max_s=120)).emit()
    sent = {m: {t // 1000 * 1000 for t, *_ in f} for m, f in truth["fixes"].items()}
    wrong = 0
    for recv, raw in stream:
        for rec in normalise(env(raw, recv)):
            if isinstance(rec, PositionReport) and rec.ts not in sent[rec.mmsi] and "late" not in rec.q:
                wrong += 1
    assert wrong == 0, f"{wrong} positions have a wrong, unflagged event time"


# ---------- clock skew ----------

@pytest.mark.parametrize("skew_s", [-120, -30, 30, 120])
def test_clock_skew_keeps_ships_on_the_map(scale, skew_s):
    """AISStream's clock is off from ours. With the default stale limit, no live ship may be dropped from the map."""
    from dvm import config
    stale_s = getattr(config, "STALE_AFTER_S", None) or 1800
    stream, _ = world(scale, 1, synth.Faults(skew_s=skew_s)).emit()
    res = harness.run(stream)
    now = stream[-1][0]                       # our wall clock at the end
    _, removed = res.live.take_changes(now, stale_s)
    recent = {raw["MetaData"]["MMSI"] for recv, raw in stream if recv > now - 600_000}
    assert not (set(removed) & recent), f"skew {skew_s} s removed ships heard in the last 10 min"


@pytest.mark.xfail(strict=True, reason="A position whose recv time is far in the future (corrupt time_utc) pins the "
                   "vessel: later true fixes are older, so they never move the dot again. Low likelihood, high visibility.")
def test_one_future_dated_fix_does_not_freeze_a_vessel():
    live = Live()
    ship = synth.Ship(538003705, 60.0, 25.0, 10, 90, 10)
    bad = synth.position_msg(ship, synth.T0_MS, synth.T0_MS + 3_600_000, 60.5, 25.5)
    for rec in normalise(env(bad)):
        live.apply(rec)
    for i in range(1, 10):
        t = synth.T0_MS + i * 10_000
        for rec in normalise(env(synth.position_msg(ship, t, t, 60.0, 25.0 + i / 100), t)):
            live.apply(rec)
    assert live.pos[538003705].lon == pytest.approx(25.09), "vessel stuck at the future-dated fix"


# ---------- bursts and back-pressure ----------

def test_burst_throughput_through_the_consume_path(scale, tmp_path):
    """The full consume path (JSON, raw log, normalise, Live) must keep up with a burst far above the live rate."""
    n = scale["burst"]
    rng = synth.random.Random(7)
    ships = synth.background(2000, rng, 2)
    stream, _ = synth.World(ships, n * 2 / 2000 * 1.05, synth.Faults(interval_jitter=0.0), seed=7).emit()
    stream = stream[:n]
    res = harness.run(stream, rawlog_dir=tmp_path)
    live_rate = 90   # msg/s measured on the desktop at 17:34
    print(f"\nconsume path: {res.rate:,.0f} msg/s over {res.msgs:,} messages ({res.rate / live_rate:.0f}x live)")
    assert res.rate >= 20 * live_rate, f"only {res.rate:.0f} msg/s"


def test_queue_overflow_is_counted_not_raised():
    async def go():
        q, feed = asyncio.Queue(maxsize=100), ingest.Feed()
        for i in range(1000):
            ingest.enqueue(q, b"{}", feed)
        return q.qsize(), feed.received, feed.dropped
    assert asyncio.run(go()) == (100, 100, 900)
    assert limits.QUEUE_MAX >= 10_000
