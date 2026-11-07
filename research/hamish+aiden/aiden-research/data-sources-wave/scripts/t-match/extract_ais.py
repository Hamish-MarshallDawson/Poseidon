"""Extract Danish AIS messages around a time window and bbox from aisdk-2026-11-01.zip."""
import pandas as pd, zipfile, sys, os
Z=os.environ["WAVE"]+"/data/t-match/aisdk-2026-11-01.zip"
t0,t1=sys.argv[1],sys.argv[2]
out=sys.argv[3]
cols=["# Timestamp","Type of mobile","MMSI","Latitude","Longitude","SOG","COG","Heading","IMO","Callsign","Name","Ship type","Cargo type","Width","Length","Type of position fixing device","Draught","Destination","ETA","Data source type"]
frames=[]; nrows=0
with zipfile.ZipFile(Z) as z:
    name=z.namelist()[0]
    print("member:",name, file=sys.stderr)
    with z.open(name) as f:
        for i,chunk in enumerate(pd.read_csv(f, sep=",", usecols=lambda c: c in cols or c=="Timestamp", dtype=str, chunksize=2_000_000, on_bad_lines="skip", low_memory=False)):
            nrows+=len(chunk)
            ts=pd.to_datetime(chunk["# Timestamp"], format="%d/%m/%Y %H:%M:%S", errors="coerce", utc=True)
            keep=(ts>=pd.Timestamp(t0))&(ts<=pd.Timestamp(t1))
            if keep.any():
                c=chunk[keep].copy(); c["ts"]=ts[keep]; frames.append(c)
            print("chunk",i,"rows",nrows,"kept",sum(len(f) for f in frames), file=sys.stderr)
df=pd.concat(frames) if frames else pd.DataFrame()
df.to_parquet(out) if False else df.to_csv(out,index=False)
print("total rows scanned",nrows,"kept",len(df),"->",out)
