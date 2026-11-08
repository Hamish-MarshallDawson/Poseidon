"""Read-only export of Tiger `positions`, `statics` and `gaps` to Parquet, one file per hour (#121).

    ml/.venv/bin/python -m ml.godark.tiger [--out DIR] [--since ISO] [--until ISO]

Sessions are read-only (`default_transaction_read_only`), so nothing here can write to Tiger. Existing complete hour
files are skipped, so a rerun only fetches new hours. The track columns follow the ml contract
(`mmsi, ts, lat, lon, sog_kn, cog_deg, heading_deg, nav_status, cls, src`) plus `recv_ts`, which the gap detector
replay needs.
"""
from __future__ import annotations

import argparse
import asyncio
import datetime as dt
import os
from pathlib import Path

import pandas as pd

DEFAULT_OUT = (Path(os.environ.get("POSEIDON_DATA", "/home/aiden/data/poseidon")) / "godark/tiger")
READ_ONLY = {"default_transaction_read_only": "on"}

POS_SQL = """SELECT mmsi, ts, recv_ts, lat, lon, sog_kn, cog_deg, heading_deg, nav_status, cls, src FROM positions
WHERE time >= $1 AND time < $2 ORDER BY mmsi, ts"""
STATIC_SQL = """SELECT mmsi, ts, recv_ts, imo, ship_type, type_group, length_m, draught_m, flag_iso2, src FROM statics
WHERE time >= $1 AND time < $2"""
GAPS_SQL = "SELECT * FROM gaps"


def _env_url() -> str:
    from dotenv import load_dotenv
    root = Path(__file__).resolve().parents[2]
    load_dotenv(root / ".env")
    return os.environ["TIGER_DATABASE_URL"]


async def _connect(url: str):
    import asyncpg
    return await asyncpg.connect(url, server_settings=READ_ONLY, command_timeout=600)


def _frame(rows) -> pd.DataFrame:
    return pd.DataFrame([dict(r) for r in rows]) if rows else pd.DataFrame()


async def export(out: Path, since: dt.datetime | None, until: dt.datetime | None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    c = await _connect(_env_url())
    try:
        lo, hi = await c.fetchrow("SELECT min(time), max(time) FROM positions")
        since = since or lo.replace(minute=0, second=0, microsecond=0)
        # Only whole hours that are over, so a file never changes after it is written.
        until = until or hi.replace(minute=0, second=0, microsecond=0)
        h, done = since, {"positions": 0, "statics": 0, "hours": 0}
        while h < until:
            nxt = h + dt.timedelta(hours=1)
            tag = h.strftime("%Y%m%dT%H")
            for name, sql in (("positions", POS_SQL), ("statics", STATIC_SQL)):
                f = out / name / f"{tag}.parquet"
                if f.exists():
                    continue
                f.parent.mkdir(exist_ok=True)
                df = _frame(await c.fetch(sql, h, nxt))
                tmp = f.with_suffix(".tmp")
                df.to_parquet(tmp, index=False)
                tmp.rename(f)
                done[name] += len(df)
            done["hours"] += 1
            h = nxt
        gaps = _frame(await c.fetch(GAPS_SQL))
        if "q" in gaps:
            gaps = gaps.drop(columns=["q"])
        gaps.to_parquet(out / "gaps.parquet", index=False)
        done["gaps"] = len(gaps)
        done["until"] = until.isoformat()
        return done
    finally:
        await c.close()


def load_positions(root: Path = DEFAULT_OUT) -> pd.DataFrame:
    files = sorted((root / "positions").glob("*.parquet"))
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def load_statics(root: Path = DEFAULT_OUT) -> pd.DataFrame:
    files = sorted((root / "statics").glob("*.parquet"))
    return pd.concat([pd.read_parquet(f) for f in files], ignore_index=True)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=DEFAULT_OUT)
    ap.add_argument("--since", type=dt.datetime.fromisoformat)
    ap.add_argument("--until", type=dt.datetime.fromisoformat)
    a = ap.parse_args()
    print(asyncio.run(export(a.out, a.since, a.until)))


if __name__ == "__main__":
    main()
