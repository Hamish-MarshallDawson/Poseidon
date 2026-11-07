# mt-gulf-feeds: public feeds in the priority regions

*Track mt-gulf-feeds, MarineTraffic wave, Sat 7 Nov 2026, 18:17–18:55 UTC. Everything below was run from the venue network with no accounts, no keys and no sign-ups. Labels: `measured` = I ran it and saw this output; `documented` = the operator's own page says so; `vendor claim` = marketing only; `unverified` = a lead I could not settle. Downloads/notes in `$WAVE/data/mt-gulf-feeds/` (nothing was downloaded beyond HTML/JSON probe responses).*

**Search caveat:** my provider throttled after ~10 queries, so the less obvious national portals (Poland, Germany, Estonia, Latvia, Lithuania, Philippines, Qatar, Kuwait, Bahrain) are thin. "Nothing found" means "nothing on the pages I reached", not proof of absence.

## 1. Bottom line

1. **No government or port in the Gulf, Red Sea, Suez, Malacca, Singapore, Indonesia, Malaysia, Thailand, Vietnam or the Philippines publishes a usable public AIS feed.** Five candidates were opened and measured; all five fail as feeds (tokens, API keys, or a front-end over a commercial vendor).
2. **The clearest find is a schema, not data.** Thailand's Marine Department is building AIS services in an Esri org at `esrith-bd.cdg.co.th`. Its public layers load and query without a token, but hold 2,030 / 3 / 6 rows of **US MarineCadastre sample data from 2022-05-02 off San Diego**, field-for-field the NOAA schema. Its production folder answers `{"error":{"code":499,"message":"Token Required"}}`.
3. **Ship-level proxies are the only open route, and they are daily.** IMF PortWatch (known, ~6 days), Suez Canal Authority tables (monthly/quarterly/annual only, no API), and Zenodo **LNG-T3** (global LNG tanker voyages and terminal throughput 2020–2024, CC BY 4.0, 406 tankers, 545 terminals) — the only open dataset I found with per-vessel Gulf records.
4. **The "Finland-to-Denmark gap" is an access gap, not a receiver gap.** Sweden's Sjöfartsverket has 40-odd base stations, a live stream and RAIS history from Sep 2006, and sells both against a published 2027 price annex. Free coverage stops where Denmark and Finland stop.
5. **Nothing here is worth a live test.** This track's product is a list of dead ends with exact status codes, so nobody re-probes them on Sunday.

## 2. Findings

### What I opened (`measured` unless noted)

- **Thailand (Marine Department, hosted by CDG on Esri TH).** `Hosted/ข้อมูลเรือ_2` returns 2,030 rows, `source="MarineCadastre"`, `basedatetime` 2022-05-02, positions 32.76 N −117.24 W; `editingInfo.lastEditDate` 2023-07-25. `Hosted/ข้อมูลเรือ_Recent` = 3 rows, `Hosted/VesselList_ReconstructTracks` = 6 tracks, same sample. The public `Hosted` folder holds 67 services, 3 vessel-related. `server/rest/services/MD?f=json` → `499 Token Required`. Separately `nsw.md.go.th/mxdataservice` advertises REST with an **API-KEY**, issued after phoning their IT group, including yacht and foreign-fishing-vessel arrival notifications (`documented`).
- **Indonesia (KKP).** `vtc.kkp.go.id` returns a real 123 kB dashboard (vessels, port arrivals, logbooks, fishing activity) but its JS calls `/modules/webservice/rest/…` and OAuth `client_credentials` on `api.integrated-voyage.com`. A ministry map over a licensed commercial AIS product; not probed further.
- **Vietnam.** `hpradar.com/api`: 8 Hai Phong ground stations, `GET /ais/vessels` JSON, free tier **100 req/hour**, access "upon request" by email. Hai Phong approaches only (`documented`).
- **Malaysia / Singapore.** `api.data.gov.my/data-catalogue` → `400 "Query parameter 'id' is required."` (no browsable catalogue, no AIS dataset surfaced); `data.gov.sg/api/action/package_search` → `404` (v1 retired).
- **Suez.** SCA statistics page → monthly/quarterly/yearly tonnage and transit tables, SharePoint HTML, no daily series, no API. `lethagencies.com` transit lists are client-side, not public.

### Do regional authorities publish raw AIS? No.

Every authority I could reach runs AIS internally for VTS and publishes either statistics or nothing; the newer portals are gated. Thailand shows all three stages at once: a token-gated production folder, public layers carrying *another country's* open data, and a Single Window issuing API keys on request.

### Proxies: what is actually open

- **IMF PortWatch** — 28 chokepoints, ~1,800 ports, daily calls/transits, ~6 days behind (documented; measured by other tracks). No identity, no positions, but the only free daily series covering Hormuz, Bab el-Mandeb, Suez, Malacca and Singapore consistently. Not re-measured here.
- **Suez Canal Authority** — official tonnage/transit counts at month-or-coarser granularity. Cannot support a daily collapse chart; PortWatch can.
- **LNG-T3 (Zenodo 19571058, 2026-04-01, CC BY 4.0)** — `LNG_tanker_voyage.csv` 2.0 MB, `LNG_terminal_daily.csv`, `LNG_tanker.csv` (406 vessels), `LNG_terminal.csv` (545 terminals), `LNG_trade_daily.csv`, `AIS_feed.zip` 0.2 MB. Daily 2020–2024, AIS-derived, per vessel: the one open ship-level window on Gulf energy traffic. Metadata measured; CSVs not downloaded in the time box.
- **Zenodo search is badly behaved.** A query for `AIS strait of malacca` reported 5.7 M hits; only `type=dataset` plus quoted phrases is meaningful. With that filter: `AegeaNET Syros AIS Dataset` (Greece, 2026), "Anonymised AIS dataset" (2019) — and **no raw AIS for the Gulf, Red Sea, Malacca, Singapore or Indonesia** in the top results. A title warning: `SAR Ship Gulf` (Zenodo 21000650) is the Gulf of *Mexico*.

### EMODnet route density is EU-only

`mt-rivals` flagged EMODnet as a CC BY 4.0 AIS product; it looks global, so I pinned it down. `ows.emodnet-humanactivities.eu/wms` (GetCapabilities `200`, 1.05 MB, 207 layers, `routedensity_all` with monthly `TIME` 2019-01 → 2026-10, abstract: made by **EMSA**, 1 km). Same 400×300 GetMap for four boxes on 2026-10-01, opaque pixels of 120,000:

| Box | PNG bytes | opaque px |
|---|---|---|
| Danish straits 55–58 N, 10–13 E | 38,731 | 6,238 |
| Persian Gulf 24–30 N, 48–57 E | 2,772 | 300 |
| Red Sea 12–30 N, 42–57 E | 2,772 | 300 |
| Malacca/Singapore 1–7 N, 100–105 E | 2,772 | 300 |

300 px is the empty mask. **No traffic outside European waters** — not a Gulf or Asia proxy.

### Baltic gap, Finland to Denmark

Finland (Digitraffic) and Denmark (aisdata.ais.dk) are free and bound the gap. Between them, **Sweden** has 40-odd base stations, a live streaming product and RAIS history from 2006, both charged ("handläggarens tidsåtgång för uttag debiteras samt uttagskostnad") with a 2027 price annex. **Germany, Poland, Estonia, Latvia, Lithuania** are unsettled: their sites were on my list when the search provider throttled.

Practical reading: the free Baltic is two countries at the ends of the lane, and the middle third is where the money is.

## 3. Source rows

| Source | Operator | Type | Regions covered | Access route | Account or cost | What one record contains | Update rate | Delay | Identifies the ship? | Licence, limits | Likely used by MarineTraffic? | Usable by us? | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Thai MD vessel layers (`Hosted/ข้อมูลเรือ_2`, `_Recent`, `VesselList_ReconstructTracks`) | Marine Dept, Thailand, hosted by CDG/Esri TH | demo/ArcGIS feature service | none (holds US sample) | public REST `query` | none | MMSI, name, IMO, callsign, type, lat/lon, SOG, COG, heading, status, dims, draft, A/B class, `source` | none (static 2022 sample) | n/a | yes | no stated licence; 2,030 rows | unlikely | **no**, except as evidence the system exists | `measured` (200, counts, field values, lastEditDate) |
| Thai MD production services (`/services/MD`) | Marine Dept, Thailand | ArcGIS feature/map services | Thailand (presumed) | REST, **token** | account/token | unknown | unknown | unknown | yes (presumed) | closed | possibly | **no** — `499 Token Required` | `measured` |
| Thai Marine Dept Single Window | Marine Dept, Thailand | HTTPS REST data service | Thai ports, arrivals | `nsw.md.go.th/mxdataservice` | **API-KEY**, issued after contacting their IT group | arrival/departure notifications incl. yachts and foreign fishing vessels | not stated | not stated | yes (vessel-level) | not stated | no | **no** without an account | `documented` (page copy) |
| KKP vessel traffic dashboard (`vtc.kkp.go.id`) | Ministry of Marine Affairs & Fisheries, Indonesia | GIS dashboard over licensed AIS | Indonesian waters | web; data via `/modules/webservice/rest/` | OAuth client credentials to `api.integrated-voyage.com` | vessel positions, port arrivals, logbooks, fishing activity (as displayed) | live (map) | unknown | yes | not stated | the upstream vendor may supply MT | **no** — account + commercial upstream | `measured` (HTML 200, JS endpoints) |
| Telkomsat AIS | PT Telkomsat, Indonesia | commercial AIS API | Indonesia, Malacca | REST API product page | **paid** (`vendor claim`) | positions per their product page | not stated | not stated | yes | commercial | possibly (as a vendor, unverified) | no, no free tier advertised | `vendor claim` |
| HP Radar AIS | HP Radar, Hai Phong, Vietnam | community/ground-station API | Hai Phong approaches (8 stations) | `api.hpradar.com/ais/vessels` | **email request**; free tier 100 req/h | JSON vessel records per MMSI | live | not stated | yes (MMSI) | not published | no | **no** without an email | `documented` |
| Suez Canal Authority navigation statistics | SCA, Egypt | official statistics | Suez Canal | HTML tables | none | monthly/quarterly/yearly transit counts and net tonnage by ship type | monthly+ | weeks–months | **no** | Egyptian government site | no | only as a coarse cross-check | `measured` |
| IMF PortWatch chokepoints | IMF / Oxford ECI | AIS-derived aggregates | 28 chokepoints incl. Hormuz, Bab el-Mandeb, Suez, Malacca, Singapore | ArcGIS FeatureServer | none | daily transit calls and trade volume per chokepoint | daily | ~6 days (other tracks) | **no** | IMF terms, free | no | **yes**, as the Gulf daily baseline | `documented` + other tracks' measurement |
| LNG-T3 (Zenodo 19571058) | academic authors | AIS-derived research dataset | global, incl. Gulf LNG terminals | Zenodo files | none | per-vessel LNG voyage legs, terminal daily throughput, 406 tankers / 545 terminals | daily, 2020–2024 | years (static) | **yes** (vessel-level) | **CC BY 4.0** | no | **yes**, historical Gulf energy traffic | `measured` (record metadata, file list, licence) |
| Swedish AIS (Sjöfartsverket) | Swedish Maritime Administration | national AIS, live + historical | Swedish coast, Bothnia, Sound, Vänern/Vättern | live stream subscription; RAIS extracts per order | **charged** (price annex 2027) | full AIS message with all attributes (`documented`) | real time | seconds (stream) | yes | commercial terms | unknown | only if paid | `documented` |
| Malaysia open data (`api.data.gov.my`) | Malaysian government | national open-data API | Malaysia | REST, dataset `id` required | none | no AIS/vessel dataset found | – | – | – | Malaysian open data terms | no | no | `measured` (400 without id) |
| Singapore open data (`data.gov.sg`) | Singapore government | national open data | Singapore | v2 API | none | no AIS dataset found; v1 API `404` | – | – | – | Singapore open data terms | no | no | `measured` |
| EMODnet Human Activities route density | EMSA, published by EMODnet | AIS-derived density raster (WMS) | **European seas only** (measured) | `ows.emodnet-humanactivities.eu/wms`, `routedensity_all[_avg]`, 1 km, monthly `TIME` 2019-01→2026-10, annual averages | none | density value per 1 km cell per month, per ship type (`routedensity_01`…`05`) | monthly | weeks after month end (not measured) | **no** | CC BY 4.0, upstream AIS from CLS/ORBCOMM/vesseltracker.com (`mt-rivals`) | no | only for European waters; **blank for Gulf/Red Sea/Malacca** | `measured` (GetCapabilities + 4 GetMaps + pixel counts) |
| AISHub | AISHub | receiver cooperative | global where members feed; own counter 79,730 vessels / 1,788 stations / 82 countries | XML/JSON API | **must feed a receiver** | raw AIS positions | near real time | seconds | yes | commercial reuse with credit | no | only via contribution (see mt-receivers) | `measured` (homepage counters) |

## 4. What this means for us

- **A live Gulf claim cannot be supported from public feeds.** The options are a contributed receiver, a paid vendor, or delayed proxies — and any Gulf point on a map should say which, per point.
- **Keep proxies in their own table.** PortWatch, SCA and LNG-T3 are daily or coarser, keyed by chokepoint/port/date, with no positions. A `source`, `granularity` and `lag_days` column on every row lets the UI label them honestly.
- **Never render a PortWatch count as "ships we see".** Official transits fell 43.5 → 0.7 a day while AIS presence fell only 393 → 220; those two numbers in one unlabelled chart is the likeliest way for this project to say something false.
- **The Thai schema is worth copying**: it matches NOAA MarineCadastre exactly (`MMSI, BaseDateTime, LAT, LON, SOG, COG, Heading, VesselName, IMO, CallSign, VesselType, Status, Length, Width, Draft, Cargo, TransceiverClass`). If a regional archive ever opens, ingesting it is free, and a later licensed feed would fit the same model.
- **Do not scrape any of these portals.** Two of four systems need tokens or OAuth issued to named users, and the open layers hold another country's 2022 data.

## 5. Unknowns

1. What `/services/MD` actually contains and whether it is live — one call with a token issued to MD or CDG would settle it. I did not attempt it (Rule 2).
2. Whether Thailand's Single Window arrival notifications are the best regional proxy for port calls (they include foreign fishing vessels, which is unusual and useful) — needs an API key, i.e. a phone call.
3. Poland, Germany, Estonia, Latvia, Lithuania, Philippines, Qatar, Kuwait, Bahrain: not searched to exhaustion. A second pass with a working search provider is cheap.
4. Whether Telkomsat or any Indonesian reseller offers a trial; whether AD Ports, Mawani, ASYAD or MPA publish machine-readable arrival lists (their home pages were reachable but I did not enumerate schedules).
5. Whether HP Radar would grant a free tier by email — needs a person to send one.
6. Whether PortWatch's Hormuz and Suez series are daily and ~6 days old here; other tracks measured this, I did not.
7. Whether LNG-T3's `AIS_feed.zip` (0.2 MB) contains real NMEA or only a pointer — the file was listed but not downloaded.

## 6. Sources

- `https://esrith-bd.cdg.co.th/server/rest/services?f=json`, `…/Hosted?f=json`, `…/Hosted/ข้อมูลเรือ_2/FeatureServer/2/query?where=1=1&returnCountOnly=true&f=json`, `…/Hosted/ข้อมูลเรือ_Recent`, `…/Hosted/VesselList_ReconstructTracks`, `…/services/MD?f=json` — Thai Marine Dept's public demo layers (2,030 rows, `source=MarineCadastre`, 2022-05-02, San Diego), the 67-service public folder, and the token-gated production folder.
- `https://nsw.md.go.th/mxdataservice/` — Thai Marine Dept Single Window: REST API with API-KEY, account via their IT group, arrival/departure dataset descriptions.
- `https://vtc.kkp.go.id/` and its `assets_gis/js/mainpro.js` — Indonesian KKP dashboard; `/modules/webservice/rest/`, OAuth to `api.integrated-voyage.com`.
- `https://ais.telkomsat.co.id/` — Indonesian commercial AIS API (`vendor claim`).
- `https://hpradar.com/api` — Hai Phong AIS/ADS-B API: `/ais/vessels`, free tier 100 req/hour, access by request.
- `https://www.suezcanal.gov.eg/English/Navigation/Pages/NavigationStatistics.aspx` — SCA monthly/quarterly/yearly statistics only.
- `https://lethagencies.com/` — Suez agency; transit lists not public.
- `https://portwatch.imf.org/` — IMF/Oxford chokepoint and port aggregates (documented here, measured elsewhere).
- `https://zenodo.org/records/19571058` — LNG-T3, CC BY 4.0, 2020–2024, per-vessel LNG voyages and terminal throughput.
- `https://zenodo.org/api/records?q=%22AIS%22…&type=dataset` — dataset search; `AegeaNET Syros AIS Dataset` (Zenodo 18926663), "Anonymised AIS dataset" (Zenodo 3342090). Caution: Zenodo's default query semantics inflate hit counts.
- `https://www.sjofartsverket.se/sv/tjanster/sjokortsprodukter/digital-data/ais-data/` — Swedish live AIS and RAIS history, 40-odd base stations, charged, 2027 price annex.
- `https://api.data.gov.my/data-catalogue` (400 without `id`), `https://data.gov.sg/api/action/package_search` (404) — national open-data APIs checked for AIS/vessel datasets.
- `https://ows.emodnet-humanactivities.eu/wms?service=WMS&request=GetCapabilities` and `…&request=GetMap&layers=routedensity_all&bbox=…&time=2026-10-01` — 207-layer AIS-derived service; `routedensity_*` abstracts credit EMSA; pixel counts show content in the Danish straits (6,238 opaque px) and nothing in the Gulf, Red Sea or Malacca (300 px = empty mask).
- `https://www.aishub.net/` — cooperative counters (79,730 vessels, 1,788 stations, 82 countries) and share-to-get terms.
