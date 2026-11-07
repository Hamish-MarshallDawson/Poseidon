# 02: Historical data, labels and licences

Checked Sat 7 Nov 2026, ~16:00. Live tests were run from a UK connection. Downloads are in the session scratchpad, not the repo.

## 1. Verdict: AMBER

The data sources exist, are free, and work. But the **6-hour "go dark" forecast cannot be honestly trained and evaluated** from them in ~17 hours. The DMA data covers Danish waters only (not the Gulf of Finland), the latest file is 3 days old, and true intentional gaps are rare. The OpenSanctions file has no dates in its CSV, and only 25 MMSI-bearing vessels have a usable listing date in the full data.

Workaround: build the **gap detector plus a risk-score ranking** (labels = OpenSanctions "shadow fleet" flag, validated on DMA), and label the forecast honestly as a heuristic. Details in section 4. Both licences (GFW, OpenSanctions) are CC BY-NC 4.0. A non-profit student demo fits that, with attribution and one caveat (section 4, Q6).

## 2. Claims table

| # | Claim | Status | Evidence | Note |
|---|---|---|---|---|
| 1.11 | DMA publishes free daily historical AIS CSVs, ~0.5 to 2.6 GB/day | **partly** | https://www.dma.dk/safety-at-sea/navigational-information/ais-data ; bucket listing http://aisdata.ais.dk.s3.eu-central-1.amazonaws.com/?delimiter=/ | Free and daily: yes (page: "You can get access to continuously updated historical AIS data for free"). Now served as **zips of 0.50 to 1.04 GB (mean 0.66 GB)**, not 0.5 to 2.6 GB. The unzipped CSV for 3 Nov 2026 is 3.36 GB. The 2.6 GB figure matches older 2023 files. Location moved: old `web.ais.dk/aisdata/` has an **expired TLS certificate**; use `http://aisdata.ais.dk/` (an S3 bucket). Only 616 daily zips are listed (2025-02-27 to 2026-11-04). Latest file is ~3 days old: a file appears 2 to 3 days after its date. No licence terms on the DMA page. |
| 1.12 | OpenSanctions maritime CSV ~4.9 MB, has `imo`, `mmsi`, `flag`, `risk`, `datasets`, `aliases`; daily; CC BY-NC 4.0 | **confirmed** | https://www.opensanctions.org/datasets/maritime/ ; https://data.opensanctions.org/datasets/latest/maritime/index.json | Real size 5,163,124 bytes (4.92 MiB). Columns: `type, caption, imo, risk, countries, flag, mmsi, id, url, datasets, aliases`. Daily frequency stated. Note the `latest/.../targets.simple.csv` path 404s: get the URL from `index.json` (`resources[0].url`, currently `https://data.opensanctions.org/artifacts/maritime/20261107150307-kpx/maritime.csv`). |
| 1.13 | GFW tokens issued instantly on registration; free for non-commercial use | **confirmed** | https://globalfishingwatch.org/our-apis/documentation/docs/authentication ; https://globalfishingwatch.org/our-apis/documentation/docs/license-rate-limits | Needs a GFW account. "Tokens are issued instantly and do not expire." Up to 5 tokens per user. Not tested (no sign-up allowed). |
| 1.14 | GFW SAR detections matched/unmatched to AIS, 2017 to ~5 days ago; PNG tiles | **partly** | https://globalfishingwatch.org/our-apis/documentation/docs/v3/general-api-doc/key-concepts | Dataset `public-global-sar-presence:latest` v5.0, "2017 to 5 days ago" confirmed. Matched/unmatched split and PNG tiles not seen on the pages I could fetch (4Wings page not re-fetched). Treat as unverified. |
| 1.15 | GFW vessel presence 2012 to ~4 days ago | **confirmed** | same key-concepts page | `public-global-presence:latest`: "from 2012 to 96 hours ago", one position per hour per vessel. |
| 1.16 | GFW calls a gap intentional only if >= 12 h, starts >= 50 nm from shore, in good reception | **confirmed (with extras)** | https://globalfishingwatch.github.io/GFW_technical_documentation/files/gaps.html (now returns 404; read via search excerpt of the same doc) | Filters also need reception quality > 10 positions/day at the gap start and >= 14 satellite positions in the 12 h before. Reason given: >99% of terrestrial AIS messages are within 50 nm of shore, and 12 h is the peak of satellite-coverage gaps. The gap-events API dataset `public-global-gaps-events:latest` is described as **prototype stage** with no stated latency. |
| 1.20 | EIA publishes weekly crude imports/exports via a free API | **partly** | https://www.eia.gov/opendata/ ; `https://api.eia.gov/v2/petroleum/move/wkly/` | Live call returned `API_KEY_MISSING: Please register for one`, so the v2 API is real and a (free) key is needed. The Open Data page says the Petroleum "Imports/exports and movements" route "includes weekly imports and exports". Exact series IDs untested (key required). The registration page returned HTTP 503 from here. EIA is US data, so it is background for the Hormuz extension only. |

## 3. Live test results

### OpenSanctions maritime CSV (run on `maritime.csv`, 7 Nov 2026)
Method: `curl` the artifact URL from `index.json`; parsed with Python `csv`.

| Measure | Value |
|---|---|
| Rows | 23,833 (20,989 `VESSEL`, 2,844 `ORGANIZATION`) |
| Vessels with an IMO | 20,147 |
| **Vessels with an MMSI** | **7,341** (35%); 396 have several MMSIs joined by `;` |
| Vessels with an MMSI starting 273 (Russian MID) | **752** |
| Vessels with flag `ru` | 1,120 (750 of them have an MMSI) |
| Vessels with an MMSI and flag in a commonly used flag-of-convenience set (pa, lr, mh, km, cm, ga, sl, tg, bb, vc, gm, cw, ae, hk, cn, tz, ck, pw, sg, mt, cy; my own list) | 4,696 |
| Top flags among MMSI vessels | pa 1,777; lr 859; ru 750; mh 547; sl 202; hk 193; mt 160; sg 158; bb 147; cm 144 |
| `risk` tags (vessels) | mare.detained 7,585; sanction 5,456; poi 1,488; **mare.shadow 896**; reg.warn 777; blank 6,313 |
| Main source datasets (vessels) | tokyo_mou_detention 6,037; ext_tokyo_mou_psc 4,492; us_ofac_sdn 1,570; ua_war_sanctions 1,488; eu_sanctions_map 866; kp_rusi_reports 766; eu_journal_sanctions 750; gb_fcdo_sanctions 683 |
| Sanctioned vessels with an MMSI | 873 of 5,456 |

Key point: **this is not a pure sanctions list.** Over a third of vessels are port-state-control detentions (Tokyo MoU etc.), which are not shadow fleet. Filter on `risk` containing `sanction` or `mare.shadow`. Only ~870 sanctioned vessels have an MMSI, so you can match only those on AIS by MMSI. The rest need an IMO match (AIS static messages carry IMO).

### Designation dates (open question 3)
Method: downloaded `https://data.opensanctions.org/datasets/latest/maritime/entities.ftm.json` (139 MB; the server ignored my range request, so I fetched all of it) and parsed it.

- **The CSV has no dates.**
- The full JSON has `Sanction` records linked to each vessel. Relevant fields: `listingDate` (25,905 records across all entities), `startDate` (30,596). Among the **2,944 sanction records attached to vessels, only 721 carry a date** (323 `listingDate`, 607 `startDate`, some overlap). Dates range 2016-05-18 to 2025-03-04, median 2024-12-17; 297 in 2025 and 268 in 2024.
- **Only 25 of those dated vessels have an MMSI.** The entity-level `first_seen` is just when OpenSanctions first crawled it (coverage starts 2025-04-01), so it is useless as a designation date.
- Caveat: the JSON has 3,701 `Vessel` entities, while the CSV has 20,989 vessels. I did not reconcile the two; the JSON seems to be a narrower selection.
- Conclusion for question 3: **"we flagged it before it was sanctioned" cannot be tested with this data.** 25 vessels is too few, and the dates end March 2025 while the DMA files run only from Feb 2025.

### DMA historical AIS
Method: `curl -I` and the S3 XML listing of `http://aisdata.ais.dk.s3.eu-central-1.amazonaws.com/?delimiter=/`; HTTP range request of the first 26 MB of `aisdk-2026-11-03.zip` (624,618,210 bytes), then raw-deflate decompress of the first entry.

- Listing: 616 daily zips, 2025-02-27 to 2026-11-04; plus a README. Zip size min 499 MB, mean 661 MB, max 1,036 MB. Latest (11-04) was uploaded 2026-11-07, so the data lags ~3 days.
- Format: CSV in zip, 26 columns, header `# Timestamp,Type of mobile,MMSI,Latitude,Longitude,Navigational status,ROT,SOG,COG,Heading,IMO,Callsign,Name,Ship type,Cargo type,Width,Length,Type of position fixing device,Draught,Destination,ETA,Data source type,A,B,C,D`. Timestamp is `dd/mm/yyyy hh:mm:ss`; decimal point is `.` (README still shows a comma; the file uses a point). Unknown values are written `Unknown`/`Undefined`. Rows are sorted by time. Unzipped, one day is ~3.4 GB.
- The first 26 MB of compressed data gave 134 MB of CSV: 751,178 rows covering **00:00 to 01:10** on 3 Nov. Positions span lat 53.85 to 91 (91 = "not available"), lon 0 to 16.4. This is **Danish waters and the western Baltic only**, not the Gulf of Finland. Class A 658k, Base Station 49k, Class B 25k, AtoN 19k messages.

### Baltic count of listed vessels (open question 4, measured on a 70-minute slice)
I matched the slice's MMSIs, and IMOs from the static fields, against the OpenSanctions vessels. Slices: 03/11 and 20/10, both 00:00 to ~01:10.

| Slice | Unique MMSIs | Any OpenSanctions match | `mare.shadow` | `sanction` only (no shadow tag) | Detention only |
|---|---|---|---|---|---|
| 3 Nov | 2,361 | 50 | 23 | 0 | 5 |
| 20 Oct | 2,724 | 36 | 11 | 1 | 12 |

The "shadow" matches are almost all from `ua_war_sanctions`, which tags shadow-fleet ships. Examples (3 Nov slice): PALARA (sl), TULU (bb), ALMOND (ru), ZENTURO (bb), PALARA, BEAST. In the 3 Nov slice 14 vessels had a 273 MMSI, 3 of which are not in OpenSanctions.

## 4. Answers to the open questions

**Q3: Does OpenSanctions entity JSON include designation dates?** Partly. Dates exist for about a quarter of vessel sanction records (721 of 2,944), but only 25 of those vessels have an MMSI. The CSV has none. A "flagged before it was sanctioned" test is not feasible. Do not promise it in the pitch.

**Q4: How many OpenSanctions-listed vessels are in the Baltic on a typical day?**
- Measured: 11 to 23 `mare.shadow`-tagged vessels in a single 70-minute window of DMA's coverage (Danish waters, not the whole Baltic). Any-listing matches (including detentions) were 36 to 50.
- Over a full day, unique vessels grow (more ships pass through). My guess, not measured: **~25 to 60 shadow-tagged and ~60 to 120 any-listed** per day in DMA coverage. Pure `sanction` risk with no shadow tag is near zero in these slices.
- That is above the ~20 threshold in the plan only if "listed" includes the shadow tag. Whether that makes the **forecast evaluation** meaningful: no. Most listed vessels just transit and keep transmitting, so there are very few positive events among them (see Q8).
- To measure it in 30 minutes: download two or three full days (660 MB each, ~5 minutes each), stream-unzip, group by MMSI (and IMO from static messages), join to `maritime.csv`, and count unique matches per day. The script I used is ~30 lines; the join key code is above.

**Q6: Do GFW's and OpenSanctions' non-commercial terms allow a student hackathon demo judged by commercial sponsors?**
Probably yes, but this is not legal advice.
- GFW, https://globalfishingwatch.org/our-apis/documentation/docs/license-rate-limits : "The Services are available for noncommercial use only in accordance with the CC BY-NC 4.0 license." An app must not be "intended (primarily or materially) for or directed towards commercial advantage or monetary compensation." GFW "may revoke usage rights at any time if it finds an application inconsistent with the noncommercial restriction." Attribution: "Powered by Global Fishing Watch." with a link.
- Token rules: "You may not include Your token in a publicly available web interface" and tokens are not to be shared with other users. So keep the token in the backend, one team member's token.
- Limits: "We ask that users not exceed 50,000 DAILY API requests per day and 1,500,000 per month." Breach gives HTTP 429, a 24-hour block (daily) or 30-day block (monthly), enforced per user across all tokens.
- CC BY-NC 4.0 legal code, https://creativecommons.org/licenses/by-nc/4.0/legalcode.en : "NonCommercial means not primarily intended for or directed towards commercial advantage or monetary compensation."
- OpenSanctions, https://www.opensanctions.org/datasets/maritime/ : "The data is licensed under the terms of Creative Commons 4.0 Attribution NonCommercial." It is "free for non-commercial users"; businesses need a data licence.
- Reading: a student demo, no revenue, no customers, shown at a hackathon fits. The prize (a console) is for the team and not paid for the data. Sponsors seeing it does not make it commercial. The risk is if the project is later pitched as a product (then you need an OpenSanctions licence and GFW's permission). Put credits for both on the demo screen and the Devpost page.

**Q8: Can a 6-hour "go dark" forecast be trained from a few days of DMA data? How many labelled gap events?**
No, not honestly. Measurements and reasoning:
- In the 3 Nov 70-minute slice only **5 vessels** had a >= 30-minute gap inside the Danish interior (lat 54 to 58.5, lon 8 to 15) while last seen moving. Rough scaling (my guess): ~50 to 150 per day, i.e. **a few hundred for 3 days**. Most are Class B, coverage holes, or ships entering ports. GFW needs >= 12 h and >= 50 nm from shore and still treats them as only "likely" intentional; in the Danish straits nothing is 50 nm from shore, so GFW's own definition yields **zero** labels in this region.
- So labels would be mostly "receiver artefact" gaps, and a model trained on them predicts coverage holes, not hiding. Of the 11 to 23 listed shadow ships per day, I expect only a handful to have a gap at all.
- A few days gives no meaningful temporal hold-out either, and the 3-day lag means you cannot test on yesterday.
- Fall-back that is honest: a "likely shadow fleet" risk score, with OpenSanctions `mare.shadow`/`sanction` as positives and everything else as unlabelled. Features: flag/MID mismatch, gap counts, loitering, MMSI/IMO inconsistency, destination text. Label this as "risk ranking", not "forecast". If the forecast stays, call it an **explicit heuristic** (rule-based hazard from gap history, speed, and distance to coverage edge), show a base-rate comparison, and avoid any accuracy claim.

**Key judgement: is there enough labelled data to train and honestly evaluate a forecast in ~17 hours, and which label source?** **No for the 6-hour go-dark forecast; yes for a risk score at demo scale.** Use **OpenSanctions (`risk` contains `shadow` or `sanction`) as the label source**, matched by MMSI plus IMO, with DMA used for development and sanity-checking of the detector. Do not use GFW gap events as labels: the dataset is prototype, GFW's definition needs 50 nm offshore, and the free API adds a sign-up and latency of days.

## 5. Risks and fixes, ranked

1. **Forecast has no honest evaluation.** Fix: rename to "risk ranking" or "heuristic outlook" and say so on screen. Decide this before hour 6 (see "Known inconsistency" in the claims file).
2. **DMA does not cover the Gulf of Finland, and lags 3 days.** The demo map is the Baltic, but history is Danish waters. Fix: show history replay on Danish waters only (Kattegat/Belt), or use live AISStream/Digitraffic for the Gulf. Do not claim backtesting on the Gulf.
3. **Wrong label set.** The CSV is 36% port-state detentions. Fix: filter on `risk` containing `shadow` or `sanction`; expect ~870 sanctioned vessels with an MMSI, ~900 shadow-tagged.
4. **MMSI-only matching misses most.** Only 35% of listed vessels have an MMSI. Fix: also match IMO from AIS static messages (done in my test; IMO matched an extra 13 vessels).
5. **Data handling time.** One DMA day is 3.4 GB raw. Fix: stream the zip, filter by bounding box and Class A, or use range requests for the first N MB as I did (time-sorted rows give a clean early-day slice).
6. **Licence slip.** Fix: attribution on screen, GFW token in the backend only, no OpenSanctions redistribution in the repo (download at build time). Keep the 50k/day GFW cap in mind.
7. **web.ais.dk certificate expired.** Fix: use `http://aisdata.ais.dk/` (HTTP, no TLS) and verify files by ETag if integrity matters.

## 6. Anything missed

- **OpenSanctions has an API** (`api.opensanctions.org`) that needs a key; the bulk CSV and JSON need none. The bulk file URL changes daily, so fetch `index.json` first.
- **`ua_war_sanctions` is the best shadow-fleet tag** (Ukrainian war-sanctions portal), and it carries the `mare.shadow` marker. Check if the pitch can cite it explicitly. Not verified beyond the data.
- **GFW gap dataset is prototype**, no latency published. SAR presence is 5 days old, so it cannot confirm an event from the last hours.
- **DMA's own contact** for terms: sifa@brs2.dk (from the DMA page). No licence is stated on the page.
- **A SAERI data portal** lists a restricted copy of DMA 2014 to Jan 2026 (https://dataportal.saeri.org/); not usable without access.
- Not checked: Digitraffic as a Gulf of Finland history source (it serves live data, so history would have to be self-recorded from now).
