#!/usr/bin/env python3
"""Paired polling: CetaHAV /ais (slow, ~13 s) + Digitraffic /locations (fast).
Goal: estimate the age of CetaHAV positions by snapping them onto Digitraffic's
near-real-time tracks for the same MMSI.

Writes two JSONL files: ceta lines and digi lines, one per poll.
"""
import json, sys, time, requests

CETA = "https://cetahav.org/api/public/v1/ais"
DIGI = "https://meri.digitraffic.fi/api/ais/v1/locations"
OUT = sys.argv[1]
MINUTES = float(sys.argv[2]) if len(sys.argv) > 2 else 10
DIGI_EVERY = 20.0
CETA_EVERY = 60.0

def get(url, hdrs):
    t0 = time.time()
    r = requests.get(url, headers=hdrs, timeout=90)
    return r.status_code, r.content, time.time() - t0

fc = open(OUT + ".ceta.jsonl", "w")
fd = open(OUT + ".digi.jsonl", "w")
start = time.time()
next_d = start
next_c = start
while time.time() - start < MINUTES * 60:
    now = time.time()
    if now >= next_c:
        t0 = time.time()
        rec = {"iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)), "t": round(t0, 3)}
        try:
            st, body, el = get(CETA, {"User-Agent": "hacktheburgh/feasibility"})
            d = json.loads(body)
            rec.update(status=st, elapsed=round(el, 2))
            rec["features"] = [
                {"mmsi": f["properties"]["mmsi"], "name": f["properties"].get("name"),
                 "sog": f["properties"].get("sog"), "cog": f["properties"].get("cog"),
                 "lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1]}
                for f in d.get("features", [])]
            rec["n"] = len(rec["features"])
        except Exception as e:
            rec.update(status="ERROR", error=f"{type(e).__name__}: {e}")
        fc.write(json.dumps(rec) + "\n"); fc.flush()
        next_c = time.time() + CETA_EVERY
    now = time.time()
    if now >= next_d:
        t0 = time.time()
        rec = {"iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0)), "t": round(t0, 3)}
        try:
            st, body, el = get(DIGI, {"Digitraffic-User": "hacktheburgh/feasibility"})
            d = json.loads(body)
            rec.update(status=st, elapsed=round(el, 2))
            rec["features"] = [
                {"mmsi": f["properties"]["mmsi"], "sog": f["properties"].get("sog"),
                 "ts": f["properties"].get("timestampExternal"),
                 "lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1]}
                for f in d.get("features", [])]
            rec["n"] = len(rec["features"])
        except Exception as e:
            rec.update(status="ERROR", error=f"{type(e).__name__}: {e}")
        fd.write(json.dumps(rec) + "\n"); fd.flush()
        next_d = time.time() + DIGI_EVERY
    time.sleep(1.0)
print("done", time.time() - start)
