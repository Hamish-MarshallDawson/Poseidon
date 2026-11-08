# pr-data: training and grading data (issue #113)

Checked 8 Nov 2026, about 04:15 to 04:50 UTC. Read-only. **M** = measured by me today, **D** = documented (link), **E** = estimated.

## Recommendation

1. **Train the first model on the Danish AIS archive (DMA).** It is free, needs no account, and has full dense tracks. I measured the latest file at 2.2 days old and 33 MB/s download. Take **14 to 30 recent days** (about 8 to 20 GB zipped), keep Class A, resample to 1 minute, cut into "now, then 1/3/6/24 h" examples. Add **older months** (same bucket, back to 2007) only if the first model is data-starved.
2. **Grade with the same archive, delayed.** Each daily file arrives about 2 to 3 days late and is the exact route for Danish waters. This is the only free source that grades a *route* rather than an end point.
3. **Do not use GFW gap events as training or grading data for our four regions.** They are open-ocean only, and I found none in the Danish box or Gulf of Finland (details below). Use them only as a worldwide "where did it reappear" set, if at all.
4. **Fast grading stays our own AIS** (Tiger `positions`, since 16:51 on 7 Nov).
5. **Skip NOAA, Kystverket and Digitraffic history for the first model.** NOAA is US waters and about 130 days old; Kystverket needs an application; Digitraffic has no history.

## Sources compared

| Source | Access (checked) | Delay | Size per day | Coverage | Fit for first model |
|---|---|---|---|---|---|
| **DMA archive** `http://aisdata.ais.dk/aisdk-YYYY-MM-DD.zip` | Anonymous HTTP, S3 bucket listing at `http://aisdata.ais.dk/` (M). Daily zips from 2025-02-27; monthly under `YYYY/` back to 2007 (M, HEAD 200 for 2007-06, 2010-01) | Latest file is **2026-11-05**, `Last-Modified` 8 Nov 00:22 UTC. 6 Nov and 7 Nov return 404 (M). So 2 to 3 days | 553 to 748 MB zip (M, 6 days sampled: 553, 661, 576, 748, 702 MB), about 3.4 GB CSV | Danish waters, Kattegat, W Baltic, slice of North Sea; 2.6 to 16.5 E, 53.7 to 58.7 N (wave, M) | **Best.** Dense (median 10 s), identity mostly present |
| NOAA MarineCadastre | `https://noaaocm.blob.core.windows.net/ais/csv2/csv2026/ais-YYYY-MM-DD.csv.zst`, anonymous, listing via `?restype=container&comp=list` (M) | **About 130 days**: last 2026 file is 30 Jun, uploaded 18 Sep (M) | 250 to 320 MB `.csv.zst` (M listing); 7.6 MB/s (M) | US waters and USCG receivers only; 2009 to 2026 (D, [NOAA catalog](https://coast.noaa.gov/digitalcoast/data/vesseltraffic.html)) | Possible extra training area. No grading of live routes (too old) |
| Kystverket (Norway) | HAIS (hais.kystverket.no, GeoParquet) and ais-public.kystverket.no (CSV, open licence, ships over 45 m in 12 nm) exist (D, [search result](https://www.kystverket.no/en/sea-transport-and-ports/ais/access-to-ais-data/)); both URLs answered HTTP 200 (M). Full access needs a registration form stating the reason | Unknown, not tested | Unknown | Norway, plus Kystverket's own AIS satellites | Not usable in 5 hours. Ask for access only for a later phase |
| Digitraffic | Live API only; agent wave found no history (wave, D) | n/a | n/a | N Baltic | No. We already record it live |
| BarentsWatch open AIS | Live only, no data older than 14 days, needs client registration (D) | n/a | n/a | Norway | No |
| HELCOM AIS | Standard agreement required (D) | n/a | n/a | Baltic | No (paperwork) |

Licence: the DMA page says historical data are free to download ([DMA AIS data](https://www.dma.dk/safety-at-sea/navigational-information/ais-data), via search; I could not open the terms page itself). The DMA's older policy says access falls under the Danish PSI Act and the DMA may charge for data sales ([policy](https://dma.dk/safety-at-sea/navigational-information/ais-data/ais-data-management-policy-)). **Treat the licence as "free to download, terms unconfirmed"; cite DMA as the source in Devpost.**

### DMA schema (M, first 400 KB of `aisdk-2026-11-05.zip`)
Columns: `# Timestamp` (`dd/mm/yyyy hh:mm:ss`), Type of mobile, MMSI, Latitude, Longitude, Navigational status, ROT, SOG, COG, Heading, IMO, Callsign, Name, Ship type, Cargo type, Width, Length, Type of position fixing device, Draught, Destination, ETA, Data source type, A, B, C, D. Absent values are `Unknown`, `Undefined` or empty. Gotchas from the research wave (M, 1 Nov file): 28% of rows are same-second duplicates from several receivers; 0.78% of consecutive pairs imply over 40 kn (drop with a speed gate); lat 91, lon 0 appears as a placeholder (I saw it in the head sample); Base Stations and Class B are in the same file.

### Load time
- Download one day: about 20 to 25 s at 33 MB/s (M, 20 MB range took 0.6 s).
- Parse one day: the wave's stdlib Python took 15.5 min for 16 M rows (M, wave). With DuckDB or Polars on this desktop I expect 1 to 3 minutes a day (E, not tested). 30 days: download about 12 min, parse 30 to 90 min, run in the background.
- Do **not** load raw rows into Tiger. After thinning to 1 min and Class A, one day is about 2,400 vessels x up to 1,440 = under 3.5 M rows, and 30 days about 100 M rows (E). Keep training data as local Parquet on the desktop; put only graded prediction cases and per-day summaries in Tiger.

## What is in Tiger now (M, read-only, 04:15 UTC)

| Table | Rows | Span |
|---|---|---|
| `positions` (aisstream + digitraffic) | about 2.0 M (approximate) | **7 Nov 16:51 to 8 Nov 04:11 UTC**, 11.3 h. About 31,000 distinct MMSI in the last hour. Last 30 min: aisstream A 85,943, aisstream B 20,351, digitraffic A 59,225. 149 MB |
| `statics` | about 56,000 | same period |
| `gaps` (src `derived`, our detector) | 10,626 versions, 959 closed | start_ts 7 Nov to 8 Nov |
| `observations` gfw `ais_presence` | 2,029,625 | 8 Aug to 4 Nov (92 daily windows per region) |
| gfw `sar_detection` | 54,266 | 8 Aug to 4 Nov |
| gfw `port_visit` | 202,214 | 2012 to 3 Nov |
| gfw `loitering` / `encounter` | 5,002 / 44 | Feb 2026 to 3 Nov / 26 Aug to 2 Nov |
| gfw `gap` | **0 rows** (confirmed, issue #112) | n/a |
| sentinel1 `radar_scene` footprints | 34,225 | May 2018 to 7 Nov 2026 (danish 15,403; gof 12,402; oman 4,559; hormuz 2,587) |
| `observations` size | 1,288 MB | |

Consequence: our own tracks are 11 hours old, so **nothing trainable is in Tiger yet**. Training must start from the archive.

## GFW gap events (M, `public-global-gaps-events:latest`, one global query per date range, `limit` up to 1000)

- **Count:** a date range returns events *overlapping* the range: 2,798 for 20 to 21 Oct, 2,124 for 27 to 28 Oct, 1,444 for 2 to 3 Nov (falling because recent gaps have not closed yet or have not been published). Roughly **2,000 to 2,800 a day worldwide**, 30,039 for October.
- **Fields (M):** `start`, `end`, `id`, `position`, `regions`, `distances.{start,end}DistanceFromShoreKm`, `distances.{start,end}DistanceFromPortKm`, `vessel.{id,name,ssvid(=MMSI),flag,type,nextPort}`, `gap.{intentionalDisabling, distanceKm, durationHours, impliedSpeedKnots, positions12HoursBeforeSat, positionsPerDaySatReception, offPosition{lat,lon}, onPosition{lat,lon}}`.
- **Every event is `intentionalDisabling: true`** (2,124 of 2,124). This is GFW's filtered "likely disabling" subset (D, [GFW technical docs](https://globalfishingwatch.github.io/GFW_technical_documentation/files/gaps.html): at least 14 satellite positions in the 12 h before). Median start distance from shore **556 km** (M).
- **Shape:** durations p10/p50/p90/p99 = 14.5 h / 45.8 h / 908 h / 8,057 h; 17% of the day's events last over 14 days (some are years-long open gaps, e.g. a buoy). Median implied speed 2.0 kn, median displacement 137 km, p90 686 km (M, events under 14 days).
- **Our regions: effectively none.** Off/on points inside Danish box: 0; Gulf of Finland: 0; Hormuz 1; Gulf of Oman 1 (of 2,124, M). A geometry query over the Danish box for all of October returned total 0 (M). This explains Tiger's 0 rows and says #112 may *correctly* find almost nothing, not only be a bug. Tell the #112 agent.
- **Use:** each event gives only two end points (off, on) plus duration. That grades "where did it reappear" worldwide, not a route. Reasonable as a second, separate benchmark for open-ocean reappearance with no route model needed. It cannot be the first model's training set (no tracks in the gap, and the pre-gap track is not provided, so we would need AIS history we do not have outside Denmark).

## GFW port visits, radar, Sentinel-1
- **Port visits** (202 k rows in Tiger, 2012 on): grades destination or next port (see pr-targets), not routes. Fine for a coarse sanity check that a predicted path ends near the port the ship then visited.
- **GFW radar detections** (54 k rows, 8 Aug to 4 Nov, 3 to 4 days late): anonymous cells; use as occasional checkpoints only.
- **Sentinel-1** (34 k footprints): tells us when and where radar imaged. Without running a detector (108 s per 40 km window on the RTX 4060 in the wave, unproven), it grades nothing. Not for the first model.

## What to build first (order, hours are estimates)
1. (0.5 h) Script: download 14 DMA days (6 to 19 Oct: 14 days, about 9 GB) to the desktop, convert to Parquet with DuckDB, drop duplicates, speed-gate, keep Class A moving ships.
2. (1 h) Examples builder: for each vessel and time, features from last N minutes, targets at +1/3/6/24 h; time-split by day (train 6 to 17 Oct, validate 18 to 19 Oct).
3. (0.5 h) **Time-machine held-out set:** the newest 3 available days (3, 4, 5 Nov), never trained on. This is also the backtest for the demo. Use the `available_ts` convention: a day counts as known 3 days after its end.
4. Live grading: predictions table vs Tiger `positions` for reappearing ships (hours), and DMA days 2 to 3 days late.

## Open questions for Aiden
1. **Gap definition for training:** the archive has no real dead zones in Danish waters (the wave found gaps there are 69%+ reception artefacts). Do we train on **synthetic dead zones** (hide a window from complete tracks, predict through it) and call it that? I recommend yes: it is the only way to get true labels.
2. **How far back:** 14 days (9 GB) or 90 days (about 55 GB, about 3 h parse)? I suggest 14, then extend only if the learning curve is still rising.
3. **Licence comfort:** are we happy to cite DMA as free data without a confirmed licence page? (Likely fine for a hackathon.)
4. **Tell #112:** GFW gap events essentially never touch our four regions. Do we widen the target to "worldwide, keep all" for a global reappearance benchmark, or drop gap ingestion?
5. **Kystverket:** worth one email now for Norwegian satellite-AIS history after the hackathon?

Sources: [DMA AIS data](https://www.dma.dk/safety-at-sea/navigational-information/ais-data), [DMA policy](https://dma.dk/safety-at-sea/navigational-information/ais-data/ais-data-management-policy-), [NOAA Vessel Traffic](https://coast.noaa.gov/digitalcoast/data/vesseltraffic.html), [Kystverket AIS access](https://www.kystverket.no/en/sea-transport-and-ports/ais/access-to-ais-data/), [GFW gaps technical doc](https://globalfishingwatch.github.io/GFW_technical_documentation/files/gaps.html).
