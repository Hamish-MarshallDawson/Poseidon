import json,os,urllib.request,urllib.parse,urllib.error,collections,sys
T=[l.split('=',1)[1].strip() for l in open(os.path.expanduser('~/.config/hedged-bets/wave.env')) if l.startswith('GFW_API_TOKEN=')][0]
def poly(b): a,c,d,e=b; return {'type':'Polygon','coordinates':[[[a,c],[d,c],[d,e],[a,e],[a,c]]]}
def go(ds,b,s,e,res='LOW',temp='DAILY',extra=None,agg='true'):
    q={'spatial-resolution':res,'temporal-resolution':temp,'datasets[0]':ds,'date-range':f'{s},{e}','format':'JSON','spatial-aggregation':agg}; q.update(extra or {})
    r=urllib.request.Request('https://gateway.api.globalfishingwatch.org/v3/4wings/report?'+urllib.parse.urlencode(q),json.dumps({'geojson':poly(b)}).encode(),{'Authorization':'Bearer '+T,'Content-Type':'application/json','User-Agent':'hacktheburgh-feasibility/1.0'})
    try: d=json.load(urllib.request.urlopen(r,timeout=170))
    except urllib.error.HTTPError as x: return ('ERR',x.code,x.read()[:200])
    return [x for en in d.get('entries',[]) for v in en.values() for x in (v or [])]
S='public-global-sar-presence:latest';P='public-global-presence:latest'
PER={'Feb26 (pre-closure)':('2026-02-01','2026-02-28'),'Apr26':('2026-04-01','2026-04-30'),'Oct26':('2026-10-01','2026-10-31')}
REG={'Hormuz':(55,25.5,57.5,27),'Gulf of Oman':(57.5,22,62,26),'Danish straits (control)':(9.5,54,14,58),'Malacca (control)':(98,2,104,6)}
print('region|period|radar days|radar/day|no-AIS radar/day|no-AIS %|AIS avg ships|AIS moving? n/a')
for n,b in REG.items():
  for pn,(s,e) in PER.items():
    a=go(S,b,s,e);u=go(S,b,s,e,extra={'filters[0]':"matched='false'"});p=go(P,b,s,e)
    if isinstance(a,tuple) or isinstance(u,tuple) or isinstance(p,tuple): print(n,pn,a if isinstance(a,tuple) else '',u if isinstance(u,tuple) else '',p if isinstance(p,tuple) else '');continue
    da=len({x['date'] for x in a});ta=sum(x.get('detections',0) or 0 for x in a);tu=sum(x.get('detections',0) or 0 for x in u);hp=sum(x.get('hours',0) or 0 for x in p);dp=len({x['date'] for x in p})
    print(n,'|',pn,'|',da,'|',round(ta/max(da,1),1),'|',round(tu/max(da,1),1),'|',round(100*tu/max(ta,1)),'% |',round(hp/max(dp,1)/24))
print('--- radar-only target check, 2026-11-01, 12.6444E 56.4543N')
for lab,bb in {'±0.02deg':(12.6244,56.4343,12.6644,56.4743),'±0.1deg':(12.5444,56.3543,12.7444,56.5543),'aoi3':(12.6,56.3,13.2,56.7)}.items():
    a=go(S,bb,'2026-11-01','2026-11-02',res='HIGH',agg='false');print(lab,len(a) if not isinstance(a,tuple) else a)
    if not isinstance(a,tuple):
        for x in a[:12]: print('  ',{k:x.get(k) for k in ('date','lat','lon','detections','mmsi','shipName','vesselType')})
