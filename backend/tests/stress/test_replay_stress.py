"""Replays the recorded raw log (data/raw/aisstream/<hour>.jsonl[.gz], written by dvm/rawlog.py) through the pipeline.

Needs --replay <file or folder>; skipped otherwise. Read-only: the log is never modified, nothing is written to Tiger,
and no AISStream connection is opened. One test per hour file, so pytest-xdist runs files in parallel.
"""
from __future__ import annotations

import gzip
import json
from collections import Counter, defaultdict

import pytest

from dvm.models import Envelope, PositionReport
from dvm.normalise import normalise
from tests.stress import adapter, harness

pytestmark = pytest.mark.stress
FLOOR_MS = 1800 * 1000


def read_log(path):
    """Yields (recv_ts, raw) in file order. Lines that are not log envelopes are counted, not fatal."""
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as f:
        try:
            for line in f:
                try:
                    e = json.loads(line)
                    yield e["recv_ts"], e["raw"]
                except (ValueError, KeyError, TypeError):
                    yield None, line
        except EOFError:   # truncated .gz (rotation interrupted): keep what was readable, count it as junk
            yield None, "<truncated gzip>"


def load(*files):
    if not files or files[0] is None:
        pytest.skip("no recorded log: pass --replay <file or folder>")
    stream, junk = [], 0
    for path in files:
        for recv, raw in read_log(path):
            if recv is None or not isinstance(raw, dict):
                junk += 1
            else:
                stream.append((recv, raw))
    stream.sort(key=lambda m: m[0])
    return stream, junk


def test_replay_never_crashes_and_keeps_up(replay_file):
    stream, junk = load(replay_file)
    crashes = Counter()
    for recv, raw in stream:
        try:
            normalise(Envelope(src="aisstream", recv_ts=recv, raw=raw))
        except Exception as e:   # noqa: BLE001
            crashes[type(e).__name__] += 1
    assert not crashes, f"normalise raised on real messages: {dict(crashes)}"
    res = harness.run(stream)
    span_s = (stream[-1][0] - stream[0][0]) / 1000 if stream else 0
    print(f"\n{replay_file.name}: {res.msgs:,} msgs, {junk} junk lines, {res.rate:,.0f} msg/s, "
          f"{len(res.live.pos):,} ships, {span_s / max(res.seconds, 1e-9):.0f}x real time")
    assert res.rate > 0


def test_replay_gap_rate_by_flag(replay_file, request):
    """Not pass/fail on the numbers: prints how many gaps of each flag the detector raises on a real hour."""
    det = adapter.make(request.config.getoption("--detector"))
    if det is None:
        pytest.skip("dvm/gaps.py GapDetector is not merged yet")
    stream, _ = load(replay_file)
    res = harness.run(stream, det, end_ms=stream[-1][0] if stream else None)
    flags = Counter(g["coverage_flag"] for g in res.gaps().values())
    hours = (stream[-1][0] - stream[0][0]) / 3.6e6 if stream else 0
    print(f"\n{replay_file.name}: {dict(flags)} over {hours:.2f} h, {len(res.live.pos):,} ships")


def test_replay_injected_switch_off_is_found(replay_window, request):
    """Pick the busiest steady reporter, delete 45 min of its messages, and expect exactly that gap."""
    det = adapter.make(request.config.getoption("--detector"))
    if det is None:
        pytest.skip("dvm/gaps.py GapDetector is not merged yet")
    stream, _ = load(*replay_window)
    replay_file = replay_window[0]
    if not stream or stream[-1][0] - stream[0][0] < 80 * 60_000:
        pytest.skip("need at least 80 min of log to inject a 45 min switch-off with a baseline")
    times = defaultdict(list)
    for recv, raw in stream:
        if raw.get("MessageType") == "PositionReport":
            mmsi = (raw.get("MetaData") or {}).get("MMSI")
            if mmsi:
                times[mmsi].append(recv)
    t_start = stream[0][0] + 35 * 60_000
    t_end = t_start + 45 * 60_000

    def steady(ts):   # heard throughout, every few minutes at most
        inside = [t for t in ts if stream[0][0] <= t <= t_end + 10 * 60_000]
        return len(inside) > 60 and max(b - a for a, b in zip(inside, inside[1:])) < 5 * 60_000
    candidates = sorted((m for m, ts in times.items() if steady(ts)), key=lambda m: -len(times[m]))
    if not candidates:
        pytest.skip("no steadily reporting Class A ship in this file")
    target = candidates[0]
    cut = [(r, raw) for r, raw in stream
           if not ((raw.get("MetaData") or {}).get("MMSI") == target and t_start <= r < t_end)]
    res = harness.run(cut, det, end_ms=cut[-1][0])
    mine = [g for g in res.gaps().values() if g["mmsi"] == target]
    print(f"\n{replay_file.name}: target {target}, gaps {[(g['coverage_flag'], g['neighbours_heard']) for g in mine]}")
    assert len(mine) == 1, f"expected one gap for {target}, got {len(mine)}"
    g = mine[0]
    assert g["state"] == "closed" and g["end_ts"] is not None
    assert g["detected_at"] - g["start_ts"] >= FLOOR_MS - 60_000
    if g["neighbours_baseline"] >= 3 and g["neighbours_heard"] >= 3:
        assert g["coverage_flag"] == "deliberate_candidate", g
