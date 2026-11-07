# mt-receivers: getting AIS by contributing a receiver

*Track mt-receivers, MarineTraffic wave, Sat 7 Nov 2026, 18:17–19:10 UTC. No accounts created, no forms submitted, no payments, no logins. Labels: `measured` = I ran it; `documented` = primary source page; `vendor claim` = operator's own words; `unverified` = seen only in a search listing or inferred.*

Scratch `$WAVE=/tmp/claude-1000/-home-aiden-Projects-Personal-Hedged-Bets-hacktheburgh/703a82eb-0773-4b07-b85c-af65197add0d/scratchpad/wave`. Scripts `$WAVE/scripts/mt-receivers/` (`aishub_stations.py` fetches, `aishub_parse.py` parses cache); output `$WAVE/data/mt-receivers/aishub_stations.json`.

## 1. Bottom line

1. **Three networks pay contributors in product access; one pays in data.** MarineTraffic/Kpler and VesselFinder give a better web account; ShipXplorer gives a free Business account (list $399.50/yr); **AISHub is the only reward that is the dataset itself** — the whole network's latest positions, JSON/XML/CSV, once a minute, with IMO, dimensions, draught, destination and ETA, and commercial use allowed with credit. `documented`
2. **Nothing here starts inside a hackathon.** MarineTraffic's tiers need **>40% (Essential) or >85% (Enterprise) station availability over the past three months**; AISHub needs a **7-day average** of ≥10 vessels, ≥90% uptime, ≤10 s delay; ShipXplorer quotes ~3 days to decide plus **7–14 business days** shipping. Days-to-weeks, not hours. `documented`
3. **An Edinburgh receiver hears the Forth, never Hormuz.** AIS is VHF line-of-sight: 20–40 nm typical ship-to-shore, ≈26 nm for a 20 m ship antenna against a 50 m shore site. Edinburgh–Hormuz is ~3,000 nm. A Forth station reaches Gulf data only by **barter**, and MarineTraffic's barter wording is "volume roughly equal to what you send", not a guaranteed area. `documented`
4. **Even AISHub's whole volunteer network is thin exactly where we need it.** Its public station directory (measured 18:38–18:52Z 7 Nov 2026) yields **1,459 unique station IDs across 83 countries**; in the Gulf, **4 stations, all UAE**, plus **5 in Israel** — zero in Oman, Qatar, Saudi Arabia, Kuwait, Bahrain, Iraq, Iran, Yemen, Egypt. `measured`
5. **Software is free and open; hardware is ~£50–£250.** AIS-catcher (GPLv3) runs an RTL-SDR dongle and can feed several aggregators at once, so contributing is not exclusive. For `t-feeds`: **aiscatcher.org runs a free, no-paywall community map** (1,313 stations online, 105,989 ships/24 h, 276.3 M messages/24 h at 18:25Z) — a candidate source, not just a place to contribute. `measured`

## 2. Findings

### 2.1 What MarineTraffic gives partners (two different things)

- **Product plans, automatic.** "All users who contribute… are rewarded with plans… Essential Plan and a fleet of 50… at least one Station with > 40% availability during the past three months… Enterprise Plan… > 85%" (My Account > My Online Services). `documented` (support.marinetraffic.com/en/articles/9552976)
- **Timing conflict.** A second article says the account is "automatically upgraded **within 48 hours**" (…/9639818). Both are current; likely a base upgrade in 48 h, named tiers after 3 months of availability. One support email would settle it. `unverified`
- **Raw data, by barter.** "We can share more data with you from certain areas or vessels of your choice… The volume… has to be **roughly equal** to what you send… We can also **bounce back** your data to an IP/Port combination that you choose." NMEA 0183 `!AIVDM`/`!AIVDO` over TCP or UDP to your public IP and port (…/9552990) — exactly the shape we would want, but discretionary, human-arranged, volume-matched and silent on latency, area guarantees and history.
- **It will supply hardware**: "if your area is not sufficiently covered… we will be pleased to provide you with a top-notch AIS receiver for free"; a nearby station is no bar ("either as a backup or to expand coverage"). `documented` (…/9553000)
- **Its public site is closed to us:** `marinetraffic.com/en/p/ais-receivers` and `/en/join-us` returned **403**; the Kpler-hosted support subdomain is readable. No attempt was made to work around it. `measured`
### 2.2 What each network gives a contributor

In one line each (full rows in §3): **AISHub** pays in data — the whole network's latest positions, one request a minute, commercially usable with credit, re-publishing raw data forbidden; **MarineTraffic/Kpler** pays in web plans plus the discretionary barter feed above, and will post you a receiver where coverage is wanted ("if your area is not sufficiently covered… free"; a nearby station is no bar, "either as a backup or to expand coverage"); **VesselFinder** grants "a VesselFinder Premium account free of charge" and nothing raw; **ShipXplorer** grants a free Business account (list $399.50/yr) and ships free receivers to feeders within 5 km of the coast with a 360° view; **aiscatcher.org** issues a sharing key and puts your station on a free, unfiltered map.

AISHub's field list is worth copying into our data model, because it is the richest free per-vessel record in this wave: MMSI, last-report time, lat/lon, COG, SOG, true heading, ROT, position accuracy, nav status, **IMO, name, call sign, ship-and-cargo type, A/B/C/D dimensions, draught, destination, ETA as entered by the crew**. Same shape as a MarineTraffic vessel card, minus port calls and history. `documented`

### 2.3 Hardware and software, with costs

Minimum station: a 162 MHz receiver, an antenna, an always-on host, power and internet. Three receiver routes — RTL-SDR decoded in software, a dedicated AIS receiver, or tapping the discriminator output of an existing VHF set (MarineTraffic documents the soldering). Antenna: any marine VHF antenna, 5/8 vertical preferred, as high as possible with a clear view of water; keep coax short and run longer ethernet instead. One dongle covers **one** AIS channel unless you buy a dual-channel receiver (e.g. dAISy-catcher). All `documented` (…/9553000).

Prices from search listings **not fetched directly**, so `unverified`: RTL-SDR Blog V4 **£42.99** (wai-works.com, listing dated 2026-02-17); dAISy **£65.99** (uputronics); AIS antenna **£154.95** (Metz); dedicated receiver **£204** (AMEC Cypho-150). Floor ≈**£50–£120** if you own a Pi; comfortable ≈£250+.

### 2.4 Would it work from Edinburgh, and what does it unlock?

Physics decides. AIS transmits on 161.975/162.025 MHz, VHF, line-of-sight, no relay at sea. Government of Canada: ship-to-shore range **20–40 nm** (37–74 km) depending on weather and topography, more from elevated sites; the usual approximation is `d(NM) ≈ 2.23 × (√h₁ + √h₂)` with heights in metres — a 50 m site against a 20 m ship gives ≈26 nm, 100 m gives ≈32 nm. `documented` (e-navigation.canada.ca; marineactivity.com, 2026-10). From Edinburgh that is the Forth, its approaches and a fan of the northern North Sea — not Hormuz, the Gulf of Oman, the Red Sea, Malacca, Natuna or Singapore.

**A Forth station would be a high-volume contributor, measured indirectly.** AISHub already lists two Edinburgh stations (3607, 6 ships / 0 distinct; 3070, 8 ships / 4 distinct), plus Dunfermline (0 ships, 18% uptime), Lochgelly and Carnoustie — small counts next to Cardiff (1,509 ships / 215 distinct), the Solent (137) or Southampton (126). That looks like low inland siting, not an absence of ships. `unverified` estimate: tens of vessels at any moment, hundreds a day.

**But the barter pool is the same network whose Gulf footprint I measured:** 4 UAE stations (Abu Dhabi 770 ships/635 distinct; "Persian Gulf" 125/26; Zayed Military City 47/2; Dubai 14/1) and 5 in Israel, nothing on the Iranian, Omani, Qatari, Saudi, Kuwaiti, Bahraini, Iraqi, Yemeni or Egyptian coasts. Volume-for-volume exchange can only return data from stations that exist. Southeast Asia is better but modest: Indonesia 13, Japan 25, Singapore 8, Malaysia 8, India 5, Philippines 4, Thailand 3, Hong Kong 7, none in Vietnam or Taiwan. `measured`

### 2.5 Barter arithmetic

Volume is driven by Class A under-way reporting (2–10 s) and distinct vessels heard, so one busy Forth station plausibly emits more NMEA lines per day than a handful of Gulf stations — favourable in bytes, in principle. But it sits behind three months of availability history, is decided by "certain areas or vessels of *your* choice" (their choice in practice), and nothing published promises a live Gulf feed. Wording `documented`; arithmetic `unverified`.

## 3. Source rows

| Source | Operator | Type | Regions covered | Access route | Account or cost | What one record contains | Update rate | Delay | Identifies the ship? | Licence, limits | Likely used by MarineTraffic? | Usable by us? | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| AISHub feed | volunteer cooperative | aggregated terrestrial AIS | global; **thin in the Gulf** (4 UAE, 5 Israel, 0 elsewhere there) | `data.aishub.net/ws.php`, JSON/XML/CSV, bbox+MMSI/IMO+max-age | must feed a receiver; free after | full voyage + static record (2.2 field list) | continuous upstream, **1 req/min** | unpublished; ≤10 s delay is a feeder rule | yes | commercial use with credit; no re-publishing raw | likely | yes — if we ever run a station, not tonight | `documented` + `measured` |
| AISHub station directory | same | coverage metadata | 1,459 unique IDs / 83 countries | `aishub.net/stations`, 50 rows/page | none | station ID, 7-day uptime, country, location, live ships, distinct-only count | snapshot | current | station, not ship | public page | – | yes, for honest coverage caveats | `measured` 18:38–18:52Z |
| MarineTraffic partner programme | MarineTraffic / Kpler | terrestrial + satellite AIS | global (vendor claim) | `marinetraffic.com/en/join-us/cover-your-area` (403 to us) | free receiver possible; reward = web plan | n/a — product access | – | – | – | 3-month availability tiers | is MarineTraffic | no, this weekend | `documented` |
| MarineTraffic partner raw feed | same | raw NMEA exchange | "certain areas or vessels of your choice" | TCP/UDP push to your IP:port, via support | active contributor status | `!AIVDM`/`!AIVDO` | streaming | not stated | yes | volume roughly equal; personal use | is MarineTraffic | months out | `documented` |
| VesselFinder | VesselFinder | terrestrial network | global (mt-rivals measured 1,494 stations, 100 countries, 115,096 vessels online) | `stations.vesselfinder.com` | free Premium web account | n/a — web | – | – | – | no raw data; API paid, forbids dataset building | likely | no | `documented` |
| ShipXplorer | ShipXplorer | terrestrial + satellite sources | global; 21,889 stations / 113 countries claimed | `/addcoverage` | free hardware possible; free Business account | n/a — web | – | – | – | ≤5 km from coast, 24/7 online | unlikely | no | `documented` |
| aiscatcher.org community | AIS-catcher project | volunteer terrestrial AIS, unfiltered | global, 1,313 stations online | public vessel and port pages; feed via sharing key | **viewing needs no account** | position, SOG/COG, destination, track; port arrivals | live | none claimed | yes | GPLv3; "no paywall, no delay, no filtering" | unlikely | **test it — handed to `t-feeds`** | `measured` (200 on plain GET, 18:31Z) |

## 4. What this means for us

- **Rule out for this weekend:** every receiver-contribution route. Fastest (ShipXplorer) is application plus shipping; AISHub needs a week of statistics; MarineTraffic three months. This changes nothing about Sunday's demo.
- **AISHub is the interesting next-time option.** One station buys the whole network's latest positions with IMO, dimensions, draught, destination and ETA, once a minute, commercially usable — a better fit than AISStream, whose position messages carry no IMO.
- **Do not treat "contribute and get Gulf data" as a plan.** The Gulf is the emptiest part of every volunteer network I could measure; Hormuz needs a commercial or satellite feed.
- **Borrow the coverage-directory method:** per-station ship counts and 7-day uptime make an honest caveat layer for our map ("we hear what these N stations hear"), better than an unexplained empty region.
- **Storage implication:** the snapshot semantics argue for *last-known-per-MMSI plus a separate position history*, the split `t-ais-live` found at Digitraffic. IMO, dimensions, draught, destination and ETA are self-reported and must be flagged, since the identity work turns on exactly that.

## 5. Unknowns

1. Which MarineTraffic timing rule governs — 48 hours or 3-month availability. One support email settles it; not asked, because it changes nothing before feature freeze.
2. Whether barter ever covers a region with no station — the crux of whether a Forth receiver could ever yield Hormuz data. Needs a written answer quoting the volume-matching sentence.
3. Latency, history and format of the bartered NMEA feed: unpublished.
4. AISHub's real Gulf content after joining: the directory shows 770/125/47/14 ships at 18:50Z, but without a key I cannot say how much of the strait those stations see.
5. Station counts are one snapshot; 289 IDs appeared on more than one page, so 1,459 unique IDs under-reports the stated 1,788 items. Read country totals as "at least this many", zeros as "no station declaring that country here".
6. Prices are listing snippets, not fetched pages; and whether AIS works from a specific Edinburgh building (height, sea view, RF noise) only a trial receiver answers.
7. aiscatcher.org's Gulf coverage: its layer is script-loaded, and `/stats` served a bot-check page to a direct request, which I did not attempt to bypass.

## 6. Sources

- `aishub.net/join-us`, `aishub.net/api` — feeder thresholds, credit and no-republish terms, API shape, field list, error strings.
- `aishub.net/stations` pages 1–36 (18:38–18:52Z) — the coverage measurement; `/stations/4126`, `/3966` — sample UAE pages.
- `support.marinetraffic.com/en/articles/9552976` (tiers), `…/9639818` (48-hour upgrade, cover-my-area), `…/9552990` (NMEA barter), `…/9553000` (antenna, cabling, free hardware), `…/9552998` (discriminator tap), `…/9552934` (shipped hardware).
- `stations.vesselfinder.com/become-partner`; `shipxplorer.com/faq`, `/blog/help-us-increase-coverage-and-get-a-free-business-account`, `/subscribe`, `/api` (feed conditions, 3-day decision + 7–14 business-day shipping, prices, API "under construction").
- `aiscatcher.org/`, `/quickstart`, `/stats`, `/stations` (counters, no-paywall claim, station key, bot check); `github.com/jvde-github/AIS-catcher` (GPLv3, supported SDRs, outputs, `-X` key).
- `e-navigation.canada.ca/TOPICS/traffic/docs/ais/works` — 20–40 nm AIS range (Government of Canada); `marineactivity.com/guides/ais-coverage-limits/` (2026-10-17) — range formula and worked examples.
