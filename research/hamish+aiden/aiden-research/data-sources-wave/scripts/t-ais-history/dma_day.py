#!/usr/bin/env python3
"""Stream one DMA day (Danish AIS) and measure what the archive is good for.

Inputs:  ../../data/t-ais-history/aisdk-2026-11-01.zip  (one CSV inside)
Outputs: ../../data/t-ais-history/day_<date>/
          vessels.csv        one row per MMSI
          gaps.csv           silence intervals >= 20 min for moving vessels
          classa_1630_1700Z.csv  Class A positions in a 30-min window (for t-match)
          report_<date>.json summary numbers

Single pass, stdlib only. Rows in the DMA CSV are time-sorted.
"""
import csv
import io
import json
import os
import statistics as st
import sys
import zipfile
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone

HERE = os.path.dirname(os.path.abspath(__file__))
DAY = "2026-11-01"
ZIP = os.path.join(HERE, "..", "..", "data", "t-ais-history", f"aisdk-{DAY}.zip")
OUT = os.path.join(HERE, "..", "..", "data", "t-ais-history", f"day_{DAY}")

# Danish waters / western Baltic, the box the archive actually covers
BOX = (53.0, 58.5, 7.5, 16.0)  # lat_min, lat_max, lon_min, lon_max
WIN0 = datetime.strptime("2026-11-01 16:30:00", "%Y-%m-%d %H:%M:%S")
WIN1 = datetime.strptime("2026-11-01 17:00:00", "%Y-%m-%d %H:%M:%S")
GAP_MIN = 20            # minutes of silence counted as a gap
MOVING_SOG = 3.0        # knots
CLASS_A_MOBILE = "Class A"


def fnum(s, default=None):
    try:
        v = float(s)
        return v
    except (TypeError, ValueError):
        return default


def hav_nm(lat1, lon1, lat2, lon2):
    from math import radians, sin, cos, asin, sqrt
    r = 3440.065
    p1, p2 = radians(lat1), radians(lat2)
    dp, dl = p2 - p1, radians(lon2 - lon1)
    a = sin(dp / 2) ** 2 + cos(p1) * cos(p2) * sin(dl / 2) ** 2
    return 2 * r * asin(sqrt(a))


def main():
    os.makedirs(OUT, exist_ok=True)
    zf = zipfile.ZipFile(ZIP)
    name = [n for n in zf.namelist() if n.lower().endswith(".csv")][0]
    print("member:", name, "compressed", zf.getinfo(name).compress_size,
          "uncompressed", zf.getinfo(name).file_size, file=sys.stderr)

    tsfmt = "%d/%m/%Y %H:%M:%S"
    cols = None

    mob = Counter()            # Type of mobile
    src = Counter()            # Data source type
    fix = Counter()            # Type of position fixing device
    nav = Counter()            # Navigational status
    rows = 0
    bad_ts = bad_pos = 0
    out_of_box = 0
    per_v = defaultdict(lambda: {
        "class": None, "first": None, "last": None, "n": 0,
        "imo": "", "name": "", "shiptype": "", "draught": "", "dest": "",
        "callsign": "", "length": "", "width": "", "flag": None,
        "sog_max": 0.0, "moved": False, "lat0": None, "lon0": None,
        "lat1": None, "lon1": None, "deltas": [], "pos_bad": 0,
        "statics": 0, "heading_null": 0, "dup_ts": 0, "ins_box": 0,
    })
    lastpos = {}
    gaps = []
    win_rows = []

    with zf.open(name) as raw:
        f = io.TextIOWrapper(raw, encoding="utf-8", errors="replace", newline="")
        rdr = csv.reader(f)
        header = next(rdr)
        if header[0].startswith("#"):
            header[0] = header[0].lstrip("# ").strip()
        cols = header
        idx = {c: i for i, c in enumerate(cols)}
        need = ["Timestamp", "Type of mobile", "MMSI", "Latitude", "Longitude",
                "Navigational status", "SOG", "COG", "Heading", "IMO", "Callsign",
                "Name", "Ship type", "Cargo type", "Width", "Length",
                "Type of position fixing device", "Draught", "Destination",
                "Data source type"]
        missing = [c for c in need if c not in idx]
        if missing:
            print("MISSING COLUMNS:", missing, file=sys.stderr)
        I = lambda r, k: r[idx[k]] if k in idx and idx[k] < len(r) else ""

        for r in rdr:
            rows += 1
            ts_s = I(r, "Timestamp")
            try:
                ts = datetime.strptime(ts_s, tsfmt)
            except ValueError:
                bad_ts += 1
                continue
            mobi = I(r, "Type of mobile")
            mob[mobi] += 1
            src[I(r, "Data source type")] += 1
            mmsi = I(r, "MMSI").strip()
            if not mmsi:
                continue
            v = per_v[mmsi]
            if v["class"] is None:
                v["class"] = mobi
            if v["class"] != mobi:
                v["class"] = mobi if mobi == CLASS_A_MOBILE else v["class"]
            c = int(mmsi[0]) if mmsi.isdigit() else -1
            v["flag"] = {2: "EU(2xx)", 3: "NA(3xx)"}.get(c, "MID" + mmsi[0] if c >= 0 else "?")

            # static fields (ship's identity) come in type-5 messages
            nm = I(r, "Name").strip()
            if nm and nm not in ("Unknown", "", "Undefined"):
                v["name"] = v["name"] or nm
            imo = I(r, "IMO").strip()
            if imo and imo not in ("Unknown", "Undefined"):
                v["imo"] = v["imo"] or imo
            stype = I(r, "Ship type").strip()
            if stype and stype not in ("Unknown", "Undefined"):
                v["shiptype"] = v["shiptype"] or stype
            dr = I(r, "Draught").strip()
            if dr and dr not in ("Unknown", "Undefined", "0.0"):
                v["draught"] = v["draught"] or dr
            de = I(r, "Destination").strip()
            if de and de not in ("Unknown", "Undefined"):
                v["dest"] = v["dest"] or de
            cs = I(r, "Callsign").strip()
            if cs and cs not in ("Unknown", "Undefined"):
                v["callsign"] = v["callsign"] or cs
            ln = I(r, "Length").strip()
            if ln and ln not in ("Unknown", "Undefined", "0"):
                v["length"] = v["length"] or ln
            wd = I(r, "Width").strip()
            if wd and wd not in ("Unknown", "Undefined", "0"):
                v["width"] = v["width"] or wd

            lat = fnum(I(r, "Latitude"))
            lon = fnum(I(r, "Longitude"))
            nav[I(r, "Navigational status")] += 1
            fix[I(r, "Type of position fixing device")] += 1
            if lat is None or lon is None or not (-90 <= lat <= 90) or not (-180 <= lon <= 180):
                bad_pos += 1
                v["pos_bad"] += 1
                continue
            if not (BOX[0] <= lat <= BOX[1] and BOX[2] <= lon <= BOX[3]):
                out_of_box += 1
            else:
                v["ins_box"] += 1

            sog = fnum(I(r, "SOG"), 0.0) or 0.0
            if sog > v["sog_max"]:
                v["sog_max"] = sog

            # reporting-interval and gap statistics, using consecutive positions
            prev = lastpos.get(mmsi)
            if prev is not None:
                dt = (ts - prev[0]).total_seconds()
                if dt == 0:
                    v["dup_ts"] += 1
                elif dt > 0:
                    v["deltas"].append(dt)
                    if dt >= GAP_MIN * 60 and prev[1] >= MOVING_SOG:
                        gaps.append(dict(
                            mmsi=mmsi, name=v["name"], shiptype=v["shiptype"],
                            imo=v["imo"], cls=v["class"],
                            gap_start=prev[0].isoformat(sep=" "),
                            gap_end=ts.isoformat(sep=" "),
                            gap_min=round(dt / 60, 1),
                            lat=prev[2], lon=prev[3], sog=prev[1],
                            dist_nm=round(hav_nm(prev[2], prev[3], lat, lon), 1)))
                if dt > 0 and hav_nm(prev[2], prev[3], lat, lon) > 0.1:
                    v["moved"] = True
            lastpos[mmsi] = (ts, sog, lat, lon)

            if v["first"] is None:
                v["first"] = ts
            v["last"] = ts
            v["n"] += 1
            if v["lat0"] is None:
                v["lat0"], v["lon0"] = lat, lon
            v["lat1"], v["lon1"] = lat, lon

            if WIN0 <= ts <= WIN1 and mobi == CLASS_A_MOBILE:
                win_rows.append([
                    ts.strftime("%Y-%m-%dT%H:%M:%SZ"), mmsi,
                    f"{lat:.5f}", f"{lon:.5f}", I(r, "SOG"), I(r, "COG"),
                    I(r, "Heading"), I(r, "Navigational status"),
                    v["name"], v["imo"], v["shiptype"], v["length"], v["width"],
                    v["draught"], I(r, "Destination")])

    print("rows:", rows, "bad timestamps:", bad_ts, "bad positions:", bad_pos,
          "outside box:", out_of_box, file=sys.stderr)

    # ---- per-vessel table
    vpath = os.path.join(OUT, "vessels.csv")
    vcols = ["mmsi", "cls", "name", "imo", "shiptype", "length", "width",
             "draught", "dest", "callsign", "n_pos", "first_ts", "last_ts",
             "median_interval_s", "p90_interval_s", "gaps_20min", "sog_max",
             "pos_bad", "dup_ts", "in_box"]
    with open(vpath, "w", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(vcols)
        for m, v in per_v.items():
            if v["n"] == 0:
                continue
            d = sorted(v["deltas"])
            med = st.median(d) if d else ""
            p90 = d[int(0.9 * (len(d) - 1))] if d else ""
            w.writerow([m, v["class"], v["name"], v["imo"], v["shiptype"],
                        v["length"], v["width"], v["draught"], v["dest"],
                        v["callsign"], v["n"], v["first"].isoformat(sep=" "),
                        v["last"].isoformat(sep=" "), med, p90, 0,
                        round(v["sog_max"], 1), v["pos_bad"], v["dup_ts"],
                        v["ins_box"]])

    if gaps:
        with open(os.path.join(OUT, "gaps.csv"), "w", newline="") as fo:
            w = csv.DictWriter(fo, fieldnames=list(gaps[0].keys()))
            w.writeheader()
            w.writerows(gaps)

    with open(os.path.join(OUT, "classa_1630_1700Z.csv"), "w", newline="") as fo:
        w = csv.writer(fo)
        w.writerow(["ts_utc", "mmsi", "lat", "lon", "sog", "cog", "heading",
                    "nav_status", "name", "imo", "ship_type", "length", "width",
                    "draught", "destination"])
        w.writerows(win_rows)

    # ---- summary
    byclass = Counter()
    for v in per_v.values():
        byclass[v["class"]] += 1
    a = [v for v in per_v.values() if v["class"] == CLASS_A_MOBILE and v["n"] > 2]
    allint = [x for v in a for x in v["deltas"][:2000]]
    summary = dict(
        day=DAY, rows=rows, bad_ts=bad_ts, bad_pos=bad_pos,
        outside_box_rows=out_of_box,
        distinct_mmsi=len(per_v), by_class=dict(byclass),
        mobile_types=dict(mob), data_source=dict(src),
        pos_fixing=dict(fix), nav_status=dict(nav),
        classA_vessels=len(a),
        classA_with_name=sum(1 for v in a if v["name"]),
        classA_with_imo=sum(1 for v in a if v["imo"]),
        classA_with_shiptype=sum(1 for v in a if v["shiptype"]),
        classA_with_draught=sum(1 for v in a if v["draught"]),
        classA_with_dest=sum(1 for v in a if v["dest"]),
        classA_with_length=sum(1 for v in a if v["length"]),
        classA_with_callsign=sum(1 for v in a if v["callsign"]),
        classA_total_pos=sum(v["n"] for v in a),
        classA_median_interval_s=st.median(allint) if allint else None,
        classA_interval_p10_p90=(
            sorted(allint)[int(0.1 * len(allint))] if allint else None,
            sorted(allint)[int(0.9 * len(allint))] if allint else None),
        gaps_20min=len(gaps),
        vessels_with_gap=len({g["mmsi"] for g in gaps}),
        gap_minutes_total=round(sum(g["gap_min"] for g in gaps), 1),
        window_rows=len(win_rows),
        window_vessels=len({w[1] for w in win_rows}),
    )
    with open(os.path.join(OUT, f"report_{DAY}.json"), "w") as f:
        json.dump(summary, f, indent=1, sort_keys=True, default=str)
    print(json.dumps(summary, indent=1, sort_keys=True, default=str))


if __name__ == "__main__":
    t0 = datetime.now()
    main()
    print("elapsed s:", (datetime.now() - t0).total_seconds(), file=sys.stderr)
