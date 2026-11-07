import json,re,sys,collections,statistics as st
from datetime import datetime as D
P=lambda s:D.fromisoformat(s.replace('Z','+00:00')) if s else None
N=lambda s:re.sub(r'[^A-Z0-9]','',(s or '').upper())
rows=[json.loads(l) for l in open(sys.argv[1])]
print('records',len(rows),'errors',sum('error' in r for r in rows),'empty',sum(not r.get('entries') for r in rows if 'error' not in r))
print('groups',collections.Counter((r['group'],r['region']) for r in rows))
def periods(r):
    ps=[]
    for e in r.get('entries') or []:
        for c in e.get('selfReportedInfo') or []:
            if str(c.get('imo'))==str(r['imo']) and c.get('transmissionDateFrom') and c.get('transmissionDateTo'):
                ps.append((P(c['transmissionDateFrom']),P(c['transmissionDateTo']),str(c.get('ssvid')),N(c.get('shipname')),c.get('flag')))
    return sorted(ps,key=lambda x:x[0])
W0=P('2025-11-05T00:00:00Z');W1=P('2026-11-05T00:00:00Z')
res=collections.defaultdict(list);gaps=collections.defaultdict(list);flagc=collections.defaultdict(collections.Counter)
for r in rows:
    if 'error' in r: continue
    ps=periods(r)
    if not ps: continue
    act=[p for p in ps if p[1]>=W0 and p[0]<=W1]
    if not act: continue
    res[r['group'],r['region']].append((len({p[2] for p in act})-1,len({p[3] for p in act})-1,len({p[4] for p in act})-1,len(act)))
    for a,b in zip(ps,ps[1:]):
        if a[2]!=b[2] and b[0]>=W0: gaps[r['group']].append((b[0]-a[1]).total_seconds()/3600)
print('\nLast 12 months, ships active: group region | n | ≥1 new MMSI % | ≥1 name % | ≥1 flag % | ≥2 new MMSIs % | avg new MMSI per ship-year')
agg=collections.defaultdict(list)
for k,v in sorted(res.items()):
    n=len(v);f=lambda i,t=1:round(100*sum(x[i]>=t for x in v)/n)
    print(k,n,f(0),f(1),f(2),f(0,2),round(sum(x[0] for x in v)/n,2));agg[k[0]]+=v
print('\nPooled by group')
for k,v in agg.items():
    n=len(v);f=lambda i,t=1:round(100*sum(x[i]>=t for x in v)/n,1)
    print(k,'n',n,'≥1 MMSI',f(0),'≥1 name',f(1),'≥1 flag',f(2),'≥2 MMSI',f(0,2),'≥3 MMSI',f(0,3))
print('\nSwitch timing, consecutive periods with different MMSI starting in last 12 months (hours from end of old to start of new)')
for g,v in gaps.items():
    v=sorted(v);n=len(v);print(g,'n',n,'median',round(st.median(v),1),'overlap <0',round(100*sum(x<0 for x in v)/n),'% | 0-1h',round(100*sum(0<=x<=1 for x in v)/n),'% | 1-24h',round(100*sum(1<x<=24 for x in v)/n),'% | 1-7d',round(100*sum(24<x<=168 for x in v)/n),'% | >7d',round(100*sum(x>168 for x in v)/n),'%')
