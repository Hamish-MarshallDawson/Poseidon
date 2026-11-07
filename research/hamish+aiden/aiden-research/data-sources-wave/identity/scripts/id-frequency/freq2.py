"""id-frequency v2: identity-change frequency from GFW public-global-vessel-identity samples.

Fixes v1's duplication artefact: GFW returns several identity groups per IMO (matched and
NO_MATCH), each repeating part of the same SSVID history. We merge identical
(ssvid,name,flag,callsign) records across groups and analyse SSVID windows instead.
"""
import json, sys, collections, statistics, datetime as dt

PATH = sys.argv[1] if len(sys.argv) > 1 else '/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave/data/identity/gfw-identities.jsonl'


def ts(s):
    s = s.replace('Z', '').replace('+00:00', '')
    if '.' in s:
        s = s[:26]
    else:
        s = s[:19]
    return dt.datetime.fromisoformat(s).replace(tzinfo=None)


def yrs(a, b):
    return (b - a).total_seconds() / 86400 / 365.25


recs = [json.loads(l) for l in open(PATH) if 'entries' in l]
print(f'== records read: {len(recs)}  by group/region: {dict(collections.Counter((r["group"], r["region"]) for r in recs))}')

ships = []
for r in recs:
    raw = []
    owners = set()
    reg = []
    for e in r['entries']:
        raw += [x for x in (e.get('selfReportedInfo') or []) if x.get('transmissionDateFrom')]
        reg += e.get('registryInfo') or []
        owners |= {o.get('name') for o in (e.get('registryOwners') or []) if o.get('name')}
    # merge duplicates across groups: key = ssvid+name+flag+callsign -> min from, max to
    m = {}
    for x in raw:
        k = (x.get('ssvid'), x.get('shipname'), x.get('flag'), x.get('callsign'))
        a, b = ts(x['transmissionDateFrom']), ts(x.get('transmissionDateTo') or x['transmissionDateFrom'])
        if k in m:
            m[k] = (min(m[k][0], a), max(m[k][1], b))
        else:
            m[k] = (a, b)
    # per ssvid window and within-ssvid variants
    bys = collections.defaultdict(list)
    for k, (a, b) in m.items():
        bys[k[0]].append(dict(name=k[1], flag=k[2], call=k[3], a=a, b=b))
    for v in bys.values():
        v.sort(key=lambda x: x['a'])
    start = min(ts(y['transmissionDateFrom']) for y in raw)
    end = max(ts(y.get('transmissionDateTo') or y['transmissionDateFrom']) for y in raw)
    ships.append(dict(imo=r['imo'], group=r['group'], region=r['region'], total=r.get('total'),
                      n_groups=len(r['entries']), raw=raw, bys=bys, reg=reg, owners=owners,
                      start=start, end=end, span=yrs(start, end), n_records=len(m)))

N = len(ships)
print(f'ships: {N}  by group: {dict(collections.Counter(s["group"] for s in ships))}')
print(f'observed ship-years (sum of first->last span): {sum(s["span"] for s in ships):.0f}'
      f'  median span {statistics.median([s["span"] for s in ships]):.1f} y')
print('periods per ship (after merge):', dict(sorted(collections.Counter(s['n_records'] for s in ships).items())))
print('distinct SSVIDs per ship:', dict(sorted(collections.Counter(len(s['bys']) for s in ships).items())))
print('ships with >1 identity group returned by GFW:', sum(1 for s in ships if s['n_groups'] > 1), '/', N)

# ---- MMSI-level transitions ----
mmsi_tr = []   # (gap_h, prev_ssvid, next_ssvid, ship)
within_tr = []  # (kind, ship) field changes inside one SSVID
for s in ships:
    order = sorted(s['bys'].items(), key=lambda kv: min(v['a'] for v in kv[1]))
    for i in range(1, len(order)):
        p_ss, p_v = order[i - 1]
        n_ss, n_v = order[i]
        gap = (min(v['a'] for v in n_v) - max(v['b'] for v in p_v)).total_seconds() / 3600
        mmsi_tr.append((gap, p_ss, n_ss, s))
    for ss, vs in s['bys'].items():
        for i in range(1, len(vs)):
            for f, lab in ((('name',), 'name'), (('flag',), 'flag'), (('call',), 'call')):
                if vs[i][f[0]] != vs[i - 1][f[0]]:
                    within_tr.append((lab, s))

T = len(mmsi_tr)
print(f'\n== MMSI transitions (one SSVID to the next): {T}')
print('gap distribution (next start - prev end):')
b = collections.Counter()
for g, _, _, _ in mmsi_tr:
    if g <= -1:
        b['overlap (>-1h, incl. -1..-1)'] += 1
    elif g < 1:
        b['<=1 h'] += 1
    elif g < 24:
        b['1-24 h'] += 1
    elif g < 24 * 30:
        b['1-30 d'] += 1
    elif g < 24 * 365:
        b['30-365 d'] += 1
    else:
        b['>365 d'] += 1
for k in ['overlap (>-1h, incl. -1..-1)', '<=1 h', '1-24 h', '1-30 d', '30-365 d', '>365 d']:
    print(f'   {k:32s} {b[k]:4d}  {100*b[k]/T:4.1f}%')
print('  share of MMSI transitions within 31 days (i.e. likely within one month):',
      f'{100*(b["<=1 h"]+b["1-24 h"]+b["1-30 d"])/T:.0f}%')
mid = collections.Counter()
for g, p, n, s in mmsi_tr:
    p, n = str(p), str(n)
    if len(p) == 9 and len(n) == 9:
        mid['same MID' if p[:3] == n[:3] else 'different MID'] += 1
    else:
        mid['invalid-length SSVID on one side'] += 1
print('  MMSI transition by MID:', dict(mid))

# name/flag change at transitions
pats = collections.Counter()
for g, p, n, s in mmsi_tr:
    pv = s['bys'][p][-1]
    nv = s['bys'][n][0]
    pat = ''.join(c for c, f in (('M', None), ('N', 'name'), ('F', 'flag'), ('C', 'call'))
                  if f is None or pv[f] != nv[f])
    pats[pat] += 1
print('  field pattern at MMSI transitions:', dict(pats.most_common()))
print('\n== within-SSVID field changes (same MMSI, new value):', len(within_tr))
print('  by field:', dict(collections.Counter(k for k, _ in within_tr)))
print('  example within-MMSI name variants:')
shown = 0
for ss, vs, s in ((ss, vs, s) for s in ships for ss, vs in s['bys'].items()):
    names = [v['name'] for v in vs]
    if len(set(names)) > 1 and shown < 8:
        print(f'   IMO {s["imo"]} {s["group"]:13s} {ss}: ' +
              ' -> '.join(f'{v["name"]!r} ({v["a"].date()})' for v in vs))
        shown += 1

# ---- rates ----
shipyears = sum(s['span'] for s in ships)
print(f'\n== pooled rates over {shipyears:.0f} ship-years')
def rate(n):
    return f'{n/shipyears:.3f}'
print(f'  MMSI transitions {len(mmsi_tr)} ({rate(len(mmsi_tr))}/ship-year)')
nm = sum(1 for g, p, n, s in mmsi_tr if s['bys'][p][-1]['name'] != s['bys'][n][0]['name'])
print(f'  name changes {nm + sum(1 for k, _ in within_tr if k=="name")} ({rate(nm + sum(1 for k,_ in within_tr if k=="name"))})'
      f'  [at MMSI switch {nm}, within MMSI {sum(1 for k,_ in within_tr if k=="name")}]')
fl = sum(1 for g, p, n, s in mmsi_tr if s['bys'][p][-1]['flag'] != s['bys'][n][0]['flag'])
print(f'  flag changes {fl + sum(1 for k,_ in within_tr if k=="flag")} ({rate(fl + sum(1 for k,_ in within_tr if k=="flag"))})'
      f'  [at switch {fl}, within MMSI {sum(1 for k,_ in within_tr if k=="flag")}]')
cl = sum(1 for g, p, n, s in mmsi_tr if s['bys'][p][-1]['call'] != s['bys'][n][0]['call'])
print(f'  call-sign changes {cl + sum(1 for k,_ in within_tr if k=="call")} ({rate(cl + sum(1 for k,_ in within_tr if k=="call"))})')

print('\n== per ship-year by group (MMSI / name / flag)')
for grp in ('random_tanker', 'random_cargo', 'silent_tanker'):
    rs = [s for s in ships if s['group'] == grp]
    if not rs:
        continue
    sy = sum(s['span'] for s in rs)
    mm = sum(1 for g, p, n, s in mmsi_tr if s['group'] == grp)
    nn = sum(1 for g, p, n, s in mmsi_tr if s['group'] == grp and s['bys'][p][-1]['name'] != s['bys'][n][0]['name'])
    ff = sum(1 for g, p, n, s in mmsi_tr if s['group'] == grp and s['bys'][p][-1]['flag'] != s['bys'][n][0]['flag'])
    print(f'  {grp:14s} n={len(rs):3d} sy={sy:6.0f}  MMSI {mm/sy:.3f}  name {nn/sy:.3f}  flag {ff/sy:.3f}')

print('\n== per ship-year by region')
for reg in sorted({s['region'] for s in ships}):
    rs = [s for s in ships if s['region'] == reg]
    sy = sum(s['span'] for s in rs)
    mm = sum(1 for g, p, n, s in mmsi_tr if s['region'] == reg)
    nn = sum(1 for g, p, n, s in mmsi_tr if s['region'] == reg and s['bys'][p][-1]['name'] != s['bys'][n][0]['name'])
    ff = sum(1 for g, p, n, s in mmsi_tr if s['region'] == reg and s['bys'][p][-1]['flag'] != s['bys'][n][0]['flag'])
    print(f'  {reg:9s} n={len(rs):3d} sy={sy:6.0f}  MMSI {mm/sy:.3f}  name {nn/sy:.3f}  flag {ff/sy:.3f}')

print('\n== per calendar year of observation (ship-years from overlapping spans; events by start date)')
sy = collections.Counter()
for s in ships:
    y = s['start'].year
    while y <= s['end'].year:
        a = max(s['start'], dt.datetime(y, 1, 1))
        bb = min(s['end'], dt.datetime(y + 1, 1, 1))
        if bb > a:
            sy[y] += yrs(a, bb)
        y += 1
ev = collections.defaultdict(collections.Counter)
for g, p, n, s in mmsi_tr:
    y = min(v['a'] for v in s['bys'][n]).year
    ev[y]['mmsi'] += 1
    if s['bys'][p][-1]['name'] != s['bys'][n][0]['name']:
        ev[y]['name'] += 1
    if s['bys'][p][-1]['flag'] != s['bys'][n][0]['flag']:
        ev[y]['flag'] += 1
for y in sorted(sy):
    if sy[y] < 15:
        continue
    e = ev[y]
    print(f'  {y}  sy={sy[y]:5.0f}  MMSI {e["mmsi"]:3d} ({e["mmsi"]/sy[y]:.2f})  name {e["name"]:3d} ({e["name"]/sy[y]:.2f})  flag {e["flag"]:3d} ({e["flag"]/sy[y]:.2f})')

# ---- windows ----
print('\n== change inside a window at the end of each ship\'s own observed span')
elig = [s for s in ships if s['span'] >= 1.0]
for days, lab in ((30, '1 month'), (90, '3 months'), (365, '12 months')):
    n = 0
    for s in ships:
        if s['span'] < 1:
            continue
        cut = s['end'] - dt.timedelta(days=days)
        if any(min(v['a'] for v in vs) >= cut and i > 0
               for i, (ss, vs) in enumerate(sorted(s['bys'].items(), key=lambda kv: min(v['a'] for v in kv[1])))):
            n += 1
    print(f'   {lab:9s} {n:3d}/{len(elig)} = {100*n/len(elig):.1f}%   (denominator: ships with span>=1y)')
print('\n== ships with >=3 SSVIDs starting inside one 365-day window')
cnt = 0
mx = collections.Counter()
for s in ships:
    fs = sorted(min(v['a'] for v in vs) for vs in s['bys'].values())
    best = max((sum(1 for g in fs if f <= g < f + dt.timedelta(days=365)) for f in fs), default=0)
    mx[best] += 1
    if best >= 3:
        cnt += 1
print(f'   {cnt}/{N} = {100*cnt/N:.1f}%   distribution of max SSVID starts per 365d:', dict(sorted(mx.items())))

# ---- identity-period durations and flag direction ----
durs = []
for s in ships:
    for ss, vs in s['bys'].items():
        durs.append((max(v['b'] for v in vs) - min(v['a'] for v in vs)).total_seconds() / 86400)
durs.sort()
print(f'\n== SSVID lifetime (days): n={len(durs)} median {statistics.median(durs):.0f}'
      f'  p10 {durs[len(durs)//10]:.0f}  p90 {durs[len(durs)*9//10]:.0f}  max {durs[-1]:.0f}')
print(f'   share of SSVID lifetimes <30 d: {100*sum(1 for d in durs if d<30)/len(durs):.1f}%'
      f'  <1 y: {100*sum(1 for d in durs if d<365)/len(durs):.1f}%')
ft = collections.Counter()
for g, p, n, s in mmsi_tr:
    a, bb = s['bys'][p][-1]['flag'], s['bys'][n][0]['flag']
    if a != bb:
        ft[(a, bb)] += 1
print('\n== top flag transitions at MMSI switches:', ft.most_common(12))
print('   flags seen as a destination:', collections.Counter(k[1] for k in ft.elements()).most_common(10))

# ---- registry side ----
print('\n== registry records')
print('   ships with no registry record:', sum(1 for s in ships if not s['reg']), '/', N)
print('   registry sourceCode:', dict(collections.Counter(tuple(g.get('sourceCode') or []) for s in ships for g in s['reg'])))
print('   registry records per ship (by id):',
      dict(sorted(collections.Counter(len({g.get('id') for g in s['reg'] if g.get('id')}) for s in ships).items())))
print('   ships with latestVesselInfo record:', sum(1 for s in ships if any(g.get('latestVesselInfo') for g in s['reg'])))
regnames = {s['imo']: {g.get('shipname') for g in s['reg'] if g.get('shipname')} for s in ships}
disj = [s for s in ships if s['reg'] and regnames[s['imo']] and not (regnames[s['imo']] & {v['name'] for vs in s['bys'].values() for v in vs})]
print(f'   registry names never equal any AIS name: {len(disj)}/{sum(1 for s in ships if s["reg"])} of registry-matched ships')
print('   ships with owner records:', sum(1 for s in ships if s['owners']))
print('   registry records per ship with TMT source:', sum(1 for s in ships if any('TMT' in (g.get('sourceCode') or []) for g in s['reg'])))

# ---- validity of SSVID ----
allss = {str(ss) for s in ships for ss in s['bys']}
bad = [x for x in allss if not (len(x) == 9 and x.isdigit())]
print(f'\n== SSVID validity: {len(allss)} distinct MMSIs, not 9 digits: {len(bad)} -> {bad[:12]}')
print('   ships whose MMSI prefix is 0 or 1:', sorted({x for x in allss if x[0] in '01'})[:10])

# ---- examples ----
print('\n== neutral data examples, ships with most SSVIDs')
for s in sorted(ships, key=lambda s: -len(s['bys']))[:5]:
    print(f"  IMO {s['imo']} {s['group']}/{s['region']} span {s['start'].date()}..{s['end'].date()}")
    for ss, vs in sorted(s['bys'].items(), key=lambda kv: min(v['a'] for v in kv[1])):
        print(f"    {ss} " + ' | '.join(f"{v['name']!r} {v['flag']} {v['call']} {v['a'].date()}->{v['b'].date()}" for v in vs))
    if s['owners']:
        print('    owners in registry:', sorted(s['owners'])[:4])
