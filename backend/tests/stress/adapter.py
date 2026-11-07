"""The one place that knows the gap detector's names. If Jake's dvm/gaps.py uses different ones, change this file only.

Expected (proposed on the board, 20:57): dvm.gaps.GapDetector(**params) with
  observe(rec: PositionReport) -> list[GapEvent]   every position, after Live.apply; closes gaps
  tick(now_ms: int) -> list[GapEvent]              every 5 s on the recv_ts clock; opens and updates gaps
  note_stall(start_ms: int, end_ms: int) -> None   our own ingest stall, for coverage_flag = own_stall
GapEvent per 06 section 2.4. Events may be Pydantic models or dicts.
"""
from __future__ import annotations

import importlib

GAP_FIELDS = {"id", "version", "mmsi", "state", "start_ts", "end_ts", "detected_at", "duration_s", "last_lat", "last_lon",
              "next_lat", "next_lon", "implied_speed_kn", "neighbours_heard", "neighbours_baseline", "cell_id",
              "coverage_flag"}
FLAGS = {"deliberate_candidate", "coverage_gap", "own_stall", "unknown"}


class _AsDicts:
    """Wraps a detector so the tests always see plain dicts."""

    def __init__(self, inner):
        self.inner = inner

    @staticmethod
    def _d(events):
        return [e.model_dump() if hasattr(e, "model_dump") else dict(e) for e in (events or [])]

    def observe(self, rec):
        return self._d(self.inner.observe(rec))

    def tick(self, now_ms):
        return self._d(self.inner.tick(now_ms))

    def note_stall(self, start_ms, end_ms):
        if hasattr(self.inner, "note_stall"):
            self.inner.note_stall(start_ms, end_ms)


def dvm_detector_class():
    """Jake's detector, or None if it is not merged yet."""
    try:
        return importlib.import_module("dvm.gaps").GapDetector
    except (ImportError, AttributeError):
        return None


def make(which: str):
    """which = 'dvm' (Jake's, the real target) or 'reference' (validates this suite only)."""
    if which == "reference":
        from tests.stress.reference_detector import ReferenceGapDetector
        return _AsDicts(ReferenceGapDetector())
    cls = dvm_detector_class()
    return _AsDicts(cls()) if cls else None
