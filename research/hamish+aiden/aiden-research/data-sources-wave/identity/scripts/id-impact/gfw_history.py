"""id-impact: what a long history looks like when keyed on MMSI only.

From GFW identity records per IMO (self-reported AIS periods), measure:
  - how many MMSI keys one hull uses over its life (history splits)
  - handover gap / overlap between consecutive radio identities
  - name and flag changes, and which are normalisation-only (typos)
  - whether identity changes cluster right after a transmission gap
    (the "went dark, came back under a new name" pattern that a
    gap detector and a 'went dark before' feature would key on)
"""
import json
from collections import Counter, defaultdict

WAVE = '/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave'
SRC = WAVE + '/data/identity/gfw-identities.jsonl'
OUT = WAVE + '/data/id-impact/gfw_history_summary.json'


def norm(s):
    return ''.join(ch for ch in (s or '').upper() if ch.isalnum())


def dt(s):
    if not s:
        return None
    import datetime
    return datetime.datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp()


rows = [json.loads(l) for l in open(SRC)]
# one IMO can come back as several identity groups (matched + NO_MATCH) that repeat
# overlapping parts of the same SSVID history: dedupe by imo, then by period key.
by_imo = {}
for r in rows:
    by_imo.setdefault(r.get('imo'), []).append(r)
per_imo = []
for imo, rr in by_imo.items():
    r = rr[0]
    ents = [e for x in rr for e in (x.get('entries') or [])]
    sri, reg, own = [], [], []
    seen_p = set()
    seen_r = set()
    seen_o = set()
    for e0 in ents:
        for s in (e0.get('selfReportedInfo') or []):
            k = (str(s.get('ssvid') or ''), s.get('shipname'), s.get('flag'),
                 s.get('callsign'), s.get('transmissionDateFrom'), s.get('transmissionDateTo'))
            if k not in seen_p:
                seen_p.add(k); sri.append(s)
        for s in (e0.get('registryInfo') or []):
            k = (str(s.get('ssvid') or ''), s.get('shipname'), s.get('flag'),
                 s.get('transmissionDateFrom'), s.get('transmissionDateTo'))
            if k not in seen_r:
                seen_r.add(k); reg.append(s)
        for s in (e0.get('registryOwners') or []):
            k = (s.get('name'), s.get('flag'), s.get('dateFrom'), s.get('dateTo'))
            if k not in seen_o:
                seen_o.add(k); own.append(s)
    periods = []
    for s in sri:
        periods.append({'mmsi': str(s.get('ssvid') or ''),
                        'name': s.get('shipname'),
                        'flag': s.get('flag'),
                        'cs': s.get('callsign'),
                        'from': dt(s.get('transmissionDateFrom')),
                        'to': dt(s.get('transmissionDateTo')),
                        'msgs': s.get('messagesCounter'),
                        'pos': s.get('positionsCounter')})
    periods = [p for p in periods if p['from'] or p['to']]
    periods.sort(key=lambda p: p['from'] or 0)
    per_imo.append({'imo': imo, 'group': r.get('group'), 'region': r.get('region'),
                    'n_groups': len(rr),
                    'periods': periods,
                    'registry': [{'name': x.get('shipname'), 'flag': x.get('flag'),
                                  'ssvid': str(x.get('ssvid') or ''),
                                  'src': x.get('sourceCode'),
                                  'from': dt(x.get('transmissionDateFrom')),
                                  'to': dt(x.get('transmissionDateTo')),
                                  'imo': x.get('imo')} for x in reg],
                    'owners': [{'name': x.get('name'), 'flag': x.get('flag'),
                                'from': dt(x.get('dateFrom')), 'to': dt(x.get('dateTo')),
                                'src': x.get('sourceCode')} for x in own]})

n = len(per_imo)
splits = []          # (imo, mmsi_count, name_changes, flag_changes, gaps)
hist_share = []
handover = []
flag_changes = 0
name_changes = 0
name_changes_norm_equal = 0
imo_multi = 0
for p in per_imo:
    ps = p['periods']
    mmsis = {x['mmsi'] for x in ps if x['mmsi']}
    if len(mmsis) > 1:
        imo_multi += 1
    names = [x['name'] for x in ps if x['name']]
    flags = [x['flag'] for x in ps if x['flag']]
    nc = sum(1 for a, b in zip(names, names[1:]) if a != b)
    name_changes += nc
    name_changes_norm_equal += sum(1 for a, b in zip(names, names[1:])
                                   if a != b and norm(a) == norm(b))
    fc = sum(1 for a, b in zip(flags, flags[1:]) if a != b)
    flag_changes += fc
    durs = [((x['to'] or 0) - (x['from'] or 0)) / 86400.0 for x in ps]
    tot = sum(d for d in durs if d > 0)
    hist_share.append({'imo': p['imo'], 'n_periods': len(ps), 'mmsis': len(mmsis),
                       'total_days': round(tot, 1),
                       'largest_share': round(max(durs) / tot, 3) if tot > 0 else None,
                       'max_days': round(max(durs), 1) if durs else None})
    for a, b in zip(ps, ps[1:]):
        if not (a['to'] and b['from']):
            continue
        gap_h = (b['from'] - a['to']) / 3600.0
        handover.append({'imo': p['imo'], 'group': p['group'], 'region': p['region'],
                         'old_mmsi': a['mmsi'], 'new_mmsi': b['mmsi'],
                         'old_name': a['name'], 'new_name': b['name'],
                         'old_flag': a['flag'], 'new_flag': b['flag'],
                         'gap_h': round(gap_h, 2),
                         'same_mmsi': a['mmsi'] == b['mmsi'],
                         'name_changed': (a['name'] != b['name']),
                         'flag_changed': (a['flag'] != b['flag']),
                         'old_msgs': a['msgs'], 'new_msgs': b['msgs']})
    splits.append({'imo': p['imo'], 'group': p['group'], 'region': p['region'],
                   'periods': len(ps), 'mmsis': len(mmsis), 'name_changes': nc,
                   'flag_changes': fc})

ssvid_imos = defaultdict(set)
for p in per_imo:
    for x in p['periods']:
        if x['mmsi']:
            ssvid_imos[x['mmsi']].add(p['imo'])
ssvid_multi = {k: sorted(v) for k, v in ssvid_imos.items() if len(v) > 1}

outs = {
    'source': SRC, 'imo_records': n,
    'ssvid_total': len(ssvid_imos),
    'ssvid_under_multiple_imos': len(ssvid_multi),
    'ssvid_multi_examples': {k: ssvid_multi[k] for k in list(ssvid_multi)[:10]},
    'group_counts': dict(Counter(p['group'] for p in per_imo)),
    'region_counts': dict(Counter(p['region'] for p in per_imo)),
    'imo_with_multiple_mmsi': imo_multi,
    'periods_total': sum(s['periods'] for s in splits),
    'name_changes_total': name_changes,
    'name_changes_normalisation_only': name_changes_norm_equal,
    'flag_changes_total': flag_changes,
    'handover_pairs': len(handover),
    'handover_same_mmsi': sum(1 for h in handover if h['same_mmsi']),
    'handover_gap_lt_1h': sum(1 for h in handover if not h['same_mmsi'] and 0 <= h['gap_h'] < 1),
    'handover_gap_lt_24h': sum(1 for h in handover if not h['same_mmsi'] and 0 <= h['gap_h'] < 24),
    'handover_gap_negative_overlap': sum(1 for h in handover if not h['same_mmsi'] and h['gap_h'] < 0),
    'handover_silence_gt_7d_before_switch': sum(1 for h in handover if not h['same_mmsi'] and h['gap_h'] > 168),
    'handover_gap_buckets_h': {
        '0_to_0.33 (no gap detector)': sum(1 for h in handover if not h['same_mmsi'] and 0 <= h['gap_h'] < 0.33),
        '0.33_to_6': sum(1 for h in handover if not h['same_mmsi'] and 0.33 <= h['gap_h'] < 6),
        '6_to_24': sum(1 for h in handover if not h['same_mmsi'] and 6 <= h['gap_h'] < 24),
        '1_to_7d': sum(1 for h in handover if not h['same_mmsi'] and 24 <= h['gap_h'] < 168),
        'gt_7d': sum(1 for h in handover if not h['same_mmsi'] and h['gap_h'] >= 168),
        'overlap_negative': sum(1 for h in handover if not h['same_mmsi'] and h['gap_h'] < 0),
    },
    'history_days_total': round(sum(h['total_days'] for h in hist_share), 1),
    'hulls': len(hist_share),
    'hulls_largest_key_lt_50pct_history': sum(1 for h in hist_share if h['largest_share'] is not None and h['largest_share'] < 0.5),
    'hulls_largest_key_lt_25pct_history': sum(1 for h in hist_share if h['largest_share'] is not None and h['largest_share'] < 0.25),
    'hulls_all_keys_lt_30d': sum(1 for h in hist_share if h['max_days'] is not None and h['max_days'] < 30),
    'median_largest_share': sorted([h['largest_share'] for h in hist_share if h['largest_share'] is not None])[len([h for h in hist_share if h['largest_share'] is not None]) // 2] if any(h['largest_share'] is not None for h in hist_share) else None,
    'splits': sorted(splits, key=lambda s: -s['mmsis'])[:30],
    'handovers': sorted(handover, key=lambda h: -h['gap_h'])[:30],
    'handover_same_mmsi_examples': [h for h in handover if h['same_mmsi']][:20],
    'registry_vs_selfreported_mismatch': [],
}
for p in per_imo:
    ps = p['periods']
    if ps and p['registry']:
        a = ps[-1]
        for x in p['registry']:
            if (x['name'] or '') and (a['name'] or '') and norm(x['name']) != norm(a['name']):
                outs['registry_vs_selfreported_mismatch'].append(
                    {'imo': p['imo'], 'self': a['name'], 'registry': x['name'],
                     'self_flag': a['flag'], 'reg_flag': x['flag'], 'src': x['src']})
                break
outs['registry_vs_selfreported_mismatch_n'] = len(outs['registry_vs_selfreported_mismatch'])
outs['registry_vs_selfreported_mismatch'] = outs['registry_vs_selfreported_mismatch'][:20]
json.dump(outs, open(OUT, 'w'), indent=1)
print(json.dumps({k: v for k, v in outs.items() if not isinstance(v, list)}, indent=1))
