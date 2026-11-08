"""Import a Lab history bundle into the database: idempotent, additive.

    python -m dvm.lab.importer --bundle data/lab-history [--db URL] [--allow-tiger] [--dry-run]

The bundle is `runs.jsonl`, `proposals.jsonl`, `events.jsonl` (one record per line, docs/handoffs/lab.md; a missing
file is skipped). The database is --db, else SOURCES_DATABASE_URL, else TIGER_DATABASE_URL; Tiger Cloud is refused
without --allow-tiger.

- runs go into `model_runs` (append-only, key run_id + status): a status a run already has is skipped. A new
  status row is recorded after the run's newest row when it is further along (candidate < champion/rejected <
  retired), else before it, so re-importing an old bundle never rolls a run's status back.
- proposals are upserted into `ml_proposals` by a stable id (run_id, outcome, rationale, source filled in).
- events are inserted into `ml_events` by a hash of (ts, target, kind, run_id, version); repeats are skipped.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import logging
import os
import sys
import time
from pathlib import Path
from typing import Iterator

import asyncpg

from dvm.lab import records as R, schema
from dvm.predict import schema as predict_schema

log = logging.getLogger("dvm.lab.importer")
COLS = predict_schema.RUN_COLS + schema.RUN_EXTRA
RUN_INSERT = (f"INSERT INTO model_runs ({', '.join(COLS)}) VALUES ({', '.join(f'${i}' for i in range(1, len(COLS) + 1))}) "
              "ON CONFLICT DO NOTHING")
RUN_REQUIRED = ("run_id", "target", "model", "status", "created_at")


def read_jsonl(path: Path) -> Iterator[dict]:
    if not path.is_file():
        return
    for n, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        if not line.strip():
            continue
        try:
            d = json.loads(line)
            if not isinstance(d, dict):
                raise ValueError("not an object")
        except ValueError as e:
            log.warning("%s line %d skipped: %s", path.name, n, e)
            continue
        yield d


def run_rows(runs: list[dict], existing: dict[str, list[tuple[str, int]]], now: int) -> list[tuple]:
    """model_runs rows for the bundle's runs that aren't there yet. `existing` maps run_id to its (status,
    recorded_at) rows and is updated as rows are planned, so several statuses of one run in a bundle stack up."""
    out = []
    for d in runs:
        if any(d.get(c) is None for c in RUN_REQUIRED):
            log.warning("run skipped, needs %s: %s", ", ".join(RUN_REQUIRED), d.get("run_id"))
            continue
        rid, st = d["run_id"], d["status"]
        have = existing.setdefault(rid, [])
        if any(s == st for s, _ in have):
            continue
        created = R.to_ms(d["created_at"])
        at = R.to_ms(d.get("recorded_at")) or created
        if have:
            newest_s, newest_t = max(have, key=lambda x: x[1])
            if R.STATUS_RANK.get(st, 0) > R.STATUS_RANK.get(newest_s, 0):
                at = max(at, newest_t + 1)
            else:
                at = min(at, min(t for _, t in have) - 1)
        have.append((st, at))
        row = {**d, "created_at": created, "recorded_at": at, "train_from": R.to_ms(d.get("train_from")),
               "train_to": R.to_ms(d.get("train_to")), "config": json.dumps(d.get("config") or {}),
               "metrics": json.dumps(d.get("metrics") or {})}
        out.append(tuple(row.get(c) for c in COLS))
    return out


def proposal_rows(props: list[dict], now: int) -> list[tuple]:
    out = []
    for p in props:
        if not p.get("target"):
            log.warning("proposal skipped, no target: %s", p.get("id"))
            continue
        row = {**p, "id": R.proposal_id(p), "created_at": R.to_ms(p.get("created_at")),
               "proposal": json.dumps(p.get("proposal")), "valid": p.get("valid") is not False,
               "errors": json.dumps(p.get("errors") or []), "recorded_at": now}
        out.append(tuple(row.get(c) for c in schema.PROPOSAL_COLS))
    return out


def event_rows(events: list[dict], now: int) -> list[tuple]:
    out = []
    for e in events:
        if e.get("ts") is None or not e.get("target") or not e.get("kind"):
            log.warning("event skipped, needs ts, target, kind: %s", e)
            continue
        row = {**e, "id": R.event_id(e), "ts": R.to_ms(e["ts"]), "detail": json.dumps(e.get("detail") or {}),
               "recorded_at": now}
        out.append(tuple(row.get(c) for c in schema.EVENT_COLS))
    return out


async def import_bundle(con: asyncpg.Connection, bundle: Path, now: int | None = None, dry_run: bool = False) -> dict:
    """Read the bundle and write it (one transaction). Returns per kind how many lines were read and rows written."""
    now = now or int(time.time() * 1000)
    runs, props, events = (list(read_jsonl(bundle / f"{k}.jsonl")) for k in ("runs", "proposals", "events"))
    existing: dict[str, list[tuple[str, int]]] = {}
    ids = sorted({d["run_id"] for d in runs if d.get("run_id")})
    if ids:
        for x in await con.fetch("SELECT run_id, status, recorded_at FROM model_runs WHERE run_id = ANY($1)", ids):
            existing.setdefault(x["run_id"], []).append((x["status"], x["recorded_at"]))
    rr, pr, er = run_rows(runs, existing, now), proposal_rows(props, now), event_rows(events, now)
    new_events = len(er)
    if er:
        have = {x["id"] for x in await con.fetch("SELECT id FROM ml_events WHERE id = ANY($1)", [e[0] for e in er])}
        new_events = len({e[0] for e in er} - have)
    out = {"runs": {"read": len(runs), "new_rows": len(rr)}, "proposals": {"read": len(props), "upserted": len(pr)},
           "events": {"read": len(events), "new": new_events}, "dry_run": dry_run}
    if dry_run:
        return out
    async with con.transaction():
        if rr:
            await con.executemany(RUN_INSERT, rr)
        if pr:
            await con.executemany(schema.PROPOSAL_UPSERT, pr)
        if er:
            await con.executemany(schema.EVENT_INSERT, er)
    return out


def database_url(db: str | None, allow_tiger: bool) -> str:
    url = db or os.getenv("SOURCES_DATABASE_URL", "") or os.getenv("TIGER_DATABASE_URL", "")
    if not url:
        sys.exit("Set --db, SOURCES_DATABASE_URL or TIGER_DATABASE_URL.")
    tiger = os.getenv("TIGER_DATABASE_URL", "")
    if not allow_tiger and ((tiger and url == tiger) or "tsdb.cloud" in url or "timescale.com" in url):
        sys.exit("Refusing to write to Tiger Cloud without --allow-tiger.")
    return url


async def _main(a) -> dict:
    con = await asyncpg.connect(database_url(a.db, a.allow_tiger))
    try:
        if not a.dry_run:
            await predict_schema.setup(con)
            await schema.setup(con)
        return await import_bundle(con, Path(a.bundle), dry_run=a.dry_run)
    finally:
        await con.close()


def main(argv=None) -> None:
    ap = argparse.ArgumentParser(prog="python -m dvm.lab.importer", description=__doc__.split("\n\n")[0])
    ap.add_argument("--bundle", required=True, help="folder with runs.jsonl, proposals.jsonl, events.jsonl")
    ap.add_argument("--db")
    ap.add_argument("--allow-tiger", action="store_true")
    ap.add_argument("--dry-run", action="store_true", help="read and count, write nothing (needs the tables)")
    a = ap.parse_args(argv)
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:
        pass
    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(message)s")
    if not Path(a.bundle).is_dir():
        sys.exit(f"no bundle folder {a.bundle}")
    print(json.dumps(asyncio.run(_main(a)), indent=1))


if __name__ == "__main__":
    main()
