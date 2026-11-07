# mt-access: MarineTraffic pricing, plans and data terms

*Track mt-access, MarineTraffic wave, Sat 7 Nov 2026, 18:17–19:10 UTC. Public pages only: no account, no payment, no login, no private endpoints. Labels: `measured` = I ran it here; `documented` = the operator's published text; `vendor claim` = marketing; `unverified` = lead I could not confirm.*

## Bottom line

1. **No self-serve MarineTraffic/Kpler API and no published API price.** API access is sales-led, metered in credits against a signed contract: the public API docs still ship `/exportcredits` with a `CREDIT_BALANCE` field, but Kpler's data-services page is a "book a meeting" page with no numbers (`documented`, 2026-11-07).
2. **MarineTraffic's own marketing pages are closed to me.** `www.marinetraffic.com` returned **HTTP 403** for every page tried (`/en/online-services/plans`, `/en/p/academic`, `/p/terms`, `/en/p/api-services`) to both `curl` and the fetch tool (`measured`). Not worked around, so **current official prices and current site terms are unverified**. The help centre and the API docs site are open and carry most of this report.
3. **The only historically cheap bulk route was an academic one: EUR 30/month** for a "Research Plan" that included a regional API/NMEA feed and 250,000 historical positions a year — `documented` but from a **2017** archive capture. The page began redirecting in June 2018 and today's academic page is 403. If it still exists, it is the one MarineTraffic offer that fits a hackathon budget.
4. **Buying a consumer plan cannot supply a dataset.** Export allowance is capped per account per month: **Basic 5 rows, Essential 300, Enterprise 10,000** (`documented`, Oct 2026). One Sentinel-1 scene needs thousands.
5. **The terms forbid what a public demo would do.** Kpler's Terms of Use: no derived data "in any way", no reproduction or publication, no mirroring, purge on exit, no use in advertising without consent (`documented`). Storing positions to train or validate a model needs written agreement, not a subscription.

## Findings

### A. Free tier (`documented`, help centre, updated Oct 2026)

Free account: live map, vessel search, custom areas, notifications, small fleet. **Satellite AIS is not included** — "Viewing Satellite AIS position data requires a Mobile Pro Plan subscription" — so the one thing MarineTraffic has that our free feeds lack sits behind at least a mobile subscription.

### B. Plans and prices

Names: **Basic, Essential, Enterprise**; Enterprise is "our only sales-assisted offering" and its quote form needs a company email (`documented`). **Essential** = satellite tracking for **one** vessel via "SAT Flex", 7-day port calls and replays; **Enterprise** = unlimited satellite tracking, 5-year position history, 5,000-vessel fleet, 10,000 export rows/month, 2,000 custom areas.

**Prices could not be read from the vendor** (`measured` 403). Three third-party pages dated 2026 agree on **Basic US$10/month (US$100/year), Essential US$100/month (US$1,000/year)**, one claiming it recorded them from the official page in August 2026 (`unverified` — stack.liuhuo.org, worldeye.app, argosatlas.com). Indicative only.

**Consumer credits and add-ons were withdrawn 23 January 2025** (Sat-Flexible, Export Data, Fleet 50/500) — `documented`, article 10442248. **Trial**: 7 days, once per plan, card/PayPal pre-authorisation, converts to paid automatically, "no refunds are possible", "single-user license" (`documented`). A trial is a purchase with a 7-day cancellation window, licensed to one person.

### C. The API

Surface (`documented`, servicedocs.marinetraffic.com, public ReDoc site): vessel track, single-vessel / static-fleet / custom-area positions, port calls, vessel events, berth calls, particulars, photo, ship search, voyage forecast, ETA to port, predictive destinations, expected and predictive arrivals, port congestion, route to port, reverse geocoding, fleets, **credit balance**, passage-plan import.

- **Hard cap: 100 requests/minute per key, successful or failed**, "regardless of this agreed limit", with the contractual limit set separately ("for example '2 calls per minute'") — `documented` in the `/exportcredits` notes.
- **Credits are metered but unpriced publicly**: `/exportcredits` returns `USER_ID`, `CREDIT_BALANCE`, `LAST_CHARGED`.
- **Extra fields cost more credits**: `msg_type=extended` "returns a lot more data but cost a lot more api credits as well" (`documented` in the vendor's own parameter doc, quoted in the amphinicy client README — `unverified` as current billing). Design hint: a cheap contract buys MMSI/lat/lon/SOG/COG/time and little else.
- **API is separate from the web plans** — keys live under My Account → API Services, and no help article binds API access to Basic/Essential/Enterprise. The $10/$100 plans do not buy bulk positions.
- No published free tier and no published academic tier.

### D. Academic and research access

- **The 2017 "AIS Data Research" page is the most concrete find** (`documented`, Wayback 2017-07-01 of `marinetraffic.com/en/p/ais-for-research`, saved locally). A **MarineTraffic Research Network** gave members: a **Research Plan** with terrestrial AIS global coverage, 50-vessel fleet, vessel particulars, 60-day voyage history, **3,000 export rows/month**; **historical data on request, up to 250,000 positions/year (CSV)**; and **"AIS current data: NMEA or API data feed for your region (area defined based on vessel density)"**. Cost: **"FREE for data contributors. Subscription fees for non-contributors: EUR 30 for monthly billing or EUR 300 for annual billing."**
- Caveats: it is **nine years old**; CDX shows 200 up to 2017-07-01, **301 from 2018-06-01**, no 200 captures since. And the feed is scoped to *"your region"*, defined by vessel density — for a UK team that probably means UK/North Sea waters, not Hormuz. Both `unverified` today.
- Current status: `/en/p/academic` is 403 (`measured`). A third-party page (European MSP Platform) says "academics can ask the Academic Relations Team for support" — `unverified`, but consistent with the programme having existed. My later Wayback attempts returned **429**.
- Public-sector precedent: a **"Non-exclusive AIS data access and licence of use agreement", 15 Dec 2021, UK Cabinet Office and Exmile Solutions Ltd (MarineTraffic)** on Contracts Finder (`documented` that it exists; attachment 403 to me) — shape of a real deal, no price.

### E. Terms that decide our use

From Kpler's current Terms of Use (fetched 2026-11-07): not to "(attempt to) download, reverse engineer, modify, aggregate or decompile the Data … or create derived data from the Data, in any way"; not to "copy, (sub)licence, (re)sell, reproduce, duplicate or publish"; not to "transfer, forward or make available" to anyone not allowed access, or "mirror" it on another server; not to use it "in any advertising or marketing" without prior consent; no web scraping; "promptly delete and purge" Data at the end. Attribution to Kpler is required and does not cure the rest.

Read plainly: **showing MarineTraffic positions in the entry, deck or README, or training/validating a model on them, is outside the terms** even for a paying customer, absent written agreement. The 2023 capture of `/p/terms` is downloaded but I did not rely on it.

### F. Would a small paid test add anything?

What MarineTraffic has that free feeds do not: **terrestrial + satellite + "roaming" positions with the source labelled per position** in the UI. In the Gulf, Red Sea and Natuna — where AISStream returns nothing and GFW is ~4 days old — that is the only per-vessel ground truth available this weekend.

Every route is too small (300 rows/month), too slow (Enterprise quote needs a company email and a sales cycle), or legally unusable for a demo. **A one-month Essential subscription (~US$100, unverified) buys a private answer to "was this hull transmitting then?" for one vessel at a time with 7-day replay** — a validation oracle for a handful of examples, not a data source. Concretely, it could check whether the ~3 tankers/day PortWatch counts at Hormuz are the same hulls Sentinel-1 sees. Useful internally; not publishable under these terms.

## Source rows

| Source | Operator | Type | Regions covered | Access route | Account or cost | What one record contains | Update rate | Delay | Identifies the ship? | Licence, limits | Likely used by MarineTraffic? | Usable by us? | Evidence |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| MarineTraffic web plans (Basic/Essential/Enterprise) | Kpler | consumer UI | global; satellite by tier | marinetraffic.com | free account; paid, 7-day trial | map position, port calls, replays, CSV export | seconds on map | seconds–minutes | yes | single-user, no refunds; 5/300/10,000 export rows per month | n/a (is the product) | **No** for bulk; private oracle only | `documented`; price page 403 |
| MarineTraffic AIS API | Kpler | API, contract | global | spec at servicedocs.marinetraffic.com | sales contract, credits; no public price | MMSI, lat/lon, SOG/COG/heading, timestamp; more fields = more credits | per contract | seconds–minutes | yes | 100 req/min hard cap; credits; no derived data, no publishing | n/a | **No** — no price, no self-serve, terms bar demo use | `documented` |
| Research Network / Research Plan | MarineTraffic (now Kpler) | academic, barter or subscription | global terrestrial; API/NMEA "for your region" | membership application (2017 terms) | free for contributors; **EUR 30/month or 300/year** (2017) | fleet of 50, particulars, 60-day history, 3,000 export rows/month; ≤250k historical positions/year; regional feed | real time (feed) | seconds–minutes | yes | research use, region-scoped; unknown today | n/a | **Possibly** — one enquiry | `documented` 2017 archive; current status `unverified` |
| Academic access (current) | Kpler | unknown | unknown | `/en/p/academic` | unknown | unknown | unknown | unknown | unknown | unknown | n/a | **Unknown** — 403 | `measured` |
| AIS-station reward | Kpler | barter | wherever the station is | register station | free hardware + hosting | plan tiers; own data + volume-matched NMEA stream | real time | seconds | yes | personal use, volume-matched, NMEA 0183 TCP/UDP | n/a | Only if a station exists there | `documented` |
| Roaming AIS (vessel-hosted) | Kpler | contributed | wherever contributing ships sail | ship wires transponder to a converter → `listener.marinetraffic.com` | free to the vessel | at-sea positions labelled "Roaming" | minutes | minutes | yes | partnership terms | **Yes** — a named MT source type | No (no ships) | `documented`, 28 Oct 2025 |
| Kpler maritime data services | Kpler | enterprise data | global | kpler.com, book a meeting | contract, quote | AIS archive since 2010, live NMEA option | real time | seconds–minutes | yes | Kpler ToU: no derived data, no publishing, purge | n/a | **No** | `vendor claim` + `documented` ToU |

## What this means for us

- **Rule out** MarineTraffic as a data layer for the entry: the export caps and the licence each independently kill it, whichever plan is bought.
- **Keep one narrow use:** an optional private spot-check of a specific MMSI at a specific time. It must not appear in the demo, README or deck.
- **Borrow the vocabulary, not the data.** MarineTraffic labels every position **Terrestrial / Satellite / Roaming** with the source timestamp. Our schema should carry `source`, `source_detail`, and `received_at` distinct from `fix_time`, because "AIS said nothing here" only means something if we also record who was listening.
- **Pitch line:** the cheapest commercial route to satellite AIS for one hull is a ~US$100/month consumer plan (`unverified`) with a 300-row cap; enterprise needs a quote. The free alternatives are the only ones whose licences allow a public demo.
- **Interface implication:** area polling is billed per returned row, not per call, and capped at 100 calls/minute.

## Unknowns

- **Whether the Research Plan still exists, at what price, and whether "your region" can be an area of research interest (the Gulf) rather than the applicant's home waters.** The single most valuable unknown here; one enquiry to Kpler Academic Relations settles it.
- Current official plan prices and the full comparison table — needs an unblocked network.
- Whether API access can be bought self-serve at all, and per-service credit costs; only a quote settles it. The 2021 Cabinet Office licence attachment may contain redacted prices.
- Whether Essential's SAT Flex yields satellite positions on the web map or only in the paid mobile tier (the two help articles imply different gates).
- Whether "Roaming" positions are sold through the API or shown only in the UI.

## Sources

- `servicedocs.marinetraffic.com/` + `/tag/Balances/` — endpoint list, 100 req/min cap, credit balance schema (spec text extracted from the ReDoc bundle).
- Help centre (`support.marinetraffic.com/en/articles/…`): 9552658 plans; 9552679 purchase; 12578604 free trial; 9552899 export caps; 9552907 SAT Flex; 9552653 account features; 14594297 terrestrial/satellite/roaming; 9552976 partner rewards (>40% availability → Essential + 50-vessel fleet, >85% → Enterprise); 9552990 partner data (NMEA TCP/UDP, personal use, volume-matched); 10248814 roaming partnership; 10442248 credits withdrawn 23 Jan 2025.
- `https://www.kpler.com/company/terms-of-use` — the licence prohibitions quoted in E.
- `https://www.kpler.com/product/maritime/data-services` — AIS archive since 2010, live NMEA, 13,000 receivers (vendor claim), no prices.
- Wayback 2017-07-01 capture of `marinetraffic.com/en/p/ais-for-research` — Research Network terms and EUR 30/300 pricing (`wb_research_2017.html`); CDX shows 301 from June 2018.
- Contracts Finder attachment `d830ae84-2a0d-4e87-a628-b7af18ea608b` — Cabinet Office / Exmile Solutions, 15 Dec 2021 (403 to me).
- Third-party price summaries, indicative: stack.liuhuo.org/en/discover/marinetraffic, worldeye.app/compare/marinetraffic-vs-vesselfinder, argosatlas.com/en/blog/is-marinetraffic-free/.
- Evidence and downloads: `$WAVE/data/mt-access/` (`art/`, `kpler_tou.txt`, `state.js`, `wb_*.html`); fetcher `$WAVE/scripts/mt-access/fetch_mt_pages.sh`.
