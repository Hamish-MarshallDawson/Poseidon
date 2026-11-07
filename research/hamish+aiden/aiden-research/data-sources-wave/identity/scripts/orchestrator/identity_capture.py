"""Throwaway: raw worldwide AISStream capture for the identity wave. Never prints the key."""
import asyncio, json, os, random, sys, time
import websockets

DUR, OUT = int(sys.argv[1]), sys.argv[2]
KEY = [l.split('=', 1)[1].strip() for l in open(os.path.expanduser('~/.config/hedged-bets/wave.env')) if l.startswith('AISSTREAM_API_KEY=')][0]
SUB = json.dumps({'APIKey': KEY, 'BoundingBoxes': [[[-90, -180], [90, 180]]],
                  'FilterMessageTypes': ['ShipStaticData', 'StaticDataReport', 'PositionReport', 'StandardClassBPositionReport']})


async def main():
    t0, n, back = time.time(), 0, 2
    with open(OUT, 'a', buffering=1) as f:
        while time.time() - t0 < DUR:
            try:
                async with websockets.connect('wss://stream.aisstream.io/v0/stream', compression='deflate', max_size=None, open_timeout=20) as ws:
                    await ws.send(SUB); back = 2
                    while time.time() - t0 < DUR:
                        m = await asyncio.wait_for(ws.recv(), 60)
                        f.write(json.dumps({'recv': time.time(), 'msg': json.loads(m)}) + '\n'); n += 1
            except Exception as e:
                print('reconnect', type(e).__name__, str(e)[:100].replace(KEY, '***'), flush=True)
                await asyncio.sleep(back + random.random()); back = min(back * 2, 120)
    print('done', n, round(time.time() - t0), flush=True)

asyncio.run(main())
