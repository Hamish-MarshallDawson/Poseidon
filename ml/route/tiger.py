"""Export our own live AIS from Tiger to Parquet, read-only, in the contract's track columns.

    python -m ml.route.tiger --out /home/aiden/data/poseidon/route/tiger [--hours 48]

Writes `positions.parquet` (mmsi, ts, lat, lon, sog_kn, cog_deg, heading_deg, nav_status, cls, src; sorted by
mmsi, ts), `statics.parquet` (latest identity per mmsi: mmsi, imo, name, ship_type, length, draught) and
`gaps.parquet` (latest version of every gap). The session is opened read-only; this never writes to Tiger.
"""
from __future__ import annotations

import argparse
import asyncio
import json
import os
import time
from pathlib import Path

import pandas as pd

from ml.route import REPO

TRACK_COLS = ["mmsi", "ts", "lat", "lon", "sog_kn", "cog_deg", "heading_deg", "nav_status", "cls", "src"]
POS_SQL = """
SELECT mmsi, ts, lat, lon, sog_kn, cog_deg, heading_deg, nav_status, cls, src
FROM positions WHERE time >= $1 AND time < $2
"""
STATICS_SQL = """
SELECT DISTINCT ON (mmsi) mmsi, imo, name, ship_type, length_m AS length, draught_m AS draught
FROM statics ORDER BY mmsi, time DESC
"""
GAPS_SQL = """
SELECT DISTINCT ON (id) id, version, mmsi, state, start_ts, end_ts, duration_s, last_lat, last_lon, last_sog_kn,
  last_cog_deg, last_nav_status, next_lat, next_lon, implied_speed_kn, coverage_flag, src
FROM gaps ORDER BY id, version DESC
"""


async def connect():
    import asyncpg
    from dotenv import load_dotenv
    load_dotenv(REPO / ".env")
    return await asyncpg.connect(os.environ["TIGER_DATABASE_URL"],
                                 server_settings={"default_transaction_read_only": "on"})


async def export(out: Path, hours: float | None) -> dict:
    out.mkdir(parents=True, exist_ok=True)
    con = await connect()
    try:
        lo, hi = await con.fetchrow("SELECT min(time), max(time) FROM positions")
        if hours:
            lo = max(lo, hi - pd.Timedelta(hours=hours))
        frames, t0 = [], time.time()
        step = pd.Timedelta(hours=1)
        cur = lo
        while cur <= hi:
            rows = await con.fetch(POS_SQL, cur, cur + step)
            if rows:
                frames.append(pd.DataFrame([tuple(r) for r in rows], columns=TRACK_COLS))
            cur += step
        pos = pd.concat(frames, ignore_index=True)
        pos = pos.drop_duplicates(["mmsi", "ts"]).sort_values(["mmsi", "ts"], kind="stable").reset_index(drop=True)
        pos = pos.astype({"mmsi": "int64", "ts": "int64", "lat": "float64", "lon": "float64",
                          "sog_kn": "float32", "cog_deg": "float32", "heading_deg": "float32",
                          "nav_status": "float32"})
        pos.to_parquet(out / "positions.parquet", index=False)
        st = pd.DataFrame([tuple(r) for r in await con.fetch(STATICS_SQL)],
                          columns=["mmsi", "imo", "name", "ship_type", "length", "draught"])
        st.to_parquet(out / "statics.parquet", index=False)
        gp = await con.fetch(GAPS_SQL)
        gaps = pd.DataFrame([dict(r) for r in gp])
        gaps.to_parquet(out / "gaps.parquet", index=False)
        man = {"source": "tiger positions (read-only)", "from": str(lo), "to": str(hi), "rows": len(pos),
               "ships": int(pos.mmsi.nunique()), "statics": len(st), "gaps": len(gaps),
               "seconds": round(time.time() - t0, 1)}
        (out / "manifest.json").write_text(json.dumps(man, indent=2))
        return man
    finally:
        await con.close()


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--out", type=Path, default=Path(os.environ.get("POSEIDON_DATA", "/home/aiden/data/poseidon")) / "route/tiger")
    ap.add_argument("--hours", type=float, default=None, help="only the newest N hours")
    a = ap.parse_args()
    print(json.dumps(asyncio.run(export(a.out, a.hours)), indent=2))


if __name__ == "__main__":
    main()
