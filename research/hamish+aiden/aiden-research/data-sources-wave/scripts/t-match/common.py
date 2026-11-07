import numpy as np, rasterio, json, os
WAVE=os.environ["WAVE"]; D=WAVE+"/data/t-match"
TIFF=D+"/s1c_vv.tiff"
# georeferencing comes from STAC item properties (the COG itself carries none)
P=json.load(open(os.path.join(os.path.dirname(__file__),"item_grd.json")))["properties"]["proj:transform"]
A,B,C,Dd,E,F=P
SCENE_T0="2026-11-01T05:31:51.1Z"; SCENE_T1="2026-11-01T05:32:16.1Z"

def window_for(bbox):
    west,south,east,north=bbox
    col0=int(round((west-C)/A)); col1=int(round((east-C)/A))
    row0=int(round((north-F)/E)); row1=int(round((south-F)/E))
    return row0,col0,row1,col1

def read_window(bbox, band=1):
    r0,c0,r1,c1=window_for(bbox)
    with rasterio.open(TIFF) as ds:
        a=ds.read(band, window=rasterio.windows.Window(c0,r0,c1-c0,r1-r0)).astype("float32")
    return a,(r0,c0)

def transform_for(bbox):
    r0,c0,r1,c1=window_for(bbox)
    t=rasterio.Affine(A,0.0,C+c0*A,0.0,E,F+r0*E)
    return t,(r0,c0)
