"""Section 2.7 evaluation: merge, match rates, chance control, unmatched radar list."""
import glob, json, math, sys
import numpy as np, pandas as pd, rasterio
import shapely
from rslearn.const import WGS84_PROJECTION
from rslearn.utils.geometry import STGeometry
from rslearn.utils.get_utm_ups_crs import get_utm_ups_projection

W = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave"
RUN = sys.argv[1] if len(sys.argv) > 1 else "big1"
AOI = (12.20, 56.40, 12.95, 57.15)
T = pd.Timestamp("2026-11-01T16:44:39Z")

picks = json.load(open("/tmp/s1picks.json"))["target"]
shp = shapely.geometry.shape(picks["geometry"])
c = shp.centroid
proj = get_utm_ups_projection(c.x, c.y, 10, -10)

summary = json.load(open(f"{W}/data/t-model/summary_{RUN}.json"))
bounds = summary["window_bounds_utm"]
x0, y0, x1, y1 = bounds
det = pd.DataFrame(summary["detections"]).rename(columns={"longitude": "lon", "latitude": "lat"})
det["length"] = det.attributes.apply(lambda a: a["length"])
det["score"] = det.score.astype(float)

ras = glob.glob(f"{W}/data/t-model/scratch/{RUN}/windows/detector_predict/0/layers/sentinel1/vv/*.tif")[0]
ds = rasterio.open(ras)

def to_px(lon, lat):
    g = STGeometry(WGS84_PROJECTION, shapely.Point(lon, lat), None).to_projection(proj)
    return (g.shp.x - x0, y1 - g.shp.y)  # col, row in window pixels (1 unit = 1 px)

def valid(lon, lat, r=3):
    col, row = to_px(lon, lat)
    if not (0 <= col < ds.width and 0 <= row < ds.height):
        return False
    c0, r0 = int(col) - r, int(row) - r
    c0, r0 = max(0, c0), max(0, r0)
    w = ds.read(1, window=rasterio.windows.Window(c0, r0, 2 * r + 1, 2 * r + 1))
    return bool(w.max() > 0)

def hav(lon1, lat1, lon2, lat2):
    lon1, lat1, lon2, lat2 = map(np.asarray, (lon1, lat1, lon2, lat2))
    r = 6371000.0
    p1, p2 = np.radians(lat1), np.radians(lat2)
    dl = np.radians(lon2 - lon1)
    a = np.sin((p2 - p1) / 2) ** 2 + np.cos(p1) * np.cos(p2) * np.sin(dl / 2) ** 2
    return 2 * r * np.arcsin(np.sqrt(a))

def nearest(lon, lat, lons, lats):
    if len(lons) == 0:
        return np.inf, -1
    d = hav(lon, lat, np.asarray(lons), np.asarray(lats))
    i = int(np.argmin(d))
    return float(d[i]), i

# ---- AIS at image time (Class A, Danish archive) ----
df = pd.read_csv(f"{W}/data/t-ais-history/day_2026-11-01/classa_1630_1700Z.csv", parse_dates=["ts_utc"])
tt = T.value // 10**9
rows = []
for mmsi, g in df.sort_values("ts_utc").groupby("mmsi"):
    if len(g) < 2:
        continue
    ts = g["ts_utc"].values.astype("datetime64[s]").astype(np.int64)
    if ts[0] > tt or ts[-1] < tt:
        continue
    lon = float(np.interp(tt, ts, g["lon"].values)); lat = float(np.interp(tt, ts, g["lat"].values))
    if not (AOI[0] <= lon <= AOI[2] and AOI[1] <= lat <= AOI[3]):
        continue
    r = g.iloc[-1]
    rows.append(dict(mmsi=mmsi, lon=lon, lat=lat, sog=float(np.interp(tt, ts, g["sog"].values)),
                     length=r["length"], name=r["name"], vessel_type=r["ship_type"]))
ais = pd.DataFrame(rows)
ais["in_valid"] = [valid(r.lon, r.lat) for r in ais.itertuples()]
print(f"AIS Class A in AOI at {T}: {len(ais)} | in valid imagery: {int(ais.in_valid.sum())}")
import numpy as _np
wv = ds.read(1, out_shape=(ds.height // 8, ds.width // 8))
print(f"window {ds.width}x{ds.height} px, decimated valid fraction {float((wv > 0).mean()):.3f}")

va = ais[ais.in_valid].copy()

def band(L):
    if pd.isna(L): return "unknown"
    if L < 20: return "<20 m"
    if L < 50: return "20-50 m"
    if L < 100: return "50-100 m"
    return ">=100 m"

va["band"] = va.length.apply(band)
va["state"] = np.where(va.sog >= 3, "moving >=3 kn", np.where(va.sog < 0.5, "stopped <0.5 kn", "1-3 kn"))
print("\nAIS in valid imagery by band x state:")
print(pd.crosstab(va.band, va.state, margins=True).to_string())
print("\nAIS in valid imagery, >=50 m:")
print(va[va.length.fillna(0) >= 50][["mmsi", "name", "length", "sog", "lon", "lat"]].to_string(index=False))

# ---- merge detections within 300 m (single linkage) ----
d = det.reset_index(drop=True)
n = len(d)
parent = list(range(n))
def find(a):
    while parent[a] != a:
        parent[a] = parent[parent[a]]; a = parent[a]
    return a
def union(a, b):
    ra, rb = find(a), find(b)
    if ra != rb: parent[rb] = ra
for i in range(n):
    for j in range(i + 1, n):
        if hav(d.lon[i], d.lat[i], d.lon[j], d.lat[j]) <= 300:
            union(i, j)
groups = {}
for i in range(n):
    groups.setdefault(find(i), []).append(i)
merged = []
for idx in groups.values():
    g = d.iloc[idx]
    k = int(g.score.idxmax())
    merged.append(dict(lon=float(g.lon.mean()), lat=float(g.lat.mean()), boxes=len(idx),
                       score=float(d.score[k]), length=float(d.length[k]) if pd.notna(d.length[k]) else np.nan))
m = pd.DataFrame(merged)
print(f"\nraw detections {n} -> merged within 300 m: {len(m)} "
      f"(multi-box groups: {int((m.boxes > 1).sum())})")
m["in_valid"] = [valid(r.lon, r.lat) for r in m.itertuples()]
print(f"merged detections in valid imagery: {int(m.in_valid.sum())} of {len(m)}")
mv = m[m.in_valid].copy()

# ---- match rates ----
def rates(dlons, dlats, alons, alats, thresholds=(200, 500, 1000)):
    out = {}
    for th in thresholds:
        d_match = sum(nearest(x, y, alons, alats)[0] <= th for x, y in zip(dlons, dlats))
        a_match = sum(nearest(x, y, dlons, dlats)[0] <= th for x, y in zip(alons, alats))
        out[th] = (d_match, a_match)
    return out

alons, alats = va.lon.values, va.lat.values
print(f"\nmatched (detections, AIS) out of ({len(mv)}, {len(va)}) at thresholds:")
res = rates(mv.lon.values, mv.lat.values, alons, alats)
for th, (dm, am) in res.items():
    print(f"  {th:4d} m: radar {dm}/{len(mv)} ({100*dm/max(len(mv),1):.0f}%)  "
          f"AIS {am}/{len(va)} ({100*am/max(len(va),1):.0f}%)")
print("\nper AIS band (nearest detection within 500 m / within band):")
for b, g in va.groupby("band"):
    am = sum(nearest(r.lon, r.lat, mv.lon.values, mv.lat.values)[0] <= 500 for r in g.itertuples())
    print(f"  {b:9s}: {am}/{len(g)}")
print("per AIS state (within 500 m):")
for s, g in va.groupby("state"):
    am = sum(nearest(r.lon, r.lat, mv.lon.values, mv.lat.values)[0] <= 500 for r in g.itertuples())
    print(f"  {s:14s}: {am}/{len(g)}")

# ---- chance control ----
print("\nchance control (AIS shifted, kept if inside AOI and valid imagery):")
ctrl = {}
for km in (10, 20):
    for ang in range(0, 360, 45):
        dx = km * 1000 * math.sin(math.radians(ang)); dy = km * 1000 * math.cos(math.radians(ang))
        slons = va.lon.values + dx / (111320 * np.cos(np.radians(va.lat.values)))
        slats = va.lat.values + dy / 110540
        keep = [(lo, la) for lo, la in zip(slons, slats)
                if AOI[0] <= lo <= AOI[2] and AOI[1] <= la <= AOI[3] and valid(lo, la)]
        if not keep:
            continue
        klon = np.array([k[0] for k in keep]); klat = np.array([k[1] for k in keep])
        r = rates(mv.lon.values, mv.lat.values, klon, klat)
        ctrl[(km, ang)] = (len(keep), r)
        print(f"  {km:2d} km at {ang:3d} deg: kept {len(keep):2d} | "
              + "  ".join(f"{th}m radar {dm} AIS {am}" for th, (dm, am) in r.items()))
if ctrl:
    for th in (200, 500, 1000):
        dm = [v[1][th][0] for v in ctrl.values()]; am = [v[1][th][1] for v in ctrl.values()]
        print(f"  control totals {th:4d} m: radar matches mean {np.mean(dm):.2f} max {max(dm)}, "
              f"AIS matches mean {np.mean(am):.2f} max {max(am)} over {len(ctrl)} shifts")

# ---- unmatched radar list ----
anyc = pd.read_csv(f"{W}/data/t-model/ais_1640_1650_allclasses.csv")
anyc = anyc[(anyc.ts >= "16:43:39") & (anyc.ts <= "16:45:39")]
print(f"\nany-class AIS fixes within +-60 s: {len(anyc)} ({anyc.mobile.value_counts().to_dict()})")
print("\nunmatched radar targets (no AIS within 1 km):")
n_unm = 0
for r in mv.itertuples():
    dist_any, j = nearest(r.lon, r.lat, anyc.lon.values, anyc.lat.values)
    dist_clsA, _ = nearest(r.lon, r.lat, alons, alats)
    if dist_clsA > 1000:
        n_unm += 1
        near = anyc.iloc[j] if j >= 0 else None
        print(f"  {r.lon:.4f}E {r.lat:.4f}N score {r.score:.2f} len {r.length:6.1f} m "
              f"boxes {r.boxes} | nearest AIS any class {dist_any:6.0f} m "
              f"({near.mobile if near is not None else '-'} mmsi {near.mmsi if near is not None else '-'}) "
              f"| nearest Class A {dist_clsA:6.0f} m")
print(f"total unmatched (1 km): {n_unm} of {len(mv)}")
json.dump(dict(run=RUN, det_summary={k: v for k, v in summary.items() if k != "detections"},
               ais_in_valid=int(len(va)), merged=int(len(mv))),
          open(f"{W}/data/t-model/big_eval_{RUN}.json", "w"), indent=1)
