"""AIS-side matching: for each vessel in the window, distance to the nearest radar detection."""
import sys, os, json, numpy as np, pandas as pd
sys.path.insert(0,'.'); import geo2
D=os.environ["WAVE"]+"/data/t-match"; tag=sys.argv[1] if len(sys.argv)>1 else "greatbelt"
meta=json.load(open(D+f"/meta_{tag}.json")); bbox=meta["bbox"]
det=pd.read_csv(D+f"/det_{tag}.csv")
df=pd.read_csv(D+"/ais_0532_raw.csv", low_memory=False)
df["ts"]=pd.to_datetime(df["# Timestamp"],format="%d/%m/%Y %H:%M:%S",utc=True)
for c in ("Latitude","Longitude","SOG","COG","Length","Width","MMSI","Draught"):
    df[c]=pd.to_numeric(df[c],errors="coerce")
df=df.dropna(subset=["Latitude","Longitude","MMSI","ts"])
df=df[(df.Latitude>50)&(df.Latitude<62)&(df.Longitude>-2)&(df.Longitude<20)]
img_t=geo2.line_time((meta["r0"]+meta["r1"])/2)
inside=df[(df.Latitude>=bbox[1])&(df.Latitude<=bbox[3])&(df.Longitude>=bbox[0])&(df.Longitude<=bbox[2])]
# one position per vessel, interpolated at the image mid time
rows=[]
for m,g in inside.groupby("MMSI"):
    g=g.sort_values("ts"); ts=g.ts.values.astype("datetime64[s]").astype("int64").astype(float)
    if len(ts)<2: continue
    lat=float(np.interp(img_t,ts,g.Latitude.values)); lon=float(np.interp(img_t,ts,g.Longitude.values))
    rows.append(dict(MMSI=int(m),lat=lat,lon=lon,sog=float(g.SOG.max()),cog=float(g.COG.median()),
                     length=float(g.Length.max()),shiptype=g["Ship type"].iloc[-1],name=g.Name.iloc[-1],
                     draught=float(g.Draught.max()),n=len(g)))
v=pd.DataFrame(rows)
coslat=np.cos(np.radians(56))
dn=(v.lat.values[:,None]-det.lat.values[None,:])*111320.0
de=(v.lon.values[:,None]-det.lon.values[None,:])*111320.0*coslat
d=np.sqrt(dn**2+de**2)
j=np.argmin(d,axis=1)
v["dist"]=d[np.arange(len(v)),j]; v["res_n"]=dn[np.arange(len(v)),j]; v["res_e"]=de[np.arange(len(v)),j]
# local along-track / across-track directions
la1,lo1=geo2.latlon(det.row.values+meta["r0"], det.col.values)
la2,lo2=geo2.latlon(det.row.values+meta["r0"]+50, det.col.values)
an=(la2-la1)*111.32*1000; ae=(lo2-lo1)*111.32*1000*coslat
nn=np.hypot(an,ae); an/=nn; ae/=nn
v=v.join(pd.DataFrame(dict(an=an[j],ae=ae[j])).reset_index(drop=True))
v["res_az"]=v.res_n*v.an+v.res_e*v.ae
v["res_rg"]=v.res_n*v.ae-v.res_e*v.an
v["v_az"]=(v.sog*0.5144*np.cos(np.radians(v.cog)))*v.an+(v.sog*0.5144*np.sin(np.radians(v.cog)))*v.ae
v["v_rg"]=(v.sog*0.5144*np.cos(np.radians(v.cog)))*v.ae-(v.sog*0.5144*np.sin(np.radians(v.cog)))*v.an
v.to_csv(D+f"/ais_side_{tag}.csv",index=False)
print(f"vessels inside window at {pd.Timestamp(img_t,unit='s')}: {len(v)}")
for gate in (30,50,100,200,500,1000):
    print(f"  within {gate:>4} m of a radar detection: {int((v.dist<=gate).sum()):3d} ({100*(v.dist<=gate).mean():4.0f}%)")
print("\nby length band:")
for a,b in [(0,20),(20,50),(50,100),(100,200),(200,400)]:
    s=v[(v.length>=a)&(v.length<b)]
    if len(s)==0: continue
    print(f"  {a}-{b} m: n={len(s):3d} median nearest-detection distance {s.dist.median():6.0f} m, <=200m {100*(s.dist<=200).mean():3.0f}%")
print("\nlargest ships (length>=100 m):")
print(v[v.length>=100].sort_values("length",ascending=False)[["name","MMSI","length","sog","dist","res_az","res_rg","v_az","v_rg"]].head(20).to_string(index=False,float_format=lambda x:f"{x:.0f}"))
mov=v[(v.sog>3)&(v.dist<2500)]
if len(mov)>10:
    A=np.column_stack([mov.v_az,mov.v_rg,np.ones(len(mov))])
    co,*_=np.linalg.lstsq(A,mov.res_az.values,rcond=None)
    pred=A@co; r2s=1-((mov.res_az-pred)**2).sum()/((mov.res_az-mov.res_az.mean())**2).sum()
    print(f"\nfit on {len(mov)} moving vessels (SOG>3kn, nearest detection <2.5 km):")
    print(f"  res_az = {co[0]:.0f}*v_az + {co[1]:.0f}*v_rg + {co[2]:.0f}   (theory dt~0, b=-R/V~-105 s)  R2={r2s:.2f}")
    B=np.column_stack([mov.v_rg,np.ones(len(mov))])
    cb,*_=np.linalg.lstsq(B,mov.res_az.values,rcond=None)
    print(f"  simple: res_az = {cb[0]:.0f}*v_rg + {cb[1]:.0f}")
