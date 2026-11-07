"""Poll Digitraffic (Fintraffic) AIS REST endpoints and log raw responses with receive time.

Run: ../venv-t-ais-live/bin/python rest_collect.py <outprefix> [seconds]
Writes <outprefix>-locations.jsonl (<outprefix>-vessels.jsonl polled every 60 s).
"""
import gzip
import json
import sys
import time

import requests

PREFIX = sys.argv[1]
DURATION = int(sys.argv[2]) if len(sys.argv) > 2 else 1800
H = {"Digitraffic-User": "hacktheburgh/feasibility", "Accept-Encoding": "gzip"}
BASE = "https://meri.digitraffic.fi/api/ais/v1"

loc = open(f"{PREFIX}-locations.jsonl", "w", buffering=1)
ves = open(f"{PREFIX}-vessels.jsonl", "w", buffering=1)
s = requests.Session()
s.headers.update(H)
t0 = time.time()
last_vessels = 0
n = 0
while time.time() - t0 < DURATION:
    tick = time.time()
    try:
        r = s.get(f"{BASE}/locations", timeout=20)
        recv = int(time.time() * 1000)
        n += 1
        loc.write(json.dumps({"recv_ts": recv, "status": r.status_code, "latency_ms": int((time.time() - tick) * 1000), "body": r.json()}) + "\n")
        if time.time() - last_vessels > 60:
            rv = s.get(f"{BASE}/vessels", timeout=20)
            ves.write(json.dumps({"recv_ts": int(time.time() * 1000), "body": rv.json()}) + "\n")
            last_vessels = time.time()
    except Exception as e:
        loc.write(json.dumps({"recv_ts": int(time.time() * 1000), "error": f"{type(e).__name__}: {e}"}) + "\n")
    if n % 20 == 0:
        print(f"{time.strftime('%H:%M:%S')} polls={n}", flush=True)
    time.sleep(max(0, 5 - (time.time() - tick)))
loc.close(); ves.close()
print("FINAL polls", n, flush=True)
