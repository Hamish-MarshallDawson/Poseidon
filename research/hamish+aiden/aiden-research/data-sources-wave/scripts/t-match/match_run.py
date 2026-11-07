"""Match radar detections to AIS interpolated at each detection's own image time."""
import sys, os, numpy as np, pandas as pd
sys.path.insert(0,'.')
import geo2

D=os.environ["WAVE"]+"/data/t-match"
tag=sys.argv[1] if len(sys.argv)>1 else "greatbelt"

df=pd.read_csv(D+"/ais_0532_raw.csv", low_memory=False)
df["ts"]=pd.to_datetime(df["# Timestamp"], format="%d/%m/%Y %H:%M:%S", utc=True)
for c in ("Latitude","Longitude","SOG","COG","Length","Width","MMSI","Draught"):
    df[c]=pd.to_numeric(df[c], errors="coerce")
df=df.dropna(subset=["Latitude","Longitude","MMSI","ts"])
df=df[(df.Latitude>50)&(df.Latitude<62)&(df.Longitude>-2)&(df.Longitude<20)]
df=df[df["Type of mobile"].isin(["Class A","Class B"])]
df=df[df.SOG.fillna(0)>=0]
print("AIS rows", len(df), "vessels", df.MMSI.nunique(), file=sys.stderr)

det=pd.read_csv(D+f"/det_{tag}.csv")
print("detections", len(det), file=sys.stderr)
# per-detection time from its row (line index in the product)
r0=int(__import__("json").load(open(D+f"/meta_{tag}.json"))["r0"])
det["t"]=geo2.line_time(det.row.values+r0)

# per-vessel tracks
tracks={m:(g.ts.values.astype("datetime64[s]").astype("int64").astype(float), g.Latitude.values, g.Longitude.values)
        for m,g in df.sort_values("ts").groupby("MMSI") if len(g)>=1}
dt=np.array(sorted(tracks))
det.sort_values("t", inplace=True)
tt=det.t.values
Ns=len(dt); Nd=len(tt)
LAT=np.full((Ns,Nd), np.nan); LON=np.full((Ns,Nd), np.nan); GAP=np.full((Ns,Nd), np.nan); SOG=np.full((Ns,Nd), np.nan); COG=np.full((Ns,Nd), np.nan)
for i,m in enumerate(dt):
    ts,la,lo=tracks[m]
    if len(ts)<2:
        continue
    LAT[i]=np.interp(tt,ts,la); LON[i]=np.interp(tt,ts,lo)
    g=df[df.MMSI==m]
    SOG[i]=np.interp(tt,ts,g.SOG.fillna(0).values); COG[i]=np.interp(tt,ts,g.COG.fillna(0).values)
    GAP[i]=np.min(np.abs(tt[:,None]-ts[None,:]),axis=1)
# metres
coslat=np.cos(np.radians(56))
DETLAT=det.lat.values; DETLON=det.lon.values
dn=(LAT-DETLAT[None,:])*111320.0
de=(LON-DETLON[None,:])*111320.0*coslat
dist=np.sqrt(dn**2+de**2)
dist[GAP>900]=np.inf   # no AIS update within 15 min -> not a valid comparison
dist=np.where(np.isnan(dist), np.inf, dist)
print("cells", dist.shape, file=sys.stderr)

nn=np.argmin(dist,axis=0); dmin=dist[nn,np.arange(Nd)]
res=pd.DataFrame(dict(det_i=np.arange(Nd), mmsi=dt[nn], dist=dmin, t=det.t.values,
                      w=det.w.values, h=det.h.values, npx=det.npx.values, peak_db=det.peak_db.values,
                      de=de[nn,np.arange(Nd)], dn=dn[nn,np.arange(Nd)], gap=GAP[nn,np.arange(Nd)],
                      sog=SOG[nn,np.arange(Nd)], cog=COG[nn,np.arange(Nd)]))
meta=df.groupby("MMSI").agg(name=("Name","last"), shiptype=("Ship type","last"), length=("Length","max"),
                           width=("Width","max"), imo=("IMO","last"), draught=("Draught","max"), dest=("Destination","last")).reset_index()
res=res.merge(meta,left_on="mmsi",right_on="MMSI",how="left")

# azimuth (along-track) unit vector per detection
r=det.row.values+r0; c=det.col.values
la1,lo1=geo2.latlon(r,c); la2,lo2=geo2.latlon(r+50,c)
ax=(la2-la1)*111320.0; ay=(lo2-lo1)*111320.0*coslat
norm=np.hypot(ax,ay); ax/=norm; ay/=norm
res["az_res"]=(res.de*ay + res.dn*ax)     # component of (AIS - detection)? see sign below
res["rg_res"]=(res.de*ay - res.dn*ax)     # perpendicular (range) component
res.to_csv(D+f"/match_{tag}.csv", index=False)

print("\n== detections matched at gate ==")
for gate in (50,100,200,300,500,1000,2000,5000):
    m=dmin<=gate
    print(f"gate {gate:>4} m: matched {m.sum():4d}/{Nd} = {100*m.mean():5.1f}%")

# AIS side: vessels in the window at image time with >=1 detection within gate
print("\n== AIS vessels vs detections (gate 500 m) ==")
gate=500
m=dmin<=gate
matched_mmsi=set(res.loc[m,"mmsi"])
# all vessels with a position inside the detection window at their own interpolated time
sub=df[(df.ts>=pd.Timestamp('2026-11-01T05:30:00Z'))&(df.ts<=pd.Timestamp('2026-11-01T05:34:00Z'))]
inside=sub[(sub.Latitude>=55.05)&(sub.Latitude<=55.75)&(sub.Longitude>=10.6)&(sub.Longitude<=11.45)]
v=inside.groupby("MMSI").agg(length=("Length","max"), shiptype=("Ship type","last"), name=("Name","last"), sog=("SOG","max"), n=("ts","count")).reset_index()
v["matched"]=v.MMSI.isin(matched_mmsi)
print("vessels with positions inside window:", len(v), "matched:", int(v.matched.sum()))
bandsv=[(0,20),(20,50),(50,100),(100,200),(200,400)]
print(f"{'len band m':>12} {'vessels':>8} {'matched':>8} {'rate':>6}")
for a,b in bandsv:
    s=v[(v.length>=a)&(v.length<b)]
    print(f"{f'{a}-{b}':>12} {len(s):>8} {int(s.matched.sum()) if len(s) else 0:>8} {(s.matched.mean()*100 if len(s) else float('nan')):>5.0f}%")
print("\nunmatched AIS vessels (gate 500 m), by max SOG:")
print(v[~v.matched].sort_values("sog",ascending=False).head(15).to_string())
print("\n== offset (radar - AIS) for near matches, gate 2 km ==")
m2=dmin<=2000
print(res.loc[m2,["de","dn"]].describe().loc[["mean","50%","std"]].round(0).to_string())
np.save(D+f"/r0.npy", np.array([r0]))
open(D+f"/r0_{tag}.txt","w").write(str(r0))
