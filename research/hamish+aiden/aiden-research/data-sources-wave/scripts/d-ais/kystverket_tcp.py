import socket, time, collections, sys
HOST, PORT, DUR = "153.44.253.27", 5631, 60
s = socket.create_connection((HOST, PORT), timeout=10)
s.settimeout(2)
t0 = time.time()
buf = b""; nmea = []; types = collections.Counter(); talkers = collections.Counter()
while time.time() - t0 < DUR:
    try: chunk = s.recv(65536)
    except socket.timeout: continue
    if not chunk: break
    buf += chunk
    while b"\n" in buf:
        line, buf = buf.split(b"\n", 1)
        line = line.strip().decode("ascii", "ignore")
        if not line.startswith("!"): continue
        nmea.append((time.time()-t0, line))
        parts = line.split(",")
        types[parts[0]] += 1
        if len(line) > 10: talkers[line[3:6]] += 1
el = time.time()-t0
print(f"duration {el:.1f}s lines {len(nmea)} rate {len(nmea)/el:.1f}/s")
print("sentence types", dict(types))
print("talkers", dict(talkers))
print("first 3:", [l for _, l in nmea[:3]])
print("last:", nmea[-1][1] if nmea else None)
# distinct MMSI in the stream
mmsis = set()
for _, l in nmea:
    p = l.split(",")
    if p[0].endswith("VDM") or p[0].endswith("VDO"):
        # payload decode not attempted here; count fragments
        pass
print("samples/s of VDM payloads:", sum(1 for _,l in nmea if 'VDM' in l)/el)
s.close()
