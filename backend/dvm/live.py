"""In-memory live state: the latest position and identity per vessel, and what changed since the last tick."""
from __future__ import annotations

from dvm.models import PositionReport, Record, VesselStatic, VesselView

STATIC_FIELDS = ("imo", "name", "callsign", "ship_type", "type_group", "length_m", "beam_m", "draught_m",
                 "destination", "eta_utc", "flag_iso2")
GAP_KEEP_MS = 24 * 3_600_000      # a ship with an open gap stays on the map this long after its last fix (#76)
CLOSED_SHOWN_MS = 3_600_000       # closed gaps a new browser gets in its snapshot
DETAIL_GAPS = 5                   # most recent gaps in a ship's detail reply


class Live:
    def __init__(self):
        self.pos: dict[int, PositionReport] = {}
        self.static: dict[int, dict] = {}
        self.changed: set[int] = set()
        self.gaps: dict[str, dict] = {}        # gap id -> latest version (dvm/gaps.py), open and recently closed
        self.open_gap: dict[int, str] = {}     # mmsi -> id of its open gap

    def apply(self, rec: Record) -> bool:
        """Update state. Returns True if the record is new information worth storing."""
        if isinstance(rec, PositionReport):
            last = self.pos.get(rec.mmsi)
            if last and (last.ts // 1000, round(last.lat, 4), round(last.lon, 4)) == (
                    rec.ts // 1000, round(rec.lat, 4), round(rec.lon, 4)):
                return False   # duplicate fix (06 section 1.5)
            if not last or rec.ts >= last.ts:   # an older fix is stored but never moves the dot back
                self.pos[rec.mmsi] = rec
                self.changed.add(rec.mmsi)
            return True
        # Statics: keep only messages that change something, so repeated names and 6-minute rebroadcasts aren't stored.
        known = self.static.setdefault(rec.mmsi, {})
        new = {f: getattr(rec, f) for f in STATIC_FIELDS
               if getattr(rec, f) is not None and getattr(rec, f) != known.get(f) and not (f == "type_group" and rec.type_group == "unknown")}
        if not new:
            return False
        known.update(new)
        if rec.mmsi in self.pos:
            self.changed.add(rec.mmsi)
        return True

    def view(self, mmsi: int) -> dict:
        p, s = self.pos[mmsi], self.static.get(mmsi, {})
        return VesselView(mmsi=mmsi, name=s.get("name"), imo=s.get("imo"), flag=s.get("flag_iso2"),
                          type_group=s.get("type_group", "unknown"), length_m=s.get("length_m"),
                          lat=p.lat, lon=p.lon, sog_kn=p.sog_kn, cog_deg=p.cog_deg, heading_deg=p.heading_deg,
                          last_ts=p.ts, status=self._status(mmsi), open_gap_id=self.open_gap.get(mmsi),
                          cls=p.cls).model_dump()

    def _status(self, mmsi: int) -> str:
        """gap_open only when the open gap looks like the ship (deliberate_candidate); other open gaps are silent."""
        gid = self.open_gap.get(mmsi)
        if gid is None:
            return "active"
        return "gap_open" if self.gaps[gid]["coverage_flag"] == "deliberate_candidate" else "silent"

    def snapshot(self) -> list[dict]:
        return [self.view(m) for m in self.pos]

    def detail(self, mmsi: int) -> dict:
        """06 section 4.3 `detail` reply. shortcut: `statics` holds the merged current identity, not the last 5 records."""
        return {"type": "detail", "mmsi": mmsi, "vessel": self.view(mmsi),
                "statics": [{"mmsi": mmsi, **self.static.get(mmsi, {})}],
                "gaps": self.gaps_of(mmsi), "spoofs": [], "sanction": None, "score": None}

    def apply_gaps(self, events: list[dict]) -> None:
        """Gap versions from the detector: keep the latest per id and the ship's gap_open status."""
        for g in events:
            cur = self.gaps.get(g["id"])
            if cur and cur["version"] > g["version"]:
                continue
            self.gaps[g["id"]] = g
            if g["state"] == "open":
                self.open_gap[g["mmsi"]] = g["id"]
            elif self.open_gap.get(g["mmsi"]) == g["id"]:
                del self.open_gap[g["mmsi"]]
            if g["mmsi"] in self.pos:
                self.changed.add(g["mmsi"])

    def gaps_of(self, mmsi: int) -> list[dict]:
        mine = [g for g in self.gaps.values() if g["mmsi"] == mmsi]
        return sorted(mine, key=lambda g: g["start_ts"], reverse=True)[:DETAIL_GAPS]

    def snapshot_gaps(self, now_ms: int) -> list[dict]:
        """Open gaps, plus gaps closed in the last hour, for a browser that has just connected."""
        return [g for g in self.gaps.values()
                if g["state"] == "open" or (g["end_ts"] or 0) >= now_ms - CLOSED_SHOWN_MS]

    def take_changes(self, now_ms: int, stale_after_s: int) -> tuple[list[dict], list[int]]:
        """Vessels changed since the last call, and vessels removed for being silent too long.

        A ship with an open gap stays (status gap_open) until the gap closes or GAP_KEEP_MS has passed."""
        cutoff, gap_cutoff = now_ms - stale_after_s * 1000, now_ms - GAP_KEEP_MS
        removed = [m for m, p in self.pos.items()
                   if p.recv_ts < (gap_cutoff if m in self.open_gap else cutoff)]
        for m in removed:
            del self.pos[m]
            self.open_gap.pop(m, None)
        for gid in [gid for gid, g in self.gaps.items()   # forget closed gaps after a day, open ones with their ship
                    if (g["state"] == "closed" and (g["end_ts"] or 0) < gap_cutoff)
                    or (g["state"] == "open" and self.open_gap.get(g["mmsi"]) != gid)]:
            del self.gaps[gid]
        changed, self.changed = self.changed, set()
        return [self.view(m) for m in changed if m in self.pos], removed
