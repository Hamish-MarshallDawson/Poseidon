"""Throwaway: Global Fishing Watch identity histories for sampled IMOs. Never prints the token."""
import json, os, random, sys, time, urllib.error, urllib.parse, urllib.request

OUT = sys.argv[1]; random.seed(20261107)
T = [l.split('=', 1)[1].strip() for l in open(os.path.expanduser('~/.config/hedged-bets/wave.env')) if l.startswith('GFW_API_TOKEN=')][0]
H = {'Authorization': 'Bearer ' + T, 'Content-Type': 'application/json', 'User-Agent': 'hacktheburgh-feasibility/1.0'}
B = 'https://gateway.api.globalfishingwatch.org/v3'
REG = {'Hormuz': (55, 25.5, 57.5, 27), 'Malacca': (98, 2, 104, 6), 'Danish': (9.5, 54, 14, 58)}


def call(req):
    for i in range(5):
        try:
            return json.load(urllib.request.urlopen(req, timeout=120))
        except urllib.error.HTTPError as e:
            if e.code in (429, 500, 502, 503, 504):
                time.sleep(5 * (i + 1)); continue
            raise
    raise RuntimeError('gave up')


def presence(b):
    q = {'spatial-resolution': 'LOW', 'temporal-resolution': 'ENTIRE', 'group-by': 'VESSEL_ID', 'datasets[0]': 'public-global-presence:latest',
         'date-range': '2026-02-01,2026-02-28', 'format': 'JSON', 'spatial-aggregation': 'true'}
    geo = {'type': 'Polygon', 'coordinates': [[[b[0], b[1]], [b[2], b[1]], [b[2], b[3]], [b[0], b[3]], [b[0], b[1]]]]}
    d = call(urllib.request.Request(B + '/4wings/report?' + urllib.parse.urlencode(q), json.dumps({'geojson': geo}).encode(), H))
    r = {}
    for e in d['entries']:
        for v in e.values():
            for x in (v or []):
                r.setdefault(x.get('vesselId'), x)
    return list(r.values())


plan = []
for reg, b in REG.items():
    v = [x for x in presence(b) if x.get('imo')]
    t = [x for x in v if x.get('geartype') == 'TANKER']
    c = [x for x in v if x.get('geartype') == 'CARGO']
    s = [x for x in t if (x.get('lastTransmissionDate') or '9')[:7] <= '2026-08']
    print(reg, 'tankers', len(t), 'cargo', len(c), 'silent', len(s), flush=True)
    for group, pool, n in (('random_tanker', t, 150), ('random_cargo', c, 100), ('silent_tanker', s, 80)):
        plan += [(x['imo'], group, reg) for x in random.sample(pool, min(n, len(pool)))]
random.shuffle(plan)
print('planned', len(plan), flush=True)
done = set()
with open(OUT, 'a', buffering=1) as f:
    for i, (imo, group, reg) in enumerate(plan):
        if (imo, group, reg) in done: continue
        q = {'where': f"imo='{imo}'", 'datasets[0]': 'public-global-vessel-identity:latest', 'limit': 25, 'includes[0]': 'OWNERSHIP', 'includes[1]': 'MATCH_CRITERIA'}
        try:
            d = call(urllib.request.Request(B + '/vessels/search?' + urllib.parse.urlencode(q), headers=H))
            ent = [{k: e.get(k) for k in ('selfReportedInfo', 'registryInfo', 'registryOwners', 'combinedSourcesInfo')} for e in d.get('entries', [])]
            f.write(json.dumps({'imo': imo, 'group': group, 'region': reg, 'total': d.get('total'), 'entries': ent}) + '\n')
        except Exception as e:
            f.write(json.dumps({'imo': imo, 'group': group, 'region': reg, 'error': str(e)[:150].replace(T, '***')}) + '\n')
        done.add((imo, group, reg))
        if i % 100 == 0: print(i, flush=True)
        time.sleep(0.35)
print('done', len(done), flush=True)
