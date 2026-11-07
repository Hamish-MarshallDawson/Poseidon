import json,os,urllib.request,urllib.parse,collections
T=[l.split('=',1)[1].strip() for l in open(os.path.expanduser('~/.config/hedged-bets/wave.env')) if l.startswith('GFW_API_TOKEN=')][0]
def go(q,b):
    r=urllib.request.Request('https://gateway.api.globalfishingwatch.org/v3/4wings/report?'+urllib.parse.urlencode(q),json.dumps({'geojson':{'type':'Polygon','coordinates':[[[b[0],b[1]],[b[2],b[1]],[b[2],b[3]],[b[0],b[3]],[b[0],b[1]]]]}}).encode(),{'Authorization':'Bearer '+T,'Content-Type':'application/json','User-Agent':'hacktheburgh-feasibility/1.0'})
    return json.load(urllib.request.urlopen(r,timeout=170))
for name,b in {'Hormuz strait box':(55,25.5,57.5,27),'Natuna':(105,2,110,6)}.items():
    d=go({'spatial-resolution':'LOW','temporal-resolution':'ENTIRE','group-by':'VESSEL_ID','datasets[0]':'public-global-presence:latest','date-range':'2026-10-08,2026-11-04','format':'JSON','spatial-aggregation':'true'},b)
    rows=[x for e in d['entries'] for v in e.values() for x in (v or [])]
    seen={};ty=collections.Counter();hrs=collections.Counter();fl=collections.Counter()
    for x in rows:
        k=x.get('vesselId') or x.get('mmsi')
        if k in seen: continue
        seen[k]=1;t=x.get('vesselType') or '?';g=x.get('geartype') or '?';ty[t]+=1;fl[x.get('flag') or '?']+=1
    for x in rows: hrs[x.get('vesselType') or '?']+=x.get('hours',0) or 0
    print(name,'vessels',len(seen),'types',ty.most_common(8),'hours',[(k,round(v)) for k,v in hrs.most_common(6)],'flags',fl.most_common(8),'last transmit in 3d of end',sum(1 for x in rows if (x.get('lastTransmissionDate') or '')>='2026-11-04'))
