"""Cleaning rules of ml/data/dma.py on a small synthetic day in the archive's CSV layout."""
import json
from pathlib import Path

import duckdb
import pytest

from ml.data import dma

HEADER = ("# Timestamp,Type of mobile,MMSI,Latitude,Longitude,Navigational status,ROT,SOG,COG,Heading,IMO,Callsign,"
          "Name,Ship type,Cargo type,Width,Length,Type of position fixing device,Draught,Destination,ETA,"
          "Data source type,A,B,C,D")


def row(t, mmsi, lat, lon, mobile="Class A", nav="Under way using engine", sog="10.0", cog="90.0", hdg="90",
        imo="Unknown", name="", stype="Undefined", length="", draught=""):
    return (f"05/11/2026 {t},{mobile},{mmsi},{lat},{lon},{nav},0.0,{sog},{cog},{hdg},{imo},Unknown,{name},{stype},,"
            f",{length},GPS,{draught},Unknown,,AIS,,,,")


@pytest.fixture
def out(tmp_path: Path) -> Path:
    A, B = 219000001, 219000002
    lines = [HEADER,
             # ship A: 1 fix a minute eastwards at about 10 kn (0.005 deg lon at lat 55 is about 320 m)
             row("00:00:00", A, 55.0, 10.000, imo="9123456", name="ALPHA", stype="Cargo", length="120"),
             row("00:00:00", A, 55.0, 10.000),  # same-second multi-receiver copy
             row("00:00:30", A, 55.0, 10.0025),  # second fix in minute 0 (thinned away)
             row("00:01:00", A, 55.0, 10.005, sog="102.3", cog="360.0", hdg="511", nav="Unknown value"),
             row("00:02:00", A, 56.0, 10.010),  # spike: 111 km in a minute and back
             row("00:03:00", A, 55.0, 10.015, draught="7.5"),
             row("00:04:00", A, 55.0, 10.020),
             # ship B, class B: a jump of 64 km in a minute it does not come back from (pass 2 drops the jump fix)
             row("00:00:00", B, 54.5, 11.0, mobile="Class B", stype="Pleasure"),
             row("00:01:00", B, 54.5, 12.0, mobile="Class B"),
             row("00:02:00", B, 54.5, 12.0005, mobile="Class B"),
             # rows that must go
             row("00:00:00", 2190001, 55.0, 10.0, mobile="Base Station"),
             row("00:00:00", 992191234, 55.0, 10.0, mobile="AtoN"),
             row("00:00:00", 111219000, 55.0, 10.0),  # SAR aircraft MMSI range, not a vessel
             row("00:00:00", 219000003, 91.0, 0.0),
             row("00:00:00", 219000004, 55.0, 181.0),
             row("00:00:00", 219000005, 55.0, 0.0),
             row("00:00:00", 219000006, 54.2, 116.8)]  # outside the coverage box
    csv = tmp_path / "aisdk-2026-11-05.csv"
    csv.write_text("\n".join(lines) + "\n")
    o = tmp_path / "out"
    dma.convert_csv(csv, "2026-11-05", o, threads=1, memory="1GB")
    return o


def test_tracks_contract_and_cleaning(out: Path):
    t = duckdb.sql(f"SELECT * FROM read_parquet('{out}/tracks/2026-11-05.parquet')")
    assert t.columns == [c for c, _ in dma.TRACK_SCHEMA]
    types = dict(zip(t.columns, map(str, t.types)))
    assert types == {"mmsi": "INTEGER", "ts": "BIGINT", "lat": "DOUBLE", "lon": "DOUBLE", "sog_kn": "FLOAT",
                     "cog_deg": "FLOAT", "heading_deg": "SMALLINT", "nav_status": "SMALLINT", "cls": "VARCHAR",
                     "src": "VARCHAR"}
    rows = t.fetchall()
    assert {r[0] for r in rows} == {219000001, 219000002}
    a = [r for r in rows if r[0] == 219000001]
    # duplicate removed, spike at 00:02 removed
    assert [r[1] for r in a] == [1793836800000 + s * 1000 for s in (0, 30, 60, 180, 240)]
    assert all(r[2] == 55.0 for r in a)
    sentinel = a[2]
    assert sentinel[4:8] == (None, None, None, None)  # sog 102.3, cog 360, heading 511, nav 15
    assert a[0][4:8] == (10.0, 90.0, 90, 0)
    assert {r[8] for r in a} == {"A"} and {r[9] for r in rows} == {"dma"}
    b = [r for r in rows if r[0] == 219000002]
    assert [r[1] for r in b] == [1793836800000, 1793836920000] and {r[8] for r in b} == {"B"}
    assert rows == sorted(rows, key=lambda r: (r[0], r[1]))


def test_thinned_and_identity_and_stats(out: Path):
    thin = duckdb.sql(f"SELECT mmsi, ts FROM read_parquet('{out}/tracks_1m/2026-11-05.parquet')").fetchall()
    assert [ts for m, ts in thin if m == 219000001] == [1793836800000 + s * 1000 for s in (0, 60, 180, 240)]
    ident = {r[0]: r for r in duckdb.sql(
        f"SELECT mmsi, imo, name, ship_type, type_group, length, draught, cls "
        f"FROM read_parquet('{out}/identity/2026-11-05.parquet')").fetchall()}
    assert ident[219000001][1:] == (9123456, "ALPHA", "Cargo", "cargo", 120.0, 7.5, "A")
    assert ident[219000002][3:5] == ("Pleasure", "pleasure")
    stats = json.loads((out / "stats" / "2026-11-05.json").read_text())
    r = stats["rows"]
    assert (r["raw"], r["class_a_b"], r["vessel_mmsi"], r["valid_position"]) == (17, 15, 14, 11)
    assert r["in_area"] == 10
    assert (r["dedup_same_second"], r["speed_gate_spikes"], r["clean"], r["thin_1m"]) == (9, 8, 7, 6)
    m = dma.write_manifest(out)
    assert m["days"] == ["2026-11-05"] and m["rows"] == 7 and m["ships"] == 2 and len(m["dataset_hash"]) == 64


def test_moved_folder_reads_and_verifies(out: Path, tmp_path: Path):
    dma.write_manifest(out)
    moved = tmp_path / "moved"
    out.rename(moved)
    assert dma.verify(moved) == []
    n = duckdb.connect().execute(f"SELECT count(*) FROM {dma.tracks_sql(moved, thin=True)}").fetchone()[0]
    assert n == 6
    p = moved / "tracks_1m" / "2026-11-05.parquet"
    p.write_bytes(p.read_bytes() + b"x")
    assert dma.verify(moved) == [f"sha256 differs: {p}"]


def test_select_days():
    listing = {f"2026-11-0{i}": 1 for i in range(1, 6)}
    assert dma.select_days(listing, 2) == ["2026-11-05", "2026-11-04"]
    assert dma.select_days(listing, 2, until="2026-11-03") == ["2026-11-03", "2026-11-02"]
    assert dma.select_days(listing, 9, until="2026-10-01") == []
