import sys, os, numpy as np, pandas as pd, json
sys.path.insert(0,'.'); import geo2
D=os.environ["WAVE"]+"/data/t-match"
tag=sys.argv[1] if len(sys.argv)>1 else "greatbelt"
r=pd.read_csv(D+f"/match_{tag}.csv")
det=pd.read_csv(D+f"/det_{tag}.csv")
r0=json.load(open(D+f"/meta_{tag}.json"))["r0"]
# unit vectors (north, east) along-track and across-track from the tie-point grid
la1,lo1=geo2.latlon(det.row.values+r0, det.col.values)
la2,lo2=geo2.latlon(det.row.values+r0+50, det.col.values)
coslat=np.cos(np.radians(56))
an=(la2-la1)*1000*111.32; ae=(lo2-lo1)*1000*111.32*coslat
n=np.hypot(an,ae); an/=n; ae/=n
rn, re = ae, -an
r["res_n"]=r.dn; r["res_e"]=r.de      # AIS minus radar
r["res_az"]=r.res_n*an + r.res_e*ae
r["res_rg"]=r.res_n*rn + r.res_e*re
sog_ms=r.sog.fillna(0)*0.5144; cog=np.radians(r.cog.fillna(0))
vn=sog_ms*np.cos(cog); ve=sog_ms*np.sin(cog)
r["v_az"]=vn*an+ve*ae; r["v_rg"]=vn*rn+ve*re
r["dist"]=r.dist
print("== residuals (AIS - radar), all detections with a vessel within gate ==")
for lo,hi in [(0,0.5),(0.5,2),(2,5),(5,20)]:
    s=r[(r.sog>=lo)&(r.sog<hi)&(r.dist<=5000)]
    if len(s)<5: continue
    print(f"  SOG {lo}-{hi} kn: n={len(s):4d} |res_az| median {np.median(np.abs(s.res_az)):6.0f} m, |res_rg| median {np.median(np.abs(s.res_rg)):5.0f} m, dist<=200m {100*(s.dist<=200).mean():4.0f}%, <=500m {100*(s.dist<=500).mean():4.0f}%")
low=r[(r.sog<1.0)&(r.dist<=1500)]
if len(low)>3:
    print(f"  slow (<1 kn, <=1.5 km) n={len(low)}: res_n mean {low.res_n.mean():.0f} +- {low.res_n.std():.0f} m, res_e mean {low.res_e.mean():.0f} +- {low.res_e.std():.0f} m")
fit=r[(r.sog>3)&(r.dist<=3000)].copy()
if len(fit)>20:
    A=np.column_stack([fit.v_az, fit.v_rg, np.ones(len(fit))])
    coef,*_=np.linalg.lstsq(A, fit.res_az.values, rcond=None)
    pred=A@coef; ss=1-((fit.res_az.values-pred)**2).sum()/((fit.res_az.values-fit.res_az.mean())**2).sum()
    print(f"\n== fit res_az = dt*v_az + b*v_rg + c  (n={len(fit)}, SOG>3kn, dist<=3km) ==")
    print(f"  dt = {coef[0]:.1f} s   (timing offset between AIS interpolation and the image pixel time)")
    print(f"  b  = {coef[1]:.1f} s   (theory: -R/V = -105 s, i.e. azimuth shift per m/s of radial speed)")
    print(f"  c  = {coef[2]:.0f} m   (constant along-track geolocation bias)   R2 = {ss:.2f}")
print("\n== largest unmatched radar targets (dist > 2 km) ==")
u=r[r.dist>2000].sort_values("peak_db",ascending=False)
print(u[["lat","lon","npx","h","w","peak_db","bg_db","elong"]].head(12).to_string())
u.to_csv(D+f"/unmatched_{tag}.csv",index=False)
