# d-imagery: what satellites can actually see

Agent d-imagery, Sat 7 Nov 2026. `measured` = I ran it; `documented` = primary source; `vendor claim`; `unverified`. Scripts: `$WAVE/scripts/d-imagery/`.

## 1. Bottom line

1. **Free radar is real, current and pixel-accessible with no account.** Sentinel-1 IW GRD (Interferometric Wide swath, Ground Range Detected — the standard 10 m radar image) is served as plain HTTPS GeoTIFFs from the AWS open bucket `sentinel-s1-l1c`. `measured`: a 500 KB range request returned HTTP 206 in 0.64 s; products for 5 Nov 2026 were present when queried on 7 Nov.
2. **Two Sentinel-1 satellites again.** `documented`: 1C (Dec 2024) and 1D (Nov 2025) reached final orbital configuration on 24 Jun 2026; 1A ended Jun 2026; one satellite = 12-day repeat, two = 6-day. `measured`: 27 IW GRD slices over the Danish straits box in the 7 days to 6 Nov 2026 (13 from 1C, 14 from 1D).
3. **It images coasts and tasked areas, not the open ocean.** `measured`: 30 days to 7 Nov 2026, scenes touching a 2°×2° box — mid-Atlantic (30W, 20N) 0, open South China Sea 0, 70E/10S 0; Hormuz 28, Natuna 6, Gotland 41. Same answer from two independent catalogues. A mid-ocean dark ship is a paid problem.
4. **Optical is plentiful but blind at night and in cloud.** `measured` Sentinel-2 L2A scenes under 20% cloud, same boxes, 30 days: Gotland 20 of 109, Hormuz 30 of 42, Natuna 15 of 93, Gulf of Guinea 11 of 61, mid-Atlantic 0. Sunlit, 10:30 local time, 5-day nominal revisit.
5. **Nothing free identifies a ship.** Radar gives position, a length estimate and a type guess. Identity enters only by matching a detection to AIS/VMS within seconds and a few hundred metres — so the match, not the imagery, is the load-bearing part.

## 2. Findings

### Radar

`measured` Planetary Computer STAC (collection `sentinel-1-grd`): per scene `sar:resolution_range` 20 m, `resolution_azimuth` 22 m, `pixel_spacing` 10 m, looks 5×1, VV+VH, platform `sentinel-1c`/`sentinel-1d`. Assets: `vv`, `vh` COGs, `rendered_preview`, `thumbnail`.

Three things a team will trip over, all `measured`:

- **AWS route needs no token but no CRS either.** `curl -r 0-500001 "https://sentinel-s1-l1c.s3.amazonaws.com/GRD/2026/11/5/IW/DV/<PRODUCT>/measurement/iw-vv.tiff"` → HTTP 206, 0.64 s, GeoTIFF. Per product 632 MB VV + 524 MB VH plus annotation/noise/calibration XML and `manifest.safe`. But these Level-1 TIFFs are in radar geometry with `crs=None` and an identity transform, so bbox→window reads fail: georeference from the `annotation/iw-vv.xml` geolocation grid (t-regions measured ~756 m p95 residual on a tie-point affine) or use RTC.
- **Planetary Computer needs a SAS step and rate-limits it.** Raw asset URLs give `HTTP 409 Public access is not permitted on this storage account`; `GET /api/sas/v1/token/sentinel-1-grd` then answers `HTTP 429 Rate limit is exceeded. Try again in 19 seconds` on repeat tries. No account, but flaky.
- **`sentinel-1-rtc` is georeferenced and keeps up**: EPSG:32634, 10 m float32 (per t-sat-access); 17 RTC scenes vs 19 GRD over Gotland in the last 14 days, newest identical (2026-11-05T04:58). Use RTC for matching.
- **One STAC item is a ~25 s slice** of a ~95 s acquisition (d-methods measured four consecutive items 16:43:37→16:44:52 on 1 Nov), i.e. 25 s of sensing over a 250 km swath, not a whole pass.

`measured` coverage, 30 days to 7 Nov 2026, scenes touching a box (IW, PC and Earth Search agreeing except Gotland 41 vs 38): Hormuz 28 (longest gap 84 h), Natuna 6 (288 h gap), Gotland 41 (84 h), Gulf of Guinea 8 (120 h), mid-Atlantic 0, SCS open 0, Indian Ocean 0. A 40°×20° Indian Ocean box gave 20 scenes in 7 days, all hugging the African coast. Coverage follows the acquisition plan, not orbital geometry; Natuna is the weak story region.

**How small a ship?** `documented`: IW GRD is "about 20 metres" resolution (xView3 technical guide); GFW says it detects most vessels above ~15 m and misses most below, and counts 20 million detections of vessels "greater than approximately 10 metres" (2022). Practically: 25 m steel hull confident, 15-20 m maybe, 10 m fishing boat luck. High sea state raises the clutter floor and hides small hulls. `unverified` in this wave: detection probability by length, wind and incidence angle.

**Sub-metre radar is not open.** `documented` (vendor): Umbra >25 cm, open-data programme on AWS is Creative Commons and needs no signup — but `measured` its STAC covers 2024-2025 only, no `stac/2026/` keys, and the newest object in a 1,000-key sample was modified 2026-02-05: a fixed set of ~20 locations plus `ship_detection_testdata`, not a live feed. Capella's open bucket is maintained: `measured` `data/2026/` prefixes through September 2026, ~1,000 collects, STAC browser at `https://capella-open-data.s3.amazonaws.com/index.html`; still opportunistic. RADARSAT-2/RCM and ICEYE are commercial. ALOS-2 high resolution is paid (`documented`, JAXA); free ScanSAR is ~100 m, too coarse.

**NISAR is new and late.** `documented` (ASF): L-band, 3-10 m, 12-day repeat, ~6-day average with ascending+descending; validated L0-L2 released 6 Nov 2026 for acquisitions from 21 Oct 2026 — ~2.5 weeks behind — and download needs a free Earthdata login. L-band is the right sensor for small hulls in wind, but not for this weekend.

### Optical, thermal, night lights

- **Sentinel-2 L2A** (`documented`, SentiWiki): 10/20/60 m, 290 km swath, 10-day single-satellite and 5-day nominal two-satellite revisit, 10:30 local time, acquisition scenario limited to land, coastal waters, islands, Mediterranean and closed seas. `measured` cloud share explains the rest (above). At 10 m a 100 m tanker is unmistakable; a 20 m trawler only in sun glint. `unverified` for our seas.
- **Landsat C2 L2** (`documented`): 30 m, ~8-day combined, free on Planetary Computer with no account; same daylight and cloud limits, coarser.
- **VIIRS boat detection (VBD)** (`documented`, NOAA/EOG): 750 m pixels, reports *lit* boats only — purse seiners, squid jinkers — so it is blind to a dark tanker and excellent for the South China Sea lit-fleet signal; nightly, NRT within ~6 h but NRT is paid and the open data are the monthly reprocessed FINAL set.
- **SDGSAT-1** (`documented`): 10 m pan / 40 m RGB night lights, the only source that could pick out individual lit hulls, but access needs registration, a proposal and a 20-image quota. Account required.
- **Thermal**: Sentinel-3 SLSTR at 1 km (free, on Planetary Computer) cannot resolve a ship; wake or plume anomalies only. Not a detector.

### Radio frequency and ready-made products

- **RF geolocation** (HawkEye 360, Unseenlabs, Kleos): trilaterates a ship's own radar/VHF emissions, so a ship that is dark on AIS but still radiating is findable. `vendor claim`, paid, no free data. One pitch sentence, nothing more.
- **Global Fishing Watch SAR presence** (`documented`): processed global layer, 2017 to ~5 days ago, API dataset `public-global-sar-presence:latest` via 4Wings, CC BY-NC 4.0, free token issued instantly. Fastest way to say "radar saw a thing here" without touching pixels, at the cost of latency and someone else's matching.
- **Skylight (AI2)** (`documented`): public map with **no login** but delayed 48 h and demonstration-only; the operational platform is free to NGOs/governments on request.
- **xView3 / SARFish** (`documented`): GFW+DIU labelled Sentinel-1 set — 991 scenes from 2020, ~60k AIS/VMS-matched and ~200k hand-labelled detections with length estimates and vessel/fishing/confidence labels. The benchmark for what a detector can do on this imagery, and the training set behind the `allenai/rslearn_projects` model.

## 3. Source rows

| Source | Type | Regions covered | Free access route | Account needed? | What one record contains | Update rate | Delay from event to us | Position or resolution accuracy | Identifies the ship? | Licence, commercial limits | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Sentinel-1 IW GRD (AWS) | C-band radar | coasts + tasked areas (open ocean measured absent) | `https://sentinel-s1-l1c.s3.amazonaws.com/GRD/<yyyy>/<mm>/<dd>/IW/DV/` | No | one 25 s slice, 250 km swath: VV+VH TIFFs, annotation/noise/cal XML, manifest | ~4 slices/day touching a Baltic 2° box | hours (median 1.2 h Baltic, orchestrator) | 20×22 m, 10 m pixels; no CRS, annotation-grid geolocation ~100s m | No | Copernicus, free/open | measured |
| Sentinel-1 GRD (Planetary Computer) | same, STAC+SAS | as above | `api/stac/v1/search` + `/api/sas/v1/token/sentinel-1-grd` | No (429s) | STAC item + COGs | hours | hours | same | No | same | measured |
| Sentinel-1 RTC (Planetary Computer) | terrain-corrected radar | global land+coast | collection `sentinel-1-rtc` | No | georeferenced COG, EPSG:326xx, 10 m float32 | hours; 17 vs 19 GRD, 14 days Gotland | same as GRD | 10 m, georeferenced | No | Copernicus | measured |
| Sentinel-1 EW | wide-swath radar | tasked ocean areas | AWS/PC as GRD | No | 400 km swath ~40 m | same | hours | 40 m | No | Copernicus | documented |
| Sentinel-2 L2A | optical, 13 bands | land, coasts, islands, closed seas | PC / Earth Search / CDSE STAC | No | 10 m tile + cloud mask | 5-day nominal | hours-days | 10 m | Very rarely (VHR only) | Copernicus | measured + documented |
| Landsat C2 L2 | optical | global land+coast | Planetary Computer | No | 30 m tile | ~8-day combined | 1-3 days | 30 m | No | US public domain | documented |
| VIIRS boat detections | night lights | global (SAA redacted) | `eogdata.mines.edu/wwwdata/viirs_products/vbd-pub/...` FINAL | No for FINAL | lat/lon, radiance, quality flag | nightly; monthly FINAL | ~6 h NRT (paid), else weeks | 750 m pixels | No | EOG/NOAA attribution | documented |
| SDGSAT-1 glimmer | night lights | global on request | sdgsat.ac.cn portal | Yes (proposal, 20-image quota) | 10 m pan / 40 m RGB scene | on request | days-weeks | 10-40 m | possibly lit hulls | research use | documented |
| NISAR L-band | radar | global land, some coast | ASF Vertex / earthaccess | Yes (Earthdata) | L0-L2, 3-10 m | 12-day repeat, ~6-day asc+desc | ~2.5 weeks | 3-10 m | No | open | documented |
| ALOS-2 PALSAR-2 | L-band radar | global on order | G-Portal free ScanSAR; AUIG catalogue | Yes | ~100 m free, high-res paid | on order | days-weeks | 3-100 m | No | paid high-res | documented |
| RADARSAT-2 / RCM | C-band radar | global on order | commercial (MDA) | Yes, paid | scenes | on order | days | 1-100 m | No | commercial | documented |
| ICEYE | X-band radar | global tasking | commercial | Yes, paid | scenes | on order | hours-days | 0.25-3 m | No | commercial | documented |
| Capella open data | X-band radar | ~1,000 collects, opportunistic | `capella-open-data.s3.amazonaws.com/index.html` | No | SLC/GEO/GEC/SICD/SIDD/CPHD | opportunistic; `data/2026/` to Sep 2026 | not current | 0.5-1 m | No | vendor open licence | measured |
| Umbra open data | X-band radar | ~20 fixed locations + ship test data | `umbra-open-data-catalog` S3 | No | GEC/SICD/SIDD/CPHD + STAC | no 2026 STAC items, newest object Feb 2026 (sampled) | stale | 25 cm-1 m | No | Creative Commons | measured |
| GFW SAR presence | processed detections | global coastal | 4Wings `public-global-sar-presence:latest` | Yes, free token | cells/date, counts, AIS match | daily | ~5 days | ~tens of m, aggregated | partly | CC BY-NC 4.0 | documented |
| Skylight | processed detections | global | public map (no login) | No for public map | vessel markers | daily | 48 h (public map) | not stated | partly | free for NGOs/govts | documented |
| xView3 / SARFish | labelled dataset | 2020 S1 sample worldwide | iuu.xview.us | No | chips + length/class/confidence labels | static | n/a | 10 m | labels from AIS/VMS + humans | public dataset | documented |
| RF geolocation | radio emissions | global | none free | Yes, paid | emitter fix | continuous | minutes-hours | ~km-sub-km | yes if beacon matches | commercial | vendor claim |
| Sentinel-3 SLSTR | thermal | global ocean | Planetary Computer | No | 1 km LST/FRP tiles | daily | hours | 1 km | No | Copernicus | documented |

## 4. Consequence for feasibility

- **Enables** pixel-level radar-vs-AIS comparison wherever ESA images a coast with an AIS archive behind it. The Baltic is the best such place on Earth (free radar density, free Danish and Finnish AIS, sanctions angle). It also enables an honest regional indicator — "radar targets in this swath, N not matched to AIS" — for Hormuz and Malacca even with no live AIS, because the imagery is free and detections are countable.
- **Rules out** any global or mid-ocean claim from free radar: the mid-Atlantic, Indian Ocean and open South China Sea had zero scenes in 30 days. High-seas transshipment and mid-ocean dark tankers need commercial SAR or GFW's lagged layer. It also rules out identifying a ship from satellite alone.
- **Regions, by evidence**: Baltic best (41 slices/30 days on a 1° box, best radar density); Hormuz strong and the best optical conditions of any box tested (28 slices, 71% of S2 scenes under 20% cloud) — which is why an energy-flow story looks good; Natuna/Malacca thin on radar (6 slices, 12-day hole) but the best *dark-fishing* story via VIIRS lights plus 20 M historic GFW detections; Gulf of Guinea thin and cloudy.
- **Best free pairing**: radar for the deliberately-dark tanker plus VIIRS lights for the lit fishing fleet — two different anomalies, one map, one honest caveat each.

## 5. Unknowns

- Detection probability by length, wind and incidence angle in our three regions — not measured here. Settle with t-match/t-model by tabulating detections against AIS-reported length.
- Whether Sentinel-1 images our regions on 7-8 Nov: query STAC for the next 24 h.
- Umbra's true freshness and whether the open programme has ended (its STAC stops at 2025; my S3 sample is partial).
- Whether Sentinel-2 sees a 20 m trawler at all in sun glint; needs a scene with a known VMS/AIS boat.
- Whether Capella's open collects include any of our waters: bbox query on its `by-datetime` STAC.
- GFW SAR end-to-end latency: docs say "5 days ago", matching the orchestrator; treat 5 days as the planning number.

## 6. Sources

- `https://sentiwiki.copernicus.eu/web/s1-mission` — modes, 20 m/400 km trade-off, 12-day/6-day repeat, <1 day Arctic and 1-3 day Europe revisit, coastal/land acquisition scenario.
- `https://sentinels.copernicus.eu/-/sentinel-1c/1d-final-orbital-configuration-achieved`, `https://www.esa.int/Applications/Observing_the_Earth/Copernicus/Sentinel-1/Facts_and_figures` — constellation dates, end of 1A.
- `https://planetarycomputer.microsoft.com/api/stac/v1/collections/sentinel-1-grd` and `/search` — item metadata, assets, 409/429 behaviour, per-box counts.
- `https://earth-search.aws.element84.com/v1` — second free STAC route, `s3://` asset form, confirming counts.
- `https://sentinel-s1-l1c.s3.amazonaws.com/...` — working no-account pixel access, file sizes.
- `https://iuu.xview.us/xview3_dataset_whitepaper.pdf` — 991 scenes, 60k auto + 200k hand labels, "about 20 metres", AIS/VMS matching.
- `https://globalfishingwatch.org/research-project-dark-vessels/`, `.../press-release/technology-highlights-hidden-vessels/`, `.../platform-update/2024-may-data-download-portal-new-dataset-released-featuring-vessel-detections-from-sentinel-1-sar/` — 15 m threshold, 20 M detections ~>10 m, 2017 to 5 days ago.
- `https://api-doc.globalfishingwatch.org/` — `public-global-sar-presence:latest`, token, CC BY-NC 4.0.
- `https://support.skylight.global/en_US/skylight-public`, `https://skylight.helpjuice.com/en_US/access-to-skylight` — no-login public map, 48 h delay, NGO access.
- `https://eogdata.mines.edu/products/vbd/` — quality flags, 6 h NRT, FINAL open, SAA redaction.
- `https://nisar-docs.asf.alaska.edu/availability-overview/`, `https://nisar.jpl.nasa.gov/mission/quick-facts/` — resolution, repeat, validated release dates, Earthdata login.
- `https://www.eorc.jaxa.jp/ALOS/en/dataset/alos_open_and_free_e.htm`, `https://gportal.jaxa.jp/gpr/information/support` — free ScanSAR only, high-res paid.
- `https://sentiwiki.copernicus.eu/web/s2-mission` — 10/20/60 m, 290 km, 5-day nominal, land/coastal/closed-sea scenario.
- `https://umbra.space/open-data/`, `https://umbra-open-data-catalog.s3.us-west-2.amazonaws.com/stac/catalog.json` — 25 cm, CC licence, no signup, 2024-2025 STAC only.
- `https://capella-open-data.s3.amazonaws.com/stac/catalog.json` — open collects, modes, 2021-2026.
- `https://sdgs.un.org/sites/default/files/2025-08/CBAS%20SDGSAT-1%20User%20Manual.pdf`, `https://www.sdgsat.ac.cn/sciencePlan/aboutPro` — registration, quota, 10 m pan / 40 m RGB.
