"""Danish AIS archive (Danish Maritime Authority, http://aisdata.ais.dk/) to Parquet in the ml track contract.

Data: Danish Maritime Authority, AIS data, http://aisdata.ais.dk/ (cite "Source: Danish Maritime Authority").

    python -m ml.data.dma                     # 14 newest days: download, convert, manifest
    python -m ml.data.dma --days 2            # the 2 newest
    python -m ml.data.dma --day 2026-11-05    # one named day (repeatable)
    python -m ml.data.dma --download-only     # zips only
    python -m ml.data.dma --manifest-only     # rebuild manifest.json from what is on disk

Output under --out (default /home/aiden/data/poseidon/dma, or $POSEIDON_DMA_DIR):

    raw/aisdk-YYYY-MM-DD.zip          the archive file as downloaded (size checked against the bucket listing)
    tracks/YYYY-MM-DD.parquet         cleaned positions, contract columns, sorted by mmsi, ts
    tracks_1m/YYYY-MM-DD.parquet      the same thinned to the first fix per ship per UTC minute
    identity/YYYY-MM-DD.parquet       one row per mmsi per day: imo, name, callsign, ship_type, type_group,
                                      length, width, draught, destination (latest non-empty value that day)
    stats/YYYY-MM-DD.json             per-day row counts after each cleaning step, timings, bytes, sha256
    manifest.json                     all days: rows, ships, bytes, sha256 per file, plus one dataset hash

Track columns (same as Tiger `positions`): mmsi int32, ts int64 (epoch ms UTC), lat, lon float64, sog_kn,
cog_deg float32, heading_deg, nav_status int16, cls ('A' | 'B'), src ('dma').

Cleaning, in order: keep Class A and B only (drops base stations, AtoN, SAR aircraft); keep vessel MMSIs (MID 200 to
799, same rule as the live normaliser); drop placeholder positions (|lat| > 90, |lon| > 180, lat 0 or lon 0) and
fixes outside a generous box round the Danish coverage (AREA: lat 50 to 62, lon -2 to 22); AIS
sentinels to NULL (sog >= 102.3, cog >= 360, heading >= 360, nav status 15 "Unknown value"); de-duplicate rows with
the same mmsi and second (multi-receiver copies; keep one); then a speed gate: drop a fix whose implied speed from the
previous fix of that ship exceeds 40 kn, both as an isolated spike (in and out both too fast) and, in a second pass,
any remaining jump, with 200 m of slack for GPS noise at short intervals.
"""
from __future__ import annotations

import argparse
import concurrent.futures as cf
import datetime as dt
import hashlib
import json
import os
import re
import shutil
import sys
import tempfile
import time
import xml.etree.ElementTree as ET
import zipfile
from pathlib import Path

import duckdb
import httpx

BUCKET = "http://aisdata.ais.dk.s3.eu-central-1.amazonaws.com"
DEFAULT_OUT = Path(os.environ.get("POSEIDON_DMA_DIR", "/home/aiden/data/poseidon/dma"))
LICENCE = "Source: Danish Maritime Authority (Søfartsstyrelsen), AIS data, http://aisdata.ais.dk/"
MAX_KN = 40.0
# Generous box round the Danish receiver network; a fix outside it is a receiver or GPS error (138 of 10.5 M on
# 2026-11-05, e.g. lon 116 or lat -83), which the speed gate misses when it is a ship's first fix.
AREA = {"lat_min": 50.0, "lat_max": 62.0, "lon_min": -2.0, "lon_max": 22.0}
SLACK_M = 200.0
DAY_RE = re.compile(r"^aisdk-(\d{4}-\d{2}-\d{2})\.zip$")
UA = {"User-Agent": "poseidon-hackathon-dma-fetch/1.0"}

CSV_COLUMNS = [
    "ts_text", "mobile", "mmsi", "lat", "lon", "nav_text", "rot", "sog", "cog", "heading", "imo", "callsign",
    "name", "ship_type", "cargo_type", "width", "length", "epfd", "draught", "destination", "eta", "source",
    "a", "b", "c", "d",
]

NAV_CODES = {
    "Under way using engine": 0, "At anchor": 1, "Not under command": 2, "Restricted maneuverability": 3,
    "Constrained by her draught": 4, "Moored": 5, "Aground": 6, "Engaged in fishing": 7, "Under way sailing": 8,
    "Reserved for future amendment [HSC]": 9, "Reserved for future amendment [WIG]": 10,
    "Power-driven vessel towing astern": 11, "Power-driven vessel pushing ahead or towing alongside": 12,
    "Reserved for future use": 13, "AIS-SART is active": 14,
}
# DMA ship type text to the backend's type_group (dvm/normalise.py type_group, by the ITU code each text stands for).
TYPE_GROUPS = {
    "Tanker": "tanker", "Cargo": "cargo", "Passenger": "passenger", "Fishing": "fishing", "Military": "military",
    "Pleasure": "pleasure", "Sailing": "pleasure", "Towing": "tug_special", "Towing long/wide": "tug_special",
    "Pilot": "tug_special", "SAR": "tug_special", "Tug": "tug_special", "Port tender": "tug_special",
    "Anti-pollution": "tug_special", "Law enforcement": "tug_special", "Medical": "tug_special",
    "Not party to conflict": "tug_special", "Spare 1": "tug_special", "Spare 2": "tug_special",
    "Undefined": "unknown",
}

TRACK_SCHEMA = [
    ("mmsi", "INTEGER"), ("ts", "BIGINT"), ("lat", "DOUBLE"), ("lon", "DOUBLE"), ("sog_kn", "REAL"),
    ("cog_deg", "REAL"), ("heading_deg", "SMALLINT"), ("nav_status", "SMALLINT"), ("cls", "VARCHAR"),
    ("src", "VARCHAR"),
]


def log(msg: str) -> None:
    print(f"[{dt.datetime.now(dt.UTC):%H:%M:%S}] {msg}", flush=True)


# ---------------------------------------------------------------- listing and download

def list_days(client: httpx.Client | None = None) -> dict[str, int]:
    """Every daily file at the bucket root: {'YYYY-MM-DD': size_bytes}. Follows S3 pagination."""
    own = client is None
    client = client or httpx.Client(timeout=60, headers=UA)
    ns = {"s": "http://s3.amazonaws.com/doc/2006-03-01/"}
    out: dict[str, int] = {}
    token = None
    try:
        while True:
            params = {"list-type": "2", "delimiter": "/", "prefix": "aisdk-"}
            if token:
                params["continuation-token"] = token
            r = client.get(BUCKET + "/", params=params)
            r.raise_for_status()
            root = ET.fromstring(r.content)
            for c in root.findall("s:Contents", ns):
                m = DAY_RE.match(c.findtext("s:Key", "", ns))
                if m:
                    out[m.group(1)] = int(c.findtext("s:Size", "0", ns))
            if root.findtext("s:IsTruncated", "false", ns) != "true":
                break
            token = root.findtext("s:NextContinuationToken", None, ns)
    finally:
        if own:
            client.close()
    return dict(sorted(out.items()))


def download(day: str, size: int, raw_dir: Path, retries: int = 3) -> Path:
    """Download one day's zip to raw_dir, via a .part file; skip if the file exists with the listed size."""
    raw_dir.mkdir(parents=True, exist_ok=True)
    dest = raw_dir / f"aisdk-{day}.zip"
    if dest.exists() and dest.stat().st_size == size:
        log(f"{day}: zip present ({size / 1e6:.0f} MB)")
        return dest
    part = dest.with_suffix(".zip.part")
    for attempt in range(1, retries + 1):
        t0 = time.monotonic()
        try:
            with httpx.stream("GET", f"{BUCKET}/aisdk-{day}.zip", timeout=120, headers=UA) as r:
                r.raise_for_status()
                with open(part, "wb") as f:
                    for chunk in r.iter_bytes(1 << 20):
                        f.write(chunk)
            got = part.stat().st_size
            if got != size:
                raise IOError(f"size {got} != listed {size}")
            part.rename(dest)
            secs = time.monotonic() - t0
            log(f"{day}: downloaded {size / 1e6:.0f} MB in {secs:.0f} s ({size / 1e6 / max(secs, 1e-3):.0f} MB/s)")
            return dest
        except (httpx.HTTPError, IOError) as e:
            log(f"{day}: download attempt {attempt} failed: {e}")
            part.unlink(missing_ok=True)
            if attempt == retries:
                raise
            time.sleep(10 * attempt)
    raise AssertionError("unreachable")


# ---------------------------------------------------------------- conversion

def _sql_map(d: dict, default: str = "NULL") -> str:
    parts = " ".join(f"WHEN {_q(k)} THEN {v if isinstance(v, int) else _q(v)}" for k, v in d.items())
    return f"CASE {{col}} {parts} ELSE {default} END"


def _q(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def _num(col: str, typ: str = "DOUBLE") -> str:
    return f"TRY_CAST(NULLIF(NULLIF({col}, ''), 'Unknown') AS {typ})"


def _txt(col: str) -> str:
    """Trimmed text; empty, 'Unknown' and 'Undefined' become NULL."""
    return f"NULLIF(NULLIF(NULLIF(TRIM({col}), ''), 'Unknown'), 'Undefined')"


def _haversine_m(lat1: str, lon1: str, lat2: str, lon2: str) -> str:
    return (f"2 * 6371008.8 * asin(sqrt(pow(sin(radians({lat2} - {lat1}) / 2), 2) + "
            f"cos(radians({lat1})) * cos(radians({lat2})) * pow(sin(radians({lon2} - {lon1}) / 2), 2)))")


def _too_fast(dist: str, dt_ms: str) -> str:
    # implied speed over MAX_KN with SLACK_M slack; dt 0 cannot happen after the same-second de-duplication
    return f"({dist}) > {MAX_KN} * 0.514444 * ({dt_ms}) / 1000.0 + {SLACK_M}"


def convert_csv(csv_path: Path, day: str, out: Path, threads: int = 6, memory: str = "6GB") -> dict:
    """Clean one day's CSV into tracks/, tracks_1m/, identity/ and stats/ under out. Returns the day's stats."""
    for sub in ("tracks", "tracks_1m", "identity", "stats"):
        (out / sub).mkdir(parents=True, exist_ok=True)
    tmp = out / "tmp" / day
    tmp.mkdir(parents=True, exist_ok=True)
    t0 = time.monotonic()
    con = duckdb.connect(str(tmp / "work.duckdb"))
    con.execute(f"SET threads = {threads}; SET memory_limit = '{memory}'; SET temp_directory = '{tmp}';"
                "SET preserve_insertion_order = false; SET TimeZone = 'UTC';")
    cols = ", ".join(f"'{c}': 'VARCHAR'" for c in CSV_COLUMNS)
    con.execute(f"""
        CREATE TABLE raw AS SELECT * FROM read_csv({_q(str(csv_path))}, header = true, columns = {{{cols}}},
            delim = ',', quote = '"', escape = '"', ignore_errors = true, parallel = true)""")
    n_raw = con.execute("SELECT count(*) FROM raw").fetchone()[0]

    nav = _sql_map(NAV_CODES).format(col="nav_text")
    con.execute(f"""
        CREATE TABLE typed AS
        SELECT CAST(mmsi AS INTEGER) AS mmsi,
               CAST(epoch_ms(strptime(ts_text, '%d/%m/%Y %H:%M:%S')) AS BIGINT) AS ts,
               {_num('lat')} AS lat, {_num('lon')} AS lon,
               CASE WHEN {_num('sog', 'REAL')} >= 0 AND {_num('sog', 'REAL')} < 102.3 THEN {_num('sog', 'REAL')} END
                 AS sog_kn,
               CASE WHEN {_num('cog', 'REAL')} >= 0 AND {_num('cog', 'REAL')} < 360 THEN {_num('cog', 'REAL')} END
                 AS cog_deg,
               CAST(CASE WHEN {_num('heading')} >= 0 AND {_num('heading')} < 360 THEN {_num('heading')} END
                 AS SMALLINT) AS heading_deg,
               CAST({nav} AS SMALLINT) AS nav_status,
               CASE mobile WHEN 'Class A' THEN 'A' ELSE 'B' END AS cls,
               {_num('imo', 'BIGINT')} AS imo, {_txt('name')} AS name, {_txt('callsign')} AS callsign,
               {_txt('ship_type')} AS ship_type, {_num('length', 'REAL')} AS length,
               {_num('width', 'REAL')} AS width, {_num('draught', 'REAL')} AS draught,
               {_txt('destination')} AS destination
        FROM raw
        WHERE mobile IN ('Class A', 'Class B') AND TRY_CAST(mmsi AS BIGINT) IS NOT NULL""")
    n_class = con.execute("SELECT count(*) FROM typed").fetchone()[0]
    con.execute("DROP TABLE raw")

    con.execute("""
        DELETE FROM typed WHERE NOT (mmsi BETWEEN 100000000 AND 999999999 AND mmsi // 1000000 BETWEEN 200 AND 799)
            OR ts IS NULL""")
    n_mmsi = con.execute("SELECT count(*) FROM typed").fetchone()[0]
    con.execute("DELETE FROM typed WHERE lat IS NULL OR lon IS NULL OR abs(lat) > 90 OR abs(lon) > 180 "
                "OR lat = 0 OR lon = 0")
    n_pos = con.execute("SELECT count(*) FROM typed").fetchone()[0]
    con.execute(f"DELETE FROM typed WHERE NOT (lat BETWEEN {AREA['lat_min']} AND {AREA['lat_max']} "
                f"AND lon BETWEEN {AREA['lon_min']} AND {AREA['lon_max']})")
    n_area = con.execute("SELECT count(*) FROM typed").fetchone()[0]

    # identity: latest non-empty value per field per ship, from every fix that survived the identity filters
    def latest(c: str) -> str:
        return f"arg_max({c}, ts) FILTER (WHERE {c} IS NOT NULL) AS {c}"
    tg = _sql_map(TYPE_GROUPS, "'other'").format(col="ship_type")
    con.execute(f"""
        COPY (SELECT * EXCLUDE (fixes, first_ts, last_ts),
                     CASE WHEN ship_type IS NULL THEN 'unknown' ELSE {tg} END AS type_group, fixes, first_ts, last_ts
              FROM (SELECT mmsi, CAST({_q(day)} AS DATE) AS day, arg_max(cls, ts) AS cls,
                           CAST(arg_max(imo, ts) FILTER (WHERE imo BETWEEN 1000000 AND 9999999) AS INTEGER) AS imo,
                           {latest('name')}, {latest('callsign')}, {latest('ship_type')}, {latest('length')},
                           {latest('width')}, {latest('draught')}, {latest('destination')},
                           count(*) AS fixes, min(ts) AS first_ts, max(ts) AS last_ts
                    FROM typed GROUP BY mmsi)
              ORDER BY mmsi)
        TO {_q(str(out / 'identity' / f'{day}.parquet'))} (FORMAT parquet, COMPRESSION zstd)""")

    con.execute("""
        CREATE TABLE dedup AS
        SELECT mmsi, ts, lat, lon, sog_kn, cog_deg, heading_deg, nav_status, cls FROM typed
        QUALIFY row_number() OVER (PARTITION BY mmsi, ts ORDER BY lat, lon, sog_kn NULLS LAST) = 1""")
    con.execute("DROP TABLE typed")
    n_dedup = con.execute("SELECT count(*) FROM dedup").fetchone()[0]

    # pass 1: isolated spikes (both legs too fast)
    d_in = _haversine_m("p_lat", "p_lon", "lat", "lon")
    d_out = _haversine_m("lat", "lon", "n_lat", "n_lon")
    con.execute(f"""
        CREATE TABLE pass1 AS
        SELECT * EXCLUDE (p_lat, p_lon, p_ts, n_lat, n_lon, n_ts) FROM (
          SELECT *, lag(lat) OVER w AS p_lat, lag(lon) OVER w AS p_lon, lag(ts) OVER w AS p_ts,
                 lead(lat) OVER w AS n_lat, lead(lon) OVER w AS n_lon, lead(ts) OVER w AS n_ts
          FROM dedup WINDOW w AS (PARTITION BY mmsi ORDER BY ts))
        WHERE NOT (p_ts IS NOT NULL AND n_ts IS NOT NULL
                   AND {_too_fast(d_in, 'ts - p_ts')} AND {_too_fast(d_out, 'n_ts - ts')})""")
    con.execute("DROP TABLE dedup")
    n_spike = con.execute("SELECT count(*) FROM pass1").fetchone()[0]

    # pass 2: any remaining jump from the previous kept fix
    con.execute(f"""
        CREATE TABLE clean AS
        SELECT * EXCLUDE (p_lat, p_lon, p_ts) FROM (
          SELECT *, lag(lat) OVER w AS p_lat, lag(lon) OVER w AS p_lon, lag(ts) OVER w AS p_ts
          FROM pass1 WINDOW w AS (PARTITION BY mmsi ORDER BY ts))
        WHERE p_ts IS NULL OR NOT {_too_fast(d_in, 'ts - p_ts')}""")
    con.execute("DROP TABLE pass1")
    n_clean, n_ships = con.execute("SELECT count(*), count(DISTINCT mmsi) FROM clean").fetchone()

    select = ", ".join(f"CAST({c} AS {t}) AS {c}" if c != "src" else "'dma' AS src" for c, t in TRACK_SCHEMA)
    tracks = out / "tracks" / f"{day}.parquet"
    con.execute(f"""COPY (SELECT {select} FROM clean ORDER BY mmsi, ts) TO {_q(str(tracks))}
                    (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 1000000)""")
    thin = out / "tracks_1m" / f"{day}.parquet"
    con.execute(f"""COPY (SELECT {select} FROM clean
                          QUALIFY row_number() OVER (PARTITION BY mmsi, ts // 60000 ORDER BY ts) = 1
                          ORDER BY mmsi, ts) TO {_q(str(thin))}
                    (FORMAT parquet, COMPRESSION zstd, ROW_GROUP_SIZE 1000000)""")
    n_thin = con.execute(f"SELECT count(*) FROM read_parquet({_q(str(thin))})").fetchone()[0]
    con.close()
    shutil.rmtree(tmp, ignore_errors=True)

    stats = {
        "day": day,
        "rows": {"raw": n_raw, "class_a_b": n_class, "vessel_mmsi": n_mmsi, "valid_position": n_pos,
                 "in_area": n_area,
                 "dedup_same_second": n_dedup, "speed_gate_spikes": n_spike, "clean": n_clean, "thin_1m": n_thin},
        "ships": n_ships,
        "convert_s": round(time.monotonic() - t0, 1),
        "files": {sub: _file_info(out / sub / f"{day}.parquet") for sub in ("tracks", "tracks_1m", "identity")},
    }
    (out / "stats" / f"{day}.json").write_text(json.dumps(stats, indent=2))
    return stats


def _file_info(p: Path) -> dict:
    h = hashlib.sha256()
    with open(p, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 22), b""):
            h.update(chunk)
    return {"path": str(p), "bytes": p.stat().st_size, "sha256": h.hexdigest()}


def convert_day(day: str, out: Path, threads: int, memory: str) -> dict:
    """Unzip one day's CSV to a scratch file next to the output, convert it, delete the CSV."""
    zpath = out / "raw" / f"aisdk-{day}.zip"
    t0 = time.monotonic()
    scratch = Path(tempfile.mkdtemp(prefix=f"csv-{day}-", dir=out))
    try:
        with zipfile.ZipFile(zpath) as z:
            name = next(n for n in z.namelist() if n.endswith(".csv"))
            z.extract(name, scratch)
        unzip_s = time.monotonic() - t0
        stats = convert_csv(scratch / name, day, out, threads=threads, memory=memory)
    finally:
        shutil.rmtree(scratch, ignore_errors=True)
    stats["unzip_s"] = round(unzip_s, 1)
    stats["zip_bytes"] = zpath.stat().st_size
    (out / "stats" / f"{day}.json").write_text(json.dumps(stats, indent=2))
    r = stats["rows"]
    log(f"{day}: {r['raw']:,} raw -> {r['clean']:,} clean ({r['thin_1m']:,} at 1/min), {stats['ships']:,} ships, "
        f"unzip {unzip_s:.0f} s + convert {stats['convert_s']:.0f} s")
    return stats


def write_manifest(out: Path) -> dict:
    days = []
    for p in sorted((out / "stats").glob("*.json")):
        s = json.loads(p.read_text())
        if all(Path(f["path"]).exists() for f in s["files"].values()):
            days.append(s)
    h = hashlib.sha256()
    for s in days:
        for sub in ("tracks", "tracks_1m", "identity"):
            h.update(f"{s['day']}/{sub}:{s['files'][sub]['sha256']}\n".encode())
    manifest = {
        "source": LICENCE,
        "created_at": dt.datetime.now(dt.UTC).isoformat(timespec="seconds"),
        "days": [s["day"] for s in days],
        "rows": sum(s["rows"]["clean"] for s in days),
        "rows_1m": sum(s["rows"]["thin_1m"] for s in days),
        "ships_per_day_max": max((s["ships"] for s in days), default=0),
        "bytes": {sub: sum(s["files"][sub]["bytes"] for s in days) for sub in ("tracks", "tracks_1m", "identity")},
        "zip_bytes": sum(s.get("zip_bytes", 0) for s in days),
        "dataset_hash": h.hexdigest(),
        "columns": {c: t for c, t in TRACK_SCHEMA},
        "cleaning": {"max_kn": MAX_KN, "slack_m": SLACK_M, "area": AREA},
        "per_day": days,
    }
    distinct = None
    if days:
        files = ", ".join(_q(s["files"]["identity"]["path"]) for s in days)
        distinct = duckdb.connect().execute(f"SELECT count(DISTINCT mmsi) FROM read_parquet([{files}])").fetchone()[0]
    manifest["ships"] = distinct or 0
    (out / "manifest.json").write_text(json.dumps(manifest, indent=2))
    return manifest


# ---------------------------------------------------------------- reading (for ml/route, ml/godark)

def track_files(out: Path = DEFAULT_OUT, thin: bool = False, days: list[str] | None = None) -> list[str]:
    """Paths of the converted track Parquet files, oldest day first, from the manifest."""
    m = json.loads((out / "manifest.json").read_text())
    sub = "tracks_1m" if thin else "tracks"
    return [s["files"][sub]["path"] for s in m["per_day"] if days is None or s["day"] in days]


def tracks_sql(out: Path = DEFAULT_OUT, thin: bool = False, days: list[str] | None = None) -> str:
    """A DuckDB FROM-clause over the chosen days: `SELECT * FROM {tracks_sql()} WHERE mmsi = ...`.
    Each file is sorted by mmsi, ts; across days add ORDER BY mmsi, ts."""
    return "read_parquet([" + ", ".join(_q(p) for p in track_files(out, thin, days)) + "])"


# ---------------------------------------------------------------- CLI

def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--days", type=int, default=14, help="the N newest days in the archive (default 14)")
    ap.add_argument("--day", action="append", default=[], help="a named day YYYY-MM-DD (repeatable)")
    ap.add_argument("--downloads", type=int, default=3, help="parallel downloads (default 3)")
    ap.add_argument("--converts", type=int, default=2, help="parallel conversions (default 2)")
    ap.add_argument("--threads", type=int, default=6, help="DuckDB threads per conversion")
    ap.add_argument("--memory", default="6GB", help="DuckDB memory limit per conversion")
    ap.add_argument("--download-only", action="store_true")
    ap.add_argument("--force", action="store_true", help="re-convert days that already have output")
    ap.add_argument("--manifest-only", action="store_true")
    a = ap.parse_args(argv)
    out: Path = a.out
    out.mkdir(parents=True, exist_ok=True)
    if a.manifest_only:
        m = write_manifest(out)
        log(f"manifest: {len(m['days'])} days, {m['rows']:,} rows, {m['ships']:,} ships")
        return 0

    listing = list_days()
    if a.day:
        missing = [d for d in a.day if d not in listing]
        if missing:
            log(f"not in the archive: {missing}")
            return 2
        days = sorted(a.day, reverse=True)
    else:
        days = sorted(listing, reverse=True)[: a.days]
    log(f"{len(days)} days: {days[-1]} .. {days[0]} ({sum(listing[d] for d in days) / 1e9:.1f} GB zipped)")

    done = {d for d in days if (out / "stats" / f"{d}.json").exists() and (out / "tracks" / f"{d}.parquet").exists()}
    todo = [d for d in days if a.force or d not in done]
    failures = []
    t0 = time.monotonic()
    with cf.ThreadPoolExecutor(a.downloads) as dl, cf.ProcessPoolExecutor(a.converts) as cv:
        dls = {dl.submit(download, d, listing[d], out / "raw"): d for d in todo}
        convs = {}
        for f in cf.as_completed(dls):
            d = dls[f]
            try:
                f.result()
            except Exception as e:  # noqa: BLE001 - report and continue with the other days
                failures.append((d, f"download: {e}"))
                continue
            if not a.download_only:
                convs[cv.submit(convert_day, d, out, a.threads, a.memory)] = d
        for f in cf.as_completed(convs):
            try:
                f.result()
            except Exception as e:  # noqa: BLE001
                failures.append((convs[f], f"convert: {e}"))
    if not a.download_only:
        m = write_manifest(out)
        log(f"done in {time.monotonic() - t0:.0f} s: {len(m['days'])} days, {m['rows']:,} rows "
            f"({m['rows_1m']:,} at 1/min), {m['ships']:,} ships, tracks {m['bytes']['tracks'] / 1e9:.2f} GB, "
            f"hash {m['dataset_hash'][:12]}")
    for d, e in failures:
        log(f"FAILED {d}: {e}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
