#!/usr/bin/env python3
"""Poll CetaHAV /api/public/v1/ais for N minutes, one JSONL line per poll."""
import json, sys, time, urllib.request, statistics

URL = "https://cetahav.org/api/public/v1/ais"
OUT = sys.argv[1]
MINUTES = float(sys.argv[2]) if len(sys.argv) > 2 else 12
INTERVAL = float(sys.argv[3]) if len(sys.argv) > 3 else 20

start = time.time()
n = 0
with open(OUT, "w") as f:
    while time.time() - start < MINUTES * 60:
        t0 = time.time()
        rec = {"t_req": round(t0, 3), "iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(t0))}
        try:
            req = urllib.request.Request(URL, headers={"User-Agent": "hacktheburgh/feasibility"})
            with urllib.request.urlopen(req, timeout=60) as r:
                body = r.read()
                rec.update(status=r.status, bytes=len(body),
                           elapsed=round(time.time() - t0, 2),
                           cache=r.headers.get("cf-cache-status"),
                           cdn_age=r.headers.get("age"),
                           ctype=r.headers.get("content-type"))
            fc = json.loads(body)
            feats = fc.get("features", [])
            rec["n"] = len(feats)
            rec["features"] = [
                {"mmsi": ft["properties"].get("mmsi"),
                 "name": ft["properties"].get("name"),
                 "sog": ft["properties"].get("sog"),
                 "cog": ft["properties"].get("cog"),
                 "hdg": ft["properties"].get("heading"),
                 "lon": ft["geometry"]["coordinates"][0],
                 "lat": ft["geometry"]["coordinates"][1]}
                for ft in feats]
            rec["keys"] = sorted({k for ft in feats for k in ft["properties"]})
        except Exception as e:
            rec.update(status="ERROR", error=f"{type(e).__name__}: {e}",
                       elapsed=round(time.time() - t0, 2))
        f.write(json.dumps(rec) + "\n")
        f.flush()
        n += 1
        time.sleep(max(0, INTERVAL - (time.time() - t0)))
print(f"polls={n} wall={time.time()-start:.0f}s")
