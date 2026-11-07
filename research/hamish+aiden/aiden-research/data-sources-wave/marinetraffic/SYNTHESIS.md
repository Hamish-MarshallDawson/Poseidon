# MarineTraffic wave: synthesis

Saturday 7 November 2026, about 18:30 UTC. Seven DeepSeek agents working from public material only. Evidence, not a project decision. "Checked" means the orchestrator confirmed it against the source; everything else is the agents' finding. Some report timestamps run later than the actual clock, so treat their times as approximate.

## Answer

**MarineTraffic's Gulf density can't be reproduced from any free source we found, and no hidden public feed explains it.** Its value comes from a large receiver network plus owned satellite data. For the project, its methods are more useful than its data.

## Where its data comes from

| Layer | Meaning | Evidence |
|---|---|---|
| **Terrestrial** | "Picked up by a land-based AIS receiver" | Checked, MarineTraffic support. Stations are "managed and maintained by our dedicated partners" per agent |
| **Roaming** | "Received via a shared network of AIS receivers" | Checked, MarineTraffic support |
| **Satellite** | "Captured by a satellite AIS receiver" | Checked |

- **Scale:** Kpler claims 6,600+ receivers for MarineTraffic and 13,000+ for Kpler AIS (vendor claims, agent).
- **Satellite ownership:** ORBCOMM supplied it from 2013. Kpler bought Spire Maritime, closing in April 2025. S&P Global bought ORBCOMM's AIS business (agent, press).
- **Unknown:** no published split between volunteers, partners, governments and satellites. Any finer breakdown is unverified.
- **Gulf positions:** no agent could establish which layer supplies them. Aiden's manual look at the map shows coverage there.

## Free or cheap routes tested

| Route | Result | Status |
|---|---|---|
| **Government or port feeds, Gulf to South-East Asia** | None usable. Five candidates fail on tokens, keys or commercial front-ends | Agent |
| **CetaHAV** | AISStream-based Baltic sampler: about 55 ships per 12.6 s call, no timestamps, 6.9% of positions over 1 h old. Hormuz zero | Agent, two independently |
| **AIS-catcher community map** | Claims 1,313 stations; blocks automated clients and requires human confirmation. Not used | Agent; boundary respected |
| **AIS Trail** | Key-gated; 9-station volunteer network | Agent |
| **EMODnet density** | CC BY 4.0, 1 km monthly grids, EU waters; Hormuz blank | Agent |
| **Sweden's Sjöfartsverket** | Paid live stream and history from 2006 | Agent |
| **Zenodo LNG-T3** | CC BY 4.0 LNG tanker voyages 2020 to 2024, includes Gulf terminals. Historical only | Agent |
| **Pelyr free plan** | Free account, non-commercial: reportedly 50 ships by MMSI, 3-day history, satellite detections. Named AIS sources are Finnish and Norwegian, plus own stations and unnamed permitted feeds. **Gulf coverage unknown** | Sources page checked; plan terms agent only; needs a key to test |

## Contributing a receiver

- **AISHub is the only network that pays in data:** the combined feed once a minute, usable in commercial products with credit. Requires a station with at least 10 vessels, 90% uptime, up to 60 s downsampling and up to 10 s delay, on a 7-day average (checked). Raw data can't be passed on.
- **It can't help this weekend.** AISHub needs a week of statistics. MarineTraffic tiers need up to three months of uptime statistics (agent).
- **Hardware is about £50 to £250,** and AIS-catcher is open source (agent).
- **An Edinburgh receiver hears the Forth, not Hormuz.** Network access is the only route to Gulf data.
- **Volunteer Gulf coverage is thin:** 4 UAE stations in AISHub's directory (agent). VesselFinder lists one UAE station with 555 ships (agent).

## Paying

- **No published API price.** API access is sales-led (agent). Self-serve consumer plans are capped at 5, 300 and 10,000 exported rows a month (agent, documented October 2026).
- **Kpler's terms rule out using it as a data layer.** They bar creating derived data and publishing or mirroring the Data (checked). That rules out modelling or public display without written agreement.
- **Narrow use:** a private manual spot-check of a named ship. A 7-day trial exists but auto-charges (agent). Keep it out of the demo.
- **Other prices:** VesselFinder's API starts at €175 for 5,000 credits and is shore-only; its satellite product is a separate $139 a month (agent). This replaces the "€9/yr" figure in `d-ais`.

## Methods worth borrowing

- **Provenance on every position:** source class, source and receive time.
- **Silence as states, not one flag:** published thresholds are out of range after 1 h on terrestrial, 3 h on the global channel, compliance-grade gaps over 20 h with coverage at start or end (agent, documented). Our shorter gaps need their own labels.
- **Raw and cleaned layers:** spoofed positions stay in raw data and are excluded from analytics once confirmed.
- **Simple spoof test:** predict the next position, compare, flag and escalate. Cheap versions: impossible speed, inland clusters, one MMSI in two places, checked against GPSJam.
- **Dark claims confirmed with imagery:** "Dark STS" and "dark port call" are verified using satellite imagery. That supports AIS-plus-radar and the careful wording.
- **Thinned feeds:** Kpler downsamples terrestrial messages within 5-minute periods by MMSI and message type (checked). Its display is also thinned, so raw high-rate feeds remain more useful for silence analysis.
- **Stale ships drop off the map after 24 h,** and tracks aren't interpolated across gaps.

## What this changes

1. Don't plan a free live Gulf feed. Use Global Fishing Watch, labelled as days old, or decide separately to buy something.
2. Treat MarineTraffic as a manual cross-check at most, with no scraping and no demo use.
3. Add source class and coverage basis to the data, if the team agrees.
4. AISHub is a good next-step option after the hackathon.
5. Pelyr is the one free test left. It may also be the nearest competitor, since it offers satellite detections and ship-to-ship finds.

## Unknowns

- MarineTraffic's supplier breakdown and which layer feeds the Gulf.
- Pelyr's real Gulf coverage.
- Current MarineTraffic plan prices: its marketing site returned 403 to agents, and they didn't work around it.
- Whether its free view shows position age and fields. Aiden's manual check can settle this.
