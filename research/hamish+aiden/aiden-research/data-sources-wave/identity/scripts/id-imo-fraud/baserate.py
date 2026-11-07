"""Base rates for IMO-vs-registry and identity-chain tests. python3 -I baserate.py <gfw.jsonl>"""
import json, sys, collections, datetime as dt
def tp(s): return dt.datetime.fromisoformat(s.replace("Z","+00:00")) if s else None
rows=[json.loads(l) for l in open(sys.argv[1])]
n=0; after=0; g90=g365=g730=0; deltas=[]
chains=collections.Counter()
for r in rows:
    selfend=regend=None
    ids=set()
    for g in r['entries']:
        for s in g.get('selfReportedInfo') or []:
            b=tp(s.get('transmissionDateTo'))
            if b and (selfend is None or b>selfend): selfend=b
            if s.get('ssvid'): ids.add((s['ssvid'],(s.get('shipname') or '').strip(),s.get('flag')))
        for x in g.get('registryInfo') or []:
            b=tp(x.get('transmissionDateTo'))
            if b and (regend is None or b>regend): regend=b
    if not (selfend and regend): continue
    n+=1; d=(selfend-regend).days; deltas.append(d)
    if d>0: after+=1
    if d>90: g90+=1
    if d>365: g365+=1
    if d>730: g730+=1
deltas.sort()
print('records', len(rows), 'with both self+registry', n)
print('ais after last registry record', after, '/', n)
print('>90d', g90, '>365d', g365, '>730d', g730)
if deltas: print('median delta days', deltas[len(deltas)//2], 'min', deltas[0], 'max', deltas[-1])
