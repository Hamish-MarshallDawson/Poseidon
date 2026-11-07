# t-sat-access: can we get satellite radar with no account, and what does it actually cover?

Agent: t-sat-access. Measured 2026-11-07 16:30–17:45 UTC on this machine. Jargon: **SAR** = synthetic aperture radar, an active microwave sensor that images the sea surface day or night through cloud; bright returns come from metal, hard edges and roughened water. **GRD** = ground-range-detected (the standard SAR product); **RTC** = radiometrically terrain-corrected (a GRD resampled onto a map grid). **dB** = decibels of backscatter; a calm sea sits near −22 to −18 dB, a steel ship +10 to +30 dB above that. **STAC** = a standard catalogue API; **COG** = cloud-optimised GeoTIFF, readable in byte ranges; **SAS** = a free signed URL. "Pass" = one satellite overflight; "revisit" = how often the same spot is imaged.

## 1. Bottom line

1. Sentinel-1 radar is fully usable with **no account** through Microsoft Planetary Computer: catalogue search ~1 s, and a 2048×2048-pixel sea window (about 20 × 20 km at 10 m) streams in **1.0 s** (~8 MB/s). This is the route for t-match, t-model and t-regions.
2. Use the **`sentinel-1-rtc`** collection, not `sentinel-1-grd`. The GRD assets on Planetary Computer carry **no georeferencing** (rasterio: `crs=None`, identity transform) and the STAC `proj:transform`/`proj:shape` are transposed and ~2× wrong in longitude (t-match measured this against the annotation: true 10 m = 0.000157° lon, 0.00009° lat). RTC is properly georeferenced (EPSG:326xx, 10 m, float32 linear power) and needs no correction. This one fact saves hours of mislabelled pixels; for GRD, georeference from the AWS annotation XML instead.
3. Coverage is real but uneven and much sparser than the "one image per day" pitch implies. Point coverage over 30 days (true point-in-swath, not "the box was touched"): Baltic 4.7–5.1 passes/week, English Channel 3.5, Hormuz 3.0, Gulf of Oman 1.9, Gulf of Guinea 2.1, mid-Atlantic 2.3, Malacca 0.9, **Red Sea 0.5, Natuna 0.5, open South China Sea 0**.
4. Delay from sensing to product is short: median **0.5–1.0 h in European waters, 2–4 h in the Gulf and Asia**. Longest gap at a single point is the real constraint: 4.5 days at Hormuz, 12 days at Natuna and the Red Sea sample point. So "what is happening now" works in the Baltic and the Channel; elsewhere it is "what happened in the last few days, at these few times".
5. Only 2 of 11 sample points have a Sentinel-1 pass predicted between now (Sat 16:30Z) and the Sunday 12:00 deadline: Danish straits (Sun 05:23Z) and Hormuz (Sun 02:14Z). Enough for one live end-to-end demonstration, not for a rolling picture.

## 2. Findings

### 2.1 No-account access routes, measured

| Route | Search | Asset bytes | Verdict |
|---|---|---|---|
| Planetary Computer STAC | 1.1–1.3 s for 22 items | 206, 0.28–0.39 s | **Works, fastest** |
| Element 84 Earth Search | 1.6 s for 21 items | hrefs are `s3://sentinel-s1-l1c/…`; HTTPS equivalent `https://sentinel-s1-l1c.s3.amazonaws.com/…` returned **206 anonymously** | Works, one URL rewrite |
| CDSE STAC | 1.1 s; **429 "WAF rate limit exceeded"** after ~6 rapid queries | assets `s3://eodata/…`; public mirror **403** | Catalogue only, download needs a free token |
| ASF (NISAR, Sentinel-1) | search API 200 anonymously, 2.4 s | granule HDF5 **303 redirect** (Earthdata login) | Needs a free account |
| Umbra open-data S3 | anonymous list OK; per-task STAC JSON | **206** anon, incl. a 47 GB CPHD | Works, task-based, not systematic |
| VIIRS night lights | `noaa-viirs-c2`/`-c1` buckets **404**; `eogdata.mines.edu` **302** (login) | – | Unverified; d-imagery owns it |

Working snippet (this is what I posted to shared notes):

```python
import planetary_computer as pc, rasterio
from pystac_client import Client
c = Client.open('https://planetarycomputer.microsoft.com/api/stac/v1', timeout=120)
items = [i for i in c.search(collections=['sentinel-1-rtc'], bbox=B, datetime=T, limit=200).items()]
h = pc.sign(items[0].assets['vv'].href)          # free SAS token, no account
with rasterio.open(h) as ds:                     # ds.crs = EPSG:32633, 10 m
    col = int((x_utm - ds.transform.c) / ds.transform.a)   # from pyproj lon/lat -> UTM
    row = int((ds.transform.f - y_utm) / abs(ds.transform.e))
    arr = ds.read(1, window=rasterio.windows.Window(col, row, 2048, 2048))
```

### 2.2 Pixels read, format and speed

Measured on Gulf of Finland item `S1C_IW_GRDH_1SDV_20261107T044122_…` (sensed 04:41Z, published to the catalogue and readable at 16:35Z):

- GTiff/COG, uint16, zstd, 1024×1024 blocks, 26 454 × 16 665 px, 603 MB for VV. 512×512 window 2.1 s cold, 1.1 s warm; 1024² 1.2 s; 2048² 1.0 s; ceiling ≈8 MB/s raw. (The read speeds hold regardless of georeferencing; only the *location* of a window is wrong under PC's GRD transform.)
- RTC VV (float32 linear power): median sea backscatter −22.0 dB (Gulf of Oman), −18.0 dB (Hormuz), −16.7 dB (Danish straits, wind-roughened). Land control at Helsinki: median −8.4 dB, 95 % of pixels above −20 dB — geolocation correct.
- Resolution: metadata says 10 m pixel spacing, 20–22 m resolution. A 100 m fishing boat is ~10 px; a 250 m tanker ~25 px and unmistakable; below ~20 m is not reliably separable from clutter.

### 2.3 True coverage: 11 sea points, 30 days (2026-10-08 16:30Z → 2026-11-07 16:30Z)

Method: STAC search over a ±0.06° box, then a shapely point-in-footprint test on each item's geometry, so a pass only counts if the point is actually inside the imaged swath. Delay = `s1:processing_datetime − datetime` (an upper bound on availability; the file was already downloadable then), median over the point's passes.

| Point (lon, lat) | GRD passes | Passes/week | Median delay | Max delay | Longest gap | Last pass (age at 16:30Z) | Distinct relative orbits |
|---|---|---|---|---|---|---|---|
| Gulf of Finland (24.70, 59.90) | 22 | 5.13 | 0.92 h | 1.1 h | 108.9 h | 11-07 04:41 (12 h) | 5 |
| Danish straits (12.60, 55.40) | 20 (19 unique) | 4.67 | 0.91 h | 35.6 h | 83.6 h | 11-07 05:32 (11 h) | 4 |
| English Channel (1.50, 50.80) | 15 | 3.50 | 0.74 h | 0.9 h | 60.4 h | 11-06 17:41 (23 h) | 3 |
| Hormuz (56.40, 26.60) | 13 | 3.03 | 1.98 h | 2.4 h | 108.0 h | 11-06 14:17 (26 h) | 3 |
| Gulf of Oman (57.50, 24.80) | 8 | 1.87 | 2.29 h | 2.4 h | 144.0 h | 11-06 14:16 (26 h) | 2 |
| Red Sea (39.00, 18.00) | 2 | 0.47 | 1.94 h | 2.0 h | 288 h | 11-01 03:15 (6.5 d) | 1 |
| Malacca (100.00, 3.50) | 4 | 0.93 | 3.68 h | 3.8 h | 288 h | 11-01 23:03 (5.7 d) | 2 |
| Natuna (107.00, 3.50) | 2 | 0.47 | 3.37 h | 3.4 h | 288 h | 10-29 22:39 (8.7 d) | 1 |
| South China Sea open (114.00, 12.00) | **0** | 0 | – | – | – | – | 0 |
| Gulf of Guinea (3.00, 3.50) | 9 | 2.10 | 2.32 h | 3.5 h | 155.5 h | 11-02 18:00 (4.9 d) | 3 |
| mid-Atlantic (−30.00, 40.00) | 10 | 2.33 | 0.49 h | 0.6 h | 120.1 h | 11-07 08:05 (8.4 h) | 2 |

Caveats:

- The **box** count (any pass whose swath overlaps the ±0.06° box) exceeds the point count where the swath clips a box edge: Channel 20 vs 15, Gulf of Oman 13 vs 8, mid-Atlantic 15 vs 10, Guinea 12 vs 9. So both effects the brief warns about exist; point-in-swath is the honest denominator for one point, and a 100 km-wide region gets more passes than any point.
- Each point is imaged from **several relative orbits** (1C and 1D fly interleaved tracks). Five orbits give the Finnish 5.1/week, in clusters (10-13/15, 10-19/21, 10-25/26, 10-31/11-02, 11-06/07) with 4.5-day holes: "two or three good days, then four bad ones".
- RTC trails GRD: 30-day counts 17 (Finland), 18 (Danish), 15 (Channel), 13 (Hormuz), 6 (Gulf of Oman), 2 (Red Sea), 3 (Malacca), 2 (Natuna), 0 (open SCS), 9 (Guinea), **4** (mid-Atlantic vs 10 GRD); RTC delivery median 0.74–3.74 h.
- One duplicate product in the Danish series (11-02 05:24 twice) — raw counts overstate ~5 % where swaths overlap.
- CDSE gives 23 (Finland box) and 13 (Hormuz box) against Planetary Computer's 22 and 13, so PC is not visibly missing data.
- Red Sea and Natuna at 0.5/week is the **acquisition plan**, not our access: Sentinel-1 spends its time on land, ice and European coasts, and much of the open ocean is never imaged.

### 2.4 Do ships actually show up at these settings?

Danish straits, RTC VV, 2026-11-06 16:52 UTC, 2048×2048 px (20.5 × 20.5 km) centred on 12.60, 55.40: sea background median −16.7 dB (std 2.1, wind streaks visible). A tiled local-background test (64×64 px tiles, threshold = tile median + 8 dB, blobs 6–3000 px) returned 30 candidates: the two strongest (+14.3 dB and +11.5 dB above local background, 211 and 249 px including wake) are unambiguous isolated ships in open water; roughly 28 of the remaining hits sit on one bright fixed object at the image edge (island or wind farm). Crop saved at `$WAVE/data/t-sat-access/danish_rtc_2048_detections.png`, along with `rtc_<region>.png` for five regions.

So a naive detector already finds ships and already puts most of its false alarms on fixed structures — cheap to fix, and a 20 km patch costs about a second.

### 2.5 Forecast for the demo window (16:30Z Sat → 12:00Z Sun)

Method: Sentinel-1 repeats its ground track every 12 days, so each observed pass in the last 12 days is shifted forward 12 days and kept if it lands in the window. Result: **Danish straits, Sentinel-1C, Sun 05:23Z, descending (rel. orbit 168)** and **Hormuz, Sentinel-1C, Sun 02:14Z, descending (rel. orbit 166)**. No predicted pass at the other nine points. The Danish one is the useful one: it lands about 4 h after the predicted 01:00Z publication latency and inside Danish AIS coverage. Residual timing drift of seconds to a minute per 12-day cycle is not measured here, and unscheduled acquisitions would not be predicted.

## 3. Source rows

| Source | Type | Regions covered | Free access route | Account needed? | What one record contains | Update rate | Delay from event to us | Position or resolution accuracy | Identifies the ship? | Licence, commercial limits | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Planetary Computer `sentinel-1-grd` | SAR GRD (VV+VH) | Global, land/coastal-biased | STAC + free SAS: `pc.sign(asset.href)` | No | 1 slice of one pass, 10 m px, uint16, ~26 000×16 700 | Per pass | 0.5–4 h (measured) | 10 m px, 20–22 m res; **no CRS in file**, and PC `proj:transform` is transposed and ~2× wrong in lon — georeference from the AWS annotation XML | No (a bright target) | ESA Copernicus open; PC adds no fee | measured: 1.0 s per 2048² window; `coverage.json`; corrected by t-match (shared notes) |
| Planetary Computer `sentinel-1-rtc` | SAR RTC (VV+VH) | Same, fewer scenes | Same | No | Orthorectified float32 linear power, 10 m, EPSG:326xx | Per pass | median 0.74–3.74 h | Verified correct (Helsinki land test) | No | As above | measured: `rtc_coverage.json`, `rtc_probe.py` |
| Element 84 Earth Search (`sentinel-1-grd`) | STAC over AWS `sentinel-s1-l1c` | Global | STAC anon; HTTPS object URL anon (206) | No | Native GRD tiff, needs annotation XML for georef | Per pass | hours | 10 m; georef from `annotation/iw-vv.xml` (see t-regions note) | No | AWS Open Data | measured: 21 items, HTTP 206 |
| CDSE STAC (`stac.dataspace.copernicus.eu`) | STAC catalogue | Global | Search only | Catalogue no; download yes (free token) | Item metadata; `s3://eodata` assets | Per pass | 0.5–4 h | – | No | Copernicus | measured: 22–23 items; 403 on bytes; 429 rate limit |
| ASF (NISAR L1 RSLC) | SAR, L/S band | Global (US-covered), not systematic | Search anon; data needs Earthdata | Yes | HDF5 stack, very large | Per pass | days | S-band ~10 m, L-band ~7 m (vendor claim) | No | NASA open, account-gated | measured: 303 on granule HDF5 |
| Umbra open data catalogue | SAR, ~0.25–1 m (vendor claim) | Task-based, sparse global | `https://umbra-open-data-catalog.s3.us-west-2.amazonaws.com/…` anon 206 | No | CPHD/ SICD/ GEC per task + STAC json | Irregular, on request | Days to months | Sub-metre (vendor claim, not measured) | No; length/shape only | Umbra open-data licence terms not checked | measured: bucket listing + 206 |
| NOAA VIIRS night lights (night-time boat lights) | Optical night-time | Global | Not found without account in this track | Unknown | – | Daily | – | 750 m native (documented) | No | – | unverified; d-imagery owns it |

## 4. Consequence for feasibility

- **Possible.** A live pipeline for one area: search the catalogue, sign a URL, pull a 20 km patch in a second, detect bright targets, compare with AIS. Baltic/Danish waters give 4.7–5.1 passes/week with ~1 h latency and dense free AIS — enough to show matching, unmatched radar targets and gaps for real, several times over the weekend.
- **Hormuz** is the strongest non-European case (3/week, 2 h latency, roughly 2-day cadence, worst hole 4.5 days). Gulf of Oman at 1.9/week is thin.
- **Ruled out.** Natuna, open South China Sea, the Red Sea and most of the Indian/Pacific open ocean cannot carry a "watch it happen" story: 0–0.5 passes/week and 5.7–8.7-day-old last images at the time of writing. Illegal fishing in Asia as a live demo fails on radar access alone; it could only be a historical study on 2–4 images a month, or rely on GFW/Skylight detections (5+ days old) or a paid provider.
- **Timing.** Only Danish waters and Hormuz have a pass before submission. No download or storage step is needed; the two time sinks (GRD georeferencing, fixed structures) are now known.

## 5. Unknowns

- Whether the 12-day extrapolation is right about Sunday's passes: query the same STAC search after the pass, or read an official acquisition plan (the `s1planning-catalog` bucket I tried returns NoSuchBucket; ASF's planning page answers 200 but I did not open it).
- VIIRS night lights with no account (my two bucket probes 404'd, EOG redirected).
- Umbra licence terms and true resolution (licence text not read; no GEC image opened).
- Whether RTC in Asian waters is systematically absent (2–3 items/30 d) or merely late.
- Ascending vs descending detectability (range- vs azimuth-travelling ships, along-track ambiguity, multi-pixel wake) — t-match's match-distance experiment should measure it.
- Delays are `processing_datetime − sensing`, i.e. production time; true queryable lag is probably 10–30 min larger.

## 6. Sources

- `https://planetarycomputer.microsoft.com/api/stac/v1/` — catalogue and free SAS signing; supported every pixel result here.
- `https://earth-search.aws.element84.com/v1/`, `https://sentinel-s1-l1c.s3.amazonaws.com/` — alternative anonymous route (206, 21 items).
- `https://stac.dataspace.copernicus.eu/v1`, `https://catalogue.dataspace.copernicus.eu/odata/v1` — item-count cross-check; the 403/429 findings.
- `https://api.daac.asf.alaska.edu/services/search/param?platform=NISAR`, `https://nisar.asf.earthdatacloud.nasa.gov/` — NISAR metadata anonymous, data gated.
- `https://umbra-open-data-catalog.s3.us-west-2.amazonaws.com/?list-type=2` — anonymous listing and 206 object access.
- Scripts: `$WAVE/scripts/t-sat-access/{stac_probe,asset_probe,pixel_read,rtc_and_speed,coverage,rtc_coverage,rtc_probe,danish_ships}.py`; JSON in `/tmp/tsat/`; crops in `$WAVE/data/t-sat-access/`.
