import json,urllib.parse,urllib.request,time,sys,os
BASE="https://sentinel1euwest.blob.core.windows.net/s1-grd/GRD/2026/11/1/IW/DV/S1C_IW_GRDH_1SDV_20261101T053151_20261101T053216_010139_0143CB_2CB4/measurement/"
def sign(path):
    cache=os.path.join(os.path.dirname(__file__),"signed.json")
    d=json.load(open(cache)) if os.path.exists(cache) else {}
    exp=d.get("expiry","")
    if path in d and exp>time.strftime("%Y-%m-%dT%H:%M:%SZ",time.gmtime(time.time()+120)):
        return d[path]
    for attempt in range(6):
        try:
            u="https://planetarycomputer.microsoft.com/api/sas/v1/sign?href="+urllib.parse.quote(BASE+path,safe='')
            r=json.load(urllib.request.urlopen(u,timeout=60))
            d={path:r["href"],"expiry":r["msft:expiry"]}
            json.dump(d,open(cache,"w"))
            return r["href"]
        except Exception as e:
            print("retry",attempt,type(e).__name__,e,file=sys.stderr); time.sleep(10+10*attempt)
    raise SystemExit("signing failed")
if __name__=="__main__":
    print(sign(sys.argv[1]))
