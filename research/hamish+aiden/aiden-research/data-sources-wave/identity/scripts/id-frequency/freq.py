"""id-frequency: identity-change frequency from GFW public-global-vessel-identity samples.
Input: $WAVE/data/identity/gfw-identities.jsonl (growing). Read-only, absolute paths.
Run: python3 -I /abs/path/freq.py [path.jsonl]
"""
import json, sys, collections, datetime as dt

PATH = sys.argv[1] if len(sys.argv) > 1 else '/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave/data/identity/gfw-identities.jsonl'


def ts(s):
    if not s:
        return None
    s = s.replace('Z', '').replace('+00:00', '')
    try:
        d = dt.datetime.fromisoformat(s)
    except ValueError:
        d = dt.datetime.strptime(s[:19], '%Y-%m-%dT%H:%M:%S')
    return d.replace(tzinfo=None)


def span_years(a, b):
    return (b - a).total_seconds() / 86400.0 / 365.25


recs = []
bad = 0
for line in open(PATH):
    r = json.loads(line)
    if 'entries' not in r:
        bad += 1
        continue
    recs.append(r)

# ---------- flatten ----------
ships = []
for r in recs:
    sr, rg, ow = [], [], []
    for e in r['entries']:
        for s in e.get('selfReportedInfo') or []:
            sr.append(s)
        for g in e.get('registryInfo') or []:
            rg.append(g)
        for o in e.get('registryOwners') or []:
            ow.append(o)
    # dedupe self-reported periods by (ssvid,name,flag,callsign,from,to)
    seen = set()
    sr2 = []
    for s in sr:
        k = (s.get('ssvid'), s.get('shipname'), s.get('flag'), s.get('callsign'),
             s.get('transmissionDateFrom'), s.get('transmissionDateTo'))
        if k in seen:
            continue
        seen.add(k)
        sr2.append(s)
    ships.append(dict(imo=r['imo'], group=r['group'], region=r['region'],
                      total=r.get('total'), n_entries=len(r['entries']),
                      sr=sr2, rg=rg, ow=ow))

N = len(ships)
print(f'== sample: {N} IMO records ({bad} with error)')
print('by group/region:', dict(collections.Counter((s['group'], s['region']) for s in ships)))
print('by group:', dict(collections.Counter(s['group'] for s in ships)))

# ship-level summary
def uniq(vals):
    return {v for v in vals if v not in (None, '')}


shiprows = []
for s in ships:
    sr = [x for x in s['sr'] if ts(x.get('transmissionDateFrom'))]
    sr.sort(key=lambda x: ts(x['transmissionDateFrom']))
    if not sr:
        shiprows.append(dict(ship=s, sr=[], span=None))
        continue
    start = min(ts(x.get('transmissionDateFrom')) for x in sr)
    end = max(ts(x.get('transmissionDateTo') or x.get('transmissionDateFrom')) for x in sr)
    names = uniq(x.get('shipname') for x in sr)
    mmsis = uniq(x.get('ssvid') for x in sr)
    flags = uniq(x.get('flag') for x in sr)
    calls = uniq(x.get('callsign') for x in sr)
    rg_names = uniq(x.get('shipname') for x in s['rg'])
    rg_flags = uniq(x.get('flag') for x in s['rg'])
    rg_ids = uniq(x.get('id') for x in s['rg'])
    shiprows.append(dict(ship=s, sr=sr, start=start, end=end, span=span_years(start, end),
                         names=names, mmsis=mmsis, flags=flags, calls=calls,
                         rg_names=rg_names, rg_flags=rg_flags, rg_ids=rg_ids,
                         owners=uniq(o.get('name') for o in s['ow'])))

have = [r for r in shiprows if r['sr']]
print(f'ships with >=1 self-reported period: {len(have)}/{N}')
counts = collections.Counter(len(r['sr']) for r in have)
print('self-reported identity periods per ship:', dict(sorted(counts.items())))
tot_years = sum(r['span'] for r in have)
print(f'total observed ship-years: {tot_years:.0f}; median span {sorted(r["span"] for r in have)[len(have)//2]:.1f} y')

# ---------- change counts and rates ----------
fields = [('mmsi', 'mmsis'), ('name', 'names'), ('flag', 'flags'), ('callsign', 'calls')]
print('\n== changes per ship-year (distinct-1 over observed span sum), all ships pooled')
for label, key in fields + [('registry name', 'rg_names'), ('registry flag', 'rg_flags')]:
    ch = sum(max(0, len(r[key]) - 1) for r in have)
    print(f'  {label:15s} changes {ch:6d}  per ship-year {ch/tot_years:.3f}')

print('\n== per ship-year by group (pooled changes / pooled ship-years)')
for grp in ('random_tanker', 'random_cargo', 'silent_tanker'):
    rs = [r for r in have if r['ship'].get('group') == grp]
    ty = sum(r['span'] for r in rs)
    if not ty:
        continue
    row = []
    for label, key in fields:
        ch = sum(max(0, len(r[key]) - 1) for r in rs)
        row.append(f'{label} {ch/ty:.3f}')
    print(f'  {grp:14s} n={len(rs):4d} shipyears={ty:7.0f}  ' + '  '.join(row))

print('\n== per ship-year by region')
for reg in sorted({r['ship'].get('region') for r in have}):
    rs = [r for r in have if r['ship'].get('region') == reg]
    ty = sum(r['span'] for r in rs)
    row = []
    for label, key in fields:
        ch = sum(max(0, len(r[key]) - 1) for r in rs)
        row.append(f'{label} {ch/ty:.3f}')
    print(f'  {reg:10s} n={len(rs):4d} shipyears={ty:7.0f}  ' + '  '.join(row))

print('\n== per ship-year by year of observation (change events attributed to the year the new period starts)')
yearev = collections.defaultdict(lambda: collections.Counter())
yearyears = collections.Counter()
for r in have:
    # attribute: split span by calendar year to get ship-years per year
    y = r['start'].year
    while y <= r['end'].year:
        y0 = max(r['start'], dt.datetime(y, 1, 1))
        y1 = min(r['end'], dt.datetime(y + 1, 1, 1))
        if y1 > y0:
            yearyears[y] += span_years(y0, y1)
        y += 1
    prev = None
    for x in r['sr']:
        f = ts(x['transmissionDateFrom'])
        if prev is not None:
            if x.get('ssvid') != prev.get('ssvid'):
                yearev[f.year]['mmsi'] += 1
            if x.get('shipname') != prev.get('shipname'):
                yearev[f.year]['name'] += 1
            if x.get('flag') != prev.get('flag'):
                yearev[f.year]['flag'] += 1
        prev = x
for y in sorted(yearyears):
    if yearyears[y] < 20:
        continue
    e = yearev[y]
    print(f'  {y}  shipyears {yearyears[y]:6.0f}  mmsi {e["mmsi"]:4d} ({e["mmsi"]/yearyears[y]:.2f}/sy)'
          f'  name {e["name"]:4d} ({e["name"]/yearyears[y]:.2f})  flag {e["flag"]:4d} ({e["flag"]/yearyears[y]:.2f})')

# ---------- boundary / timing distribution ----------
print('\n== time between consecutive self-reported identity periods (per transition)')
buckets = collections.Counter()
trans = []
for r in have:
    prev = None
    for x in r['sr']:
        if prev is not None:
            gap = (ts(x['transmissionDateFrom']) - ts(prev.get('transmissionDateTo') or prev['transmissionDateFrom'])).total_seconds() / 3600.0
            trans.append((gap, x, prev, r))
            if gap <= -1:
                buckets['overlap (next starts before prev ends)'] += 1
            elif gap < 1:
                buckets['<=1 h'] += 1
            elif gap < 24:
                buckets['1-24 h'] += 1
            elif gap < 24 * 30:
                buckets['1-30 d'] += 1
            elif gap < 24 * 365:
                buckets['30-365 d'] += 1
            else:
                buckets['>365 d'] += 1
        prev = x
T = len(trans)
print(f'  transitions: {T} across {len(have)} ships')
for k in ['overlap (next starts before prev ends)', '<=1 h', '1-24 h', '1-30 d', '30-365 d', '>365 d']:
    print(f'    {k:42s} {buckets[k]:5d}  {100.0*buckets[k]/T if T else 0:5.1f}%')

# what changes at each transition
print('\n== field pattern at each transition (n=%d)' % T)
pats = collections.Counter()
for gap, x, prev, r in trans:
    pat = ''.join(k for k, f in (('M', 'ssvid'), ('N', 'shipname'), ('F', 'flag'), ('C', 'callsign'))
                  if x.get(f) != prev.get(f))
    pats[pat or '-'] += 1
for p, c in pats.most_common():
    print(f'    {p:6s} {c:5d}  {100.0*c/T:5.1f}%')

# MID change on MMSI switch
print('\n== MMSI switches: same country (same MID) vs different country')
same = diff = 0
for gap, x, prev, r in trans:
    a, b = str(prev.get('ssvid') or ''), str(x.get('ssvid') or '')
    if a == b:
        continue
    if len(a) == 9 and len(b) == 9:
        if a[:3] == b[:3]:
            same += 1
        else:
            diff += 1
print(f'    same MID {same}  different MID {diff}  total {same+diff}')

# ---------- share changing within a window ----------
print('\n== share of ships with >=1 change starting inside the last 12 months of their own observed window')
elig = [r for r in have if r['span'] >= 1.0]
def changed_within(r, days):
    cut = r['end'] - dt.timedelta(days=days)
    prev = None
    for x in r['sr']:
        f = ts(x['transmissionDateFrom'])
        if prev is not None and f >= cut:
            if any(x.get(k) != prev.get(k) for k in ('ssvid', 'shipname', 'flag')):
                return True
        prev = x
    return False
for days, lab in ((30, '1 month'), (365, '12 months')):
    n = sum(1 for r in elig if changed_within(r, days))
    print(f'    window {lab:9s} {n:4d}/{len(elig)} = {100.0*n/len(elig):.1f}%   (denominator: ships observed >=1.0 y)')

print('\n== ships with >=3 identity periods starting inside any 365-day window')
hits = []
for r in have:
    fs = [ts(x['transmissionDateFrom']) for x in r['sr']]
    best = 0
    for i, f in enumerate(fs):
        c = sum(1 for g in fs if f <= g < f + dt.timedelta(days=365))
        best = max(best, c)
    r['maxperyear'] = best
    if best >= 3:
        hits.append(r)
print(f'    {len(hits)}/{len(have)} = {100.0*len(hits)/len(have):.1f}%   (max periods starting in a 365-day window >=3)')
print('    distribution of max periods/year:', dict(sorted(collections.Counter(r['maxperyear'] for r in have).items())))

# ---------- registry coverage ----------
print('\n== registry side')
nomatch = [r for r in have if not r['rg']]
print(f'    ships with no registry record at all: {len(nomatch)}/{len(have)} = {100.0*len(nomatch)/len(have):.1f}%')
srcc = collections.Counter(tuple(g.get('sourceCode') or []) for r in have for g in r['ship']['rg'])
print('    registry sourceCode:', dict(srcc))
latest = [r for r in have if any(g.get('latestVesselInfo') for g in r['ship']['rg'])]
print(f'    ships with a current (latestVesselInfo) registry record: {len(latest)}/{len(have)}')
print('    registry records per ship:', dict(sorted(collections.Counter(len({g.get("id") for g in r["ship"]["rg"] if g.get("id")}) for r in have).items())))
# registry name vs AIS name disagreement
dis = [r for r in have if r['rg_names'] and r['names'] and not (r['rg_names'] & r['names'])]
print(f'    ships where registry name set and AIS name set never intersect: {len(dis)}/{len(have)} = {100.0*len(dis)/len(have):.1f}%')

# ---------- artefacts ----------
print('\n== artefact checks')
to_dates = collections.Counter(str(x.get('transmissionDateTo'))[:10] for r in have for x in r['sr'])
print('    most common transmissionDateTo (10):', to_dates.most_common(5))
dup = sum(1 for r in have if any(v > 1 for v in
         collections.Counter((x.get('ssvid'), x.get('shipname'), x.get('flag')) for x in r['sr']).values()))
print(f'    ships with the same (mmsi,name,flag) appearing in >1 period: {dup}/{len(have)}')
samemmsi = [r for r in have if any(len({x.get('shipname') for x in r['sr'] if x.get('ssvid') == m}) > 1 for m in r['mmsis'])]
print(f'    ships where one MMSI carries >1 name: {len(samemsi)}/{len(have)} = {100.0*len(samemsi)/len(have):.1f}%')

# ---------- examples ----------
print('\n== neutral data examples (periods, most recent first)')
ex = sorted(have, key=lambda r: -len(r['sr']))[:6]
for r in ex:
    print(f"  IMO {r['ship']['imo']} {r['ship']['group']}/{r['ship']['region']} periods={len(r['sr'])}")
    for x in reversed(r['sr']):
        print(f"     {x.get('ssvid')} {x.get('shipname')!r} {x.get('flag')} {x.get('callsign')} "
              f"{str(x.get('transmissionDateFrom'))[:10]} -> {str(x.get('transmissionDateTo'))[:10]}")
    if r['owners']:
        print('     owners:', sorted(r['owners'])[:5])
