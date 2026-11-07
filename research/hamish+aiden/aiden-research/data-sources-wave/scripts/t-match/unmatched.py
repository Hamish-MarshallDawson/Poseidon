import pandas as pd, numpy as np, json, os
D=os.environ["WAVE"]+"/data/t-match"
r=pd.read_csv(D+"/match_greatbelt.csv"); d=pd.read_csv(D+"/det_greatbelt.csv").reset_index(drop=True)
m=pd.concat([r.reset_index(drop=True), d[["lat","lon","bg_db","elong"]].reset_index(drop=True)],axis=1)
m.to_csv(D+"/match_greatbelt_full.csv",index=False)
u=m[m.dist>2000]
print("unmatched detections:",len(u),"of",len(m))
print("\ntop unmatched by brightness with npx>=10:")
print(u[u.npx>=10].sort_values("peak_db",ascending=False)[["lat","lon","npx","h","w","peak_db","bg_db","elong","dist"]].head(10).to_string(index=False,float_format=lambda x:f"{x:.1f}"))
print("\nlargest unmatched blobs:")
print(u.sort_values("npx",ascending=False)[["lat","lon","npx","h","w","peak_db","elong","dist"]].head(8).to_string(index=False,float_format=lambda x:f"{x:.1f}"))
