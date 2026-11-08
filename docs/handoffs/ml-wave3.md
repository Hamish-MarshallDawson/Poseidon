# Briefs: model 3, fishing in protected areas and predicted zone incursion (issue #157), from 07:05 UTC

Read `docs/handoffs/COMMON.md` and `docs/handoffs/ml-architecture.md` first (absolute paths under
`/home/aiden/.herdr/worktrees/Hedged-Bets-hacktheburgh/59-ingest-resilience/`), and the **Zones** section of
`docs/prediction-loop/PLAN.md` (what was checked at 04:40). Base everything on `origin/main` (the training batch is
merged there now, main 12f0d378 or later). Freeze is 09:00 UTC: a tested PR each by **about 08:00**, smallest change that
works. `Part of #157`. Don't merge. Hands off `frontend/`, `backend/dvm/collab/`, `backend/dvm/gaps.py`.
Tiger read-only for you (the server runs any writes after be-integrate merges).

Facts already checked (04:40):
- GFW fishing events `public-global-fishing-events:latest` work with our region polygons: 526 events in 1 to 8 Oct in the
  Danish straits, 32 in the Gulf of Oman. Each has `regions` (`eez`, `eez12Nm`, `mpa`, `mpaNoTake`, `protectedseas`,
  `rfmo`, `highSeas`) and `fishing.potentialRisk`, `fishing.vesselPublicAuthorizationStatus`, average speed and duration.
  102 of 200 sampled Danish events were inside an MPA.
- EEZ shapes: Marine Regions WFS, `https://geo.vliz.be/geoserver/MarineRegions/wfs?service=WFS&version=1.0.0&request=
  GetFeature&typeName=MarineRegions:eez&outputFormat=application/json&bbox=<minLon,minLat,maxLon,maxLat>` (CC BY 4.0;
  `mrgid` matches GFW's `eez` tags, e.g. 5674 Denmark). About 33 MB unclipped for the Danish box.
- Marine protected areas: WDPA map service `https://data-gis.unep-wcmc.org/server/rest/services/ProtectedSites/
  The_World_Database_of_Protected_Areas/MapServer/1/query` (fields include `site_id, name_eng, desig_eng, realm,
  no_take, status`), filter `realm <> 'Terrestrial'`: 662 sites in the Danish box, 24 around Hormuz and the Gulf of Oman.
  Its `no_take` filter gave 0, so take no-take status from GFW's `mpaNoTake` tag. Licence: non-commercial, attribution.

## `zones` (branch `157-zones`, port 55551)
`backend/dvm/zones/` (new package):
- `build.py`: a one-off CLI that fetches EEZs and marine WDPA polygons for our four regions plus a margin (at least the
  `gfw_gaps.AREAS` boxes' overlap with our regions), clips and simplifies them (about 100 m tolerance), and writes one
  compact GeoJSON per layer to `backend/dvm/zones/data/` (commit it only if under about 5 MB in total; otherwise write
  it to a data dir and load at start-up, and say which). Keep ids: EEZ `mrgid`, WDPA `site_id`, names, designation.
- `lookup.py`: load once, an STRtree index; `zone_of(lat, lon) -> {eez, eez_name, mpa: [ids], mpa_names}` and
  `distance_to_eez_border_m(lat, lon)`, fast enough for 20k calls a second.
- `incursion.py`: given a route prediction (point plus 80% and 95% radii, as in `route_predictions`), the share of the
  80% circle inside any marine protected area and inside an EEZ other than the ship's current one; returns
  `{mpa_ids, mpa_share_80, foreign_eez, foreign_share_80}`.
- Wire it into the live predictor minimally: `backend/dvm/predict/predictor.py` adds the incursion fields to each route
  prediction it hands to `forecast` (in memory, for the map) and writes an `incursions` list to the ledger as new
  nullable columns on `route_predictions` (additive ALTER in `predict/schema.py`). Don't change anything else there.
- Route `GET /zones?bbox=&layers=eez,mpa` (same login as `/coverage`) returning GeoJSON for the map, and
  `/health` gains a `zones` block (loaded layers, counts).
Tests: lookup correctness on a few known points (a point in Danish waters, one in Swedish, one inside a known MPA),
incursion shares on a synthetic square, route shape. Real check: build the layers, run the server locally (no
AISStream key) on a local database, curl `/zones`.

## `gfw-fishing` (branch `157-gfw-fishing`, port 55552)
Ingest GFW fishing events as `observations` kind `fishing`, like `gfw_gaps.py` does for gaps:
- Add `fishing` to the `Kind` list in `backend/dvm/sources/common.py` (and the routes' `KINDS`), a new module
  `backend/dvm/sources/gfw_fishing.py` with its own ledger stream (`src = 'gfw', stream = 'fishing'`, region = our
  region names, weekly windows by event start, using the region polygons, which work for fishing events), storing
  `ts`, `end_ts`, `lat`/`lon`, `mmsi`, `value` = hours, and in `attrs`: `eez`, `eez12nm`, `mpa`, `mpa_no_take`,
  `protectedseas`, `rfmo`, `high_seas`, `potential_risk`, `authorization_status`, `avg_speed_kn`, `distance_km`, vessel
  name, flag, gear type. Stable id `gfw:fishing:<event id>`; `available_ts` as `gfw.available` does.
- CLI: `backfill-back gfw-fishing`, `poll gfw-fishing` and `backfill gfw-fishing --start --end` in
  `dvm/sources/__main__.py`, like gfw-gaps. Uses only `/events` (no report lock).
- Tests with a recorded response, idempotent re-fetch, a one-week live backfill into a local database. Report events per
  week per region and an estimated size for a year. State the server commands.

## `fishing-model` (branch `157-fishing-model`, port 55553)
`ml/fishing/` through `ml/core` (a `TargetSpec` in `ml/fishing/target.py`), trained **without waiting for the
ingest**: pull GFW fishing events directly from the GFW API for our four regions (the `GFW_API_TOKEN` in the repo
`.env`; polite: one request at a time, back off on 429, the live server shares the token) for as many weeks as you
can in about 15 minutes, cached as Parquet under `/home/aiden/data/poseidon/fishing/`, plus GFW presence and port visits
from Tiger read-only if useful. Target, pick and justify after looking at the label rate first:
- **(a)** per fishing vessel and week, whether it has a fishing event inside a marine protected area (`mpa` or
  `mpa_no_take` non-empty) in the next week, or
- **(b)** whether its next fishing event carries `potentialRisk = true`.
Features from that vessel's history before the week only (`available_ts <= as_of`): past fishing hours inside and
outside MPAs, share near EEZ borders, flag, gear type, authorisation status, region, recent port visits. LightGBM with
class weights and isotonic calibration, baseline = rate by gear and flag, time split with an embargo, frozen held-out
set, report through `ml.core.report`, plus a deployable artifact in the backend's go-dark-style format (`heads` with
`model` and `calibration`) if it beats the baseline; say so plainly if it does not. Cap threads at 6.
