import json,os,urllib.request,urllib.parse,urllib.error,collections,datetime as dt
T=[l.split('=',1)[1].strip() for l in open(os.path.expanduser('~/.config/hedged-bets/wave.env')) if l.startswith('GFW_API_TOKEN=')][0]
H={'Authorization':'Bearer '+T,'Content-Type':'application/json','User-Agent':'hacktheburgh-feasibility/1.0'}
B='https://gateway.api.globalfishingwatch.org/v3'
def get(p,q):
    try: return json.load(urllib.request.urlopen(urllib.request.Request(B+p+'?'+urllib.parse.urlencode(q),headers=H),timeout=120))
    except urllib.error.HTTPError as e: return {'ERR':e.code,'body':e.read()[:300].decode('utf8','replace')}
b=(55,25.5,57.5,27);geo={'type':'Polygon','coordinates':[[[b[0],b[1]],[b[2],b[1]],[b[2],b[3]],[b[0],b[3]],[b[0],b[1]]]]}
def rep(s,e,extra=None,res='LOW',temp='ENTIRE',agg='true',group='VESSEL_ID',g=geo):
    q={'spatial-resolution':res,'temporal-resolution':temp,'datasets[0]':'public-global-presence:latest','date-range':f'{s},{e}','format':'JSON','spatial-aggregation':agg}
    if group:q['group-by']=group
    q.update(extra or {})
    r=urllib.request.Request(B+'/4wings/report?'+urllib.parse.urlencode(q),json.dumps({'geojson':g}).encode(),H)
    try:d=json.load(urllib.request.urlopen(r,timeout=170))
    except urllib.error.HTTPError as x:return {'ERR':x.code,'body':x.read()[:300].decode('utf8','replace')}
    return [x for en in d.get('entries',[]) for v in en.values() for x in (v or [])]
feb=rep('2026-02-01','2026-02-28');rows={}
for x in feb: rows.setdefault(x.get('vesselId'),x)
R=list(rows.values());print('Feb vessels',len(R),'types',collections.Counter(x.get('vesselType') for x in R).most_common(5),'geartypes',collections.Counter(x.get('geartype') for x in R).most_common(6))
big=[x for x in R if x.get('vesselType')=='CARGO' or 'TANKER' in str(x.get('geartype'))]
def month(x): return (x.get('lastTransmissionDate') or '')[:7]
print('big ships Feb',len(big),'last transmission month',sorted(collections.Counter(month(x) for x in big).items())[-14:])
gone=[x for x in big if month(x) and month(x)<='2026-08']
print('last AIS by Aug (≥2 months silent as of data end):',len(gone),'of',len(big),'flags',collections.Counter(x.get('flag') for x in gone).most_common(6),'with IMO',sum(bool(x.get('imo')) for x in gone))
oct_=rep('2026-10-01','2026-10-31');oids={x.get('vesselId') for x in oct_}
print('big Feb ships present in the box in Oct',sum(x.get('vesselId') in oids for x in big))
# vessel info
s=sorted(big,key=lambda x:x.get('hours',0),reverse=True)
v=get('/vessels/'+s[0]['vesselId'],{'dataset':'public-global-vessel-identity:latest'})
print('vessel api keys',list(v.keys())[:10],v.get('ERR'),str(v.get('body',''))[:200])
if 'combinedSourcesInfo' in v:
    print(' shiptypes',(v['combinedSourcesInfo'] or [{}])[0].get('shiptypes'),' registryInfo',[{k:r.get(k) for k in ('flag','imo','shipname','tonnageGt','lengthM')} for r in v.get('registryInfo',[])[:1]])
# course test: one vessel, hourly, high res
vid=s[0]['vesselId'];tr=rep('2026-09-20','2026-10-20',extra={'filters[0]':f"vessel_id='{vid}'"},res='HIGH',temp='HOURLY',agg='false',group=None,g={'type':'Polygon','coordinates':[[[40,10],[70,10],[70,32],[40,32],[40,10]]]})
print('track test',tr if isinstance(tr,dict) else ('points',len(tr),[ {k:p.get(k) for k in ('date','lat','lon','hours')} for p in tr[:5]]))
# gap and encounter events for a gone ship
if gone:
    g=sorted(gone,key=lambda x:x.get('lastTransmissionDate'))[len(gone)//2];print('gone example',{k:g.get(k) for k in('flag','vesselType','lastTransmissionDate','firstTransmissionDate')})
    e=get('/events',{'datasets[0]':'public-global-gaps-events:latest','vessels[0]':g['vesselId'],'start-date':'2025-01-01','end-date':'2026-11-05','limit':3,'offset':0});print(' gaps',e.get('total'),e.get('ERR'))
    e=get('/events',{'datasets[0]':'public-global-port-visits-events:latest','vessels[0]':g['vesselId'],'start-date':'2026-01-01','end-date':'2026-11-05','limit':100,'offset':0});print(' port visits',e.get('total'),e.get('ERR'))
