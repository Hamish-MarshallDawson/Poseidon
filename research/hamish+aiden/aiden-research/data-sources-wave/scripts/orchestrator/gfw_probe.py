"""Throwaway read-only Global Fishing Watch probe. Never prints the token."""
import json, os, sys, time, urllib.error, urllib.parse, urllib.request
TOKEN = [l.split('=', 1)[1].strip() for l in open(os.path.expanduser('~/.config/hedged-bets/wave.env')) if l.startswith('GFW_API_TOKEN=')][0]
OUT = sys.argv[1]; B = 'https://gateway.api.globalfishingwatch.org/v3'
REG = {'Danish straits': (9.5, 54, 14, 58), 'Gulf of Finland': (22, 59, 30.5, 61), 'Hormuz': (55, 25.5, 57.5, 27), 'Gulf of Oman': (57.5, 22, 62, 26), 'Red Sea south': (41, 12, 44, 16),
       'Malacca': (98, 2, 104, 6), 'Natuna': (105, 2, 110, 6), 'South China Sea open': (110, 8, 118, 16), 'Java Sea': (106, -7, 116, -3), 'Gulf of Guinea': (-5, -2, 10, 6)}
res = {}


def req(path, body=None, q=None):
    u = B + path + ('?' + urllib.parse.urlencode(q, doseq=True) if q else '')
    r = urllib.request.Request(u, data=json.dumps(body).encode() if body is not None else None, headers={'Authorization': 'Bearer ' + TOKEN, 'Content-Type': 'application/json', 'User-Agent': 'hacktheburgh-feasibility/1.0'})
    t = time.time()
    try:
        with urllib.request.urlopen(r, timeout=120) as x:
            return x.status, json.load(x), round(time.time() - t, 1)
    except urllib.error.HTTPError as e:
        return e.code, e.read().decode('utf8', 'replace')[:500].replace(TOKEN, '***'), round(time.time() - t, 1)
    except Exception as e:
        return 0, str(e)[:300], round(time.time() - t, 1)


def poly(b):
    a, c, d, e = b
    return {'type': 'Polygon', 'coordinates': [[[a, c], [d, c], [d, e], [a, e], [a, c]]]}


def rows(d):
    return [x for e in d.get('entries', []) for v in e.values() for x in (v or [])]


def report(ds, b, start, end, extra=None):
    q = {'spatial-resolution': 'LOW', 'temporal-resolution': 'DAILY', 'datasets[0]': ds, 'date-range': f'{start},{end}', 'format': 'JSON', 'spatial-aggregation': 'true'}
    q.update(extra or {})
    return req('/4wings/report', {'geojson': poly(b)}, q)


S, E = '2026-10-08', '2026-11-07'
for name, b in REG.items():
    o = {}
    for label, ds, ex in [('sar_all', 'public-global-sar-presence:latest', None), ('sar_no_ais', 'public-global-sar-presence:latest', {'filters[0]': "matched='false'"}), ('sar_ais_matched', 'public-global-sar-presence:latest', {'filters[0]': "matched='true'"}), ('ais_presence', 'public-global-presence:latest', None), ('fishing', 'public-global-fishing-effort:latest', None)]:
        st, d, sec = report(ds, b, S, E, ex)
        if st == 200:
            r = rows(d); ds_ = sorted(x.get('date') for x in r if x.get('date')); o[label] = dict(status=st, sec=sec, days=len(set(ds_)), last=ds_[-1] if ds_ else None, detections=sum(x.get('detections', 0) or 0 for x in r), hours=round(sum(x.get('hours', 0) or 0 for x in r)), vessels_sum=sum(x.get('vesselIDs', 0) or 0 for x in r), sample=r[0] if r else None)
        else:
            o[label] = dict(status=st, err=d, sec=sec)
    st, d, sec = req('/events', {'datasets': ['public-global-gaps-events:latest'], 'startDate': S, 'endDate': E, 'geometry': poly(b)}, {'limit': 100, 'offset': 0})
    if st == 200:
        ent = d.get('entries', []); ts = sorted(x.get('end') or x.get('start') or '' for x in ent)
        o['gap_events'] = dict(status=st, sec=sec, total=d.get('total'), returned=len(ent), newest=ts[-1] if ts else None, sample=ent[0] if ent else None)
    else:
        o['gap_events'] = dict(status=st, err=d, sec=sec)
    res[name] = o
    json.dump(res, open(OUT, 'w'), indent=1, default=str)
    print(name, {k: {a: v.get(a) for a in ('status', 'days', 'last', 'detections', 'hours', 'total', 'newest', 'err') if v.get(a) is not None} for k, v in o.items()}, flush=True)
