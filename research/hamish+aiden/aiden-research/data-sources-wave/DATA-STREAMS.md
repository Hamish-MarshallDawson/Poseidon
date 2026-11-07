# Data streams catalogue

Every data source assessed so far. **Tested** means someone ran it on 7 November 2026: **orchestrator** means Aiden's main agent ran and checked it, **agent** means a research agent did, and **docs** means documentation only. Numbers come from short tests, so re-measure before relying on them.

## What ships announce

| Source | Coverage | Delay | Access | What it gives | Limits | Tested |
|---|---|---|---|---|---|---|
| **AISStream** | Strong in North Sea, Danish straits, Channel, US East; some Baltic, Singapore, Java Sea; **zero** in Hormuz, Persian Gulf, Gulf of Oman, Red Sea, Natuna, Gulf of Thailand, open South China Sea | Live; about 1 update a minute per ship at best. Its 3 s figure may be its own timestamp | Free key via GitHub; WebSocket | Position, MMSI, static data with IMO, Class A and B | 3 connections per account and IP; no replay; no SLA. 26,133 vessels in 16 min | Orchestrator |
| **Digitraffic** | Northern Baltic, 16.6 to 32.5E, 57.6 to 65.8N; thin at Russian ports | About 0.5 s; 37 messages a second | No key; MQTT over WebSocket, REST | Position; name, type, draught, destination, IMO 68% | Class A only; **fishing boats removed**; types folded; REST gives last position, not tracks. Needs `Digitraffic-User` header and gzip. CC BY 4.0 | Agent |
| **Danish Maritime Authority** | Danish waters, western Baltic, 53.7 to 58.7N, 2.6 to 16.5E | About 3 days | No key; `http://aisdata.ais.dk/aisdk-YYYY-MM-DD.zip` | Full tracks; name 91%, IMO 61.5%; median 10 s | 580 MB zip per day; 28% duplicates; monthly files to 2007; licence unstated | Agent |
| **Global Fishing Watch AIS** | Global, all ship types despite the name | About 4 days | Free token | Vessel presence, identity, flag, type, port visits, gap events | Non-commercial (CC BY-NC 4.0). **Per-vessel positions return 404 "temporarily unavailable"**; anonymous hourly cell positions work | Orchestrator |
| **NOAA MarineCadastre** | US waters | Ends 31 Dec 2024 | No key; daily zips | Full tracks, `TransceiverClass`, IMO 58% | Stale; 2025 and 2026 return 404 | Agent |
| **CetaHAV** | Baltic and Danish straits, 9 to 26E; Hormuz zero | About 1 min for moving ships; old for stopped ones | No key; `cetahav.org/api/public/v1/ais` | MMSI, name, speed, course, heading; **no timestamp** | AISStream-based sampler: about 55 ships per 12.6 s call; 6.9% of positions over 1 h old; parallel calls return empty. An empty answer never means no ships | Agent |
| **Pelyr** | Named sources Finnish and Norwegian, plus own and unnamed permitted feeds; **Gulf unknown** | Unknown | Free account and key, non-commercial; Community plan free on application for research and open source | Free: positions and 3-day history. **Satellite detections and ship-to-ship finds are not on Free** (`403 detection_not_in_plan`); they come with Community or paid plans from Fleet up. Detections carry an AIS state, where `dark` means no AIS from a ship that size while coverage was good | Free: 50 ships by MMSI, 3.5 million km², 2 requests a minute, no time slice. Community: 500 ships, whole world, raw NMEA. Detection areas are chosen by Pelyr. Also a possible competitor | Pricing, API docs and sources pages checked by orchestrator; **not tested, needs key**. See `contributor-access.md` |
| **AIS Trail** | Mostly Baltic, Norway, US, Taiwan port calls | Varies | Key | Positions, per-source provenance | 9-station volunteer network | Agent |
| **AIS-catcher community map** | Claims 1,313 stations | Claimed live | Human-confirmed viewing only | Viewing | Blocks automated clients; no network API. Not a usable feed | Agent |
| **Sweden, Sjöfartsverket** | Swedish waters | Live, history from 2006 | Paid, by order | AIS stream, history | Published 2027 price annex | Agent |
| **BarentsWatch** | Norwegian zone, Svalbard, Jan Mayen | Live | Free account and OAuth client | Latest AIS, 14-day history | Norway only | Docs |
| **Kystverket TCP** | Norway | Live | `153.44.253.27:5631` | Raw AIS | Timed out from this network; port 5632 closes without data | Orchestrator, agent |
| **AISHub** | Global where members feed; 4 UAE stations in its directory | Near real time; station delay up to 10 s | Must contribute a receiver | Combined latest positions once a minute | Station needs 10+ vessels, 90% uptime on a 7-day average. Commercial use with credit; no passing on raw data. **Not possible this weekend** | Terms checked by orchestrator; directory by agent |
| **MarineTraffic / Kpler** | Global | Shore near live; satellite in bursts, paid | Free map to view; plans; sales-led API | Rich processed data, labelled terrestrial, roaming or satellite | **Terms bar derived data and publishing.** Export capped at 5, 300 or 10,000 rows a month on plans. Manual cross-check at most; not for scraping | Terms checked by orchestrator; Aiden's manual look; agent |
| **Paid APIs** | Global | Varies | ShipAtlas from €65/month; MyShipTracking from €90, reportedly shore-only; Searoutes from €300; VesselFinder from €175 for 5,000 credits, shore-only, satellite separate at $139/month; others by quote | Varies | Listed prices mostly unverified; check licence and coverage | Docs, agent |

## What satellites see

| Source | Coverage | Delay | Access | What it gives | Limits | Tested |
|---|---|---|---|---|---|---|
| **Sentinel-1 raw radar** | Coasts: passes per week at a point: Gulf of Finland 5.1, Danish straits 4.7, Hormuz 3.0, Gulf of Oman 1.9 to 4.0, Malacca 0.7 to 0.9, Natuna 0.5 to 0.9. Mostly zero in open ocean | Usually 1 to 5 h, sometimes 10+ h | No account via Earth Search with AWS, or Planetary Computer | 10 m images, cloud and night proof | **Planetary Computer `sentinel-1-grd` location metadata is wrong**; use annotation XML or `sentinel-1-rtc`. No identity | Orchestrator, agents |
| **Global Fishing Watch radar detections** | Coastal, but **almost none in Gulf of Finland** | 3 to 4 days | Free token | Daily detections with or without AIS match | Non-commercial; per-vessel view currently unavailable | Orchestrator |
| **Sentinel-2 optical** | Mostly wide coastal | Hours | No account via Earth Search | 10 m colour imagery | Daylight and cloud limited. Clear days are few in November's Baltic | Orchestrator, agent |
| **Skylight** | Global | Days | Free public map; platform for governments and NGOs | Detections from radar and optical | No bulk route confirmed | Docs |
| **VIIRS boat detection** | Global | About 6 h for paid; open data later | Final data open; near-real-time paid | Night-light boats | Baltic coverage not confirmed | Docs |
| **Umbra open data** | Selected sites | Task-based | No account, S3 | Very high-resolution radar | Not systematic | Agent |
| **NISAR** | Mainly land | Days or more | Free Earthdata login | L-band radar | Poor fit for ships at sea | Agent |

## Detection tools

| Tool | Status | Notes |
|---|---|---|
| **Ai2 `rslearn_projects` Sentinel-1 detector** | Runs on an RTX 4060; 108 s per 40 km window | Apache-2.0. Weights about 2.4 GB. Needs a historical scene. Missed 4 of 8 ships in its larger test, so unproven |
| **Simple threshold (CFAR-style)** | Runs on CPU in 13 to 16 s per window | Higher recall, about 30 false detections per real ship without a good land and structure mask |
| **esamoun/dark-vessel-detection** | Reference | MIT; good matching method; no published weights confirmed |

## Context to combine

| Source | What it adds | Join on | Access | Tested |
|---|---|---|---|---|
| **OpenSanctions maritime** | Sanctions, shadow fleet, detentions | IMO, MMSI | No key; CC BY-NC. **Filter on `sanction` or `mare.shadow`**, because 36% of rows are detentions | Orchestrator |
| **OFAC SDN** | US sanctions | IMO in remarks | No key | Agent |
| **Paris and Tokyo MoU** | Port-state detentions | IMO | Public search | Agent |
| **IOTC lists** | Fishing authorisation, illegal-fishing list | IMO, name | Public; bulk file dated Feb 2025 | Agent |
| **ITU ship station register** | MMSI and flag check | MMSI | Public search | Docs |
| **Equasis, IMO GISIS** | Name, flag and owner history | IMO | Free account; no bulk | Agent saw login wall |
| **Marine Regions** | EEZs, territorial seas | Location | No key | Agent |
| **EMODnet Human Activities** | Pipelines, wind farms, cables, oil and gas | Location | No key; lat,lon order in WFS 2.0 | Agent |
| **Protected Planet** | Marine protected areas | Location | Token needed | Agent |
| **GPSJam** | GPS interference | Location, day | No key; daily; about 1 day old; follows aircraft | Agent |
| **Open-Meteo Marine** | Waves, including past dates | Location, time | No key | Agent |
| **IMF PortWatch** | Daily transits and capacity at 28 chokepoints | Chokepoint, day | No key; 6 days old; updated weekly | Orchestrator, agent |
| **FRED Brent** | Oil price | Day | No key CSV; about 4 days old | Agent |
| **EMODnet vessel density** | Monthly ship density at 1 km, EU waters; useful as a normal-traffic prior; Hormuz blank | Location, month | No key; CC BY 4.0 | Agent |
| **Zenodo LNG-T3** | LNG tanker voyages and terminal throughput 2020 to 2024, includes Gulf terminals | Vessel, terminal, day | No key; CC BY 4.0; historical only | Docs, agent |

## Coverage by region

| Region | Live AIS | Delayed AIS | Own radar check | Summary |
|---|---|---|---|---|
| Danish straits | AISStream | Danish archive, GFW | Yes, about 5 a week | Best test bench |
| Gulf of Finland | Digitraffic, AISStream | GFW | Yes, about 5 a week; no GFW radar | Best live AIS |
| North Sea, Channel | AISStream | GFW | Yes, about 3.5 a week in the Channel | Good; not yet studied |
| Hormuz | None free | GFW | About 3 a week | Study, days old |
| Red Sea | None free | GFW | Under 1 to about 2 a week, depending on the point | Study |
| Malacca | Near Singapore | GFW | About 1 a week | Sparse |
| Natuna, Java Sea | Patchy or none | GFW | Natuna under 1 a week | Study only |
| Open ocean | None free | GFW | Mostly none | Out of scope |

## Still to test

- Pelyr's real Gulf coverage (needs a free key).
- Whether Global Fishing Watch's per-vessel positions return.
- Equasis for checking a sample of identity changes (needs a free account).

See `marinetraffic/SYNTHESIS.md` for why MarineTraffic itself isn't a data source for us.
