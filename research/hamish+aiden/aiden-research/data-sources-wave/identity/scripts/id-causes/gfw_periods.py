import json, sys
from datetime import datetime
p = sys.argv[1]
def d(s):
    return datetime.fromisoformat(s.replace('Z','+00:00')) if s else None
ships = [json.loads(l) for l in open(p) if l.strip()]
trans = []
for s in ships:
    pers = []
    for ent in s['entries']:
        for e in ent.get('selfReportedInfo') or []:
            pers.append(e)
    # dedupe identical records
    seen=set(); uniq=[]
    for e in pers:
        k=(e.get('ssvid'), e.get('shipname'), e.get('flag'), e.get('transmissionDateFrom'), e.get('transmissionDateTo'))
        if k in seen: continue
        seen.add(k); uniq.append(e)
    uniq.sort(key=lambda e: e.get('transmissionDateFrom') or '')
    print(f"== IMO {s['imo']} {s['group']} {s['region']} periods={len(uniq)}")
    for e in uniq:
        print(f"   {e.get('transmissionDateFrom','')[:10]} -> {e.get('transmissionDateTo','')[:10]} mmsi={e.get('ssvid')} mid={str(e.get('ssvid'))[:3]} {e.get('flag')} {e.get('shipname')!r} cs={e.get('callsign')} {e.get('matchFields')}")
    for a,b in zip(uniq, uniq[1:]):
        ta=d(b.get('transmissionDateFrom')); tb=d(a.get('transmissionDateTo'))
        gap=(ta-tb).total_seconds()/86400 if ta and tb else None
        trans.append(dict(imo=s['imo'],grp=s['group'],
            flag_changed=a.get('flag')!=b.get('flag'), mmsi_changed=a.get('ssvid')!=b.get('ssvid'),
            name_changed=a.get('shipname')!=b.get('shipname'), cs_changed=a.get('callsign')!=b.get('callsign'),
            gap_days=gap, same_flag_days=None))
print('\nTRANSITIONS', len(trans))
print('flag changed', sum(t['flag_changed'] for t in trans))
print('mmsi changed', sum(t['mmsi_changed'] for t in trans))
print('mmsi changed & flag same', sum(1 for t in trans if t['mmsi_changed'] and not t['flag_changed']))
print('flag changed & mmsi same', sum(1 for t in trans if t['flag_changed'] and not t['mmsi_changed']))
print('name changed', sum(t['name_changed'] for t in trans))
print('name changed & mmsi same', sum(1 for t in trans if t['name_changed'] and not t['mmsi_changed']))
print('cs changed', sum(t['cs_changed'] for t in trans))
ov=[t for t in trans if t['gap_days'] is not None and t['gap_days']<0]
print('overlaps (next starts before prev ends)', len(ov), 'min gap days', min([t['gap_days'] for t in trans if t['gap_days'] is not None], default=None), 'max', max([t['gap_days'] for t in trans if t['gap_days'] is not None], default=None))
print('switch gap <=1 day', sum(1 for t in trans if t['gap_days'] is not None and abs(t['gap_days'])<=1))
print('switch gap <=30 days', sum(1 for t in trans if t['gap_days'] is not None and abs(t['gap_days'])<=30))
