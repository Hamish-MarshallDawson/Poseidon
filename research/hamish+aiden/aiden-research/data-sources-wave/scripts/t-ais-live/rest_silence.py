"""Validate Digitraffic's cheap "silence index": from/to windows vs our own MQTT truth.

Run from $WAVE/scripts/t-ais-live:
  ../../venv-t-ais-live/bin/python rest_silence.py <mqtt.jsonl>

For several windows W ending shortly before now, compares
  (a) REST features whose last-known-position timestamp lies in W, and
  (b) vessels in our MQTT log whose last message before window end lay in W.
"""
import json
import sys
import time
import collections
import datetime as dt
import requests

MQ = sys.argv[1]
H = {"Digitraffic-User": "hacktheburgh/feasibility", "Accept-Encoding": "gzip"}
s = requests.Session()
s.headers.update(H)


def ts(x):
    return dt.datetime.fromtimestamp(x, dt.timezone.utc).strftime("%H:%M:%SZ")


fix = []
for line in open(MQ):
    r = json.loads(line)
    if r["topic"].endswith("/location"):
        try:
            p = json.loads(r["payload"])
        except Exception:
            continue
        if isinstance(p.get("time"), (int, float)):
            fix.append((int(r["topic"].split("/")[1]), p["time"]))
fix.sort(key=lambda x: x[1])
t0, t1 = fix[0][1], fix[-1][1]
last_seen = {}
for m, t in fix:
    last_seen[m] = t  # file is time-sorted
print(f"MQTT log {ts(t0)} .. {ts(t1)}, {len(last_seen)} vessels")

now = time.time()
print("\nwindow                          REST   MQTT(vessels whose last msg fell in W)")
for mins_ago in (0, 10, 20, 30, 40, 60):
    hi = t1 - mins_ago * 60 if mins_ago else t1
    lo = hi - 600
    if lo < t0 - 3600:
        continue
    r = s.get("https://meri.digitraffic.fi/api/ais/v1/locations",
              params={"from": int(lo * 1000), "to": int(hi * 1000)}, timeout=60)
    n_rest = len(r.json().get("features", []))
    n_mqtt = sum(1 for m, t in last_seen.items() if lo <= t <= hi)
    print(f"{ts(lo)}..{ts(hi)}  rest={n_rest:5d}   mqtt={n_mqtt:5d}   {r.status_code}")
print("\n(same 10-minute windows; REST retention keeps vessels that never reported again)")
