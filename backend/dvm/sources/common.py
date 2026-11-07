"""Shared pieces for every provider adapter: the Observation record, the source registry, regions and times.

An Observation is one thing a provider says about a place and time that is not a single AIS fix: an AIS presence
cell, a radar detection, a provider event (gap, encounter, loitering, port visit) or a radar scene footprint.
AIS fixes stay in `positions` and identities in `statics`, exactly as models.py defines them.
"""
from __future__ import annotations

import os
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Literal, Optional

from pydantic import BaseModel, ConfigDict

USER_AGENT = "hacktheburgh-poseidon/1.0"

ObsSrc = Literal["gfw", "sentinel1"]
Kind = Literal["ais_presence", "sar_detection", "gap", "encounter", "loitering", "port_visit", "radar_scene"]
# Observation quality flags (the observations.q column; positions/statics keep the models.py Q list).
ObsQ = Literal["available_est", "region_level", "cell_level"]


class Observation(BaseModel):
    model_config = ConfigDict(frozen=True)
    id: str                          # deterministic, so a re-run writes the same key
    src: ObsSrc
    kind: Kind
    ts: int                          # event (or interval start) time, epoch ms UTC
    end_ts: Optional[int] = None     # interval end; None for an instant
    recv_ts: int                     # when we fetched it
    available_ts: int                # when the provider first made it public (the leakage clock)
    mmsi: Optional[int] = None       # only a valid vessel MMSI; anonymous cells and scenes have none
    lat: Optional[float] = None      # point, cell centre or footprint centroid
    lon: Optional[float] = None
    bbox: Optional[tuple[float, float, float, float]] = None   # min_lon, min_lat, max_lon, max_lat
    cell_deg: Optional[float] = None  # grid size when the row is a cell aggregate
    value: Optional[float] = None    # the kind's measure: hours (presence, events) or detections (radar)
    n: Optional[int] = None          # distinct vessels behind a cell aggregate
    matched: Optional[bool] = None   # radar detection matched to AIS by the provider
    geom: Optional[dict] = None      # GeoJSON footprint (radar scenes)
    attrs: dict[str, Any] = {}       # provider extras worth keeping (ids, names, scores); never needed to join
    q: list[ObsQ] = []


# One entry per provider: what it is, how fresh, licence and the attribution the frontend must show.
SOURCES: dict[str, dict] = {
    "aisstream": {"tier": "live", "delay": "about 1 s", "licence": "AISStream terms",
                  "attribution": "AIS data: AISStream.io"},
    "digitraffic": {"tier": "live", "delay": "about 0.5 s", "licence": "CC BY 4.0",
                    "attribution": "Source: Fintraffic / digitraffic.fi, CC BY 4.0"},
    "gfw": {"tier": "delayed", "delay": "3 to 4 days", "licence": "CC BY-NC 4.0",
            "attribution": "Global Fishing Watch, globalfishingwatch.org, CC BY-NC 4.0 (non-commercial)"},
    "sentinel1": {"tier": "delayed", "delay": "1 to 13 h", "licence": "Copernicus Sentinel data licence (free, open)",
                  "attribution": "Contains modified Copernicus Sentinel data 2026, catalogue via Element 84 Earth Search"},
}

# (min_lon, min_lat, max_lon, max_lat). Regions where the team has live AIS or a study interest.
REGIONS: dict[str, tuple[float, float, float, float]] = {
    "danish_straits": (9.5, 54.0, 14.0, 58.0),
    "gulf_of_finland": (22.0, 59.0, 30.5, 61.0),
    "hormuz": (55.0, 25.5, 57.5, 27.0),
    "gulf_of_oman": (57.5, 22.0, 62.0, 26.0),
}

DAY_MS = 86_400_000


def now_ms() -> int:
    return time.time_ns() // 1_000_000


def iso_ms(s: str | None) -> Optional[int]:
    """ISO 8601 (Z or offset, any fraction) -> epoch ms; None for empty or unparseable."""
    if not s:
        return None
    try:
        s = s.strip().replace("Z", "+00:00")
        if "." in s:   # Python wants at most 6 fraction digits
            head, rest = s.split(".", 1)
            frac = "".join(ch for ch in rest if ch.isdigit())
            tz = rest[len(frac):]
            s = f"{head}.{frac[:6].ljust(6, '0')}{tz}"
        dt = datetime.fromisoformat(s)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return int(dt.timestamp() * 1000)
    except ValueError:
        return None


def day_ms(d: date) -> int:
    return int(datetime(d.year, d.month, d.day, tzinfo=timezone.utc).timestamp() * 1000)


def days(start: date, end: date) -> list[date]:
    """Inclusive list of days."""
    return [start + timedelta(n) for n in range((end - start).days + 1)]


def utc_today() -> date:
    return datetime.now(timezone.utc).date()


def bbox_intersects(a, b) -> bool:
    return not (a[2] < b[0] or a[0] > b[2] or a[3] < b[1] or a[1] > b[3])


def poly(b) -> dict:
    a, c, d, e = b
    return {"type": "Polygon", "coordinates": [[[a, c], [d, c], [d, e], [a, e], [a, c]]]}


def gfw_token() -> str:
    """GFW_API_TOKEN from the environment, else ~/.config/hedged-bets/wave.env. Never logged."""
    tok = os.getenv("GFW_API_TOKEN", "").strip()
    if tok:
        return tok
    p = Path.home() / ".config" / "hedged-bets" / "wave.env"
    if p.exists():
        for line in p.read_text().splitlines():
            if line.startswith("GFW_API_TOKEN="):
                return line.split("=", 1)[1].strip().strip('"').strip("'")
    raise RuntimeError("GFW_API_TOKEN not set (env or ~/.config/hedged-bets/wave.env)")


# ISO 3166-1 alpha-3 -> alpha-2, for GFW flags (statics.flag_iso2 is alpha-2).
_ISO = (
    "AFG AF ALA AX ALB AL DZA DZ ASM AS AND AD AGO AO AIA AI ATA AQ ATG AG ARG AR ARM AM ABW AW AUS AU AUT AT AZE AZ "
    "BHS BS BHR BH BGD BD BRB BB BLR BY BEL BE BLZ BZ BEN BJ BMU BM BTN BT BOL BO BES BQ BIH BA BWA BW BVT BV BRA BR "
    "IOT IO BRN BN BGR BG BFA BF BDI BI CPV CV KHM KH CMR CM CAN CA CYM KY CAF CF TCD TD CHL CL CHN CN CXR CX CCK CC "
    "COL CO COM KM COG CG COD CD COK CK CRI CR CIV CI HRV HR CUB CU CUW CW CYP CY CZE CZ DNK DK DJI DJ DMA DM DOM DO "
    "ECU EC EGY EG SLV SV GNQ GQ ERI ER EST EE SWZ SZ ETH ET FLK FK FRO FO FJI FJ FIN FI FRA FR GUF GF PYF PF ATF TF "
    "GAB GA GMB GM GEO GE DEU DE GHA GH GIB GI GRC GR GRL GL GRD GD GLP GP GUM GU GTM GT GGY GG GIN GN GNB GW GUY GY "
    "HTI HT HMD HM VAT VA HND HN HKG HK HUN HU ISL IS IND IN IDN ID IRN IR IRQ IQ IRL IE IMN IM ISR IL ITA IT JAM JM "
    "JPN JP JEY JE JOR JO KAZ KZ KEN KE KIR KI PRK KP KOR KR KWT KW KGZ KG LAO LA LVA LV LBN LB LSO LS LBR LR LBY LY "
    "LIE LI LTU LT LUX LU MAC MO MDG MG MWI MW MYS MY MDV MV MLI ML MLT MT MHL MH MTQ MQ MRT MR MUS MU MYT YT MEX MX "
    "FSM FM MDA MD MCO MC MNG MN MNE ME MSR MS MAR MA MOZ MZ MMR MM NAM NA NRU NR NPL NP NLD NL NCL NC NZL NZ NIC NI "
    "NER NE NGA NG NIU NU NFK NF MKD MK MNP MP NOR NO OMN OM PAK PK PLW PW PSE PS PAN PA PNG PG PRY PY PER PE PHL PH "
    "PCN PN POL PL PRT PT PRI PR QAT QA REU RE ROU RO RUS RU RWA RW BLM BL SHN SH KNA KN LCA LC MAF MF SPM PM VCT VC "
    "WSM WS SMR SM STP ST SAU SA SEN SN SRB RS SYC SC SLE SL SGP SG SXM SX SVK SK SVN SI SLB SB SOM SO ZAF ZA SGS GS "
    "SSD SS ESP ES LKA LK SDN SD SUR SR SJM SJ SWE SE CHE CH SYR SY TWN TW TJK TJ TZA TZ THA TH TLS TL TGO TG TKL TK "
    "TON TO TTO TT TUN TN TUR TR TKM TM TCA TC TUV TV UGA UG UKR UA ARE AE GBR GB USA US UMI UM URY UY UZB UZ VUT VU "
    "VEN VE VNM VN VGB VG VIR VI WLF WF ESH EH YEM YE ZMB ZM ZWE ZW"
).split()
ISO3_TO_2 = dict(zip(_ISO[::2], _ISO[1::2]))
