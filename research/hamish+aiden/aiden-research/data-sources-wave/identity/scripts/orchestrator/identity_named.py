import json,os,sys,time,urllib.parse,urllib.request
T=[l.split('=',1)[1].strip() for l in open(os.path.expanduser('~/.config/hedged-bets/wave.env')) if l.startswith('GFW_API_TOKEN=')][0]
H={'Authorization':'Bearer '+T,'User-Agent':'hacktheburgh-feasibility/1.0'}
with open(sys.argv[1],'w') as f:
    for imo in '9177686 9213301 9292993 9233313 9259173 9231468 9238868'.split():
        q={'where':f"imo='{imo}'",'datasets[0]':'public-global-vessel-identity:latest','limit':25,'includes[0]':'OWNERSHIP'}
        d=json.load(urllib.request.urlopen(urllib.request.Request('https://gateway.api.globalfishingwatch.org/v3/vessels/search?'+urllib.parse.urlencode(q),headers=H),timeout=60))
        e=[{k:x.get(k) for k in('selfReportedInfo','registryInfo','registryOwners')} for x in d.get('entries',[])]
        f.write(json.dumps({'imo':imo,'total':d.get('total'),'entries':e})+'\n');print(imo,d.get('total'),[(c.get('shipname'),c.get('flag'),(c.get('transmissionDateTo') or '')[:10]) for x in e for c in (x['selfReportedInfo'] or [])][:6]);time.sleep(.4)
