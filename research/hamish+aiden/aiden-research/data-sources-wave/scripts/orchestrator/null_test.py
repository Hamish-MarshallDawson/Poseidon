import numpy as np,pandas as pd,json,os,sys
from shapely.geometry import shape,Point
from shapely.ops import unary_union
from shapely.prepared import prep
D=sys.argv[1]
land=prep(unary_union([shape(f['geometry']) for f in json.load(open(D+'/ne_10m_land.geojson'))['features'] if True]))
AOI={'greatbelt':(10.60,55.05,11.45,55.75),'fehmarn':(10.95,54.35,11.65,54.85)}
rng=np.random.default_rng(1);K=111320.;C=np.cos(np.radians(55.2))
G=[100,200,500,1000]
def rate(v,detlat,detlon,minpx=None):
    out=[]
    for la,lo in v:
        out.append(np.sqrt(((detlat-la)*K)**2+((detlon-lo)*K*C)**2).min())
    out=np.array(out);return [round(100*(out<=g).mean()) for g in G],len(out)
for t,(a,b,c,e) in AOI.items():
    det=pd.read_csv(f'{D}/det_{t}.csv');ais=pd.read_csv(f'{D}/ais_side_{t}.csv')
    print('==',t,'detections',len(det),'columns',list(ais.columns)[:14])
    la='lat' if 'lat' in ais else [x for x in ais.columns if x.lower().startswith('lat') or 'ais_lat' in x.lower()][0]
    lo='lon' if 'lon' in ais else [x for x in ais.columns if x.lower().startswith('lon') or 'ais_lon' in x.lower()][0]
    sogc=[x for x in ais.columns if x.lower() in('sog','speed')][0];lenc=[x for x in ais.columns if 'length' in x.lower()][0]
    ais=ais.dropna(subset=[la,lo])
    for name,dd in {'all detections':det,'>=20 px':det[det.npx>=20],'>=50 px':det[det.npx>=50]}.items():
        for vn,vv in {'all vessels':ais,'moving >3kn, >=50m':ais[(ais[sogc]>3)&(ais[lenc]>=50)]}.items():
            v=vv[[la,lo]].values
            real,n=rate(v,dd.lat.values,dd.lon.values)
            shifted=[]
            for ang in np.arange(0,360,30):
                for km in (3,5,8):
                    dla=km*1000*np.cos(np.radians(ang))/K;dlo=km*1000*np.sin(np.radians(ang))/(K*C)
                    for p in v+[dla,dlo]:
                        if a<=p[1]<=c and b<=p[0]<=e and not land.contains(Point(p[1],p[0])): shifted.append(p)
            sr,sn=rate(np.array(shifted),dd.lat.values,dd.lon.values) if shifted else ([None]*4,0)
            print(f'{name:15s} {vn:20s} n={n:3d} real {dict(zip(G,real))} | chance (shifted, sea only, n={sn}) {dict(zip(G,sr))}')
