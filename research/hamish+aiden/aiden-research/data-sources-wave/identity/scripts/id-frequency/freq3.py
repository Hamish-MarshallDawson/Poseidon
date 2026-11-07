"""id-frequency v3 supplements: concentration, overlaps, same-MID switches, normalised-name agreement."""
import json, sys, collections, statistics, math, datetime as dt

PATH = sys.argv[1] if len(sys.argv) > 1 else '/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave/data/identity/gfw-identities.jsonl'


def ts(s):
    s = s.replace('Z', '').replace('+00:00', '')
    return dt.datetime.fromisoformat(s[:26] if '.' in s else s[:19]).replace(tzinfo=None)


recs = [json.loads(l) for l in open(PATH) if 'entries' in l]
ships = []
for r in recs:
    raw, reg, owners, groups = [], [], set(), []
    for e in r['entries']:
        g = [x for x in (e.get('selfReportedInfo') or []) if x.get('transmissionDateFrom')]
        raw += g
        groups.append(g)
        reg += e.get('registryInfo') or []
        owners |= {o.get('name') for o in (e.get('registryOwners') or []) if o.get('name')}
    m = {}
    for x in raw:
        k = (x.get('ssvid'), x.get('shipname'), x.get('flag'), x.get('callsign'), x.get('nShipname'))
        a, b = ts(x['transmissionDateFrom']), ts(x.get('transmissionDateTo') or x['transmissionDateFrom'])
        m[k] = (min(m[k][0], a), max(m[k][1], b)) if k in m else (a, b)
    bys = collections.defaultdict(list)
    for k, (a, b) in m.items():
        bys[k[0]].append(dict(name=k[1], nname=k[4], flag=k[2], call=k[3], a=a, b=b))
    for v in bys.values():
        v.sort(key=lambda x: x['a'])
    ships.append(dict(imo=r['imo'], group=r['group'], region=r['region'], bys=bys, reg=reg,
                      owners=owners, groups=groups, raw=raw,
                      start=min(ts(x['transmissionDateFrom']) for x in raw),
                      end=max(ts(x.get('transmissionDateTo') or x['transmissionDateFrom']) for x in raw)))

sy_total = sum((s['end'] - s['start']).total_seconds() / 86400 / 365.25 for s in ships)
print('ships', len(ships), 'ship-years %.0f' % sy_total)

tr = []
for s in ships:
    order = sorted(s['bys'].items(), key=lambda kv: min(v['a'] for v in kv[1]))
    for i in range(1, len(order)):
        (ps, pv), (ns, nv) = order[i - 1], order[i]
        gap = (min(v['a'] for v in nv) - max(v['b'] for v in pv)).total_seconds() / 3600
        tr.append(dict(gap=gap, ps=ps, ns=ns, p=pv[-1], n=nv[0], s=s))
print('MMSI transitions', len(tr))

print('\n== overlap detail (gap <= -1h): n =', sum(1 for t in tr if t['gap'] <= -1))
ov = sorted([t for t in tr if t['gap'] <= -1], key=lambda t: t['gap'])
print('   overlap hours p50 %.1f  p90 %.1f  min %.1f' % (
    statistics.median([-t['gap'] for t in ov]), sorted(-t['gap'] for t in ov)[int(.9 * len(ov))], -ov[0]['gap']))
print('   overlaps <48h:', sum(1 for t in ov if -t['gap'] < 48), ' >30d:', sum(1 for t in ov if -t['gap'] > 720))
for t in ov[:6]:
    print('   IMO %s %s %s %r end %s -> %s %r start %s (%.0fh)' % (
        t['s']['imo'], t['s']['group'], t['ps'], t['p']['name'], t['p']['b'].date(),
        t['ns'], t['n']['name'], t['n']['a'].date(), -t['gap']))

print('\n== same-MID MMSI switches (no country change), n =', sum(1 for t in tr if str(t['ps'])[:3] == str(t['ns'])[:3]))
for t in tr:
    if str(t['ps'])[:3] == str(t['ns'])[:3] and len(str(t['ps'])) == 9:
        print('   IMO %s %s %s %r %s -> %s %r %s  gap %.0fh  name_same=%s' % (
            t['s']['imo'], t['s']['group'], t['ps'], t['p']['name'], t['p']['flag'],
            t['ns'], t['n']['name'], t['n']['flag'], t['gap'], t['p']['name'] == t['n']['name']))

print('\n== concentration of transitions')
per = sorted(((sum(1 for t in tr if t['s'] is s), s) for s in ships), key=lambda x: -x[0])
tot = len(tr)
print('   ships with 0 transitions:', sum(1 for c, _ in per if c == 0), '/', len(ships),
      '=%.1f%%' % (100 * sum(1 for c, _ in per if c == 0) / len(ships)))
k10 = max(1, len(ships) // 10)
print('   top 10%% of ships (%d) hold %d/%d = %.0f%% of transitions' % (k10, sum(c for c, _ in per[:k10]), tot,
                                                                      100 * sum(c for c, _ in per[:k10]) / tot))
lam = tot / sy_total
for k in (2, 3):
    p = 1 - sum(math.exp(-lam) * lam ** i / math.factorial(i) for i in range(k))
    print('   Poisson(lambda=%.3f/ship-year) P(>=%d changes in a year) = %.5f -> expected %.2f ships, observed %d'
          % (lam, k, p, p * len(ships), sum(1 for c, _ in per if c >= k)))
print('   max transitions for one ship:', per[0][0], 'IMO', per[0][1]['imo'], per[0][1]['group'])

print('\n== concurrent identities: earlier SSVID still transmitting after newer one starts')
conc = 0
for s in ships:
    order = sorted(s['bys'].items(), key=lambda kv: min(v['a'] for v in kv[1]))
    if any(min(v['a'] for v in order[i][1]) < max(v['b'] for v in order[i - 1][1]) for i in range(1, len(order))):
        conc += 1
print('   %d/%d ships = %.1f%%' % (conc, len(ships), 100 * conc / len(ships)))

print('\n== per-group SSVID counts')
for grp in ('random_tanker', 'random_cargo', 'silent_tanker'):
    rs = [s for s in ships if s['group'] == grp]
    c = collections.Counter(len(s['bys']) for s in rs)
    print('   %-14s n=%3d  mean %.2f SSVIDs  share with >=2: %.0f%%  >=4: %.0f%%' % (
        grp, len(rs), statistics.mean(len(s['bys']) for s in rs),
        100 * sum(v for k, v in c.items() if k >= 2) / len(rs),
        100 * sum(v for k, v in c.items() if k >= 4) / len(rs)))

print('\n== registry vs AIS names (normalised nShipname)')
ais_n = collections.defaultdict(set)
reg_n = collections.defaultdict(set)
for s in ships:
    for vs in s['bys'].values():
        for v in vs:
            if v['nname']:
                ais_n[s['imo']].add(v['nname'])
    for g in s['reg']:
        if g.get('nShipname') or g.get('shipname'):
            reg_n[s['imo']].add(g.get('nShipname') or g.get('shipname'))
matched = [s for s in ships if reg_n[s['imo']]]
dis = [s for s in matched if not (reg_n[s['imo']] & ais_n[s['imo']])]
print('   ships with registry names: %d; no intersection with AIS names: %d' % (len(matched), len(dis)))
print('   registry sources: %s' % dict(collections.Counter(tuple(g.get('sourceCode') or []) for s in ships for g in s['reg'])))
print('   ships with any TMT-sourced registry record:', sum(1 for s in ships if any(any('TMT' in (c or '') for c in (g.get('sourceCode') or [])) for g in s['reg'])))
print('   registry records total:', sum(len(s['reg']) for s in ships), ' AIS periods total:', sum(len(vs) for s in ships for vs in s['bys'].values()))

print('\n== base rates per ship-day (for flag design)')
sdays = sy_total * 365.25
for lab, n in (('MMSI transition', len(tr)),
               ('name change', sum(1 for t in tr if t['p']['name'] != t['n']['name'])),
               ('flag change', sum(1 for t in tr if t['p']['flag'] != t['n']['flag']))):
    print('   %-16s %4d events / %.0f ship-days = %.5f per ship-day -> at 1,000 ships %.2f/day, at 5,000 ships %.2f/day'
          % (lab, n, sdays, n / sdays, 1000 * n / sdays, 5000 * n / sdays))
print('   per ship-year: MMSI %.3f  name %.3f  flag %.3f' % (
    len(tr) / sy_total,
    sum(1 for t in tr if t['p']['name'] != t['n']['name']) / sy_total,
    sum(1 for t in tr if t['p']['flag'] != t['n']['flag']) / sy_total))

print('\n== last-identity recency (how many ships changed MMSI in the last 12 months of data)')
fresh = dt.datetime(2026, 11, 5)
n = sum(1 for s in ships if any(min(v['a'] for v in vs) > fresh - dt.timedelta(days=365)
                                for vs in list(s['bys'].values())[1:]) and len(s['bys']) > 1)
print('   %d/%d = %.1f%% have a non-first SSVID starting after %s' % (n, len(ships), 100 * n / len(ships), fresh.date() - dt.timedelta(days=365)))
print('\n== silent tankers: last SSVID start and days since')
for s in [s for s in ships if s['group'] == 'silent_tanker'][:12]:
    order = sorted(s['bys'].items(), key=lambda kv: min(v['a'] for v in kv[1]))
    last_ss, last_v = order[-1]
    print('   IMO %s n_ssvid=%d last %s %r %s start %s end %s' % (
        s['imo'], len(order), last_ss, last_v[0]['name'], last_v[0]['flag'],
        str(min(v['a'] for v in last_v))[:10], str(max(v['b'] for v in last_v))[:10]))
