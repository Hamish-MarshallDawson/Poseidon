"""id-impact: what breaks if we key tracks on MMSI only.

Streams the full Danish day (2026-11-01, ~16M rows) from the zip and builds
per-MMSI and per-IMO identity summaries, then measures:
  - IMO seen under >1 MMSI in one day (track splits / merges)
  - handover timing & distance between the old and new key
  - MMSI carrying >1 IMO, >1 name, >1 size (reassignment or collision)
  - infeasible position jumps within one MMSI (false jumps)
  - gaps from the existing gap detector that are explained by a key change

Writes JSON to $WAVE/data/id-impact/dma_identity_summary.json
"""
import csv, io, json, math, sys, zipfile
from collections import defaultdict

WAVE = '/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave'
ZIP = WAVE + '/data/t-match/aisdk-2026-11-01.zip'
OUT = WAVE + '/data/id-impact/dma_identity_summary.json'
GAPS = WAVE + '/data/t-ais-history/day_2026-11-01/gaps.csv'

MOBILE_SKIP = {'Base Station', 'AtoN', 'SAR Airborne', 'Search and Rescue Transponder',
               'Emergency PIRB', 'MOB Device', 'Physical Shore Station', 'Undefined'}
MISSING = {'', 'Unknown', 'unknown', 'Undefined', 'undefined', 'N/A', '0'}


def norm(s):
    return ''.join(ch for ch in (s or '').upper() if ch.isalnum())


import datetime
_TS_CACHE = {}
_DAY0 = datetime.datetime(2026, 11, 1, tzinfo=datetime.timezone.utc).timestamp()


def ts_epoch(s):
    # '01/11/2026 00:00:00' -> epoch seconds (fast path, cached by string)
    v = _TS_CACHE.get(s)
    if v is not None:
        return v
    t = s[-8:]                       # HH:MM:SS
    v = _DAY0 + int(t[0:2]) * 3600 + int(t[3:5]) * 60 + int(t[6:8])
    _TS_CACHE[s] = v
    return v


def hav_nm(a, b, c, d):
    R = 3440.065
    p1, p2 = math.radians(a), math.radians(c)
    dp = p2 - p1
    dl = math.radians(d - b)
    h = math.sin(dp / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * R * math.asin(min(1.0, math.sqrt(h)))


mmsi = {}          # mmsi -> dict of aggregates
imo_to_mmsi = defaultdict(set)
rows = 0
skipped = 0
bad_float = 0

z = zipfile.ZipFile(ZIP)
f = io.TextIOWrapper(z.open('aisdk-2026-11-01.csv'), encoding='utf-8', errors='replace')
r = csv.reader(f)
hdr = next(r)
idx = {h: i for i, h in enumerate(hdr)}
I_T, I_CLS, I_M = idx['# Timestamp'], idx['Type of mobile'], idx['MMSI']
I_LAT, I_LON = idx['Latitude'], idx['Longitude']
I_SOG = idx['SOG']
I_IMO, I_CS, I_NAME = idx['IMO'], idx['Callsign'], idx['Name']
I_TYPE, I_W, I_L = idx['Ship type'], idx['Width'], idx['Length']

for row in r:
    rows += 1
    if rows % 2000000 == 0:
        print('rows', rows, 'mmsis', len(mmsi), flush=True)
    cls = row[I_CLS]
    if cls in MOBILE_SKIP:
        skipped += 1
        continue
    ms = row[I_M].strip()
    if len(ms) != 9:
        skipped += 1
        continue
    try:
        t = ts_epoch(row[I_T])
        lat = float(row[I_LAT]); lon = float(row[I_LON])
    except Exception:
        bad_float += 1
        continue
    d = mmsi.get(ms)
    if d is None:
        d = mmsi[ms] = {
            'cls': cls, 'n': 0, 'first_ts': t, 'last_ts': t,
            'first_pos': (lat, lon), 'last_pos': (lat, lon),
            'names': {}, 'imos': {}, 'cs': {}, 'types': {}, 'sizes': {},
            'jumps': 0, 'jump_max_kn': 0.0, 'jump_examples': [],
            'last': (t, lat, lon),
        }
    d['n'] += 1
    if t < d['first_ts']:
        d['first_ts'] = t; d['first_pos'] = (lat, lon)
    if t > d['last_ts']:
        d['last_ts'] = t; d['last_pos'] = (lat, lon)

    nm = row[I_NAME].strip()
    if nm and nm not in MISSING:
        e = d['names'].get(nm)
        if e is None:
            d['names'][nm] = [t, t]
        else:
            if t < e[0]: e[0] = t
            if t > e[1]: e[1] = t
    im = row[I_IMO].strip()
    if im and im not in MISSING:
        e = d['imos'].get(im)
        if e is None:
            d['imos'][im] = [t, t]
        else:
            if t < e[0]: e[0] = t
            if t > e[1]: e[1] = t
        imo_to_mmsi[im].add(ms)
    c = row[I_CS].strip()
    if c and c not in MISSING:
        e = d['cs'].get(c)
        if e is None: d['cs'][c] = [t, t]
        else:
            if t < e[0]: e[0] = t
            if t > e[1]: e[1] = t
    ty = row[I_TYPE].strip()
    if ty and ty not in MISSING:
        e = d['types'].get(ty)
        if e is None: d['types'][ty] = [t, t]
        else:
            if t < e[0]: e[0] = t
            if t > e[1]: e[1] = t
    sz = (row[I_L].strip(), row[I_W].strip())
    if sz[0] and sz[0] not in MISSING:
        e = d['sizes'].get(sz)
        if e is None: d['sizes'][sz] = [t, t]
        else:
            if t < e[0]: e[0] = t
            if t > e[1]: e[1] = t

    lt, la, lo = d['last']
    dt = t - lt
    if dt >= 60:
        try:
            sog = float(row[I_SOG]) if row[I_SOG] not in ('', None) else None
        except Exception:
            sog = None
        dist = hav_nm(la, lo, lat, lon)
        kn = dist / (dt / 3600.0)
        if kn > 60.0:
            d['jumps'] += 1
            if kn > d['jump_max_kn']:
                d['jump_max_kn'] = kn
            if len(d['jump_examples']) < 3:
                d['jump_examples'].append({'ts': t, 'from': [la, lo], 'to': [lat, lon],
                                           'dt_s': round(dt), 'nm': round(dist, 1),
                                           'implied_kn': round(kn, 1), 'sog': sog})
        d['last'] = (t, lat, lon)
    elif dt > 0:
        d['last'] = (t, lat, lon)

print('parsed rows', rows, 'skipped', skipped, 'bad', bad_float, flush=True)

# ---- aggregates -------------------------------------------------------
n_mmsi = len(mmsi)
multi_name = multi_imo = multi_cs = multi_type = multi_size = 0
name_change_norm_equal = 0
jump_mmsi = 0
jump_examples = []
for ms, d in mmsi.items():
    if len(d['names']) > 1:
        multi_name += 1
        norms = {norm(n) for n in d['names']}
        if len(norms) == 1:
            name_change_norm_equal += 1
    if len(d['imos']) > 1: multi_imo += 1
    if len(d['cs']) > 1: multi_cs += 1
    if len(d['types']) > 1: multi_type += 1
    if len(d['sizes']) > 1: multi_size += 1
    if d['jumps'] > 0:
        jump_mmsi += 1
        if len(jump_examples) < 15:
            jump_examples.append({'mmsi': ms, 'jumps': d['jumps'],
                                  'max_kn': round(d['jump_max_kn'], 1),
                                  'first': d['jump_examples'][0]})

# IMO -> MMSI within the day
imo_multi = {im: sorted(v) for im, v in imo_to_mmsi.items() if len(v) > 1}
handovers = []
overlaps = []
for im, ms_list in imo_multi.items():
    ivs = []
    for ms in ms_list:
        d = mmsi[ms]
        ivs.append((d['first_ts'], d['last_ts'], ms))
    ivs.sort()
    for i in range(len(ivs) - 1):
        a = ivs[i]; b = ivs[i + 1]
        da, db = mmsi[a[2]], mmsi[b[2]]
        # overlap?
        ov = min(a[1], b[1]) - max(a[0], b[0])
        gap_s = b[0] - a[1]
        dist = hav_nm(da['last_pos'][0], da['last_pos'][1], db['first_pos'][0], db['first_pos'][1])
        rec = {'imo': im, 'old': a[2], 'new': b[2], 'gap_s': round(gap_s),
               'overlap_s': round(ov), 'dist_nm': round(dist, 1),
               'old_name': sorted(da['names'])[0] if da['names'] else None,
               'new_name': sorted(db['names'])[0] if db['names'] else None,
               'old_n': da['n'], 'new_n': db['n'],
               'speed_between_kn': round(dist / (gap_s / 3600.0), 1) if gap_s > 0 else None}
        handovers.append(rec)
        if ov > 300:
            overlaps.append(rec)

# ---- gaps explained by a key change -----------------------------------
gaps_explained = 0
gaps_total = 0
gap_rows = []
with open(GAPS) as fh:
    for g in csv.DictReader(fh):
        gaps_total += 1
        ms = g['mmsi']; im = (g['imo'] or '').strip()
        gs = ts_epoch(g['gap_start'][11:])
        ge = ts_epoch(g['gap_end'][11:])
        # an IMO-level continuation during the gap on a different MMSI?
        hit = None
        if im and im not in MISSING:
            for other in imo_to_mmsi.get(im, ()):
                if other == ms:
                    continue
                od = mmsi.get(other)
                if not od:
                    continue
                # other key reports inside the gap window
                if od['first_ts'] <= ge and od['last_ts'] >= gs:
                    hit = other
                    break
        if hit:
            gaps_explained += 1
            if len(gap_rows) < 15:
                gap_rows.append({'mmsi': ms, 'imo': im, 'other_mmsi': hit,
                                 'gap_min': g['gap_min'], 'name': g['name']})

summary = {
    'day': '2026-11-01', 'source': 'aisdk-2026-11-01.zip (full day, Danish AIS)',
    'rows_parsed': rows, 'rows_skipped_nonvessel_or_bad_mmsi': skipped,
    'mobile_mmsi': n_mmsi,
    'mmsi_multiple_names': multi_name,
    'mmsi_multiple_names_normalised_equal': name_change_norm_equal,
    'mmsi_multiple_imos': multi_imo,
    'mmsi_multiple_callsigns': multi_cs,
    'mmsi_multiple_shiptypes': multi_type,
    'mmsi_multiple_sizes': multi_size,
    'mmsi_with_infeasible_jump': jump_mmsi,
    'jump_examples': jump_examples,
    'imo_seen': len(imo_to_mmsi),
    'imo_on_multiple_mmsi_same_day': len(imo_multi),
    'handover_pairs': len(handovers),
    'handover_gap_lt_20min': sum(1 for h in handovers if 0 <= h['gap_s'] < 1200),
    'handover_gap_lt_6h': sum(1 for h in handovers if 0 <= h['gap_s'] < 21600),
    'handover_overlap_gt_5min': len(overlaps),
    'handover_examples': sorted(handovers, key=lambda h: -h['gap_s'])[:15],
    'overlap_examples': overlaps[:10],
    'gap_events_total': gaps_total,
    'gap_events_explained_by_other_mmsi_same_imo': gaps_explained,
    'gap_examples': gap_rows,
}
json.dump(summary, open(OUT, 'w'), indent=1)
print(json.dumps({k: v for k, v in summary.items() if not k.endswith('examples')}, indent=1))
