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

AOI = (12.25, 56.30, 12.85, 56.70)  # lon0, lat0, lon1, lat1 (Kattegat, north of Kullen)
OUT_JSON = f"{W}/data/t-model/dets_run1.json"
OUT_GEOJSON = f"{W}/data/t-model/dets_run1.geojson"
OUT_CROPS = f"{W}/data/t-model/crops_run1"
SCRATCH = f"{W}/data/t-model/scratch/run1"
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

# --- override the S3 ingest to read local files ---
LOCAL = {
    target.name: {"vv": f"{S1CACHE}/target_vv.tiff", "vh": f"{S1CACHE}/target_vh.tiff"},
    hist.name: {"vv": f"{S1CACHE}/hist_vv.tiff", "vh": f"{S1CACHE}/hist_vh.tiff"},
}


def local_ingest(self, tile_store, items, geometries):  # noqa: ANN001
    for item in items:
        for band in ("vv", "vh"):
            if tile_store.is_raster_ready(item, [band]):
                continue
            path = LOCAL[item.name][band]
            print(f"ingest {item.name[:40]}... band={band} from {path}", flush=True)
            tile_store.write_raster_file(
                item, [band], UPath(path), time_range=item.geometry.time_range
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
    "detections": [
        {
            "lon": round(d_["lon"], 5) if "lon" in d_ else None,
            "lat": round(d_["lat"], 5) if "lat" in d_ else None,
            "score": round(float(d_.get("score", 0)), 3),
            "length": d_.get("attributes", {}).get("length"),
            "width": d_.get("attributes", {}).get("width"),
            "vessel_type": d_.get("attributes", {}).get("vessel_type"),
            "speed": d_.get("attributes", {}).get("speed"),
        }
        for d_ in final
    ],
}
json.dump(summary, open(f"{W}/data/t-model/summary_run1.json", "w"), indent=1)
print(json.dumps({k: v for k, v in summary.items() if k != "detections"}, indent=1))
