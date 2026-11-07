# mt-rivals: similar aggregators

*Track mt-rivals, MarineTraffic wave, Sat 7 Nov 2026, 18:17–19:20 UTC. Public pages only: no accounts, no sign-ups, no map endpoints inspected, no scraping. `measured` = I fetched it here; `documented` = the operator's own published text; `vendor claim` = marketing with no mechanism shown; `unverified` = lead I could not settle.*

## Bottom line

1. **The open rivals all credit the same six public authorities and a small volunteer network, and none credits a Gulf, Red Sea or South-East Asian feed.** AIS Trail and Pelyr each publish a per-source page; the union is Fintraffic/Digitraffic (Finland), Danish Maritime Authority, BarentsWatch and Kystverket (Norway), NOAA Marine Cadastre (US), Taiwan International Ports Corporation port calls, plus their own receivers — the same set `d-ais` found. **No rival showed a public feed that explains MarineTraffic's Gulf density.** `mt-sources` supplies the other half of the answer: Kpler classifies its own Gulf positions as Terrestrial, "Roaming" (third-party receiver networks) or Satellite, and now owns Spire Maritime outright.
2. **The best free route found for the Gulf is Pelyr's free developer plan** (free account, key, non-commercial): 50 vessels by MMSI, 3.5 million km² stream area, 3-day history, 2 requests/minute, plus satellite-image vessel detections and STS finds in the same API. **Its Gulf coverage is unpublished and untestable without a key** — the one open question worth a key.
3. **The "€9/yr" VesselFinder entry does not exist today.** Its own API page (fetched 7 Nov) prices credits at **175 EUR minimum** (5,000 credits, AIS 1 credit/record, valid 12 months), and the positions API is **terrestrial only**; satellite is a separate 139 USD/month product.
4. **CetaHAV is an AISStream wrapper over a Baltic map and should not be treated as an extra source.** `/api/public/v1/sources` (measured, key-free) lists 20 sources and **no AIS provider**; the use-case page labels AIS "Live AIS (AISStream)"; `/api/public/v1/ais` returned **63 positions, bbox 9.19–25.83E / 54.15–62.64N, zero in a Gulf box**.
5. **Volunteer networks are local.** AIS Trail's entire network is **9 stations**, median range 3–8 nm (measured from `map.aistrail.com/live/stations.json`). VesselFinder instead lists **1,494 stations, 100 countries, 115,096 vessels**, including "Residence Tower, United Arab Emirates" (555 ships) and Indonesian port stations — rival Gulf coverage is shore-contributed, which is why their maps are dense on the coast and empty offshore.

## Findings

### A. What each rival says its sources are

| Rival | Named sources | Evidence |
|---|---|---|
| **AIS Trail** (2026) | Digitraffic (CC BY 4.0); DMA daily files (Danish PSI Act); BarentsWatch + Kystverket (NLOD 2.0, "shore stations and Norwegian satellites"); NOAA Marine Cadastre (CC0); Taiwan ports + MOTC **port calls only** (Taiwan OGL 1.0); Portnet calls (CC BY 4.0); own stations `rx-<id>`; Pelyr for the free map only | `documented`, `aistrail.com/docs/sources/`, 7 Nov |
| **Pelyr** (Dr. Zürner GmbH, Austria) | Digitraffic; BarentsWatch (owner Kystverket); Kystverket historical; Copernicus Sentinel imagery; World Port Index/Wikidata/OSM; own + community stations; unnamed "third-party feeds whose providers permit us to license their data on these terms" | `documented`, `pelyr.com/sources` + Data Licence 2.0, 7 Nov |
| **CetaHAV** (Swedish pilot) | AISStream (map label), SMHI, CMEMS, EMODnet, HELCOM, EEA, NASA GIBS, GFW | `measured` sources JSON; `documented` label |
| **VesselFinder** | "terrestrial AIS network" for the API; separate satellite product; 1,494 credited stations; archive "back to 2009" | `documented`, `vesselfinder.com/vessel-positions-api`, `stations.vesselfinder.com` |
| **MyShipTracking** | "powered exclusively by terrestrial AIS data"; contributors feed via TCP/UDP | `documented`, `api.myshiptracking.com/docs/faq` |
| **ShipXplorer** | "various data sources including its network of ground-based AIS receivers"; plans say "3 Vessel Data Sources… including Satellite AIS sources" | `documented` FAQ, `vendor claim` on the three |
| **ShipFinder**, two unrelated firms | `.co` (UK): own ground receivers, free receiver offer, satellite per help centre. `.com` (TST Corporation, Japan): own facilities "around the Japanese and Chinese coastlines" plus low-orbit satellite receivers, ~60,000 ships | `documented` / `vendor claim` |
| **ShipAtlas / Maritime Optima; MarineRadar (Lascade, Dubai)** | Neither names an AIS supplier. ShipAtlas markets "live satellite AIS positions updated every 5th minute"; MarineRadar says "terrestrial and satellite AIS feeds" | `vendor claim` / `documented`, unspecified |
| **EMODnet Human Activities** (not a rival, same supply chain) | **"AIS data from CLS, ORBCOMM and vesseltracker.com"**, CC BY 4.0 density rasters | `documented` via AIS Trail's attribution text |

**Two supply chains, one visible.** The government-feed chain is public and shared; the satellite chain is commercial and hidden — CLS, ORBCOMM and Spire/exactEarth leak out through EMODnet's attribution and ShipAtlas's explainer, never from a rival's own page. **I found no evidence that any of these resells another's positions**, and none names MarineTraffic/Kpler as a supplier. "They all share one hidden feed" is unproven.

### B. Every credited public source (required by the brief)

**Public AIS:** Digitraffic (`meri.digitraffic.fi`, CC BY 4.0, Class A only, fishing removed); Danish Maritime Authority (`aisdata.ais.dk`, PSI Act, Class A+B, private vessels excluded, 2–3 days behind); BarentsWatch Live AIS (NLOD 2.0, Norwegian EEZ + Svalbard/Jan Mayen, **includes "Norwegian satellites"**, excludes fishing <15 m, leisure <45 m, offshore-station positions); Kystverket historical (`hais.kystverket.no`, NLOD 2.0, positions only, from Nov 2024); NOAA Marine Cadastre (CC0, US waters, ≤1 position/vessel/minute, months behind); Taiwan International Ports Corporation + MOTC (Taiwan OGL 1.0, port calls only); Portnet Finnish port calls (CC BY 4.0); AISStream (credited by CetaHAV only).

**Derived:** EMODnet vessel and EMSA route density (CC BY 4.0); UK MMO Shipping Vessel Density Grid (OGL v3, "AIS data reproduced with permission of the MCA and MMO"); GFW fishing effort (CetaHAV); NOAA ENC cables; GEBCO; NVE cables (NLOD 1.0).

**Reference/sanctions:** OFAC SDN (public domain), UK Sanctions List (OGL v3), EU Reg. 833/2014 Annex XLII (CC BY 4.0); World Port Index, Wikidata (CC0), OSM (ODbL). AIS Trail **does not** use the UN Consolidated List because its terms forbid commercial redistribution — a useful precedent for us.

### C. Free and cheap routes, ranked for our regions

| Route | Gulf / Red Sea | Asia | Cost | What it gives |
|---|---|---|---|---|
| Pelyr free | unknown (not published) | unknown | 0, free account | 50 MMSI, 3.5 M km² stream area, 3-day history, 2 req/min; box-at-an-instant; satellite detections + STS finds; MCP |
| AIS Trail free map + keyless MCP | **no** | no | 0 | live map, replay; its sources contain no Gulf data |
| ShipXplorer Basic | map only | map only | 0 | live map (10-minute map timeout); **track download CSV/GeoJSON/KML is Business-only**; API page "under construction" |
| ShipAtlas Free | map only | map only | 0 | 10 live AIS views, 5 historical, no export |
| MarineRadar | map only | map only | 0 | free web map, no account; satellite credits paid |
| VesselFinder credits | yes, terrestrial | yes, terrestrial | **175 EUR / 5,000 records**, VAT extra | JSON: MMSI, position, SOG/COG/heading/status, destination+UN/LOCODE, ETA |
| VesselFinder satellite | yes | yes | 139 USD/month, 1,399 USD/year | undelayed satellite positions, "unlimited" ships |
| ShipXplorer paid | yes | yes | 24.50–399.50 USD/yr | UI history 7/30/90/365 days by plan; download at 399.50 USD/yr |

**No free tier here gives bulk Gulf positions.** Each free plan is either a human map with export disabled or an API whose coverage is exactly the public-authority set above. The one credible zero-cost Gulf candidate is Pelyr's free plan, because its licence names third-party feeds it does not identify.

### D. What the rivals' terms allow

- **Pelyr (Data Licence 2.0).** Free-plan data is **non-commercial only** (its own definition excludes non-profit research and teaching that generates no income — the read is ours). You **may store, analyse and display** it, indefinitely; you **may not** pass on raw data "not as a file, not as a feed, not through an API", relay the service, or do "bulk or systematic extraction, not even through your own interface". Visible attribution required. The **public map** uses a rotating pseudonymous identifier and resolving it "by correlating positions or by any other means" is forbidden — an anti-scraping design we must not work around.
- **AIS Trail.** CC BY 4.0/CC0 sources are redistributable with attribution; **its Danish data is not**; bulk resale needs a written redistribution agreement.
- **VesselFinder.** `d-ais` records that its terms forbid dataset building; per-record pricing is consistent with that. **ShipXplorer** gives a free Business subscription for feeding a station, but data still leaves only as UI or CSV.

### E. Methods worth borrowing

1. **Per-record provenance and freshness:** `meta.attribution` (+ `X-Attribution` on CSV), per-source first/last dates and `available_until` (AIS Trail); a `license` id on every message resolving through `sources[]` and a key-free `/v1/sources` (Pelyr). Exactly the discipline a radar-versus-AIS comparison needs.
2. **Delay stated per source, never averaged** ("DMA 2–3 days behind, BarentsWatch live, NOAA months late").
3. **Sanctions flags as a separately sourced layer**, labelled "informational, not a compliance determination".
4. **Satellite detections and STS finds inside the same API** (Pelyr): our idea already exists as a product, paired the same way.
5. **Pseudonymous display IDs** for a demo of data we may not republish; **MCP servers** over the same endpoints.

## Source rows

| Source | Operator | Type | Regions | Access route | Account/cost | One record | Update | Delay | Identifies ship? | Licence, limits | Used by MT? | Usable by us? | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| CetaHAV | Swedish pilot (Esri) | aggregator | Baltic only | `/api/public/v1/*`, open CORS | none | mmsi, name, sog, cog, heading (63 pts measured) | 1 min | not stated | yes | not stated | no | map only; adds no coverage | measured |
| AIS Trail | AIS Trail (2026) | aggregator, paid API + free map/MCP | FI, DK, NO, US, Taiwan ports, 9 stations | API key; keyless MCP | free map; paid API | positions, identity, port calls, sanctions flags | s–days by source | published per source | yes | CC BY/CC0/NLOD/OGL/Danish PSI | no | source list yes; no Gulf | documented + measured |
| Pelyr | Dr. Zürner GmbH | aggregator + community | FI, NO, own/community stations, satellite detections | HTTPS, WS, NMEA, MCP | free account; Free plan non-commercial | positions, tracks, box-at-instant, satellite detections, STS | stream, 3-day history | not published | yes | Data Licence 2.0 (store/analyse/display; no redistribution/bulk) | no | best free candidate; Gulf unverified | documented; measured 401 without key |
| VesselFinder | VesselFinder Ltd | aggregator | global terrestrial + satellite | web, credits API, area subscription | 175 EUR min | AIS + Voyage + Master | minutes | minutes | yes | per-record; no dataset building | competitor | only if paid, terrestrial only | measured pricing |
| ShipXplorer | ShipXplorer | aggregator + hardware | global via own receivers + "3 sources" | web/app | Basic free; 24.50–399.50 USD/yr | map entities; export at top tier | minutes | not stated | yes | subscription terms | no | map only; no API | documented |
| MyShipTracking | MyShipTracking | aggregator | global terrestrial | web + paid API | paid, trial | positions, voyage, calls | <1 s claimed | seconds | yes | paid API terms | no | no free route | documented |
| ShipFinder (.co) | ShipFinder UK | aggregator | global, own receivers | web/app | free map, Pro paid | positions, particulars | minutes | not stated | yes | app terms | no | map only | documented |
| ShipFinder (.com) | TST Corp (Japan) | aggregator | Japan/China emphasis, satellite | web/app | paid | positions | ~3 M packets/day | not stated | yes | commercial | no | no | vendor claim |
| ShipAtlas | Maritime Optima | aggregator/app | global incl. satellite | web/app | free tier, €10/mo | positions, last/next port, ETA | satellite every 5 min | not stated | yes | app terms | no | no export | vendor claim |
| MarineRadar | Lascade | aggregator/app | global terrestrial + satellite | web/app | free, no account | positions, particulars, ports, lights | not stated | not stated | yes | app terms | no | map only | documented, supplier unnamed |
| AISHub | receiver co-op | raw pool | where members feed | XML/JSON API | must feed a receiver | raw AIS | near-real-time | seconds | yes | reuse with credit | unknown | only via receiver | documented |
| EMODnet density | EMODnet HA (Cogea) | derived density | global | WMS/download | none | vessel-hours per cell | periodic | years | no | CC BY 4.0; AIS from CLS/ORBCOMM/vesseltracker | n/a | yes, as traffic baseline | documented |
| UK MMO density | MMO/Defra | derived density | UK | Defra API | none | transit density per cell | annual | 1 yr+ | no | OGL v3 | n/a | UK baseline only | documented |

## What this means for us

- **Use.** The reusable asset from this track is **provenance plumbing**, not positions: per-record source, age and licence, published as AIS Trail and Pelyr publish it. That is what lets us mix Danish archives, GFW and radar without ever misstating currency.
- **Borrow.** A key-free `/sources` endpoint stating what we serve and how old it is; per-source delay rather than one number; sanctions flags as a separate sourced layer; pseudonymous display IDs if we ever surface a restricted feed; an MCP tool over our own API.
- **Rule out.** Any hope that a free rival API closes the Gulf. CetaHAV is AISStream; AIS Trail, Pelyr and ShipFinder's free tiers are Baltic/Norway/US/Taiwan; VesselFinder's cheap product is terrestrial and costs 175 EUR minimum; ShipXplorer and ShipAtlas export nothing free. **MarineTraffic's Gulf density is not reproducible from any free aggregator found.**
- **Watch.** Pelyr is the one credible free Gulf candidate (3.5 M km² would cover the Gulf and Gulf of Oman) and it already ships satellite-detection and STS products — both a possible route and the nearest existing competitor.
- **Store/serve/display.** "Keep it, don't redistribute it" terms fit a backend that caches and analyses and a demo that shows *findings* (gaps, identity changes) with attribution, not a live mirror of someone else's feed.

## Unknowns

- **Pelyr's Gulf and South-East Asian coverage.** Unpublished, hidden behind a key (measured 401 on `GET /v1/sources`). Settle by registering one free account and querying a Hormuz and a Malacca box; the licence permits that use.
- Whether Pelyr's unnamed "third-party feeds" include satellite AIS, which is what Gulf coverage would require.
- Whether any rival white-labels MarineTraffic/Kpler, Spire or ORBCOMM positions. No page names a supplier; MarineRadar's "terrestrial and satellite AIS feeds" is the most opaque.
- ShipXplorer's "3 Vessel Data Sources"; MyShipTracking's station count; ShipAtlas's satellite supplier.
- Whether VesselFinder still sells the small annual plan `d-ais` recorded at €9/yr — today's page shows a 175 EUR minimum instead.
- How much of MarineTraffic's own Gulf density is shore versus satellite. This track can only bound it negatively; `mt-sources` and `mt-access` own that answer.

## Sources

- **CetaHAV:** `cetahav.org/api-docs`, `/api/public/v1/sources` and `/api/public/v1/ais` (both measured), `/map/uc1` ("Live AIS (AISStream)").
- **AIS Trail:** `aistrail.com/docs/sources/` (licences, attribution, coverage, "Norwegian satellites", UN-list exclusion); `api.aistrail.com/v1/sources` and `map.aistrail.com/live/stations.json` (measured).
- **Pelyr:** `pelyr.com/pricing`, `/sources`, `/pelyr-data-license`, `/network/`, `dashboard.pelyr.com/en/docs`.
- **VesselFinder:** `stations.vesselfinder.com`; `vesselfinder.com/vessel-positions-api`, `/satellite-ais`, `/realtime-ais-data`.
- **ShipXplorer:** `shipxplorer.com/faq`, `/addcoverage`, `/sharing-data`, `/subscribe`, `/api` ("under construction"). **MyShipTracking:** `api.myshiptracking.com/docs/faq`, `/help-center/contributors/add-your-station`.
- **ShipFinder:** `shipfinder.co/about/how-shipfinder-works`, `/about/coverage`; `helpcenter.shipfinder.com/guides/vessel-tracking/real-time-vessel-tracking`; `toyoshingo.co.jp/en/service/information/shipfinder.html`.
- **ShipAtlas:** `maritimeoptima.com/shipatlas`, `/shipatlas/pricing`, `help.maritimeoptima.com/en/articles/13941326-…`, `/insights/ais-and-the-main-categories-of-ais-challenges`. **MarineRadar:** `marineradar.com/about`, `/hub/marineradar-free-vs-paid`.
- **Derived layers:** `emodnet.ec.europa.eu/en/human-activities` (CC BY 4.0, "AIS data from CLS, ORBCOMM and vesseltracker.com"), read from AIS Trail's attribution text; UK MMO Shipping Vessel Density Grid, `environment.data.gov.uk` (OGL v3).
