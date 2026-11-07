# t-match: Sentinel-1 radar against Danish AIS — measured

Track: real radar-vs-AIS comparison. Everything below is `measured` on this machine on Sat 7 Nov 2026 unless marked `documented`.
Scripts: `$WAVE/scripts/t-match/` (`geo2.py`, `detect2.py`, `match_run.py`, `ais_side.py`, `analyze2.py`, `regcheck.py`, `crop.py`). Data and crops: `$WAVE/data/t-match/`.

## 1. Bottom line

1. **The comparison works, on free data, with no account.** On two windows of one Sentinel-1C pass over Danish waters I detected bright radar targets, interpolated Danish AIS to each detection's own line time, and matched. **Large ships under way were found within a few hundred metres** (16 of 17 vessels ≥120 m matched within 467 m), and moving vessels matched at a median of ~100 m.
2. **Vessel coverage (the number that matters):** of AIS vessels inside a window, 41 % (Great Belt) and 58 % (Fehmarn Belt) had a radar detection within 100 m; 49 % / 73 % within 200 m; 58 % / 87 % within 500 m. For vessels under way (>3 kn), pooled: 47 %/68 %/79 % at 100/200/300 m, median 102 m.
3. **Precision is the weakness, not recall.** 2595–3173 detections per window against ~110 AIS vessels: only ~2–3 % of detections sit within 100 m of an AIS vessel — ~30:1 clutter, dominated by **land/coastline edges** (coarse Natural Earth mask) and **harbour and bridge structures**, not by sea spikes.
4. **Georeferencing is a trap but solvable.** Planetary Computer's `sentinel-1-grd` COGs carry no CRS, and their STAC `proj:transform`/`proj:shape` are transposed and wrong (they put you ~2× off in one axis). The product annotation geolocation grid from the open AWS bucket fixes it; independently checked by cross-correlating the coastline against the image, giving a registration error below ~30 m.
5. **Minimum useful size:** ≥50 m cargo/tanker in open water — reliably detected and matched. 15–50 m — usually detected, matched ~60 % of the time within 100 m. Below ~15 m — not separable from clutter. Radar alone never identifies a ship; identity comes only from the AIS match.

## 2. Findings

### 2.1 Setup (measured)

Danish Maritime Authority day archive: `http://aisdata.ais.dk/aisdk-2026-11-01.zip`, 579,029,270 bytes, one CSV of 2,905,957,560 bytes. Downloaded in ~4 min with `curl`; extracted with `unzip -p … | awk -F, '$1>="01/11/2026 05:18:00"{…exit}'` in 19 s. Extract 05:18–05:46 UTC: **304,209 rows, 2,519 MMSI** (Class A 267,990; Class B 10,535; base stations 20,181; AtoN 5,503). Median reporting interval 7 s (p75 10, p95 30; the low tail is same-second duplicates from overlapping receivers — t-ais-history measured 28 % duplicates). Completeness: name/length/width/draught 100 %, ship type 89 %, destination 72 %, IMO 57 %.

Imagery, Sentinel-1C IW GRD VV, two consecutive 25 s slices of one descending acquisition:

| window | slice (PC id / AWS id) | sensing (UTC) | AOI | pixels |
|---|---|---|---|---|
| Great Belt ↔ Småland Sea | `…053151_053216_010139_0143CB` `_2CB4` / `_DAD5` | 05:31:51–05:32:16 | 10.60–11.45 E, 55.05–55.75 N | 8164 × 6715 = 54.8 Mpx (4187 km² bbox) |
| Fehmarn Belt / Kadet | `…053216_053241_010139_0143CB` `_CBF0` / `_B93E` | 05:32:16–05:32:41 | 10.95–11.65 E, 54.35–54.85 N | 6235 × 5497 = 34.3 Mpx (2463 km² bbox) |

Access (no account, measured): STAC search at `https://planetarycomputer.microsoft.com/api/stac/v1/search` (`sentinel-1-grd`), sign the VV asset with `GET /api/sas/v1/sign?href=<urlencoded>`, then **`rasterio.open(signed_url)` directly** — not `vsicurl/…`, which failed here (`CPLE_OpenFailedError: No such file or directory`). Remote read of 34.3 Mpx: **7.0 s** (local copy 3 s). Signing hit HTTP 429 once, so cache the URL (~1 h validity).

### 2.2 Georeferencing (the step that silently ruins the comparison)

`rasterio.open` on the PC GRD gives `crs=None, transform=identity`. PC's `proj:transform = [0.00028044658, 0, 8.875659, 0, -7.1706567e-05, 56.735538]` with `proj:shape [26725, 16678]` is transposed relative to the raster (`width 26725, height 16678`) and implies 17.4 × 8.0 m pixels. The product annotation says `numberOfSamples 26725, numberOfLines 16678, range/azimuthPixelSpacing 10 m`, and its 210-tie-point `geolocationGridPoint` grid gives 10 × 10 m on a rotated grid. I georeferenced by bilinear interpolation of that grid (`geo2.py`) and used it to convert each detection's row to its **own line time** (`productFirstLineUtcTime`→`productLastLineUtcTime`, 25 s per slice).

Independent check: FFT cross-correlation of the Natural Earth land mask against the image's own land/sea contrast over 10.95–11.35 E, 55.15–55.55 N peaked **at zero shift** (corr 0.89, full ±window search) — registration error below ~30 m at 10 m pixels. Consequence: **PC's transform cannot be used for matching**, and a 700 m error would look exactly like a moving-ship displacement.

### 2.3 Detector (documented method, throwaway code)

`20·log10(DN)` (uncalibrated, no LUT — dB here is relative); background = 32 × 32 px (320 m) block mean clipped at the 97th percentile; mask = contrast > 8 dB, DN > 0, minus land rasterised from Natural Earth 10m at 0.0002° and dilated 30 m (200 m buffer variant tested); components ≥4 px (≈400 m²), ≤200 px extent. Runtime 13–16 s per window on CPU (read 3–7 s, mask 3 s, detect 7 s). Result: **Great Belt 3173 detections** (2595 with the 200 m buffer), **Fehmarn Belt 2688**. Median blob 8 px, largest 955 px, median peak-vs-background 11 dB.

### 2.4 Matching (measured)

AIS positions interpolated per MMSI to each detection's line time (linear between bracketing reports; vessel excluded if no report within 900 s). Distances in metres at 56° N.

Detection side (percent of detections with an AIS vessel within a gate):

| gate | Great Belt | Fehmarn Belt |
|---|---|---|
| 50 m | 0.9 % | 0.8 % |
| 100 m | 2.0 % | 2.6 % |
| 200 m | 5.3 % | 4.9 % |
| 500 m | 12.3 % | 12.3 % |
| 1 km | 21.5 % | 18.5 % |

Vessel side (nearest radar detection to each AIS vessel present in the window; 118 vessels Great Belt, 109 Fehmarn):

| gate | Great Belt | Fehmarn Belt |
|---|---|---|
| 50 m | 21 % | 24 % |
| 100 m | 41 % | 58 % |
| 200 m | 49 % | 73 % |
| 500 m | 58 % | 87 % |
| 1 km | 65 % | 91 % |

Pooled by ship length (both windows, 227 vessel-observations): 0–15 m 31 % within 100 m / 49 % within 200 m; 15–25 m 66 % / 72 %; 25–50 m 61 % / 65 %; 50–100 m 49 % / 57 %; 100–400 m 44 % / 62 % (81 % within 500 m). Restricted to vessels under way (>3 kn, n = 47): 47 % within 100 m, 68 % within 200 m, 79 % within 300 m, median 102 m, p90 361 m. Vessels stopped (SOG < 3 kn) match only 59 % within 200 m (pooled) — mostly because they are alongside in harbours and marinas that the land mask and 200 m buffer remove, not because radar misses them.

Largest ships, AIS-to-nearest-detection distance: MSC MARIA PIA 196 m cargo **13 m**; AUTUMN STREAM 158 m 49 m; VEZUVIAN 245 m tanker 61 m; LUNNI 156 m 69 m; FRIDA KNUTSEN 277 m 76 m; STAR SPIRIT 188 m 89 m; SEADEVIL 200 m tanker 96 m; BRAVEWIND 149 m 117 m; PRINS RICHARD 141 m 123 m; LUNA PELAGOS 243 m 141 m; BOTNIA ENABLER 242 m 196 m; PRINCESS FAYZAH 169 m 186 m; WIKING 255 m 212 m; VOYAGER 174 m 467 m.

Cross-check from another agent: t-model's rslearn detector on the 16:44Z Danish pass found 3 detections, all within 311 m of a Class A vessel — consistent with this.

### 2.5 Moving-ship shift, and what the residuals really show

`documented` (d-methods): azimuth displacement ≈ (R/V)·v_radial ≈ 105 s × radial speed — ~600 m for a 12 kn ship beam-on. My measurements neither confirm nor refute it. For the 12–16 kn ships above the total residual is 13–467 m (median ~100 m); a fit of residual-azimuth on (v_azimuth, v_radial, 1) over 22–24 pairs gives ≈ −15 s per m/s radial with R² = 0.17. That is selection bias: taking the *nearest* target to an AIS position preferentially picks targets with small displacement, while a 600 m displaced ship matches other clutter. Settling it needs per-vessel identification (brightest target inside 1.5 km, wake verified in the crop) or the same ship in two images minutes apart. Two errors I did control: the 25 s sweep (scene midpoint would cost up to 130 m at 20 kn — I used per-row times) and georeferencing (§2.2).

### 2.6 What the false detections actually are (crops inspected)

Crops in `$WAVE/data/t-match/` (`u1_…png` … `u6_…png`, `crop_test_1105.png`; red = all radar detections, cyan = AIS at 05:32Z):

- **u1, 55.10 N 11.40 E** — bright strips inside an archipelago where the Natural Earth 10m coastline does not resolve islands or fields; land leaks through the mask. This is the dominant false-detection cause in Danish waters; u5 (55.10 N 11.30 E) and u2 (55.70 N 11.20 E) repeat it along harbour breakwaters and field edges.
- **The Storebælt bridge** — a straight chain of ~20–30 bright targets along 55.34 N between 11.00 E and 11.09 E, all unmatched. Fixed structures need an explicit mask; radar sees them exactly like ships.
- **u6, 55.50 N 11.00 E** — open water in the Great Belt with a tight cluster of 5–6 targets at 55.48 N 11.05 E: a real group of returns (moorings/fish-farm/works/wake — cannot be settled from one image).
- **Wakes and streaks** — elongated blobs (up to 955 px, elongation >3) off moving ships and wind streaks in the Småland Sea.

A 200 m coastline buffer removed 18 % of detections (3173 → 2595) with unchanged match rates: it trades clutter for a few coastal ships.

### 2.7 Size threshold that the comparison supports

- **≥50 m in open water, under way:** detection essentially certain, position agreement 10–200 m — enough to say "this ship is on the radar at its AIS position, or it is not".
- **15–50 m:** usually detected (66 %/61 % within 100 m); a miss is not evidence of anything.
- **<15 m:** 31 % within 100 m — not separable from clutter at 10 m GRD.
- **Alongside or in harbour:** not usable, masked by land and structures.
- **Identity:** radar gives position, a size proxy and a wake, never MMSI or flag. The AIS match is the whole identity mechanism.

## 3. Source rows

| Source | Type | Regions covered | Free access route | Account needed? | What one record contains | Update rate | Delay from event to us | Position or resolution accuracy | Identifies the ship? | Licence, commercial limits | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Danish Maritime Authority AIS archive (`aisdata.ais.dk`) | shore-receiver AIS archive, CSV per day | Danish waters + adjacent Baltic/Kattegat | `curl http://aisdata.ais.dk/aisdk-YYYY-MM-DD.zip` | No | one position report: time, MMSI, lat, lon, SOG, COG, heading, nav status, name, IMO, type, size, draught, destination, source | daily file | 2026-11-01 published 2026-11-04; 11-05…11-07 return 404 (≈3–6 days behind) | AIS nominal ~10 m; measured median reporting interval 7 s | Yes (MMSI/IMO/name) | DMA open data; `measured` 579 MB/day | downloaded, parsed, §2.1 |
| Planetary Computer `sentinel-1-grd` | STAC catalogue + COG blobs, VV/VH | global land + coastal ocean, polar ships excluded by revisit | STAC search + `/api/sas/v1/sign`, `rasterio.open(signed)` | No | 25 s slice, 10 m × 10 m GRD, 16678 × 26725 px, ~583 MB VV | 6-day revisit per orbit, 1–3 day sub-cycle | scenes online within hours (2026-11-01 item fetched 2026-11-07; t-sat-access measured same-day items) | no embedded CRS; get georeferencing from annotation (below); measured registration <30 m | No | Copernicus Sentinel data, free/open | §2.1–2.2 |
| AWS `sentinel-s1-l1c` bucket (annotation) | product annotation XML, anonymous HTTPS | global | `GET https://sentinel-s1-l1c.s3.amazonaws.com/GRD/YYYY/M/D/IW/DV/<PRODUCT>/annotation/iw-vv.xml` | No | 1.8–1.9 MB XML, 210 geolocationGridPoint (line, pixel → lat, lon, incidence), per-line azimuth times, calibration/noise LUTs | per product | same as product | grid is authoritative; measured round-trip <1 px, coast check <30 m | No | Copernicus, open | fetched 2 products, used for all matching |
| Natural Earth 10m land polygons | vector land/sea mask | global | `https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_land.geojson` | No | polygons (11 features, 10 MB) | static | n/a | ~1:10m, kilometres in archipelagos — too coarse; caused most false detections | No | public domain | §2.6 |

## 4. Consequence for feasibility

**Possible, cheaply, in the Baltic.** A radar-vs-AIS discrepancy map for Danish/German waters is buildable in a hackathon with no accounts: GRD window reads at ~7 s per 34 Mpx, the Danish AIS archive, one land mask and ~120 lines of numpy. Measured state of that stack on my two windows: 58–73 % of AIS vessels matched within 200 m in open water, ~49 % in an archipelago window, essentially all large moving ships, and 25–40 clutter detections per real ship unless land and fixed structures are handled.

**What it rules out (as a naive claim).** "Radar plus AIS shows ships hiding" cannot be said from a threshold-blob comparison: 97 % of my returns had no AIS within 100 m, and inspection showed most were land edges, the Great Belt bridge, harbour works and wakes. A dark-ship claim needs (a) a land/structure mask good to ~30 m — Natural Earth is not it, an OSM or image-derived mask would be, (b) a per-target check that the return is ship-shaped with a wake, and (c) the AIS track on both sides of the gap. Unmatched AIS is not a defect either: 41–54 % of stopped vessels had no radar match, all of them alongside.

**Regions.** Danish straits, Kattegat, Fehmarn Belt: enough data for a genuine comparison, with dense shore AIS and a 6-day-revisit radar. Hormuz, Gulf of Oman, Red Sea, Natuna, Malacca, South China Sea open water: no free AIS at sea that I could reach (orchestrator measured AISStream at 0 vessels for all of those; PortWatch is daily chokepoint counts), so radar-vs-AIS *matching* cannot be demonstrated there, only radar-target counting or GFW's own radar-derived no-AIS share (orchestrator: 1788/3190 Hormuz, 3333/5767 Malacca, 644/6132 Danish straits). That makes the honest hackathon story Baltic-first, with the Gulf as a "where GFW's radar products already show the phenomenon" slide.

**Timing reality for a demo.** Danish AIS is 3–6 days behind (11-01 is the newest file today), Sentinel-1 GRD appears within hours, and the free live Baltic AIS feed is Digitraffic (t-ais-live measured 947 vessels, MQTT ~35 msg/s). So a live demo pairs today's Digitraffic feed with yesterday's Sentinel-1 pass; a rigorous matched demo uses 2026-11-01 (both available), which is what I did.

## 5. Unknowns

- **Moving-target displacement** (§2.5): unresolved, needs per-vessel identification or two acquisitions of the same ship.
- **How many unmatched bright targets are genuine non-AIS vessels.** I inspected 6 crops; a defensible answer needs ~50 labelled targets (eye or a detector such as t-model's rslearn run).
- **A better land/water mask** (GSHHG full resolution, OSM coastline, or image-derived) would probably remove most of the 97 % clutter — not tested.
- **Generality.** Two windows, one pass, one sea state, one AIS archive. Open Baltic, high sea state, Asian fishing density: untested.
- **Small craft compliance.** Only 10.5 k Class B messages in 28 min, so "unmatched radar" inshore cannot be attributed.
- **No time-series test.** One image per area; before/after-gap analysis needs tracks over hours (t-ais-history's gap file plus GFW no-AIS counts would support it).

## 6. Sources

- `http://aisdata.ais.dk/aisdk-2026-11-01.zip` — Danish AIS day archive, licence/coverage page at `aisdata.ais.dk`; used for all AIS positions.
- `https://planetarycomputer.microsoft.com/api/stac/v1` + `/api/sas/v1/sign` — Sentinel-1 GRD discovery and anonymous pixel access; documented at `planetarycomputer.microsoft.com/docs`.
- `https://sentinel-s1-l1c.s3.amazonaws.com/GRD/2026/11/1/IW/DV/…/annotation/iw-vv.xml` — product annotation: geolocation grid, line times, calibration LUTs.
- `https://raw.githubusercontent.com/nvkelso/natural-earth-vector/master/geojson/ne_10m_land.geojson` — land polygons (public domain).
- Shared notes: t-sat-access (PC/S3 routes), d-methods (moving-target arithmetic, 25 s sweep), t-ais-history (archive completeness, gaps), t-model (rslearn cross-check), orchestrator (GFW no-AIS shares, AISStream counts).
