"""Read the Danish archive Parquet written by ml/data/dma.py (layout in ml/data/README.md) as a track and statics.

Source: Danish Maritime Authority (Søfartsstyrelsen), AIS data, http://aisdata.ais.dk/.
"""
from __future__ import annotations

import json
import time
from pathlib import Path

import pandas as pd

TRACK_COLS = ["mmsi", "ts", "lat", "lon", "sog_kn", "cog_deg", "heading_deg", "nav_status", "cls", "src"]


def days_available(d: Path) -> list[str]:
    man = json.loads((d / "manifest.json").read_text())
    return [x for x in man["days"] if (d / "tracks_1m" / f"{x}.parquet").exists()]


def _read(path: Path, **kw) -> pd.DataFrame:
    for attempt in range(5):                    # ml-data may be rewriting a day (--force): retry briefly
        try:
            return pd.read_parquet(path, **kw)
        except Exception:
            if attempt == 4:
                raise
            time.sleep(5)


def load(d: Path, days: int | None = None, thinned: bool = True, day_list: list[str] | None = None):
    """(track sorted by mmsi, ts; statics with mmsi, type_group, ship_type, length), newest `days` days."""
    d = Path(d)
    sel = day_list or days_available(d)
    if days:
        sel = sel[-days:]
    sub = "tracks_1m" if thinned else "tracks"
    tr = pd.concat([_read(d / sub / f"{x}.parquet", columns=TRACK_COLS) for x in sel], ignore_index=True)
    tr = tr.astype({"mmsi": "int64", "ts": "int64", "sog_kn": "float32", "cog_deg": "float32",
                    "heading_deg": "float32", "nav_status": "float32"})
    tr = tr.sort_values(["mmsi", "ts"], kind="stable").drop_duplicates(["mmsi", "ts"]).reset_index(drop=True)
    idt = pd.concat([_read(d / "identity" / f"{x}.parquet").assign(_day=x) for x in sel], ignore_index=True)
    idt = idt.sort_values(["mmsi", "_day"]).drop_duplicates("mmsi", keep="last")
    st = idt[["mmsi", "type_group", "ship_type", "length", "draught"]].astype({"mmsi": "int64"})
    return tr, st
