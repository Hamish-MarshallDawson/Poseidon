"""Throwaway measurement of AISStream: one connection, whole world, per-region stats. Never prints the key."""
import asyncio, collections, json, os, random, re, statistics as st, sys, time
from datetime import datetime, timezone
import websockets

DUR = int(sys.argv[1]); OUT = sys.argv[2]
KEY = [l.split('=', 1)[1].strip() for l in open(os.path.expanduser('~/.config/hedged-bets/wave.env')) if l.startswith('AISSTREAM_API_KEY=')][0]
R = {  # lon0, lat0, lon1, lat1
 'Gulf of Finland': (22, 59, 30.5, 61), 'Baltic Proper': (15, 54, 22, 59), 'Danish straits': (9.5, 54, 14, 58), 'North Sea': (-2, 51, 9.5, 60),
 'English Channel': (-5, 49, 2, 51.5), 'Hormuz': (55, 25.5, 57.5, 27), 'Persian Gulf': (48, 24, 55, 30), 'Gulf of Oman': (57.5, 22, 62, 26),
 'Red Sea': (32, 12, 44, 28), 'Malacca-Singapore': (98, 0.5, 105, 7), 'Natuna': (105, 2, 110, 6), 'South China Sea open': (110, 8, 118, 16),
 'Java Sea': (106, -8, 118, -3), 'Gulf of Thailand': (99, 6, 105, 13), 'Philippines': (118, 5, 127, 19), 'East China Sea': (120, 25, 130, 35),
 'Gulf of Guinea': (-5, -2, 10, 7), 'US East': (-80, 25, -65, 42), 'Mid-Atlantic': (-45, 10, -25, 35), 'Indian Ocean mid': (60, -20, 85, 5),
}
S = {k: dict(pos=0, stat=0, mmsi=set(), imo=set(), lag=[], cells=set(), last={}, gaps=[]) for k in R}
W = dict(msgs=0, mmsi=set(), types=collections.Counter(), reconnects=0, lag=[], errors=[], first=None)
q = asyncio.Queue(maxsize=200000); drops = 0; t0 = time.time()
TS = re.compile(r'(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d)(\.\d+)?')


def parse_t(s):
    m = TS.match(s or '')
    if not m: return None
    return datetime.strptime(m.group(1), '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp() + float(m.group(2) or 0)


async def reader():
    global drops
    back = 2
    while time.time() - t0 < DUR:
        try:
            async with websockets.connect('wss://stream.aisstream.io/v0/stream', compression='deflate', max_size=None, open_timeout=20) as ws:
                await ws.send(json.dumps({'APIKey': KEY, 'BoundingBoxes': [[[53.5, 9], [66, 31]]]}))
                back = 2
                while time.time() - t0 < DUR:
                    m = await asyncio.wait_for(ws.recv(), timeout=60)
                    if W['first'] is None: W['first'] = time.time() - t0
                    try: q.put_nowait((time.time(), m))
                    except asyncio.QueueFull: drops += 1
        except Exception as e:
            W['reconnects'] += 1; W['errors'].append(f'{time.time()-t0:.0f}s {type(e).__name__}: {str(e)[:150]}'.replace(KEY, '***'))
            await asyncio.sleep(back + random.random()); back = min(back * 2, 120)


def handle(now, raw):
    d = json.loads(raw); md = d.get('MetaData') or {}; ty = d.get('MessageType', '?')
    W['msgs'] += 1; W['types'][ty] += 1
    mm = md.get('MMSI')
    if mm: W['mmsi'].add(mm)
    lat, lon = md.get('latitude', md.get('Latitude')), md.get('longitude', md.get('Longitude'))
    if lat is None or lon is None: return
    t = parse_t(md.get('time_utc')); lag = now - t if t else None
    if lag is not None and W['msgs'] % 20 == 0: W['lag'].append(lag)
    isstat = ty == 'ShipStaticData'
    for k, (a, b, c, e) in R.items():
        if a <= lon <= c and b <= lat <= e:
            s = S[k]; s['mmsi'].add(mm); s['cells'].add((int(lon * 2), int(lat * 2)))
            if isstat:
                s['stat'] += 1; i = (d.get('Message', {}).get('ShipStaticData') or {}).get('ImoNumber')
                if i: s['imo'].add(i)
            else:
                s['pos'] += 1
                if lag is not None and len(s['lag']) < 50000: s['lag'].append(lag)
                if mm in s['last']: s['gaps'].append(now - s['last'][mm])
                s['last'][mm] = now


async def worker():
    while time.time() - t0 < DUR + 3 or not q.empty():
        try: now, m = await asyncio.wait_for(q.get(), timeout=2)
        except asyncio.TimeoutError: continue
        try: handle(now, m)
        except Exception as e: W['errors'].append('parse ' + str(e)[:100])


def pct(x, p): return round(sorted(x)[int(p * (len(x) - 1))], 1) if x else None


def report():
    el = time.time() - t0
    rows = {}
    for k, s in S.items():
        rows[k] = dict(position_msgs=s['pos'], static_msgs=s['stat'], vessels=len(s['mmsi']), with_imo=len(s['imo']), half_degree_cells=len(s['cells']),
                       msgs_per_s=round(s['pos'] / el, 2), delay_s_p50=pct(s['lag'], .5), delay_s_p90=pct(s['lag'], .9), update_gap_s_p50=pct(s['gaps'], .5), update_gap_s_p90=pct(s['gaps'], .9))
    o = dict(elapsed_s=round(el), first_message_s=W['first'], total_msgs=W['msgs'], msgs_per_s=round(W['msgs'] / el, 1), vessels=len(W['mmsi']), reconnects=W['reconnects'], errors=W['errors'][:10],
             queue_drops=drops, world_delay_p50=pct(W['lag'], .5), world_delay_p90=pct(W['lag'], .9), types=W['types'].most_common(8), regions=rows)
    json.dump(o, open(OUT, 'w'), indent=1)


async def main():
    async def periodic():
        while time.time() - t0 < DUR + 5:
            await asyncio.sleep(min(60, max(1, DUR / 3))); report()
    await asyncio.gather(reader(), worker(), periodic())
    report()

asyncio.run(main())
