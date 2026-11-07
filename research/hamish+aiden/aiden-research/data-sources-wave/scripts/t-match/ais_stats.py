import pandas as pd, numpy as np, sys
sys.path.insert(0,'.')
import match as M
df=pd.read_csv(M.D+"/ais_0532_raw.csv", low_memory=False)
print("rows",len(df))
df["ts"]=pd.to_datetime(df["# Timestamp"], format="%d/%m/%Y %H:%M:%S", utc=True)
for c in ("Latitude","Longitude","SOG","COG","Length","Width","MMSI","Draught"):
    df[c]=pd.to_numeric(df[c], errors="coerce")
df=df.dropna(subset=["Latitude","Longitude","MMSI"])
print("unique MMSI", df.MMSI.nunique())
print(df["Type of mobile"].value_counts().to_string())
print(df["Ship type"].value_counts().head(8).to_string())
print(df["Data source type"].value_counts().to_string())
print("bbox", df.Latitude.min(), df.Latitude.max(), df.Longitude.min(), df.Longitude.max())
# reporting intervals per vessel
g=df.sort_values("ts").groupby("MMSI")["ts"]
dts=g.diff().dt.total_seconds().dropna()
print("report interval s percentiles", np.percentile(dts,[5,25,50,75,95]).round(1), "n",len(dts))
# field completeness
for c in ("IMO","Name","Ship type","Draught","Destination","Length","Width"):
    v=df[c].astype(str)
    ok=~v.isin(["nan","Unknown","Undefined","","None"])
    print(f"{c} present {ok.mean()*100:.1f}%")
