import json,sys
from datetime import datetime,timedelta
from collections import defaultdict,Counter
p=sys.argv[1]
def dt(s): return datetime.fromisoformat(s.replace('Z','+00:00')) if s else None
ships=[json.loads(l) for l in open(p) if l.strip()]
grp=defaultdict(lambda: Counter()); overlaps=[]; mmsi_imo=defaultdict(set)
for s in ships:
    pers=[]
    for ent in s['entries']:
        for e in ent.get('selfReportedInfo') or []: pers.append(e)
    seen=set(); uniq=[]
    for e in pers:
        k=(e.get('ssvid'),e.get('shipname'),e.get('flag'),e.get('transmissionDateFrom'),e.get('transmissionDateTo'))
        if k in seen: continue
        seen.add(k); uniq.append(e)
    uniq.sort(key=lambda e: e.get('transmissionDateFrom') or '')
    g=s['group']; grp[g]['ships']+=1; grp[g]['periods']+=len(uniq)
    if len(uniq)>1: grp[g]['multi']+=1
    flags=[]; starts=[(dt(e.get('transmissionDateFrom')),e) for e in uniq if dt(e.get('transmissionDateFrom'))]
    hop=False
    for i,(t,e) in enumerate(starts):
        win={starts[j][1].get('flag') for j in range(i,len(starts)) if starts[j][0]-t<=timedelta(days=365)}
        if len(win)>=3: hop=True
    if hop: grp[g]['hop3_365']+=1; grp[g].setdefault('hop_imos',[]).append(s['imo'])
    if len(uniq)>=3: grp[g]['ge3_periods']+=1
    for a,b in zip(uniq,uniq[1:]):
        ta=dt(b.get('transmissionDateFrom')); tb=dt(a.get('transmissionDateTo'))
        if ta and tb:
            gap=(ta-tb).total_seconds()/86400
            if gap<0: overlaps.append((s['imo'],g,round(-gap,1),a.get('ssvid'),b.get('ssvid'),a.get('flag'),b.get('flag'),a.get('shipname'),b.get('shipname')))
for k,v in grp.items():
    print(k, {kk:vv for kk,vv in v.items() if kk!='hop_ships'}, 'hop_imos', v.get('hop_imos'))
print('\noverlaps n',len(overlaps),'<30d',sum(1 for o in overlaps if o[2]<30),'>=30d',sum(1 for o in overlaps if o[2]>=30),'>=365d',sum(1 for o in overlaps if o[2]>=365))
print('largest', sorted(overlaps,key=lambda x:-x[2])[:5])
