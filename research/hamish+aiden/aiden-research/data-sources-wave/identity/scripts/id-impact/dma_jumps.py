"""id-impact: false jumps within one MMSI key on a full Danish day.

Excludes the AIS 'not available' position sentinel (lat 91 / lon 0 or 181) and
requires two observations <=30 min apart, so a jump is a real teleport on one
radio key, not a long absence. Reports how many MMSIs teleport, at what size,
and a few examples for the map display.
"""
import csv, io, json, math, zipfile

WAVE = '/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave'
ZIP = WAVE + '/data/t-match/aisdk-2026-11-01.zip'
OUT = WAVE + '/data/id-impact/dma_jumps_summary.json'
SKIP = {'Base Station', 'AtoN', 'SAR Airborne', 'Search and Rescue Transponder',
        'Emergency PIRB', 'MOB Device', 'Physical Shore Station', 'Undefined'}
DAY0 = 1793491200.0 + 0.0  # placeholder, computed below
import datetime
DAY0 = datetime.datetime(2026, 11, 1, tzinfo=datetime.timezone.utc).timestamp()
TS = {}


def ts(s):
    v = TS.get(s)
    if v is None:
        t = s[-8:]
        v = DAY0 + int(t[0:2]) * 3600 + int(t[3:5]) * 60 + int(t[6:8])
        TS[s] = v
    return v


def hav(a, b, c, d):
    R = 3440.065
    p1, p2 = math.radians(a), math.radians(c)
    h = math.sin((p2 - p1) / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(math.radians(d - b) / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))


def valid(lat, lon):
    return abs(lat) <= 90 and abs(lon) <= 180 and not (lat >= 90.0) and not abs(lon) >= 181.0


z = zipfile.ZipFile(ZIP)
f = io.TextIOWrapper(z.open('aisdk-2026-11-01.csv'), encoding='utf-8', errors='replace')
r = csv.reader(f)
h = next(r)
i = {k: n for n, k in enumerate(h)}
T, C, M = i['# Timestamp'], i['Type of mobile'], i['MMSI']
LA, LO, SO = i['Latitude'], i['Longitude'], i['SOG']
IM, NM = i['IMO'], i['Name']
last = {}
jump_mmsi = {}
sentinel = 0
rows = 0
for row in r:
    rows += 1
    if row[C] in SKIP:
        continue
    ms = row[M].strip()
    if len(ms) != 9:
        continue
    try:
        lat = float(row[LA]); lon = float(row[LO]); t = ts(row[T])
    except Exception:
        continue
    if not valid(lat, lon):
        sentinel += 1
        continue
    p = last.get(ms)
    if p is None:
        last[ms] = (t, lat, lon)
        continue
    dt = t - p[0]
    if dt <= 0:
        continue
    if dt <= 1800:
        nm = hav(p[1], p[2], lat, lon)
        kn = nm / (dt / 3600.0)
        if kn > 100 and nm > 5:
            e = jump_mmsi.setdefault(ms, {'n': 0, 'max_kn': 0, 'max_nm': 0, 'ex': None})
            e['n'] += 1
            if kn > e['max_kn']:
                e['max_kn'] = round(kn, 1)
            if nm > e['max_nm']:
                e['max_nm'] = round(nm, 1)
            if e['ex'] is None:
                e['ex'] = {'ts': t, 'dt_s': round(dt), 'nm': round(nm, 1), 'kn': round(kn, 1),
                           'from': [p[1], p[2]], 'to': [lat, lon], 'sog': row[SO]}
    last[ms] = (t, lat, lon)

out = {'day': '2026-11-01', 'rows': rows, 'sentinel_positions_skipped': sentinel,
       'mmsi_with_jump_gt100kn_le30min': len(jump_mmsi),
       'jump_events': sum(v['n'] for v in jump_mmsi.values()),
       'examples': sorted(([k] + [v[k2] for k2 in ('n', 'max_kn', 'max_nm', 'ex')]
                           for k, v in jump_mmsi.items()), key=lambda x: -x[3])[:12]}
json.dump(out, open(OUT, 'w'), indent=1)
print(json.dumps({k: v for k, v in out.items() if k != 'examples'}, indent=1))
