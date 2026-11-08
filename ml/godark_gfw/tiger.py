"""Read-only cache of the GFW rows in Tiger `observations` as local Parquet, one file per kind and month (#121).

    ml/.venv/bin/python -m ml.godark_gfw.tiger [--out DIR] [--kinds ais_presence,gap,...]

Sessions are read-only (`default_transaction_read_only`). The GFW backfill is still filling older months, so every
run asks Tiger for each month's row count and newest `recv_ts` (cheap, on the `(kind, time)` index) and re-pulls only
months that changed; the manifest records what each file holds, so the training data says which history it used.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import json
import os
import time
from pathlib import Path

import pandas as pd

DEFAULT_OUT = Path(os.getenv("GODARK_GFW_DATA") or Path(os.environ.get("POSEIDON_DATA", "/home/aiden/data/poseidon")) / "godark_gfw")
READ_ONLY = {"default_transaction_read_only": "on"}

_EVENT = "mmsi, ts, end_ts, available_ts, recv_ts, value AS hours"
COLS = {
    # one row per vessel, region and day (the region-level presence rows carry the mmsi)
    "ais_presence": "mmsi, ts, available_ts, recv_ts, value AS hours, attrs->>'region' AS region, "
                    "attrs->>'flag' AS flag, attrs->>'vesselType' AS vessel_type, attrs->>'geartype' AS geartype",
    "gap": _EVENT + ", lat, lon, (attrs->>'off_shore_km')::float8 AS off_shore_km, attrs->>'flag' AS flag, "
                    "attrs->>'vessel_type' AS vessel_type, (attrs->'areas')::text AS areas",
    "port_visit": _EVENT,
    "loitering": _EVENT + ", (attrs->'detail'->>'averageDistanceFromShoreKm')::float8 AS shore_km",
    "encounter": _EVENT,
}
KINDS = list(COLS)


def _env_url() -> str:
    from dotenv import load_dotenv
    load_dotenv(Path(__file__).resolve().parents[2] / ".env")
    return os.environ["TIGER_DATABASE_URL"]


async def _connect(url: str):
    import asyncpg
    return await asyncpg.connect(url, server_settings=READ_ONLY, command_timeout=600)


def _months(lo: dt.datetime, hi: dt.datetime) -> list[dt.datetime]:
    m, out = lo.replace(day=1, hour=0, minute=0, second=0, microsecond=0), []
    while m <= hi:
        out.append(m)
        m = (m + dt.timedelta(days=32)).replace(day=1)
    return out


async def _retry(fn, tries: int = 4):
    for i in range(tries):
        try:
            return await fn()
        except (OSError, Exception) as e:   # Tiger has dropped sessions ("administrator command"): reconnect
            if i == tries - 1 or "read-only" in str(e):
                raise
            await asyncio.sleep(5 * (i + 1))


async def export(out: Path, kinds: list[str], log=print) -> dict:
    url = _env_url()
    out.mkdir(parents=True, exist_ok=True)
    man_p = out / "manifest.json"
    man = json.loads(man_p.read_text()) if man_p.exists() else {}
    stats = {}
    for kind in kinds:
        t0, pulled, kept = time.monotonic(), 0, 0

        async def bounds():
            c = await _connect(url)
            try:
                return await c.fetchrow("SELECT min(time), max(time) FROM observations WHERE src = 'gfw' AND kind = $1"
                                        " AND mmsi IS NOT NULL", kind)
            finally:
                await c.close()

        lo, hi = await _retry(bounds)
        if lo is None:
            continue
        mk = man.setdefault(kind, {})
        for m in _months(lo, hi):
            nxt = (m + dt.timedelta(days=32)).replace(day=1)
            tag = m.strftime("%Y-%m")
            f = out / kind / f"{tag}.parquet"

            async def pull():
                c = await _connect(url)
                try:
                    n, mx = await c.fetchrow(
                        "SELECT count(*), max(recv_ts) FROM observations WHERE src = 'gfw' AND kind = $1 AND "
                        "mmsi IS NOT NULL AND time >= $2 AND time < $3", kind, m, nxt)
                    if mk.get(tag) == {"n": n, "max_recv_ts": mx} and f.exists():
                        return None
                    rows = await c.fetch(
                        f"SELECT {COLS[kind]} FROM observations WHERE src = 'gfw' AND kind = $1 AND mmsi IS NOT NULL"
                        f" AND time >= $2 AND time < $3", kind, m, nxt)
                    return n, mx, rows
                finally:
                    await c.close()

            res = await _retry(pull)
            if res is None:
                kept += mk[tag]["n"]
                continue
            n, mx, rows = res
            if n == 0:
                mk[tag] = {"n": 0, "max_recv_ts": None}
                continue
            df = pd.DataFrame([dict(r) for r in rows])
            f.parent.mkdir(exist_ok=True)
            tmp = f.with_suffix(".tmp")
            df.to_parquet(tmp, index=False)
            tmp.rename(f)
            mk[tag] = {"n": n, "max_recv_ts": mx}
            pulled += len(df)
            man_p.write_text(json.dumps(man, indent=1))   # after each month, so a stopped run resumes
        stats[kind] = {"pulled": pulled, "unchanged": kept, "from": lo.date().isoformat(),
                       "to": hi.date().isoformat(), "seconds": round(time.monotonic() - t0, 1)}
        log(kind, stats[kind])
    man_p.write_text(json.dumps(man, indent=1))
    return stats


def load(kind: str, root: Path = DEFAULT_OUT) -> pd.DataFrame:
    files = sorted((root / kind).glob("*.parquet"))
    if not files:
        return pd.DataFrame()
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--kinds", default=",".join(KINDS))
    a = ap.parse_args()
    print(json.dumps(asyncio.run(export(a.out, a.kinds.split(",")))))


if __name__ == "__main__":
    main()
