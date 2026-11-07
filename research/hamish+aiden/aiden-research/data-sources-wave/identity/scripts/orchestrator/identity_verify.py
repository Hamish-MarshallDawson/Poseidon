import json,csv,collections,re,sys,os
W=sys.argv[1]
print('--- named IMOs')
for l in open(W+'/data/identity/gfw-named-imos.jsonl'):
    r=json.loads(l);ps=sorted([(c.get('transmissionDateFrom','')[:10],c.get('transmissionDateTo','')[:10],c.get('shipname'),c.get('flag'),c.get('ssvid')) for e in r['entries'] for c in (e.get('selfReportedInfo') or [])])
    print(r['imo'],r['total']);[print('   ',p) for p in ps[-7:]]
print('--- sanctions join, Danish vessels')
os_=W+'/../probes/os.csv'
imo=collections.defaultdict(set);mm=collections.defaultdict(set)
for x in csv.DictReader(open(os_,encoding='utf-8')):
    if x['type']!='VESSEL':continue
    t=set(x['risk'].split(';'))
    m=re.sub(r'\D','',x['imo'] or '')
    if m:imo[m]|=t
    for k in (x['mmsi'] or '').split(';'):
        if k.strip():mm[k.strip()]|=t
print('list IMOs',len(imo),'MMSIs',len(mm))
p=W+'/data/t-ais-history/day_2026-11-01/vessels.csv';rows=list(csv.DictReader(open(p)));print('cols',list(rows[0].keys())[:14],'rows',len(rows))
ck=[c for c in rows[0] if c.lower()=='mmsi'][0];ci=[c for c in rows[0] if c.lower()=='imo'][0];cc=[c for c in rows[0] if 'class' in c.lower() or 'mobile' in c.lower()]
def ok(i):return len(i)==7 and i.isdigit() and sum(int(i[j])*(7-j) for j in range(6))%10==int(i[6])
hasimo=[r for r in rows if ok(re.sub(r'\D','',r[ci] or ''))]
bi=[r for r in hasimo if re.sub(r'\D','',r[ci]) in imo];bm=[r for r in rows if r[ck] in mm]
S={'sanction','mare.shadow'}
bis={r[ck] for r in bi if imo[re.sub(r'\D','',r[ci])]&S};bms={r[ck] for r in bm if mm[r[ck]]&S}
print('rows valid IMO',len(hasimo),'IMO match',len(bi),f'{100*len(bi)/len(hasimo):.1f}%','MMSI match',len(bm),f'{100*len(bm)/len(rows):.1f}%','| union',len({r[ck] for r in bi}|{r[ck] for r in bm}),'IMO-only',len({r[ck] for r in bi}-{r[ck] for r in bm}),'MMSI-only',len({r[ck] for r in bm}-{r[ck] for r in bi}))
print('sanction/shadow tag only: IMO',len(bis),'MMSI',len(bms),'IMO-only',len(bis-bms),'MMSI-only',len(bms-bis))
