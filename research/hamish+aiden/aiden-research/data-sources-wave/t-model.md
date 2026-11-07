# t-model: can the open Ai2 Sentinel-1 ship detector run here?

Agent t-model, 7 Nov 2026. Evidence labels: `measured` (I ran it), `documented` (primary source),
`unverified`.

## 1. Bottom line

1. **It runs end to end on this machine.** `allenai/rslearn_projects`' Sentinel-1 vessel detector
   (Apache-2.0 code, Apache-2.0 weights on a public Google bucket, no account) processed a
   38 x 46 km Kattegat window in **108 s** once imagery was on disk, on the RTX 4060 (peak ~1.1 GB
   of the 8 GB). Fixed setup cost: 5.7 GB venv, 2.4 GB weights, 2.56 GB of Sentinel-1 files.
   `measured`
2. **The documented quick-start does not work as written.** The scene-ID route resolves scenes
   through CDSE, which needs Copernicus credentials; the AWS ingest routine builds an S3 key
   without the 4-hex product-folder suffix that current products carry (that key returns 404) and
   requests the bucket with `RequestPayer: requester`, i.e. an AWS account. Workaround, anonymous
   throughout: take asset hrefs from Earth Search STAC, fetch the tiffs over plain https.
   `measured` + `documented`
3. **On the windows I tested it is credible on large ships, and it found one genuine radar-only
   target.** Danish Class A AIS puts 4 vessels in the first window at image time (STAITHES 180 m
   cargo, AQUAMARINE SW 178 m cargo, STOC MARCIA 100 m tanker, plus a 12 m SAR boat). The model
   returned 3 detections, all within 311 m of an AIS position, two of them the *same* 180 m ship
   split bow/stern; it missed the second 178 m ship and the 12 m boat. A second window produced a
   **bright 85 m radar target at 12.6444E 56.4543N with no AIS transmitter of any class within
   3 km** over ten minutes (110,742 messages checked) — the product's shape is real, one target is
   not a story. `measured`
4. **The attribute head is worth having.** 100 m and tanker for a 100 m tanker; 170–175 m for a
   180 m cargo ship. Length/width are useful; vessel type was wrong on one of three. `measured`
5. **Cost and coverage, not the model, are the limits.** ~2.5 GB of imagery per target+historical
   pair, ~3 min of ingest for a 40 km window, ~2 min of inference. The stock ingest is far worse
   (whole-scene TPS warp, no output after 5.5 min per band; I replaced it with an AOI crop).
   Of the four AIS vessels the model did not report, three were simply outside the radar footprint
   — an IW swath is a ~250 km strip, so half a lon/lat box of this size can be nodata. A larger
   2,812 km² window (§2.7) gave 5 boxes, 4 after 300 m merging, 3 on valid imagery, 2 matched to
   AIS, and the same radar-only target; no moving ship was inside valid imagery to test. `measured`

## 2. Findings

### 2.1 Install

```
uv venv --python 3.12 $W/venv-t-model
uv pip install --python $W/venv-t-model/bin/python -r rslearn_projects/requirements.txt
```

Result: 5.7 GB venv, `torch 2.15.0+cu132`, `torch.cuda.is_available() == True`, device
`NVIDIA GeForce RTX 4060 Laptop GPU`. RAM was never the limit (peak ~2.7 GB per worker); GPU use
peaked at ~1.1 GB. **`requirements.txt` is incomplete**: importing the pipeline raises
`ModuleNotFoundError: No module named 'einops'` (from `rslearn/utils/raster_format.py`), and the
config parse then fails on `No module named 'scipy'`; `uv pip install einops scipy` fixes both
(`measured`).

Weights, per `docs/sentinel1_vessels.md`, public and account-free on
`storage.googleapis.com/ai2-rslearn-projects-data`: detector
`.../20260626_num_historical/data_20250521_model_20250530_satlaspretrain_unfreeze4_13_1hist/best.ckpt`
(**1,262,487,287 B**) and attributes `.../2026_09_17_vessel_attribute_l1/sentinel1_l1/best.ckpt`
(**1,157,039,279 B**). They must sit at `$RSLP_PREFIX/projects/<project_name>/<run_name>/best.ckpt`,
matching the names in the two configs (`measured`, `documented`).

### 2.2 The two blocked routes

- `python -m rslp.main sentinel1_vessels predict --tasks '[{"scene_id": ...}]'` resolves scenes via
  `rslearn.data_sources.copernicus.Sentinel1`, which reads `COPERNICUS_ACCESS_TOKEN` or
  `COPERNICUS_USERNAME`/`COPERNICUS_PASSWORD` (`documented`). Not attempted, per the
  no-credentials rule.
- `rslearn/data_sources/aws_sentinel1.py` builds `GRD/<y>/<m>/<d>/IW/DV/<product-name>/measurement/iw-<band>.tiff`
  and downloads with `ExtraArgs={"RequestPayer": "requester"}`. That key for the 2026-11-01 product
  returns **HTTP 404**; the real prefix carries a trailing hash, e.g. `..._010146_014404_DF59`.
- **Working route** (`measured`): `POST https://earth-search.aws.element84.com/v1/search` with
  `collections=["sentinel-1-grd"], ids=[...]` → `assets.vv.href` / `assets.vh.href` → rewrite
  `s3://sentinel-s1-l1c/` to `https://sentinel-s1-l1c.s3.amazonaws.com/`. One target+historical pair
  = **2.56 GB** (691,866,564 + 592,424,439 + 690,465,029 + 589,390,728 B), ~13 min at 2–5 MB/s. The
  same COGs open directly in rasterio over https (4.2 s to open) if only a sub-window is needed.

### 2.3 What I ran

Scene: `S1C_IW_GRDH_1SDV_20261101T164427_20261101T164452_010146_014404`, **2026-11-01 16:44:39 Z**,
IW GRD DV, 10 m pixel spacing, 20 x 22 m resolution. Historical reference (the model needs one to
suppress fixed structures): `..._20260926T164427_..._009621_01325E`, 36 days earlier, same satellite
and relative track, near-identical footprint — inside the pipeline's own 30–60 day search window
(`measured`).

Driver `$W/scripts/t-model/run_rslearn_fast.py` builds the rslearn dataset/window for a lon/lat box,
writes the repo's `data/sentinel1_vessels/config.json` with the right orbit direction, then calls the
repo's own `get_vessel_detections`, `run_attribute_model` and `_build_predictions_and_crops`, so the
model, normalisation (mean 0, std 250), NMS, 0.7 threshold and 0.2 km marine-infrastructure filter are
the published ones. The only replacement is `Sentinel1.ingest`, which crops my AOI out of the
downloaded tiffs while keeping the source ground control points, so rslearn still does its own TPS
georeferencing.

| Window (2026-11-01 16:44:39 Z) | Size | Valid (non-nodata) | Raw dets | After infra filter | Detector | Attributes |
|---|---|---|---|---|---|---|
| aoi3 12.60–13.20E, 56.30–56.70N (east Kattegat) | 38.4 x 45.7 km, 96 patches of 512 px | 68 % (1,186 km²) | 3 | 3 | 75.3 s | 36.5 s |
| aoi1 12.25–12.85E, 56.30–56.70N (west Kattegat) | 38.6 x 45.9 km | 52 % (923 km²) | 4 | 4 | 77.4 s | 34.0 s |

Total wall time for a run including ingest: **108 s** (log 17:02:47 → 17:04:35); ~0.8 s per
512 x 512 patch of inference. The nodata is geometry, not failure: the IW swath is a ~250 km strip,
and my ingest crop (sized by the first window) clipped the second one's eastern edge (`measured`,
zero-pixel fractions 0.48 and 0.32).

The stock ingest is the expensive part: with the unmodified `write_raster_file`, two workers ran
5.5 min at 100 % CPU, RSS past 2.7 GB, no output file — killed. Its cost scales with scene area
(26,761 x 16,688 px), not AOI area (`measured`).

### 2.4 Detections versus AIS at the image instant

Ground truth: `$W/data/t-ais-history/day_2026-11-01/classa_1630_1700Z.csv` (t-ais-history's Danish
Class A extract, 294,883 rows / 1,564 MMSI, 16:30–17:00 Z), linearly interpolated to 16:44:39 Z;
matching radius 1 km, no moving-ship shift correction (all ships here were nearly stationary).
Script `$W/scripts/t-model/ais_compare.py`.
aoi3 (`measured`):

```
4 AIS vessels at image time (0 moving >=3 kn)
  212123000 STOC MARCIA   Tanker 100 m  12.7785, 56.4883
  265048050 RESCUE LENAH  SAR     12 m  12.6253, 56.4278
  373879000 AQUAMARINE SW Cargo  178 m  12.8561, 56.6567
  538012500 STAITHES      Cargo  180 m  12.7433, 56.6044
3 detections, all matched within 1 km:
   311 m  model 170 m "tanker" 0.78 -> STAITHES 180 m Cargo
    46 m  model 100 m "tanker" 0.99 -> STOC MARCIA 100 m Tanker
   153 m  model 175 m "cargo"  0.99 -> STAITHES 180 m Cargo
UNMATCHED AIS: RESCUE LENAH (12 m), AQUAMARINE SW (178 m, inside the window)
```

So: 3 detections, 2 distinct ships, 0 false positives against AIS, 2 of 3 ships over 100 m found
(67 %), the 12 m boat not found. Two boxes on one 180 m hull is the usual bow/stern split, so a
downstream step must merge detections 100–300 m apart. Crops (`$W/data/t-model/crops_aoi3/*.png`,
128 x 128 px VV and VH) show one compact bright target against speckle — no wake, as all ships were
stopped.

### 2.5 aoi1: 6 AIS vessels, 4 detections, one radar-only target

```
4 detections, 3 matched within 1 km:
   315 m  model 177 m "tanker" 0.80 -> STAITHES 180 m Cargo
    53 m  model 100 m "tanker" 0.99 -> STOC MARCIA 100 m Tanker
   136 m  model 178 m "cargo"  0.99 -> STAITHES 180 m Cargo
UNMATCHED radar 12.6444E 56.4543N, 85 m, score 0.79
UNMATCHED AIS: HANNE (14 m fishing, 2.7 kn), CHARLOTTE THERESA (130 m tanker, 10.4 kn),
               BITONIA (100 m tanker, 10.7 kn), RESCUE LENAH (12 m SAR)
```

Three of the four unmatched AIS targets are **outside the radar data**, not missed: CHARLOTTE
THERESA and BITONIA fall outside my image crop (west of the swath edge), and HANNE's position is
961/961 zero pixels — nodata. So this window says nothing about moving ships; coverage decides, not
the detector. Only one target is genuinely unexplained: a bright return at 12.6444E 56.4543N in
valid imagery (31 x 31 px window, max 422 DN, background 0) with no **Class A** vessel within 1 km.
Whether a Class B unit was there is a separate question, answered from the raw DMA day in §2.5b.

Both windows reuse the same scenes, so they double as a stability check: the same two ships, the
same two-box split, lengths within 6 %.

### 2.5b Was the radar-only target transmitting anything at all?

I streamed the raw DMA day (`$W/data/t-match/aisdk-2026-11-01.zip`, 2.9 GB CSV) and looked for
**any** AIS transmitter within 3 km of 12.6444E 56.4543N between 16:40 and 16:50 Z: 110,742 messages
in that window (98,295 Class A, 3,703 Class B, 1,764 AtoN, 6,937 base-station), **none within 3 km**
(`measured`, `$W/scripts/t-model/ais_classb_check.py`). So a bright, ship-sized radar target in a
well-covered Danish area had no AIS of any class near it, which is the situation the product is
about. It is not proof of intent or even of a vessel: the same signature fits a moored buoy, a
non-AIS structure or a wake, and the model's 85 m length has not been checked against anything.

### 2.6 The lighter alternative

`esamoun/dark-vessel-detection` (MIT) clones and installs in seconds (`uv pip install <repo>`) and
gives a 31-subcommand `darkvessel` CLI needing no torch, GPU or network. But its shipped detector is
`BrightPixelDetector`, whose docstring says it "is a substitute, not a detector… on a real scene it
would return every bright scatterer" (`documented`). `TrainedDetector` loads a torchvision Faster
R-CNN checkpoint trained on LS-SSDD, but that checkpoint comes from your own training run; I found no
published weights link in the repo (`unverified` that none exist — the releases API rate-limited me).
Usable as a reference implementation of the georeferencing/interpolation/matching chain, not as a
ready detector.

### 2.7 Rerun on the largest useful window: 5 detections, 8 AIS vessels, no moving ships in view

Same scene, same historical image, no new downloads. To get more vessels I searched the whole
slice for a window that maximises AIS vessels x valid data, and took the best: **12.20–12.95E,
56.40–57.15N** (Swedish Kattegat coast and Gothenburg approaches), a **48.8 x 85.2 km** window,
4,158 km² of which **67.6 % (2,812 km²) is valid imagery** — the rest is outside the IW swath.
Ingest (4 AOI crops, 53 M px per band) ~110 s, detector **177 s for 209 patches of 512 px**,
attribute model 41 s, 5 raw detections (`measured`, `$W/data/t-model/run_big1.log`).

**Detections and merging.** 5 raw detections → **4 after merging any two boxes within 300 m**
(one group held two boxes, 250 m apart). 3 of the 4 lie in valid imagery; the fourth sits on
nodata at the window edge and is excluded from all rates below.

**AIS at the image instant** (Danish Class A, interpolated to 16:44:39 Z, inside the same
window): 30 vessels, of which **8 are in valid imagery**. Their distribution:

| length band | stopped <0.5 kn | 1–3 kn | moving >=3 kn | in valid imagery |
|---|---|---|---|---|
| <20 m | 1 | 1 | 0 | 2 |
| 20–50 m | 0 | 0 | 0 | 0 |
| 50–100 m | 2 | 0 | 0 | 2 |
| >=100 m | 4 | 0 | 0 | 4 |
| total | 7 | 1 | **0** | 8 |

**There were no moving ships in valid imagery at that instant.** The two ships under way inside
the window — CHARLOTTE THERESA (130 m, 10.4 kn) and BITONIA (100 m, 10.7 kn), both off the
Danish coast at 12.25–12.32E — fall **outside the swath** (nodata), and t-ais-history's 22 moving
vessels in the wider slice bbox are likewise only in the part of the bbox this pass does not
image. So this rerun cannot say anything about detecting moving ships; that question is still
open.

**Match rates** (3 radar targets in valid imagery vs 8 AIS vessels in valid imagery, script
`$W/scripts/t-model/big_eval.py`):

| threshold | radar matched | AIS matched | chance control (mean over 16 shifts, see below) |
|---|---|---|---|
| 200 m | 1/3 (33 %) | 1/8 (13 %) | 0.00 radar, 0.00 AIS |
| 500 m | 2/3 (67 %) | 2/8 (25 %) | 0.00 radar, 0.00 AIS |
| 1000 m | 2/3 (67 %) | 2/8 (25 %) | 0.06 radar, 0.06 AIS (one hit in one shift) |

By band (AIS matched within 500 m): **>=100 m 2/4**, 50–100 m 0/2, <20 m 0/2. By state:
stopped 2/7, 1–3 kn 0/1. The two matches are STAITHES (180 m cargo; 305 m to the pre-merge box,
144 m to its twin) and STOC MARCIA (100 m tanker, 53 m); the four misses (AQUAMARINE SW 178 m,
NORDIC CRYSTAL 100 m, LISTERVIK 90 m, TJALFE R 58 m) are all in valid data and all return bright
pixels when sampled — max 478, 278, 278 and 292 DN in a 31 x 31 px box against a sea background —
so those misses are the model's, not the mask's. Three of the four (NORDIC CRYSTAL, LISTERVIK,
TJALFE R) are moored within ~400 m of each other at 12.48E 56.89N, and that cluster produced no
detections at all.

**Chance control.** Every AIS position was shifted by 10 km and 20 km in eight compass directions
(16 shifts), keeping only shifted positions that land inside the window and on valid imagery
(2–7 positions survive per shift). Result: **0 radar matches and 0 AIS matches at 200 m and 500 m
in all 16 shifts**, and exactly one radar+AIS match at 1000 m in one shift (20 km, due east).
So the two real 500 m matches are not a product of target density, though with 3 targets and 8
vessels the rates themselves are only indicative. The control keeps no land mask, so it is a
nodata-only "valid sea" proxy.

**Unmatched radar targets** (no AIS within 1 km; nearest AIS of **any** class from the raw DMA
day, ±60 s of image time — 2,559 fixes in that interval: 1,980 Class A, 159 Class B, 159 AtoN,
261 base stations):

| position | score | predicted length | boxes merged | nearest AIS any class | nearest AIS, interpolated Class A |
|---|---|---|---|---|---|
| 12.6444E 56.4541N | 0.84 | 81.8 m | 1 | **9,071 m** (Class A, stationary) | 3,155 m (STOC MARCIA) |

That is the same object the smaller window flagged in §2.5b (85 m, score 0.79 that time): a
consistent, bright, ship-sized radar target with no AIS transmitter nearby, now measured with a
larger window and a higher score. The nearest-AIS figures differ because the ±60 s raw set misses
slow-reporting vessels: STOC MARCIA reports every ~3 min at anchor, so it appears in the
interpolated set but not in the raw ±60 s slice.

**What this run does and does not show.** It shows the pipeline scales to a 2,812 km² window in
5 minutes on this GPU, that detections there are few (1 per ~940 km²) and that the ones found are
mostly attributable to AIS-transmitting ships over 100 m; it also reproduces the radar-only target
independently. It does **not** give a recall estimate: 3 valid detections and 8 AIS vessels, all
stopped or drifting, cannot support one, and nothing here tests moving ships.

## 3. Source rows

| Source | Type | Regions covered | Free access route | Account needed? | What one record contains | Update rate | Delay from event to us | Position or resolution accuracy | Identifies the ship? | Licence, commercial limits | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Ai2 Sentinel-1 vessel detector (`allenai/rslearn_projects`) | ship detector (code + weights) | any Sentinel-1 IW GRD acquisition | GitHub; two `best.ckpt` on `storage.googleapis.com/ai2-rslearn-projects-data` | no | detection: projected x/y, score, predicted length/width/speed/heading/type, 128 px VV+VH crops, JSON/GeoJSON | per run | minutes of compute per scene | boxes on a 10 m pixel grid; matched AIS at 46–311 m; lengths within 6 % | yes, by content: size/type plus position to join AIS | Apache-2.0 code; weights published with the repo, no separate model licence found | measured, §2 |
| Sentinel-1 IW GRD, `sentinel-s1-l1c` (Sinergise / AWS Open Data) | SAR imagery (cloud- and dark-penetrating radar) | global land and coastal seas, **no open-ocean imaging**; 2–4 passes/day per region | `https://sentinel-s1-l1c.s3.amazonaws.com/<key>`, anonymous https, COG range reads | no | one scene, 26,761 x 16,688 px, 590–692 MB per polarisation | 12-day repeat per satellite | catalogue publication lag (not measured) | 10 m pixel, 20 x 22 m resolution | no | Copernicus Sentinel data, free and open | measured: 4 full downloads, 2.56 GB |
| Earth Search STAC (`earth-search.aws.element84.com`) | scene catalogue | global | `POST /v1/search` | no | item id, footprint, time, orbit state, asset hrefs | follows the archive | — | — | no | free, Element 84 terms | measured |
| Danish AIS archive (DMA; t-ais-history extract) | what ships *announce* (AIS, self-reported) | Danish waters + western Baltic | `http://aisdata.ais.dk/aisdk-YYYY-MM-DD.zip` | no | time, MMSI, lat/lon, SOG, COG, heading, name, IMO, type, size, draught, destination | daily file, ~3 days behind | ~1 day for the file, seconds for the fix | GPS, metres; 2–10 s under way, ~3 min at anchor | yes (MMSI, IMO, name) | DMA open data, free | measured by t-ais-history, reused |
| `esamoun/dark-vessel-detection` | reference fusion pipeline | northern Kattegat demo | GitHub | no | code, configs, docs | static (v1.0.0, 2026-09-04) | — | — | chain only; detector is a stand-in | MIT | measured: installs, CLI runs |

## 4. Consequence for feasibility

- **Radar-versus-AIS comparison in a Danish/Kattegat window is demonstrably possible with no
  accounts and no spend**, using a published model callable as a library. A 40 x 46 km window costs
  ~2 min GPU plus a few minutes of CPU prep, and the output is already what the product needs:
  targets with size, type and position, ready to join to AIS.
- **What it rules out** is treating the open model as a drop-in global service in a weekend: 2.5 GB
  of imagery per target+historical pair and minutes of ingest per scene mean you demo one or two
  windows, not a moving picture. A dark-vessel story told over one scene is honest; a service is not.
- **Weak points to state openly:** a 178 m cargo ship and a 12 m boat were missed in one window, one
  ship was double-counted, and 3 of 4 unmatched AIS vessels were outside the footprint. Claims should
  be about ships over ~100 m, with a merge step and an explicit "we do not see small craft" caveat.
- **Regions:** the model is scene-agnostic, so it inherits Sentinel-1 coverage — dense in the
  Baltic/Danish straits and North Sea, sparse at Hormuz/Natuna/Malacca open water (t-sat-access
  measured 0.5–3.0 passes/week). The same code will run on a Hormuz scene; revisit fails there, not
  capability.
- **What it gives over thresholding:** calibrated boxes plus size/type, so a radar-only target can be
  described ("~170 m, probably cargo, not transmitting AIS") before any identity work, and fixed
  structures are suppressed for free by the historical image.

## 5. Unknowns

- **Recall and false-positive rate at scale**: one scene, 4 AIS vessels, all stationary. Settle it
  with 20–40 windows over a week of Danish passes against the DMA archive (the per-scene download is
  the bottleneck).
- **Moving ships untested**: no azimuth-shift correction in the match; a 10 kn ship shifts ~300–600 m
  in azimuth (esamoun measured that correction as worth 89 of its 149 matches).
- **Nodata/edge behaviour untested**: whether the model invents detections along the nodata boundary
  of a part-covered window.
- **Historical-image dependency**: rslearn wants a same-orbit-direction scene 30–60 days earlier;
  without one, fixed structures (wind farms, platforms, buoys) will start appearing as ships. Not
  measured.
- **Weight licence** is inferred from the repo (Apache-2.0); no separate model card. If an entry
  redistributes them, ask the organisers. The Docker/FastAPI route
  (`ghcr.io/allenai/sentinel1-vessel-detection`, needs Docker + NVIDIA runtime + 15 GB shm) untested.
- **The radar-only target** needs a human look at a crop and, ideally, a second pass over it or a
  coastal-radar check, before anyone calls it a dark ship.

## 6. Sources

- `https://github.com/allenai/rslearn_projects` (Apache-2.0): `docs/sentinel1_vessels.md` (download
  and inference instructions), `data/sentinel1_vessels/config.yaml` and
  `data/sentinel1_vessel_attribute/config.yaml` (SwinB + FPN + Faster R-CNN, patch 512, batch 8,
  Normalize 0/250, threshold 0.7), `rslp/sentinel1_vessels/predict_pipeline.py` (the code path I
  called), `rslp/utils/filter.py` (0.2 km infrastructure filter, 7.2 MB public GeoJSON).
- `https://storage.googleapis.com/ai2-rslearn-projects-data/...` — the two checkpoints.
- `https://github.com/allenai/rslearn` (0.1.19, Apache-2.0): `data_sources/aws_sentinel1.py` (S3 key,
  `RequestPayer`), `data_sources/copernicus.py` (token env vars), and `utils/geometry.py` +
  `utils/get_utm_ups_crs.py` — **projection coordinates are pixels (true UTM ÷ 10)**, which silently
  breaks any attempt to feed them to pyproj (two of my runs died on this).
- `https://earth-search.aws.element84.com/v1/search`, `https://sentinel-s1-l1c.s3.amazonaws.com/`,
  `http://aisdata.ais.dk/aisdk-2026-11-01.zip` (via t-ais-history),
  `https://github.com/esamoun/dark-vessel-detection`.
- Scripts `$W/scripts/t-model/{run_rslearn_fast.py,run_rslearn.py,ais_compare.py,ais_classb_check.py,check_cov.py,dl_s1.sh}`;
  logs, detections and crops in `$W/data/t-model/`.
