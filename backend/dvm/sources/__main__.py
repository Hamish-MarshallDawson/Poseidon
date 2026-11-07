"""python -m dvm.sources <command>. See dvm/sources/README.md.

  setup                                   create the tables (idempotent)
  digitraffic [--minutes N]               stream live Digitraffic (forever without --minutes)
  poll {gfw,sentinel1} [--once]           fetch the recent windows that may have changed, then sleep
  backfill {gfw,sentinel1} --start D --end D [--force]
  backfill digitraffic                    replay data/raw/digitraffic into the database
  backfill-back {gfw,sentinel1} [--until D] [--max-db-gb N]
                                          from today backwards until stopped, history ends, or the size cap
  readonly-role [--role R]                create a read-only login; its URL goes to ~/.config/hedged-bets/readonly.env
  status                                  freshness per source and row counts

The database is SOURCES_DATABASE_URL (or --db). Tiger Cloud is refused unless --allow-tiger is given, which is
for after the team has agreed the schema (see README "Proposal").
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
from datetime import date
from pathlib import Path

from dvm.sources import jobs, query, schema
from dvm.sources.common import REGIONS, now_ms


def database_url(args) -> str:
    url = args.db or os.getenv("SOURCES_DATABASE_URL", "")
    if not url:
        sys.exit("Set SOURCES_DATABASE_URL or --db (a local TimescaleDB; see README).")
    tiger = os.getenv("TIGER_DATABASE_URL", "")
    if not args.allow_tiger and ((tiger and url == tiger) or "tsdb.cloud" in url or "timescale.com" in url):
        sys.exit("Refusing to write to Tiger Cloud without --allow-tiger (schema not agreed yet).")
    return url


async def status(url: str) -> dict:
    pool = await jobs.connect(url)
    try:
        async with pool.acquire() as con:
            kinds = await con.fetch("SELECT src, kind, count(*) AS n, count(DISTINCT mmsi) AS vessels "
                                    "FROM observations GROUP BY 1, 2 ORDER BY 1, 2")
            pos = await con.fetch("SELECT src, count(*) AS n, count(DISTINCT mmsi) AS vessels FROM positions GROUP BY 1")
            sta = await con.fetch("SELECT src, count(*) AS n, count(DISTINCT mmsi) AS vessels FROM statics GROUP BY 1")
            wins = await con.fetch("SELECT src, stream, status, count(*) AS n FROM source_windows GROUP BY 1, 2, 3")
            fresh = await query.freshness(con, now_ms())
    finally:
        await pool.close()
    return {"observations": [dict(r) for r in kinds], "positions": [dict(r) for r in pos],
            "statics": [dict(r) for r in sta], "windows": [dict(r) for r in wins], "freshness": fresh}


def readonly_role(url: str, role: str) -> dict:
    """The password is generated here and written only to a 0600 file; it is never printed."""
    import secrets
    from urllib.parse import quote, urlsplit, urlunsplit

    password = secrets.token_urlsafe(24)
    asyncio.run(jobs.create_readonly_role(url, role, password))
    u = urlsplit(url)
    host = u.hostname + (f":{u.port}" if u.port else "")
    ro_url = urlunsplit((u.scheme, f"{quote(role)}:{quote(password)}@{host}", u.path, u.query, ""))
    path = Path.home() / ".config" / "hedged-bets" / "readonly.env"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.touch(mode=0o600, exist_ok=True)
    path.chmod(0o600)
    path.write_text(f"READONLY_DATABASE_URL={ro_url}\n")
    return {"role": role, "url_written_to": str(path)}


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python -m dvm.sources")
    ap.add_argument("--db")
    ap.add_argument("--allow-tiger", action="store_true")
    ap.add_argument("--data-dir", type=Path, default=None, help="raw dumps go here (default: backend DATA_DIR)")
    sub = ap.add_subparsers(dest="cmd", required=True)
    sub.add_parser("setup")
    sub.add_parser("status")
    d = sub.add_parser("digitraffic")
    d.add_argument("--minutes", type=float)
    p = sub.add_parser("poll")
    p.add_argument("src", choices=["gfw", "sentinel1"])
    p.add_argument("--regions", default=",".join(REGIONS))
    p.add_argument("--once", action="store_true")
    b = sub.add_parser("backfill")
    b.add_argument("src", choices=["gfw", "sentinel1", "digitraffic"])
    b.add_argument("--regions", default=",".join(REGIONS))
    b.add_argument("--start", type=date.fromisoformat)
    b.add_argument("--end", type=date.fromisoformat)
    b.add_argument("--force", action="store_true")
    bb = sub.add_parser("backfill-back")
    bb.add_argument("src", choices=["gfw", "sentinel1"])
    bb.add_argument("--regions", default=",".join(REGIONS))
    bb.add_argument("--until", type=date.fromisoformat, default=date(2017, 1, 1))
    bb.add_argument("--max-db-gb", type=float, default=jobs.DEFAULT_MAX_DB_GB)
    ro = sub.add_parser("readonly-role")
    ro.add_argument("--role", default="poseidon_ro")
    args = ap.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)   # request lines would be noise (and carry params)
    url = database_url(args)
    if args.data_dir is None:
        from dvm.config import DATA_DIR
        args.data_dir = DATA_DIR

    def regions():
        rs = [r.strip() for r in args.regions.split(",") if r.strip()]
        bad = [r for r in rs if r not in REGIONS]
        if bad:
            sys.exit(f"unknown region(s) {bad}; known: {list(REGIONS)}")
        return rs

    if args.cmd == "setup":
        async def _setup():
            pool = await jobs.connect(url)
            await pool.close()
        asyncio.run(_setup())
        out = {"ok": True, "tables": ["observations", "source_windows"]}
    elif args.cmd == "status":
        out = asyncio.run(status(url))
    elif args.cmd == "digitraffic":
        out = asyncio.run(jobs.stream_digitraffic(url, args.minutes * 60 if args.minutes else None, args.data_dir))
    elif args.cmd == "poll":
        out = asyncio.run(jobs.poll(url, args.src, regions(), once=args.once, data_dir=args.data_dir))
    elif args.cmd == "backfill-back":
        out = asyncio.run(jobs.backfill_back(url, args.src, regions(), until=args.until, max_db_gb=args.max_db_gb,
                                             data_dir=args.data_dir))
    elif args.cmd == "readonly-role":
        out = readonly_role(url, args.role)
    elif args.src == "digitraffic":
        out = asyncio.run(jobs.backfill_digitraffic_raw(url, args.data_dir, force=args.force))
    else:
        if not args.start or not args.end:
            sys.exit("backfill needs --start and --end (YYYY-MM-DD, inclusive)")
        out = asyncio.run(jobs.backfill(url, args.src, regions(), args.start, args.end, force=args.force,
                                        data_dir=args.data_dir))
    print(json.dumps(out, indent=1, default=str))


if __name__ == "__main__":
    main()
