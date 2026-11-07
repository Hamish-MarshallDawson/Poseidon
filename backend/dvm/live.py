"""In-memory live state: the latest position and identity per vessel, and what changed since the last tick."""
from __future__ import annotations

from dvm.models import PositionReport, Record, VesselStatic, VesselView

STATIC_FIELDS = ("imo", "name", "callsign", "ship_type", "type_group", "length_m", "beam_m", "draught_m",
                 "destination", "eta_utc", "flag_iso2")


class Live:
    def __init__(self):
        self.pos: dict[int, PositionReport] = {}
        self.static: dict[int, dict] = {}
        self.changed: set[int] = set()

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
                          last_ts=p.ts).model_dump()

    def snapshot(self) -> list[dict]:
        return [self.view(m) for m in self.pos]

    def take_changes(self, now_ms: int, stale_after_s: int) -> tuple[list[dict], list[int]]:
        """Vessels changed since the last call, and vessels removed for being silent too long."""
        cutoff = now_ms - stale_after_s * 1000
        removed = [m for m, p in self.pos.items() if p.recv_ts < cutoff]
        for m in removed:
            del self.pos[m]
        changed, self.changed = self.changed, set()
        return [self.view(m) for m in changed if m in self.pos], removed
