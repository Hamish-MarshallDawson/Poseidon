#!/usr/bin/env python3
"""Cheap second-day robustness check: stream the first N MB of another DMA day
(raw-deflate on the first zip member, the rows are time-sorted so this is the
early hours of the day) and repeat the gap-cell test."""
import csv, io, sys, urllib.request, zlib
from collections import Counter, defaultdict
from datetime import datetime
from math import radians, sin, cos, asin, sqrt

DAY = "2026-11-03"
N = 160 * 1024 * 1024
url = f"http://aisdata.ais.dk/aisdk-{DAY}.zip"
req = urllib.request.Request(url, headers={"Range": f"bytes=0-{N-1}"})
raw = urllib.request.urlopen(req, timeout=300).read()
print("bytes fetched:", len(raw), file=sys.stderr)
# find local file header end: assume single stored/deflated member, data starts after header
i = raw.find(b"PK\x03\x04")
name_len = int.from_bytes(raw[i+26:i+28], "little")
extra_len = int.from_bytes(raw[i+28:i+30], "little")
start = i + 30 + name_len + extra_len
d = zlib.decompressobj(-15)
text = d.decompress(raw[start:]).decode("utf-8", "replace")
lines = text.splitlines()
print("decoded MB:", len(text)//2**20, "lines:", len(lines), file=sys.stderr)

rdr = csv.reader(io.StringIO("\n".join(lines)))
hdr = next(rdr)
if hdr[0].startswith("#"):
    hdr[0] = hdr[0].lstrip("# ").strip()
ix = {c: j for j, c in enumerate(hdr)}
g = lambda r, k: r[ix[k]] if k in ix and ix[k] < len(r) else ""
last = {}
gaps = 0
cells = Counter()
msgs = Counter()
tmin = tmax = None
for r in rdr:
    try:
        ts = datetime.strptime(g(r, "Timestamp"), "%d/%m/%Y %H:%M:%S")
        lat = float(g(r, "Latitude")); lon = float(g(r, "Longitude"))
        sog = float(g(r, "SOG") or 0)
    except ValueError:
        continue
    tmin = tmin or ts; tmax = ts
    msgs[(round(lat, 1), round(lon, 1))] += 1
    m = g(r, "MMSI")
    p = last.get(m)
    if p and (ts - p[0]).total_seconds() >= 1200 and p[1] >= 3.0:
        gaps += 1
        cells[(round(p[2], 1), round(p[3], 1))] += 1
    last[m] = (ts, sog, lat, lon)
print(f"\n{DAY} slice {tmin} .. {tmax}: messages {sum(msgs.values())}, vessels {len(last)}, gaps>=20min {gaps}")
print("gap-start cells vs messages in the same slice:")
for c, n in cells.most_common(8):
    print(f"  {c} gaps {n:3d}  msgs {msgs.get(c,0):6d}")
tot = sum(cells.values())
lowtraffic = sum(n for c, n in cells.items() if msgs.get(c, 0) < 500)
print(f"  {100*lowtraffic/tot:.0f}% of gap starts are in cells with <500 messages in the slice")
