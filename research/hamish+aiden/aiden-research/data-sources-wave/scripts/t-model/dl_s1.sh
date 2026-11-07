#!/bin/bash
W=/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave
cd $W/data/t-model/s1cache
python3 - <<'PY'
import json, subprocess, os
p=json.load(open("/tmp/s1picks.json"))
procs=[]
for k,v in p.items():
    for b in ("vv","vh"):
        url="https://sentinel-s1-l1c.s3.amazonaws.com/"+v[b][len("s3://sentinel-s1-l1c/"):]
        out=f"{k}_{b}.tiff"
        procs.append((k,b,out,subprocess.Popen(["/usr/bin/curl","-sS","--max-time","1200","-o",out,url])))
for k,b,out,pr in procs:
    rc=pr.wait()
    print(k,b,"rc=",rc,"size=",os.path.getsize(out) if os.path.exists(out) else None, flush=True)
PY
echo DONE
