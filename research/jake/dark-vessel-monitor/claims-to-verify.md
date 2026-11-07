# Claims to verify

Every factual claim the Dark Vessel Monitor plan relies on. Researched with Claude on 7 Nov 2026 from web sources; none of it has been independently checked yet.

**How to use this:** open the source, confirm the claim, and set Status to `confirmed`, `wrong: <correct value>` or `unverifiable`. Add your handle in Checked by. If a source is secondary (news summary, aggregator, scraper listing), try to find the primary source and add it.

Priority: **P1** = the build or demo breaks if this is wrong. **P2** = a number we'd say to judges. **P3** = background.

## 1. Data access and limits (P1)

| # | Claim | Source | Status | Checked by |
| --- | --- | --- | --- | --- |
| 1.1 | AISStream is free, sign-up via GitHub, endpoint `wss://stream.aisstream.io/v0/stream`, subscription JSON must be sent within 3 s of connecting | [AISStream docs](https://aisstream.io/documentation) | | |
| 1.2 | AISStream allows 3 connections per account and 3 per IP (counted before auth); browser connections are not permitted, so a backend relay is required | [AISStream docs](https://aisstream.io/documentation) | | |
| 1.3 | Subscription updates limited to 1 per second per connection; slow readers have messages dropped; no replay | [AISStream docs](https://aisstream.io/documentation) | | |
| 1.4 | Uncompressed connections bandwidth-limited since Sept 2026; `permessage-deflate` should be enabled | [AISStream docs](https://aisstream.io/documentation) | | |
| 1.5 | AISStream had a silent stream (connects, zero messages) from 5 Aug 2026, an expired SSL cert on 11 Aug, sign-up timeouts, a team IP rate-limited (HTTP 429) for days (#287), and Google Cloud IPs closed ~700 ms after subscribing (#285) | [AISStream issue tracker](https://github.com/aisstream/issues/issues) | | |
| 1.6 | AISStream mentions no satellite AIS feed (terrestrial receivers only) | [AISStream docs](https://aisstream.io/documentation) | | |
| 1.7 | Digitraffic (Finland) gives free live vessel locations and metadata over MQTT-over-WebSocket, topics `vessels-v2/+/location` and `vessels-v2/+/metadata`, CC BY 4.0, no key | [Digitraffic marine](https://digitraffic.fi/en/marine-traffic) | | |
| 1.8 | Digitraffic throttles clients without a `Digitraffic-User` header (429s) | [Digitraffic news, Dec 2024](https://www.digitraffic.fi/en/news/2024/12/03/api-throttles-turned-on-en.html) | | |
| 1.9 | Finland's network tracks well over 18,000 vessels at a time across the Gulfs of Finland and Bothnia | [Apify scraper listing](https://apify.com/parseforge/finland-digitraffic-marine-ais-scraper.md) (secondary; find a primary) | | |
| 1.10 | Kystverket (Norway) raw NMEA AIS over TCP at `153.44.253.27:5631`, no registration | [Kystverket](https://www.kystverket.no/en/sea-transport-and-ports/ais/access-to-ais-data/), [pyais docs](https://pyais.readthedocs.io/en/stable/_sources/examples.rst.txt) | | |
| 1.11 | Danish Maritime Authority publishes free daily historical AIS CSVs, roughly 0.5 to 2.6 GB per day | [DMA AIS data](https://www.dma.dk/safety-at-sea/navigational-information/ais-data) | | |
| 1.12 | OpenSanctions maritime CSV (~4.9 MB) has `imo`, `mmsi`, `flag`, `risk`, `datasets`, `aliases`; daily updates; CC BY-NC 4.0 | [OpenSanctions maritime](https://www.opensanctions.org/datasets/maritime/) | | |
| 1.13 | Global Fishing Watch API tokens are issued instantly on registration; free for non-commercial use | [GFW API key concepts](https://globalfishingwatch.org/our-apis/documentation/docs/v3/general-api-doc/key-concepts) | | |
| 1.14 | GFW SAR (Sentinel-1) vessel detections, matched/unmatched to AIS, run from 2017 to about 5 days ago; PNG map tiles available | [GFW 4Wings API](https://globalfishingwatch.org/our-apis/documentation/docs/v3/4wings) | | |
| 1.15 | GFW vessel presence dataset covers 2012 to about 4 days ago | [GFW API key concepts](https://globalfishingwatch.org/our-apis/documentation/docs/v3/general-api-doc/key-concepts) | | |
| 1.16 | GFW only calls a gap intentional if it lasts 12 h or more, starts at least 50 nm from shore, and starts in an area of good reception | [gfwr release notes](https://globalfishingwatch.r-universe.dev/gfwr/NEWS.txt), [GFW gaps docs](https://globalfishingwatch.github.io/GFW_technical_documentation/files/gaps.html) | | |
| 1.17 | OpenFreeMap dark style at `https://tiles.openfreemap.org/styles/dark` needs no key and has no request limits | [OpenFreeMap](https://openfreemap.org) | | |
| 1.18 | CARTO basemaps now need a free key; non-commercial free up to 5 million tile requests a month | [CARTO basemaps FAQ](https://docs.carto.com/faqs/carto-basemaps) | | |
| 1.19 | MapLibre GL JS v5+ supports globe projection via `map.setProjection({type: 'globe'})`; deck.gl `MapboxOverlay` with `interleaved: true` works with MapLibre's globe | [MapLibre globe example](https://maplibre.org/maplibre-gl-js/docs/examples/display-a-globe-with-an-atmosphere/), [deck.gl Mapbox/MapLibre](https://deck.gl/docs/api-reference/mapbox/overview) | | |
| 1.20 | EIA publishes weekly crude imports/exports through a free API | [EIA Weekly Petroleum Status Report](https://www.eia.gov/petroleum/supply/weekly/) | | |

## 2. AIS behaviour our detector depends on (P1)

| # | Claim | Source | Status | Checked by |
| --- | --- | --- | --- | --- |
| 2.1 | Class A reports every 2 to 10 s underway and every 3 min at anchor; Class B every 30 s or 3 min | [US Coast Guard NAVCEN](https://www.navcen.uscg.gov/node/84) | | |
| 2.2 | Static data (incl. IMO number) is sent every 6 minutes; Class B never sends IMO | NAVCEN / ITU-R M.1371 (find exact source) | | |
| 2.3 | AISStream's position `Timestamp` field is only the second within the minute (0 to 59) | [AISStream docs](https://aisstream.io/documentation) | | |
| 2.4 | The first three digits of an MMSI (MID) identify the flag state | ITU MID table (add link) | | |
| 2.5 | AIS is required on ships of 300 gross tonnes and above on international voyages | [AISStream overview](https://aisstream.io) (secondary; SOLAS Ch. V Reg. 19 is primary) | | |
| 2.6 | Shore-based AIS fades quickly once ships move into open ocean | [AXSMarine](https://public.axsmarine.com/blog/ais-for-shipping) | | |

## 3. Baltic context (P2)

| # | Claim | Source | Status | Checked by |
| --- | --- | --- | --- | --- |
| 3.1 | Around half of shadow-fleet oil exports pass through the Baltic | [CEPA](https://cepa.org/article/choking-russias-shadow-fleet-in-the-baltic/) | | |
| 3.2 | In April 2026, 30 to 40 shadow-fleet tankers were idling near Russian waters and in the international strip between Finland and Estonia | [Moscow Times, 14 Apr 2026](https://www.themoscowtimes.com/2026/04/14/idling-shadow-fleet-tankers-threaten-baltic-security-and-environment-experts-warn-a92498) | | |
| 3.3 | The EU's shadow-fleet list passed 670 vessels in its 21st sanctions package on 23 July 2026 | [Grosswald tracker](https://www.grosswald.org/baltic-sea-security-tracker/) (secondary; check EU Official Journal) | | |
| 3.4 | Finland's Coast Guard has reported constant GNSS interference in the Baltic and tankers spoofing positions | [MarineLink](https://marinelink.com/news/finland-coast-guard-detects-satnav-518723?cid=87) | | |
| 3.5 | An LPG tanker bound for Ust-Luga drew circular AIS patterns for ~10 days in the Gulf of Finland while loading in port | [Hellenic Shipping News](https://www.hellenicshippingnews.com/?p=1110298) | | |
| 3.6 | In Jan 2026 tankers loaded with Venezuelan state oil tried to leave Venezuelan waters with AIS off | [OpenSanctions entity](https://www.opensanctions.org/entities/NK-bcokCDJNYi7ztnQjV7Az3W) | | |

## 4. South-east Asia fishing (P2, extension only)

| # | Claim | Source | Status | Checked by |
| --- | --- | --- | --- | --- |
| 4.1 | A 2024 Nature study led by GFW found ~75% of industrial fishing vessels are not publicly tracked, and 7 in 10 fishing vessels found were in Asia | [GFW](https://globalfishingwatch.org/?p=39532) | | |
| 4.2 | In the Natuna Sea, satellite images showed at least 15 non-AIS vessels around one AIS signal from a Vietnamese vessel, apparently pair trawling | [GFW](https://globalfishingwatch.org/?p=10233) | | |
| 4.3 | More than 85% of fishing vessels in the VIIRS database do not broadcast AIS or publicly shared VMS | [GFW](https://globalfishingwatch.org/?p=7776) | | |
| 4.4 | VIIRS boat detection is published nightly as CSV, latency roughly 4 h | [EOG VIIRS boat detection](https://eogdata.mines.edu/products/vbd/) | | |
| 4.5 | Indonesia shares its VMS publicly through GFW | GFW (add link) | | |

## 5. Hormuz and energy markets (P2, extension only)

| # | Claim | Source | Status | Checked by |
| --- | --- | --- | --- | --- |
| 5.1 | About 20 million b/d (~one-fifth of world oil consumption, over a quarter of seaborne oil trade) passed through Hormuz in 2024 and early 2025 | [EIA](https://eia.gov/todayinenergy/detail.php?embed=true&id=65504) | | |
| 5.2 | A conflict began on 28 Feb 2026 and Hormuz transits fell 97% in March | [Windward Q1 2026 report](https://windward.ai/knowledge-base/q1-2026-maritime-risk-report/) | | |
| 5.3 | Shipping was roughly 70% below pre-conflict levels in the week to 30 Oct 2026 (tracker citing UKMTO) | [Hormuz briefing, 2 Nov](https://political.org/strait-of-hormuz-archive/iran-briefing-2026-11-02/) (secondary; find UKMTO primary) | | |
| 5.4 | In Aug 2026, 61.2% of logged Hormuz transits were false, created by GPS jamming | [Windward](https://windward.ai/knowledge-base/gps-jamming-and-false-transits-in-the-strait-of-hormuz/) | | |
| 5.5 | 42 Iranian-oil ship-to-ship transfers documented off Malaysia (EOPL) since 28 Feb | [Manila Bulletin, 14 May 2026](https://mb.com.ph/2026/05/14/malaysia-says-iranian-oil-transfers-near-its-waters-exploit-a-maritime-loophole) | | |
| 5.6 | Houthi blockade on Saudi Arabia declared on 20 July 2026 | [Reuters via Chronicle.lu](https://chronicle.lu/category/international/62944-hormuz-traffic-slows-as-uncertainty-over-waterway-persists) (secondary; find Reuters primary) | | |
| 5.7 | AIS-derived oil movements help predict oil prices, but added explanatory power is marginal | [NHH thesis](https://openaccess.nhh.no/nhh-xmlui/handle/11250/2560514) | | |

## 6. Competitors (P2)

| # | Claim | Source | Status | Checked by |
| --- | --- | --- | --- | --- |
| 6.1 | Palantir Gotham (government) and Foundry (commercial) share one data model, are deployed by Apollo and run AIP | [B.D. Emerson](https://www.bdemerson.com/article/palantir-gotham) (secondary; check palantir.com) | | |
| 6.2 | Palantir's own Gotham demo flags a warship going dark and projects its routes | [summary of Palantir video](https://lilys.ai/en/notes/palantir-20260127/palantir-gotham-defense) (secondary; find the video) | | |
| 6.3 | Saildrone and Palantir partnered on maritime intelligence (Mar 2025) | [Naval News](https://www.navalnews.com/naval-news/2025/03/saildrone-and-palantir-announce-strategic-partnership-to-advance-ai-powered-maritime-intelligence/) | | |
| 6.4 | Windward customers include BP, Shell and HSBC | [City AM](https://www.cityam.com/?p=1811280), [Windward](https://windward.ai/?p=36099) | | |
| 6.5 | Skylight (Ai2) is free for qualifying users, used by 300+ organisations in ~70 countries, does SAR and night-light dark-vessel detection | [GeekWire](https://www.geekwire.com/2026/ai2s-skylight-project-launches-shippy-an-ai-agent-that-dives-into-ocean-data/) | | |
| 6.6 | Kayrros sells off-the-radar (AIS-off) vessel detection to traders; Kpler and Vortexa sell tanker-flow data | [Kayrros](https://www.kayrros.com/products/off-the-radar-detection-for-traders/) | | |
| 6.7 | Competitors we may have missed (Spire, MarineTraffic, exactEarth, Pole Star, Lloyd's List Intelligence, HawkEye 360, Unseenlabs?) | none yet | | |

## Open questions (need a live test or a decision)

1. Does AISStream actually stream Baltic data right now, and what is the message rate for the Baltic box? (First-hour check.)
2. Does AISStream's `MetaData` carry a full UTC time, or only the second-of-minute `Timestamp`?
3. Does OpenSanctions entity JSON include designation dates? If yes, we can test whether we flag ships before they were sanctioned.
4. How many OpenSanctions-listed vessels are in the Baltic on a typical day of DMA data? If fewer than ~20, is the forecast evaluation meaningful?
5. Is the 30-minute gap floor and ~20 km neighbour radius sensible? Tune on DMA data.
6. Does GFW's non-commercial licence allow use in a hackathon demo shown to commercial sponsors? Same question for OpenSanctions CC BY-NC.
7. Is AISStream coverage in the Gulf usable at all (Hormuz extension)?
8. Can a 6-hour "go dark" forecast be trained from a few days of DMA data, or should we fall back to a "likely shadow fleet" classifier, as the research doc suggests?

## Known inconsistency to resolve

The pitch plan describes the forecast as P(go dark in next 6 h). The API research doc describes the prediction as P(vessel is shadow fleet) from behaviour, with sanctions labels as positives. These are different targets. The team should pick one before hour 6.
