import json,sys
from datetime import datetime,timedelta
from collections import defaultdict,Counter
p=sys.argv[1]
def dt(s): return datetime.fromisoformat(s.replace('Z','+00:00')) if s else None
ships=[json.loads(l) for l in open(p) if l.strip()]
grp=defaultdict(Counter); rows=[]; sameflag=[]; nameonly=[]; rapid=defaultdict(list)
for s in ships:
    pers=[]
    for ent in s['entries']:
        for e in ent.get('selfReportedInfo') or []: pers.append(e)
    seen=set(); uniq=[]
    for e in pers:
        k=(e.get('ssvid'),(e.get('shipname') or '').strip(),e.get('flag'),(e.get('callsign') or '').strip())
        if k in seen: continue
        seen.add(k); uniq.append(e)
    uniq.sort(key=lambda e: e.get('transmissionDateFrom') or '')
    g=s['group']; grp[g]['ships']+=1; grp[g]['periods']+=len(uniq)
    if len(uniq)>1: grp[g]['multi']+=1
    starts=[(dt(e.get('transmissionDateFrom')),e) for e in uniq if dt(e.get('transmissionDateFrom'))]
    hop=False
    for i,(t,e) in enumerate(starts):
        if len({starts[j][1].get('flag') for j in range(i,len(starts)) if starts[j][0]-t<=timedelta(days=365)})>=3: hop=True
    if hop: grp[g]['hop3_365']+=1; rapid[g].append(s['imo'])
    for a,b in zip(uniq,uniq[1:]):
        grp[g]['trans']+=1
        ta=dt(b.get('transmissionDateFrom')); tb=dt(a.get('transmissionDateTo'))
        gap=(ta-tb).total_seconds()/86400 if ta and tb else None
        r=dict(imo=s['imo'],grp=g,fc=a.get('flag')!=b.get('flag'),mc=a.get('ssvid')!=b.get('ssvid'),
               nc=(a.get('shipname') or '').strip()!=(b.get('shipname') or '').strip(),gap=gap,
               a=(a.get('flag'),a.get('ssvid'),a.get('shipname'),str(a.get('transmissionDateFrom'))[:10]),
               b=(b.get('flag'),b.get('ssvid'),b.get('shipname'),str(b.get('transmissionDateFrom'))[:10]))
        rows.append(r)
        if r['mc'] and not r['fc']: sameflag.append(r)
        if not r['mc'] and not r['fc'] and r['nc']: nameonly.append(r)
print('ships',len(ships),'periods',sum(len(s['entries']) for s in ships))
for k,v in grp.items(): print(k, dict(v), 'rapid', rapid.get(k))
print('transitions',len(rows),'flag_changed',sum(r['fc'] for r in rows),'mmsi_changed',sum(r['mc'] for r in rows),'name_changed',sum(r['nc'] for r in rows))
print('fc&mc',sum(1 for r in rows if r['fc'] and r['mc']),'fc&!mc',sum(1 for r in rows if r['fc'] and not r['mc']),'nameonly',len(nameonly))
b=Counter()
for r in rows:
    g=r['gap']
    b['unknown' if g is None else 'overlap' if g<0 else '0-1d' if g<=1 else '1-30d' if g<=30 else '30-365d' if g<=365 else '>365d']+=1
print('buckets',dict(b))
print('time_shifted', round(100*len({(r['grp']) for r in rows})/1,1))
print('sameflag n',len(sameflag)); [print(' ',r['imo'],r['a'],'->',r['b']) for r in sameflag[:8]]
print('nameonly'); [print(' ',r['imo'],r['a'],'->',r['b']) for r in nameonly]
d=Counter()
for s in ships:
    fl={(e.get('flag') or '') for ent in s['entries'] for e in ent.get('selfReportedInfo') or []}
    d[min(len(fl),6)]+=1
print('flags per imo capped',dict(sorted(d.items())))
