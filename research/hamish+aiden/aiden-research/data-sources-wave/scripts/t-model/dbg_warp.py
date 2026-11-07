import json
import rasterio
from rasterio.transform import from_gcps
from pyproj import Transformer
from rslearn.utils.get_utm_ups_crs import get_utm_ups_projection

p = json.load(open("/tmp/s1picks.json"))
AOI = (12.25, 56.30, 12.85, 56.70)
proj = get_utm_ups_projection((AOI[0]+AOI[2])/2, (AOI[1]+AOI[3])/2, 10, -10)
print("proj", proj.crs)
from rslearn.const import WGS84_PROJECTION
from rslearn.utils.geometry import STGeometry
import shapely
geom = STGeometry(WGS84_PROJECTION, shapely.box(*AOI), None).to_projection(proj)
minx, miny, maxx, maxy = geom.shp.bounds
print("utm bounds", minx, miny, maxx, maxy)
t = Transformer.from_crs(proj.crs, "EPSG:4326", always_xy=True)
for x in (minx, maxx):
    for y in (miny, maxy):
        print("corner", x, y, "->", t.transform(x, y))
for k in ("target", "hist"):
    url = "https://sentinel-s1-l1c.s3.amazonaws.com/" + p[k]["vv"][len("s3://sentinel-s1-l1c/"):]
    with rasterio.open(url) as src:
        gcps, crs = src.gcps
        tr = from_gcps(gcps)
        pts = []
        for x in (minx, maxx):
            for y in (miny, maxy):
                lon, lat = t.transform(x, y)
                pts.append(~tr * (lon, lat))
        print(k, "size", src.width, src.height, "pixel corners", [(round(a), round(b)) for a, b in pts])
