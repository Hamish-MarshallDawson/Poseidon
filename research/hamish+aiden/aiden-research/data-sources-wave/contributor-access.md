# Contributor access: can feeding a station earn us better ship data?

Research agent for Aiden, 7 Nov 2026, 20:41–20:45 UTC (real clock). Public pages and search only. Nothing was signed up for, applied to or emailed. Labels: `documented` (page read 7 Nov 2026 unless noted), `vendor claim`, `press`, `unverified`, `derived` (our own arithmetic).

## Bottom line
1. **No contributor programme gets us Hormuz or Gulf data.** Each one gives contributors map or account perks on the same pooled network. That network is thin in the Gulf for the reasons `mt-rivals.md` sets out. An Edinburgh receiver adds coverage of the Firth of Forth and nothing else.
2. **The one route worth taking needs no radio: apply for Pelyr Community as a research, education or open-source project.** It's free, a person reviews each request, and it gives 500 vessels by MMSI with an unlimited stream area, raw NMEA over TCP, and satellite vessel detections with ship-to-ship finds through the API. Commercial use needs a separate agreement. `documented`, pelyr.com/pricing and dashboard.pelyr.com/en/docs/api. *(Orchestrator correction: this report first said Community has no raw NMEA. The pricing table's columns run Free, Fleet, Community, Horizon, Global, Enterprise, and raw NMEA is listed for Community and Enterprise. The API docs say vessel detection is part of paid plans from Fleet up and of Community access; the Free plan gets `403 detection_not_in_plan`.)* Whether it covers the Gulf is still unknown.
3. **Station perks are UI-only, or they bar passing data on.** VesselFinder gives a free Premium account with no API or export listed. ShipXplorer gives a Business membership. MarineTraffic gave premium plans to stations in 2014 (`press`). AISHub gives an API, but you may not pass raw data on. None of these lets us republish a feed.
4. **Every no-hardware route that works by forwarding someone else's data is ruled out.** AISHub says so explicitly: "Synthesized, scraped, stolen, or data from public AIS services is not accepted" (`documented`, aishub.net/join-us). We found no "contribute compute or software for data" programme anywhere.
5. **A £30–60 dongle can't be approved by 09:00 Sunday.** It needs delivery, setup, review, and a 7-day uptime average for AISHub. It's worth doing only after the hackathon, as a lesson, or to show a live Forth layer in the demo using our own decoded data, which needs no one's approval.

## Comparison

| Service | What contributors get | Requirements | Time to access | Licence fit for our platform | No-hardware route? |
|---|---|---|---|---|---|
| **Pelyr** | Station operators *qualify* for Community. It isn't granted automatically. Community: 500 MMSI, unlimited area and boxes, 5 streams, 10 req/min, 10 alert zones, 7-day tracks, SAR imagery viewing, raw NMEA over TCP, satellite vessel detections and ship-to-ship finds. No SLA | Station registered in the dashboard; "New stations are reviewed before they can send data"; forward the full live feed via AIS-catcher, docker-shipfeeder or UDP (`documented`, pelyr.com/network/) | Not stated; a person reviews each request; granted for up to 12 months and can be withdrawn | Free plan is non-commercial with attribution. Community allows commercial use only under a project agreement. Licence 2.0: you may store, analyse and display, but not redistribute or extract in bulk (`documented`) | **Yes**: researchers, educators, non-profits and open-source projects qualify without a station |
| **AISHub** | All members: map and station stats. "Good station": API key for combined data, 1 req/min | Your own raw NMEA feed; 10+ vessels and 90% uptime (7-day averages); ≤60 s downsampling; ≤10 s delay; station location made public | Not stated; effectively ≥7 days to hit the averages (`derived`) | Commercial use allowed with credit "Data: AISHub contributors"; no passing on raw data; not for navigation | **No**, explicitly |
| **VesselFinder** | Free Premium account, station stats, outage emails, an embeddable map | Application with position, equipment, contact; host and port given after approval; no stated minimums | After approval; time not stated | Terms of Use apply; no API or export listed; `d-ais` notes a ban on building datasets | No |
| **MarineTraffic / Kpler** | Historically free Pro or Premium "depending on performance" (`press`, Panbo 2014); a free Comar receiver for good locations (`documented`, apply-for-free-ais-receiver page via search) | Apply through the "Become a Station Owner" button; a location can be refused if the area is already covered (`unverified`, user report) | Not stated | Terms bar derived data and publishing (already known) | No |
| **ShipXplorer** | "Become Business member" (tier and term not specified); free receiver by application | Within 5 km of a major port or route, clear sea view, online 24/7, start sharing within 7 days of delivery, return the kit if you stop (`documented`, shipxplorer.com/addcoverage) | Not stated; the application page showed a server error | UI or CSV only; no API | No |
| **MyShipTracking** | Not readable (403) | TCP/UDP feed (`documented` earlier in mt-rivals) | Unknown | API is paid | No |
| **AIS-catcher community** | Your ships appear on the community map, coverage and station pages. The local web viewer with export is part of the free software, so it isn't a reward | RTL-SDR (~€30) or dAISy, a high antenna, a sharing key from registration | Immediate once registered (`vendor claim`) | Map only; blocks automated clients (mt-rivals) | No |
| **aprs.fi** | No AIS contributor programme found. The API returns AIS targets to any account | Free account and key | Immediate | Attribution; app must be free to use; no archival harvesting or bulk copying; query only when a user actively needs the data (`documented`, aprs.fi/page/api) | Yes, but coverage is ham/AIS feeders and its Gulf coverage is unknown |
| **Global Fishing Watch** | No contributor programme. Access is by self-registration | Account; represent an organisation supporting sustainable ocean use | Self-service, minutes; some APIs need approval (`documented`) | CC BY-NC 4.0; tokens must not be put in a public web UI; 50k req/day; no elevated tier stated | Already in use |
| **AISStream** | No contributor programme found; upstream sources unnamed; no SLA | Not applicable | Not applicable | Terms not on its docs page (`unverified`) | Not applicable |

## The Edinburgh answer
- **Without radio equipment:** there is no honest contributor route, because every programme requires a receiver you run yourself. The only no-hardware routes are *access* routes rather than contributor ones: Pelyr Community (apply as a hackathon or open-source research project), aprs.fi's keyed API, and GFW, which we already use. Any route that forwards someone else's receiver or a public service as "our station" is ruled out, and AISHub forbids it in writing.
- **With an RTL-SDR and a VHF antenna:** AIS is line-of-sight. The radio horizon is d(km) ≈ 4.12 × (√h_rx + √h_ship) (`derived`, standard formula). Take a ship's antenna at about 20 m:
  - Window at about 10 m: roughly 31 km in theory.
  - Rooftop at about 30 m: roughly 41 km.
  - Buildings and hills cut this sharply, and a window that doesn't face the Forth may hear very little (`unverified`).
  - Leith (~3 km) and Rosyth or the Forth bridges (~15 km) are realistic. Grangemouth (~30 km, upriver) is marginal. The outer Forth anchorage could be possible from a high site with a clear view.

  Expect tens of vessels: tankers, ferries, tugs and fishing boats (`unverified` count). That would probably meet AISHub's 10-vessel minimum. It **does nothing for Hormuz or the Gulf of Finland**. It might earn Pelyr Community or an AISHub key, but we can get the first without a station, and the second doesn't add Gulf data.
- **Before 09:00 Sunday:** no. There's no shop delivery overnight on a Saturday (`unverified`). Pelyr reviews new stations first, AISHub needs a 7-day average, and VesselFinder and MarineTraffic approve by hand.

## Recommendation
- **Now (only with Aiden's go-ahead, since it's an application):** send one short Pelyr Community request describing the project as open-source hackathon research. Then test a Hormuz box. Treat it as a bonus if it arrives before the freeze. Don't plan the demo around it.
- **For the demo:** don't build any contributor route into the plan. Present "a volunteer receiver could add live local truth" as future work.
- **After the hackathon:** a £30 dongle on an Edinburgh rooftop is a cheap way to learn the AIS pipeline. It earns AISHub's API with commercial use and credit allowed, and a Pelyr station listing. It's worth doing only if the project continues.

## Unknowns
- Pelyr's approval time and whether it covers the Gulf.
- What MarineTraffic or Kpler currently give stations, since the official pages returned 403 or 404.
- ShipXplorer's Business term and whether it includes an API.
- MyShipTracking contributor perks (403).
- AISStream's sources and terms.
- The real vessel count from an Edinburgh window.

## Sources (read 7 Nov 2026)
pelyr.com/pricing; pelyr.com/network/; stations.vesselfinder.com/become-partner; aishub.net/join-us; shipxplorer.com/sharing-data, /addcoverage; support.marinetraffic.com/en/articles/13641805; marinetraffic.com/p/apply-for-free-ais-receiver (search snippet); panbo.com/the-new-marinetraffic-internet-ais-service-cautiously-optimistic/ (2014, press); aiscatcher.org; aprs.fi/page/api; api-doc.globalfishingwatch.org/our-apis/documentation/docs/license-rate-limits; aisstream.io/documentation. These returned 403: marinetraffic.com/en/p/expand-coverage, myshiptracking.com help centre.
