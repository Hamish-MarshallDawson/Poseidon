# Dark Vessel Monitor: one unified data model

*Contract for ingest, replay, detectors, forecast, watchlist, map and evaluation. Written Sat 7 Nov 2026, ~16:30. Source formats were checked against primary docs and live payloads (see section 3 for status per source).*

Rule of the whole document: **every consumer reads canonical records only. Nobody downstream of `normalise()` ever sees a source-specific field.** Live, replay and backtest run the same code path.

## 0. Verified source facts that shaped the model

| Fact | Evidence | Consequence |
|---|---|---|
| AISStream `MetaData` has a **full UTC string**, `time_utc`, e.g. `2022-12-29 18:22:32.318353 +0000 UTC` (Go time format), plus `MMSI`, `MMSI_String`, `ShipName`, `latitude`, `longitude`. The docs page shows only `MMSI, ShipName, Latitude, Longitude` (capital L) and says nothing of `time_utc`. | Docs example at aisstream.io/documentation; `time_utc` seen in third-party samples (dev.to/jj/follow-that-ship-with-aisstreamer-21g3). **Not seen in a live payload by me (needs API key).** | Treat `time_utc` as the **receive time** (when AISStream got it), not the instrument time. Parse defensively, accept both key cases, fall back to local clock. |
| `PositionReport.Timestamp` is the UTC **second within the minute** (0 to 59; 60 to 63 mean not available/manual/estimated/inoperative). | Digitraffic OpenAPI text (live), ITU-R M.1371 | `ts` must be rebuilt (section 1.3). |
| AISStream type definitions: `ShipStaticData{ImoNumber, CallSign, Name, Type, Dimension{A,B,C,D}, FixType, Eta{Month,Day,Hour,Minute}, MaximumStaticDraught(double), Destination}`; `StaticDataReport{ReportA{Name}, ReportB{ShipType, CallSign, Dimension{A..D}}}`; `StandardClassBPositionReport` has no name/type; `ExtendedClassBPositionReport` has `Name, Type, Dimension`. | github.com/aisstream/ais-message-models `type-definition.yaml` (downloaded) | Class B static data arrives via types 24 and 19, never carries IMO. `Eta` has **no year**. |
| Digitraffic REST `/api/ais/v1/locations` returns GeoJSON; `properties` has `mmsi, sog, cog, navStat, rot, posAcc, raim, heading, timestamp (second 0-59), timestampExternal (epoch ms)`. Coordinates are `[lon, lat]`. | Live read 7 Nov 15:50 UTC, 276 KB, saved `datamodel/loc_all.json`; OpenAPI at meri.digitraffic.fi/swagger/openapi.json | `timestampExternal` is a full time (receive-side). Use as `recv_ts`. |
| Digitraffic metadata: `eta` is **bit-packed** (bits 19-16 month, 15-11 day, 10-6 hour, 5-0 minute), `draught` is **1/10 m** (255 = 25.5 m or more, 0 = n/a), `imo` 0 = n/a, `shipType` int, `referencePointA..D`. | OpenAPI text (live) and live read `vessels.json` (e.g. `eta 740352` = 11-09 16:00, `draught 29` = 2.9 m) | Conversions in section 3. |
| **MQTT payload names differ from REST.** MQTT location: `time` (seconds), `sog, cog, rot, heading, navStat, posAcc, raim, lon, lat`. MQTT metadata: `timestamp` (ms), `destination, name, callSign, draught, eta, posType, refA..refD, imo, type`. | digitraffic.fi/en/marine-traffic page | Two mapping columns for Digitraffic. MQTT location has **no ms receive time**, only `time` in whole seconds. |
| DMA CSV header (verified on first 300 KB of `2025/aisdk-2025-01-01.zip`, 480 MB zip, public S3 bucket `aisdata.ais.dk`): `# Timestamp,Type of mobile,MMSI,Latitude,Longitude,Navigational status,ROT,SOG,COG,Heading,IMO,Callsign,Name,Ship type,Cargo type,Width,Length,Type of position fixing device,Draught,Destination,ETA,Data source type,A,B,C,D`. Timestamp `01/01/2025 00:00:00` (dd/mm/yyyy, UTC, whole second). Enums are **text** ("Under way using engine", "Cargo", "Class A", "Base Station", "AtoN"); n/a is blank or `Unknown`. | Downloaded: `datamodel/dma_sample.csv` | One time column only, so `recv_ts = ts` for history. Needs text-to-code maps. Must drop base stations and AtoN. |
| OpenSanctions maritime CSV, header: `type,caption,imo,risk,countries,flag,mmsi,id,url,datasets,aliases`. 23,833 rows on 7 Nov; `imo` is written `IMO9427366`; only 7,341 rows have an MMSI; **one row per (vessel, source dataset)**, so duplicates by IMO; `risk` tags include `sanction` (6,236 rows), `mare.shadow`, `mare.detained`, `poi`. | Downloaded `datamodel/os_maritime.csv` from `data.opensanctions.org/artifacts/maritime/<run>/maritime.csv` (link on the dataset page) | De-duplicate on IMO. A **`mare.shadow` tag exists**: a ready-made shadow-fleet label. |
| pyais 3.x `decode(...).asdict()` field names (verified by running it): type 1-3 `mmsi,status,turn,speed,accuracy,lon,lat,course,heading,second,maneuver,raim,radio`; type 18 `mmsi,speed,accuracy,lon,lat,course,heading,second,cs,display,dsc,band,msg22,assigned,raim,radio`; type 5 `mmsi,ais_version,imo,callsign,shipname,ship_type,to_bow,to_stern,to_port,to_starboard,epfd,month,day,hour,minute,draught,destination,dte`; type 19 adds `shipname, ship_type, to_*`; type 24 part A `shipname`, part B `ship_type, vendorid, model, serial, callsign, to_*`. Speed is knots, lat/lon degrees, draught **metres** (already /10). | Ran pyais in scratchpad | `status`, `ship_type`, `epfd` are enums: use `.value`. |
| GFW v3 events: dataset `public-global-gaps-events:latest` for AIS-off gaps. Exact response keys **not verified** (token needed, docs page does not show them). | globalfishingwatch.org/our-apis/documentation/docs/v3/events | Mapping in section 3 is marked *unverified*; confirm on the first real response. GFW is used for **evaluation only**, never in the live path. |

## 1. Principles

### 1.1 Identifiers

- **`mmsi` (int, 9 digits) is the primary key** of every vessel-level table and WebSocket message. It is the only identifier present in every message type from every source.
- **`imo` (int, 7 digits, nullable) is a linked attribute**, not a key. It comes only from Class A static data (type 5), Digitraffic metadata, DMA, OpenSanctions. Class B never sends it. IMO 0 or `Unknown` becomes `null`. Validate the IMO check digit (weighted sum of the first 6 digits, last digit of result equals 7th digit); a failing IMO is stored with flag `imo_bad_checksum` and **not** used for the sanctions join.
- **MMSI changes and reuse.** We do not try to merge identities in the key. Instead:
  - `VesselStatic` is an append-only history of `(mmsi, ts, imo, name, callsign, ...)`.
  - The **identity links** the detectors read are derived: `imo -> set of mmsi`, `mmsi -> set of imo`, both with first and last seen time.
  - One IMO seen under two MMSIs at different times is a `SpoofEvent(type="mmsi_change")`. One MMSI seen with two IMOs is `type="imo_change"`. One MMSI reporting from two places that are too far apart for the time gap is `type="duplicate_mmsi"` (two ships sharing an MMSI, or a clone).
  - All three are evidence, never errors.
- **Non-vessel MMSIs are dropped by `normalise()`** (counted in feed stats only): base stations `00MIDxxxx`, AtoN `99MIDxxxx`, SAR aircraft `111MIDxxx`, handhelds `8xxxxxxxx`, AIS-SART/MOB/EPIRB `970/972/974xxxxxx`, and anything that is not 9 digits with a valid first-three-digit MID (200 to 799). DMA gives `Type of mobile` which makes this exact; for the others use the digit patterns.
- **Flag** is derived from the MID (first three digits) with a static lookup file `data/mid_to_flag.csv` (ITU MID list). It is `flag_iso2`, nullable. A "declared flag" is not carried by AIS at all. OpenSanctions has its own `flag`; that goes into `SanctionsMatch`, and the **flag mismatch** feature is `flag_from_mid != sanctions.flag`.
- **IDs for events** are deterministic strings so replay and re-runs produce the same IDs: `gap-{mmsi}-{start_ts}`, `spoof-{type}-{mmsi}-{ts}`, `score-{mmsi}-{target}-{made_at}`.

### 1.2 Units and coordinates

| Quantity | Canonical unit | Suffix in field name | Notes |
|---|---|---|---|
| Time | **epoch milliseconds, UTC, int64** | `_ts` | JSON and Parquet use the integer. Polars: `pl.from_epoch(col, "ms")` gives a UTC datetime. No timezone-naive times anywhere. |
| Duration | seconds (int) | `_s` | |
| Speed | knots | `_kn` | AIS 102.3 (n/a) becomes `null`. |
| Course, heading | degrees true, 0 to 359.9 | `_deg` | COG 360 and heading 511 become `null`. |
| Distance, dimensions, draught | metres (float) | `_m` | Digitraffic draught is /10; DMA already metres; AISStream `MaximumStaticDraught` is a double, **assumed metres, check on first live message**. |
| Latitude, longitude | WGS84 decimal degrees, `lat` in [-90, 90], `lon` in [-180, 180] | `lat`, `lon` | AIS "not available" is lat 91 and lon 181: drop the record. Arrays for the map are always `[lon, lat]` (GeoJSON and deck.gl order). |
| Probability | float in [0, 1] | `p` | |

### 1.3 Time

Two times on every record. Never mix them.

- **`ts` = event time**: when the position was true (the best estimate of the instrument time).
- **`recv_ts` = received time**: when *our system* (or the source's server, for history) first had the message. For live feeds this is `time_utc` / `timestampExternal` if present, else our own clock at the socket read. `recv_ts >= ts - 5000` always.
- **Detectors and the live forecast order by `recv_ts` and may only use records with `recv_ts <= as_of`.** Geometry and speed maths (jumps, implied speed) use `ts`. This is the leakage rule (section 5).

**Rebuilding `ts` where a source only gives second-of-minute** (AISStream, Digitraffic MQTT, Kystverket, all PositionReports):

```
sec = report second (0..59)
if sec not in 0..59:  ts = recv_ts;  ts_quality = "recv_only"
else:
    cand = recv_ts truncated to the minute + sec seconds
    if cand > recv_ts + 5 s: cand -= 60 s          # report is from the previous minute
    ts = cand;  ts_quality = "rebuilt"
```

This is correct whenever the delay between the instrument time and `recv_ts` is under about 55 s, which holds for live terrestrial feeds. If a message is genuinely delayed longer (buffered base station), `ts` can be wrong by whole minutes: such records get `q` flag `late` when `recv_ts - ts > 120 s` and are excluded from jump/speed detectors (still used for presence). Sources with a full instrument time (DMA only has the base-station receive time, one column) get `ts = recv_ts = file timestamp`, `ts_quality = "source"`.

### 1.4 Source and quality on every record

Every record has `src` (`aisstream | digitraffic | kystverket | dma | gfw | opensanctions | derived`) and `q` (list of short quality strings, may be empty). The allowed `q` values are fixed:

`late`, `ts_recv_only`, `sog_na`, `cog_na`, `hdg_na`, `imo_bad_checksum`, `dup_other_src` (same fix already seen from another source, kept for audit but skipped by detectors), `jam_suspect` (cell-level simultaneous jumps, set by the spoof detector), `own_stall` (ingest queue was backed up around this time).

### 1.5 De-duplication

Two sources and several receivers hear the same message. Key: `(mmsi, ts_ms // 1000, round(lat, 4), round(lon, 4))`. The first one in `recv_ts` order is kept; later copies are dropped before storage and counted in feed stats. If the same fix arrives from a second source, only the stats change. Do **not** dedupe on `ts` alone: a ship can legitimately send several messages per second from different slots, but this rule keeps them since positions differ.

## 2. Entities

Types: `int`, `float`, `str`, `bool`, `ts` (= int64 epoch ms UTC), `list[...]`, `json`. "Null?" says whether the field may be missing. **R** = required for the MVP; **O** = optional, cut first.

### 2.1 PositionReport (R) `positions` table, `kind: "pos"`

| Field | Type | Unit | Null? | Meaning |
|---|---|---|---|---|
| `mmsi` | int | | no | Vessel key. |
| `ts` | ts | ms | no | Event time (section 1.3). |
| `recv_ts` | ts | ms | no | Time we (or the source server) received it. |
| `lat` | float | deg | no | WGS84. |
| `lon` | float | deg | no | WGS84. |
| `sog_kn` | float | kn | yes | Speed over ground. |
| `cog_deg` | float | deg | yes | Course over ground. |
| `heading_deg` | int | deg | yes | True heading. |
| `nav_status` | int | | yes | AIS 0 to 14 (0 engine, 1 anchor, 5 moored...). 15 (default) becomes null. |
| `cls` | str | | no | `"A"` or `"B"`. |
| `msg_type` | int | | no | AIS message id: 1, 2, 3, 18, 19, or 0 for formats that do not say (DMA, Digitraffic). |
| `ts_quality` | str | | no | `rebuilt`, `recv_only`, `source`. |
| `src` | str | | no | Source. |
| `q` | list[str] | | no | Quality flags (1.4). Empty list is normal. |

Key: `(mmsi, ts, lat, lon)`. Sorted by `recv_ts`.

### 2.2 VesselStatic (R) `statics` table, `kind: "static"`

Identity and voyage. **Partial updates are normal:** a Class B type 24 part A has only a name; a Digitraffic metadata message has everything. `null` means "this message did not carry it". Every non-null value is a fact at `ts`. The table is append-only, one row per message.

| Field | Type | Unit | Null? | Meaning |
|---|---|---|---|---|
| `mmsi` | int | | no | |
| `ts` | ts | ms | no | Event time. For statics this equals `recv_ts` (no second field). |
| `recv_ts` | ts | ms | no | |
| `imo` | int | | yes | 7 digits; 0 and unknown become null. |
| `name` | str | | yes | Trimmed, upper case, no trailing `@` or spaces. Empty becomes null. |
| `callsign` | str | | yes | Trimmed. |
| `ship_type` | int | | yes | AIS ship and cargo type, 0 to 99. 0 becomes null. DMA text mapped back to a representative code (section 3). |
| `type_group` | str | | no | Derived: `tanker` (80 to 89), `cargo` (70 to 79), `passenger` (60 to 69), `fishing` (30), `tug_special` (31, 32, 52, 50 to 59 other), `military` (35), `pleasure` (36, 37), `other`, `unknown`. |
| `dim_a_m`, `dim_b_m`, `dim_c_m`, `dim_d_m` | int | m | yes | Distance from the GPS antenna to bow, stern, port, starboard. |
| `length_m` | int | m | yes | `A + B`. |
| `beam_m` | int | m | yes | `C + D`. |
| `draught_m` | float | m | yes | Maximum present static draught. Changes when a tanker loads: key signal. |
| `destination` | str | | yes | Free text, cleaned as above. |
| `eta_utc` | ts | ms | yes | ETA with the year inferred (first matching date at or after `ts - 1 day`). Null if month/day/hour/minute are n/a (month 0, day 0, hour 24, minute 60). |
| `mid` | int | | no | First three digits of the MMSI. |
| `flag_iso2` | str | | yes | From the MID lookup; null for an unknown MID. |
| `src` | str | | no | |
| `q` | list[str] | | no | |

### 2.3 Vessel (R) merged current state; **in memory, never stored as a source of truth**

Built by one reducer from `PositionReport` and `VesselStatic`. The map, detectors and forecast read this. It is rebuildable from the records at any `as_of`, which is what makes replay and backtest identical.

| Field | Type | Unit | Null? | Meaning |
|---|---|---|---|---|
| `mmsi` | int | | no | |
| `imo`, `name`, `callsign`, `ship_type`, `type_group`, `length_m`, `beam_m`, `draught_m`, `destination`, `eta_utc`, `flag_iso2`, `mid` | as in VesselStatic | | yes | Latest non-null value of each. |
| `draught_prev_m` | float | m | yes | The previous different draught (for the draught-jump signal). |
| `cls` | str | | yes | `A` or `B`. |
| `lat`, `lon`, `sog_kn`, `cog_deg`, `heading_deg`, `nav_status` | | | yes | Last position fields. |
| `last_ts` | ts | ms | no | `ts` of the last position. |
| `last_recv_ts` | ts | ms | no | `recv_ts` of the last position. |
| `last_src` | str | | no | |
| `report_interval_s` | float | s | yes | Exponentially weighted mean of the gaps between consecutive reports (alpha 0.2) while moving. The expected silence limit is `max(floor_s, k * report_interval_s)`. |
| `status` | str | | no | `active` (heard within the limit), `silent` (past the limit, no confirmed gap yet), `gap_open` (an open `GapEvent`), `stale` (not heard for over 24 h, hidden on the map). |
| `open_gap_id` | str | | yes | |
| `spoof_recent` | list[str] | | no | Spoof types in the last 6 h. |
| `sanctioned` | bool | | no | An IMO or MMSI match exists. |
| `risk_p` | float | | yes | Latest `RiskScore.p` for the primary target. |
| `risk_rank` | int | | yes | Rank on the watchlist, if listed. |

### 2.4 GapEvent (R) `gaps` table, `kind: "gap"`

An open gap is created when a vessel passes its silence limit while neighbours are still heard; it is updated in place (same `id`) and closed when the next position arrives. The table keeps every version (append), the latest `version` wins.

| Field | Type | Unit | Null? | Meaning |
|---|---|---|---|---|
| `id` | str | | no | `gap-{mmsi}-{start_ts}`. |
| `version` | int | | no | Increments on every update. |
| `mmsi` | int | | no | |
| `state` | str | | no | `open` or `closed`. |
| `start_ts` | ts | ms | no | `ts` of the last position before the silence. |
| `end_ts` | ts | ms | yes | `ts` of the first position after. Null while open. |
| `detected_at` | ts | ms | no | `recv_ts`-clock time the detector first raised it. **Labels in training use `start_ts`; anything the live system "knew" uses `detected_at`.** |
| `duration_s` | int | s | no | `end_ts - start_ts` if closed, else `as_of - start_ts`. |
| `expected_interval_s` | float | s | yes | The vessel's `report_interval_s` when the gap started. |
| `last_lat`, `last_lon` | float | deg | no | Last position before the gap. |
| `last_sog_kn`, `last_cog_deg` | float | | yes | |
| `last_nav_status` | int | | yes | Anchored ships look dark; keep this. |
| `next_lat`, `next_lon` | float | deg | yes | First position after the gap. |
| `implied_speed_kn` | float | kn | yes | Great-circle distance between last and next fix over the gap time. |
| `draught_before_m`, `draught_after_m` | float | m | yes | For the draught-jump signal. |
| `neighbours_heard` | int | | no | Distinct other vessels with a position inside 20 km of `last_lat/lon` during the gap window (open: since `start_ts`; use only the last 10 minutes for the "still silent" test). |
| `neighbours_baseline` | int | | no | Same count over the 30 minutes **before** `start_ts`. |
| `cell_id` | str | | no | Coverage cell of the last position (2.9). |
| `coverage_flag` | str | | no | `deliberate_candidate` (neighbours heard, cell healthy), `coverage_gap` (cell quiet or neighbours silent too), `own_stall` (overlaps one of our ingest stalls), `unknown` (no neighbours in baseline, e.g. open sea). Only `deliberate_candidate` counts as "went dark" for labels and the watchlist. |
| `src` | str | | no | `derived`, or `gfw` for imported labels. |
| `gfw_intentional` | bool | | yes | Only for `src = gfw`. |
| `q` | list[str] | | no | |

### 2.5 SpoofEvent (R) `spoofs` table, `kind: "spoof"`

| Field | Type | Unit | Null? | Meaning |
|---|---|---|---|---|
| `id` | str | | no | `spoof-{type}-{mmsi}-{ts}`. |
| `mmsi` | int | | no | |
| `ts` | ts | ms | no | Event time of the offending fix (second one of a pair). |
| `detected_at` | ts | ms | no | |
| `type` | str | | no | `jump` (implied speed above the limit for the type), `on_land` (O), `circling_at_anchor` (reports `nav_status` 1 or 5 but track is a tight loop), `duplicate_mmsi`, `mmsi_change`, `imo_change`, `flag_mismatch` (O). |
| `severity` | float | | no | 0 to 1. Detector's own scale. |
| `evidence` | json | | no | Type-specific dict. `jump`: `{from:{ts,lat,lon}, to:{ts,lat,lon}, dist_m, implied_kn, limit_kn}`. `circling_at_anchor`: `{window_s, radius_m, path_m, nav_status}`. `*_change`: `{old, new, first_seen_ts, last_seen_ts}`. `duplicate_mmsi`: `{a:{ts,lat,lon}, b:{ts,lat,lon}, dist_m, dt_s}`. |
| `jamming_suspect` | bool | | no | True if at least 5 vessels in the same cell showed a jump within 10 minutes. These are shown differently and **excluded from the model's spoof features**. |
| `cell_id` | str | | no | |
| `src` | str | | no | `derived`. |

### 2.6 SanctionsMatch (R) `sanctions` table (one row per matched vessel), `kind: "sanction"`

Built by loading the OpenSanctions CSV, grouping rows by IMO (or by MMSI when IMO is empty), then matching against `VesselStatic`. Re-matched whenever a new IMO or name arrives.

| Field | Type | Unit | Null? | Meaning |
|---|---|---|---|---|
| `mmsi` | int | | no | Our vessel. |
| `imo` | int | | yes | |
| `match_type` | str | | no | `imo` (exact, confidence 1.0), `mmsi` (exact, 0.9; MMSIs are re-used), `name` (O, normalised name equality, 0.4; **never shown as sanctioned, only as a hint**). |
| `confidence` | float | | no | |
| `os_ids` | list[str] | | no | OpenSanctions entity ids (each row `id`); evidence link is `url`. |
| `os_urls` | list[str] | | no | Evidence links. |
| `datasets` | list[str] | | no | e.g. `eu_journal_sanctions`, `us_ofac_sdn`, `ua_war_sanctions`. |
| `risk_tags` | list[str] | | no | e.g. `sanction`, `mare.shadow`, `mare.detained`, `poi`. |
| `is_sanctioned` | bool | | no | `risk_tags` contains `sanction`. |
| `is_shadow_tagged` | bool | | no | contains `mare.shadow`. |
| `os_flag` | str | | yes | Lower-case ISO2 as given. |
| `list_version` | str | | no | The `run` folder name of the CSV (e.g. `20261107150307-kpx`). |
| `matched_at` | ts | ms | no | |

### 2.7 RiskScore / Forecast (R) `scores` table, `kind: "score"`

One row per `(mmsi, target, made_at)`. Written every scoring cycle (default 5 minutes) for every **active** vessel; only changed or top-ranked ones go to the browser.

| Field | Type | Unit | Null? | Meaning |
|---|---|---|---|---|
| `id` | str | | no | `score-{mmsi}-{target}-{made_at}`. |
| `mmsi` | int | | no | |
| `target` | str | | no | `dark_6h` (primary: a `deliberate_candidate` gap starts within the horizon), `spoof_6h` (O: a non-jamming SpoofEvent within the horizon). |
| `made_at` | ts | ms | no | The **as_of** time: the model saw only records with `recv_ts <= made_at`. |
| `horizon_s` | int | s | no | 21600 for 6 h. Label window is `(made_at, made_at + horizon_s]`. |
| `p` | float | | no | Probability, calibrated. |
| `model_version` | str | | no | e.g. `lgbm-2026-11-07a`; `baseline-tankers`, `baseline-prior-gap` for the baselines. |
| `feature_version` | str | | no | Version of the feature list. |
| `features` | json | | no | Snapshot of every input value the model used (dict name to number or null). This is what the UI explains and what a backtest re-checks. |
| `contrib` | json | | yes | O: top signed contributions (name to value) for the "why" panel. |
| `mode` | str | | no | `live`, `replay` or `backtest`. A score from the live run and one from a later backtest of the same time are different rows; evaluation of "forecast made early in the hackathon" uses `mode = live` only. |

### 2.8 WatchlistEntry (R) `watchlist` table, `kind: "watch"`

A snapshot of the ranked inspection list, refreshed every cycle. The table keeps every snapshot (top 50 only).

| Field | Type | Unit | Null? | Meaning |
|---|---|---|---|---|
| `snapshot_ts` | ts | ms | no | Equal to the `made_at` of the scores it ranks. |
| `rank` | int | | no | 1 is the top. |
| `mmsi` | int | | no | |
| `score_id` | str | | no | Link to the `RiskScore`. |
| `p` | float | | no | |
| `decision` | str | | no | `inspect` (rank <= K and `p >= p_alert`), `watch`, `none`. |
| `reason_codes` | list[str] | | no | Fixed set: `OPEN_GAP`, `RECENT_GAP`, `SPOOF_JUMP`, `SPOOF_CIRCLING`, `ID_CHANGE`, `FLAG_MISMATCH`, `SANCTIONED`, `SHADOW_TAGGED`, `DRAUGHT_JUMP`, `LOITERING`, `NEAR_TRANSFER_AREA` (O), `BLANK_DESTINATION`, `HIGH_FORECAST`. |
| `evidence` | list[obj] | | no | Each `{kind: "gap"\|"spoof"\|"sanction"\|"score", id: str, label: str, url?: str}`. IDs point at rows in the other tables; `url` is used for OpenSanctions pages. |
| `prev_rank` | int | | yes | For the up/down arrow. |

### 2.9 CoverageCell (R) `coverage` table, `kind: "cov"`

Grid: `cell_id = f"{floor(lat*10)}_{floor(lon*10)}"` (0.1 degree squares, about 11 km by 5.5 km at 60 N). One row per `(cell_id, bucket_ts)`, bucket = 1 hour for history; the live reducer also keeps a 15-minute sliding value.

| Field | Type | Unit | Null? | Meaning |
|---|---|---|---|---|
| `cell_id` | str | | no | |
| `bucket_ts` | ts | ms | no | Start of the hour. |
| `n_msgs` | int | | no | Vessel position messages received in the cell. |
| `n_vessels` | int | | no | Distinct MMSIs heard. |
| `n_src` | json | | no | Messages per source. |
| `expected_vessels` | float | | yes | Median `n_vessels` for this cell and hour-of-day over the recorded history (null for the first day). |
| `coverage_score` | float | | no | `min(1, n_vessels / expected_vessels)`; if `expected_vessels` is null, 1 when `n_vessels >= 1` else 0 (unknown). |
| `state` | str | | no | `ok` (>= 0.5), `degraded` (0.1 to 0.5), `dead` (< 0.1 and expected > 0). The cell state is what turns a candidate gap into `coverage_gap`. |

### 2.10 Outcome (R) `outcomes` table, `kind: "outcome"`

Written after `made_at + horizon_s` has passed (plus a grace of 30 minutes for late data). This is the evaluation table.

| Field | Type | Unit | Null? | Meaning |
|---|---|---|---|---|
| `score_id` | str | | no | One outcome per `RiskScore`. |
| `mmsi`, `target`, `made_at`, `horizon_s` | | | no | Copied for fast joins. |
| `resolved_at` | ts | ms | no | When the label was fixed. |
| `label` | bool | | yes | True if a qualifying event started in the window. Null when censored. |
| `censored` | str | | yes | `coverage_gap` (the only candidate was in a dead cell), `own_stall`, `data_end` (window runs past the end of the log), `already_dark` (vessel was in an open gap at `made_at`; excluded from scoring). |
| `event_id` | str | | yes | The `GapEvent.id` or `SpoofEvent.id` that made the label true. |
| `lead_s` | int | s | yes | `event.start_ts - made_at`. Hours of warning. |

### 2.11 Small supporting records

| Name | Opt? | Use |
|---|---|---|
| **FeedStatus** `kind: "health"` | R | `{src, ts, state: "up"\|"silent"\|"down"\|"stall", msgs_per_s, queue_depth, note}`. Written by ingest on every state change and every 10 s. The `stall` windows are how a gap that overlaps our own backlog is marked `own_stall`. Also drives the "live source" badge. |
| **SarDetection** `sar_detections` | O | `{id, ts, lat, lon, length_m?, matched: bool, matched_mmsi?, src:"gfw"}` for the radar overlay and the "dark but there" claim. Fields on the GFW side *unverified*. |

## 3. Source mapping

Legend: **ok** maps directly, **conv** needs a conversion (stated), **n/a** the source cannot fill it. All lat/lon in source order noted.

### 3.1 AISStream (live, JSON over WebSocket)

Envelope: `{"MessageType": "...", "MetaData": {...}, "Message": {"<MessageType>": {...}}}`. Verified field names from `type-definition.yaml`; MetaData `time_utc`, `MMSI_String`, lower-case `latitude/longitude` from third-party samples (accept both cases).

| Canonical | PositionReport (1-3) | StandardClassB (18) | ExtendedClassB (19) | ShipStaticData (5) | StaticDataReport (24) |
|---|---|---|---|---|---|
| `mmsi` | `Message.*.UserID` | same | same | same | same |
| `recv_ts` | `MetaData.time_utc` parsed (fallback: local clock) | same | same | same | same |
| `ts` | rebuilt from `Timestamp` + `recv_ts` | same | same | = `recv_ts` | = `recv_ts` |
| `lat`, `lon` | `Latitude`, `Longitude` (conv: drop if 91 / 181 or `Valid=false`) | same | same | n/a | n/a |
| `sog_kn` | `Sog` (conv: 102.3 -> null) | same | same | n/a | n/a |
| `cog_deg` | `Cog` (360 -> null) | same | same | n/a | n/a |
| `heading_deg` | `TrueHeading` (511 -> null) | same | same | n/a | n/a |
| `nav_status` | `NavigationalStatus` (15 -> null) | n/a (null) | n/a | n/a | n/a |
| `cls` | `"A"` | `"B"` | `"B"` | `"A"` | `"B"` |
| `msg_type` | `MessageID` | 18 | 19 | 5 | 24 |
| `imo` | n/a | n/a | n/a | `ImoNumber` (0 -> null) | n/a (Class B has no IMO) |
| `name` | `MetaData.ShipName` (trim) | `MetaData.ShipName` | `Name` | `Name` | `ReportA.Name` |
| `callsign` | n/a | n/a | n/a | `CallSign` | `ReportB.CallSign` |
| `ship_type` | n/a | n/a | `Type` | `Type` | `ReportB.ShipType` |
| `dim_a..d_m` | n/a | n/a | `Dimension.A..D` | `Dimension.A..D` | `ReportB.Dimension.A..D` |
| `draught_m` | n/a | n/a | n/a | `MaximumStaticDraught` (assume metres; verify) | n/a |
| `destination` | n/a | n/a | n/a | `Destination` | n/a |
| `eta_utc` | n/a | n/a | n/a | `Eta{Month,Day,Hour,Minute}`, year inferred | n/a |

AISStream **cannot** fill: heading/nav status for Class B (not sent), IMO for Class B, a true instrument timestamp (only the second-of-minute), any history (no replay). Position-bearing types 9, 21 and 27 are ignored. Messages that carry both a position and a name (type 19, and `MetaData.ShipName` on any type) emit a `PositionReport` and, if the name changed, a partial `VesselStatic`. Boolean fields `Valid`, `Raim`, `PositionAccuracy` are not stored (use `Valid=false` as a drop rule).

### 3.2 Digitraffic (live backup and REST, Finland)

REST `/api/ais/v1/locations` (GeoJSON) and `/api/ais/v1/vessels` (array). MQTT `vessels-v2/<mmsi>/location` and `.../metadata`. Send header `Digitraffic-User: hedgedbets/dvm`.

| Canonical | REST location | MQTT location | REST vessels (metadata) | MQTT metadata |
|---|---|---|---|---|
| `mmsi` | `mmsi` | topic segment 2 | `mmsi` | topic segment 2 |
| `recv_ts` | `properties.timestampExternal` (ms) | `time` * 1000 (**whole seconds only**) | `timestamp` (ms) | `timestamp` (ms) |
| `ts` | rebuilt from `properties.timestamp` (second) + `recv_ts` | the MQTT payload has no second-of-minute field, so `ts = recv_ts`, `ts_quality = "recv_only"` (up to 1 s of rounding) | = `recv_ts` | = `recv_ts` |
| `lat`, `lon` | `geometry.coordinates` = **[lon, lat]** | `lat`, `lon` | n/a | n/a |
| `sog_kn` | `sog` (102.3 -> null) | `sog` | n/a | n/a |
| `cog_deg` | `cog` (360 -> null) | `cog` | n/a | n/a |
| `heading_deg` | `heading` (511 -> null) | `heading` | n/a | n/a |
| `nav_status` | `navStat` (15 -> null) | `navStat` | n/a | n/a |
| `cls` | **not given**; default `"A"` if `navStat` is 0 to 14 or `rot` is not -128, else `"B"` (a guess; Class B sends neither). Decision 4 depends on it | same | n/a | n/a |
| `msg_type` | 0 | 0 | 0 | 0 |
| `imo` | n/a | n/a | `imo` (0 -> null) | `imo` |
| `name` | n/a | n/a | `name` (trim) | `name` |
| `callsign` | n/a | n/a | `callSign` | `callSign` |
| `ship_type` | n/a | n/a | `shipType` | `type` |
| `dim_a..d_m` | n/a | n/a | `referencePointA..D` | `refA..refD` |
| `draught_m` | n/a | n/a | `draught` / 10 (0 -> null; 255 means 25.5 m or more) | same |
| `destination` | n/a | n/a | `destination` (`"0"` -> null) | same |
| `eta_utc` | n/a | n/a | `eta` unpacked: month `(eta>>16)&15`, day `(eta>>11)&31`, hour `(eta>>6)&31`, minute `eta&63`; year inferred | same |

Digitraffic **cannot** fill: a reliable second-of-minute on MQTT (so `ts` has up to 1 s rounding, fine), ship class A/B (guess or null), anything outside the Finnish receiver network. **Check on the first connection which of the two location formats the MQTT broker really sends** (the docs page shows `time`/`lat`/`lon`; the REST schema shows GeoJSON).

### 3.3 Kystverket raw NMEA (optional second spare, decoded by pyais)

Raw `!AIVDM` sentences over TCP `153.44.253.27:5631`. pyais `decode()` handles multi-sentence messages (type 5). The decoded dict is mapped as follows. **Not tested live**: port 5631 may be blocked on venue Wi-Fi, and I did not confirm whether the stream carries a tag block with a timestamp (pyais can read `c:` epoch seconds into `tag_block.receiver_timestamp`; if absent use the local clock).

| Canonical | Type 1/2/3 | Type 18 | Type 19 | Type 5 | Type 24 |
|---|---|---|---|---|---|
| `mmsi` | `mmsi` | same | same | same | same |
| `recv_ts` | tag block `c:` * 1000, else local clock | same | same | same | same |
| `ts` | rebuilt from `second` | same | same | = `recv_ts` | = `recv_ts` |
| `lat`, `lon` | `lat`, `lon` (91 / 181 -> drop) | same | same | n/a | n/a |
| `sog_kn` | `speed` (102.3 -> null) | `speed` | `speed` | n/a | n/a |
| `cog_deg` | `course` (360 -> null) | `course` | `course` | n/a | n/a |
| `heading_deg` | `heading` (511 -> null) | `heading` | `heading` | n/a | n/a |
| `nav_status` | `status.value` | n/a | n/a | n/a | n/a |
| `imo` | n/a | n/a | n/a | `imo` | n/a |
| `name` | n/a | n/a | `shipname` | `shipname` | part A `shipname` |
| `callsign` | n/a | n/a | n/a | `callsign` | part B `callsign` |
| `ship_type` | n/a | n/a | `ship_type.value` | `ship_type.value` | part B `ship_type` |
| `dim_*` | n/a | n/a | `to_bow, to_stern, to_port, to_starboard` = A, B, C, D | same | part B `to_*` |
| `draught_m` | n/a | n/a | n/a | `draught` (already metres) | n/a |
| `destination` | n/a | n/a | n/a | `destination` | n/a |
| `eta_utc` | n/a | n/a | n/a | `month, day, hour, minute` | n/a |

### 3.4 Danish Maritime Authority CSV (history for training and backtest)

One zip per day, one CSV inside, `aisdk-YYYY-MM-DD.csv`. URL pattern `http://aisdata.ais.dk/<year>/aisdk-<YYYY>-<MM>-<DD>.zip` (listing: `http://aisdata.ais.dk.s3.eu-central-1.amazonaws.com/?prefix=2025`). Verified header and sample rows. Read with Polars `read_csv(..., encoding="latin1", infer_schema_length=0)`, then cast.

| Canonical | DMA column | Conversion |
|---|---|---|
| `mmsi` | `MMSI` | int; drop rows where `Type of mobile` is not `Class A` or `Class B` (this removes `Base Station`, `AtoN`, SAR, etc.) |
| `ts`, `recv_ts` | `# Timestamp` | parse `dd/mm/yyyy HH:MM:SS` as UTC; `ts = recv_ts`; `ts_quality = "source"` |
| `lat`, `lon` | `Latitude`, `Longitude` | float |
| `sog_kn` | `SOG` | float; blank -> null |
| `cog_deg` | `COG` | float |
| `heading_deg` | `Heading` | int |
| `nav_status` | `Navigational status` | **text to code** map: `Under way using engine`=0, `At anchor`=1, `Not under command`=2, `Restricted manoeuvrability`=3, `Constrained by her draught`=4, `Moored`=5, `Aground`=6, `Engaged in fishing`=7, `Under way sailing`=8, others by index; `Unknown value` -> null |
| `cls` | `Type of mobile` | `Class A` -> A, `Class B` -> B |
| `msg_type` | n/a | 0 |
| `imo` | `IMO` | `Unknown` or blank -> null |
| `name` | `Name` | blank -> null |
| `callsign` | `Callsign` | `Unknown` -> null |
| `ship_type` | `Ship type` | **text**, not code. Map text to `type_group` directly, and store a representative `ship_type`: `Tanker`=80, `Cargo`=70, `Passenger`=60, `Fishing`=30, `Tug`=52, `Military`=35, `Pleasure`=37, `Sailing`=36, other known text -> 90, `Undefined` -> null. Good enough for `type_group`; not for sub-types (e.g. crude vs chemical) |
| `dim_a..d_m` | `A`, `B`, `C`, `D` | int |
| `length_m`, `beam_m` | `Length`, `Width` (use these if A..D blank) | |
| `draught_m` | `Draught` | float metres |
| `destination` | `Destination` | `Unknown` -> null |
| `eta_utc` | `ETA` | parse `dd/mm/yyyy HH:MM:SS` (full date with year, no inference) |

DMA **cannot** fill: a separate event time vs receive time (one column only), `msg_type`, heading for Class B in many rows, anything outside Danish receiver range, any "who else was heard" beyond what is in the same file (fine: the file is the whole network). Static columns are **blank on most rows** and filled on some: build `VesselStatic` from distinct non-null static tuples per MMSI, emitted at the `ts` of the row where they first appear or change. Rows are about 2 to 10 s apart for moving Class A ships; the raw file is several million rows per day, so crop to the Baltic box before anything else.

### 3.5 OpenSanctions maritime CSV

| Canonical (`SanctionsMatch`) | CSV column | Conversion |
|---|---|---|
| `imo` | `imo` | strip the `IMO` prefix, int; blank -> null |
| `mmsi` (source side) | `mmsi` | int; blank for about 69 % of rows |
| `os_ids` | `id` | collected over duplicate rows |
| `os_urls` | `url` | |
| `datasets` | `datasets` | split on `;` |
| `risk_tags` | `risk` | split on `;` |
| `os_flag` | `flag` (fallback `countries`) | |
| name hint | `caption`, `aliases` | normalise: upper case, strip punctuation and `MT `/`M/V ` |
| `list_version` | URL path run id | |

Group rows by IMO first (`datasets` and `risk` are unioned), then index by IMO and by MMSI. It **cannot** give designation dates (confirmed absent from the CSV columns), so "flagged before sanctioned" is not testable from this file.

### 3.6 Global Fishing Watch v3 (evaluation only; **fields unverified, token needed**)

| Canonical | GFW gap event (`public-global-gaps-events:latest`) | Note |
|---|---|---|
| `GapEvent.mmsi` | `vessel.ssvid` | |
| `start_ts`, `end_ts` | `start`, `end` (ISO strings) | |
| `last_lat/lon` | `gap.offPosition` (guess) | confirm key names on first response |
| `next_lat/lon` | `gap.onPosition` (guess) | |
| `duration_s` | `gap.durationHours * 3600` (guess) | |
| `implied_speed_kn` | `gap.impliedSpeedKnots` (guess) | |
| `gfw_intentional` | `gap.intentionalDisabling` (guess) | The GFW rule: at least 12 h, starts at least 50 nm from shore, good reception (from Jake's research, gfwr notes). Their gaps are far too long for our 6 h horizon. |
| `neighbours_heard`, `coverage_flag`, `cell_id` | n/a | GFW gives none. Compute our own from the log if the gap falls inside it. |

GFW **cannot** be used live (events lag), and SAR detections lag at least 5 days. Both enter only as `src = "gfw"` rows for the backtest and as the radar overlay.

## 4. Storage and transport

### 4.1 Raw append-only log (the replay source)

One directory `data/raw/`; one **JSON Lines file per source per hour**, gzip-closed on rotation: `data/raw/aisstream/2026-11-07T16.jsonl.gz`. A line is an **envelope**, not a canonical record:

```json
{"v":1,"src":"aisstream","recv_ts":1794068101234,"raw":{"MessageType":"PositionReport","MetaData":{"MMSI":538003705,"ShipName":"EXAMPLE ","latitude":60.056,"longitude":28.411,"time_utc":"2026-11-07 16:15:01.234567 +0000 UTC"},"Message":{"PositionReport":{"MessageID":1,"UserID":538003705,"Sog":13.0,"Cog":120.3,"TrueHeading":117,"Latitude":60.056268,"Longitude":28.411697,"Timestamp":1,"NavigationalStatus":0}}}}
```

- `raw` is the **original payload unchanged** (object for JSON sources, string for NMEA, GeoJSON feature for Digitraffic REST). `recv_ts` is **our local clock at socket read**, written before any parsing, and is the replay clock. Storing raw means a bug in `normalise()` can be fixed and the whole night re-processed.
- Writes are `append + flush` every second; one writer task fed by an `asyncio.Queue`. The reader loop only enqueues (the failure playbook in Jake's research).
- Health lines go to the same stream: `{"v":1,"src":"_health","recv_ts":...,"raw":{<FeedStatus>}}`.
- Size: roughly 300 bytes a message; at an assumed 200 msg/s that is about 2 GB a day gzipped to ~300 MB. **The real rate is unmeasured; measure it in hour one.**

**Replay reads it back through the same path as live:**

```
live:    socket  -> envelope(src, recv_ts, raw) -> LOG.write(envelope)
                                                -> normalise(envelope) -> Records -> pipeline.sink(rec)
replay:  LOG.read(hour files, merged by recv_ts) -> normalise(envelope) -> Records -> pipeline.sink(rec)
         (clock: wait (env.recv_ts - prev_recv_ts) / speed, or no wait for backtest)
```

`normalise(envelope) -> list[Record]` is the **only** function that knows source formats. `pipeline.sink` is the only entry into detectors and state. A flag `mode` ("live" or "replay") is carried by the pipeline for scores and the WebSocket `hello`, never by records. Replay uses `recv_ts` from the envelope as the clock source for detectors (not the wall clock), so results are deterministic.

The DMA history does not go through an envelope. `dma_to_records(csv) -> Iterator[Record]` yields canonical records directly (it is its own `normalise`), and the loader writes them to Parquet and can also feed `pipeline.sink` in `recv_ts` order for a backtest.

### 4.2 Parquet and Polars tables

Hive-partitioned by UTC date of `recv_ts`: `data/parquet/<table>/date=2026-11-07/part-*.parquet`. Written by a batch job that runs `normalise` over the raw log (so live-recorded days and DMA days have the same schema). Polars schema (`ts` columns are `Int64` ms on disk; convert with `pl.from_epoch(pl.col("ts"), "ms")` only when needed for resampling).

| Table | Key | Main columns (see section 2) |
|---|---|---|
| `positions` | `(mmsi, ts, lat, lon)` | all of 2.1; `mmsi: Int64`, `ts, recv_ts: Int64`, floats `Float64`, `q: List(Utf8)`, `src/cls/ts_quality: Categorical` |
| `statics` | `(mmsi, ts)` | all of 2.2 |
| `gaps` | `(id, version)` | 2.4; latest version via `.sort("version").group_by("id").last()` |
| `spoofs` | `id` | 2.5; `evidence` as a JSON string column |
| `scores` | `id` | 2.7; `features` as a JSON string column (also flattened to `f_*` columns in the training view) |
| `watchlist` | `(snapshot_ts, rank)` | 2.8 |
| `outcomes` | `score_id` | 2.10 |
| `coverage` | `(cell_id, bucket_ts)` | 2.9 |
| `sanctions` | `mmsi` | 2.6 (overwritten each load) |

The live process keeps an in-memory ring (last 24 h of positions in Polars, or simply per-vessel deques) and appends to Parquet every 5 minutes in row groups. Nothing reads a half-written file: writers write `part-*.tmp` then rename.

### 4.3 WebSocket to the browser (FastAPI, one socket, JSON text frames)

Rules: server pushes a **delta every 1000 ms** (skipped if empty, but a `ping` goes every 10 s). Each delta contains **whole `VesselView` objects for vessels that changed**, never partial field patches (simplest for the client; a vessel is about 200 bytes so 500 changes a second is 100 KB). Times are epoch ms; coordinates are `lon`, `lat` numbers. Every message has `type` and `seq` (increments by 1 per server message; a gap in `seq` means the client must reconnect and take a new `snapshot`). Schema version in `hello`.

`VesselView` (what the map needs, not the full `Vessel`):
`mmsi, name, imo, flag, type_group, length_m, lat, lon, sog_kn, cog_deg, heading_deg, last_ts, status, open_gap_id, risk_p, risk_rank, sanctioned, spoof_recent`.

**Server to client**

`hello` (first message):
```json
{"type":"hello","seq":1,"schema":1,"mode":"live","speed":1,"now_ts":1794068101000,
 "sources":[{"src":"aisstream","state":"up","msgs_per_s":142.3},{"src":"digitraffic","state":"up","msgs_per_s":38.0}],
 "bbox":[[19.0,54.0],[31.0,61.0]]}
```

`snapshot` (after hello, and on request):
```json
{"type":"snapshot","seq":2,"now_ts":1794068101000,
 "vessels":[{"mmsi":538003705,"name":"EXAMPLE","imo":9390862,"flag":"MH","type_group":"tanker","length_m":249,
   "lat":60.0563,"lon":28.4117,"sog_kn":13.0,"cog_deg":120.3,"heading_deg":117,"last_ts":1794068101000,
   "status":"active","open_gap_id":null,"risk_p":0.12,"risk_rank":null,"sanctioned":false,"spoof_recent":[]}],
 "trails":{"538003705":[[1794066300000,28.20,60.00],[1794066360000,28.25,60.01]]},
 "gaps":[],"spoofs":[],"watchlist":{"snapshot_ts":1794068100000,"entries":[]},
 "coverage":[{"cell_id":"600_284","state":"ok","coverage_score":0.93}],
 "stats":{"tracked":2412,"msgs_per_s":180.3,"queue_depth":12}}
```
`trails`: `{mmsi: [[ts, lon, lat], ...]}`, at most 30 points per vessel, at least 60 s apart, last 60 minutes. Coverage lists only cells that are not `ok` or are inside the current viewport.

`delta` (every second):
```json
{"type":"delta","seq":3,"now_ts":1794068102000,
 "vessels":[{"mmsi":538003705,"name":"EXAMPLE","imo":9390862,"flag":"MH","type_group":"tanker","length_m":249,
   "lat":60.0571,"lon":28.4130,"sog_kn":13.1,"cog_deg":120.2,"heading_deg":117,"last_ts":1794068102000,
   "status":"gap_open","open_gap_id":"gap-538003705-1794068102000","risk_p":0.61,"risk_rank":4,"sanctioned":true,"spoof_recent":[]}],
 "removed":[311001866],
 "gaps":[{"id":"gap-538003705-1794068102000","version":2,"mmsi":538003705,"state":"open","start_ts":1794068102000,"end_ts":null,
   "duration_s":1200,"last_lat":60.0571,"last_lon":28.4130,"last_sog_kn":13.1,"last_cog_deg":120.2,"next_lat":null,"next_lon":null,
   "neighbours_heard":14,"neighbours_baseline":16,"cell_id":"600_284","coverage_flag":"deliberate_candidate","radius_m":8400}],
 "spoofs":[{"id":"spoof-jump-265546930-1794068050000","mmsi":265546930,"ts":1794068050000,"type":"jump","severity":0.9,
   "jamming_suspect":false,"evidence":{"dist_m":42100,"implied_kn":181.0,"limit_kn":40}}],
 "watchlist":null,
 "stats":{"tracked":2413,"msgs_per_s":176.9,"queue_depth":9}}
```
`radius_m` in a gap is a derived UI field (`last_sog_kn` converted to m/s times `duration_s`, capped), added by the server so the front end draws the ghost circle without maths. `watchlist` is `null` unless it changed (see next).

`watchlist` (sent when rank order or any `p` changes by more than 0.02, at most every 5 s; it can also be included in a delta):
```json
{"type":"watchlist","seq":4,"snapshot_ts":1794068100000,"entries":[
 {"rank":1,"mmsi":538003705,"name":"EXAMPLE","p":0.74,"decision":"inspect","prev_rank":2,
  "reason_codes":["OPEN_GAP","SANCTIONED","DRAUGHT_JUMP"],
  "evidence":[{"kind":"gap","id":"gap-538003705-1794068102000","label":"Silent 20 min, 14 neighbours still heard"},
              {"kind":"sanction","id":"eu-oj-4040af042492462ea3b81288a1c82de917ac029c","label":"EU sanctions list","url":"https://www.opensanctions.org/entities/eu-oj-4040af042492462ea3b81288a1c82de917ac029c"}]}]}
```

`status` (feed state change, replay position):
```json
{"type":"status","seq":5,"now_ts":1794068103000,"mode":"replay","speed":30,
 "sources":[{"src":"aisstream","state":"silent","msgs_per_s":0.0},{"src":"digitraffic","state":"up","msgs_per_s":40.1}],
 "replay":{"from_ts":1794000000000,"to_ts":1794086400000}}
```

**Client to server**

```json
{"type":"subscribe","bbox":[[19.0,54.0],[31.0,61.0]],"min_status":"active"}
{"type":"replay","action":"seek","t":1794050000000}
{"type":"replay","action":"speed","speed":30}
{"type":"replay","action":"pause"}
{"type":"detail","mmsi":538003705}
```
`detail` is answered with one `detail` message: `{"type":"detail","seq":n,"mmsi":...,"vessel":<full Vessel>,"statics":[last 5 VesselStatic],"gaps":[...],"spoofs":[...],"sanction":<SanctionsMatch>|null,"score":<RiskScore with features>}`. This is how the evidence panel gets the features snapshot without sending it every second.

## 5. How each consumer uses the model

One-line rule per consumer; the same records in the same order produce the same output in all three modes (live, replay, backtest).

| Consumer | Reads | Writes | Notes |
|---|---|---|---|
| **Ingest** | source sockets/files | raw log, then `PositionReport`, `VesselStatic`, `FeedStatus` via `normalise` | Reader loop only enqueues. De-duplicates (1.5). Sets `recv_ts` first. Marks `own_stall` windows when queue depth exceeds a limit. |
| **State reducer** | records, `sanctions` | `Vessel` (memory), `CoverageCell` | Single writer of `Vessel`. Updates `report_interval_s`, `status`. Maintains the neighbour grid (dict of cell to set of MMSI heard in the last 10 min). |
| **Gap detector** | `Vessel`, neighbour grid, `CoverageCell`, `FeedStatus` | `GapEvent` | Runs every 5 s on `recv_ts` clock. Opens when `now - last_recv_ts > max(floor_s, k * report_interval_s)` (defaults: floor 1800 s, k = 20). Sets `coverage_flag` using `neighbours_heard >= 3`, cell not `dead`, and no overlapping stall. Closes on the next position. |
| **Spoof detector** | `PositionReport` pairs (by `ts`), `VesselStatic` history | `SpoofEvent` | Skips records with `late` flag. Jump limit by `type_group` (tanker/cargo 35 kn, others 60 kn; guess, tune). Marks `jamming_suspect` from cell counts. |
| **Sanctions join** | `VesselStatic`, OpenSanctions CSV | `SanctionsMatch` | Run on every new IMO and once per name change. |
| **Forecast: features** | `positions`, `statics`, `gaps`, `spoofs`, `sanctions`, `coverage` | feature rows | `build_features(mmsi, as_of)` uses only rows with `recv_ts <= as_of` (and `detected_at <= as_of` for events). See below. |
| **Forecast: scoring** | feature row | `RiskScore` | Every 5 min for every `active` vessel. |
| **Watchlist** | latest `RiskScore`, open `GapEvent`/`SpoofEvent`, `SanctionsMatch` | `WatchlistEntry` | Sort by `p`; the reason codes are computed from the evidence rows, not from the model. Hard rule: `SANCTIONED` and `OPEN_GAP` can raise the decision to `watch` but not above `inspect` threshold on their own. |
| **Front end** | WebSocket only | none | Never touches Parquet or the raw log. |
| **Evaluation** | `scores`, `watchlist`, `gaps`, `spoofs`, `sanctions`, `outcomes` | `Outcome` | Section 5.3. |

### 5.1 Forecast without leakage

Three clocks, kept apart:

- `as_of` = `made_at` (the scoring moment).
- Feature inputs: only rows with `recv_ts <= as_of`. For history that has no separate receive time (DMA), `recv_ts = ts`, so this is the same rule.
- Label window: `(as_of, as_of + horizon_s]`, measured on **event time `start_ts`** of a `GapEvent` with `coverage_flag = deliberate_candidate`. Labels are built **after** `as_of + horizon_s + 30 min` from the full gap table, never from the live feature path.

Rules that make this safe:

1. The feature code takes `(store, mmsi, as_of)` and nothing else. In the backtest it is called with `as_of` stepping through history; there is no code path that reads "all data".
2. A gap that is **open at `as_of`** is a feature (`open_gap_age_s`), and that sample is censored (`already_dark`) because the label would be trivially true.
3. Static data is as-of joined: `statics.join_asof(samples, on="recv_ts", by="mmsi", strategy="backward")`.
4. The coverage baseline (`expected_vessels`) for a time uses only days **before** that day.
5. **Sanctions are a feature only in the "with list" model.** The list is today's list, so for old days it knows the future. The headline "behaviour alone" model hides `sanctioned`, `is_shadow_tagged` and uses them only as the label for a `shadow_prior` score and for the evaluation ablation.
6. Train and test are split **by vessel** (not by time slice within a vessel) and also by time (the last day is never in training).
7. Sampling for training: every 15 min per `active` vessel. Drop samples whose window runs past the end of the data (`data_end`), samples in dead cells at `as_of`, and `already_dark`.

Starting feature list (all computed from canonical fields, name in `features` JSON): `gaps_24h`, `gaps_7d`, `longest_gap_s_7d`, `time_since_last_gap_s`, `open_gap_age_s`, `report_interval_s`, `sog_kn`, `sog_mean_1h`, `loiter_frac_1h` (share of 1 h under 1 kn), `dist_to_nearest_port_m` (O), `dist_to_primorsk_ustluga_m` (O), `type_group` (one-hot), `length_m`, `draught_m`, `draught_jump_m_24h`, `dest_blank`, `dest_changes_7d`, `spoof_events_24h`, `id_change_flag`, `flag_is_flag_of_convenience` (list in repo), `hour_of_day`, `neighbour_density_20km`, `cell_coverage_score`.

### 5.2 Same model for live, replay and backtest

| | Live | Replay | Backtest |
|---|---|---|---|
| Record source | socket, via `normalise` | raw log, via `normalise` | raw log or DMA Parquet |
| Clock | wall clock for the scheduler, `recv_ts` for data | envelope `recv_ts` / speed | envelope `recv_ts`, no sleeping |
| Detectors, reducer, features, scorer | same code | same code | same code |
| Output `mode` on `RiskScore` | `live` | `replay` | `backtest` |
| Writes to browser | yes | yes (labelled "Replay") | no |

### 5.3 Evaluation

Everything is computed from tables, not from the pipeline.

1. For each `RiskScore` with `mode = live`, wait for the window, then write an `Outcome` (rules in 2.10).
2. **Precision@K**: for each `WatchlistEntry` snapshot, take the top K rows, join `outcomes` on `score_id`, ignore `censored` rows, report mean precision with the count of non-censored rows. Same table for `model_version = baseline-tankers` (all tankers ranked by past gap count) and `baseline-prior-gap` (vessels with a gap in the last 24 h), so baselines are just other `model_version` values written by simple scorers, in the same schema.
3. **Calibration**: bin `p` into deciles and compare to the mean label.
4. **Lead time**: `lead_s` of true positives (hours of warning).
5. **Ablation**: re-score the backtest with feature groups removed; each gets its own `model_version`.
6. **Sanctions check**: `sanctions.is_sanctioned` as a label for a `shadow_prior` score, hidden from the model.

## 6. Code sketches

### 6.1 Python (Pydantic v2; fine at hundreds of messages a second, and `model_dump_json` / discriminated unions help)

```python
# dvm/models.py
from __future__ import annotations
from typing import Annotated, Literal, Optional, Union
from pydantic import BaseModel, ConfigDict, Field

Src = Literal["aisstream", "digitraffic", "kystverket", "dma", "gfw", "opensanctions", "derived"]
Q = Literal["late", "ts_recv_only", "sog_na", "cog_na", "hdg_na", "imo_bad_checksum",
            "dup_other_src", "jam_suspect", "own_stall"]
TypeGroup = Literal["tanker", "cargo", "passenger", "fishing", "tug_special", "military",
                    "pleasure", "other", "unknown"]

class Rec(BaseModel):
    model_config = ConfigDict(frozen=True)

class PositionReport(Rec):
    kind: Literal["pos"] = "pos"
    mmsi: int
    ts: int                      # event time, epoch ms UTC
    recv_ts: int                 # received time, epoch ms UTC
    lat: float
    lon: float
    sog_kn: Optional[float] = None
    cog_deg: Optional[float] = None
    heading_deg: Optional[int] = None
    nav_status: Optional[int] = None
    cls: Literal["A", "B"]
    msg_type: int = 0
    ts_quality: Literal["rebuilt", "recv_only", "source"]
    src: Src
    q: list[Q] = []

class VesselStatic(Rec):
    kind: Literal["static"] = "static"
    mmsi: int
    ts: int
    recv_ts: int
    imo: Optional[int] = None
    name: Optional[str] = None
    callsign: Optional[str] = None
    ship_type: Optional[int] = None
    type_group: TypeGroup = "unknown"
    dim_a_m: Optional[int] = None
    dim_b_m: Optional[int] = None
    dim_c_m: Optional[int] = None
    dim_d_m: Optional[int] = None
    length_m: Optional[int] = None
    beam_m: Optional[int] = None
    draught_m: Optional[float] = None
    destination: Optional[str] = None
    eta_utc: Optional[int] = None
    mid: int
    flag_iso2: Optional[str] = None
    src: Src
    q: list[Q] = []

class FeedStatus(Rec):
    kind: Literal["health"] = "health"
    src: str
    ts: int
    state: Literal["up", "silent", "down", "stall"]
    msgs_per_s: float = 0.0
    queue_depth: int = 0
    note: Optional[str] = None

Record = Annotated[Union[PositionReport, VesselStatic, FeedStatus], Field(discriminator="kind")]

class GapEvent(BaseModel):
    id: str
    version: int
    mmsi: int
    state: Literal["open", "closed"]
    start_ts: int
    end_ts: Optional[int] = None
    detected_at: int
    duration_s: int
    expected_interval_s: Optional[float] = None
    last_lat: float
    last_lon: float
    last_sog_kn: Optional[float] = None
    last_cog_deg: Optional[float] = None
    last_nav_status: Optional[int] = None
    next_lat: Optional[float] = None
    next_lon: Optional[float] = None
    implied_speed_kn: Optional[float] = None
    draught_before_m: Optional[float] = None
    draught_after_m: Optional[float] = None
    neighbours_heard: int
    neighbours_baseline: int
    cell_id: str
    coverage_flag: Literal["deliberate_candidate", "coverage_gap", "own_stall", "unknown"]
    src: Src = "derived"
    gfw_intentional: Optional[bool] = None
    q: list[Q] = []

class SpoofEvent(BaseModel):
    id: str
    mmsi: int
    ts: int
    detected_at: int
    type: Literal["jump", "on_land", "circling_at_anchor", "duplicate_mmsi",
                  "mmsi_change", "imo_change", "flag_mismatch"]
    severity: float
    evidence: dict
    jamming_suspect: bool = False
    cell_id: str
    src: Src = "derived"

class SanctionsMatch(BaseModel):
    mmsi: int
    imo: Optional[int] = None
    match_type: Literal["imo", "mmsi", "name"]
    confidence: float
    os_ids: list[str]
    os_urls: list[str]
    datasets: list[str]
    risk_tags: list[str]
    is_sanctioned: bool
    is_shadow_tagged: bool
    os_flag: Optional[str] = None
    list_version: str
    matched_at: int

class RiskScore(BaseModel):
    id: str
    mmsi: int
    target: Literal["dark_6h", "spoof_6h", "shadow_prior"]
    made_at: int
    horizon_s: int = 21600
    p: float
    model_version: str
    feature_version: str
    features: dict[str, Optional[float]]
    contrib: Optional[dict[str, float]] = None
    mode: Literal["live", "replay", "backtest"]

class Evidence(BaseModel):
    kind: Literal["gap", "spoof", "sanction", "score"]
    id: str
    label: str
    url: Optional[str] = None

class WatchlistEntry(BaseModel):
    snapshot_ts: int
    rank: int
    mmsi: int
    score_id: str
    p: float
    decision: Literal["inspect", "watch", "none"]
    reason_codes: list[str]
    evidence: list[Evidence]
    prev_rank: Optional[int] = None

class CoverageCell(BaseModel):
    cell_id: str
    bucket_ts: int
    n_msgs: int
    n_vessels: int
    n_src: dict[str, int]
    expected_vessels: Optional[float] = None
    coverage_score: float
    state: Literal["ok", "degraded", "dead"]

class Outcome(BaseModel):
    score_id: str
    mmsi: int
    target: str
    made_at: int
    horizon_s: int
    resolved_at: int
    label: Optional[bool] = None
    censored: Optional[Literal["coverage_gap", "own_stall", "data_end", "already_dark"]] = None
    event_id: Optional[str] = None
    lead_s: Optional[int] = None

class Envelope(BaseModel):          # one line of the raw log
    v: int = 1
    src: str
    recv_ts: int
    raw: object

class VesselView(BaseModel):        # what goes to the browser
    mmsi: int; name: Optional[str]; imo: Optional[int]; flag: Optional[str]
    type_group: TypeGroup; length_m: Optional[int]
    lat: float; lon: float; sog_kn: Optional[float]; cog_deg: Optional[float]
    heading_deg: Optional[int]; last_ts: int
    status: Literal["active", "silent", "gap_open", "stale"]
    open_gap_id: Optional[str]; risk_p: Optional[float]; risk_rank: Optional[int]
    sanctioned: bool; spoof_recent: list[str]
```

Normaliser entry points and the one tricky function, with a self-check:

```python
# dvm/normalise.py
from datetime import datetime, timezone

def rebuild_ts(recv_ts: int, sec: Optional[int]) -> tuple[int, str]:
    """Full UTC ms from second-of-minute and receive time. shortcut: assumes delay < ~55 s."""
    if sec is None or not 0 <= sec <= 59:
        return recv_ts, "recv_only"
    cand = recv_ts - recv_ts % 60_000 + sec * 1000
    if cand > recv_ts + 5_000:
        cand -= 60_000
    return cand, "rebuilt"

def parse_time_utc(s: str) -> int:             # AISStream "2026-11-07 16:15:01.234567 +0000 UTC"
    head = s.split(" +")[0]                      # drop the zone text (it is always UTC)
    head = head[:26]                             # Python parses at most microseconds
    return int(datetime.fromisoformat(head).replace(tzinfo=timezone.utc).timestamp() * 1000)

def normalise(env: Envelope) -> list[Record]:
    """The only function that knows source formats."""
    ...  # dispatch on env.src; implement per section 3; drop non-vessel MMSIs and n/a positions

# self-check (put in tests/test_time.py)
t = parse_time_utc("2026-11-07 16:15:01.234567 +0000 UTC")
assert rebuild_ts(t, 1)[0] == t - 234          # 16:15:01.000 (same minute)
assert rebuild_ts(t, 59)[0] == (t - t % 60_000) - 60_000 + 59_000   # minute rollover: previous minute
assert rebuild_ts(t, 61) == (t, "recv_only")
```

### 6.2 TypeScript (front end; mirrors the WebSocket section, same field names)

```ts
// web/src/types.ts
export type Status = "active" | "silent" | "gap_open" | "stale";
export type TypeGroup = "tanker" | "cargo" | "passenger" | "fishing" | "tug_special"
  | "military" | "pleasure" | "other" | "unknown";

export interface VesselView {
  mmsi: number; name: string | null; imo: number | null; flag: string | null;
  type_group: TypeGroup; length_m: number | null;
  lat: number; lon: number;
  sog_kn: number | null; cog_deg: number | null; heading_deg: number | null;
  last_ts: number;                 // epoch ms UTC
  status: Status; open_gap_id: string | null;
  risk_p: number | null; risk_rank: number | null;
  sanctioned: boolean; spoof_recent: string[];
}

export interface GapEvent {
  id: string; version: number; mmsi: number; state: "open" | "closed";
  start_ts: number; end_ts: number | null; duration_s: number;
  last_lat: number; last_lon: number; last_sog_kn: number | null; last_cog_deg: number | null;
  next_lat: number | null; next_lon: number | null;
  neighbours_heard: number; neighbours_baseline: number; cell_id: string;
  coverage_flag: "deliberate_candidate" | "coverage_gap" | "own_stall" | "unknown";
  radius_m?: number;               // server-derived, for the ghost circle
}

export interface SpoofEvent {
  id: string; mmsi: number; ts: number;
  type: "jump" | "on_land" | "circling_at_anchor" | "duplicate_mmsi" | "mmsi_change" | "imo_change" | "flag_mismatch";
  severity: number; jamming_suspect: boolean; evidence: Record<string, unknown>;
}

export interface Evidence { kind: "gap" | "spoof" | "sanction" | "score"; id: string; label: string; url?: string }
export interface WatchlistRow {
  rank: number; mmsi: number; name: string | null; p: number;
  decision: "inspect" | "watch" | "none"; prev_rank: number | null;
  reason_codes: string[]; evidence: Evidence[];
}
export interface Watchlist { snapshot_ts: number; entries: WatchlistRow[] }
export interface CoverageCellView { cell_id: string; state: "ok" | "degraded" | "dead"; coverage_score: number }
export interface SourceStatus { src: string; state: "up" | "silent" | "down" | "stall"; msgs_per_s: number }
export interface Stats { tracked: number; msgs_per_s: number; queue_depth: number }

type Base = { seq: number };
export type ServerMsg =
  | (Base & { type: "hello"; schema: 1; mode: "live" | "replay"; speed: number; now_ts: number;
              sources: SourceStatus[]; bbox: [[number, number], [number, number]] })
  | (Base & { type: "snapshot"; now_ts: number; vessels: VesselView[];
              trails: Record<string, [number, number, number][]>;   // [ts, lon, lat]
              gaps: GapEvent[]; spoofs: SpoofEvent[]; watchlist: Watchlist;
              coverage: CoverageCellView[]; stats: Stats })
  | (Base & { type: "delta"; now_ts: number; vessels: VesselView[]; removed: number[];
              gaps: GapEvent[]; spoofs: SpoofEvent[]; watchlist: Watchlist | null; stats: Stats })
  | (Base & { type: "watchlist" } & Watchlist)
  | (Base & { type: "status"; now_ts: number; mode: "live" | "replay"; speed: number;
              sources: SourceStatus[]; replay?: { from_ts: number; to_ts: number } })
  | (Base & { type: "detail"; mmsi: number; vessel: unknown; statics: unknown[]; gaps: GapEvent[];
              spoofs: SpoofEvent[]; sanction: unknown | null; score: unknown | null });

export type ClientMsg =
  | { type: "subscribe"; bbox: [[number, number], [number, number]]; min_status?: Status }
  | { type: "replay"; action: "play" | "pause" | "seek" | "speed"; t?: number; speed?: number }
  | { type: "detail"; mmsi: number };
```

Client rule: keep `Map<number, VesselView>`; on `delta` upsert `vessels`, delete `removed`, upsert `gaps` and `spoofs` by `id` (higher `version` wins), and append `[last_ts, lon, lat]` to that vessel's trail if it moved. If `seq` jumps, close and reconnect to get a new `snapshot`.

## 7. Open decisions for the first hour

| # | Decision | Recommended default |
|---|---|---|
| 1 | **What exactly is the forecast target?** Jake's two docs say two things: "goes dark in the next 6 h" and "is shadow fleet". | Primary target `dark_6h` (a `deliberate_candidate` gap starts within 6 h). Keep `shadow_prior` as a second, secondary score so the sanctions list gives an evaluation story. Drop `spoof_6h` unless time is spare. |
| 2 | Minimum gap length and silence rule. | Floor 30 min, `k = 20` times the vessel's own interval, neighbours heard >= 3 within 20 km. The label uses the same rule as the detector, so they are consistent. Tune only on the first night of logs. |
| 3 | Who owns `normalise()` and the `models.py` file? One owner, others import. | Hamish owns `dvm/models.py` and `normalise.py`. Everyone else changes them by asking on the board. Freeze the field names above by 17:30. |
| 4 | Class B vessels in the forecast? They report every 30 s to 3 min and look dark often. | Show them on the map, but exclude `cls = B` from gap detection, the forecast and the watchlist. Shadow tankers are Class A. |
| 5 | Which sources feed live: AISStream only, or merge Digitraffic too? | Run both, merged into one stream with the dedupe rule. `q` marks duplicates. If AISStream is silent for 30 s, nothing else changes. |
| 6 | Where does `neighbours_heard` count come from when only one source is up? | From whatever the pipeline has heard (all sources merged). Coverage cells are computed from the merged stream, so a fallback to Digitraffic only shows the Finnish area as `ok`. |
| 7 | Sanctions as a feature or only as a label? | Label only for the headline model (section 5.1 rule 5); also report a "with list" variant as an ablation. |
| 8 | Is `ts` stored for DMA as the base-station time? | Yes (`ts = recv_ts`). Backtests on DMA therefore cannot test late-data effects. State it on the slide. |
| 9 | The MID-to-flag table and flag-of-convenience list. | Put `data/mid_to_flag.csv` (ITU MID list) in the repo tonight; generate from a public ITU/Wikipedia table. A short hand-made flag-of-convenience list (Comoros, Gabon, Cameroon, Cook Islands, Palau, Sierra Leone, Equatorial Guinea, Panama, Liberia, Marshall Islands) is a starting point, **not from a verified source**. |
| 10 | Which cells and what grid size for coverage? | 0.1 degree squares, Baltic bbox `[[19,54],[31,61]]` (lon, lat) for the demo; start the coverage baseline from the first night's log. |
| 11 | How long to keep tracks and logs? | Raw log forever (disk is cheap); positions in memory 24 h; trails to the browser 60 min. |
| 12 | Browser trail source: server-sent or accumulated? | Server sends trails in `snapshot`, client appends from deltas (as in 6.2). |
| 13 | Event IDs for GFW imports? | `gfw-{ssvid}-{start}` so they never clash with ours. |
| 14 | Pydantic or dataclasses? | Pydantic v2 at the boundaries (this document), plain tuples/dicts or Polars inside the hot detector loops. |

## 8. What I could not verify

- AISStream `MetaData.time_utc` in a **live** payload (needs an API key; no sign-up made). Format taken from third-party samples. Everything about `recv_ts` for AISStream hangs on this; if it is missing the model still works with the local clock.
- AISStream `MaximumStaticDraught` unit (assumed metres) and `Eta` year handling.
- The format of the Digitraffic MQTT payload actually served (docs and REST differ).
- Kystverket stream: not connected; tag-block timestamps and port access are unknown.
- GFW v3 gap and SAR response keys (token needed).
- Message rate: the 200 msg/s used for log size is a placeholder.

Downloaded evidence, all in `C:\Users\hamis\AppData\Local\Temp\claude\360f743e01c99fde\0f422719-c131-4ee1-a816-e4eaa9a35dc3\scratchpad\dvm-downloads\datamodel\`: `loc_all.json` (Digitraffic locations, 276 KB), `vessels.json` (first 1.8 KB of Digitraffic metadata), `ais-types.yaml` (AISStream types), `dma_sample.csv` (200 KB of the DMA day file), `os_maritime.csv` (OpenSanctions), `pyaispkg/` (pyais used to confirm field names).
