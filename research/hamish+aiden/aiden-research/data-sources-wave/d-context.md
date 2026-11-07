# d-context: data that adds meaning

Checked Sat 7 Nov 2026, 16:10–17:05, from a UK connection with curl and Python. Scripts in `$WAVE/scripts/d-context/`, downloads in `$WAVE/data/d-context/`. Labels: **measured** (I ran it), **documented** (primary page), **unverified**.

## 1. Bottom line

1. **The free context layer works with no account.** Four keyless services carry most of the value and all answered in under 2 s: Marine Regions WFS (EEZs, territorial seas, high seas, MARPOL zones), EMODnet Human Activities WFS (pipelines, wind farms, cables, oil and gas fields), Open-Meteo Marine (hourly waves, including hindcasts) and FRED (daily Brent since 1987). **measured**
2. **Identity is the weak link, and it is licensing, not technique.** Equasis — the usual source of "this IMO has had four names and five flags" — and IMO GISIS both put ship particulars behind a free account, with no bulk access. The free substitutes are the ITU ship-station register (public search, no login) and the sanctions files themselves. "Same hull, new identity" is only partly demonstrable in a weekend. **measured**
3. **The sanctions and detention data already in hand is richer than the pitch assumes.** OFAC's own SDN CSV needs no key: 19,564 rows, 1,570 typed as vessels, 1,555 with an IMO in the remarks (**measured**). OpenSanctions' maritime file is 36% port-state detentions — Hamish calls that pollution, but as a **labelled outcome with IMO numbers** it is the one honest prediction target available.
4. **Fishing gives a hard, checkable join that tankers lack: authorisation.** IOTC publishes downloadable lists of vessels authorised to fish in its area, plus an IUU list. Presence without authorisation is a legal finding, not an inference. Cost: the IOTC bulk "active vessels" file is dated 28 Feb 2025 (**measured**), so use their public search instead.
5. **The interference layer is downloadable and separates our regions on the same day.** GPSJam's daily H3 files return 200 with no key: 48,253 hexagons for 6 Nov 2026 (**measured**). That day: Gulf of Finland 8.3% of aircraft reports bad (16 hexes over 10%), Danish straits 0.9%, Hormuz 12.5% (10 hexes, one at 100%), Natuna and Malacca near zero. Baltic silences need this as a control; Hormuz silences cannot be separated from it.

## 2. Findings

### 2.1 Identity and history

- **Equasis** (`equasis.org`) and **IMO GISIS** (`gisis.imo.org`): both return a login/registration shell; the "restricted" Equasis search URL also returns the login page. No API, no bulk. **measured**
- **ITU MARS ship stations** (`itu.int/mmsapp/ShipStation/list`) is a genuinely public search form: name, MMSI, call sign, `VesselIdentificationNumber` (IMO), administration and radio class. It is the authoritative record of which MMSI/call sign belongs to which flag (MID), so it is the tool for inconsistency evidence. A direct GET of the result endpoint returned a SharePoint redirect, so automated use is **unverified**; a browser can query it by hand. **measured**
- **EU Fleet Register** (`webgate.ec.europa.eu/fleet-europa/search_en`) loads and mentions registration but was not explored. **measured** (landing only)
- **GLEIF LEI** returns 3,488,344 company records dated the same day, free and keyless, but its join key is a company *name* — usable only after Equasis/GISIS supplies an owner or manager. **measured**
- **OFAC SDN CSV**: 5,833,851 bytes in 7.0 s. Free-text remarks contain "Vessel Registration Identification IMO nnnnnnn" for 1,555 of 1,570 vessel rows, which is a reliable regex. **measured**

Why it matters: IMO is the only durable key. Sanctions, detentions, authorisations and registries are indexed by IMO, but AIS carries it only in Class A static messages (roughly every 6 minutes). MMSI is the operational key and is trivially changed, so flag/MID and call-sign mismatches are evidence, not error.

### 2.2 Sanctions, shadow fleet, detentions

The reframe worth testing: **port-state detention is an outcome, not noise.** Paris MoU (`parismou.org/detentions/`, `/inspection-search/`) and Tokyo MoU (`tokyo-mou.org/inspections-detentions/detention-list/`) both publish free, searchable detention records with ship name, IMO, date and deficiency codes; neither offered bulk download from the pages I fetched (**measured**). OpenSanctions already aggregates Tokyo MoU into 6,037 and 4,492 vessels (**from our own wave's measurement**), and tags 7,585 vessels `mare.detained` against 5,456 `sanction` and 896 `mare.shadow`. So: AIS behaviour features → IMO → detention label → "does behaviour rank detained ships above the rest?" That is thousands of positives with dates, unlike "goes dark in 6 h", which has a few dozen noisy ones. Note the CSV carries no dates, so any temporal split needs the entity JSON.

### 2.3 IUU fishing, closures and authorisations

- **IOTC**: `iotc.org/vessels` links the Record of Authorised Vessels. The bulk file `.../vessel_lists/GetActiveVesselListE.zip` is **18,083,279 bytes** holding one 19.0 MB xlsx named for 28 Feb 2025; the IUU list is a 1.29 MB, 14-page PDF dated 2026-05-15 in the filename. Public search without an account: `https://rav.iotc.org/`. **measured** (I did not finish extracting xlsx columns inside the time box.)
- **WCPFC**: `vessels.wcpfc.int` (database) and `wcpfc.int/vessels/iuu-vessel-list` both 200. **measured**
- **CCSBT** and **CCAMLR** publish IUU lists (200); IOTC's page also links SEAFO, SIOFA and SPRFMO. The industry "combined" list is TMT's at `iuu-vessels.org` — public search, but ASP.NET POST forms with no machine-readable link found.
- **FAO Global Record** lives at `https://globalrecord.fao.org/` (200; `/advanced-search` 200, 851 KB), not the `fao.org/global-record` paths, which 404. `/api/vessels` 404s, so no API found; it is the intended home of the Unique Vessel Identifier.
- **Closures and MPAs**: WDPA's API returns **401 "Unauthorized"** — a token is now needed and downloads sit behind a request form (**measured**). Marine Regions covers EEZs and high seas but not MPAs. This is the biggest gap in the "was it allowed to be there?" chain.

What this adds: for a radar target with no AIS in the Natuna Sea, "inside Indonesia's EEZ + inside a closure + not on any RFMO authorised list" is far stronger than "no signal". It is the only layer that turns a detection into a *legal* statement. Practical caveat from the live-feed track: Finnish Digitraffic removes every fishing vessel (type 30) and folds ship types into coarse groups, so the Baltic AIS picture cannot show fishing at all — the authorisation join is a Southeast Asia and Indian Ocean tool.

### 2.4 Boundaries, infrastructure and structure masks

- **Marine Regions WFS** (`geo.vliz.be/geoserver/MarineRegions/wfs`) is one keyless endpoint with world EEZs, 24 nm contiguous zones, internal waters, high seas, EEZ boundaries, FAO/ICES areas and MARPOL emission control areas. A Danish EEZ feature returned in 0.6 s (422 KB) with `mrgid, geoname, territory1, iso_ter1, iso_sov1, area_km2`, filterable with `CQL_FILTER=territory1='Denmark'`. **measured**
- **EMODnet Human Activities WFS** advertises `<ows:Fees>NONE</ows:Fees>` and `<ows:AccessConstraints>NONE</ows:AccessConstraints>`, with layers for platforms, pipelines, wind farms, oil and gas fields, licences, dredging, munitions and cables split by national source. Feature counts by box (`numberMatched`): **measured**

| Box | wind farms | pipelines | oil/gas fields |
|---|---|---|---|
| Gotland basin (57–59.5°N, 17–20.5°E) | 9 | 4 | 0 |
| Danish straits (54.5–56.5°N, 10–13°E) | 15 | 3 | 35 |
| Gulf of Finland (59.2–60.5°N, 22–28°E) | 2 | **265** | 0 |

Cables in the Baltic box come from the Norwegian layer (264 features) and German (17). Two traps: WFS 2.0 bbox order is **lat,lon** (my lon,lat call silently returned zero features), and Finnish waters return 265 separate pipeline features, so the mask needs geometry, not counts.

- **TeleGeography cable map**: `submarinecablemap.com/api/v3/cable/cable-geo.json` returns 734 cable segments (755 KB) and 1,928 landing points, no key. It is an undocumented endpoint of a commercial product and I found **no licence text**, so use it but do not redistribute the geometry. **measured**
- **OSM via Overpass** failed from this network (406 and a 60 s timeout, with and without a User-Agent) — **measured failure**; a Geofabrik extract is the fallback.

This is what turns "42 unmatched radar targets" into "38 are wind turbines, rigs and dredgers, 4 need explaining". It also enables the Baltic cable story: a ship holding position inside a 1 km cable buffer with AIS off is concrete and checkable.

### 2.5 Interference and sea state

**GPSJam** (`gpsjam.org`) maps aircraft-reported navigation accuracy from airplanes.live and ADS-B Exchange, daily in UTC, refreshed soon after midnight. Its FAQ names the Baltic, Black Sea, eastern Mediterranean, Persian Gulf/Hormuz and South Asia as recurring zones and warns that red does not always mean jamming (**documented**). Bulk files work keyless (**measured**): `gpsjam.org/data/manifest.csv` (8,611 bytes gzipped; 1,726 days, 2022-02-14 → 2026-11-06, with `suspect` and `source` flags) and `gpsjam.org/data/2026-11-06-h3_4.csv` (192,208 bytes gzipped; 48,253 hexes; columns `hex,count_good_aircraft,count_bad_aircraft`; H3 resolution 4, cells of about 1,770 km²). The files are gzip but served without `Content-Encoding`, so gunzip explicitly.

World total for 6 Nov: 3,199,308 good and 13,429 bad aircraft reports (0.42%). Using the 61 res-4 hexes around each point (`$WAVE/scripts/d-context/gpsjam_regions.py`):

| Region | bad reports | hexes >10% bad | worst hex |
|---|---|---|---|
| Gulf of Finland | 8.3% (2,390 / 216) | 16 of 61 | 30.8% |
| Danish straits | 0.9% (7,620 / 70) | 0 | 7.4% |
| Gotland basin | 2.3% (3,159 / 74) | 0 | 8.3% |
| Hormuz | 12.5% (1,235 / 176) | 10 of 61 | 100% |
| Gulf of Oman | 2.1% (8,419 / 176) | 1 | 50% |
| Malacca | 0.3% | 0 | 4% |
| Natuna | 0.0% (1,703 / 0) | 0 | 0% |
| Bab el-Mandeb | **no data** | 0 | — |
| Black Sea (west) | 21.0% (2,308 / 612) | 39 of 61 | 100% |

Two lessons: the Gulf of Finland had real interference on 6 Nov while Danish waters did not, so a silence there is ambiguous that day and jamming must sit *beside* gaps; and a blank region (0 aircraft) means no ADS-B coverage, not clean skies.

**Open-Meteo Marine** needs no key: hourly `wave_height`, `swell_wave_height`, `wind_wave_height` and direction, forecast by default and **hindcast** with `start_date`/`end_date` (tested 1–2 Nov 2026, 0.26 s). Sea state drives both radar false alarms and small-craft AIS reception, so it is the cheapest way to show a "dark" night was also a 4 m wave night. **measured**

### 2.6 Markets and flows

- **FRED**: `fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU` returns 170 KB of daily Brent from 1987 in 0.5 s, no key (the JSON API does need one). **measured**
- **IMF/UNCTAD PortWatch** answers keyless with 28 chokepoints (`chokepoint6` Hormuz, `5` Malacca, `10` Oresund, `28` Kerch): `date, n_container, n_dry_bulk, n_general_cargo, n_roro, n_tanker, n_cargo, n_total, capacity_*`. **Latest date 2026-11-01 — a 6-day lag** (**measured**). It is AIS-derived and daily, so it validates trends, not a same-day radar detection.
- **EIA v2** needs a free key (Hamish measured `API_KEY_MISSING`); **UN Comtrade**'s free preview returned 200 with zero rows for my query (unproven); **NGA World Port Index** returned 503. **measured failures**

### 2.7 Three most revealing combinations (plus one)

**A. Identity chain: AIS static → IMO → sanctions/detention → identity mismatch.** Key: IMO (check digit), then MMSI/call sign. A hull on a public list, or one whose broadcast name/flag/call sign disagrees with the ITU register, still transmitting. Cheapest strong result; caveat: only ~35% of listed vessels carry an MMSI, so IMO matters.

**B. Geometry chain: radar detection → EEZ/closure/cable buffer → AIS absence → authorisation check.** Key: point-in-polygon at image time, plus IMO where AIS exists. A dark radar target inside a protected area, a closure, or holding over a cable corridor, whose vessel is on no authorised list. This is what makes "dark" mean something specific, and it works in the Baltic (cables) and Southeast Asia (EEZs, closures).

**C. Confounder chain: AIS silence ↔ GPSJam hex-day ↔ wave height.** Key: H3 hex + UTC date; lon/lat/time. It says how much of the "dark fleet" is explained by interference or weather — a credibility layer, not a headline ("of 40 silences, 11 fell on hexes with high reported interference").

**D. Behaviour → detention (for HRT).** Key: IMO. Features from AIS, label `mare.detained`. Gives an accuracy number against a real decision (which ship to inspect) — the honest version of "predict who goes dark", with dates available only in the entity JSON.

## 3. Source rows

| Source | Type | Regions covered | Free access route | Account needed? | What one record contains | Update rate | Delay from event to us | Position or resolution accuracy | Identifies the ship? | Licence, commercial limits | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| OpenSanctions maritime | Sanctions + detentions | Global | `data.opensanctions.org/datasets/latest/maritime/` | No | IMO, MMSI, flag, risk tags (`sanction`, `mare.shadow`, `mare.detained`) | Daily | ~1 day | n/a | Yes | CC BY-NC 4.0 | Hamish: 23,833 rows |
| OFAC SDN CSV | Sanctions (primary) | Global | `sanctionslistservice.ofac.treas.gov/.../SDN.CSV` | No | 19,564 rows; 1,570 vessels; IMO in remarks | Irregular | Hours–days | n/a | Yes (IMO text) | US public domain | measured 5.83 MB, 1,555 IMOs |
| EU sanctions map | Sanctions | Global | `sanctionsmap.eu` | No (web only) | EU designations search | Continuous | Days | n/a | Yes | EU reuse decision | measured 200, no bulk |
| Paris MoU / Tokyo MoU | Port-state control | Europe / Asia-Pacific | `parismou.org/detentions/`, `tokyo-mou.org/.../detention-list/` | No (web search) | Ship, IMO, date, deficiencies | Continuous | Days | n/a | Yes | Public, no bulk seen | measured 200 |
| Equasis | Identity/history | Global | portal | **Yes** (free) | Former names/flags, owner, manager, P&I, class | Continuous | Days | n/a | Yes | No bulk | measured login wall |
| IMO GISIS | Identity | Global | portal | **Yes** (free) | Ship and company particulars | Continuous | Days | n/a | Yes | No bulk | measured login wall |
| ITU MARS ship stations | Identity | Global | `itu.int/mmsapp/ShipStation/list` | No | Name, MMSI, call sign, IMO, admin, radio class | Continuous | Days | n/a | Yes | Public form | measured; API unverified |
| IOTC authorised vessels | Fishing authorisation | Indian Ocean | `iotc.org/vessels`, zip, `rav.iotc.org` | No | Authorised vessel; IUU list PDF | Annual snapshot | ~20 months (bulk) | n/a | Yes | Public | measured 18.1 MB, 2025-02-28 |
| WCPFC / CCSBT / CCAMLR | Fishing authorisation + IUU | Pacific / S. Ocean | `vessels.wcpfc.int`, `wcpfc.int/vessels/iuu-vessel-list` | No | Vessel identity, authorisations, IUU entries | Periodic | Months | n/a | Yes | Public | measured 200 |
| TMT combined IUU list | IUU aggregate | Global | `iuu-vessels.org/Home/Search` | No | IUU entries with flag/IMO | Periodic | Weeks | n/a | Yes | Public | measured; no machine-readable link |
| FAO Global Record | Fishing vessel identity | Global | `globalrecord.fao.org` | No | Vessel, UVI/IMO, authorisations | Ongoing | Unknown | n/a | Yes | Public | measured 200; no API |
| Marine Regions WFS | Boundaries | Global | `geo.vliz.be/geoserver/MarineRegions/wfs` | No | EEZ/territorial/high-seas/ECA polygon + sovereign | Static (v4 2023) | n/a | ~1:1M vector | No | licence not found on fetched pages — attribute | measured 0.6 s |
| EMODnet Human Activities WFS | Infrastructure | European seas | `ows.emodnet-humanactivities.eu/wfs` | No | Pipelines, platforms, wind farms, cables, licences | Periodic | Months–years | 10s–100s m | No | `Fees NONE`, `AccessConstraints NONE` | measured; see counts above |
| TeleGeography cable map | Infrastructure | Global | `submarinecablemap.com/api/v3/...` | No | 734 segments, 1,928 landing points | Periodic | Months | 100s m | No | no licence text found; do not redistribute | measured 755 KB, 1.2 s |
| WDPA (Protected Planet) | Protected areas | Global | portal + API | **Yes** (token) | MPA polygon, designation | Periodic | Weeks | vector | No | Free with registration | measured 401 |
| GPSJam | GNSS interference | Global (aircraft-covered) | `gpsjam.org/data/<date>-h3_4.csv` | No | H3 res-4 hex, good/bad aircraft counts | Daily | <1 day | ~1,770 km² cell, sampling not a fix | No | Public, no stated licence | measured 48,253 hexes, 0.42% world bad |
| Open-Meteo Marine | Weather/sea state | Global ocean | `marine-api.open-meteo.com/v1/marine` | No | Hourly wave/swell height and direction | Hourly | 0 (forecast) | ~5–25 km model grid | No | CC BY 4.0 | measured 0.26 s, hindcast OK |
| FRED (Brent) | Market | Global | `fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU` | No | Daily Brent spot, from 1987 | Daily | ~1 day | n/a | No | FRED terms, free | measured 170 KB, 0.5 s |
| IMF PortWatch chokepoints | Flows (AIS-derived) | 28 chokepoints | ArcGIS FeatureServer | No | Daily transit counts by ship type, capacity | Daily | **6 days** | chokepoint aggregate | No | Free with attribution | measured latest 2026-11-01 |
| EIA v2 | Energy flows | US/global | `api.eia.gov/v2/` | **Key** (free) | Petroleum supply/movement series | Weekly | Days | n/a | No | US public domain | Hamish: key required |
| GLEIF LEI | Company identity | Global | `leidata.gleif.org` | No | 3.49 M entities + parent links | Daily | Same day | n/a | Via owner name only | CC0 | measured |
| OSM / Overpass | Infrastructure | Global | `overpass-api.de/api/interpreter` | No | Cables, platforms | Continuous | Days | m–10s m | No | ODbL | **failed here**: 406/timeout |
| NGA World Port Index | Ports | Global | `msi.nga.mil` | No | Port coordinates, facilities | Irregular | Years | point | No | US public domain | measured 503 |

## 4. Consequence for feasibility

**Possible today, cheaply:** proving a dark radar target is *not* a rig, turbine or dredger (EMODnet, ~2 s per query); naming the waters a silence happened in (Marine Regions, one CQL call); saying whether a night was stormy or jammed (Open-Meteo hourly, GPSJam daily per hex); and setting a real price series against a real transit series (FRED + PortWatch, both keyless). For the Baltic that is enough to say "dark for 6 h inside the Finnish EEZ, 400 m from a telecom cable, on a night of 2.1 m waves with 30% of aircraft in that hex reporting bad navigation accuracy". For Southeast Asia the authorisation lists add a legal edge no tanker story has.

**The honest answer to "hiding or noisy sky?" is already measurable**: on 6 Nov the Gulf of Finland was degraded (8.3%, 16 hexes over 10%) and the Danish straits were clean (0.9%). That contrast belongs next to the gaps, not in a footnote.

**Ruled out for a weekend:** identity history from Equasis or GISIS (accounts, no bulk); MPA geometry from WDPA (token); Overpass from this network. Also ruled out is novelty in detection — Skylight already publishes free global Sentinel-1/2 vessel detections (shared notes), so the differentiator has to be the context joins. And same-day market validation: PortWatch is 6 days behind, so a dark-transit/price claim can only be a historical study.

**Regions:** Baltic — richest context (cables, turbines, pipelines, EEZs, detentions, jamming). Hormuz — good sanctions and market context, no free AIS, 6-day PortWatch lag, interference inseparable. Natuna/Malacca — strong legal context (EEZ, authorisation, IUU, closures partly gated), no free AIS, and thin Sentinel-1 coverage (d-imagery measured 6 passes in 30 days at Natuna).

**Framing this supports:** "we compare what a ship says, where it is, and what it is allowed to do" — three joins, each with a stated error source, rather than a claim about intent.

## 5. Unknowns

- **GPSJam coverage follows aircraft.** Bab el-Mandeb had zero reports on 6 Nov, so blank is not "clean". Any interference claim over the Red Sea or open Indian Ocean is unsupported by this source.
- **Whether daily H3 files exist for every manifest date** — I fetched two of 1,726.
- **IOTC e-RAV currentness** — whether `rav.iotc.org` reflects today's authorisations, unlike the Feb 2025 bulk file.
- **Unconfirmed licences:** Marine Regions per-layer terms, TeleGeography (none found), EMODnet layer-level terms (service says NONE), GPSJam reuse.
- **Company ownership untested.** IMO → owner/manager → LEI is plausible but the first hop needs Equasis or GISIS.
- **WDPA alternatives** (GFW's MPA layer, Marine Protection Atlas) not tried.

## 6. Sources

`equasis.org`, `gisis.imo.org` (login walls); `itu.int/mmsapp/ShipStation/list`; `webgate.ec.europa.eu/fleet-europa/search_en`; `sanctionslistservice.ofac.treas.gov/.../SDN.CSV`; `sanctionsmap.eu`; `parismou.org/detentions/`; `tokyo-mou.org/inspections-detentions/detention-list/`; `iotc.org/vessels` + `vessel_lists/GetActiveVesselListE.zip` + `rav.iotc.org`; `vessels.wcpfc.int`; `wcpfc.int/vessels/iuu-vessel-list`; `iuu-vessels.org`; `globalrecord.fao.org/advanced-search`; `geo.vliz.be/geoserver/MarineRegions/wfs`; `ows.emodnet-humanactivities.eu/wfs`; `submarinecablemap.com/api/v3/cable/cable-geo.json`; `api.protectedplanet.net` (401); `gpsjam.org` + `/faq/` + `/data/manifest.csv` + `/data/2026-11-06-h3_4.csv` (path pattern first seen in github.com/koala73/worldmonitor `scripts/fetch-gpsjam.mjs`, then confirmed); `marine-api.open-meteo.com/v1/marine`; `fred.stlouisfed.org/graph/fredgraph.csv?id=DCOILBRENTEU`; `services9.arcgis.com/.../Daily_Chokepoints_Data`; `leidata.gleif.org`; `overpass-api.de` (failed); `msi.nga.mil` (503). Earlier measurements reused from `research/hamish+aiden/hamish-research/dark-vessel-check/02-historical-data-and-labels.md`.
