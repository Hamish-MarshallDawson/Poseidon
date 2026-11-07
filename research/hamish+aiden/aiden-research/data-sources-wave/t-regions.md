# t-regions: can the "dark ship" comparison work where the story is best?

Track: test Hormuz, Natuna and Malacca honestly. All times UTC; every figure is my own
measurement unless labelled `documented` or `unverified`. Scripts:
`$WAVE/scripts/t-regions/` (`inventory.py`, `georef.py`, `detect.py`, `run_windows.py`,
`longitudinal.py`, `feb_check.py`, `portwatch.py`, `gpsjam.py`); crops and JSON in
`$WAVE/data/t-regions/`, where
`WAVE=/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave`.

## 1. Bottom line

1. **Only Hormuz has enough radar for a routine comparison, and only 3 passes a week.**
   Point-in-swath STAC queries over 2026-10-09..11-07 give: Hormuz strait 13 passes
   (3.0/week, longest gap 108 h, median publish delay 2.7 h); Gulf of Oman lane 8 (1.9/wk,
   gap 144 h); Malacca **3 (0.7/wk, gap 288 h = 12 days)** at two independent lane points;
   Natuna/Anambas 4 (0.9/wk, gap 253 h); open North Natuna Sea (106.0E, 4.5N) **0 passes in
   30 days**.
2. **No free raw AIS exists in any of the three regions.** The only free AIS-derived signal
   is IMF PortWatch daily chokepoint aggregates (no account, **6 days behind**: latest
   2026-11-01). The orchestrator's AISStream test with a key (30 s, 2,165 vessels, 62 msg/s)
   saw **zero** vessels in Hormuz, the Persian Gulf, Gulf of Oman, Red Sea, Natuna and the
   open South China Sea, and **23** in Malacca-Singapore. GFW needs a token.
3. **Hormuz is no longer a "ships going dark while traffic flows" story: the strait has been
   closed to most shipping since 1 March 2026.** Measured: PortWatch transits 78.3/day
   (2026-02) → 3.2 (03) → 3.8 (10), while Malacca stays 194-244/day, so it is a Gulf-
   specific break, not a PortWatch fault. Corroborated by Brent ($71 Feb → $121 Mar →
   $107-135 Oct, FRED, no key) and by reporting of an ongoing closure.
4. **The obvious substitute test fails.** Bright-target counts in one fixed Hormuz window
   barely moved across a 95% collapse in declared transits: Feb 2026 afternoon passes 87,
   91, 94, 89, 78 (mean 87.8) vs Oct-Nov 71, 65, 69, 64, 69 (mean 67.6, −23%); the two
   night-pass geometries rose 3-5%; the ≥50 m subset fell 32%. A target count is dominated
   by anchored, fishing and small craft, not by traffic, so "radar counts vs PortWatch
   transits" is not a usable headline.
5. **Free GPS-interference data works and separates the regions cleanly.** GPSJam daily H3
   files (no account), 14 days to 2026-11-06: Hormuz + Gulf approach 5.41% of overflying
   aircraft reporting bad GPS (daily 1.1-10.6%), Danish straits 0.25%, English Channel
   0.02%, Malacca 0.00%, Natuna 0.01%. A real "invisible" layer that needs no AIS at all.

## 2. Findings

### 2.1 Route used, and the georeferencing trap

Fastest no-account Sentinel-1 GRD route (**measured**): Element84 Earth Search STAC
(`POST https://earth-search.aws.element84.com/v1/search`, `collections=["sentinel-1-grd"]`),
then rewrite the `vv` asset `s3://sentinel-s1-l1c/...` to
`https://sentinel-s1-l1c.s3.amazonaws.com/...`; anonymous range reads work (HTTP 206 on the
676 MB product). **Trap:** that bucket's `measurement/iw-vv.tiff` has `crs=None` and an
identity transform, so bbox-window code dies with `Bounds and transform are inconsistent`.
Georeference from `annotation/iw-vv.xml` instead (210 grid points, affine to UTM;
round-trip ~130 m, p95 756 m) — fine for region counts, not for metre matching.

### 2.2 Revisit and delay (30 days to 2026-11-07)

Passes are true point-in-swath queries (`intersects` = Point), not box hits. Delay = S3
`Last-Modified` of the COG we would read, minus sensing time, so it covers catalogue
publication *and* our ability to fetch.

| Region / point | items intersecting box | passes over point | /week | median delay | max delay | longest gap |
|---|---|---|---|---|---|---|
| Hormuz strait (56.50E, 26.48N) | 28 | 13 | 3.0 | 2.7 h | 21.3 h | 108 h |
| Gulf of Oman lane (57.75E, 24.75N) | 24 | 8 | 1.9 | 3.9 h | 26.8 h | 144 h |
| Malacca, Port Klang appr. (100.95E, 2.95N) | 22 | 3 | 0.7 | 4.3 h | 4.4 h | 288 h |
| Malacca mid-lane (100.60E, 3.20N) | 22 | 3 | 0.7 | — | — | 288 h |
| Natuna / Anambas (105.65E, 3.30N) | 14 | 4 | 0.9 | 3.9 h | 8.4 h | 253 h |
| Open North Natuna Sea (106.00E, 4.50N) | 14 | **0** | 0.0 | — | — | >30 d |
| Bab el-Mandeb (43.30E, 12.60N), bonus | — | 9 | 2.1 | — | — | 144 h |

Malacca is the warning: **22 products intersect the strait box, only 3 contain a sea point**
— box-based pass counts overstate usable coverage ~7x. Delay is good everywhere (2.7-4.3 h
median) but occasionally 8-27 h.

### 2.3 Real radar windows, and what a plain detector finds

Method: full-resolution VV window, DN→dB, background = 101x101 px (~1 km) mean, candidate =
7 dB above local mean and above −14 dB absolute, 8-connected blobs 5-4000 px, land masked
with `global-land-mask`, coastline fragments rejected if longer than ~450 m or touching the
inspection-box edge. Length = sqrt(area) x 9.8 m, a lower bound.

| Window (0.4° x 0.35°) | Pass | Targets | ≥50 m | ≥100 m | within 15 km of land |
|---|---|---|---|---|---|
| Hormuz strait | 2026-11-06 14:16 asc | 69 | 27 | 3 | 64 |
| Gulf of Oman offshore lane | 2026-11-06 14:15 asc | 4 | 3 | 2 | 0 |
| Natuna Sea, west of Anambas | 2026-10-29 22:38 desc | 32 | 6 | 3 | 27 |
| Malacca, Port Klang approaches | 2026-11-01 23:03 desc | 26 | 15 | 7 | 6 |
| Malacca, off One Fathom Bank | 2026-11-01 23:03 desc | 3 | 3 | 0 | 0 |

Crops show unambiguous ships: `crop_hormuz_strait_02.png` (elongated target with dark wake),
`crop_malacca_klang_00.png` (lit elongated hull), `crop_gulf_oman_lane_00.png` (ship with a
bright cross-shaped sidelobe), `crop_natuna_open_01.png` (vessel plus wake).
`crop_hormuz_strait_00.png` is a coastline that survives the land mask — coast fragments are
the main false positive, and 64 of 69 Hormuz returns sit within 15 km of a coast because
the strait is only ~39 km wide. The "Natuna" window sits over the Anambas Islands (27 of 32
near land), so it is island-coastal fishing activity, not a clean open-water test; the One
Fathom Bank window's 3 targets mean my guess at the lane there was wrong.

**Detector stability is the real caveat.** The same window on 02:06Z descending passes gives
426-453 candidates (220 of them under 10 px) and a crop that looks like bright, grainy sea;
the same geometry in February gives 431, 399, 308 and on 2026-03-01, 645. That is sea
state/incidence, not traffic: a naive count varies by 6x between pass geometries, so any
per-pass series needs a sea-state-aware threshold.

### 2.4 The AIS side: what is reachable, and the Gulf collapse

- **IMF PortWatch** (`Daily_Chokepoints_Data` FeatureServer, no account): daily transits by
  vessel type per chokepoint, latest **2026-11-01** (6 days behind). 2026 means: Hormuz
  30.3/day (tankers 16.1), Malacca 227.8 (77.0), Bab el-Mandeb 33.6, Lombok 37.0, Oresund
  42.5, Dover 167.7. **Hormuz by month**: 89.4 (2025-10) → 78.3 (2026-02) → **3.2 (03)** →
  12.9 (06, the reopening) → 3.6 (09) → 3.8 (10); Malacca never leaves 194-244/day.
- **`documented` corroboration:** closure from 2026-03-01 after US/Israeli strikes began
  2026-02-28; 57 → 4 transits by 2026-03-02; a three-week June reopening at ~28/day; IMO 88
  confirmed incidents and 24 seafarer deaths by 2026-09-30.
- **AISStream:** no key of mine; the orchestrator's sample is the evidence. Blocked without
  an account: AISHub (needs a receiver), BarentsWatch/Kystverket (Norway), DMA (Denmark),
  GFW (token), openwaters.io and ais.ariefrse.my (no open endpoint found).

### 2.5 Does "radar target counts instead of live AIS" work? Measured: no

Same 44x39 km Hormuz window, every available pass, grouped by geometry:

| Pass type | Pre-war Feb 2026 (n) | Post-collapse Oct-Nov 2026 (n) | Change |
|---|---|---|---|
| 14:16Z ascending | 87, 91, 94, 89, 78 (5) mean 87.8 | 71, 65, 69, 64, 69 (5) mean 67.6 | −23% |
| 02:14Z descending | 77, 55, 46, 93, 59 (5) mean 66.0 | 48, 64, 75, 79, 75 (5) mean 68.2 | +3% |
| 02:06Z descending (clutter) | 431, 399, 308 (3) mean 379 | 453, 426, 320 (3) mean 400 | +5% |
| 14:16Z ascending, ≥50 m only | 43, 36, 39, 38, 28 (5) mean 36.8 | 25, 21, 27, 26, 27 (5) mean 25.2 | −32% |

Declared transits fell ~95% over the same two periods; bright targets fell 0-32%. The count
measures "what floats here", mostly anchored and small craft, so it cannot stand in for
traffic. The three March passes I also ran (closure underway) sit in the same band —
2026-03-04 14:17 asc 74, 2026-03-10 14:16 asc 62, 2026-03-06 02:14 desc 37 — and the
2026-03-01 02:06 desc pass, on the very day the closure began, returned **645**. A
"density vs public reports" panel would look flat, or absurdly high, through a war that cut
traffic 95%: a damaging result, not an impressive one.

### 2.6 Free jamming/interference evidence: it exists

GPSJam daily files (`gpsjam.org/data/manifest.csv`, then
`gpsjam.org/data/<date>-h3_4.csv`; both arrive as gzip bytes with **no** `Content-Encoding`
header, so decompress by hand; columns `hex,count_good_aircraft,count_bad_aircraft`, H3
resolution 4 ≈ 1000 km²; bad% = bad/(bad+good)). 14 days to 2026-11-06:

| Region | good | bad | bad% |
|---|---|---|---|
| Hormuz + Gulf approach (55.5-58E, 24-27.5N) | 98,276 | 5,624 | **5.41** |
| Danish straits (9-14E, 54-58N) | 145,881 | 372 | 0.25 |
| English Channel (0-3E, 49-51.5N) | 230,299 | 51 | 0.02 |
| Malacca (98.5-101E, 2.5-5N) | 26,673 | 1 | 0.00 |
| Natuna / south South China Sea | 38,989 | 2 | 0.01 |

Hormuz exceeds GPSJam's 10% "high" band on 2026-11-04 (10.6%) and is above 5% on 7 of 14
days, so interference there is continuous, not a single event. Caveats: these are
aircraft-reported navigation-accuracy flags, so they bound interference *in the region*,
not jamming of a specific ship (only 6 hexes fall inside the strait box). No stated licence,
derived from ADS-B Exchange (non-commercial): cite it, do not republish the file. Nothing
here distinguishes jamming from spoofing, and AIS spoofing detection needs AIS we do not
have.

## 3. Source rows

| Source | Type | Regions covered | Free access route | Account needed? | What one record contains | Update rate | Delay from event to us | Position or resolution accuracy | Identifies the ship? | Licence, commercial limits | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Sentinel-1 GRD (C/D, IW) | radar imagery | global land+ocean, not polar | Earth Search STAC → `https://sentinel-s1-l1c.s3.amazonaws.com/...` range reads | no | 10 m VV+VH GRD scene ~250x170 km | 12-day repeat per satellite; 0.7-3 passes/wk per point measured | median 2.7-4.3 h (max 27 h) | 10 m pixel; target position ~1 px + moving-ship shift | no | Copernicus open, commercial use OK | measured |
| SAFE annotation XML | metadata | same | `.../annotation/iw-vv.xml`, same bucket | no | 210 geolocation grid points + calibration/noise | per product | same as product | tie-point affine ~130 m round-trip | no | Copernicus open | measured |
| IMF PortWatch chokepoint transits | AIS-derived aggregates | 28 chokepoints (Hormuz, Malacca, Bab el-Mandeb, Sunda, Lombok, Oresund, Dover…) | services9.arcgis.com FeatureServer query | no | daily transits by vessel type + tonnage | daily | 6 days (latest 2026-11-01) | n/a (counts) | no | IMF terms, attribution | measured |
| GPSJam daily H3 | GNSS interference | global, aircraft-derived | `gpsjam.org/data/manifest.csv` + `<date>-h3_4.csv` | no | H3 res-4 hex, good/bad aircraft counts | daily, ~04:00 for prior day | ~1 day | ~1000 km² hexes | no | none stated; ADS-B Exchange derived (non-commercial) | measured |
| FRED Brent spot `DCOILBRENTEU` | market | global | `fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU` | no | daily USD/bbl | daily | ~1 day | n/a | no | FRED terms, attribution | measured |
| AISStream | live AIS | global (claimed) | WSS + key | yes | Class A/B position + static | seconds | 3 s in orchestrator's sample | ~10-50 m | yes (MMSI) | free, no SLA | measured by orchestrator: 0 vessels Hormuz/Persian Gulf/Gulf of Oman/Red Sea/Natuna/SCS, 23 Malacca-Singapore |
| Global Fishing Watch API | AIS + SAR detections | global | REST + token | yes | presence, gap events, SAR detections | days | ≥5 days for radar layer | varies | partly | non-commercial | documented, not tested |
| Danish DMA AIS | AIS positions | Danish waters/western Baltic | `aisdata.ais.dk` daily zip | no | full position + static records | daily, 3-day lag | 3 days | ~10-50 m | yes | free, research | measured by t-ais-history |
| AISHub / BarentsWatch / openwaters / Selat | live AIS | regional | need a station, a login, or undocumented | yes | positions | seconds | unknown | unknown | yes | varies | blocked, recorded |
| Sentinel-1 SAR vessel detections (GFW) | product | global | token | yes | detection points | days | ≥5 days | ~10-20 m | no | non-commercial | documented |

## 4. Consequence for feasibility

**Hormuz — partial, as a study rather than a live product.** Radar works (3 passes/week,
2.7 h delay, 27 targets of ≥50 m in one strait window). There is no raw AIS, only PortWatch
at daily resolution and 6 days stale, so a radar-vs-AIS *matching* demo cannot be built
there on free data, and the radar-only fallback is measurably wrong (2.5). What Hormuz does
support with real numbers is a "what the transponder picture misses" study: fixed-window
radar shows 60-90 targets including 25-37 of ≥50 m while declared transits are single
digits, with 5.4% bad-GPS aircraft as an independent interference signal — and the honest
caveat that anchored and fishing vessels dominate the returns.

**Malacca — not enough for matching.** 0.7 passes/week at two lane points, a 12-day gap,
and only 23 AIS vessels in the whole Malacca-Singapore area. It is however the best
*context* story: 200-240 declared transits a day, 26 bright targets in one Port Klang
window, and ~0% GPS interference — "busy, transparent, lawful traffic", the opposite of
Hormuz. Any dark-vessel claim in Malacca would rest on 3 images a month.

**Natuna — not enough.** 0.9 passes/week over the Anambas Islands, a 253 h gap, **no passes
at all in 30 days over the open North Natuna Sea**, no free AIS, no free Indonesian VMS.
The illegal-fishing framing there is a story, not a testable claim on free data; the honest
version is "small-vessel clusters appear around the Anambas Islands four times a month,
with nothing to check them against".

**The Baltic remains the only region with all three legs** (live AIS, 4-5 radar passes/week
per point, free historical AIS). The regional contrast is worth one slide with these
measured numbers, because it shows where the method stops working. **Ruled out:** live
Hormuz or Asian scenes, radar counts as an AIS substitute, any Asia dark-vessel claim.
**Made possible:** a quantified feasibility statement plus a free GNSS-interference layer.

## 5. Unknowns

- **No AIS ground truth for any of the three regions**, so "how many Hormuz radar targets are
  dark" is unknown. Settle it with a GFW token, a longer AISStream sample over Malacca, or a
  paid trial — all need an account.
- **My detector is naive**; the 6x spread between pass geometries means the per-pass series
  needs sea-state-aware thresholds. t-match's CFAR work on Danish data is where that lands.
- **The 02:06Z excess is assumed to be clutter**, not proven; per-pass wind and incidence
  angle would settle it.
- **Malacca lane windows were guessed**; the One Fathom Bank window (3 targets) may simply be
  off the lane.
- **GPSJam licence is unstated** and its over-water aircraft coverage is thin; attributing
  interference to a date or a ship is not yet justified.
- **Hormuz presence counts are unclassified**; anchored tankers, dhows, fishing vessels and
  warships are all plausible.

## 6. Sources

- Element84 Earth Search STAC `https://earth-search.aws.element84.com/v1` — Sentinel-1 GRD
  search; assets rewritten to the public bucket.
- `https://sentinel-s1-l1c.s3.amazonaws.com/` — anonymous COG range reads,
  `annotation/iw-vv.xml`, `productInfo.json` (`sciHubIngestion`, `s3Ingestion`; sensed 14:16,
  s3 17:04 for the 6 Nov Hormuz scene). `https://planetarycomputer.microsoft.com/api/stac/v1`
  — items found, SAS sign of the mirrored blob 404s.
- IMF PortWatch `Daily_Chokepoints_Data` FeatureServer, `https://portwatch.imf.org/` —
  transits, 6-day lag, Hormuz collapse.
- `https://worldfreightmonitor.com/stories/strait-of-hormuz-closure/` — documented closure
  timeline (sourced to PortWatch, IMO, Al Jazeera);
  `https://www.iea.org/data-and-statistics/data-tools/middle-east-maritime-chokepoints-shipping-monitor`
  — documented AIS-based chokepoint tool with uncertainty caveats.
- `https://gpsjam.org/data/manifest.csv`, `https://gpsjam.org/data/2026-11-06-h3_4.csv`,
  methodology `https://gpsjam.org/faq`; `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU`
  for Brent; Python `global-land-mask` and `h3`.
