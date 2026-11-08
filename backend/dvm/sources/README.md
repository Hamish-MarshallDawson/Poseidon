# Provider ingest: one schema for every source (#53)

Four providers, on clocks from half a second to four days, land in **the same tables with clear provenance**. AIS fixes and identities use the tables we already have. Everything else goes into **one new table, `observations`**. A small ledger, **`source_windows`**, makes polling and backfill idempotent and shows how fresh each source is.

| Provider | Clock | Lands in | How |
|---|---|---|---|
| AISStream | live, ~1 s | `positions`, `statics` | unchanged (`dvm/ingest.py`) |
| Digitraffic | live, ~0.5 s | `positions`, `statics` | MQTT stream (`digitraffic.py`) |
| Global Fishing Watch | 3–4 days old | `observations` + `statics` (identity) | polls every 6 h, one region and day per window (`gfw.py`) |
| Sentinel-1 | 1–13 h old | `observations` (`radar_scene`) | polls every 30 min (`sentinel1.py`) |

Nothing in this folder changes `models.py`, `store.py`, `app.py`, `normalise.py`, the 06 data model or an existing table. Wiring it into the live backend and Tiger needs the team's agreement (see [Proposal](#proposal)).

## The shared schema

### `observations` (new hypertable, partitioned on `time` = `ts`, 7-day chunks)

One row is one thing a provider says about a place and time that isn't a single AIS fix.

| Column | Meaning |
|---|---|
| `id` | Deterministic key, e.g. `gfw:loitering:<event id>`, `gfw:pres:2026-11-03:55.12:11.40`, `sentinel1:<item id>`. Unique with `time`. |
| `src` | `gfw` or `sentinel1` (more later) |
| `kind` | `ais_presence`, `sar_detection`, `gap`, `encounter`, `loitering`, `port_visit`, `radar_scene` |
| `ts`, `end_ts` | Event interval, epoch ms UTC (06 units). Cells and region totals cover the UTC day. |
| `recv_ts` | When we fetched it |
| `available_ts` | When the provider made it public: **the leakage clock**. Features at `as_of` use `available_ts <= as_of` only. |
| `mmsi` | Valid vessel MMSI only (06 rule). Null for anonymous cells and scenes. |
| `lat`, `lon` | Point, cell corner or footprint centroid |
| `min_lon`, `min_lat`, `max_lon`, `max_lat` | Box: cell, region (for region totals), event extent, scene bbox |
| `cell_deg` | Grid size when the row is a cell aggregate (GFW HIGH = 0.01°) |
| `value` | The kind's measure: hours (`ais_presence`, events) or detections (`sar_detection`) |
| `n` | Distinct vessels behind a cell |
| `matched` | Radar detection matched to AIS by the provider |
| `geom` | GeoJSON footprint (radar scenes) |
| `attrs` | Provider extras worth keeping (vessel ids, names, event details, orbit). Never needed to join. |
| `q` | `available_est` (time estimated, see backfill), `cell_level`, `region_level` |

Indexes: `(id, time)` unique, `(kind, time DESC)`, `(mmsi, time DESC)` where mmsi is set, `(available_ts)`.

**Write rule.** Upsert on `(id, time)`. A provider revision (an open event's end, a day's hours as late data lands) updates `end_ts`, `value`, `n`, `matched`, `geom`, `attrs` and the box. **`recv_ts` and `available_ts` keep their first values**, so "what did we know at T" still has an answer.

### `source_windows` (new table, the ledger)

`(src, stream, region, start_ts)` primary key, plus `end_ts`, `fetched_at`, `first_fetched_at`, `rows`, `status` (`ok` or `error`) and `error`. One row per window fetched (one UTC day per region for GFW and Sentinel-1; one raw-log hour for a Digitraffic replay).

### Existing tables, used as they are

- **`positions`**: Digitraffic fixes, `src = 'digitraffic'`, through the backend's own `Store` (COPY once a second).
- **`statics`**: Digitraffic metadata, and **GFW identity**: one row per vessel and day with `src = 'gfw'`, name, IMO (checked), call sign, `type_group` and `flag_iso2`. The insert is idempotent with a `NOT EXISTS` on `(mmsi, time, src)`, because `statics` has no unique key.

## How each provider maps in

### Digitraffic (`digitraffic.py`)

- `wss://meri.digitraffic.fi:443/mqtt`, topics `vessels-v2/+/location` and `vessels-v2/+/metadata`, header `Digitraffic-User: hacktheburgh/poseidon`. paho reconnects with 2 to 120 s backoff.
- **location → `PositionReport`**: `ts = time * 1000`, `ts_quality = "source"`. Measured live: `time` is the fix time in whole seconds, median 0.5 s (p90 0.9 s) before our clock. `recv_ts` is our clock at the read. `cls = "A"` (the feed is Class A only). `sog` 102.3, `cog` 360, `heading` 511 and `navStat` 15 become null with the 06 `q` flags, and `late` is set after 120 s.
- **metadata → `VesselStatic`**: `ts = timestamp`, draught /10, bit-packed `eta` unpacked, `refA..D` give the dimensions, destination `"0"` becomes null, and IMO gets the checksum flag.
- Raw envelopes go to `data/raw/digitraffic/<hour>.jsonl`, the same log format as AISStream, so replay works.
- An exact repeat of a vessel's last fix (a QoS 0 redelivery) is dropped.
- **Licence**: CC BY 4.0, "Source: Fintraffic / digitraffic.fi". Fishing boats are removed by Fintraffic, and there is no history.

### Global Fishing Watch (`gfw.py`)

Each window is one region and one UTC day. `fetch_day` takes 9 calls or more: about 10 s in the Gulf of Oman, but 55 s in the Danish straits, where about 5,800 port visits overlap every day and take six pages. `fetch_range` (below) gets a block of days with far fewer calls. Checked live on 7 Nov:

- **Per-vessel positions are unavailable**: 4Wings `group-by=VESSEL_ID` with `spatial-aggregation=false` returns 404 "temporarily unavailable". So the adapter takes what works:
  - `ais_presence` cells: anonymous 0.01° cells with `value` = hours and `n` = vessels.
  - `ais_presence` region rows: one per vessel and day, with `mmsi`, the region box and `value` = hours. Identity goes to `statics`.
  - `sar_detection` cells: `matched = true` and `false` (anonymous), `value` = detections.
  - `sar_detection` region rows: matched vessels with `mmsi`. The detection times are in `attrs.entryTimestamp`.
  - Events, from `/v3/events`, **one dataset per request** (with two, GFW ignored the geometry and returned 30,000 worldwide rows): `gap`, `encounter`, `loitering` and `port_visit`, keyed by the GFW event id, with `value` = duration in hours. Events outside the region box, or from non-vessel MMSIs (buoys, gear), are dropped and counted.
- `available_ts`: our first fetch when the day is fetched within 8 days of its end (live polling). For backfilled days it is estimated as the day's end + 4 days, with `q = available_est`.
- `User-Agent: hacktheburgh-poseidon/1.0`, because Cloudflare blocks Python's default. The token comes from `GFW_API_TOKEN` or `~/.config/hedged-bets/wave.env`, and is never logged.
- **Licence**: CC BY-NC 4.0, non-commercial. The attribution travels with every query answer (`query.observations`).
- GFW gaps go into `observations`, not into `gaps`. That table is our own detector's output, and GFW can't fill its required fields (neighbours, cell, coverage flag).

**Block fetch** (`fetch_range(client, region, bbox, start_day, end_day, recv_ts, raw_sink)`, end inclusive) returns `{day: (observations, statics, info)}`, the same per-day windows `fetch_day` gives, with the same ids and fields, so the ledger and the upserts work as before. Checked live on 8 Nov against single-day requests:

- The 3 cell reports (`temporal-resolution=DAILY` over the block) give every row a `date`. Split by `date`, each day's rows equal the single-day request's.
- Events over the block: a one-day request lists exactly the events whose `[start, end)` overlaps the day, so `event_days` puts each block event on those days, and the per-day sets match. The block request lifts the 20,000-event cap to 20,000 per day of the block, and is processed page by page.
- **The 2 vessel reports stay one call per day.** Over a block, GFW gives each vessel one `entryTimestamp` and `exitTimestamp` for the whole block, not for the day (hours and identity do match). Those fields are the radar detection times, so they must stay per day.
- A whole-path live comparison (fetch_day vs fetch_range, no database) was identical for 3 Gulf of Oman days. For 2 Danish days (36,000 rows) it was identical except one vessel's `speed` per day, differing in the 16th digit. That row comes from the same single-day request in both paths, so it's GFW's float noise. Tests: `tests/sources/test_gfw_range.py`, including a database check that both paths leave the same rows.
- raw_sink gets each block response once (`presence_cells`, `events_port_visit_p0`, `events_port_visit_p1`, ...) and the per-day vessel responses as `<day>_presence_vessels` and `<day>_sar_vessels`.
- One failed call fails the whole block, so record every day of it as an error.

Measured live on 8 Nov (one request in flight, sharing the token with the Vultr backfill, so latency is noisy). Seconds per region-day, with peak process memory:

| Block | Danish straits | Gulf of Oman |
|---|---|---|
| 1 day (`fetch_day`) | 54–55 s | 8.4–9.5 s |
| 2–3 days | 27 s, 147 MB | 4.6 s, 72 MB |
| 7 days | 24 s, 584 MB | 6.6 s, 86 MB |
| 14 days (calls only) | about 17 s | — |
| 30 days | 16.8 s, **2.2 GB** | 5.6 s, 283 MB |

In the Danish straits the block's port visits dominate: 23,600 for 7 days, 34,600 for 14 and 51,500 for 30, about 5 s per 1,000-event page. Elsewhere the per-day vessel calls dominate (about 2.5 s a day). Memory grows with the block, because every day holds its own copy of the long port visits until the block returns. **Recommended block: 7 days** (2 to 3 times faster, under 0.6 GB even in the Danish straits, so regions can run side by side). Use 14 days only with memory to spare. Responses stay small for the 170 s timeout: the largest single one was 20 MB in 5 s (Danish presence cells, 30 days).

### Sentinel-1 (`sentinel1.py`)

- Element 84 Earth Search STAC, collection `sentinel-1-grd`, bbox and day, following `next` pages. No pixels are read and no ships are detected: a scene is **radar coverage**.
- `radar_scene` row: `ts` and `end_ts` are the sensing start and end, `available_ts` is the item's `created` (1 to 13 h after sensing on 6–7 Nov), and the row has the footprint `geom`, the bbox, the centroid, and in `attrs` the platform, mode, polarisations, orbit and the VV asset href.
- Earth Search footprints are right. The Planetary Computer `sentinel-1-grd` location metadata is wrong, so don't swap endpoints without moving to `sentinel-1-rtc`.
- **Licence**: Copernicus Sentinel data, free and open, credited as "Contains modified Copernicus Sentinel data".

## Cadence, idempotency and backfill

| Source | Live job | Window | Refetch while | Frozen after |
|---|---|---|---|---|
| Digitraffic | stream | — | — | — |
| GFW | `poll gfw`: the last 8 days up to yesterday | region × day | at most every 6 h | fetched 7 days after the day ended |
| Sentinel-1 | `poll sentinel1`: today and yesterday | region × day | at most every 30 min | fetched 2 days after the day ended |

**Backfill** runs the same window function over a date range. Windows that are already settled are skipped, and `--force` fetches them again. Because rows are upserts on deterministic ids, a forced run adds no duplicates (tested). The raw responses are gzipped under `data/raw/<src>/<region>/<day>/`, outside the repo.

Digitraffic has no history API. `backfill digitraffic` replays our own `data/raw/digitraffic/*.jsonl[.gz]` into the database. It skips any hour that already has Digitraffic positions, is in the ledger, or is still being written.

## Serving the model and the frontend

`query.observations(con, kinds, bbox, start_ts, end_ts, as_of, src, mmsi, limit)` is one query for every provider. It returns the rows whose interval overlaps the time range and whose point or box touches `bbox`, plus `attribution` for each source in the answer. **The model passes `as_of`**, which applies the leakage rule. The frontend draws by `kind`, not by provider: `radar_scene` footprints are coverage, `sar_detection` cells with `matched = false` are radar targets without AIS, and events are markers. `query.freshness(con, now)` gives the newest event, the last fetch and the age per source, for the "radar 5 h ago" and "AIS 4 days old" labels.

## Run it

```bash
cd backend
.venv/bin/pip install -r requirements.txt   # now includes paho-mqtt and httpx
docker run -d --name poseidon-tsdb -p 55433:5432 -e POSTGRES_PASSWORD=local timescale/timescaledb:latest-pg17
export SOURCES_DATABASE_URL=postgresql://postgres:local@127.0.0.1:55433/postgres

.venv/bin/python -m dvm.sources setup
.venv/bin/python -m dvm.sources digitraffic --minutes 5            # no --minutes = forever
.venv/bin/python -m dvm.sources poll gfw --regions danish_straits --once
.venv/bin/python -m dvm.sources poll sentinel1                      # forever, every 30 min
.venv/bin/python -m dvm.sources backfill gfw --regions hormuz --start 2026-10-01 --end 2026-11-03
.venv/bin/python -m dvm.sources backfill sentinel1 --start 2026-10-25 --end 2026-11-07
.venv/bin/python -m dvm.sources backfill digitraffic
.venv/bin/python -m dvm.sources backfill-back gfw            # today backwards until stopped (see below)
.venv/bin/python -m dvm.sources readonly-role                 # read-only login for training and teammates
.venv/bin/python -m dvm.sources status
```

**Backward backfill** (`backfill-back {gfw,sentinel1}`) starts at the newest available day and walks back one day across all regions at a time. It skips windows that are already settled, so a restart resumes where it stopped. It stops at `--until` (default 2017-01-01), after 21 consecutive empty days (the provider's history has ended), or when the database reaches `--max-db-gb` (default 60). It checks the size before every day (before every block with `--block-days`). GFW calls are paced (0.3 s apart, backoff on 429 and 5xx). GFW identity rows go to `statics` only for the last 30 days, because `statics` has 15-minute chunks and a year of daily rows would make hundreds of tiny ones. Older identities stay in the `ais_presence` region rows (`attrs`: name, flag, IMO, type). `observations` chunks compress 30 days after they end.

**Concurrency** (`--workers N`, `--inflight N`, `--block-days N`). The regions of a day always run at the same time. `backfill --workers N` splits the date range into N contiguous shards walked at once; `backfill-back --workers N` has N workers take the next day from one shared cursor, newest first, so recent history still lands first and the stop rules are applied to the days in order (a worker may finish one block past the stopping day). The ledger and one transaction per window keep workers from overlapping or double-writing, and a restart resumes where it stopped (tested: N workers write exactly the rows and ledger of one, and a run killed mid-way and restarted fetches only the missing windows). GFW limits: a token may run **only one 4Wings report at a time** (a second gets 429 "not currently enabled to perform more than one concurrent report"), while `/events` took 8 at once. So the client is shared through a gate: reports go one at a time, and at most `--inflight` requests (default 4) are in flight across all regions and workers. Any other process on the same token (the `poll gfw` job) can still collide with a report and then backs off 10 s. Most of a GFW day is `/events` paging (a Danish straits day: about 5 s of reports and 120 s of port-visit pages). `--block-days N` fetches N days per call once `gfw.fetch_range` exists, and is one day per call otherwise.

**Read-only role** (`readonly-role`) creates `poseidon_ro`. It can `SELECT` every table and view, including ones created later, and every session is read-only. Its URL is written only to `~/.config/hedged-bets/readonly.env` (mode 600) and is never printed. Use it for training scripts and teammates.

Regions are `danish_straits`, `gulf_of_finland`, `hormuz` and `gulf_of_oman` (`common.REGIONS`). **Tiger Cloud is refused** unless you pass `--allow-tiger`, which is for after the proposal is agreed. Tests: `pytest tests/sources`. The database test runs when `SOURCES_TEST_DATABASE_URL` points at a local TimescaleDB.

## Proposal

These changes need agreement from Jake and Hamish. Everything above works without them.

1. **Create `observations` and `source_windows` on Tiger** by adding `dvm.sources.schema.SCHEMA` to start-up, after `store.SCHEMA`. It is safe with existing data: both are new tables built with `IF NOT EXISTS`, and no existing table, index, aggregate or policy is touched. Rollback is `DROP TABLE observations, source_windows`.
2. **Run the Digitraffic stream inside the backend**, so the live map and the gap detector see it. In `app.py` start-up, start `dvm.sources.digitraffic.run(sink, rawlog)` as a task, where `sink` is the same function that AISStream records go to (pipeline plus `Store.add`). Config: `DIGITRAFFIC=1`.
3. **Add a `normalise.py` dispatch**: `if env.src == "digitraffic": return normalise_digitraffic(env)`, so replay of `data/raw/digitraffic` goes through the one normaliser.
4. **Add `sentinel1` to `models.Src`.** It only matters once a canonical record or route carries it. The observations code has its own `ObsSrc`.
5. **Accept GFW identity rows in `statics`** (`src = 'gfw'`, one row per vessel and day). This changes "latest statics row for an MMSI" for ships GFW has seen: for Hormuz ships it is the only name source. A consumer that wants only broadcast identity filters `src <> 'gfw'`.
6. **Overlapping live feeds.** In the Baltic, AISStream and Digitraffic hear the same ships, so `coverage_1m` counts both. Either count per source (`src` in the aggregate) or mark the second copy `dup_other_src` with the 06 rule 1.5 key. Jake's call, since it affects gap baselines.
7. **Routes** (Hamish's area): `GET /observations?kinds=&bbox=&start=&end=&as_of=` → `query.observations`, and `GET /sources` → `query.freshness`, both behind the same Auth0 check as `/coverage`.

## Known limits

- GFW per-vessel positions and per-vessel radar locations are out while GFW's 404 lasts. The region rows hold the vessel lists and the cells hold the places, but they can't be joined.
- GFW port visits overlap the window, so some span years (e.g. 2012 to 2026) and their `value` is huge. Filter on `ts` if you need recent visits only.
- Whether a GFW cell's `lat` and `lon` give its corner or its centre isn't documented. The box assumes the south-west corner.
- Digitraffic `cls` is always `A`, as the feed promises. `nav_status` is the only class hint.
