"""Pure parts of the yacht reference: IMO checks, the OpenSanctions CSV filter, the notable list and the /yachts rows."""
from __future__ import annotations

import csv
import json
import re
from pathlib import Path
from typing import Iterable

NOTABLE_PATH = Path(__file__).with_name("notable.json")
PLACEHOLDER_IMOS = {0, 1234567, 9999999}   # pass or nearly pass the check digit but are filler, not ships
YACHT_SHIP_TYPES = {36, 37}                # AIS sailing, pleasure craft
OS_ENTITY_URL = "https://www.opensanctions.org/entities/"
IMO_RE = re.compile(r"IMO\s*(\d{7})\b")


def valid_imo(n) -> bool:
    """A real 7-digit IMO number: the check digit matches, and it is not a known placeholder."""
    try:
        n = int(n)
    except (TypeError, ValueError):
        return False
    if not 1_000_000 <= n <= 9_999_999 or n in PLACEHOLDER_IMOS:
        return False
    d = [int(c) for c in str(n)]
    return sum(x * w for x, w in zip(d[:6], (7, 6, 5, 4, 3, 2))) % 10 == d[6]


def imo_of(text: str | None) -> int | None:
    """The first valid IMO in a text like 'IMO9661792;ZGFO' or 'IMO number: 9661792'."""
    for m in IMO_RE.finditer(text or ""):
        if valid_imo(m.group(1)):
            return int(m.group(1))
    return None


def sanctioned_vessels(lines: Iterable[str]) -> dict[int, dict]:
    """OpenSanctions targets.simple.csv -> {imo: {name, programs, entity_id}} for sanctioned vessels with a valid IMO.

    Every vessel type is kept (about 2,000 rows): the CSV has no vessel type, so yachts are picked at match time
    (our AIS ship type, or the notable list)."""
    out: dict[int, dict] = {}
    for row in csv.DictReader(lines):
        if row.get("schema") != "Vessel":
            continue
        imo = imo_of(row.get("identifiers"))
        programs = sorted({p for p in (row.get("program_ids") or "").split(";") if p})
        if imo is None or not (programs or row.get("sanctions")):
            continue
        cur = out.get(imo)
        if cur:   # one ship listed by several sanctioning bodies: merge the programmes
            cur["programs"] = sorted(set(cur["programs"]) | set(programs))
        else:
            out[imo] = {"name": row.get("name") or None, "programs": programs, "entity_id": row["id"]}
    return out


def load_notable(path: Path = NOTABLE_PATH) -> dict[int, dict]:
    """notable.json -> {imo: {name, length_m, owner, url}}, keeping only valid IMOs."""
    data = json.loads(path.read_text(encoding="utf-8"))
    return {y["imo"]: y for y in data["yachts"] if valid_imo(y.get("imo"))}


def candidate_imos(notable: dict[int, dict], sanctioned: dict[int, dict]) -> list[int]:
    return sorted(set(notable) | set(sanctioned))


def build_rows(notable: dict[int, dict], sanctioned: dict[int, dict], statics: dict[int, dict]) -> list[dict]:
    """The yacht list before live status. statics: {imo: {mmsi, ship_type, length_m, name}} from the latest statics row
    with that IMO. A sanctioned vessel counts as a yacht only when it is on the notable list or our AIS calls it a
    pleasure or sailing craft, so sanctioned tankers never show here."""
    rows = []
    for imo in candidate_imos(notable, sanctioned):
        n, s, st = notable.get(imo), sanctioned.get(imo), statics.get(imo)
        if n is None and (st is None or st.get("ship_type") not in YACHT_SHIP_TYPES):
            continue
        rows.append({
            "imo": imo,
            "name": (n or {}).get("name") or (st or {}).get("name") or (s or {}).get("name"),
            "length_m": (n or {}).get("length_m") or (st or {}).get("length_m"),
            "owner_reported": (n or {}).get("owner"),
            "owner_source_url": (n or {}).get("url") if n and n.get("owner") else None,
            "sanctioned": s is not None,
            "programs": s["programs"] if s else [],
            "sanctions_source": OS_ENTITY_URL + s["entity_id"] if s else None,
            "mmsi": st["mmsi"] if st else None,
        })
    return rows


def with_status(rows: list[dict], live_pos: dict, open_gap, last_seen: dict[int, int]) -> list[dict]:
    """Adds last_seen_ts and status from our live state: ais (on the map with no open gap), no_ais (silent since
    last_seen_ts) or not_seen (no MMSI for the IMO, or no stored fix in the lookback)."""
    out = []
    for r in rows:
        m = r["mmsi"]
        p = live_pos.get(m) if m is not None else None
        ts = max(p.ts if p else 0, last_seen.get(m, 0)) or None
        if p is not None and m not in open_gap:
            status = "ais"
        else:
            status = "no_ais" if ts else "not_seen"
        out.append({**r, "last_seen_ts": ts, "status": status})
    return out
