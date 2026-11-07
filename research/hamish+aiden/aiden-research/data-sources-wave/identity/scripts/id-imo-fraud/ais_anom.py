"""Analyse AISStream capture for IMO / MMSI identity anomalies.

python3 -I ais_anom.py <aisstream.jsonl> <out.json> [midlist]
Checks: IMO check digit and range; MMSI MID allocation; one MMSI with several
IMOs/names/callsigns; one IMO on several MMSIs.
"""
import json, sys, collections

src, out_path = sys.argv[1], sys.argv[2]
midlist_path = sys.argv[3] if len(sys.argv) > 3 else None

mids = set()
if midlist_path:
    for line in open(midlist_path):
        line = line.strip()
        if line and line[0] != "#":
            mids.add(line[:3])

def imo_ok(s):
    s = str(s)
    if len(s) != 7 or not s.isdigit():
        return False
    return (7*int(s[0]) + 6*int(s[1]) + 5*int(s[2]) + 4*int(s[3])
            + 3*int(s[4]) + 2*int(s[5])) % 10 == int(s[6])

mmsi_imo = collections.defaultdict(collections.Counter)
mmsi_name = collections.defaultdict(collections.Counter)
mmsi_call = collections.defaultdict(collections.Counter)
mmsi_dims = collections.defaultdict(collections.Counter)
mmsi_type = collections.defaultdict(collections.Counter)
imo_mmsi = collections.defaultdict(collections.Counter)
imo_name = collections.defaultdict(collections.Counter)
all_mmsi = set()
imo_seen = collections.Counter()
imo_bad = collections.Counter()
imo_zero = 0
static_names_ok = 0
times = []

for line in open(src):
    d = json.loads(line)
    m = d.get("msg", {})
    md = m.get("MetaData") or {}
    if md.get("time_utc"):
        times.append(md["time_utc"])
    mt = m.get("MessageType")
    uid = md.get("MMSI") or md.get("MMSI_String")
    msg = m.get("Message") or {}
    if mt == "ShipStaticData":
        s = msg.get("ShipStaticData") or {}
        uid = s.get("UserID", uid)
        name = (s.get("Name") or "").strip()
        imo = s.get("ImoNumber")
        call = (s.get("CallSign") or "").strip()
        dim = (s.get("Dimension") or {})
        st = s.get("Type")
    elif mt == "StaticDataReport":
        s = msg.get("StaticDataReport") or {}
        uid = s.get("UserID", uid)
        ra = s.get("ReportA") or {}
        rb = s.get("ReportB") or {}
        name = (ra.get("Name") or rb.get("Name") or "").strip()
        imo = None
        call = (rb.get("CallSign") or "").strip()
        dim = (rb.get("Dimension") or {})
        st = rb.get("ShipType")
    else:
        continue
    if not uid:
        continue
    uid = str(uid)
    all_mmsi.add(uid)
    if name:
        mmsi_name[uid][name] += 1
        if imo:
            imo_name[str(imo)][name] += 1
    if call:
        mmsi_call[uid][call] += 1
    if dim:
        dd = "%s/%s/%s/%s" % (dim.get("A"), dim.get("B"), dim.get("C"), dim.get("D"))
        if dd != "0/0/0/0" and dd != "None/None/None/None":
            mmsi_dims[uid][dd] += 1
    if st is not None:
        mmsi_type[uid][st] += 1
    if imo:
        imo = int(imo)
        if imo == 0:
            imo_zero += 1
            continue
        s7 = str(imo).zfill(7)
        imo_seen[s7] += 1
        mmsi_imo[uid][s7] += 1
        imo_mmsi[s7][uid] += 1
        if not imo_ok(s7):
            imo_bad[s7] += 1

def multi(dc):
    return {k: dict(v) for k, v in dc.items() if len(v) > 1}

mids_seen = collections.Counter(u[:3] for u in all_mmsi)
unalloc = {k: v for k, v in mids_seen.items() if mids and k not in mids}
bad_len = [u for u in all_mmsi if len(u) != 9]

out = {
    "n_static_msgs": sum(imo_seen.values()) + imo_zero,
    "time_first": times[0] if times else None,
    "time_last": times[-1] if times else None,
    "unique_mmsi": len(all_mmsi),
    "imo_zero": imo_zero,
    "imo_values": len(imo_seen),
    "imo_bad_check": len(imo_bad),
    "imo_bad_check_msgs": sum(imo_bad.values()),
    "imo_bad_check_examples": imo_bad.most_common(25),
    "imo_bad_check_list": sorted(imo_bad),
    "mid_list_loaded": len(mids),
    "unallocated_mid": unalloc,
    "non9digit_mmsi": bad_len[:40],
    "n_non9digit": len(bad_len),
    "mmsi_multi_imo": multi(mmsi_imo),
    "mmsi_multi_name": multi(mmsi_name),
    "mmsi_multi_call": multi(mmsi_call),
    "mmsi_multi_dims": multi(mmsi_dims),
    "mmsi_multi_type": multi(mmsi_type),
    "imo_multi_mmsi": multi(imo_mmsi),
    "imo_multi_name": multi(imo_name),
}
for k in ("mmsi_multi_imo", "mmsi_multi_name", "mmsi_multi_call", "mmsi_multi_dims",
          "mmsi_multi_type", "imo_multi_mmsi", "imo_multi_name"):
    out["n_" + k] = len(out[k])
    out[k] = dict(list(out[k].items())[:50])
with open(out_path, "w") as f:
    json.dump(out, f, indent=1)
print("ok", out["unique_mmsi"], "mmsi;", out["imo_values"], "imo")
