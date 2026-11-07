"""id-frequency final snapshot: chained switches + side identities + registry, one pass."""
import json,collections,statistics,datetime as dt,sys
PATH=sys.argv[1] if len(sys.argv)>1 else '/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave/data/identity/gfw-identities.jsonl'
def ts(s):
    s=s.replace('Z','').replace('+00:00','')
    return dt.datetime.fromisoformat(s[:26] if '.' in s else s[:19]).replace(tzinfo=None)
Y=86400*365.25
recs=[json.loads(l) for l in open(PATH) if 'entries' in l]
ships=[]
for r in recs:
    per={}; reg=[]; own=set()
    for gi,e in enumerate(r['entries']):
        for x in (e.get('selfReportedInfo') or []):
            if not x.get('transmissionDateFrom'): continue
            k=(x.get('ssvid'),x.get('shipname'),x.get('flag'),x.get('callsign'),x.get('nShipname'))
            a=ts(x['transmissionDateFrom']); b=ts(x.get('transmissionDateTo') or x['transmissionDateFrom'])
            per.setdefault(k,{'a':a,'b':b,'g':set()})
            per[k]['a']=min(per[k]['a'],a); per[k]['b']=max(per[k]['b'],b); per[k]['g'].add(gi)
        reg+=e.get('registryInfo') or []
        own|={o.get('name') for o in (e.get('registryOwners') or []) if o.get('name')}
    ps=[dict(ssvid=k[0],name=k[1],flag=k[2],call=k[3],nname=k[4],a=v['a'],b=v['b'],g=v['g']) for k,v in per.items()]
    ps.sort(key=lambda p:(p['a'],p['b']))
    ships.append(dict(imo=r['imo'],group=r['group'],region=r['region'],periods=ps,reg=reg,own=own,
        ngroups=len(r['entries']),start=min(p['a'] for p in ps),end=max(p['b'] for p in ps)))
for s in ships: s['span']=(s['end']-s['start']).total_seconds()/Y
SY=sum(s['span'] for s in ships); SD=SY*365.25; NP=sum(len(s['periods']) for s in ships)
N=len(ships)
print('SAMPLE %d IMOs, %.0f ship-years, %d identity periods, %.0f ship-days'%(N,SY,NP,SD))
print('groups',dict(collections.Counter(s['group'] for s in ships)),'regions',dict(collections.Counter(s['region'] for s in ships)))
print('periods/ship',dict(sorted(collections.Counter(len(s['periods']) for s in ships).items())))
print('median span %.1f y'%statistics.median([s['span'] for s in ships]))
sw=[];side=[]
for s in ships:
    st=[]
    for p in s['periods']:
        act=[q for q in st if q['b']>p['a']]
        if act:
            q=max(act,key=lambda q:q['b']); side.append((p,q,s))
        elif st:
            q=max(st,key=lambda q:q['b']); sw.append(dict(prev=q,new=p,ship=s,gap=(p['a']-q['b']).total_seconds()/3600))
        st.append(p)
def chg(t,f): return t['prev'][f]!=t['new'][f]
print('\nSWITCHES (new identity starts after the previous stopped): %d = %.3f/ship-year'%(len(sw),len(sw)/SY))
g=sorted(t['gap'] for t in sw)
for k in ('<1 h','1-24 h','1-30 d','30-365 d','>365 d'):
    n=sum(1 for x in g if (x<1 if k=='<1 h' else 1<=x<24 if k=='1-24 h' else 24<=x<720 if k=='1-30 d' else 720<=x<8760 if k=='30-365 d' else x>=8760))
    print('   %-9s %4d  %5.1f%%'%(k,n,100*n/len(g)))
print('   <=24h %.1f%%  <=31d %.1f%%  p50 %.2f h  p90 %.1f h'%(100*sum(1 for x in g if x<24)/len(g),100*sum(1 for x in g if x<720)/len(g),statistics.median(g),g[int(.9*len(g))]))
pat=collections.Counter(''.join(c for c,f in (('M',None),('N','name'),('F','flag'),('C','call')) if f is None or chg(t,f)) for t in sw)
print('   patterns',dict(pat.most_common()))
print('   name kept at switch %d/%d = %.0f%%; flag changed %d/%d; same-MID MMSI change %d'%(
 sum(1 for t in sw if not chg(t,'name')),len(sw),100*sum(1 for t in sw if not chg(t,'name'))/len(sw),
 sum(1 for t in sw if chg(t,'flag')),len(sw),sum(1 for t in sw if str(t['prev']['ssvid'])[:3]==str(t['new']['ssvid'])[:3])))
print('\nRATES per ship-year: MMSI %.3f  name %.3f  flag %.3f  callsign %.3f'%(
 len(sw)/SY,sum(1 for t in sw if chg(t,'name'))/SY,sum(1 for t in sw if chg(t,'flag'))/SY,sum(1 for t in sw if chg(t,'call'))/SY))
for grp in ('random_tanker','random_cargo','silent_tanker'):
    rs=[s for s in ships if s['group']==grp]; sy=sum(s['span'] for s in rs)
    t=[x for x in sw if x['ship']['group']==grp]; sd=[x for x in side if x[2]['group']==grp]
    print('  %-14s n=%3d sy=%5.0f  switch %.3f/sy  name %.3f/sy  flag %.3f/sy  periods/ship %.2f  starts-with-side %.1f%%'%(
      grp,len(rs),sy,len(t)/sy,sum(1 for x in t if chg(x,'name'))/sy,sum(1 for x in t if chg(x,'flag'))/sy,
      statistics.mean(len(s['periods']) for s in rs),100*len(sd)/max(1,len(t)+len(sd))))
for reg in sorted({s['region'] for s in ships}):
    rs=[s for s in ships if s['region']==reg]; sy=sum(s['span'] for s in rs)
    t=[x for x in sw if x['ship']['region']==reg]
    print('  %-9s n=%3d sy=%5.0f  switch %.3f/sy'%(reg,len(rs),sy,len(t)/sy))
syy=collections.Counter(); ev=collections.defaultdict(collections.Counter)
for s in ships:
    y=s['start'].year
    while y<=s['end'].year:
        a=max(s['start'],dt.datetime(y,1,1)); z=min(s['end'],dt.datetime(y+1,1,1))
        if z>a: syy[y]+=(z-a).total_seconds()/Y
        y+=1
for t in sw:
    y=t['new']['a'].year; ev[y]['m']+=1; ev[y]['n']+=chg(t,'name'); ev[y]['f']+=chg(t,'flag')
print('\nBY YEAR:')
for y in sorted(syy):
    if syy[y]>=20: print('   %d sy=%5.0f switch %3d (%.2f) name (%.2f) flag (%.2f)'%(y,syy[y],ev[y]['m'],ev[y]['m']/syy[y],ev[y]['n']/syy[y],ev[y]['f']/syy[y]))
print('\nSIDE IDENTITIES (period starts while another MMSI of the same IMO was on air): %d = %.0f%% of periods, on %d/%d ships'%(
 len(side),100*len(side)/NP,len({id(x[2]) for x in side}),N))
d=sorted((x[0]['b']-x[0]['a']).total_seconds()/86400 for x in side)
print('   side duration days p50 %.1f; <1 d %.0f%%; <7 d %.0f%%; <30 d %.0f%%; >1 y %.0f%%; same name as parent %.0f%%; same GFW group %.0f%%'%(
 statistics.median(d),100*sum(1 for x in d if x<1)/len(d),100*sum(1 for x in d if x<7)/len(d),
 100*sum(1 for x in d if x<30)/len(d),100*sum(1 for x in d if x>365)/len(d),
 100*sum(1 for x in side if x[0]['name']==x[1]['name'])/len(side),
 100*sum(1 for x in side if x[0]['g']&x[1]['g'])/len(side)))
print('\nWINDOWS at end of own span (denominator ships with span>=1y):')
elig=[s for s in ships if s['span']>=1]
for days,lab in ((30,'1 month'),(90,'3 months'),(365,'12 months')):
    n=sum(1 for s in elig if any(t['ship'] is s and t['new']['a']>=s['end']-dt.timedelta(days=days) for t in sw+[dict(ship=x[2],new=x[0]) for x in side]))
    print('   %-9s %3d/%3d = %4.1f%%'%(lab,n,len(elig),100*n/len(elig)))
mx=collections.Counter()
for s in ships:
    fs=sorted(p['a'] for p in s['periods'])
    mx[max((sum(1 for g2 in fs if f<=g2<f+dt.timedelta(days=365)) for f in fs),default=0)]+=1
print('   max period starts in any 365 d window:',dict(sorted(mx.items())),
      ' >=3: %d/%d = %.1f%%'%(sum(v for k,v in mx.items() if k>=3),N,100*sum(v for k,v in mx.items() if k>=3)/N))
cnt=sorted(((sum(1 for t in sw if t['ship'] is s)+sum(1 for p,q,s2 in side if s2 is s),s) for s in ships),key=lambda x:-x[0])
print('   ships with zero identity starts: %d/%d = %.0f%%'%(sum(1 for c,_ in cnt if c==0),N,100*sum(1 for c,_ in cnt if c==0)/N))
k=max(1,N//10)
print('   top 10%% (%d ships) hold %d/%d = %.0f%% of all starts'%(k,sum(c for c,_ in cnt[:k]),len(sw)+len(side),100*sum(c for c,_ in cnt[:k])/(len(sw)+len(side))))
print('\nBASE RATE per ship-day: switch %.5f (1,000 ships %.2f/d, 5,000 %.2f/d); name %.5f; flag %.5f'%(
 len(sw)/SD,1000*len(sw)/SD,5000*len(sw)/SD,sum(1 for t in sw if chg(t,'name'))/SD,sum(1 for t in sw if chg(t,'flag'))/SD))
print('\nREGISTRY: no record %d/%d = %.0f%%; records %d for %d AIS periods; sources %s; owners %d ships'%(
 sum(1 for s in ships if not s['reg']),N,100*sum(1 for s in ships if not s['reg'])/N,
 sum(len(s['reg']) for s in ships),NP,dict(collections.Counter(tuple(x.get('sourceCode') or []) for s in ships for x in s['reg'])),sum(1 for s in ships if s['own'])))
print('\nSILENT TANKERS: identity that stopped by 2026-08-01 and another SSVID later: %d/%d'%(
 sum(1 for s in ships if s['group']=='silent_tanker' and any(p['b']<=dt.datetime(2026,8,1) for p in s['periods']) and any(p['b']>dt.datetime(2026,8,1) for p in s['periods'])),
 sum(1 for s in ships if s['group']=='silent_tanker')))
print('\nFLAG DESTINATIONS', collections.Counter(t['new']['flag'] for t in sw if chg(t,'flag')).most_common(10))
