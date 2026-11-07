import json, sys
from collections import defaultdict
p=sys.argv[1]
name=defaultdict(set); imo=defaultdict(set); cs=defaultdict(set); st=defaultdict(set); dim=defaultdict(set)
n=0; typ=defaultdict(int); mmsis=set()
def val(x):
    return x if x not in (None,'',0) else None
for l in open(p):
    try: d=json.loads(l)
    except: continue
    m=d.get('msg') or {}
    t=m.get('MessageType'); typ[t]+=1
    md=m.get('MetaData') or {}
    u=md.get('MMSI') or md.get('UserID')
    if not u: continue
    mmsis.add(u)
    msg=m.get('Message') or {}
    if t=='ShipStaticData':
        s=msg.get('ShipStaticData') or {}
        if val(s.get('Name')): name[u].add(s['Name'].strip())
        if val(s.get('ImoNumber')): imo[u].add(s['ImoNumber'])
        if val(s.get('CallSign')): cs[u].add(s['CallSign'].strip())
        if val(s.get('Type')): st[u].add(s['Type'])
    elif t=='StaticDataReport':
        s=msg.get('StaticDataReport') or {}
        ra=s.get('ReportA') or {}; rb=s.get('ReportB') or {}
        if val(ra.get('Name')): name[u].add(ra['Name'].strip())
        if val(rb.get('CallSign')): cs[u].add(rb['CallSign'].strip())
        if val(rb.get('ShipType')): st[u].add(rb['ShipType'])
        dm=rb.get('Dimension') or {}
        if any(dm.values()): dim[u].add((dm.get('A'),dm.get('B'),dm.get('C'),dm.get('D')))
    # MetaData ShipName as extra
    if val(md.get('ShipName')): name[u].add(md['ShipName'].strip())
    n+=1
print('lines',n,'mmsis',len(mmsis),'types',dict(typ))
for label,dd in (('name',name),('imo',imo),('callsign',cs),('shiptype',st),('dims',dim)):
    multi={k:v for k,v in dd.items() if len(v)>1}
    print(label,'mmsis_with_value',len(dd),'multi',len(multi), 'examples', list(multi.items())[:6])
