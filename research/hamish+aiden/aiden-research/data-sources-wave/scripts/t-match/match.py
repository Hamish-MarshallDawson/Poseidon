"""Match radar detections to Danish AIS positions interpolated to the Sentinel-1 image time."""
import os, sys, json, numpy as np, pandas as pd

WAVE=os.environ["WAVE"]; D=WAVE+"/data/t-match"
IMG_T=pd.Timestamp("2026-11-01T05:32:03.6Z")     # scene datetime (centre of 25 s sweep)
T0,T1=IMG_T-pd.Timedelta(minutes=12), IMG_T+pd.Timedelta(minutes=12)

def load_ais(csv):
    df=pd.read_csv(csv, low_memory=False)
    df["ts"]=pd.to_datetime(df["ts"], utc=True, format="mixed")
    for c in ("Latitude","Longitude","SOG","COG","Length","Width"):
        df[c]=pd.to_numeric(df[c], errors="coerce")
    df["MMSI"]=pd.to_numeric(df["MMSI"], errors="coerce")
    df=df.dropna(subset=["Latitude","Longitude","MMSI","ts"])
    df=df[(df.Latitude>54.5)&(df.Latitude<57.5)&(df.Longitude>8.0)&(df.Longitude<14.5)]
    return df

def interpolate(df, t=IMG_T, method="interp"):
    """One position per MMSI at time t."""
    out=[]
    for m,g in df.sort_values("ts").groupby("MMSI"):
        g=g.drop_duplicates("ts")
        if len(g)==0: continue
        dt=(g.ts-t).dt.total_seconds().values
        if abs(dt).min()>1800: continue
        if method=="nearest":
            i=int(np.abs(dt).argmin()); row=g.iloc[i]
            out.append((m,row.Latitude,row.Longitude,abs(dt[i]),row.SOG,row.COG,row.Length,row.Width,row.get("Ship type"),row.get("Name"),row.get("IMO"),row.get("Draught"),row.get("Destination"),row.get("Type of mobile"),row.get("Data source type")))
            continue
        j=int(np.searchsorted(g.ts.values, t.to_datetime64()))
        if j==0: lo=hi=0
        elif j>=len(g): lo=hi=len(g)-1
        else: lo,hi=j-1,j
        a,b=g.iloc[lo],g.iloc[hi]
        if lo==hi or a.ts==b.ts:
            lat,lon=a.Latitude,a.Longitude; gap=abs(dt[lo])
        else:
            f=(t-a.ts).total_seconds()/(b.ts-a.ts).total_seconds()
            lat=a.Latitude+f*(b.Latitude-a.Latitude); lon=a.Longitude+f*(b.Longitude-a.Longitude)
            gap=min(abs(dt[lo]),abs(dt[hi]))
        out.append((m,lat,lon,gap,a.SOG,a.COG,a.Length,a.Width,a.get("Ship type"),a.get("Name"),a.get("IMO"),a.get("Draught"),a.get("Destination"),a.get("Type of mobile"),a.get("Data source type")))
    cols=["MMSI","lat","lon","gap_s","sog","cog","length","width","shiptype","name","imo","draught","dest","mobile","src"]
    return pd.DataFrame(out, columns=cols)

def haversine(lat1,lon1,lat2,lon2):
    R=6371000.0
    p1,p2=np.radians(lat1),np.radians(lat2)
    dp=p2-p1; dl=np.radians(lon2-lon1)
    a=np.sin(dp/2)**2+np.cos(p1)*np.cos(p2)*np.sin(dl/2)**2
    return 2*R*np.arcsin(np.sqrt(a))

def offset_m(lat0, lon0, lat, lon):
    """metres east, north of (lat0,lon0)"""
    dn=(lat-lat0)*111320.0
    de=(lon-lon0)*111320.0*np.cos(np.radians(lat0))
    return de,dn
