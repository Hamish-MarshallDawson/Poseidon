# t-ais-history: archived AIS and free regional time series

Checked Sat 7 Nov 2026, 16:30–17:25 UTC, UK connection, no accounts used. Every number is `measured` unless marked. Scripts `$WAVE/scripts/t-ais-history/`, downloads `$WAVE/data/t-ais-history/` (nothing in the repo).

## 1. Bottom line

1. **Denmark's free AIS archive works and is better than expected.** `http://aisdata.ais.dk/aisdk-2026-11-01.zip` = 579 MB zip, 3.4 GB CSV, **15,981,609 rows, 3,778 MMSI, 2,440 Class A vessels with >2 fixes**, characterised in one 15.5-minute stdlib-Python pass. Extent **53.74–58.66 N, 2.63–16.53 E** (Danish waters, Kattegat, western Baltic, a slice of the North Sea; **not** the Gulf of Finland). ~**3 days** behind. Monthly files go back to at least **2007** (≈10–13 GB each), so a multi-year backtest is possible.
2. **Reporting is dense and identity is mostly complete:** median 10 s between Class A fixes (p10–p90 5–39 s); name 91%, IMO 61.5%, ship type 89%, draught 78%. Enough to join by IMO as well as MMSI, and to interpolate to an image time.
3. **In Danish waters a silence is mostly a reception artefact.** 1,407 silences ≥20 min that started while moving (583 vessels) — but they start in the *emptiest* cells, and the median ship moves 4.6 nm across its gap, i.e. it was simply not heard. The naive "gap = hiding" reading fails here, measurably.
4. **The 31 `mare.shadow` tankers in Danish waters on 1 Nov were transmitting perfectly** — name, IMO, type, draught, destination all present, 10 s interval, most with no gap. The visible anomaly is **identity**: 16 of the 74 OpenSanctions-matched vessels broadcast a name matching no listed caption (STAVROLIT vs ZENTURO, KASTOR vs SPIRIT 2, HELION vs COSMO SAIL…). Name mismatch is the join worth building on.
5. **PortWatch is free and daily but 6 days stale, and Hormuz is now a collapse, not a trickle of hiding.** Hormuz transits fell 78.3/day (Feb 2026) → 3.2/day (Mar) → 1–4/day since, matching press coverage of the Iran war that began 28 Feb 2026. Any Hormuz radar-vs-AIS test now compares radar with **1–4 AIS contacts a day**.

## 2. Findings

### 2.1 Danish Maritime Authority archive (only no-account AIS history in the Baltic)

`curl -I http://aisdata.ais.dk/aisdk-2026-11-01.zip` → `200`, `Content-Length: 579029270`, `Last-Modified: Wed, 04 Nov 2026 00:17:08 GMT`. One CSV per day, 3.4 GB, 26 columns, `# Timestamp` as `dd/mm/yyyy hh:mm:ss`, `Unknown`/`Undefined` for absent values, rows time-sorted. Full script `dma_day.py`, one streaming pass.

**Depth (measured HEADs):** daily zips at bucket root from `aisdk-2025-02-27`; earlier data monthly under a year prefix — `2007/aisdk-2007-06.zip` 200, `2010/aisdk-2010-01.zip` 200 at 11,444,735,497 bytes, `2010-05` 13.3 GB, `2015-06` 200, `2024-01` 200; `2006-01` 404.

| Measure | Value |
|---|---|
| Rows parsed | 15,981,609 (0 bad timestamps) |
| Message classes | Class A 14.08 M msgs / 2,558 MMSI; Base Station 1.01 M; Class B 0.59 M / 946 MMSI; AtoN 277 k |
| Ship types (Class A) | Cargo 624, Fishing 355, blank 275, Tanker 237, Passenger 236, Other 146, Tug 133, SAR 82, Pilot 65, HSC 62 |
| Per-vessel median interval | p10 7 s, **median 10 s**, p90 180 s; 241 vessels (9.9%) >180 s, 93 >600 s |
| Duplicate (MMSI, same second) rows | 6,194,835 = **28.0%** — multi-receiver overlap; de-duplicate before computing rates |
| Unparseable positions | 60,995 rows (0.38%) |
| Identity: name / IMO / type / length / draught / destination | 90.7 / 61.5 / 88.7 / 89.2 / 77.8 / 78.4 % |
| Rows outside 53–58.5 N, 7.5–16 E | 409,794 (2.6%) |

**Position quality.** No ground truth in the file, so I used implied speed over 181,647 consecutive-fix pairs (16:30–17:00 window): median 1.9 kn, p90 14.9, p99 36.7, max 9,428. 0.78% of pairs imply >40 kn, 0.21% >100 kn — single bogus fixes (MMSI 246843000 jumps 18.3 nm in 7 s). At ≤12 s spacing the 95th percentile is 19.2 kn, i.e. tens of metres of jitter over real motion. Practical: good enough for a few-hundred-metre gate, but a speed gate is needed to drop gross errors.

**Gaps** (silence starting while moving ≥3 kn): ≥20 min **1,407 events / 583 vessels**; ≥30 min 952; ≥1 h 534; ≥3 h 180; ≥12 h 10. Median 42 min, longest 1,093. 1,276 Class A, 480 Cargo, 425 untyped, 125 Tanker; start speed median 8.7 kn (40% above 10 kn); displacement across the gap median 4.6 nm, p90 22.0, max 276.9. **Density check** against 30-minute traffic per 0.1° cell: (54.2 N, 9.6 E) 37 gap starts vs 198 messages; (54.0 N, 9.3 E) 23 gaps vs 0 messages; the busy exception is Copenhagen/Øresund (55.7 N, 12.6 E, 42 gaps, 1,408 messages) = berths. So gaps mean "edge of reception" or "alongside" — the failure mode GFW's ≥50 nm-from-shore rule exists to exclude, and the Danish straits have no such water.

**Second-day check.** The same test on 2026-11-03, streaming the first 160 MB of the zip (raw-deflate slice covering 00:00–07:05 UTC, 4.66 M messages, 2,786 vessels), gives 242 gaps ≥20 min, **69% of gap starts in cells with <500 messages in the same slice**, top cells again 54.2–54.4 N / 9.5–10.1 E and 56.0 N / 6.9 E. The pattern reproduces.

**OpenSanctions join** (`index.json` → `maritime.csv`, 5,163,124 bytes, 20,989 `VESSEL` rows; 6,923 with MMSI, 9,453 with IMO):

- 74 of 2,440 Class A vessels matched (3.0%), MMSI first then IMO. Strongest tag: `mare.shadow` 31, `sanction`-only 1, `mare.detained`-only **14**, other 28 — detentions must be filtered (Hamish's warning reproduced).
- The 31 shadow vessels are all tankers (MID 273 Russia ×13, 667 Gabon ×6, 461 Comoros ×3, 636, 314…), static data complete for 31/31, median interval 10 s, 9 with zero gaps.
- **16 of 74 broadcast a name absent from the list**: STAVROLIT (ZENTURO), REDUT (ZHUO YUAN), KASTOR (Spirit 2), HELION (COSMO SAIL), FORPOST (LAHAR / SAI BABA), LUCKY ALISA (DA YING), URSA MINOR (INTERLINK NOBILITY). Renaming is detectable in one free day of data.
- 578 Class A vessels doing ≥5 kn stopped reporting before 22:00 UTC; 28 are list-matched. Honest label: "left coverage, entered port, or fell silent".
- **OFAC SDN cross-check** (`treasury.gov/ofac/downloads/sdn.csv`, no account, 19,563 rows, 1,565 vessel IMOs in the remarks text): 9 of 1,503 AIS vessels with an IMO are on SDN and **all 9 are already in the OpenSanctions match** — the second list adds no recall here.

**Density where t-match needs it.** In the Kattegat AOI (12.25–12.85 E, 56.30–56.70 N) the 30-minute window has 739 Class A rows for **6 vessels, 2 moving**; per image time 2–5 of the 6 have a fix within 60 s (median staleness 11–64 s). The wider 16:44:27 slice footprint (12.16–16.73 E, 55.97–57.86 N) has 69 vessels, 22 moving, 53–56 of 69 within 60 s (median 4–7 s). A small Kattegat crop is honest but thin.

### 2.2 PortWatch chokepoints (free, no account, 6-day lag)

`https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Chokepoints_Data/FeatureServer/0/query`, paged 1,000/row. Measured: 28 chokepoints × 1,036 daily rows = 80,136, **2024-01-01 to 2026-11-01**; today 2026-11-07 → **6-day lag** (portwatch.imf.org says weekly, Tuesdays).

Hormuz monthly mean transits: 2026-02 **78.3** → 2026-03 **3.2** → 2026-04 7.1 → 2026-08 4.7 → 2026-10 3.8; 2026-11-01 = 1 (1 tanker). Tankers 43.5/day → 0.7–1.9/day. Independent reporting of the war that began 28 Feb 2026 agrees within a factor of ~2 ("barely six vessels per day in March", Bloomberg 30 Mar 2026; "144 crossings in March, −95%" per Kpler, Xinhua 24 Mar 2026), so this is real, not a feed fault. Kerch Strait fell from ~11–16/day to 0.0–0.2/day from Aug 2026 (consistent with Lloyd's List on record AIS gaps); Malacca (223.9/day mean 2026) and Øresund (41.2/day) unchanged.

**Brent link.** Free daily Brent, no key: `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU` — 9,122 observations, 1987-05-20 to 2026-11-03 (4-day lag). Raw co-movement with Hormuz transits over 718 overlapping days: same-day **r = −0.638**, lag profile peaks at +1 to +5 d (−0.644 to −0.652), decays to −0.56 at 40 d. Split the sample and it vanishes: **2024–2025 r = +0.168**, 2026-02 onward −0.589. So the correlation is one regime break (war → transits fall, price rises), with no lead. Raw relationship only; not a trading claim.

### 2.3 NOAA MarineCadastre (US archive)

`https://coast.noaa.gov/htdata/CMSP/AISDataHandler/<year>/AIS_<year>_<mm>_<dd>.zip`, no account, range requests `206`. Measured: 2023 all ×2 probes 206; **2024-07-01 … 2024-12-31 all 206**; 2024 months Jan–Jun probed 404; 2025 and 2026 all 404. One day ≈306 MB (`AIS_2024_12_31.zip`, 305,885,964 bytes). This corrects the shared note that all 2024 files 404 — H2 2024 exists. Archive stops **2024-12-31 (~22 months stale)**, so useless for a current event; d-ais's content measurements (8.35 M rows/day, 21,116 MMSI, `TransceiverClass`, IMO 58%) apply.

## 3. Source rows

| Source | Type | Regions covered | Free access route | Account needed? | What one record contains | Update rate | Delay from event to us | Position or resolution accuracy | Identifies the ship? | Licence, commercial limits | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Danish Maritime Authority AIS history | shore-AIS archive | Denmark, Kattegat, western Baltic, 53.7–58.7 N / 2.6–16.5 E | `http://aisdata.ais.dk/aisdk-YYYY-MM-DD.zip`; monthly under `YYYY/` | No | time, MMSI, lat/lon, SOG, COG, heading, nav status + static fields (name, IMO, callsign, type, size, draught, destination) | 1 file/day | ~3 days | 10 s reporting; tens of metres jitter; 0.2% gross outliers | Yes: name 91%, IMO 61.5% | none stated on DMA pages (unresolved); http only | measured, 15.98 M rows 2026-11-01 |
| OpenSanctions maritime CSV | sanctions/identity list | global | `dataset index.json` → artifact URL | No | name, IMO, MMSI, flag, risk tags, source datasets | daily | same day | n/a | Yes | CC BY-NC 4.0 (Hamish verified) | measured: 20,989 vessels, 74 matched |
| IMF PortWatch Daily Chokepoints | derived AIS aggregate | 28 chokepoints | ArcGIS FeatureServer query | No | daily transit calls by ship category + capacity | weekly (Tue) | 6 days | chokepoint count only | No | attribute (portwatch.imf.org) | measured: 80,136 rows |
| FRED Brent `DCOILBRENTEU` | price series | global | `fredgraph.csv?id=DCOILBRENTEU` | No | daily spot price USD/bbl | daily | 4 days | n/a | n/a | FRED terms | measured: 9,122 obs |
| NOAA MarineCadastre US AIS | shore-AIS archive | US coasts, inland | `coast.noaa.gov/htdata/CMSP/AISDataHandler/` | No | position reports, `TransceiverClass`, IMO in 58% | daily files, ends 2024-12-31 | ~22 months | as AIS | partly | US open data | measured: 206 on 2023 + H2-2024, 404 on 2025/26 |
| OFAC SDN list | sanctions list | global | `treasury.gov/ofac/downloads/sdn.csv` | No | name, programme, remarks holding `Vessel Registration Identification IMO …` | as published | same day | n/a | Yes, IMO in free text | US public domain | measured: 19,563 rows, 1,565 vessel IMOs |
| CetaHAV open AIS API | live AIS aggregator | Baltic-wide | `cetahav.org/api/public/v1/ais` | No | GeoJSON point: mmsi, name, sog, cog, heading | ~1 min | seconds (shallow test) | as AIS | partly (mmsi/name only) | 20 sources with attributions at `/sources` | measured: 200, 59 vessels, 9.6–25.0 E / 54.3–65.0 N |

## 4. Consequence for feasibility

- **For the Danish straits, the AIS half of a radar-vs-AIS comparison is solved with no account.** A 30-minute extract for the 1 Nov Sentinel-1C pass (16:30–17:00 Z, 294,883 Class A rows, 1,564 vessels) is already on disk at `$WAVE/data/t-ais-history/day_2026-11-01/classa_1630_1700Z.csv` and posted for t-match; at a 10 s median interval an image time usually falls between two fixes, so interpolation is short-range.
- **It rules out two easy claims.** (a) Point dark-detection in Danish waters: gaps sit at the coverage edge and alongside, and 12 h/50 nm criteria yield nothing there. (b) "Sanctioned ships hide": the shadow tankers broadcast full identity. What survives is *identity* analysis (AIS name vs list, IMO/flag swaps) and behaviour *ranking* — not a Baltic "went dark" claim.
- **Hormuz is a different story than first sketched:** almost no AIS left (1–4 transits/day, matching press), and PortWatch 6 days late. Radar can count hulls there; it cannot be compared with "hundreds of announcements". Any Hormuz claim has to be radar counts against its own history.
- **Region ranking for AIS history:** Danish straits **enough** (free, dense, identity-rich, 3-day lag); rest of the Baltic **partial** (no free archive; Gulf of Finland history only by self-recording Digitraffic); US **partial but stale** (to 2024-12-31); Hormuz / Red Sea / Natuna / Malacca **no free AIS history at all** — PortWatch is a daily count, not positions.

## 5. Unknowns

1. **DMA licence**: no terms, no attribution requirement stated; only contact `sifa@brs2.dk`. Redistribution is **unknown** — keep data out of the repo and download at demo time. Settle by emailing DMA.
2. **Ground-truth accuracy** is not in the file; my jitter figure mixes real motion and GPS noise. Settle against a moored AtoN with known coordinates (20 minutes, not done).
3. **PortWatch internals**: whether `n_total` counts all AIS classes and how it treats ships going dark mid-chokepoint is undocumented in what I read; treat counts as indicative.
4. **One full day plus one 7-hour slice.** Ten DMA days would cost ~2.5 h of streaming; the monthly files from 2007 make a multi-year base rate possible at 10–13 GB/month. The gap clustering reproduces on the second day, but the day-to-day variation of every other count here is unmeasured.
5. **CetaHAV** was tested with one call; freshness and coverage need a 15-minute watch like t-ais-live's.

## 6. Sources

- `http://aisdata.ais.dk/` + `aisdk-2026-11-01.zip` — all archive measurements; S3 listing for depth.
- `https://www.dma.dk/safety-at-sea/navigational-information/ais-data` — DMA's free-data statement (via Hamish's report).
- `https://data.opensanctions.org/datasets/latest/maritime/index.json` → `maritime.csv` — sanctions join.
- `https://services9.arcgis.com/weJ1QsnbMYJlCHdG/arcgis/rest/services/Daily_Chokepoints_Data/FeatureServer/0/query` and `https://portwatch.imf.org/pages/data-and-methodology` — PortWatch series and its update cadence.
- `https://fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU` — Brent.
- `https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2024/index.html` + direct zip probing — US archive extent.
- `https://www.treasury.gov/ofac/downloads/sdn.csv` — SDN cross-check.
- `https://cetahav.org/api-docs` — Baltic live AIS and source list.
- Bloomberg 2026-03-30, Bloomberg 2026-03-27, Xinhua 2026-03-24 (Kpler), Lloyd's List 2026-03-02 — independent confirmation the Hormuz collapse is real; Lloyd's List Intelligence on Kerch AIS gaps.
