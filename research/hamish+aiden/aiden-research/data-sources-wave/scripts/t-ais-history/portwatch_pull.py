#!/usr/bin/env python3
"""Pull PortWatch daily chokepoint series (no account) and characterise lag + anomalies.

Source: IMF/PortWatch public ArcGIS FeatureServer, layer Daily_Chokepoints_Data.
Writes CSV per chokepoint to ../../data/t-ais-history/portwatch/
"""
import csv
import json
import os
import sys
import urllib.parse
import urllib.request
from datetime import date, datetime, timedelta, timezone

BASE = ("https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/"
        "Daily_Chokepoints_Data/FeatureServer/0/query")
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "..", "..", "data", "t-ais-history", "portwatch")
FIELDS = ("date,year,month,day,portid,portname,n_container,n_dry_bulk,"
          "n_general_cargo,n_roro,n_tanker,n_cargo,n_total,"
          "capacity_container,capacity_dry_bulk,capacity_general_cargo,"
          "capacity_roro,capacity_tanker,capacity_cargo,capacity")


def query(where, orderby="date ASC", extra=None, page=1000):
    rows, offset = [], 0
    while True:
        p = {"f": "json", "where": where, "outFields": FIELDS,
             "returnGeometry": "false", "orderByFields": orderby,
             "resultOffset": offset, "resultRecordCount": page}
        if extra:
            p.update(extra)
        url = BASE + "?" + urllib.parse.urlencode(p)
        with urllib.request.urlopen(url, timeout=180) as r:
            d = json.load(r)
        feats = d.get("features", [])
        rows += [f["attributes"] for f in feats]
        if len(feats) < page:
            return rows
        offset += len(feats)
        if offset > 200000:
            return rows


if __name__ == "__main__":
    os.makedirs(OUT, exist_ok=True)
    rows = query("year >= 2024")
    print("total rows 2024+:", len(rows))
    by = {}
    for r in rows:
        by.setdefault(r["portname"], []).append(r)
    for name, rs in by.items():
        rs.sort(key=lambda r: r["date"])
        path = os.path.join(OUT, name.replace(" ", "_") + ".csv")
        with open(path, "w", newline="") as f:
            w = csv.DictWriter(f, fieldnames=rs[0].keys())
            w.writeheader()
            w.writerows(rs)
        last = rs[-1]["date"]
        print(f"{name:26s} n={len(rs):5d} first={rs[0]['date']} last={last}")
    # lag
    today = date.today()
    lasts = {n: datetime.utcfromtimestamp(rs[-1]["date"] / 1000).date() for n, rs in by.items()}
    print("today:", today, "median lag days:", sorted((today - v).days for v in lasts.values()))
