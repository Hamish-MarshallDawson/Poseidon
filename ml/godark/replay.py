"""Replay the backend's own gap detector (`backend/dvm/gaps.py`) over recorded positions (#121).

Why: the live `gaps` table only holds trustworthy flags from about 23:40 UTC on 7 Nov. Writing began at 00:54 on
8 Nov, the warm start only sees the 2 h before a start-up (older silences become `unknown`), and ingest was down from
21:57 to 23:36. Replaying the same detector code over every stored position gives one consistent set of gaps for the
whole recording, made by the same rules the live backend uses. `compare()` checks the replay against the table where
both exist.

Outages: any stretch of more than STALL_GAP_MS with no position at all (from any source) is passed to `note_stall`
when the next position arrives, the way the backend does after a restart, plus `gaps.KNOWN_STALLS`.

    ml/.venv/bin/python -m ml.godark.replay        # writes /home/aiden/data/poseidon/godark/replay_gaps.parquet
"""
from __future__ import annotations

import json
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

BACKEND = Path(__file__).resolve().parents[2] / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

from dvm import gaps as dvm_gaps  # noqa: E402

TICK_MS = 15_000          # the backend ticks every 5 s; 15 s changes detection time by at most 10 s on a 30 min floor
STALL_GAP_MS = 30_000     # at ~50 positions a second, 30 s of nothing at all is our outage, not the ships
OUT = Path("/home/aiden/data/poseidon/godark/replay_gaps.parquet")
META = OUT.with_name("replay_meta.json")


def _num(v):
    return None if v is None or v is pd.NA or v != v else float(v)


class _Pos:
    """The PositionReport fields the detector reads (a pydantic model per row would triple the replay time)."""
    __slots__ = ("mmsi", "ts", "recv_ts", "lat", "lon", "sog_kn", "cog_deg", "heading_deg", "nav_status", "cls", "src")

    def __init__(self, *values):
        for k, v in zip(self.__slots__, values):
            setattr(self, k, v)


def find_stalls(recv_ts: np.ndarray, gap_ms: int = STALL_GAP_MS) -> list[tuple[int, int]]:
    r = np.sort(recv_ts)
    d = np.diff(r)
    idx = np.where(d > gap_ms)[0]
    return [(int(r[i]), int(r[i + 1])) for i in idx]


def replay(pos: pd.DataFrame, tick_ms: int = TICK_MS, stall_gap_ms: int = STALL_GAP_MS,
           known_stalls: list[tuple[int, int]] | None = None) -> tuple[pd.DataFrame, dict]:
    """Feed positions in receive order, tick on the receive clock, return every gap version and the detector stats."""
    pos = pos.sort_values(["recv_ts", "mmsi", "ts"], kind="mergesort")
    det = dvm_gaps.GapDetector()
    stalls = list(dvm_gaps.KNOWN_STALLS if known_stalls is None else known_stalls)
    for a, b in stalls:
        det.note_stall(a, b)
    events: list[dict] = []
    cols = [pos[c].to_numpy() for c in ("mmsi", "ts", "recv_ts", "lat", "lon", "sog_kn", "cog_deg", "heading_deg",
                                        "nav_status", "cls", "src")]
    next_tick = None
    last_recv = None
    for mmsi, ts, recv, lat, lon, sog, cog, hdg, nav, cls, src in zip(*cols):
        recv = int(recv)
        if last_recv is not None and recv - last_recv > stall_gap_ms:
            # The backend notes an outage when it comes back; tick up to the outage's start first.
            while next_tick <= last_recv:
                events += det.tick(next_tick)
                next_tick += tick_ms
            events += det.note_stall(last_recv, recv)
            stalls.append((last_recv, recv))
            next_tick = recv
        if next_tick is None:
            next_tick = recv
        while next_tick <= recv:
            events += det.tick(next_tick)
            next_tick += tick_ms
        rec = _Pos(int(mmsi), int(ts), recv, float(lat), float(lon), _num(sog), _num(cog),
                   None if _num(hdg) is None else int(hdg), None if _num(nav) is None else int(nav), str(cls), str(src))
        events += det.observe(rec)
        last_recv = recv
    if last_recv is not None:
        events += det.tick(last_recv)
    df = pd.DataFrame(events)
    if "q" in df:
        df = df.drop(columns=["q"])
    stats = dict(det.stats, stalls=[(a, b) for a, b in sorted(set(stalls))],
                 data_from=int(pos.recv_ts.min()), data_to=int(pos.recv_ts.max()))
    return df, stats


def latest(versions: pd.DataFrame) -> pd.DataFrame:
    """One row per gap: its newest version (the flag at the close, or the current flag if still open)."""
    return versions.sort_values(["id", "version"]).groupby("id", as_index=False).tail(1).reset_index(drop=True)


def compare(replayed: pd.DataFrame, table: pd.DataFrame, t0: int, t1: int) -> dict:
    """Agreement between replayed and stored gaps that started in [t0, t1): same ids, and the flag on matches."""
    a = latest(replayed)
    b = latest(table)
    a = a[(a.start_ts >= t0) & (a.start_ts < t1)].set_index("id")
    b = b[(b.start_ts >= t0) & (b.start_ts < t1)].set_index("id")
    both = a.index.intersection(b.index)
    flag_same = float((a.loc[both, "coverage_flag"] == b.loc[both, "coverage_flag"]).mean()) if len(both) else None
    conf = pd.crosstab(a.loc[both, "coverage_flag"], b.loc[both, "coverage_flag"]).to_dict() if len(both) else {}
    return {"replay": len(a), "table": len(b), "both": len(both),
            "replay_only": len(a.index.difference(b.index)), "table_only": len(b.index.difference(a.index)),
            "flag_agreement": flag_same, "confusion_table_by_replay": conf}


def main() -> None:
    from ml.godark.tiger import DEFAULT_OUT, load_positions
    t = time.time()
    pos = load_positions(DEFAULT_OUT)
    df, stats = replay(pos)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    df.to_parquet(OUT, index=False)
    meta = {k: stats[k] for k in ("stalls", "data_from", "data_to")}
    meta.update(gaps=len(latest(df)), versions=len(df), positions=len(pos), tick_ms=TICK_MS, stall_gap_ms=STALL_GAP_MS)
    META.write_text(json.dumps(meta))
    lat = latest(df)
    print(f"{len(pos)} positions -> {len(df)} versions, {len(lat)} gaps in {time.time() - t:.0f} s")
    print(lat.coverage_flag.value_counts().to_dict())
    print({k: v for k, v in stats.items() if k != "stalls"}, "stalls:", len(stats["stalls"]))
    table = pd.read_parquet(DEFAULT_OUT / "gaps.parquet")
    t0 = 1794094560000 + 3_600_000   # 8 Nov 00:36: the stored flags have a full neighbour baseline from here
    print("compare from 00:36:", compare(df, table, t0, stats["data_to"] - 2 * 3_600_000))


if __name__ == "__main__":
    main()
