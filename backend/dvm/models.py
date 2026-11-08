"""Canonical records, copied from section 6.1 of research/.../dark-vessel-check/06-unified-data-model.md.

Field names and units are the team contract: change them only by asking on the board.
Only the records milestone 1 uses are here; add the others from 06 when a consumer needs them.
"""
from __future__ import annotations

from typing import Literal, Optional

from pydantic import BaseModel, ConfigDict

Src = Literal["aisstream", "digitraffic", "kystverket", "dma", "gfw", "opensanctions", "derived"]
Q = Literal["late", "ts_recv_only", "sog_na", "cog_na", "hdg_na", "imo_bad_checksum",
            "dup_other_src", "jam_suspect", "own_stall"]
TypeGroup = Literal["tanker", "cargo", "passenger", "fishing", "tug_special", "military",
                    "pleasure", "other", "unknown"]


class Rec(BaseModel):
    model_config = ConfigDict(frozen=True)


class PositionReport(Rec):
    kind: Literal["pos"] = "pos"
    mmsi: int
    ts: int                      # event time, epoch ms UTC
    recv_ts: int                 # received time, epoch ms UTC
    lat: float
    lon: float
    sog_kn: Optional[float] = None
    cog_deg: Optional[float] = None
    heading_deg: Optional[int] = None
    nav_status: Optional[int] = None
    cls: Literal["A", "B"]
    msg_type: int = 0
    ts_quality: Literal["rebuilt", "recv_only", "source"]
    src: Src
    q: list[Q] = []


class VesselStatic(Rec):
    kind: Literal["static"] = "static"
    mmsi: int
    ts: int
    recv_ts: int
    imo: Optional[int] = None
    name: Optional[str] = None
    callsign: Optional[str] = None
    ship_type: Optional[int] = None
    type_group: TypeGroup = "unknown"
    dim_a_m: Optional[int] = None
    dim_b_m: Optional[int] = None
    dim_c_m: Optional[int] = None
    dim_d_m: Optional[int] = None
    length_m: Optional[int] = None
    beam_m: Optional[int] = None
    draught_m: Optional[float] = None
    destination: Optional[str] = None
    eta_utc: Optional[int] = None
    mid: int
    flag_iso2: Optional[str] = None
    src: Src
    q: list[Q] = []


Record = PositionReport | VesselStatic


class Envelope(BaseModel):          # one line of the raw log
    v: int = 1
    src: str
    recv_ts: int
    raw: object


class VesselView(BaseModel):        # what goes to the browser (06 section 4.3)
    mmsi: int
    name: Optional[str] = None
    imo: Optional[int] = None
    flag: Optional[str] = None
    type_group: TypeGroup = "unknown"
    length_m: Optional[int] = None
    lat: float
    lon: float
    sog_kn: Optional[float] = None
    cog_deg: Optional[float] = None
    heading_deg: Optional[int] = None
    last_ts: int
    status: Literal["active", "silent", "gap_open", "stale"] = "active"
    open_gap_id: Optional[str] = None
    cls: Optional[Literal["A", "B"]] = None   # AIS class of the latest position (#95); null when unknown
    risk_p: Optional[float] = None
    risk_rank: Optional[int] = None
    sanctioned: bool = False
    spoof_recent: list[str] = []
