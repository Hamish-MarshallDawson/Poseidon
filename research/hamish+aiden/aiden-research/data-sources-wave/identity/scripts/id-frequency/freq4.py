"""id-frequency v4: final. Chained identity timeline (handles SSVID reuse), all headline numbers.

Method
  * read gfw-identities.jsonl (one record per sampled IMO)
  * merge duplicate periods across GFW identity groups: key (ssvid,name,flag,callsign,nname)
  * order merged periods by start; the predecessor of a new period is the period with the
    latest end among those already started (the identity that was "current" at that moment)
  * transition gap = new.start - prev.end  (negative = the two MMSIs were on air together)
"""
import json, sys, collections, statistics, math, datetime as dt

PATH = sys.argv[1] if len(sys.argv) > 1 else '/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave/data/identity/gfw-identities.jsonl'


def ts(s):
    s = s.replace('Z', '').replace('+00:00', '')
    return dt.datetime.fromisoformat(s[:26] if '.' in s else s[:19]).replace(tzinfo=None)


Y = 86400 * 365.25
recs = [json.loads(l) for l in open(PATH) if 'entries' in l]

ships = []
for r in recs:
    per, reg, owners = {}, [], set()
    for e in r['entries']:
        for x in (e.get('selfReportedInfo') or []):
            if not x.get('transmissionDateFrom'):
                continue
            k = (x.get('ssvid'), x.get('shipname'), x.get('flag'), x.get('callsign'), x.get('nShipname'))
            a = ts(x['transmissionDateFrom'])
            b = ts(x.get('transmissionDateTo') or x['transmissionDateFrom'])
            per[k] = [min(per[k][0], a), max(per[k][1], b)] if k in per else [a, b]
        reg += e.get('registryInfo') or []
        owners |= {o.get('name') for o in (e.get('registryOwners') or []) if o.get('name')}
    periods = [dict(ssvid=k[0], name=k[1], flag=k[2], call=k[3], nname=k[4], a=v[0], b=v[1]) for k, v in per.items()]
    periods.sort(key=lambda p: (p['a'], p['b']))
    start = min(p['a'] for p in periods)
    end = max(p['b'] for p in periods)
    ships.append(dict(imo=r['imo'], group=r['group'], region=r['region'], periods=periods,
                      reg=reg, owners=owners, n_groups=len(r['entries']), total=r.get('total'),
                      start=start, end=end, span=(end - start).total_seconds() / Y))

N = len(ships)
SY = sum(s['span'] for s in ships)
SD = SY * 365.25
print('== sample %d IMO records, %.0f ship-years, %d AIS identity periods' % (N, SY, sum(len(s['periods']) for s in ships)))
print('   groups:', dict(collections.Counter(s['group'] for s in ships)))
print('   regions:', dict(collections.Counter(s['region'] for s in ships)))
print('   records with >1 GFW identity group:', sum(1 for s in ships if s['n_groups'] > 1))
print('   median span %.1f y, span p10 %.1f p90 %.1f' % (
    statistics.median([s['span'] for s in ships]),
    sorted(s['span'] for s in ships)[N // 10], sorted(s['span'] for s in ships)[9 * N // 10]))
print('   periods per ship:', dict(sorted(collections.Counter(len(s['periods']) for s in ships).items())))

# ---------- chained transitions ----------
trs = []
for s in ships:
    taken = []
    for p in s['periods']:
        prev = None
        for q in taken:
            if q['a'] <= p['a'] and (prev is None or q['b'] > prev['b']):
                prev = q
        if prev is not None:
            trs.append(dict(prev=prev, new=p, ship=s,
                            gap=(p['a'] - prev['b']).total_seconds() / 3600))
        taken.append(p)
T = len(trs)
print('\n== chained transitions: %d (%.3f per ship-year)' % (T, T / SY))
b = collections.Counter()
for t in trs:
    g = t['gap']
    k = ('on air together (>1h overlap)' if g <= -1 else '<=1 h' if g < 1 else '1-24 h' if g < 24
         else '1-30 d' if g < 720 else '30-365 d' if g < 8760 else '>365 d')
    b[k] += 1
for k in ('<=1 h', 'on air together (>1h overlap)', '1-24 h', '1-30 d', '30-365 d', '>365 d'):
    print('   %-32s %4d %5.1f%%' % (k, b[k], 100 * b[k] / T))
print('   within 24 h: %.0f%%   within 31 d: %.0f%%' % (
    100 * (b['<=1 h'] + b['1-24 h'] + b['on air together (>1h overlap)']) / T,
    100 * (T - b['30-365 d'] - b['>365 d']) / T))
gaps = sorted(t['gap'] for t in trs if t['gap'] >= 0)
print('   positive gaps: p50 %.1f h  p90 %.1f h' % (statistics.median(gaps), gaps[int(.9 * len(gaps))]))

print('\n== field pattern at each transition')
pat = collections.Counter()
for t in trs:
    pat[''.join(c for c, f in (('M', None), ('N', 'name'), ('F', 'flag'), ('C', 'call'))
                if f is None or t['prev'][f] != t['new'][f])] += 1
for k, v in pat.most_common():
    print('   %-5s %4d %5.1f%%' % (k, v, 100 * v / T))
lbl = {'MNFC': 'MMSI+name+flag+call', 'MFC': 'MMSI+flag+call, name kept',
       'M': 'MMSI only', 'MN': 'MMSI+name', 'MF': 'MMSI+flag', 'MC': 'MMSI+call',
       'MNC': 'MMSI+name+call', 'N': 'name only', '-': 'none'}
print('   legend:', lbl)

mid = collections.Counter()
for t in trs:
    a, c = str(t['prev']['ssvid']), str(t['new']['ssvid'])
    if len(a) == 9 and len(c) == 9:
        mid['same country (same MID)' if a[:3] == c[:3] else 'different country'] += 1
    else:
        mid['invalid SSVID length'] += 1
print('   MMSI switch type:', dict(mid))
print('   flag changed / MMSI changed: %d/%d' % (sum(1 for t in trs if t['prev']['flag'] != t['new']['flag']), T))
print('   MMSI changed but flag same: %d; flag changed but MMSI same: %d' % (
    sum(1 for t in trs if t['prev']['flag'] == t['new']['flag']),
    sum(1 for t in trs if t['prev']['flag'] != t['new']['flag'] and t['prev']['ssvid'] == t['new']['ssvid'])))

print('\n== per ship-year by group')
for grp in ('random_tanker', 'random_cargo', 'silent_tanker'):
    rs = [s for s in ships if s['group'] == grp]
    sy = sum(s['span'] for s in rs)
    ts_ = [t for t in trs if t['ship']['group'] == grp]
    nm = sum(1 for t in ts_ if t['prev']['name'] != t['new']['name'])
    fl = sum(1 for t in ts_ if t['prev']['flag'] != t['new']['flag'])
    print('   %-14s n=%3d sy=%5.0f  MMSI %.3f  name %.3f  flag %.3f  MMSIs/ship %.2f' % (
        grp, len(rs), sy, len(ts_) / sy, nm / sy, fl / sy, statistics.mean(len(s['periods']) for s in rs)))

print('\n== per ship-year by region')
for reg in sorted({s['region'] for s in ships}):
    rs = [s for s in ships if s['region'] == reg]
    sy = sum(s['span'] for s in rs)
    ts_ = [t for t in trs if t['ship']['region'] == reg]
    print('   %-9s n=%3d sy=%5.0f  MMSI %.3f  name %.3f  flag %.3f' % (
        reg, len(rs), sy, len(ts_) / sy,
        sum(1 for t in ts_ if t['prev']['name'] != t['new']['name']) / sy,
        sum(1 for t in ts_ if t['prev']['flag'] != t['new']['flag']) / sy))

print('\n== per calendar year (ship-years from overlapping spans; events by new period start)')
syy = collections.Counter()
for s in ships:
    yr = s['start'].year
    while yr <= s['end'].year:
        a = max(s['start'], dt.datetime(yr, 1, 1))
        z = min(s['end'], dt.datetime(yr + 1, 1, 1))
        if z > a:
            syy[yr] += (z - a).total_seconds() / Y
        yr += 1
ev = collections.defaultdict(collections.Counter)
for t in trs:
    y = t['new']['a'].year
    ev[y]['mmsi'] += 1
    ev[y]['name'] += t['prev']['name'] != t['new']['name']
    ev[y]['flag'] += t['prev']['flag'] != t['new']['flag']
for y in sorted(syy):
    if syy[y] < 20:
        continue
    print('   %d sy=%5.0f  MMSI %3d (%.2f)  name %3d (%.2f)  flag %3d (%.2f)' % (
        y, syy[y], ev[y]['mmsi'], ev[y]['mmsi'] / syy[y], ev[y]['name'], ev[y]['name'] / syy[y],
        ev[y]['flag'], ev[y]['flag'] / syy[y]))

print('\n== distribution of days between one ship\'s consecutive switches')
for s in sorted(ships, key=lambda s: -len(s['periods']))[:3]:
    print('   IMO %s %s %d periods' % (s['imo'], s['group'], len(s['periods'])))

print('\n== windows at the end of each ship\'s own span (denominator: span >= 1 y)')
elig = [s for s in ships if s['span'] >= 1]
for days, lab in ((30, '1 month'), (90, '3 months'), (365, '12 months')):
    n = 0
    for s in elig:
        cut = s['end'] - dt.timedelta(days=days)
        ts_ = [t for t in trs if t['ship'] is s and t['new']['a'] >= cut]
        if ts_:
            n += 1
    print('   %-9s %3d/%3d = %4.1f%%' % (lab, n, len(elig), 100 * n / len(elig)))

print('\n== >=3, >=4 switches starting inside one 365-day window')
mx = collections.Counter()
for s in ships:
    fs = sorted(p['a'] for p in s['periods'])
    best = max((sum(1 for g in fs if f <= g < f + dt.timedelta(days=365)) for f in fs), default=0)
    mx[best] += 1
print('   distribution:', dict(sorted(mx.items())))
for k in (2, 3, 4):
    n = sum(v for kk, v in mx.items() if kk >= k)
    lam = T / SY
    pois = 1 - sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(k))
    print('   >=%d starts in a year: %d/%d = %.1f%%   (Poisson(lambda=%.3f) expects %.2f%%)' % (
        k, n, N, 100 * n / N, lam, 100 * pois))

print('\n== concentration')
cnt = sorted(((sum(1 for t in trs if t['ship'] is s), s) for s in ships), key=lambda x: -x[0])
print('   ships with zero switches: %d/%d = %.1f%%' % (sum(1 for c, _ in cnt if c == 0), N,
                                                        100 * sum(1 for c, _ in cnt if c == 0) / N))
k = max(1, N // 10)
print('   top 10%% (%d ships) hold %d/%d = %.0f%% of switches' % (k, sum(c for c, _ in cnt[:k]), T,
                                                                 100 * sum(c for c, _ in cnt[:k]) / T))
print('   most switches on one ship:', cnt[0][0], 'IMO', cnt[0][1]['imo'])

print('\n== silence cross-check (like the earlier 29/40, 31/40, 38/40 test, at IMO level)')
cut = dt.datetime(2026, 8, 1)
sil = [s for s in ships if s['group'] == 'silent_tanker']
reapp = [s for s in sil if any(p['b'] > cut for p in s['periods'])]
print('   silent tankers: %d; have an SSVID transmitting after 2026-08-01: %d (%.0f%%)' % (
    len(sil), len(reapp), 100 * len(reapp) / len(sil)))
print('   ... and that SSVID is not the earliest one: %d' % sum(
    1 for s in reapp if max(s['periods'], key=lambda p: p['b'])['a'] > s['periods'][0]['a']))

print('\n== base rates per ship-day at fleet sizes')
for lab, n in (('MMSI switch', T),
               ('name change', sum(1 for t in trs if t['prev']['name'] != t['new']['name'])),
               ('flag change', sum(1 for t in trs if t['prev']['flag'] != t['new']['flag']))):
    print('   %-12s %4d / %.0f ship-days = %.5f/ship-day -> 100 ships %.2f/day, 1,000 %.2f/day, 5,000 %.2f/day' % (
        lab, n, SD, n / SD, 100 * n / SD, 1000 * n / SD, 5000 * n / SD))

print('\n== identity period lifetimes')
d = sorted((p['b'] - p['a']).total_seconds() / 86400 for s in ships for p in s['periods'])
print('   n=%d median %.0f d p10 %.0f p90 %.0f; <30 d %.1f%%, <1 y %.1f%%' % (
    len(d), statistics.median(d), d[len(d) // 10], d[9 * len(d) // 10],
    100 * sum(1 for x in d if x < 30) / len(d), 100 * sum(1 for x in d if x < 365) / len(d)))
print('   shortest periods:', [round(x, 1) for x in d[:8]])

print('\n== registry side')
print('   ships with no registry record: %d/%d = %.0f%%' % (sum(1 for s in ships if not s['reg']), N,
                                                            100 * sum(1 for s in ships if not s['reg']) / N))
print('   registry records: %d for %d AIS periods; per ship (by id): %s' % (
    sum(len(s['reg']) for s in ships), sum(len(s['periods']) for s in ships),
    dict(sorted(collections.Counter(len({g.get('id') for g in s['reg'] if g.get('id')}) for s in ships).items()))))
print('   sources:', dict(collections.Counter(tuple(g.get('sourceCode') or []) for s in ships for g in s['reg'])))
regn = {s['imo']: {g.get('nShipname') or g.get('shipname') for g in s['reg'] if (g.get('nShipname') or g.get('shipname'))} for s in ships}
aisn = {s['imo']: {p['nname'] for p in s['periods'] if p['nname']} for s in ships}
mat = [s for s in ships if regn[s['imo']]]
print('   registry-matched ships: %d; registry name set never matches any AIS name: %d' % (
    len(mat), sum(1 for s in mat if not (regn[s['imo']] & aisn[s['imo']]))))
print('   ships with owner records:', sum(1 for s in ships if s['owners']))

print('\n== SSVID validity')
alls = {str(p['ssvid']) for s in ships for p in s['periods']}
bad = sorted(x for x in alls if not (len(x) == 9 and x.isdigit()))
print('   distinct SSVIDs %d; not 9 digits: %d %s' % (len(alls), len(bad), bad))

print('\n== flag destinations at switches')
print('  ', collections.Counter(t['new']['flag'] for t in trs if t['prev']['flag'] != t['new']['flag']).most_common(12))

print('\n== worked examples (neutral data)')
for imo in ('9610341', '9318034', '9197832', '9421415', '9809601', '9388742'):
    for s in ships:
        if s['imo'] == imo:
            print('   IMO %s %s/%s' % (s['imo'], s['group'], s['region']))
            for p in s['periods']:
                print('      %s %-22r %s %-8s %s -> %s' % (p['ssvid'], p['name'], p['flag'], p['call'],
                                                           p['a'].date(), p['b'].date()))
