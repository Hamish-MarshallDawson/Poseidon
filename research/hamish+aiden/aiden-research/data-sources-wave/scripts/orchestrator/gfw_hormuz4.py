import json,os,urllib.request,urllib.parse,urllib.error,collections,random
T=[l.split('=',1)[1].strip() for l in open(os.path.expanduser('~/.config/hedged-bets/wave.env')) if l.startswith('GFW_API_TOKEN=')][0]
H={'Authorization':'Bearer '+T,'Content-Type':'application/json','User-Agent':'hacktheburgh-feasibility/1.0'}
B='https://gateway.api.globalfishingwatch.org/v3'
def poly(b): return {'type':'Polygon','coordinates':[[[b[0],b[1]],[b[2],b[1]],[b[2],b[3]],[b[0],b[3]],[b[0],b[1]]]]}
def rep(ds,s,e,b,res='LOW',temp='ENTIRE',agg='true',group='VESSEL_ID'):
    q={'spatial-resolution':res,'temporal-resolution':temp,'datasets[0]':ds,'date-range':f'{s},{e}','format':'JSON','spatial-aggregation':agg}
    if group:q['group-by']=group
    try:d=json.load(urllib.request.urlopen(urllib.request.Request(B+'/4wings/report?'+urllib.parse.urlencode(q),json.dumps({'geojson':poly(b)}).encode(),H),timeout=170))
    except urllib.error.HTTPError as x:return {'ERR':x.code,'body':x.read()[:160].decode('utf8','replace')}
    return [x for en in d.get('entries',[]) for v in en.values() for x in (v or [])]
P='public-global-presence:latest';S='public-global-sar-presence:latest';random.seed(7)
for n,b in {'Hormuz':(55,25.5,57.5,27),'Malacca control':(98,2,104,6),'Danish control':(9.5,54,14,58)}.items():
    r={}
    for x in rep(P,'2026-02-01','2026-02-28',b): r.setdefault(x.get('vesselId'),x)
    g=[x for x in r.values() if x.get('geartype')=='TANKER' and x.get('imo') and (x.get('lastTransmissionDate') or '9')[:7]<='2026-08']
    samp=random.sample(g,min(40,len(g)));back=0;newname=0;newflag=0;active=0;ex=[]
    for x in samp:
        d=json.load(urllib.request.urlopen(urllib.request.Request(B+'/vessels/search?'+urllib.parse.urlencode({'where':f"imo='{x['imo']}'",'datasets[0]':'public-global-vessel-identity:latest','limit':20}),headers=H),timeout=60))
        ids=[]
        for en in d.get('entries',[]):
            for c in en.get('selfReportedInfo',[]):
                if str(c.get('imo'))==str(x['imo']): ids.append(c)
        last=(x.get('lastTransmissionDate') or '')[:10]
        later=sorted([c for c in ids if (c.get('transmissionDateTo') or '')[:10]>last and c.get('ssvid')!=x.get('mmsi')],key=lambda c:c.get('transmissionDateTo'))
        if later:
            c=later[-1];back+=1;active+= (c.get('transmissionDateTo') or '')[:7]>='2026-10';nn=str(c.get('shipname') or '').strip().upper()!=str(x.get('shipName') or '').strip().upper();newname+=nn;newflag+=c.get('flag')!=x.get('flag')
            if nn and len(ex)<4: ex.append((x['imo'],x.get('shipName'),x.get('flag'),last,'->',c.get('shipname'),c.get('flag'),(c.get('transmissionDateFrom') or '')[:10]))
    print(n,'| silent tankers with IMO',len(g),'| sampled',len(samp),'| same IMO later under another MMSI',back,'| active since Oct',active,'| new name',newname,'| new flag',newflag);[print('   ',e) for e in ex]
print('--- per-vessel hourly positions')
x=rep(P,'2026-10-10','2026-10-11',(56,26,56.6,26.6),res='HIGH',temp='HOURLY',agg='false',group='VESSEL_ID');print(x if isinstance(x,dict) else ('rows',len(x),x[:1]))
x=rep(P,'2026-10-10','2026-10-11',(56,26,56.6,26.6),res='HIGH',temp='DAILY',agg='false',group='VESSEL_ID');print('daily',x if isinstance(x,dict) else ('rows',len(x),x[:1]))
x=rep(S,'2026-10-01','2026-10-31',(55,25.5,57.5,27),res='HIGH',temp='DAILY',agg='false',group=None);print('radar cell anonymous',x if isinstance(x,dict) else ('rows',len(x),x[:2]))
