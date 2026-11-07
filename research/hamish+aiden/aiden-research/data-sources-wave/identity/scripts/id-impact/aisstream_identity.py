"""id-impact: short-window identity behaviour in the worldwide AISStream capture.

For each MMSI in the capture window: set of names (MetaData.ShipName, msg 5 Name,
msg 24 ReportA Name), set of IMO numbers (msg 5), callsigns, ship types, dims.
Then measure the two failure modes of MMSI-only keying in this window:
  - one MMSI carrying >1 identity  -> merged record (two ships in one track)
  - one IMO under >1 MMSI          -> split record (one ship in two tracks)
plus fleet coverage: how many vessels give an IMO at all (the only fallback key).
"""
import json, math, sys
from collections import defaultdict

WAVE = '/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave'
SRC = WAVE + '/data/identity/aisstream-capture.jsonl'
OUT = WAVE + '/data/id-impact/aisstream_identity_summary.json'

MISSING = {'', 'UNKNOWN', 'N/A', '0'}


def norm(s):
    return ''.join(ch for ch in (s or '').upper() if ch.isalnum())


def clean(v):
    if v is None:
        return None
    v = str(v).strip().strip('\x00')
    return v if v.upper() not in MISSING else None


def hav_nm(a, b, c, d):
    R = 3440.065
    p1, p2 = math.radians(a), math.radians(c)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))


v = {}
imo_to_mmsi = defaultdict(set)
t0 = t1 = None
counts = defaultdict(int)

for line in open(SRC):
    d = json.loads(line)
    msg = d.get('msg') or {}
    mt = msg.get('MessageType')
    counts[mt] += 1
    md = msg.get('MetaData') or {}
    ms = md.get('MMSI')
    r = d.get('recv')
    if r:
        t0 = r if t0 is None or r < t0 else t0
        t1 = r if t1 is None or r > t1 else t1
    if not ms:
        continue
    ms = str(int(ms))
    if len(ms) != 9:
        continue
    e = v.get(ms)
    if e is None:
        e = v[ms] = {'names': {}, 'imos': {}, 'cs': {}, 'types': {}, 'pos': 0,
                     'first_ts': md.get('time_utc'), 'last_ts': md.get('time_utc'),
                     'jumps': 0, 'last': None, 'cls': set()}
    body = msg.get('Message') or {}
    name = None
    imo = None
    cs = None
    typ = None
    lat = md.get('latitude'); lon = md.get('longitude')
    if mt == 'StaticDataReport':
        s = body.get('StaticDataReport') or {}
        ra = s.get('ReportA') or {}
        name = clean(ra.get('Name') if ra.get('Valid') else None) or clean(md.get('ShipName'))
        rb = s.get('ReportB') or {}
        if rb.get('Valid'):
            cs = clean(rb.get('CallSign'))
            typ = rb.get('ShipType') or None
        e['cls'].add('B')
    elif mt == 'ShipStaticData':
        s = body.get('ShipStaticData') or {}
        name = clean(s.get('Name'))
        imo = s.get('ImoNumber')
        if imo in (0, None):
            imo = None
        cs = clean(s.get('CallSign'))
        typ = s.get('Type') or None
        e['cls'].add('A')
    else:
        name = clean(md.get('ShipName'))
        if mt in ('PositionReport',):
            e['cls'].add('A')
        elif mt == 'StandardClassBPositionReport':
            e['cls'].add('B')

    if name:
        e['names'][name] = e['names'].get(name, 0) + 1
    if imo:
        imo = str(int(imo))
        e['imos'][imo] = e['imos'].get(imo, 0) + 1
        imo_to_mmsi[imo].add(ms)
    if cs:
        e['cs'][cs] = e['cs'].get(cs, 0) + 1
    if typ:
        e['types'][str(typ)] = e['types'].get(str(typ), 0) + 1

    if r and lat is not None and lon is not None:
        e['pos'] += 1
        if e['last'] is None:
            e['last'] = (r, lat, lon)
        else:
            lr, la, lo = e['last']
            dt = r - lr
            if dt >= 60:
                kn = hav_nm(la, lo, lat, lon) / (dt / 3600.0)
                if kn > 60:
                    e['jumps'] += 1
                e['last'] = (r, lat, lon)
            elif dt > 0:
                e['last'] = (r, lat, lon)

n = len(v)
multi_name = [ms for ms, e in v.items() if len(e['names']) > 1]
multi_imo = [ms for ms, e in v.items() if len(e['imos']) > 1]
with_imo = sum(1 for e in v.values() if e['imos'])
jump = [ms for ms, e in v.items() if e['jumps']]

imo_multi = {im: sorted(s) for im, s in imo_to_mmsi.items() if len(s) > 1}

out = {
    'source': SRC,
    'window_s': round((t1 - t0), 1) if t0 else None,
    'messages_by_type': dict(counts),
    'mmsi_with_positions': sum(1 for e in v.values() if e['pos']),
    'mmsi_total': n,
    'mmsi_with_imo': with_imo,
    'mmsi_with_name': sum(1 for e in v.values() if e['names']),
    'mmsi_multiple_names': len(multi_name),
    'mmsi_multiple_names_list': [
        {'mmsi': ms, 'names': v[ms]['names'], 'norm_same': len({norm(k) for k in v[ms]['names']}) == 1}
        for ms in multi_name[:40]],
    'mmsi_multiple_imos': len(multi_imo),
    'mmsi_multiple_imos_list': [{'mmsi': ms, 'imos': v[ms]['imos']} for ms in multi_imo[:40]],
    'mmsi_multiple_callsigns': sum(1 for e in v.values() if len(e['cs']) > 1),
    'mmsi_multiple_types': sum(1 for e in v.values() if len(e['types']) > 1),
    'mmsi_with_infeasible_jump': len(jump),
    'imo_total': len(imo_to_mmsi),
    'imo_on_multiple_mmsi': len(imo_multi),
    'imo_multi_examples': {k: imo_multi[k] for k in list(imo_multi)[:15]},
}
json.dump(out, open(OUT, 'w'), indent=1)
print(json.dumps(out, indent=1))
