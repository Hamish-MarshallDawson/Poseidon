import re, numpy as np, json, sys
X=open(sys.argv[1] if len(sys.argv)>1 else "../"+"","r").read() if False else open(__import__("os").environ["WAVE"]+"/data/t-match/iw-vv.xml").read()
m=re.search(r"<imageInformation>(.*?)</imageInformation>", X, re.S).group(1)
for tag in ["productFirstLineUtcTime","productLastLineUtcTime","numberOfSamples","numberOfLines","rangePixelSpacing","azimuthPixelSpacing","projection","sliceNumber"]:
    r=re.search(rf"<{tag}>(.*?)</{tag}>", m)
    print(tag, r.group(1) if r else None)
pts=re.findall(r"<geolocationGridPoint>(.*?)</geolocationGridPoint>", X, re.S)
print("points", len(pts))
rows=[]
for p in pts:
    d={k:float(v) for k,v in re.findall(r"<(azimuthTime|slantRangeTime|line|pixel|latitude|longitude|incidenceAngle|elevationAngle)>(.*?)</\1>", p) if k!="azimuthTime"}
    t=re.search(r"<azimuthTime>(.*?)</azimuthTime>", p).group(1)
    d["t"]=t; rows.append(d)
import pandas as pd
df=pd.DataFrame(rows)
print(df[["line","pixel","latitude","longitude","t"]].head(4).to_string())
print("lines", sorted(df.line.unique()), "pixels n", df.pixel.nunique())
print("lat range", df.latitude.min(), df.latitude.max(), "lon range", df.longitude.min(), df.longitude.max())
df.to_csv(__import__("os").environ["WAVE"]+"/data/t-match/tiepoints.csv", index=False)
# per-line azimuth times
lt=re.findall(r"<azimuthTime>(.*?)</azimuthTime>", X)
print("azimuthTime count", len(lt), lt[0], lt[-1])
