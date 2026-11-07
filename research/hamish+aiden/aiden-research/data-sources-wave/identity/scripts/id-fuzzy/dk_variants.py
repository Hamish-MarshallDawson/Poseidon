"""Stream the Danish AIS day file and collect per-MMSI static-field variants.

Reads from a zip on argv[1] (never extracts to a folder we scan), writes JSON to argv[2].
Fields: 0 ts,1 mobile type,2 mmsi,3 lat,4 lon,5 nav,6 rot,7 sog,8 cog,9 hdg,10 imo,
11 callsign,12 name,13 shiptype,14 cargo,15 width,16 length,...,18 destination
"""
import sys, json, zipfile, collections

src, out = sys.argv[1], sys.argv[2]
names = collections.defaultdict(collections.Counter)
imos = collections.defaultdict(collections.Counter)
cs = collections.defaultdict(collections.Counter)
st = collections.defaultdict(collections.Counter)
dim = collections.defaultdict(collections.Counter)
rows = 0
with zipfile.ZipFile(src) as z:
    with z.open(z.namelist()[0]) as fh:
        for i, raw in enumerate(fh):
            if i == 0:
                continue
            try:
                p = raw.decode("utf-8", "replace").rstrip("\n").split(",")
            except Exception:
                continue
            if len(p) < 19:
                continue
            rows += 1
            m = p[2]
            if not m.isdigit():
                continue
            n = p[12].strip()
            if n and n != "Unknown":
                names[m][n] += 1
            im = p[10].strip()
            if im and im != "Unknown":
                imos[m][im] += 1
            c = p[11].strip()
            if c and c != "Unknown":
                cs[m][c] += 1
            s = p[13].strip()
            if s and s != "Undefined":
                st[m][s] += 1
            d = (p[16].strip(), p[15].strip())
            if d[0] or d[1]:
                dim[m][d] += 1

rec = {}
for m in names.keys() | imos.keys():
    rec[m] = {
        "names": names[m].most_common(),
        "imos": imos[m].most_common(),
        "callsigns": cs[m].most_common(),
        "shiptypes": st[m].most_common(),
        "dims": [list(k) + [v] for k, v in dim[m].most_common()],
    }
json.dump({"rows": rows, "vessels": rec}, open(out, "w"))
print("rows", rows, "vessels", len(rec))
