"""Runs a stream through the same steps as Hub.consume in dvm/app.py, without the network or the database:
JSON round trip, raw log write, normalise, Live.apply, then the gap detector (if given) on the recv_ts clock.
"""
from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

from dvm.live import Live
from dvm.models import Envelope, PositionReport
from dvm.normalise import normalise
from dvm.rawlog import RawLog


@dataclass
class Result:
    live: Live
    msgs: int = 0
    records: int = 0
    stored: int = 0
    seconds: float = 0.0
    gap_versions: list[dict] = field(default_factory=list)
    view_ts: dict[int, list[int]] = field(default_factory=dict)   # mmsi -> last_ts each time the dot moved

    @property
    def rate(self) -> float:
        return self.msgs / self.seconds if self.seconds else 0.0

    def gaps(self) -> dict[str, dict]:
        """Latest version of each gap id."""
        latest: dict[str, dict] = {}
        for g in self.gap_versions:
            if g["id"] not in latest or g["version"] >= latest[g["id"]]["version"]:
                latest[g["id"]] = g
        return latest


def run(stream, detector=None, tick_s: float = 5, stalls=(), rawlog_dir: Optional[Path] = None,
        end_ms: Optional[int] = None, track_views: bool = False) -> Result:
    live = Live()
    res = Result(live=live)
    rawlog = RawLog(rawlog_dir) if rawlog_dir else None
    tick_ms = int(tick_s * 1000)
    pending_stalls = sorted(stalls, key=lambda w: w.end_ms)
    next_tick = None

    def ticks_until(t):
        nonlocal next_tick
        while next_tick is not None and next_tick <= t:
            while pending_stalls and pending_stalls[0].end_ms <= next_tick:   # a stall is known once it is over
                w = pending_stalls.pop(0)
                detector.note_stall(w.start_ms, w.end_ms)
            res.gap_versions.extend(detector.tick(next_tick))
            next_tick += tick_ms

    t0 = time.perf_counter()
    for recv_ms, raw in stream:
        if detector is not None:
            if next_tick is None:
                next_tick = recv_ms - recv_ms % tick_ms + tick_ms
            ticks_until(recv_ms)
        msg = json.dumps(raw, separators=(",", ":"))   # what the socket hands the consumer
        parsed = json.loads(msg)
        res.msgs += 1
        if rawlog:
            rawlog.write("aisstream", recv_ms, parsed)
        for rec in normalise(Envelope(src="aisstream", recv_ts=recv_ms, raw=parsed)):
            res.records += 1
            if live.apply(rec):
                res.stored += 1
            if isinstance(rec, PositionReport):
                if track_views:
                    cur = live.pos.get(rec.mmsi)
                    seq = res.view_ts.setdefault(rec.mmsi, [])
                    if cur and (not seq or seq[-1] != cur.ts):
                        seq.append(cur.ts)
                if detector is not None:
                    res.gap_versions.extend(detector.observe(rec))
    if detector is not None and end_ms is not None:
        ticks_until(end_ms)
    res.seconds = time.perf_counter() - t0
    if rawlog:
        rawlog.close()
    return res
