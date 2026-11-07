# Pitch Plan: Dark Vessel Monitor (working title)

Nov 7, 2026 · @Jake Callcut

*Exported from the Claude doc of the same name. The doc is the live version; this copy is for review.*

**A live map of the Baltic that spots ships hiding from tracking, forecasts which will go dark next, and ranks them for inspection.**

## The idea

Every large ship must broadcast its position. Sanctions-busting "shadow fleet" tankers switch their signal off or fake it, and the Baltic is one of their main routes.

- **Detect (live):** flag ships that go silent while ships around them are still heard, or that jump impossibly or circle while "anchored".
- **Forecast (next 6 hours):** a probability for every ship that it will go dark, learned from historical behaviour.
- **Decide (automated):** a ranked "inspect next" watchlist, refreshed every few minutes.

It hits both tracks: G-Research gets something genuinely hidden made visible; HRT gets streaming data, a real forecast and an automated decision, scored against baselines.

## Data

| Source | Used for |
| --- | --- |
| AISStream (live WebSocket) | Live ship positions and identities |
| Digitraffic, Finland (live MQTT) | Backup live feed for the Baltic |
| Danish Maritime Authority (historical AIS) | Training and backtesting the forecast |
| OpenSanctions (vessel list) | Which ships are sanctioned |
| Global Fishing Watch (satellite radar) | Overlay of ships seen by radar but silent on AIS (historical) |

## Tech

- **Backend:** Python (asyncio ingest), FastAPI WebSocket to the browser
- **Model:** Polars for features, LightGBM for the 6-hour forecast
- **Frontend:** React, MapLibre (map), deck.gl (ships, trails, rings), OpenFreeMap dark basemap
- **Safety net:** every message logged to disk, so the demo can replay if live feeds drop

## Interface

Full-screen black map of the Baltic in a thin-line style: white coastlines, grey ship trails, red for alerts. Floating glass panels over it: the watchlist, a vessel card when you click a ship, live feed stats, and a timeline for replay. Mockup to follow.

## Who does what

| Role | Owns |
| --- | --- |
| Data | Live feeds, failover, logging, sanctions join |
| Model | Gap and spoofing detection, forecast, backtest numbers |
| Frontend | Map, panels, animations |
| Pitch | Story, slides, documented cases, backup video |

## Milestones

1. **Hour 2:** live Baltic data flowing and logged
2. **Hour 8:** live map with ships, trails and dark-ship alerts
3. **Hour 14:** forecast trained and backtested
4. **Hour 18:** feature freeze
5. **Hour 22:** two timed rehearsals

## What we'll show to prove it

How many of our top 10 "likely to go dark" ships actually did, compared with simple baselines. Plus forecasts made early in the hackathon, checked against what happened by demo time.

## Top risks

Most risks are handled by fallbacks we build in the first six hours. The rest are limits of the data, which we name openly in the pitch.

| Risk | Why it matters | How we get around it |
| --- | --- | --- |
| Coverage gaps look like dark ships | A ship leaving receiver range looks the same as one switching off | Only flag a gap when ships nearby are still heard; map real coverage from our logged data; ignore areas with no receivers |
| Receiver outage or GPS jamming | Many ships vanish or jump at once, flooding us with false alerts | Watch message rates per map area: many ships at once means a receiver or jamming, one ship alone means behaviour |
| Live feed goes down or silent | AISStream had a multi-day outage in August 2026, with no error raised | 30-second watchdog switches to Digitraffic automatically; everything logged so we can replay |
| Shared venue internet address | AISStream allows only 3 connections per IP; other teams on the same Wi-Fi count | Run ingest on a phone hotspot; one connection only; reconnect with backoff so we never get blocked |
| Our own code falls behind | Messages we drop look exactly like ships going dark | Reading and processing run separately; we discard any gap that overlaps a stall on our side |
| Few real events in 24 hours | A quiet demo has nothing dramatic happen | Replay recorded and historical events; feature documented cases; also forecast spoofing, which is more common in the Gulf of Finland |
| Too few examples to train on | A model trained on a handful of sanctioned ships can fool itself | Test on ships it never saw; report sample sizes; always compare with simple baselines |
| Identity data is self-reported | Ships can broadcast false IDs, and IDs arrive only every 6 minutes | Show "identity pending"; treat mismatched IDs and flags as a warning sign, not an error |
| Demo machine or venue network fails | Live demos break at the worst moment | Laptop set never to sleep; offline map fallback; recorded backup video |
| Naming real ships | Calling a ship a sanctions-buster is a serious claim | Present it as a ranked list for human review, never an accusation; placeholder names in public material |

What we cannot fix, and will say so: we cannot prove intent, we only see ships near receivers, and the satellite radar layer is at least 5 days old.

## Beyond the Baltic: other applications

The same engine (find ships that hide, forecast where it happens next, rank what to act on) works anywhere a ship has a reason not to be seen. What changes from case to case is the mix of data.

| Application | What is hidden | Who would use it |
| --- | --- | --- |
| Illegal fishing in Southeast Asia | Foreign boats fishing without licences, transponders off | Fisheries ministries, coastguards, seafood buyers checking supply chains |
| Other sanctions regimes | Tankers carrying Iranian or Venezuelan oil in "dark mode" | Sanctions enforcers, insurers, banks |
| Subsea cable and pipeline protection | Ships loitering or dragging anchor over cables | Grid and telecoms operators, navies |
| Marine protected areas | Industrial vessels inside reserves | Park authorities, conservation groups |
| Commodity trading | Oil and cargo flows missing from official figures | Trading desks estimating real supply |
| Insurance and trade finance | Risky vessels and counterparties | Marine insurers, lenders |

The sanctions case is not hypothetical: in January 2026 a group of tankers loaded with Venezuelan state oil tried to leave Venezuelan waters with their AIS switched off ([OpenSanctions](https://www.opensanctions.org/entities/NK-bcokCDJNYi7ztnQjV7Az3W)).

### Deep dive: illegal fishing in Southeast Asia

This is the biggest prize. A 2024 Nature study led by Global Fishing Watch found about 75% of the world's industrial fishing vessels are not publicly tracked, and that for every 10 fishing vessels found, 7 were in Asia ([Global Fishing Watch](https://globalfishingwatch.org/?p=39532)). In Indonesia's Natuna Sea, satellite images showed at least 15 vessels not transmitting AIS around a single AIS signal from a Vietnamese vessel, apparently working as pair trawlers ([Global Fishing Watch](https://globalfishingwatch.org/?p=10233)).

**What changes from the Baltic version:** in the Baltic, ships switch their trackers *off*. In Southeast Asian waters, many boats never switch them *on*, and shore AIS coverage is thin. So the core shifts from spotting gaps to **detecting boats directly from space, then checking whether they are broadcasting**. Anything seen but silent is a lead.

**The decision becomes patrol planning:** "Which patches of sea will have the most dark fishing tonight, and where should the patrol boat go?" That is the same forecast-and-rank loop, pointed at areas instead of single ships.

### Alternative datasets to bring in

| Dataset | What it adds | Access |
| --- | --- | --- |
| Satellite radar (Sentinel-1, via Global Fishing Watch) | Sees metal hulls day or night, through cloud | Free for non-commercial use; roughly 5 days old |
| Night lights ([VIIRS boat detection](https://eogdata.mines.edu/products/vbd/), Earth Observation Group) | Spots boats using lights to attract catch, such as squid jiggers; started in Southeast Asia, now global | Nightly CSV files |
| Optical imagery (Sentinel-2) | Confirms a boat's size and type in daylight | Free; blocked by cloud |
| Government vessel monitoring (VMS) | Positions of licensed fleets; Indonesia shares its VMS through Global Fishing Watch | Via Global Fishing Watch, where countries share it |
| Fishing, encounter and loitering events (Global Fishing Watch) | Flags likely transshipment of catch at sea | Free API |
| Ocean conditions (sea temperature, chlorophyll) | Where fish are likely to be, so where illegal fishing is likely: a strong forecast input | Free scientific data services |
| Maritime boundaries and protected areas | Turns "a boat is here" into "a foreign boat is in someone else's waters" | Free boundary datasets |
| Radio-frequency detection (commercial) | Hears a ship's radar and radio even with AIS off | Paid |

Night lights alone are striking: Global Fishing Watch reports that more than 85% of the fishing vessels in the VIIRS database do not broadcast AIS or publicly shared VMS ([Global Fishing Watch](https://globalfishingwatch.org/?p=7776)).

**How the fusion works:** match every radar, light or optical detection against AIS and VMS positions within a few kilometres and minutes. Matched means a known boat; unmatched means dark. The forecast then learns where and when unmatched detections cluster, by season, moon phase, sea temperature and distance from borders.

### After the hackathon

1. Add the radar and night-light layers to the Baltic build, so dark ships are *seen*, not only inferred.
2. Run the same pipeline on the Natuna Sea as a second region.
3. Swap the watchlist for nightly patrol recommendations, scored against what radar later confirms.
4. Approach Global Fishing Watch and regional fisheries agencies, who already work with these datasets.

## Energy markets: the Strait of Hormuz and other chokepoints

Pointing the engine at oil chokepoints is feasible and is the strongest fit for the quant sponsors, but the Gulf is much harder than the Baltic: its AIS data is heavily corrupted by GPS jamming. Treat it as the post-hackathon extension, demoed with historical data.

### Why Hormuz matters right now

- **Scale:** about 20 million barrels a day, roughly one-fifth of world oil consumption and over a quarter of seaborne oil trade, passed through the strait in 2024 and early 2025 ([EIA](https://eia.gov/todayinenergy/detail.php?embed=true&id=65504)).
- **Disruption:** after the conflict that began on 28 February 2026, transits fell 97% in March ([Windward Q1 2026 report](https://windward.ai/knowledge-base/q1-2026-maritime-risk-report/)). A public tracker citing UKMTO put shipping at roughly 70% below pre-conflict levels in the week to 30 October ([Hormuz briefing, 2 Nov](https://political.org/strait-of-hormuz-archive/iran-briefing-2026-11-02/)).
- **The data problem:** in August 2026, 61.2% of transits logged through the strait were false, created by GPS jamming rather than real ships ([Windward](https://windward.ai/knowledge-base/gps-jamming-and-false-transits-in-the-strait-of-hormuz/)). Some tankers also cross with AIS deliberately off.

That last point is the opportunity. Anyone counting raw AIS crossings gets the supply picture wrong. A tool that **removes false transits and estimates dark ones** has a genuine edge.

### What we would measure, and what it means for oil markets

| Signal | How we get it | Market meaning |
| --- | --- | --- |
| Laden tankers leaving the Gulf | Direction plus draught (a full tanker sits lower in the water) | Real supply reaching the market |
| False transits removed | Our area-wide jamming check: many ships jumping together | A cleaner count than raw AIS |
| Dark crossings (estimated) | A tanker vanishes west of the strait and reappears east of it | Hidden supply, often sanctioned |
| Loaded tankers waiting | Laden ships anchored for days | Supply that is stuck |
| Rerouted exports | Saudi crude leaving via Yanbu on the Red Sea instead | Supply bypassing the strait |

### Other places the same approach applies

| Location | What is hidden | Why traders care |
| --- | --- | --- |
| Off Malaysia (Eastern Outer Port Limits) | Iranian oil moved ship-to-ship onto other tankers, often with AIS off; 42 such transfers documented since 28 February ([Manila Bulletin](https://mb.com.ph/2026/05/14/malaysia-says-iranian-oil-transfers-near-its-waters-exploit-a-maritime-loophole)) | Iranian barrels reaching China |
| Bab el-Mandeb (Red Sea) | Transits under the Houthi blockade on Saudi Arabia declared on 20 July 2026 ([Reuters via Chronicle.lu](https://chronicle.lu/category/international/62944-hormuz-traffic-slows-as-uncertainty-over-waterway-persists)) | Red Sea exports and rerouting |
| Baltic and Black Sea Russian ports | Shadow-fleet loadings (our Baltic build) | Russian export volumes |
| US Gulf Coast | Mostly honest AIS | Ground truth to validate our estimates against official weekly figures |

### How it feeds a price model

1. **Build a daily estimate** of oil leaving each chokepoint: verified laden tankers + estimated dark crossings, minus false transits.
2. **Validate it** where official numbers exist. The US EIA publishes weekly crude imports and exports through a free API ([Weekly Petroleum Status Report](https://www.eia.gov/petroleum/supply/weekly/)).
3. **Use it as one input** to forecast Brent price moves, tanker freight rates, or the next official inventory figure.

Be honest about the size of the edge. One study found AIS-derived oil movements do help predict the oil price, but the added explanatory power was marginal ([NHH](https://openaccess.nhh.no/nhh-xmlui/handle/11250/2560514)). Commercial firms such as Kpler, Vortexa and Kayrros already sell tanker-flow data to traders. Our angle is narrower and defensible: an open, explainable correction for jamming and dark crossings.

### Feasibility

| Question | Answer |
| --- | --- |
| Can we build it in 24 hours? | Not live. As a historical study around 28 February 2026: yes, if the data loads quickly |
| Historical data | Global Fishing Watch's vessel presence dataset covers 2012 to about 4 days ago, free for non-commercial use ([GFW](https://globalfishingwatch.org/our-apis/documentation/docs/v3/general-api-doc/key-concepts)) |
| Live data | AISStream's coverage in the Gulf is untested; check it in the first hour |
| Biggest risk | Jamming makes positions unreliable, so radar or optical imagery is needed to confirm anything important |

See the third mockup board, "Energy flows: Strait of Hormuz", for how this could look.

## How this compares with Palantir and existing tools

As a business, this idea is largely already served, more by specialist maritime firms than by Palantir. As a hackathon project that doesn't matter: the judges want a hidden signal found and a forecast tested, and we can have a clear, honest edge on transparency and measured accuracy.

### Palantir

Palantir sells platforms rather than ship data. **Gotham** serves government missions and investigations, and **Foundry** (the commercial product) serves commercial and civil operations; both share the same data model, are delivered by **Apollo**, and run **AIP**, its AI platform ([B.D. Emerson](https://www.bdemerson.com/article/palantir-gotham)).

Gotham does do this kind of work. In Palantir's own notional demo, it fuses data from many sources, flags a warship going dark, and projects its likely routes ([summary of Palantir's video](https://lilys.ai/en/notes/palantir-20260127/palantir-gotham-defense)). Palantir also partners with data owners, such as Saildrone's ocean drones, to fuse their data for maritime intelligence ([Naval News](https://www.navalnews.com/naval-news/2025/03/saildrone-and-palantir-announce-strategic-partnership-to-advance-ai-powered-maritime-intelligence/)).

So Palantir is the operating system a navy or a bank would run something like this on. It is not competing with a single detector; our detector is the kind of model that would be plugged into it.

### The specialists

| Tool | For whom | What it does | Cost | Overlap with us |
| --- | --- | --- | --- | --- |
| Palantir Gotham / Foundry | Defence, government, large firms | General data fusion and decision platform | Enterprise contracts | Platform, not a competitor to the detector |
| [Windward](https://windward.ai/?p=36099) | Sanctions compliance, traders, insurers; BP, Shell and HSBC among users ([City AM](https://www.cityam.com/?p=1811280)) | Dark activity, spoofing and risk scores, fused with satellite data | Paid, enterprise | High: Baltic shadow fleet and Hormuz |
| [Skylight (Ai2)](https://www.geekwire.com/2026/ai2s-skylight-project-launches-shippy-an-ai-agent-that-dives-into-ocean-data/) | Governments, fisheries bodies, NGOs; 300+ organisations in about 70 countries | Radar and night-light detection of dark vessels, dark rendezvous alerts | Free for qualifying users | High: Southeast Asia fishing |
| Global Fishing Watch | Researchers, governments, public | Open data on fishing, gaps and radar detections | Free, non-commercial | Our data source as much as a rival |
| Kpler, Vortexa, [Kayrros](https://www.kayrros.com/products/off-the-radar-detection-for-traders/) | Commodity traders | Tanker flows, inventories, counts of vessels with AIS off | Paid | High: energy market signal |

### So is the idea trumped?

**As a product, mostly yes.** The incumbents have paid satellite and radio data, years of labelled history and analyst teams. We will not out-detect them in 24 hours, and we should not claim to.

**As a hackathon entry, no.** What we can show that they mostly don't:

1. **Every flag shows its evidence:** "14 ships nearby still heard", "implied speed 61 knots". Most commercial tools are black boxes.
2. **Free data only.** Anyone can reproduce and audit the result.
3. **A published forecast score:** precision in the top 10 against simple baselines, and forecasts made at the start of the hackathon checked by the end. Vendors rarely publish accuracy.
4. **The jamming problem made explicit.** Windward itself found most logged Hormuz transits in August were false, which shows the correction is worth making.

**If a judge asks "isn't this just Windward or Palantir?":** "Yes, the category exists and is valuable. We built an open, testable version in a day, and here is how accurate it is."

## Sources

- [AISStream documentation](https://aisstream.io/documentation) and [issue tracker](https://github.com/aisstream/issues/issues)
- [Digitraffic marine traffic](https://digitraffic.fi/en/marine-traffic)
- [OpenSanctions maritime dataset](https://www.opensanctions.org/datasets/maritime/)
- [OpenSanctions: tanker leaving Venezuela in dark mode](https://www.opensanctions.org/entities/NK-bcokCDJNYi7ztnQjV7Az3W)
- [Global Fishing Watch: 75% of industrial fishing vessels hidden from public view](https://globalfishingwatch.org/?p=39532)
- [Global Fishing Watch: dark vessels in the Natuna Sea](https://globalfishingwatch.org/?p=10233)
- [Global Fishing Watch: VIIRS night-light detections](https://globalfishingwatch.org/?p=7776)
- [Global Fishing Watch: SAR vessel detections API](https://globalfishingwatch.org/our-apis/documentation/docs/v3/4wings)
- [Earth Observation Group: VIIRS boat detection](https://eogdata.mines.edu/products/vbd/)
- [EIA: Strait of Hormuz remains critical oil chokepoint](https://eia.gov/todayinenergy/detail.php?embed=true&id=65504)
- [Windward: Q1 2026 maritime risk report](https://windward.ai/knowledge-base/q1-2026-maritime-risk-report/)
- [Windward: GPS jamming and false transits in the Strait of Hormuz](https://windward.ai/knowledge-base/gps-jamming-and-false-transits-in-the-strait-of-hormuz/)
- [Strait of Hormuz briefing, 2 November 2026](https://political.org/strait-of-hormuz-archive/iran-briefing-2026-11-02/)
- [Manila Bulletin: Iranian oil transfers near Malaysian waters](https://mb.com.ph/2026/05/14/malaysia-says-iranian-oil-transfers-near-its-waters-exploit-a-maritime-loophole)
- [Reuters via Chronicle.lu: Hormuz traffic and Bab el-Mandeb](https://chronicle.lu/category/international/62944-hormuz-traffic-slows-as-uncertainty-over-waterway-persists)
- [EIA Weekly Petroleum Status Report](https://www.eia.gov/petroleum/supply/weekly/)
- [NHH: AIS data and the price of oil](https://openaccess.nhh.no/nhh-xmlui/handle/11250/2560514)
- [Global Fishing Watch: API datasets](https://globalfishingwatch.org/our-apis/documentation/docs/v3/general-api-doc/key-concepts)
- [B.D. Emerson: Palantir Gotham vs Foundry](https://www.bdemerson.com/article/palantir-gotham)
- [Summary of Palantir's Gotham defence demo](https://lilys.ai/en/notes/palantir-20260127/palantir-gotham-defense)
- [Naval News: Saildrone and Palantir partnership](https://www.navalnews.com/naval-news/2025/03/saildrone-and-palantir-announce-strategic-partnership-to-advance-ai-powered-maritime-intelligence/)
- [Windward: risk and compliance](https://windward.ai/?p=36099)
- [City AM: Windward customers](https://www.cityam.com/?p=1811280)
- [GeekWire: Ai2's Skylight](https://www.geekwire.com/2026/ai2s-skylight-project-launches-shippy-an-ai-agent-that-dives-into-ocean-data/)
- [Kayrros: off-the-radar detection for traders](https://www.kayrros.com/products/off-the-radar-detection-for-traders/)
