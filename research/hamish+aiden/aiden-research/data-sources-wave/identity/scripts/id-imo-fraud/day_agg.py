"""Stream the Danish AIS day file and aggregate identity fields per MMSI / IMO.

Reads the zip directly (no extraction). Writes JSON aggregates to data/id-imo-fraud/.
Run with: python3 -I day_agg.py <zip> <out.json>
"""
import csv, io, json, sys, zipfile, collections

zip_path, out_path = sys.argv[1], sys.argv[2]

def ck(d):
    return (7*int(d[0]) + 6*int(d[1]) + 5*int(d[2]) + 4*int(d[3]) + 3*int(d[4]) + 2*int(d[5])) % 10 == int(d[6])

mmsi_names = collections.defaultdict(collections.Counter)   # mmsi -> name -> msgs
mmsi_imos = collections.defaultdict(collections.Counter)    # mmsi -> imo -> msgs
imo_mmsis = collections.defaultdict(collections.Counter)    # imo -> mmsi -> msgs
mmsi_calls = collections.defaultdict(collections.Counter)
mmsi_dims = collections.defaultdict(collections.Counter)
imo_bad = collections.Counter()
imo_all = collections.Counter()
rows = 0
imo_zero = 0

with zipfile.ZipFile(zip_path) as z:
    name = z.namelist()[0]
    with z.open(name) as fh:
        txt = io.TextIOWrapper(fh, encoding="utf-8", errors="replace")
        rdr = csv.reader(txt)
        header = next(rdr)
        for row in rdr:
            rows += 1
            if len(row) < 17:
                continue
            mmsi, imo, callsign, nm, stype = row[2], row[10], row[11], row[12], row[13]
            dims = (row[15], row[16])
            mmsi = mmsi.strip()
            if mmsi:
                if nm and nm not in ("Unknown", ""):
                    mmsi_names[mmsi][nm] += 1
                if callsign and callsign not in ("Unknown", ""):
                    mmsi_calls[mmsi][callsign] += 1
                if dims[0] and dims[1] and dims[0] != "Undefined":
                    mmsi_dims[mmsi][dims] += 1
                if imo and imo.isdigit() and len(imo) == 7:
                    imo_all[imo] += 1
                    mmsi_imos[mmsi][imo] += 1
                    imo_mmsis[imo][mmsi] += 1
                    if not ck(imo):
                        imo_bad[imo] += 1
                elif imo and imo not in ("Unknown", ""):
                    imo_all["nonstandard:" + imo] += 1
                elif imo == "Unknown" or not imo:
                    imo_zero += 1

multi_name = {m: dict(c) for m, c in mmsi_names.items() if len(c) > 1}
multi_imo = {m: dict(c) for m, c in mmsi_imos.items() if len(c) > 1}
shared_imo = {i: dict(c) for i, c in imo_mmsis.items() if len(c) > 1}
multi_call = {m: dict(c) for m, c in mmsi_calls.items() if len(c) > 1}
multi_dim = {m: dict(c) for m, c in mmsi_dims.items() if len(c) > 1}

out = {
    "rows": rows,
    "unique_mmsi": len(mmsi_names),
    "imo_missing_or_unknown_rows": imo_zero,
    "unique_imo": len([i for i in imo_all if not i.startswith("nonstandard:")]),
    "imo_nonstandard_values": {k: v for k, v in imo_all.items() if k.startswith("nonstandard:")},
    "unique_imo_bad_check": len(imo_bad),
    "imo_bad_check_examples": imo_bad.most_common(20),
    "mmsi_multi_name": len(multi_name),
    "mmsi_multi_imo": len(multi_imo),
    "mmsi_multi_callsign": len(multi_call),
    "mmsi_multi_dims": len(multi_dim),
    "imo_shared_by_mmsi": len(shared_imo),
    "mmsi_multi_name_detail": dict(list(multi_name.items())[:60]),
    "mmsi_multi_imo_detail": dict(list(multi_imo.items())[:40]),
    "imo_shared_detail": dict(list(shared_imo.items())[:60]),
    "mmsi_multi_call_detail": dict(list(multi_call.items())[:30]),
    "imo_bad_check_list": sorted(imo_bad),
}
with open(out_path, "w") as f:
    json.dump(out, f, indent=1)
print("done", rows, len(mmsi_names))
