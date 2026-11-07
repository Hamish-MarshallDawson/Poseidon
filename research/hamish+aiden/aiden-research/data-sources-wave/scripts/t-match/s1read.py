import json, urllib.parse, urllib.request, rasterio, os, sys
BLOB="https://sentinel1euwest.blob.core.windows.net/s1-grd/GRD/2026/11/1/IW/DV/S1C_IW_GRDH_1SDV_20261101T053151_20261101T053216_010139_0143CB_2CB4/measurement/"
def signed(href):
    u="https://planetarycomputer.microsoft.com/api/sas/v1/sign?href="+urllib.parse.quote(href,safe='')
    return json.load(urllib.request.urlopen(u, timeout=60))["href"]
os.environ["GDAL_DISABLE_READDIR_ON_OPEN"]="EMPTY_DIR"
vv=signed(BLOB+"iw-vv.tiff")
open("vv_url.txt","w").write(vv)
with rasterio.open("vsicurl/"+vv) as ds:
    print("size", ds.width, ds.height, "bands", ds.count, "dtype", ds.dtypes, "crs", ds.crs)
    print("transform", ds.transform)
    print("bounds", ds.bounds)
    print("overviews", ds.overviews(1))
    print("nodata", ds.nodata)
    print("descriptions", ds.descriptions)
