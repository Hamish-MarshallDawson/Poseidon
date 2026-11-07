"""Collect Digitraffic (Fintraffic) marine MQTT AIS messages to raw JSONL.

Run: ../venv-t-ais-live/bin/python mqtt_collect.py <outfile> [seconds]
"""
import json
import sys
import time
import threading

import paho.mqtt.client as mqtt

OUT = sys.argv[1]
DURATION = int(sys.argv[2]) if len(sys.argv) > 2 else 1800
TOPICS = [("vessels-v2/+/location", 0), ("vessels-v2/+/metadata", 0), ("vessels-v2/status", 0)]

f = open(OUT, "w", buffering=1)
counts = {"location": 0, "metadata": 0, "other": 0}
lock = threading.Lock()


def on_connect(c, ud, flags, rc, props=None):
    print(f"connected rc={rc}", flush=True)
    c.subscribe(TOPICS)
    print("subscribed", TOPICS, flush=True)


def on_message(c, ud, msg):
    recv = int(time.time() * 1000)
    kind = "location" if msg.topic.endswith("/location") else ("metadata" if msg.topic.endswith("/metadata") else "other")
    f.write(json.dumps({"recv_ts": recv, "topic": msg.topic, "payload": msg.payload.decode("utf-8", "replace")}) + "\n")
    with lock:
        counts[kind] += 1
        n = sum(counts.values())
    if n % 200 == 0:
        print(f"{time.strftime('%H:%M:%S')} n={n} {counts}", flush=True)


c = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=f"hb-feasibility-{int(time.time())}", transport="websockets")
c.ws_set_options(path="/mqtt", headers={"Digitraffic-User": "hacktheburgh/feasibility"})
c.tls_set()
c.on_connect = on_connect
c.on_message = on_message
c.connect("meri.digitraffic.fi", 443, keepalive=60)
c.loop_start()
time.sleep(DURATION)
c.loop_stop()
f.close()
print("FINAL", counts, flush=True)
