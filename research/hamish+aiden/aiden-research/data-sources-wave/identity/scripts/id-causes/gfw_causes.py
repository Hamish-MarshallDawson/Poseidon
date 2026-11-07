import json, sys
from datetime import datetime, timedelta
from collections import Counter, defaultdict
p = sys.argv[1]
def dt(s):
    return datetime.fromisoformat(s.replace('Z','+00:00')) if s else None
ships=[json.loads(l) for l in open(p) if l.strip()]
bygrp=defaultdict(lambda: dict(ships=0, periods=0, multi=0, trans=0))
rows=[]; rapid=[]; flags_same=[]
for s in ships:
    pers=[]
    for ent in s['entries']:
        for e in ent.get('selfReportedInfo') or []:
            pers.append(e)
    seen=set(); uniq=[]
    for e in pers:
        k=(e.get('ssvid'), e.get('shipname'), e.get('flag'), e.get('transmissionDateFrom'), e.get('transmissionDateTo'))
        if k in seen: continue
        seen.add(k); uniq.append(e)
    uniq.sort(key=lambda e: e.get('transmissionDateFrom') or '')
    g=bygrp[s['group']]; g['ships']+=1; g['periods']+=len(uniq)
    if len(uniq)>1: g['multi']+=1
    fl=[e.get('flag') for e in uniq]
    nm=[e.get('shipname') for e in uniq]
    # rapid flag hopping: >=3 distinct flags inside any 365-day span covering period starts
    starts=[(dt(e.get('transmissionDateFrom')), e.get('flag'), e.get('ssvid'), e.get('shipname'), e.get('callsign')) for e in uniq if dt(e.get('transmissionDateFrom'))]
    n=0
    for i,(t,f,mm,na,cs) in enumerate(starts):
        win={starts[j][1] for j in range(i,len(starts)) if starts[j][0]-t <= timedelta(days=365)}
        if len(win)>=3: n+=1
    if n: rapid.append((s['imo'], s['group'], n, len(uniq), [(str(e.get('transmissionDateFrom'))[:10], e.get('flag'), e.get('ssvid'), e.get('shipname')) for e in uniq]))
    for a,b in zip(uniq, uniq[1:]):
        g['trans']+=1
        ta=dt(b.get('transmissionDateFrom')); tb=dt(a.get('transmissionDateTo'))
        gap=(ta-tb).total_seconds()/86400 if ta and tb else None
        rec=dict(imo=s['imo'],grp=s['group'],fc=a.get('flag')!=b.get('flag'),mc=a.get('ssvid')!=b.get('ssvid'),nc=(a.get('shipname')!=b.get('shipname')),gap=gap,
                 a=(a.get('flag'),a.get('ssvid'),a.get('shipname'),str(a.get('transmissionDateFrom'))[:10],str(a.get('transmissionDateTo'))[:10]),
                 b=(b.get('flag'),b.get('ssvid'),b.get('shipname'),str(b.get('transmissionDateFrom'))[:10],str(b.get('transmissionDateTo'))[:10]))
        rows.append(rec)
        if rec['mc'] and not rec['fc']: flags_same.append(rec)
print('ships',len(ships),'periods',sum(len(s['entries']) for s in ships))
for k,v in bygrp.items(): print(k, v)
print('total transitions',len(rows))
print('flag_changed',sum(r['fc'] for r in rows),'mmsi_changed',sum(r['mc'] for r in rows),'name_changed',sum(r['nc'] for r in rows))
print('fc & mc', sum(1 for r in rows if r['fc'] and r['mc']), 'fc & !mc', sum(1 for r in rows if r['fc'] and not r['mc']))
print('mmsi same, name changed', sum(1 for r in rows if not r['mc'] and r['nc']))
buckets=Counter()
for r in rows:
    g=r['gap']
    if g is None: buckets['unknown']+=1
    elif g<0: buckets['overlap (<0)']+=1
    elif g<=1: buckets['0-1 day']+=1
    elif g<=30: buckets['1-30 days']+=1
    elif g<=365: buckets['30-365 days']+=1
    else: buckets['>365 days']+=1
print('gap buckets', dict(buckets))
print('gap<=1d pct', round(100*sum(1 for r in rows if r['gap'] is not None and 0<=r['gap']<=1)/len(rows),1))
print('\nSAME-FLAG MMSI CHANGES (n=%d)'%len(flags_same))
for r in flags_same[:15]: print(' ',r['imo'],r['grp'],r['a'],'->',r['b'],'gap',None if r['gap'] is None else round(r['gap'],1))
print('\nSAME-MMSI RENAMES (mmsi same, name changed)')
for r in [x for x in rows if not x['mc'] and x['nc']][:10]: print(' ',r['imo'],r['a'],'->',r['b'])
print('\nRAPID FLAG HOPPING >=3 flags in 365d (n=%d)'%len(rapid))
for r in rapid: print(' ',r[0],r[1],'windows',r[2],'periods',r[3],r[4])
