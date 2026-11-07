# mt-methods: how MarineTraffic (Kpler) does it, and what we can borrow

*Track mt-methods, MarineTraffic wave, Sat 7 Nov 2026, ~18:20–19:05 UTC. Public material only: MarineTraffic's support centre, Kpler's public API documentation and Kpler's blog. No account, no map endpoints, nothing scraped. Everything read today; pages are undated unless stated. Labels: `measured` = I ran it; `documented` = the operator's own published text; `vendor claim` = their marketing; `unverified` = lead I could not confirm.*

## Bottom line

1. **Their method is published, with numbers.** The support centre's event table gives the thresholds: terrestrial silence becomes OUT_OF_RANGE after **1 h**, the satellite/global channel after **3 h**, a compliance-grade gap needs **>20 h** with coverage at start *or* end, speed state flips at **<1 kn / >3.5 kn**, and proximity is **<2× the longer vessel's length** (`documented`).
2. **Their dark-activity claims are never AIS-only.** "Dark STS" and "Dark port call" are "verified using satellite imagery", and the published per-vessel field is literally `AIS on / AIS off / AIS spoofing` (`documented`). That is our idea as a product, and it sets the honest bar: imagery corroboration plus a stated coverage control.
3. **Their spoof test is cheap:** predict the next position from current motion, compare with the reported fix, flag the discrepancy, escalate with imagery, "AIS trajectory validation" or "AIS coverage validation", and publish an estimated true location (`documented`). Spoofed positions stay on the map and are excluded only from analytics once confirmed — a raw-layer / cleaned-layer split.
4. **Silence is a state machine, not a flag.** AIS_OFF (inside their coverage) is a different event from OUT_OF_RANGE, OUT_OF_GLOBAL_RANGE and SHIP_LOST, with hysteresis (out at 1 h, back after 2 h), 24 h map removal, and a deliberate 1–3.5 kn dead band.
5. **Two data-model lessons we can use tonight:** keep the raw feed (their cleaning is deliberately shallow and every position carries source and receive time), and store identity changes as events rather than overwriting a vessel row.

## Findings

### 1. Port calls

- Port level (ARRIVAL, DEPARTURE and their estimated versions) and berth level: DOCK/UNDOCK records carry `BERTH_ID`, `TERMINAL_ID`, port UN/LOCODE and **local and UTC timestamps plus the offset** (`documented`, public API example).
- Port geography is polygons, not circles: their Data Quality page shows Singapore "colour-coded … the port itself, the anchorage, the terminals, and berths", from port authorities, charts, crowdsourcing and AIS with manual checks (`documented`). **The arrival predicate itself is not published** — polygon test, dwell time, speed cut-off unknown (`unverified`).
- Ambiguity gets its own events: WAITING_OPL (stopped near a port's outer perimeter), PROXIMITY_PORT (repeats at distance intervals until arrival), STOPPED/UNDERWAY suppressed in port or anchorage (`documented`).

### 2. ETAs and routes

- They separate **reported ETA** (the AIS field) from **predicted ETA**: Route Forecast is a polyline with waypoints, expected time and distance at each, distance-to-go and ETA at destination, colour-coded by speed, with a weather band; prediction vectors extrapolate ~30 minutes; a 7-day forecast is in the mobile app (`documented`).
- A forecast needs a **valid declared destination** and enough recent movement, and is absent for stationary or intermittently transmitting vessels; their troubleshooting says it inherits whatever the crew typed (`documented`).
- ARRIVAL_DELAY_RISK fires when position and speed imply a late arrival against the reported ETA — cheap on data we already have (`documented`). Kpler's Predictive Schedules API claims port-call forecasts 6 weeks ahead from "AIS, historical behavior, and ML", refreshed every 30 min over 6,000+ container vessels (`vendor claim`).

### 3. Bad positions, spoofing and identity

- **Cleansing, published and dated**: check values against the AIS standard; drop coordinates 91/181; drop invalid MMSI (ships 9-digit, base stations 7-digit); drop IMO longer than 7 digits (no checksum validation); drop positions over land (**feature on since 2019-08-27**). They explicitly *do not* clean unintelligible names or destinations, impossible dimensions or speeds, "or other data errors"; the raw feed is available (`cleansed=false`, TCP stream) (`documented`). So their "cleaned" layer is shallow by choice — raw stays authoritative, which matches our own duplicate and sentinel findings.
- **Spoofing method**, in their words: predict → compare → identify discrepancies → flag → report, with each event sourced from satellite imagery, AIS trajectory validation, AIS coverage validation, or analyst input, including an estimated true location; scope tankers and dry bulk (`documented`).
- **Identity manipulation** is a product field: a "zombie vessel" using a scrapped or inactive vessel's identity, or duplicate identities, from AIS + imagery + reference data, naming both the transmitting and impersonated vessel (`documented`). Note that their flag is **derived from the MMSI's first three digits (MID)**, which is why FLAG_CHANGED is an AIS-transmission event and false flags need registry checks; ownership is modelled in seven layers with start and end dates (`documented`).
- Kpler's April 2026 blog names four signatures "identifiable from the signal data alone": **circular loop** (orbit at impossible speed), **teleportation**, **static ghost** (frozen broadcast while the ship moves), **identity clone** (two vessels on one MMSI). The passive GNSS signature is many vessels converging on one false position, "often a land-based point well inland" (`vendor claim` framing; patterns `documented` as their taxonomy).
- That is exactly what `t-ais-live` measured tonight: five unconnected vessels on one inland coordinate at 57.67 N 32.53 E with impossible speeds (`measured`, other track). Their taxonomy gives it a name and a rule: cluster-level and cell-level, never ship-only.

### 4. Merging shore and satellite

- Every fix carries a **source**: Terrestrial, Satellite, or **Roaming** ("a shared network of AIS receivers", i.e. third-party networks), alongside a "Data received on" timestamp; the page warns that a terrestrial-sourced fix far offshore may simply be old (`documented`, also `mt-sources`).
- Merging is deliberately unsorted: terrestrial is published immediately, satellite comes down in bursts, "we don't store our AIS messages in a buffer and sort them before publishing", so **messages arrive out of timestamp order**; satellite download prioritises the freshest message per MMSI and backfills older ones later (`documented`). Consequence for us: dedupe and sort on (MMSI, timestamp, message type) rather than arrival order.
- Two documented satellite limits that matter for our regions: **collisioning** — a ~2,000 km footprint over a high-traffic zone decodes *fewer* messages, explicitly South China Sea and Mediterranean, against terrestrial reception working within ~80 km (`documented`); and Class B signals being weaker (`documented`). Dynamic AIS™ (2,860+ satellite-enabled receivers on ships, 60 nm, ≥ every 15 min) is their answer (`vendor claim`).
- Downsampling is stated twice and differs by product: the website and stored positions keep **one position per MMSI per minute** in range, and 3–20 min for history older than 3 months (`documented`); the Messages API and TCP stream default to **one message per MMSI per message type per 5-minute window**, first one kept, full feed on request (`documented`; 2021 example 80 M vs 300 M+ messages/day). Satellite and Dynamic AIS are not downsampled.

### 5. Ships that disappear

| Tier | Rule | Purpose |
|---|---|---|
| Display | no fresh position for 24 h → removed from Live Map until a new fix | map hygiene |
| Coverage-aware | AIS_OFF: signal lost "although the vessel is sailing within an area covered by MarineTraffic" | suspicion; needs a coverage model |
| Compliance gap | >20 h, coverage at start or end, plus draught change for amber; red reserved for a named Mideast Gulf port list | alerting |

Amber gaps are "global" (outside ports/anchorages), "port/anchorage" (between different ports) or "high risk area" (sanctioned zones), each requiring a **draught change**; red gaps drop the draught requirement because the named Iraqi/Kuwaiti terminals are the signal — Khor Al Zubair, VS Oil Terminal, Umm Qasr South, Umm Qasr LPH, Al Basrah (`documented`). Gaps shorter than 20 h are outside their compliance product — the same trade-off `d-methods` found in Welch et al., at a much lower threshold.

## Source rows

| Source | Operator | Type | Regions | Access route | Account or cost | One record contains | Update rate | Delay | Identifies the ship? | Licence, limits | Used by MarineTraffic? | Usable by us? | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| Support centre event table | MarineTraffic/Kpler | method doc | global | `support.marinetraffic.com/en/articles/9552887` | none | 90+ events with definitions and thresholds | page updated ~3 weeks ago | n/a | yes | public page, no reuse licence stated | it *is* their spec | **yes** — thresholds to copy | `documented` |
| Support centre R&C methodology | MarineTraffic/Kpler | method doc | global | `…/11172276-risk-compliance-methodology` | none | gap rules, red-port list, dark STS/port-call confirmation, spoof/identity/GNSS-interference methods, 7 ownership layers | refresh 6×/day from 00:30 UTC | n/a | yes | public page | yes | **yes** — single most useful page | `documented` (bullets recovered from HTML) |
| Support FAQ set | MarineTraffic/Kpler | doc | global | articles 9552924, 9552905, 12116057, 14594297, 9552869, 15445010 | none | 24 h removal, downsampling, source labels, packet collision, prediction vectors | — | — | yes | public page | yes | yes — data-model constraints | `documented` |
| Kpler AIS Fundamentals | Kpler | doc | global | `servicedocs-sm.kpler.com/ais-fundamentals/` | none to read | cleansing list (dated 2019-08-27), 5-min downsampling, out-of-order publishing, collisioning | — | — | yes | public docs | yes | **yes** — the cleansing and merge spec | `documented` |
| AIS API reference | MarineTraffic | API docs | global | `servicedocs.marinetraffic.com` | key to call | DOCK/UNDOCK with berth, terminal, UN/LOCODE, local+UTC+offset | per contract | per contract | yes | contract terms | yes | partial — schema inspiration | `documented` example |
| Kpler blog, spoofing vs GNSS (27 Apr 2026) | Kpler | vendor analysis | 6 corridors incl. Hormuz, Red Sea, Baltic | `kpler.com/blog/ais-spoofing-vs-gnss-interference…` | none | 4 active signatures; passive = multi-vessel convergence inland; 4 corroborating layers | — | — | n/a | marketing | adjacent line | **yes** — signature list; "AIS alone cannot say where the ship was" | `vendor claim` for figures (25×, 24,000 vessels, 80%) — do not repeat |
| Kpler help: Iranian Oil Tracking Methodology | Kpler | method doc | Iran/Malaysia STS | `help.kpler.com/en/articles/5031070` | **HTTP 401** | unknown | — | — | — | gated | yes | **no** | `measured` 401 |
| Google Patents | Google | index | — | `patents.google.com/xhr/query` | none | — | — | — | — | — | — | **none found** (0 for `assignee:Kpler` + AIS tracking; text query unrelated) | `measured`, 3 queries |

No MarineTraffic/Kpler patent was found; any patent-derived claim about their internals would be invented.

## What this means for us

- **Borrow the ladder, not the labels.** Fresh / silently-inside-coverage / compliance gap maps onto free data. `t-ais-live`'s neighbour-and-rate test is a cheap stand-in for "coverage available at start or end", holding in 94% of gaps (`d-methods`). Our 20-minute Baltic gaps are far below 20 h, so the claim stays "short gap with reception control".
- **Never one silence flag, and name the sense.** Separate 1 h terrestrial and 3 h global thresholds exist because shore and satellite are different sensors. If every fix carries `source` and `coverage_basis`, the rule extends to radar: a radar-seen hull is coverage evidence where AIS is not.
- **Identity as an event log.** NAME_CHANGED, FLAG_CHANGED and identity manipulation line up with the synthesis finding that most "silent" tankers returned under a new MMSI. Flag is MID-derived, so a reflag usually arrives as a new MMSI; an append-only identity log plus IMO confidence lets a demo show the change honestly.
- **Keep raw and derived layers apart.** Their display samples to 1/min (5 min on the API) and they keep the unclean feed, because every cleaning rule is also a signal. Our silence analysis needs 9–10 s intervals and duplicate filtering, so store full-rate raw and derive display views.
- **Cheap spoof screen tonight:** impossible speed between consecutive fixes, inland cluster, one MMSI in two places, frozen position while a radar track moves. Report cluster and cell, pair with GPSJam for the same hours (`d-methods`).
- **ETA features are in reach:** destination on 92% and ETA on 98% of Digitraffic vessels (`measured`, other track). Reported ETA against speed-and-distance ETA is a defensible borrowed feature, labelled crew-typed and often stale.
- **Map semantics:** age out stale vessels (24 h is their number), show last-fix age and source, never interpolate across a gap.

## Unknowns

- The arrival predicate (polygon, dwell, speed) is unpublished; one free account and a port-call list against our own polygon test would settle it.
- What "AIS coverage validation" actually uses — their station map, a neighbour test, or satellite AIS. This is the one component we would have to substitute.
- Whether the red-gap port list is stable product configuration.
- Their current satellite supplier and merge order (mt-sources' lane); the Fundamentals page predates the Spire acquisition.
- Kpler's Iranian Oil Tracking Methodology (401) likely holds their detailed spoof/loitering rules.

## Sources

- `support.marinetraffic.com/en/articles/9552887-what-is-the-significance-of-the-marinetraffic-events` — full event table with thresholds (1 h / 3 h / 20 h / 1–3.5 kn / 2× length).
- `…/11172276-risk-compliance-methodology` — gap rules, red-port list, dark STS and dark port calls confirmed by imagery, spoof and identity methods, GNSS interference scope and 4-hour cycle.
- `…/11588240-understanding-ais-gnss-spoofing` — spoofed positions still displayed, excluded from analytics when confirmed; hot zones.
- `…/9552924` (24 h removal), `…/9552905` (AIS intervals, downsampling), `…/14594297` (Terrestrial/Satellite/Roaming labels), `…/9552869` (satellite packet collision), `…/12116057` (irregularity causes), `…/9812808` (port/berth polygons), `…/15445010` (prediction vectors), `…/9552768` (route forecast), `…/11640882` (Predictive Schedules API).
- `servicedocs-sm.kpler.com/ais-fundamentals/` — cleansing list, 5-minute downsampling, out-of-order publishing, download priority, high-traffic-zone collisioning, Dynamic AIS.
- `servicedocs.marinetraffic.com/tag/Single-Vessel-Events/` — DOCK/UNDOCK payload.
- `kpler.com/blog/ais-spoofing-vs-gnss-interference-why-the-distinction-decides-the-claim` (27 Apr 2026) — three signal types, four signatures, six corridors, four corroborating layers.
- `help.kpler.com/en/articles/5031070-iranian-oil-tracking-methodology` — HTTP 401.
