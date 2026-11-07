import json,os,urllib.request,urllib.parse,urllib.error,collections
T=[l.split('=',1)[1].strip() for l in open(os.path.expanduser('~/.config/hedged-bets/wave.env')) if l.startswith('GFW_API_TOKEN=')][0]
H={'Authorization':'Bearer '+T,'Content-Type':'application/json','User-Agent':'hacktheburgh-feasibility/1.0'}
B='https://gateway.api.globalfishingwatch.org/v3'
def poly(b): return {'type':'Polygon','coordinates':[[[b[0],b[1]],[b[2],b[1]],[b[2],b[3]],[b[0],b[3]],[b[0],b[1]]]]}
def rep(ds,s,e,b,res='LOW',temp='ENTIRE',agg='true',group='VESSEL_ID',extra=None):
    q={'spatial-resolution':res,'temporal-resolution':temp,'datasets[0]':ds,'date-range':f'{s},{e}','format':'JSON','spatial-aggregation':agg}
    if group:q['group-by']=group
    q.update(extra or {})
    try:d=json.load(urllib.request.urlopen(urllib.request.Request(B+'/4wings/report?'+urllib.parse.urlencode(q),json.dumps({'geojson':poly(b)}).encode(),H),timeout=170))
    except urllib.error.HTTPError as x:return {'ERR':x.code,'body':x.read()[:220].decode('utf8','replace')}
    return [x for en in d.get('entries',[]) for v in en.values() for x in (v or [])]
P='public-global-presence:latest';S='public-global-sar-presence:latest'
for n,b in {'Hormuz':(55,25.5,57.5,27),'Malacca control':(98,2,104,6),'Danish control':(9.5,54,14,58)}.items():
    for lab,(s,e,cut) in {'seen Feb 26, silent since Aug':('2026-02-01','2026-02-28','2026-08'),'pre-war control: seen Feb 25, silent 6 months later':('2025-02-01','2025-02-28','2025-08')}.items():
        r={}
        for x in rep(P,s,e,b): r.setdefault(x.get('vesselId'),x)
        big=[x for x in r.values() if x.get('geartype') in('CARGO','TANKER')]
        g=[x for x in big if (x.get('lastTransmissionDate') or '9')[:7]<=cut];t=[x for x in big if x.get('geartype')=='TANKER'];gt=[x for x in g if x.get('geartype')=='TANKER']
        print(n,'|',lab,'| big',len(big),'silent',len(g),f'{100*len(g)/max(len(big),1):.0f}%','| tankers',len(t),'silent',len(gt),f'{100*len(gt)/max(len(t),1):.0f}%')
feb={}
for x in rep(P,'2026-02-01','2026-02-28',(55,25.5,57.5,27)): feb.setdefault(x.get('vesselId'),x)
gone=[x for x in feb.values() if x.get('geartype')=='TANKER' and (x.get('lastTransmissionDate') or '9')[:7]<='2026-08' and x.get('imo')]
print('silent Feb tankers with IMO',len(gone))
back=0;ex=[]
for x in gone[:40]:
    try:d=json.load(urllib.request.urlopen(urllib.request.Request(B+'/vessels/search?'+urllib.parse.urlencode({'query':x['imo'],'datasets[0]':'public-global-vessel-identity:latest','limit':10}),headers=H),timeout=60))
    except Exception as ex2: print('search err',str(ex2)[:80]);break
    ids=[]
    for en in d.get('entries',[]):
        for c in en.get('selfReportedInfo',[]): ids.append((c.get('id'),c.get('ssvid'),c.get('shipname'),c.get('flag'),(c.get('transmissionDateTo') or '')[:10]))
    later=[i for i in ids if i[4]>(x.get('lastTransmissionDate') or '')[:10] and i[0]!=x.get('vesselId')]
    if later: back+=1; ex.append(((x.get('mmsi'),x.get('shipName'),x.get('flag'),(x.get('lastTransmissionDate') or '')[:10]),later[0][1:]))
print('of first',min(40,len(gone)),'silent tankers, IMO later seen under another identity:',back);[print('  ',e) for e in ex[:5]]
print('--- radar detections matched to named vessels, Hormuz Oct')
a=rep(S,'2026-10-01','2026-10-31',(55,25.5,57.5,27),res='HIGH',temp='DAILY',agg='false')
print(a if isinstance(a,dict) else ('rows',len(a),'with mmsi',sum(bool(x.get('mmsi')) for x in a),[ {k:x.get(k) for k in('date','lat','lon','detections','mmsi','shipName')} for x in a if x.get('mmsi')][:4]))
c=collections.Counter(x.get('vesselId') for x in a if x.get('vesselId')) if not isinstance(a,dict) else {}
print('distinct matched vessels',len(c),'seen on 3+ radar days',sum(v>=3 for v in c.values()))
print('--- track retries')
vid=next(iter(feb.values())).get('vesselId')
for t,r in (('DAILY','LOW'),('DAILY','HIGH')):
    x=rep(P,'2026-10-01','2026-10-20',(40,10,70,32),res=r,temp=t,agg='false',group=None,extra={'filters[0]':f"vessel_id='{vid}'"});print(t,r,x if isinstance(x,dict) else ('points',len(x),x[:2]))
x=rep(P,'2026-10-01','2026-10-02',(56,26,56.5,26.5),res='HIGH',temp='HOURLY',agg='false',group=None);print('hourly no filter',x if isinstance(x,dict) else ('points',len(x),x[:1]))
