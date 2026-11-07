"""Impossible-speed jump census on the Digitraffic MQTT collection."""
import json, math, collections, datetime as dt, sys
D=sys.argv[1]
ts=lambda x: dt.datetime.fromtimestamp(x,dt.timezone.utc).strftime('%H:%M:%SZ')
def hav(a,b,c,d):
    R=6371000.0; p1,p2=math.radians(a),math.radians(c); dp,dl=p2-p1,math.radians(d-b)
    x=math.sin(dp/2)**2+math.cos(p1)*math.cos(p2)*math.sin(dl/2)**2
    return 2*R*math.asin(math.sqrt(x))
fix=[]; meta={}
for line in open(D):
    r=json.loads(line)
    if r['topic'].endswith('/location'):
        p=json.loads(r['payload']); m=int(r['topic'].split('/')[1])
        if p.get('lat') is not None and isinstance(p.get('time'),(int,float)):
            fix.append((m,p['time'],p['lat'],p['lon'],p.get('sog')))
    elif r['topic'].endswith('/metadata'):
        meta[int(r['topic'].split('/')[1])]=json.loads(r['payload'])
byv=collections.defaultdict(list)
for f in fix: byv[f[0]].append(f)
jumps=[]
for m,xs in byv.items():
    xs.sort(key=lambda x:x[1])
    prev=None
    for x in xs:
        if prev and x[1]-prev[1]>=2:
            d=hav(prev[2],prev[3],x[2],x[3]); kn=d/(x[1]-prev[1])/0.514444
            if kn>50: jumps.append((m,prev,x,kn,d))
        prev=x
vessels={j[0] for j in jumps}
print(f"impossible jumps (>50 kn implied between consecutive fixes >=2 s apart): {len(jumps)} events, {len(vessels)} vessels, of {len(byv)}")
print("  by vessel:")
for m in sorted(vessels, key=lambda m:-sum(1 for j in jumps if j[0]==m)):
    js=[j for j in jumps if j[0]==m]; xs=byv[m]
    inland=sum(1 for x in xs if x[3]>30)
    print(f"   {m} {str(meta.get(m,{}).get('name'))[:16]:16s} type={meta.get(m,{}).get('type')} jumps={len(js):3d} "
          f"max {max(j[3] for j in js):5.0f} kn, longest {max(j[3] for j in js)*0+max(j[4] for j in js)/1000:6.1f} km, "
          f"pre-jump pos {js[0][1][2]:.2f}N {js[0][1][3]:.2f}E -> {js[0][2][2]:.2f}N {js[0][2][3]:.2f}E at {ts(js[0][2][1])}, inland fixes {inland}")
