import json,os,urllib.request,urllib.parse,collections
T=[l.split('=',1)[1].strip() for l in open(os.path.expanduser('~/.config/hedged-bets/wave.env')) if l.startswith('GFW_API_TOKEN=')][0]
H={'Authorization':'Bearer '+T,'Content-Type':'application/json','User-Agent':'hacktheburgh-feasibility/1.0'}
b=(55,25.5,57.5,27)
q={'spatial-resolution':'LOW','temporal-resolution':'ENTIRE','group-by':'VESSEL_ID','datasets[0]':'public-global-presence:latest','date-range':'2026-10-08,2026-11-04','format':'JSON','spatial-aggregation':'true'}
geo={'type':'Polygon','coordinates':[[[b[0],b[1]],[b[2],b[1]],[b[2],b[3]],[b[0],b[3]],[b[0],b[1]]]]}
d=json.load(urllib.request.urlopen(urllib.request.Request('https://gateway.api.globalfishingwatch.org/v3/4wings/report?'+urllib.parse.urlencode(q),json.dumps({'geojson':geo}).encode(),H),timeout=170))
rows={}
for e in d['entries']:
    for v in e.values():
        for x in (v or []):
            k=x.get('vesselId') or x.get('mmsi'); rows.setdefault(k,dict(x,hours=0)); rows[k]['hours']+=x.get('hours',0) or 0
R=list(rows.values());n=len(R)
print('vessels',n,'with MMSI',sum(bool(x.get('mmsi')) for x in R),'IMO',sum(bool(x.get('imo')) for x in R),'name',sum(bool(x.get('shipName')) for x in R),'callsign',sum(bool(x.get('callsign')) for x in R),'flag',sum(bool(x.get('flag')) for x in R))
print('distinct mmsi',len({x.get('mmsi') for x in R if x.get('mmsi')}),'distinct vesselId',len({x.get('vesselId') for x in R}))
print('flags',collections.Counter(x.get('flag') or '?' for x in R).most_common(10))
big=[x for x in R if x.get('vesselType') in('CARGO','BUNKER','CARRIER')]
print('cargo-like',len(big),'IMO',sum(bool(x.get('imo')) for x in big),'flags',collections.Counter(x.get('flag') or '?' for x in big).most_common(8))
hrs=collections.Counter()
for x in R: hrs[x.get('flag') or '?']+=x['hours']
tot=sum(hrs.values());print('share of hours',[(k,round(100*v/tot)) for k,v in hrs.most_common(6)])
s=sorted([x for x in big if x.get('imo')],key=lambda x:-x['hours'])[:5]
for x in s:
    q2={'datasets[0]':'public-global-port-visits-events:latest','vessels[0]':x['vesselId'],'start-date':'2026-07-01','end-date':'2026-11-05','limit':3,'offset':0}
    try:
        e=json.load(urllib.request.urlopen(urllib.request.Request('https://gateway.api.globalfishingwatch.org/v3/events?'+urllib.parse.urlencode(q2),headers=H),timeout=60))
        pv=[(p.get('start','')[:10],(p.get('port_visit',{}).get('startAnchorage',{}) or {}).get('name'),(p.get('port_visit',{}).get('startAnchorage',{}) or {}).get('flag')) for p in e.get('entries',[])]
        print('type',x.get('vesselType'),'flag',x.get('flag'),'hours',round(x['hours']),'port visits total',e.get('total'),pv)
    except urllib.error.HTTPError as ex: print('portvisit err',ex.code,ex.read()[:150])
