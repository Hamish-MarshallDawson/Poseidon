"""Replay a window of the raw AIS logs into positions and statics, writing only rows the store does not hold (#151).

    python -m dvm.replay_raw --from 2026-11-08T06:23:00Z --to 2026-11-08T06:28:00Z            # dry run (default)
    python -m dvm.replay_raw --from ... --to ... --write [--db URL] [--allow-tiger]           # writes

Reads DATA_DIR/raw/{aisstream,digitraffic}/<UTC hour>.jsonl and .jsonl.gz (dvm/rawlog.py), keeps the lines whose
recv_ts is in [from, to), and pushes them in recv_ts order through the live path: dvm.normalise (AISStream), the
Digitraffic normaliser with its repeat Dedup, and one FeedMerger with now_ms = recv_ts (merge.py is deterministic on
that clock), flushed after every record and once more at the end.

positions has no unique key, so every emitted record is checked against the database first, and nothing already
stored is ever inserted again:
- a position is skipped when a row with the same (mmsi, ts, src) exists, or another source's row holds the same fix
  (the merger's own rule: ts within 1 s, position within 0.5 m), which catches a fix whose first copy the live
  merger stored before the window started;
- a static is skipped when a row with the same (mmsi, ts, src) exists, or when it says nothing new against the latest
  stored identity of the ship in the last STATIC_LOOKBACK_H hours (replay starts with an empty merger, so every
  first sighting would emit a static).
The work goes one minute of record ts at a time, so memory on the database stays flat: that minute's existence checks
(at most BATCH_KEYS mmsis per query, on the (mmsi, time) indexes), then with --write its COPY into both tables, all
in one transaction under an advisory lock. An interrupted run leaves whole minutes written; run it again and it
writes only what is still missing, and a second complete run writes nothing. gaps are not replayed.

The database is --db, or TIGER_DATABASE_URL (the live store's). A dry run opens a read-only session and is allowed on
any database; writing to Tiger Cloud needs --allow-tiger, which only the Vultr server uses.
"""
from __future__ import annotations

import argparse
import asyncio
import gzip
import json
import logging
import os
import sys
from collections import Counter
from datetime import datetime, timedelta, timezone
from pathlib import Path

import asyncpg

from dvm import config
from dvm import store as dvm_store
from dvm.merge import HOLD_MS, MATCH_DEG, MATCH_TS_MS, FeedMerger, ID_FIELDS
from dvm.models import Envelope, PositionReport, Record, VesselStatic
from dvm.normalise import normalise
from dvm.sources.digitraffic import Dedup, normalise_digitraffic

log = logging.getLogger(__name__)

SOURCES = ("aisstream", "digitraffic")
MINUTE_MS = 60_000
BATCH_KEYS = 5_000          # most mmsis in one existence query (the whole window in one query ran Tiger out of memory)
STATIC_BATCH_KEYS = 1_000   # mmsis per statics query (one LIMIT 1 probe each for the identity before the minute)
STATIC_LOOKBACK_H = 12      # how far back a ship's latest stored identity is looked for (15-min chunks: 48 of them)
RECV_KEY = '"recv_ts":'


def parse_time(s: str) -> int:
    """ISO 8601 UTC (2026-11-08T06:23:00Z, or with an offset) -> epoch ms. A naive time is taken as UTC."""
    dt = datetime.fromisoformat(s.replace("Z", "+00:00"))
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1000)


def _hours(t0: int, t1: int) -> list[str]:
    h = datetime.fromtimestamp(t0 / 1000, timezone.utc).replace(minute=0, second=0, microsecond=0)
    end = datetime.fromtimestamp((t1 - 1) / 1000, timezone.utc)
    out = []
    while h <= end:
        out.append(h.strftime("%Y-%m-%dT%H"))
        h += timedelta(hours=1)
    return out


def _lines(path: Path):
    """Lines of a .jsonl or .jsonl.gz file; a truncated gzip (rotation cut short) yields what it holds."""
    opener = gzip.open if path.suffix == ".gz" else open
    try:
        with opener(path, "rt", encoding="utf-8", errors="replace") as f:
            yield from f
    except (EOFError, gzip.BadGzipFile, OSError) as e:
        log.warning("%s: read stopped early: %s", path, e)


def _recv_ts(line: str) -> int | None:
    """recv_ts without parsing the whole line (rawlog writes it third: {"v":1,"src":..,"recv_ts":N,"raw":..})."""
    i = line.find(RECV_KEY, 0, 80)
    if i < 0:
        return None
    i += len(RECV_KEY)
    j = line.find(",", i)
    try:
        return int(line[i:j])
    except ValueError:
        return None


def read_window(data_dir: Path, t0: int, t1: int, sources=SOURCES) -> tuple[list[Envelope], Counter]:
    """Envelopes with t0 <= recv_ts < t1 from every source's hour files, sorted by recv_ts (stable per file order).

    An hour can have both a .jsonl and a .jsonl.gz when a rotation was cut short, so exact repeat lines are dropped.
    """
    seen: set[str] = set()
    out: list[tuple[int, int, Envelope]] = []
    stats: Counter = Counter()
    n = 0
    for src in sources:
        d = data_dir / "raw" / src
        for hour in _hours(t0, t1):
            for path in (d / f"{hour}.jsonl", d / f"{hour}.jsonl.gz"):
                if not path.exists():
                    continue
                stats["files"] += 1
                for line in _lines(path):
                    r = _recv_ts(line)
                    if r is None or not t0 <= r < t1:
                        continue
                    line = line.rstrip("\n")
                    if line in seen:
                        stats["repeat_lines"] += 1
                        continue
                    seen.add(line)
                    try:
                        o = json.loads(line)
                        env = Envelope(src=o["src"], recv_ts=o["recv_ts"], raw=o["raw"])
                    except (ValueError, KeyError, TypeError):
                        stats["bad_lines"] += 1   # e.g. the half-written last line of the current hour
                        continue
                    stats[f"lines_{env.src}"] += 1
                    out.append((env.recv_ts, n, env))
                    n += 1
    out.sort(key=lambda x: (x[0], x[1]))
    return [e for _, _, e in out], stats


def run_pipeline(envs: list[Envelope], end_ms: int) -> tuple[list[Record], dict]:
    """The live ingest path on a recorded stream: normalise, Digitraffic Dedup, one FeedMerger on recv_ts time."""
    merger, dedup = FeedMerger(), Dedup()
    out: list[Record] = []
    for env in envs:
        out += merger.flush(env.recv_ts)   # the live 1 Hz tick, at every record instead
        if env.src == "digitraffic":
            recs = [r for r in normalise_digitraffic(env) if dedup.keep(r)]
        else:
            recs = normalise(env)
        for rec in recs:
            out += merger.push(rec, env.recv_ts)
    out += merger.flush(end_ms + HOLD_MS)   # fixes still held for the other feed's copy
    return out, merger.stats


def _minute(ms: int) -> str:
    return datetime.fromtimestamp(ms / 1000, timezone.utc).strftime("%Y-%m-%dT%H:%MZ")


def _chunks(xs: list, n: int):
    for i in range(0, len(xs), n):
        yield xs[i:i + n]


def _t(ms: int) -> datetime:
    return datetime.fromtimestamp(ms / 1000, timezone.utc)


async def existing_positions(con, recs: list[PositionReport]) -> dict[int, list[tuple]]:
    """Stored fixes near `recs` (one minute of record ts), at most BATCH_KEYS mmsis per query on (mmsi, time)."""
    have: dict[int, list[tuple]] = {}
    if not recs:
        return have
    lo, hi = min(r.ts for r in recs) - MATCH_TS_MS, max(r.ts for r in recs) + MATCH_TS_MS
    for mmsis in _chunks(sorted({r.mmsi for r in recs}), BATCH_KEYS):
        rows = await con.fetch(
            "SELECT mmsi, ts, src, lat, lon FROM positions WHERE mmsi = ANY($1::int[]) AND time >= $2 AND time <= $3",
            mmsis, _t(lo), _t(hi))
        for r in rows:
            have.setdefault(r["mmsi"], []).append((r["ts"], r["src"], r["lat"], r["lon"]))
    return have


def position_stored(rec: PositionReport, have: dict[int, list[tuple]]) -> bool:
    for ts, src, lat, lon in have.get(rec.mmsi, ()):
        if src == rec.src and ts == rec.ts:
            return True
        if (src != rec.src and abs(ts - rec.ts) <= MATCH_TS_MS and abs(lat - rec.lat) <= MATCH_DEG
                and abs(lon - rec.lon) <= MATCH_DEG):
            return True
    return False


STATIC_FIELDS = list(ID_FIELDS)
STATIC_SELECT = f"SELECT mmsi, ts, src, {', '.join(STATIC_FIELDS)} FROM statics"


async def existing_statics(con, recs: list[VesselStatic], m0: int, lookback_ms: int
                           ) -> tuple[set[tuple], dict[int, list[dict]]]:
    """For one minute [m0, m0 + 1 min) of record ts: the (mmsi, ts, src) keys stored in it, and per ship the
    stored identity rows from `lookback_ms` before it to its end, oldest first (each row is the full merged identity
    at its time). At most BATCH_KEYS mmsis per query, on (mmsi, time)."""
    keys: set[tuple] = set()
    hist: dict[int, list[dict]] = {}
    if not recs:
        return keys, hist
    cols = ", ".join(["mmsi", "ts", "src", *STATIC_FIELDS])
    for mmsis in _chunks(sorted({r.mmsi for r in recs}), min(BATCH_KEYS, STATIC_BATCH_KEYS)):
        # The minute's own rows, then per ship only its newest identity before the minute (one index probe each);
        # fetching every row of the lookback ran Tiger out of memory.
        now_rows = await con.fetch(
            STATIC_SELECT + " WHERE mmsi = ANY($1::int[]) AND time >= $2 AND time < $3 AND src <> 'gfw'",
            mmsis, _t(m0), _t(m0 + MINUTE_MS))
        prev_rows = await con.fetch(
            f"SELECT s.* FROM unnest($1::int[]) AS m(mmsi) CROSS JOIN LATERAL ("
            f"SELECT {cols} FROM statics WHERE statics.mmsi = m.mmsi AND time >= $2 AND time < $3 AND src <> 'gfw' "
            f"ORDER BY time DESC LIMIT 1) s", mmsis, _t(m0 - lookback_ms), _t(m0))
        for r in sorted([*prev_rows, *now_rows], key=lambda r: (r["mmsi"], r["ts"])):
            d = dict(r)
            if d["ts"] >= m0:
                keys.add((d["mmsi"], d["ts"], d["src"]))
            hist.setdefault(d["mmsi"], []).append(d)
    return keys, hist


def _identity_before(hist: list[dict], ts: int) -> dict:
    """Fields as of `ts`: the newest identity row at or before it."""
    cur: dict = {}
    for row in hist:
        if row["ts"] > ts:
            break
        cur = row
    return cur


def static_adds_nothing(rec: VesselStatic, ident: dict) -> bool:
    if not ident:
        return False
    for f in STATIC_FIELDS:
        v = getattr(rec, f)
        if v is None or (f == "type_group" and v == "unknown"):
            continue
        w = ident.get(f)
        if isinstance(v, float) and w is not None:
            if abs(v - w) > 1e-3:
                return False
        elif v != w:
            return False
    return True


async def plan_minute(con, pos: list[PositionReport], sta: list[VesselStatic], m0: int, lookback_ms: int,
                      planned: dict[int, dict]) -> dict:
    """Split one minute of emitted records into what to write and what is already stored. `planned` carries the
    identity each ship got from statics planned in earlier minutes (a dry run has not stored them)."""
    have = await existing_positions(con, pos)
    keys, hist = await existing_statics(con, sta, m0, lookback_ms)
    out = {"pos_write": [], "pos_skip": [], "static_write": [], "static_skip": []}
    for r in pos:
        out["pos_skip" if position_stored(r, have) else "pos_write"].append(r)
    for r in sorted(sta, key=lambda r: (r.mmsi, r.ts)):
        h = hist.setdefault(r.mmsi, [])
        if r.mmsi in planned and not any(x is planned[r.mmsi] for x in h):
            h.append(planned[r.mmsi])
            h.sort(key=lambda x: x["ts"])
        if (r.mmsi, r.ts, r.src) in keys or static_adds_nothing(r, _identity_before(h, r.ts)):
            out["static_skip"].append(r)
            continue
        out["static_write"].append(r)
        # later statics of this ship compare with the merged identity this one now stores
        row = planned[r.mmsi] = {"ts": r.ts, "src": r.src, **{f: getattr(r, f) for f in STATIC_FIELDS}}
        h.append(row)
        h.sort(key=lambda x: x["ts"])
        keys.add((r.mmsi, r.ts, r.src))
    return out


def table(p: dict) -> list[str]:
    c: Counter = Counter()
    for kind, recs in p.items():
        for r in recs:
            c[(_minute(r.ts), r.src, kind)] += 1
    kinds = ["pos_write", "pos_skip", "static_write", "static_skip"]
    lines = [f"{'minute (ts)':18} {'src':12} " + " ".join(f"{k:>12}" for k in kinds)]
    for minute, src in sorted({(m, s) for m, s, _ in c}):
        lines.append(f"{minute:18} {src:12} " + " ".join(f"{c[(minute, src, k)]:>12}" for k in kinds))
    lines.append(f"{'total':18} {'':12} " + " ".join(f"{len(p[k]):>12}" for k in kinds))
    return lines


async def write(con, p: dict) -> tuple[int, int]:
    """COPY one minute's planned rows; the caller holds the transaction and the lock."""
    pos = [dvm_store._row(r, dvm_store.POS_COLS) for r in p["pos_write"]]
    sta = [dvm_store._row(r, dvm_store.STATIC_COLS) for r in p["static_write"]]
    if pos:
        await con.copy_records_to_table("positions", records=pos, columns=["time", *dvm_store.POS_COLS])
    if sta:
        await con.copy_records_to_table("statics", records=sta, columns=["time", *dvm_store.STATIC_COLS])
    return len(pos), len(sta)


def by_minute(recs: list[Record]) -> dict[int, tuple[list, list]]:
    out: dict[int, tuple[list, list]] = {}
    for r in recs:
        pos, sta = out.setdefault(r.ts - r.ts % MINUTE_MS, ([], []))
        (pos if isinstance(r, PositionReport) else sta).append(r)
    return dict(sorted(out.items()))


def is_tiger(url: str) -> bool:
    tiger = os.getenv("TIGER_DATABASE_URL", "") or config.TIGER_DATABASE_URL
    return bool((tiger and url == tiger) or "tsdb.cloud" in url or "timescale.com" in url)


async def replay(url: str, data_dir: Path, t0: int, t1: int, dry_run: bool = True, echo=print,
                 lookback_h: float = STATIC_LOOKBACK_H) -> dict:
    envs, rstats = read_window(data_dir, t0, t1)
    recs, mstats = run_pipeline(envs, t1)
    echo(f"read {len(envs)} lines from {rstats['files']} files in {data_dir / 'raw'} "
         f"({', '.join(f'{k} {v}' for k, v in sorted(rstats.items()) if k != 'files')}); "
         f"merger emitted {mstats['pos_out']} positions, {mstats['static_out']} statics "
         f"(merged {mstats['merged']}, repeats dropped {mstats['dup_dropped'] + mstats['late_dup_dropped']})")
    kw = {"server_settings": {"default_transaction_read_only": "on"}} if dry_run else {}
    lookback_ms = int(lookback_h * 3_600_000)
    p: dict = {"pos_write": [], "pos_skip": [], "static_write": [], "static_skip": []}
    planned: dict[int, dict] = {}
    written = [0, 0]
    con = await asyncpg.connect(url, **kw)
    try:
        # One minute of record ts at a time: its existence checks (BATCH_KEYS mmsis per query), then, when writing,
        # its COPY in the same transaction under an advisory lock, so two replays can't both write a row and a
        # failure loses at most the minute being written (a re-run skips the minutes already done).
        for m0, (pos, sta) in by_minute(recs).items():
            if dry_run:
                part = await plan_minute(con, pos, sta, m0, lookback_ms, planned)
            else:
                async with con.transaction():
                    await con.execute("SELECT pg_advisory_xact_lock(151151)")
                    part = await plan_minute(con, pos, sta, m0, lookback_ms, planned)
                    n_pos, n_sta = await write(con, part)
                written[0] += n_pos
                written[1] += n_sta
            for k, v in part.items():
                p[k] += v
    finally:
        await con.close()
    for line in table(p):
        echo(line)
    if dry_run:
        echo("DRY RUN: nothing written. Add --write to write the *_write rows.")
    else:
        echo(f"WROTE {written[0]} positions and {written[1]} statics.")
    return {"lines": len(envs), **{k: len(v) for k, v in p.items()},
            "written_positions": written[0], "written_statics": written[1]}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python -m dvm.replay_raw", description=__doc__.split("\n\n")[0])
    ap.add_argument("--from", dest="t0", required=True, help="window start, UTC ISO 8601 (inclusive, on recv_ts)")
    ap.add_argument("--to", dest="t1", required=True, help="window end, UTC ISO 8601 (exclusive)")
    ap.add_argument("--db", default="", help="database URL (default TIGER_DATABASE_URL)")
    ap.add_argument("--data-dir", type=Path, default=config.DATA_DIR, help=f"default {config.DATA_DIR}")
    g = ap.add_mutually_exclusive_group()
    g.add_argument("--dry-run", action="store_true", default=True, help="print what would be written (default)")
    g.add_argument("--write", action="store_true", help="write the missing rows")
    ap.add_argument("--static-lookback-hours", type=float, default=STATIC_LOOKBACK_H,
                    help=f"how far back a ship's stored identity is compared (default {STATIC_LOOKBACK_H})")
    ap.add_argument("--allow-tiger", action="store_true", help="allow --write to Tiger Cloud (the server only)")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    t0, t1 = parse_time(args.t0), parse_time(args.t1)
    if not 0 < t1 - t0 <= 6 * 3_600_000:
        sys.exit("--to must be after --from, and the window at most 6 hours")
    url = args.db or os.getenv("TIGER_DATABASE_URL", "") or config.TIGER_DATABASE_URL
    if not url:
        sys.exit("No database: pass --db or set TIGER_DATABASE_URL")
    if args.write and is_tiger(url) and not args.allow_tiger:
        sys.exit("Refusing to write to Tiger Cloud without --allow-tiger (only the Vultr server writes to Tiger).")
    asyncio.run(replay(url, args.data_dir, t0, t1, dry_run=not args.write,
                       lookback_h=args.static_lookback_hours))


if __name__ == "__main__":
    main()
