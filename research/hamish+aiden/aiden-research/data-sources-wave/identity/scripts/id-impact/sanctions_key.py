"""id-impact: what MMSI-only keying costs when matching a sanctions list.

Compares the Danish 2026-11-01 fleet against OpenSanctions maritime.csv
(type == VESSEL) keyed by MMSI, by IMO, and by either. Reports matches that a
MMSI-only design cannot see, and check-digit quality of the IMO keys.
"""
import csv, json, re
from collections import defaultdict

WAVE = '/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave'
OS = WAVE + '/data/t-ais-history/os/maritime.csv'
FLEET = WAVE + '/data/t-ais-history/day_2026-11-01/vessels.csv'
OUT = WAVE + '/data/id-impact/sanctions_key_summary.json'


def imo_ok(n):
    s = str(n)
    if not re.fullmatch(r'\d{7}', s):
        return False
    tot = sum(int(c) * (7 - i) for i, c in enumerate(s[:6]))
    return tot % 10 == int(s[6])


os_imo = defaultdict(list)
os_mmsi = defaultdict(list)
n_vessel = 0
bad_imo = 0
with open(OS, newline='') as fh:
    for r in csv.DictReader(fh):
        if (r.get('type') or '') != 'VESSEL':
            continue
        n_vessel += 1
        imo = (r.get('imo') or '').strip()
        imo = re.sub(r'^IMO', '', imo)
        if imo:
            if not imo_ok(imo):
                bad_imo += 1
            os_imo[imo].append(r.get('caption'))
        for m in re.split(r'[;,]', (r.get('mmsi') or '')):
            m = m.strip()
            if re.fullmatch(r'\d{9}', m):
                os_mmsi[m].append(r.get('caption'))

fleet = []
with open(FLEET, newline='') as fh:
    for r in csv.DictReader(fh):
        if (r.get('cls') or '') not in ('Class A', 'Class B'):
            continue
        fleet.append({'mmsi': r['mmsi'], 'imo': (r['imo'] or '').strip(),
                      'name': r.get('name') or ''})

by_mmsi = set()
by_imo = set()
both = set()
for s in fleet:
    a = s['mmsi'] in os_mmsi
    b = bool(s['imo']) and s['imo'] in os_imo
    if a:
        by_mmsi.add(s['mmsi'])
    if b:
        by_imo.add(s['mmsi'])
    if a and b:
        both.add(s['mmsi'])

out = {
    'source_os': OS, 'source_fleet': FLEET,
    'os_vessel_rows': n_vessel,
    'os_vessel_rows_with_bad_imo_checkdigit': bad_imo,
    'fleet_rows': len(fleet),
    'fleet_with_imo': sum(1 for s in fleet if s['imo']),
    'matched_by_mmsi': len(by_mmsi),
    'matched_by_imo': len(by_imo),
    'matched_by_both': len(both),
    'matched_by_either': len(by_mmsi | by_imo),
    'reachable_only_via_imo': len(by_imo - by_mmsi),
    'reachable_only_via_mmsi': len(by_mmsi - by_imo),
    'mmsi_only_recall_vs_either': round(len(by_mmsi & (by_mmsi | by_imo)) / max(1, len(by_mmsi | by_imo)), 3),
}
json.dump(out, open(OUT, 'w'), indent=1)
print(json.dumps(out, indent=1))
