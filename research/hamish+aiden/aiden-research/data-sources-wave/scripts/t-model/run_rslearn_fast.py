"""Run allenai/rslearn_projects Sentinel-1 vessel detector on a Kattegat window.

Throwaway feasibility driver: builds an rslearn dataset for a sub-window of the
SCENE, then calls the repo's own get_vessel_detections / run_attribute_model so the
model code path is the published one. Only the tile-store ingest is overridden: the
upstream aws_sentinel1 ingest downloads whole scene tiffs from S3 with boto3 and a
`RequestPayer: requester` header (needs AWS credentials), and it builds the S3 key
without the trailing 4-hex-digit hash that recent L1C product folders carry, so the
key would 404 anyway. Here the four band files were fetched anonymously over https
and are read from local disk.
"""

import json
import os
import sys
import time
from datetime import datetime, timedelta

W = "/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave"
REPO = f"{W}/data/t-model/rslearn_projects"
os.environ.setdefault("RSLP_PREFIX", f"{REPO}/project_data")
sys.path.insert(0, REPO)
os.chdir(REPO)

import shapely  # noqa: E402
from upath import UPath  # noqa: E402

from rslearn.const import WGS84_PROJECTION  # noqa: E402
from rslearn.data_sources.aws_sentinel1 import Sentinel1 as AwsSentinel1  # noqa: E402
from rslearn.data_sources.copernicus import CopernicusItem  # noqa: E402
from rslearn.utils.geometry import STGeometry  # noqa: E402
from rslearn.utils.get_utm_ups_crs import get_utm_ups_projection  # noqa: E402

import importlib  # noqa: E402

pp = importlib.import_module("rslp.sentinel1_vessels.predict_pipeline")  # noqa: E402

AOI = tuple(float(v) for v in os.environ.get(
    "T_MODEL_AOI", "12.25,56.30,12.85,56.70"
).split(","))  # lon0, lat0, lon1, lat1
RUN = os.environ.get("T_MODEL_RUN", "fast1")
OUT_JSON = f"{W}/data/t-model/dets_fast1.json"
OUT_GEOJSON = f"{W}/data/t-model/dets_fast1.geojson"
OUT_CROPS = f"{W}/data/t-model/crops_fast1"
SCRATCH = f"{W}/data/t-model/scratch/{RUN}"
S1CACHE = f"{W}/data/t-model/s1cache"

picks = json.load(open("/tmp/s1picks.json"))


def make_item(key: str) -> CopernicusItem:
    p = picks[key]
    shp = shapely.geometry.shape(p["geometry"])
    t0 = datetime.fromisoformat(p["datetime"].replace("Z", "+00:00")).replace(tzinfo=None)
    geom = STGeometry(WGS84_PROJECTION, shp, (t0, t0 + timedelta(seconds=25)))
    return CopernicusItem(p["id"], geom, p["id"])


target = make_item("target")
hist = make_item("hist")

# UTM projection for the scene, 10 m pixels, as predict_pipeline does for scene ids.
centroid = target.geometry.to_projection(WGS84_PROJECTION).shp.centroid
proj = get_utm_ups_projection(centroid.x, centroid.y, pp.RESOLUTION, -pp.RESOLUTION)

aoi_geom = STGeometry(
    WGS84_PROJECTION, shapely.box(*AOI), target.geometry.time_range
).to_projection(proj)
minx, miny, maxx, maxy = aoi_geom.shp.bounds
# snap outward to whole pixels
bounds = (int(minx // 10) * 10, int(miny // 10) * 10,
          -int(-maxx // 10) * 10, -int(-maxy // 10) * 10)
width = bounds[2] - bounds[0]
height = bounds[3] - bounds[1]
print(f"window bounds={bounds} size={width}x{height} px "
      f"({width*10/1000:.1f} km x {height*10/1000:.1f} km)", flush=True)

# --- override ingest: warp only the AOI window out of the local full-scene files ---
LOCAL = {
    target.name: {"vv": f"{S1CACHE}/target_vv.tiff", "vh": f"{S1CACHE}/target_vh.tiff"},
    hist.name: {"vv": f"{S1CACHE}/hist_vv.tiff", "vh": f"{S1CACHE}/hist_vh.tiff"},
}
CROPDIR = f"{W}/data/t-model/crops_ingest"
os.makedirs(CROPDIR, exist_ok=True)


def crop_aoi(src_path: str, out_path: str) -> None:
    """Crop the AOI window out of a GCP-referenced GRD COG, keeping GCP georeferencing.

    rslearn's Projection coordinates are in pixel units (1 unit = 10 m here);
    STGeometry.to_projection converts them back to WGS84 degrees.
    """
    import rasterio
    from rasterio.control import GroundControlPoint
    from rasterio.transform import from_gcps
    from rslearn.const import WGS84_PROJECTION
    from rslearn.utils.geometry import STGeometry

    x0, y0, x1, y1 = bounds
    aoi = STGeometry(proj, shapely.box(x0, y0, x1, y1), None).to_projection(
        WGS84_PROJECTION
    )
    lon0, lat0, lon1, lat1 = aoi.shp.bounds
    with rasterio.open(src_path) as src:
        gcps, gcp_crs = src.gcps
        tr = from_gcps(gcps)
        cols, rows = zip(
            *[~tr * (lon, lat) for lon in (lon0, lon1) for lat in (lat0, lat1)]
        )
        c0 = max(0, int(min(cols)) - 300)
        c1 = min(src.width, int(max(cols)) + 300)
        r0 = max(0, int(min(rows)) - 300)
        r1 = min(src.height, int(max(rows)) + 300)
        if c1 <= c0 or r1 <= r0:
            raise ValueError(
                f"AOI window empty for {src_path}: cols {c0}-{c1} rows {r0}-{r1} "
                f"(aoi pixel corners {list(zip(cols, rows))})"
            )
        arr = src.read(1, window=rasterio.windows.Window(c0, r0, c1 - c0, r1 - r0))
    sub = [
        GroundControlPoint(row=g.row - r0, col=g.col - c0, x=g.x, y=g.y, z=g.z)
        for g in gcps
    ]
    profile = {
        "driver": "GTiff", "height": arr.shape[0], "width": arr.shape[1],
        "count": 1, "dtype": arr.dtype, "crs": None, "compress": "deflate",
    }
    with rasterio.open(out_path, "w", **profile) as out:
        out.gcps = (sub, gcp_crs)
        out.write(arr, 1)
    print(f"cropped {os.path.basename(src_path)} -> {out_path}: "
          f"rows {r0}-{r1} cols {c0}-{c1} out {arr.shape[1]}x{arr.shape[0]}, "
          f"aoi lon/lat {lon0:.3f}-{lon1:.3f}E {lat0:.3f}-{lat1:.3f}N", flush=True)


def local_ingest(self, tile_store, items, geometries):  # noqa: ANN001
    for item in items:
        for band in ("vv", "vh"):
            if tile_store.is_raster_ready(item, [band]):
                continue
            crop = f"{CROPDIR}/{item.name.split('_')[4]}_{band}.tif"
            if not os.path.exists(crop):
                crop_aoi(LOCAL[item.name][band], crop)
            print(f"ingest {item.name[:40]}... band={band} from {crop}", flush=True)
            tile_store.write_raster_file(
                item, [band], UPath(crop), time_range=item.geometry.time_range
            )


AwsSentinel1.ingest = local_ingest

ds_path = UPath(SCRATCH)
ds_path.mkdir(parents=True, exist_ok=True)
cfg = json.load(open(pp.SCENE_ID_DATASET_CONFIG))
cfg["layers"]["sentinel1_historical"]["data_source"]["init_args"]["orbit_direction"] = (
    "ASCENDING"
)
with (ds_path / "config.json").open("w") as f:
    json.dump(cfg, f)

scene_data = pp.SceneData(
    projection=proj,
    bounds=bounds,
    time_range=target.geometry.time_range,
    layer_to_item_groups={
        pp.SENTINEL1_LAYER_NAME: [[target]],
        pp.HISTORICAL_LAYER_NAME: [[hist]],
    },
)

t0 = time.monotonic()
dets = pp.get_vessel_detections(ds_path, [scene_data], score_threshold=0.7)
t_detect = time.monotonic() - t0
print(f"detector stage {t_detect:.1f}s -> {len(dets)} raw detections", flush=True)

t0 = time.monotonic()
crops = pp.run_attribute_model(ds_path, dets, [scene_data])
t_attr = time.monotonic() - t0
print(f"attribute stage {t_attr:.1f}s -> {len(crops)} crops", flush=True)

tasks = [pp.PredictionTask(geojson_path=OUT_GEOJSON, crop_path=OUT_CROPS,
                           json_path=OUT_JSON)]
by_task = pp._build_predictions_and_crops(dets, crops, tasks)
final = by_task[0]
print(f"after near-infra filter: {len(final)} detections", flush=True)

summary = {
    "scene": target.name,
    "historical": hist.name,
    "window_bounds_utm": bounds,
    "window_km": [width * 10 / 1000, height * 10 / 1000],
    "raw_detections": len(dets),
    "after_infra_filter": len(final),
    "detect_stage_s": round(t_detect, 1),
    "attribute_stage_s": round(t_attr, 1),
    "detections": [d_.to_dict() for d_ in final],
}
json.dump(summary, open(f"{W}/data/t-model/summary_{RUN}.json", "w"), indent=1)
print(json.dumps({k: v for k, v in summary.items() if k != "detections"}, indent=1))
