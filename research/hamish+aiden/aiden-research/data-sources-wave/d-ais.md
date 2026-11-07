# d-ais: every source of what ships announce

*Track d-ais, data-sources wave, Sat 7 Nov 2026, 16:30–17:25. Everything below was run from the venue network with no accounts and no credentials. Labels: `measured` = I ran it here; `documented` = primary source; `vendor claim` = the operator's own words; `unverified` = a lead I could not confirm.*

## Bottom line

1. **Nothing global is available without an account.** Every route to worldwide positions needs a sign-in of some kind: AISStream (free key via GitHub), BarentsWatch (free user + API client), Global Fishing Watch (free token), AISHub (you must feed it a receiver). There is no keyless global AIS feed.
2. **Free history is national or academic, never global, and that decides where the comparison can be reproduced.** Deep, no-account archives exist for **Denmark** (DMA daily files, `aisdata.ais.dk`), the **US** (NOAA MarineCadastre, 2009–2023 daily zips) and **Norway** (Kystverket, 2005 onward, application for the full set), plus one open research archive for **Piraeus, Greece, 2017–2019** (Zenodo, CC BY 4.0, 15.5 GB, anonymised). Finland's Digitraffic is live-only in practice.
3. **The US archive is real and large, and its 2024–2025 links are dead.** One measured day (2023-06-15): 8,346,960 rows, 21,116 distinct MMSI, columns include `TransceiverClass` (A/B) and `IMO`. But `AISDataHandler/2024/index.html` lists 366 files and every one I tried returned 404.
4. **For the Gulf, Red Sea, Malacca, Natuna, India, Japan, Korea, Taiwan and Southeast Asia there is no public raw AIS at all.** The only free views are derived: GFW (token, non-commercial) and IMF PortWatch (daily counts, measured 6 days behind by another track). Satellite AIS and LRIT are closed.
5. **Hormuz and illegal-fishing-in-Asia cannot be demonstrated as AIS-versus-radar tonight without a free account.** The Baltic can — but only the Danish slice of it, because Denmark is the one Baltic state publishing raw archives.

## Findings

### A. What actually needs no account (measured)

| Route | Call | Result |
|---|---|---|
| Digitraffic REST, Finland | `curl --compressed -H 'Digitraffic-User: hacktheburgh/feasibility' https://meri.digitraffic.fi/api/ais/v1/vessels` | 200, 41,946 B; **837 vessels**, all with MMSI/IMO/type, 780 with destination; 942 last positions in 16.56–32.53E, 57.64–65.80N. Without `Accept-Encoding: gzip`: **406** "Use of gzip compression is required". |
| DMA Danish archives | `curl -r 0-1000 http://aisdata.ais.dk/aisdk-2026-11-01.zip` | **206**, valid zip header. Daily files present for 2026-11-01. |
| NOAA MarineCadastre 2023 | `curl -r 0-2000000 …/AISDataHandler/2023/AIS_2023_06_15.zip` | **206**, 2,000,001 B, valid zip; full file 328,773,356 B, download 197 s (~1.6 MB/s). |
| NOAA MarineCadastre 2024 | `…/AISDataHandler/2024/AIS_2024_01_01.zip`, `…_06_15.zip` | **404** both; `2024/index.html` is live and claims 116.7 GB. |
| Kystverket open stream, Norway | `socket.create_connection(("153.44.253.27", 5631), timeout=10)` | **TimeoutError: timed out.** Documented as open and registration-free. |
| BarentsWatch AIS Live API | `GET https://live.ais.barentswatch.no/v1/latest/ais`, `/v1/openaisarea` | **401** both. Its own OpenAPI description: "you need to register a user at barentswatch.no and create an AIS-API client". |
| AISHub API | `https://data.aishub.net/ws.php?format=1&output=json` | 200 with **0 bytes**; its join page: "At least one raw AIS feed in NMEA format from a receiver you operate… get free access in return". |
| AMSA (Australia) digital data | `GET …/spatial/DataServices/Download` | **500**; page carries `/spatial/Home/SignIn`. AIS incl. satellite is mentioned but not downloadable anonymously. |
| MarineTraffic academic page | `GET /en/p/academic` | **403**. |
| Datalastic | pricing page | paid tiers only, "2 weeks trial", no free tier. |
| Spire maritime | product pages | no public research/free tier found (`vendor claim` structure only). |

What one US day looks like (measured, `AIS_2023_06_15.zip` → `AIS_2023_06_15.csv`, 896 MB):

```
MMSI,BaseDateTime,LAT,LON,SOG,COG,Heading,VesselName,IMO,CallSign,VesselType,Status,Length,Width,Draft,Cargo,TransceiverClass
368163860,2023-06-15T00:00:00,41.53853,-73.99443,9.2,197.9,194.0,JANICE ANN REINAUER,IMO9903932,WDL7830,57,12,177,24,6.6,57,A
```
8,346,960 rows, 21,116 MMSI, IMO present on 4.87 M rows, lat 2–51 N, lon 160 W–145 E (US waters and Pacific territories). Average ≈395 rows per vessel per day, i.e. ~3.6 min — consistent with a per-minute cap applied on top of reception gaps, not a raw feed.

### B. Free with an account (the realistic working set)

- **AISStream** — free key via GitHub, live WebSocket only, 3 connections, no history. Shared notes report no Middle East positions since ~16 Oct (issue #322), untested here.
- **BarentsWatch AIS Live API** — free registration + client; NLOD licence; Norwegian economic zone, Svalbard and Jan Mayen; excludes fishing vessels under 15 m and recreational craft under 45 m (Kystverket's own page says this of the *open* component, and says open access "does not require user registration" — the two statements only reconcile through the TCP feed).
- **Global Fishing Watch** — free non-commercial token, global presence grids and events from 2012, ~4 days behind; licence CC BY-NC 4.0.
- **AISHub** — pooled raw feed in exchange for operating a receiver; commercial reuse allowed with "Data: AISHub contributors".

### C. Coverage by region

"Past-time history" means positions at an arbitrary earlier timestamp, which is what a satellite scene needs.

| Region | Free raw AIS, no account | Past-time history, free | Evidence |
|---|---|---|---|
| Baltic N (Finland) | **Yes**, live (837 vessels) | **No** — Digitraffic returns last position per MMSI only | measured here; confirmed by t-ais-live |
| Baltic S (Denmark) | **Yes**, archives | **Yes**, daily files, ~3-day lag | measured 206; Hamish 02 |
| Norway / North Sea | TCP 5631 (no registration) | Yes, 2005+ on application | timed out here; documented |
| Sweden, Poland, Germany, Latvia, Lithuania, Estonia | none found | no | pages 404/blocked 16:36Z; not exhaustive |
| UK, Ireland | none found | no | Irish Atlas has no AIS service (`AIS/MapServer` 404) |
| US coastal + inland | no live | **Yes**, 2009–2023, 8.3 M rows/day | measured |
| Canada, Mexico, Caribbean | not verified | not verified | — |
| Mediterranean, Black Sea | none official (EMSA/THETIS hold inspections, not positions) | **one research archive**: Piraeus 2017–2019 | Zenodo record measured |
| Gulf / Hormuz | none | no | portals 405/timeout; AISStream reported dead |
| Red Sea / Suez | none | no | — |
| Malacca / Singapore | none | no | MPA page 404 |
| Indonesia / Natuna | none (KKP VMS closed) | no | `vms.kkp.go.id`, `fishnet.kkp.go.id` timeouts |
| Thailand, Vietnam, Philippines, Malaysia | none | no | timeouts / 403 |
| Japan, Korea, Taiwan | none | no | 502/timeouts; data.go.kr needs a key |
| India | none | no | 15 s timeout |
| Australia | gated (AMSA sign-in) | gated | measured |
| High seas / any ocean | only satellite AIS (paid) or AISStream/GFW | no | — |

### D. Satellite AIS, VMS, LRIT

- **Satellite AIS** is the only way to hear ships offshore. Every route found is commercial (Spire, which absorbed exactEarth; S&P Global, which absorbed ORBCOMM; CLS; MarineTraffic/Kpler; MarineRadar) or a research application. No open satellite-AIS archive and no free tier that reports a specific past position was found. Norway's Kystverket history is the one documented exception in principle, and it covers Norwegian waters only.
- **VMS** (government tracking of licensed fishing boats, usually hourly) is confidential in every state I could check: Indonesia's KKP VMS portals did not respond, Peru's IMPARPE page 404, Chile's Sernapesca site loads but publishes no positions, Panama's AMP loads but publishes no positions. The only global view is GFW's partner channel, by agreement with the flag state.
- **LRIT** (long-range identification and tracking, SOLAS V/19-1) is distributed through LRIT Data Centres and the International LRIT Data Exchange to contracting governments only; IMO's own page describes the architecture, not a public feed. No public access exists at any price.

### E. Research archives (a real, overlooked class)

Zenodo hosts AIS archives with no account and open licences. The largest I found: **"The Piraeus AIS data set expressed under the vesselAI ontology"** (Zenodo 10006470, 2023-10-16, **CC BY 4.0, 15.5 GB, open**) with `rawPositions2017/2018/2019.7z` (3.0 + 5.6 + 5.2 GB) covering 9 May 2017 – 26 Dec 2019 in the Piraeus approaches, plus synopses and trajectories. Its paper (Data in Brief, DOI 10.1016/j.dib.2021.107782) says positions are **anonymised**, so identity may not survive — decisive for sanctions joins, irrelevant to radar matching. Also on Zenodo: an AIS-annotated Sentinel-2 ship-type patch set (CC BY 4.0), useful to d-value. Historical and scene-specific, but they are the only free AIS outside six national archives.

### F. Paid services and free/student tiers

MarineTraffic (Kpler): free web, API paid, academic page 403. VesselFinder: free web, API from €9/yr, terms forbid dataset building. FleetMon is now Kpler. Datalastic and MyShipTracking are paid with short trials. ShipXplorer and MarineRadar are freemium, receiver hosting earns credit. ShipAtlas caps free satellite positions at ten. Tradlinx does free no-account lookups but no bulk. Windward, Kpler, Vortexa and S&P are enterprise only. **No student tier was verified anywhere.**

## Source rows

| Source | Type | Regions covered | Free access route | Account needed? | What one record contains | Update rate | Delay from event to us | Position or resolution accuracy | Identifies the ship? | Licence, commercial limits | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|
| Digitraffic Marine | shore AIS, government | Finland + N Baltic | REST/MQTT `meri.digitraffic.fi` | no (header only) | MMSI, IMO, name, type, draught, destination, ETA; separate position feed with SOG/COG/heading/navstat | seconds | 0.5 s median (t-ais-live) | GPS, metres | yes | CC BY 4.0 | measured |
| DMA Danish AIS | shore AIS, government | Danish waters | daily zip `aisdata.ais.dk` | no | full NMEA-derived CSV, ~0.5–2.6 GB/day | daily | ~3 days | metres | yes | free, Danish public data | measured + Hamish 02 |
| NOAA MarineCadastre | shore AIS, government | US waters + territories | daily zip per day, 2009–2023 | no | MMSI, time, lat/lon, SOG, COG, heading, name, IMO, callsign, type, status, dimensions, draft, cargo, A/B class | daily | 2+ years | metres | yes | US public domain | measured |
| Kystverket open AIS (TCP) | shore AIS, government | Norwegian EEZ, Svalbard, Jan Mayen | `153.44.253.27:5631`, IEC 62320-1 | no | raw NMEA sentences | real time | seconds | metres | yes | NLOD | documented; connect timed out |
| Kystverket historical | shore + satellite AIS | Norway | files from 2005; full set on application | partial | as above | daily | days | metres | yes | NLOD | documented, `unverified` depth |
| BarentsWatch AIS Live API | shore AIS, government | Norway | `live.ais.barentswatch.no/v1/...` | **yes**, free user + client | JSON Position/StaticData/Aton/MetHyd | streaming | seconds | metres | yes | NLOD | measured 401; spec text |
| AISStream | community aggregator | global (reported ME gap) | `wss://stream.aisstream.io/v0/stream` | **yes**, free key | raw AIS message | streaming | ~45 s–2 min (Hamish) | metres | yes | free, no SLA | documented, untested |
| AISHub | receiver cooperative | global where members feed | XML/JSON/CSV API | **yes**, must feed a receiver | raw AIS | near real time | seconds | metres | yes | commercial reuse with credit | measured 0-byte response + join page |
| Global Fishing Watch | derived AIS product | global | API + map | **yes**, free token | presence grids, gaps, encounters, port visits, SAR detections | daily | ~4 days | 0.1° grids | partly (vessel ID on events) | CC BY-NC 4.0 | documented |
| IMF PortWatch | derived AIS product | 1,800 ports, 28 chokepoints | ArcGIS FeatureServer | no | daily port calls, transit counts per chokepoint | daily | 6 days (measured) | port/chokepoint level | no | IMF terms, free | d-context measured |
| AMSA digital data | shore+satellite AIS, government | Australian SAR region | web portal | **yes** (sign-in) | AIS track shapefiles (catalogue claim) | monthly | weeks | metres | yes | Australian government | measured 500 + SignIn |
| MarineTraffic | commercial aggregator | global | web map | free web, paid API | positions, voyage, port calls | seconds | seconds–minutes | metres | yes | paid; academic page 403 | measured |
| VesselFinder, Datalastic, MyShipTracking | commercial APIs | global | web map / API | free web; API paid, trial only | positions, particulars | minutes | minutes | metres | yes | VesselFinder terms forbid dataset building | measured 400/401 |
| Zenodo AIS research archives (Piraeus) | research archive | Piraeus approaches, Greece | `zenodo.org/records/10006470`, 7z files | no | raw positions + synopses + trajectories + ontology | static, 2017–2019 | years | metres | anonymised (check) | CC BY 4.0 | measured record metadata |
| Spire / S&P (exactEarth, ORBCOMM) | satellite AIS, commercial | global ocean | contract | **yes**, sales | satellite positions | minutes–hours | 5–60 min typical | metres | yes | paid only | vendor claim |
| LRIT | treaty system | global | none (governments only) | n/a | ship identity + position to authorities | 6 h default | hours | ~km-scale | yes | restricted | documented (IMO) |
| National VMS | government fisheries | EEZ | none found public | n/a | positions of licensed fishing vessels, typically hourly | hourly (unverified) | hours–days | ~100 m (unverified) | yes | confidential | measured portals |

## Consequence for feasibility

- **What becomes possible tonight, free:** a genuine radar-versus-AIS comparison over Danish waters (DMA archives, day-level, ~3 days behind) and a repeat of the same method over US waters back to 2023. Both are strong enough for a real measured claim rather than a mock-up.
- **What is ruled out:** any current, region-wide AIS layer for the Baltic outside Denmark without an account; anything at all for Hormuz, the Red Sea, Malacca, Natuna, India, Japan, Korea, Taiwan, or the open ocean without either a free account (AISStream, GFW) or money. **Satellite AIS at a specific scene time is out of reach**, which rules out the "silence offshore" version of the story.
- **Honest framing:** the defensible sentence is "in the Baltic, where Denmark publishes raw AIS and Sentinel-1 revisits often, we can show a ship that radar saw and AIS did not". For the Gulf the same sentence would be aspirational, and the data to support it (satellite AIS or paid archives) is not obtainable in a weekend.
- **Regions this helps most:** Denmark and the Danish straits; the US Gulf and East Coast as a demonstration of scale; Norway if the TCP route or the free account works from the venue.
- **A Mediterranean precedent exists but is historical:** the Piraeus archive (2017–2019, CC BY 4.0) could support a radar-versus-AIS test there if Sentinel-1 scenes from the same window are retrieved, but its positions are described as anonymised, so it can test detection, not identification.

## Unknowns

- Whether AISStream actually delivers Baltic positions tonight (needs a key; the Middle East gap is reported, not re-tested).
- Whether Kystverket's TCP feed is reachable on a different egress — the failure here was a clean TCP timeout, which may be the venue firewall rather than the service.
- Turnaround for Kystverket's historical application, and whether its archive really includes satellite AIS positions usable at a scene time.
- What AMSA's gated download contains (hourly positions or something sparser) — a sign-in would settle it in minutes.
- Whether the dead MarineCadastre 2024/2025 files exist under `hub.marinecadastre.gov` or an S3 bucket; the hub page loads but exposes no obvious file list.
- Whether the Piraeus `rawPositions` files carry MMSI or a synthetic ID — decides whether that archive supports identity work.
- Canada, New Zealand, Ireland and West Africa were not searched exhaustively; "none found" means "no public raw AIS on the pages I checked".

## Sources

- Digitraffic Marine API — https://www.digitraffic.fi/en/marine-traffic/ (live feed, licence, headers).
- Danish Maritime Authority AIS — https://www.dma.dk/safety-at-sea/navigational-information/ais-data and `http://aisdata.ais.dk/` (archive contents).
- NOAA MarineCadastre — https://coast.noaa.gov/htdata/CMSP/AISDataHandler/2023/index.html (file lists) and https://hub.marinecadastre.gov/pages/vesseltraffic (current product).
- Kystverket access to AIS data — https://www.kystverket.no/en/sea-transport-and-ports/ais/access-to-ais-data/ (open vs closed component, TCP address, exclusions, NLOD).
- BarentsWatch AIS Live API spec — https://live.ais.barentswatch.no/live/openapi/ais/openapi.json (endpoints, auth requirement, message types, NLOD).
- AISStream — https://aisstream.io/documentation (key, limits); issue #322 reported in shared notes.
- AISHub — https://www.aishub.net/join-us (share-to-get terms, commercial reuse).
- Global Fishing Watch — https://globalfishingwatch.org/our-apis/ (token, non-commercial).
- IMF PortWatch — https://portwatch.imf.org/ (derived AIS; measured separately by d-context/t-regions).
- AMSA — https://www.operations.amsa.gov.au/Spatial/DataServices/DigitalData (AIS mentioned, sign-in gate).
- IMO LRIT — https://www.imo.org/en/OurWork/Safety/Pages/LRIT.aspx (architecture, government-only distribution).
- Zenodo Piraeus AIS dataset — https://zenodo.org/records/10006470 (files, licence, 2017–2019 coverage); paper DOI 10.1016/j.dib.2021.107782 (anonymised positions).
- MarineTraffic, VesselFinder, Datalastic, Spire, MyShipTracking pages (paid tiers; see Findings E).
