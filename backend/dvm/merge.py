"""Cross-source merge: one stored record per real AIS fix and per identity change, whichever feeds heard it (#60).

AISStream and Digitraffic both hear the northern Baltic. The Hub pushes every normalised record through one
`FeedMerger` (one asyncio task, no locking) and stores and maps only what `push` and `flush` return.

Positions
- Same fix, two feeds: same mmsi, `ts` within MATCH_TS_MS (AISStream's ts is rebuilt from second-of-minute,
  Digitraffic's is `time`; they can disagree by a second) and the same position within MATCH_DEG. This widens 06
  rule 1.5 (`ts // 1000`, `round(lat, 4)`) in time but tightens it in space: both feeds relay the same AIS message, so
  coordinates agree to AIS resolution (1/600000 deg, Digitraffic rounds to 1e-6), while round(lat, 4) is about 11 m,
  which a ship at 10 kn covers in 2 s. So two different fixes 1 s apart are kept (tests/test_merge.py).
- Only copies from *different* sources merge. A same-source repeat (equal ts and position) is dropped
  (`dup_dropped`); the coarser 06 key is not used within a source, as Digitraffic sends distinct fixes in one second.
- Hold: a Class A fix of a ship the other feed has heard in the last OVERLAP_MS (or a ship's first fix while the
  other feed is live) waits up to HOLD_MS for the other copy, and is emitted as soon as the copy arrives. Everything
  else (Class B, ships only one feed hears, which is most of the world) is emitted at once, so the map lags only
  for overlap ships and by at most HOLD_MS.
- The merged record is the first arrival with its null fields (sog, cog, heading, nav status, msg_type) filled from
  the other copy, and the timestamp of the better `ts_quality` (source > rebuilt > recv_only). `q` n/a flags are
  recomputed. `dup_other_src` is not set, because the second copy is never stored: the merged row is the fix.
- `src` of a merged fix is the source whose copy arrived first (06: "the first one in recv_ts order is kept").
  `stats["pos_in"]` counts receptions per source and `stats["merged"]` the fixes both heard, so coverage can still
  say who was listening.
- A copy that arrives after its fix was emitted (later than HOLD_MS) is dropped (`late_dup_dropped`); its extra
  fields are lost, as rows are append-only. RECENT_MS of emitted fixes are remembered per ship for this.

Statics
- Emitted only when the merged identity or voyage content of the mmsi changes; the first sighting always emits.
  The emitted record is the full merged identity (partials such as AISStream's MetaData.ShipName or Class B part A
  and part B are folded in), stamped with the src, ts and recv_ts of the message that changed it.
- A field counts as changed only if it differs from what *the same source* last said for it, so two feeds that
  spell a name differently don't flip it back and forth every few minutes; the newer source's value wins once.

Deterministic: time comes only from the `now_ms` arguments, never the wall clock, so replay and backtest give the
same output for the same records pushed in recv_ts order with now_ms = recv_ts.
"""
from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass, field
from typing import get_args

from dvm.models import PositionReport, Q, Record, VesselStatic
from dvm.normalise import imo_ok

MATCH_TS_MS = 1_000      # same fix if ts differs by at most this
MATCH_DEG = 5e-6         # and lat and lon each by at most this (about 0.5 m)
HOLD_MS = 2_500          # longest a fix waits for the other feed's copy (Digitraffic ~0.5 s, AISStream ~1 s late)
OVERLAP_MS = 600_000     # a ship counts as heard by a feed for this long after its last position from it
ACTIVE_MS = 60_000       # a feed counts as live for this long after its last position (first sightings are held)
RECENT_MS = 30_000       # how long emitted fixes are remembered to catch late copies
RECENT_PER_SHIP = 8
MAX_SHIPS = 200_000      # cap on remembered identities; the least recently changed are forgotten first

Q_ORDER = get_args(Q)
TS_RANK = {"source": 2, "rebuilt": 1, "recv_only": 0}
FILL_FIELDS = ("sog_kn", "cog_deg", "heading_deg", "nav_status")
NA_FLAGS = (("sog_na", "sog_kn"), ("cog_na", "cog_deg"), ("hdg_na", "heading_deg"))
ID_FIELDS = ("imo", "name", "callsign", "ship_type", "type_group", "dim_a_m", "dim_b_m", "dim_c_m", "dim_d_m",
             "length_m", "beam_m", "draught_m", "destination", "eta_utc", "flag_iso2")


@dataclass
class _Held:
    rec: PositionReport
    arrived: int                     # now_ms at push
    srcs: set = field(default_factory=set)
    done: bool = False


def _same_fix(a: PositionReport, b: PositionReport) -> bool:
    return abs(a.ts - b.ts) <= MATCH_TS_MS and abs(a.lat - b.lat) <= MATCH_DEG and abs(a.lon - b.lon) <= MATCH_DEG


def _repeat(a: PositionReport, b: PositionReport) -> bool:
    """Same source, same fix again (e.g. QoS 0 redelivery). Exact ts: Digitraffic sends two different fixes in one
    second (seen live: 4 m apart at 9.5 kn), which the 06 key (ts // 1000, round(lat, 4)) would call one."""
    return a.ts == b.ts and abs(a.lat - b.lat) <= MATCH_DEG and abs(a.lon - b.lon) <= MATCH_DEG


def merge_positions(first: PositionReport, other: PositionReport) -> tuple[PositionReport, int]:
    """First arrival, with nulls filled from `other` and the better timestamp. Returns (record, fields filled)."""
    upd: dict = {}
    for f in FILL_FIELDS:
        if getattr(first, f) is None and getattr(other, f) is not None:
            upd[f] = getattr(other, f)
    if not first.msg_type and other.msg_type:
        upd["msg_type"] = other.msg_type
    filled = len(upd)
    q = set(first.q) | (set(other.q) - {"ts_recv_only", "sog_na", "cog_na", "hdg_na"})
    if TS_RANK[other.ts_quality] > TS_RANK[first.ts_quality]:
        upd.update(ts=other.ts, ts_quality=other.ts_quality)
        q.discard("ts_recv_only")
        filled += 1
    for flag, f in NA_FLAGS:
        if f in upd:
            q.discard(flag)
    if not filled:
        return first, 0
    return first.model_copy(update={**upd, "q": [x for x in Q_ORDER if x in q]}), filled


class FeedMerger:
    def __init__(self):
        self._held: dict[int, list[_Held]] = {}
        self._queue: deque[_Held] = deque()                       # held fixes in arrival order
        self._recent: dict[int, deque[tuple[int, PositionReport]]] = {}   # mmsi -> (emitted_at, rec)
        self._heard: dict[int, dict[str, int]] = {}               # mmsi -> src -> now_ms of last position
        self._active: dict[str, int] = {}                         # src -> now_ms of its last position
        self._ident: OrderedDict[int, dict] = OrderedDict()       # mmsi -> merged identity last emitted
        self._said: dict[int, dict[str, dict]] = {}               # mmsi -> src -> fields that src last said
        self._pruned = 0
        self.stats: dict = {"pos_in": {}, "pos_out": 0, "merged": 0, "filled_fields": 0, "dup_dropped": 0,
                            "late_dup_dropped": 0, "held": 0, "static_in": {}, "static_out": 0,
                            "static_unchanged": 0}

    # ---- public ----
    def push(self, rec: Record, now_ms: int) -> list[Record]:
        if isinstance(rec, VesselStatic):
            return self._static(rec)
        out = self.flush(now_ms)
        out += self._position(rec, now_ms)
        return out

    def flush(self, now_ms: int) -> list[Record]:
        out: list[Record] = []
        while self._queue and (self._queue[0].done or now_ms - self._queue[0].arrived >= HOLD_MS):
            h = self._queue.popleft()
            if not h.done:
                out.append(self._emit(h, now_ms))
        self.stats["held"] = sum(not h.done for h in self._queue)
        if now_ms - self._pruned >= 10_000:
            self._pruned = now_ms
            self._prune(now_ms)
        return out

    # ---- positions ----
    def _position(self, rec: PositionReport, now_ms: int) -> list[Record]:
        st = self.stats
        st["pos_in"][rec.src] = st["pos_in"].get(rec.src, 0) + 1
        new = rec.mmsi not in self._heard
        heard = self._heard.setdefault(rec.mmsi, {})
        other = lambda d, window: any(s != rec.src and now_ms - t <= window for s, t in d.items())
        # hold when the other feed hears this ship, or when it is a new ship and the other feed is live at all
        overlap = rec.cls == "A" and (other(heard, OVERLAP_MS) or (new and other(self._active, ACTIVE_MS)))
        heard[rec.src] = self._active[rec.src] = now_ms

        for h in self._held.get(rec.mmsi, ()):   # a held fix waiting for this copy?
            if h.done:
                continue
            if rec.src in h.srcs:
                if _repeat(h.rec, rec):
                    st["dup_dropped"] += 1
                    return []
                continue
            if rec.cls == "A" and h.rec.cls == "A" and _same_fix(h.rec, rec):
                h.rec, filled = merge_positions(h.rec, rec)
                h.srcs.add(rec.src)
                st["merged"] += 1
                st["filled_fields"] += filled
                return [self._emit(h, now_ms)]
        for _, r in self._recent.get(rec.mmsi, ()):   # already emitted?
            if r.src == rec.src and _repeat(r, rec):
                st["dup_dropped"] += 1
                return []
            if r.src != rec.src and rec.cls == "A" and r.cls == "A" and _same_fix(r, rec):
                st["late_dup_dropped"] += 1
                return []
        h = _Held(rec, now_ms, {rec.src})
        if not overlap:
            return [self._emit(h, now_ms)]
        self._held.setdefault(rec.mmsi, []).append(h)
        self._queue.append(h)
        self.stats["held"] += 1
        return []

    def _emit(self, h: _Held, now_ms: int) -> PositionReport:
        h.done = True
        lst = self._held.get(h.rec.mmsi)
        if lst is not None:
            try:
                lst.remove(h)
            except ValueError:
                pass
            if not lst:
                del self._held[h.rec.mmsi]
        recent = self._recent.setdefault(h.rec.mmsi, deque(maxlen=RECENT_PER_SHIP))
        recent.append((now_ms, h.rec))
        self.stats["pos_out"] += 1
        return h.rec

    def _prune(self, now_ms: int) -> None:
        for m in [m for m, d in self._recent.items() if now_ms - d[-1][0] > RECENT_MS]:
            del self._recent[m]
        for m in [m for m, d in self._heard.items() if all(now_ms - t > OVERLAP_MS for t in d.values())]:
            del self._heard[m]

    # ---- statics ----
    def _static(self, rec: VesselStatic) -> list[Record]:
        st = self.stats
        st["static_in"][rec.src] = st["static_in"].get(rec.src, 0) + 1
        said = self._said.setdefault(rec.mmsi, {}).setdefault(rec.src, {})
        first = rec.mmsi not in self._ident
        ident = self._ident.get(rec.mmsi, {})
        changes = {}
        for f in ID_FIELDS:
            v = getattr(rec, f)
            if v is None or (f == "type_group" and v == "unknown"):
                continue
            if said.get(f) != v:   # this source says something new for the field
                said[f] = v
                if ident.get(f) != v:
                    changes[f] = v
        if not first and not changes:
            st["static_unchanged"] += 1
            return []
        ident = {**ident, **changes}
        self._ident[rec.mmsi] = ident
        self._ident.move_to_end(rec.mmsi)
        while len(self._ident) > MAX_SHIPS:
            old, _ = self._ident.popitem(last=False)
            self._said.pop(old, None)
        imo = ident.get("imo")
        st["static_out"] += 1
        return [VesselStatic(mmsi=rec.mmsi, ts=rec.ts, recv_ts=rec.recv_ts, mid=rec.mid, src=rec.src,
                             **{f: ident.get(f) for f in ID_FIELDS if f != "type_group"},
                             type_group=ident.get("type_group", "unknown"),
                             q=["imo_bad_checksum"] if imo and not imo_ok(imo) else [])]
